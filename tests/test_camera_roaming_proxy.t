use strict;use warnings;
use Test::More;
use File::Basename qw(dirname);
use Cwd qw(abs_path);
use File::Spec ();
use Socket qw(AF_UNIX SOCK_STREAM PF_UNSPEC);
use File::Temp qw(tempdir);
use IO::Socket::INET ();
use Time::HiRes ();
require File::Spec->catfile(dirname(dirname(abs_path(__FILE__))),'scripts','camera_roaming_proxy.pl');

my $identity=CameraRoamingProxy::validate_identity({version=>1,mac=>'00-11-22-33-44-55',serial=>'Fixture-Camera-Only',publicKeyPin=>'sha256//'.('A'x43).'='});
my $network=[{address=>'192.168.7.10',mask=>0xffffff00}];
my $id='12345678-1234-1234-1234-123456789ABC';
sub response {my(%change)=@_;my %field=(Uuid=>$id,Types=>'inquiry',MAC=>'00:11:22:33:44:55',DeviceSN=>'Fixture-Camera-Only',IPv4Address=>'192.168.7.64',%change);return '<?xml version="1.0"?><ProbeMatch>'.join('',map{'<'.$_.'>'.$field{$_}.'</'.$_.'>'}sort keys %field).'</ProbeMatch>';}
is(CameraRoamingProxy::parse_reply(response(),'192.168.7.64',$id,$identity,$network),'192.168.7.64','correlated local identity accepted');
for my $case([Uuid=>'other-request'],[Types=>'modify'],[MAC=>'11:22:33:44:55:66'],[DeviceSN=>'other-camera'],[IPv4Address=>'192.168.7.65']){
    ok(!defined(CameraRoamingProxy::parse_reply(response(@$case),'192.168.7.64',$id,$identity,$network)),'unmatched discovery rejected');
}
for my $xml('<!DOCTYPE bad>'.response(),response().'<junk/>',response().('x'x33000),response(DeviceSN=>'&entity;'),response().'<Uuid>extra</Uuid>'){
    ok(!defined(CameraRoamingProxy::parse_reply($xml,'192.168.7.64',$id,$identity,$network)),'malformed or unsafe XML rejected');
}
for my $host('0.0.0.0','127.0.0.1','224.0.0.1','192.168.7.0','192.168.7.255','192.168.7.10','192.168.8.64','192.168.7.064','http://evil'){
    ok(!CameraRoamingProxy::local_destination($host,$network),'non-local/self/broadcast/ambiguous destination rejected');
}
ok(CameraRoamingProxy::local_destination('10.20.9.64',[{address=>'10.20.1.10',mask=>0xffff0000}]),'customer /16 network supported');
ok(!CameraRoamingProxy::valid_mask(0xff00ff00),'non-contiguous netmask rejected');
my @verified;my $verify=sub{push @verified,$_[0];return $_[0] eq '192.168.7.99';};
is(CameraRoamingProxy::resolve_camera($identity,'192.168.7.64',$network,$verify,sub{['192.168.7.99']}),'192.168.7.99','stale cached address rejected by pin before accepting new address');
is_deeply(\@verified,['192.168.7.64','192.168.7.99'],'only expected local candidates checked without camera credentials');
ok(!defined(CameraRoamingProxy::resolve_camera($identity,undef,$network,sub{1},sub{['192.168.7.64','192.168.7.65']})),'conflicting verified identities fail closed');
@verified=();ok(!defined(CameraRoamingProxy::resolve_camera($identity,'203.0.113.5',$network,$verify,sub{['127.0.0.1','203.0.113.5']})),'discovery cannot redirect to arbitrary endpoints');
is_deeply(\@verified,[],'out-of-subnet destinations never reach network verifier');
for my $bad({%$identity,publicKeyPin=>''},{%$identity,serial=>'bad&entity'},{%$identity,mac=>'invalid'}){
    eval{CameraRoamingProxy::validate_identity($bad)};ok($@,'identity config fails closed');
}
my $late=CameraRoamingProxy::capture([$^X,'-e','close STDOUT; select undef,undef,undef,0.08;exit 0'],1);
ok($late->{ok},'stdout EOF waits for actual child completion');
my $start=Time::HiRes::time();my $timeout=CameraRoamingProxy::capture([$^X,'-e','sleep 10'],0.1);
ok(!$timeout->{ok} && Time::HiRes::time()-$start<1,'owned auxiliary timeout bounded');
my $big=CameraRoamingProxy::capture([$^X,'-e','print "x"x70000'],1);ok(!$big->{ok},'oversized child output rejected');

# A real bidirectional socket exchange proves transparent forwarding, half-close
# and cleanup. It does not claim RTSP/camera compatibility (separate Air gate).
socketpair(my $client,my $relay_client,AF_UNIX,SOCK_STREAM,PF_UNSPEC)or die;
socketpair(my $server,my $relay_server,AF_UNIX,SOCK_STREAM,PF_UNSPEC)or die;
my $pid=fork();die unless defined $pid;
if(!$pid){close $client;close $server;my $stop=0;local $SIG{ALRM}=sub{exit 9};alarm 3;CameraRoamingProxy::bridge($relay_client,$relay_server,\$stop);close $relay_client;close $relay_server;exit 0;}
close $relay_client;close $relay_server;
my $request="OPTIONS rtsp://127.0.0.1:18556/Streaming/Channels/101 RTSP/1.0\r\n\r\n";
syswrite($client,$request);shutdown($client,1);my $incoming='';while(sysread($server,my $chunk,4096)){$incoming.=$chunk;}
is($incoming,$request,'RTSP request bytes and client half-close forwarded');
my $reply="RTSP/1.0 200 OK\r\n\r\n".pack('C*',36,0,0,4,0,1,254,255);syswrite($server,$reply);shutdown($server,1);
my $received='';while(sysread($client,my $chunk,4096)){$received.=$chunk;}
is($received,$reply,'binary interleaved media response forwarded unchanged');close $client;close $server;waitpid($pid,0);is($? >> 8,0,'bridge exits after both streams close');
subtest 'two verified loopback streams can run at the same time' => sub {
    my $workspace=abs_path(tempdir(CLEANUP=>1));
    mkdir "$workspace/.local",0700 or die $!;
    open my $config,'>',"$workspace/.local/camera-roaming.json" or die $!;
    print {$config} JSON::PP::encode_json($identity);
    close $config;chmod 0600,"$workspace/.local/camera-roaming.json" or die $!;

    my $listen=sub {
        my $listener=IO::Socket::INET->new(LocalAddr=>'127.0.0.1',LocalPort=>0,Listen=>4,Proto=>'tcp') or die $!;
        return $listener;
    };
    my ($proxy,$camera)=($listen->(),$listen->());
    my ($proxy_port,$camera_port)=($proxy->sockport,$camera->sockport);
    my $pid=fork();die $! unless defined $pid;
    if(!$pid){
        close $camera;
        my $socket_new=\&IO::Socket::INET::new;
        no warnings 'redefine';
        local *IO::Socket::INET::new=sub {
            my ($class,%args)=@_;
            return $proxy if exists $args{LocalAddr};
            return $socket_new->($class,%args) unless exists $args{PeerAddr};
            return $socket_new->($class,%args,PeerAddr=>'127.0.0.1',PeerPort=>$camera_port);
        };
        local *CameraRoamingProxy::resolve_camera=sub {return '127.0.0.1';};
        my $result=eval{CameraRoamingProxy::run($workspace)};
        POSIX::_exit($@ ? 1 : $result);
    }
    close $proxy;
    my $connect=sub { return IO::Socket::INET->new(PeerAddr=>'127.0.0.1',PeerPort=>$proxy_port,Timeout=>1); };
    my $accept=sub {return IO::Select->new($camera)->can_read(1) ? $camera->accept : undef;};
    my $read=sub {
        my ($socket)=@_;
        return undef unless $socket && IO::Select->new($socket)->can_read(2);
        my $bytes='';
        return defined(sysread($socket,$bytes,4096)) ? $bytes : undef;
    };
    my ($first,$first_camera)=($connect->(),$accept->());
    my ($second,$second_camera)=($connect->(),$accept->());
    local $SIG{PIPE}='IGNORE';
    syswrite($first,'main') if $first;
    syswrite($second,'standard') if $second;
    is($read->($first_camera),'main','first stream stays open when second connects');
    is($read->($second_camera),'standard','second stream forwards independently');
    my $third=$connect->();
    is($read->($third),'','third connection is closed at the session limit');
    kill 'TERM',$pid;
    is($read->($first_camera),'','shutdown closes the first camera socket');
    is($read->($second_camera),'','shutdown closes the second camera socket');
    waitpid($pid,0);
    is($?,0,'proxy reaps owned connections before shutdown');
};
done_testing;
