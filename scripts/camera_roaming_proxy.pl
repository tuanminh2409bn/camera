#!/usr/bin/env perl
package CameraRoamingProxy;
use strict;
use warnings;
use Cwd qw(abs_path);
use File::Basename qw(dirname);
use File::Spec ();
use Fcntl qw(:DEFAULT :flock);
use IO::Socket::INET ();
use IO::Select ();
use JSON::PP ();
use POSIX qw(:sys_wait_h);
use Socket qw(IPPROTO_IP IP_MULTICAST_IF IP_MULTICAST_TTL IP_ADD_MEMBERSHIP inet_aton);
use Time::HiRes ();
use Errno qw(EAGAIN EWOULDBLOCK EINTR);

require File::Spec->catfile(dirname(abs_path(__FILE__)), 'air_recording_supervisor.pl');
use constant { LISTEN_PORT => 18556, CAMERA_PORT => 554, BUFFER_LIMIT => 65536 };

sub monotonic { Time::HiRes::clock_gettime(Time::HiRes::CLOCK_MONOTONIC()); }
sub ipv4_number {
    my ($value) = @_;
    return undef if !defined($value) || ref($value) || $value !~ /\A(?:0|[1-9][0-9]{0,2})(?:\.(?:0|[1-9][0-9]{0,2})){3}\z/;
    my @parts = split /\./, $value;
    return undef if grep { $_ > 255 } @parts;
    return unpack('N', pack('C4', @parts));
}
sub local_destination {
    my ($host, $networks) = @_;
    my $ip = ipv4_number($host);
    return 0 unless defined($ip) && ($ip >> 24) != 127 && ($ip >> 24) != 0 && ($ip >> 28) < 14;
    for my $network (@$networks) {
        my $own = ipv4_number($network->{address});
        my $mask = $network->{mask};
        next unless defined($own) && valid_mask($mask);
        my $base = $own & $mask;
        return 1 if $ip != $own && $ip != $base && $ip != ($base | (0xffffffff ^ $mask)) && ($ip & $mask) == $base;
    }
    return 0;
}
sub valid_mask {
    my ($mask)=@_;
    return 0 unless defined($mask) && $mask>=0xff000000 && $mask<=0xfffffffc;
    my $inverse=0xffffffff ^ $mask;
    return ($inverse & ($inverse+1))==0 ? 1:0;
}
sub validate_identity {
    my ($identity) = @_;
    die "Invalid camera identity\n" unless ref($identity) eq 'HASH' && ($identity->{version}//0) == 1;
    for my $name (qw(mac serial publicKeyPin)) {
        die "Invalid camera identity\n" unless defined($identity->{$name}) && !ref($identity->{$name});
    }
    die "Invalid camera identity\n" unless $identity->{mac} =~ /\A[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5}\z/i;
    die "Invalid camera identity\n" unless $identity->{serial} =~ /\A[A-Za-z0-9_.:-]{1,160}\z/;
    die "Invalid camera identity\n" unless $identity->{publicKeyPin} =~ m{\Asha256//[A-Za-z0-9+/]{43}=\z};
    my %copy = %$identity;
    $copy{mac} = lc $copy{mac}; $copy{mac} =~ tr/-/:/;
    return \%copy;
}
sub parse_reply {
    my ($xml, $source, $request_id, $identity, $networks) = @_;
    return undef if !defined($xml) || length($xml) > 32768 || $xml =~ /<!|&|\x00/;
    return undef unless $xml =~ m{\A\s*(?:<\?xml[^>]*\?>\s*)?<ProbeMatch(?:\s[^>]*)?>.*</ProbeMatch>\s*\z}s;
    my %fields;
    for my $name (qw(Uuid Types MAC DeviceSN IPv4Address)) {
        my @values = $xml =~ m{<$name(?:\s[^>]*)?>([^<]*)</$name>}g;
        return undef unless @values == 1;
        $fields{$name} = $values[0];
    }
    my $mac = lc $fields{MAC}; $mac =~ tr/-/:/;
    return undef unless $fields{Uuid} eq $request_id && $fields{Types} eq 'inquiry' &&
        $mac eq $identity->{mac} && $fields{DeviceSN} eq $identity->{serial} &&
        $fields{IPv4Address} eq $source && local_destination($source, $networks);
    return $source;
}
sub capture {
    my ($args, $timeout) = @_;
    pipe(my $reader, my $writer) or return {ok=>0,stdout=>''};
    AirRecordingSupervisor::_fd_cloexec($reader);
    my $pid = fork();
    if (!defined($pid)) {close $reader; close $writer; return {ok=>0,stdout=>''};}
    if ($pid == 0) {
        close $reader;
        open(STDIN, '<', '/dev/null') or POSIX::_exit(126);
        open(STDERR, '>', '/dev/null') or POSIX::_exit(126);
        open(STDOUT, '>&', $writer) or POSIX::_exit(126);
        close $writer;
        exec {$args->[0]} @$args or POSIX::_exit(127);
    }
    close $writer;
    my $select = IO::Select->new($reader);
    my ($data,$eof,$done,$status,$too_large) = ('',0,0,undef,0);
    my $deadline = monotonic() + $timeout;
    while (monotonic() < $deadline && !($eof && $done)) {
        unless ($done) {
            my $waited = waitpid($pid,WNOHANG);
            if ($waited == $pid) { $done=1; $status=$?; }
            elsif ($waited == -1) { $done=1; last; }
        }
        if (!$eof && $select->can_read(0.02)) {
            my $buffer=''; my $length=sysread($reader,$buffer,4096);
            if (defined($length) && $length==0) {$eof=1; $select->remove($reader);}
            elsif (defined($length)) {$data.=$buffer; if(length($data)>65536){$too_large=1;last;}}
            elsif ($! != EINTR) {last;}
        } else {Time::HiRes::sleep(0.01);}
    }
    close $reader;
    # EOF is not child completion. Wait for the owned PID before any signal.
    unless ($done) {
        kill 'TERM',$pid;
        my $until=monotonic()+0.3;
        while(monotonic()<$until){my $w=waitpid($pid,WNOHANG);if($w==$pid){$done=1;$status=$?;last;}Time::HiRes::sleep(0.01);}
        unless($done){kill 'KILL',$pid;waitpid($pid,0);}
        return {ok=>0,stdout=>''};
    }
    return {ok=>!$too_large && $eof && defined($status) && $status==0 ? 1:0,stdout=>$too_large?'':$data};
}
sub active_networks {
    my $list=capture(['/sbin/ifconfig','-l'],2); return [] unless $list->{ok};
    my @networks;
    for my $interface (split /\s+/,$list->{stdout}) {
        next unless $interface =~ /\Aen[0-9]{1,2}\z/;
        my $result=capture(['/sbin/ifconfig',$interface],2);next unless $result->{ok};
        next unless $result->{stdout}=~/^\s*status: active\s*$/m;
        while($result->{stdout}=~/^\s*inet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-f]+)\b/gmi){
            my($address,$mask)=($1,hex($2));next unless defined ipv4_number($address);
            push @networks,{interface=>$interface,address=>$address,mask=>$mask};
        }
    }
    return \@networks;
}
sub pin_verified {
    my ($host,$pin)=@_;
    # No credentials are supplied. Pinning is enforced even with a self-signed
    # camera certificate; never retry without the expected public-key pin.
    my $result=capture(['/usr/bin/curl','-q','--silent','--noproxy','*','--connect-timeout','2',
        '--max-time','4','--insecure','--pinnedpubkey',$pin,'--head','--output','/dev/null',
        '--write-out','%{http_code}','https://'.$host.'/'],5);
    return $result->{ok} && $result->{stdout}=~/\A[23][0-9]{2}\z/ ? 1:0;
}
sub discover {
    my ($identity,$networks)=@_;
    my $uuid=capture(['/usr/bin/uuidgen'],2);return [] unless $uuid->{ok};
    my $id=$uuid->{stdout};$id=~s/\s+\z//;
    return [] unless $id=~/\A[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\z/;
    my $probe='<?xml version="1.0" encoding="utf-8"?><Probe><Uuid>'.$id.'</Uuid><Types>inquiry</Types></Probe>';
    my $socket=IO::Socket::INET->new(LocalAddr=>'0.0.0.0',LocalPort=>37020,Proto=>'udp',ReuseAddr=>1);
    return [] unless $socket;
    AirRecordingSupervisor::_fd_cloexec($socket);
    $socket->setsockopt(IPPROTO_IP,IP_MULTICAST_TTL,pack('C',1));
    my @joined;
    for my $network (@$networks) {
        next unless valid_mask($network->{mask});
        my $local=inet_aton($network->{address});next unless $local;
        next unless $socket->setsockopt(IPPROTO_IP,IP_ADD_MEMBERSHIP,inet_aton('239.255.255.250').$local);
        $socket->setsockopt(IPPROTO_IP,IP_MULTICAST_IF,$local);
        my $destination=Socket::sockaddr_in(37020,inet_aton('239.255.255.250'));
        $socket->send($probe,0,$destination);push @joined,$network;
    }
    my $select=IO::Select->new($socket);my $until=monotonic()+2.5;my %found;my $received=0;
    while(monotonic()<$until && $received<128){
        next unless $select->can_read(0.1);
        my $xml='';my $peer=$socket->recv($xml,32769);next unless defined $peer;$received++;
        my($port,$packed)=Socket::sockaddr_in($peer);next unless $port==37020;
        my $address=Socket::inet_ntoa($packed);
        my $host=parse_reply($xml,$address,$id,$identity,\@joined);
        $found{$host}=1 if defined($host);
    }
    close $socket;return [sort keys %found];
}
sub resolve_camera {
    my ($identity,$hint,$networks,$verify,$discovery)=@_;
    $verify ||= \&pin_verified; $discovery ||= \&discover;
    if(defined($hint) && local_destination($hint,$networks) && $verify->($hint,$identity->{publicKeyPin})){return $hint;}
    my @verified;
    for my $host (@{$discovery->($identity,$networks)}){
        next unless local_destination($host,$networks);
        push @verified,$host if $verify->($host,$identity->{publicKeyPin});
    }
    # Conflicting identities fail closed instead of choosing the first reply.
    return @verified==1 ? $verified[0] : undef;
}
sub bridge {
    my($client,$upstream,$stopped)=@_;
    my @socket=($client,$upstream);my @buffer=('','');my @eof=(0,0);my @closed=(0,0);
    $_->blocking(0) for @socket;
    my $last=monotonic();
    while(!$$stopped && monotonic()-$last<20){
        for my $i(0,1){if($eof[1-$i] && !length($buffer[$i]) && !$closed[$i]){shutdown($socket[$i],1);$closed[$i]=1;}}
        last if $eof[0] && $eof[1] && !length($buffer[0]) && !length($buffer[1]);
        my $reads=IO::Select->new();my $writes=IO::Select->new();
        for my $i(0,1){$reads->add($socket[$i]) if !$eof[$i] && length($buffer[1-$i])<BUFFER_LIMIT;$writes->add($socket[$i]) if length($buffer[$i]);}
        my($ready_read,$ready_write)=IO::Select->select($reads,$writes,undef,0.2);
        for my $ready(@{$ready_read||[]}){
            my $i=fileno($ready)==fileno($socket[0])?0:1;my $chunk='';
            my $n=sysread($ready,$chunk,BUFFER_LIMIT-length($buffer[1-$i]));
            if(defined($n)){if($n==0){$eof[$i]=1;}else{$buffer[1-$i].=$chunk;$last=monotonic();}}
            elsif($! != EAGAIN && $! != EWOULDBLOCK && $! != EINTR){return;}
        }
        for my $ready(@{$ready_write||[]}){
            my $i=fileno($ready)==fileno($socket[0])?0:1;my $n=syswrite($ready,$buffer[$i]);
            if(defined($n) && $n>0){substr($buffer[$i],0,$n,'');$last=monotonic();}
            elsif(!defined($n) && $! != EAGAIN && $! != EWOULDBLOCK && $! != EINTR){return;}
        }
    }
}
sub run {
    my($workspace)=@_;
    my $root=abs_path($workspace);die "Invalid workspace\n" unless defined($root) && $root eq $workspace;
    AirRecordingSupervisor::require_private_dir($root,0,'.local');
    my $directory=AirRecordingSupervisor::require_private_dir($root,1,'.local','camera-roaming');
    my $config=AirRecordingSupervisor::require_private_file_0600($root,'.local','camera-roaming.json');
    my $identity=validate_identity(JSON::PP::decode_json(AirRecordingSupervisor::read_private_file($config)));
    my $lockpath=AirRecordingSupervisor::validate_no_symlink_chain($root,'.local','camera-roaming','proxy.lock');
    sysopen(my $lock,$lockpath,O_WRONLY|O_CREAT|AirRecordingSupervisor::_o_nofollow(),0600) or die "Proxy lock unavailable\n";
    chmod(0600,$lock);flock($lock,LOCK_EX|LOCK_NB) or die "Proxy already running\n";AirRecordingSupervisor::_fd_cloexec($lock);
    my $listener=IO::Socket::INET->new(LocalAddr=>'127.0.0.1',LocalPort=>LISTEN_PORT,Proto=>'tcp',Listen=>2,ReuseAddr=>1) or die "Proxy listener unavailable\n";
    AirRecordingSupervisor::_fd_cloexec($listener);
    my $selection=IO::Select->new($listener);my $stopped=0;local $SIG{TERM}=sub{$stopped=1;};local $SIG{INT}=sub{$stopped=1;};local $SIG{PIPE}='IGNORE';
    my $hint=$identity->{lastKnownHost};my $next_attempt=0;
    my $status=sub{my($state,$host)=@_;AirRecordingSupervisor::atomic_write_private_file($directory,'status.json',JSON::PP::encode_json({updatedAt=>AirRecordingSupervisor::_iso_utc(),state=>$state,address=>$host,pid=>0+$$}));};
    $status->('waiting_camera',undef);
    while(!$stopped){
        next unless $selection->can_read(0.2);my $client=$listener->accept();next unless $client;AirRecordingSupervisor::_fd_cloexec($client);
        if(monotonic()<$next_attempt){close $client;next;}
        my $host=resolve_camera($identity,$hint,active_networks());
        if(!defined($host)){$status->('camera_not_verified',undef);$next_attempt=monotonic()+5;close $client;next;}
        my $upstream=IO::Socket::INET->new(PeerAddr=>$host,PeerPort=>CAMERA_PORT,Proto=>'tcp',Timeout=>3);
        if(!$upstream){$status->('camera_unreachable',$host);$next_attempt=monotonic()+5;close $client;next;}
        AirRecordingSupervisor::_fd_cloexec($upstream);$hint=$host;$status->('connected',$host);
        bridge($client,$upstream,\$stopped);close $client;close $upstream;$status->('waiting_camera',$hint);
    }
    close $listener;$status->('stopped',undef);return 0;
}
package main;
unless(caller){
    my $code=eval{die "Usage: camera_roaming_proxy.pl ABS_WORKSPACE\n" unless @ARGV==1;CameraRoamingProxy::run($ARGV[0]);};
    if($@){print STDERR "Camera source proxy failed; inspect private configuration and status.\n";exit 2;}
    exit($code//0);
}
1;
