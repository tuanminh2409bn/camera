#!/usr/bin/env perl
package AirWebGateway;
use strict;
use warnings;
use IO::Socket::INET ();
use IO::Select ();
use JSON::PP ();
use MIME::Base64 qw(encode_base64);
use Time::Local qw(timegm);
use Time::HiRes ();
use POSIX qw(WNOHANG strftime);
use File::Basename qw(dirname);
use File::Spec ();
use Cwd qw(abs_path);
require File::Spec->catfile(dirname(abs_path(__FILE__)), 'air_recording_supervisor.pl');
our $RESPONSE_STARTED=0;

sub boolean { return $_[0] ? JSON::PP::true : JSON::PP::false; }
sub private_json {
    my ($root,@parts)=@_;
    my $path=AirRecordingSupervisor::require_private_file_0600($root,@parts);
    return JSON::PP::decode_json(AirRecordingSupervisor::read_private_file($path));
}
sub constant_equal {
    my ($a,$b)=@_;return 0 if length($a)!=length($b);
    my $different=0;for(my $i=0;$i<length($a);$i++){$different|=ord(substr($a,$i,1))^ord(substr($b,$i,1));}
    return !$different;
}
sub write_all {
    my ($socket,$value)=@_;my $offset=0;
    while($offset<length($value)){
        die "write timeout\n" unless IO::Select->new($socket)->can_write(5);
        my $count=syswrite($socket,$value,length($value)-$offset,$offset);
        die "write failed\n" unless defined($count)&&$count>0;$offset+=$count;
    }
}
sub read_some {
    my ($socket,$limit)=@_;
    die "read timeout\n" unless IO::Select->new($socket)->can_read(5);
    my $count=sysread($socket,my $bytes,$limit);die "read failed\n" unless defined $count;
    return $bytes;
}
sub read_headers {
    my ($socket)=@_;my $buffer='';
    while(index($buffer,"\r\n\r\n")<0){my $part=read_some($socket,1);die "short headers\n" if $part eq '';$buffer.=$part;die "invalid headers\n" if length($buffer)>16384;}
    my @lines=split /\r\n/,$buffer;my $first=shift @lines;my %headers;
    for my $line(@lines){next if $line eq '';die "invalid header\n" unless $line=~/\A([A-Za-z0-9-]+):[ \t]*([^\r\n]*)\z/;
        my ($key,$value)=(lc($1),$2);die "duplicate header\n" if exists $headers{$key};$headers{$key}=$value;}
    return ($first,\%headers);
}
sub native {
    my ($port,$method,$path,$authorization,$body,$stream)=@_;$body='' unless defined $body;
    die "invalid native endpoint\n" unless ($port==9997||$port==9996) && $path=~m{\A/[A-Za-z0-9/?=&%_.:+-]+\z};
    my $socket=IO::Socket::INET->new(PeerAddr=>'127.0.0.1',PeerPort=>$port,Proto=>'tcp',Timeout=>3) or die "native offline\n";
    # HTTP/1.0 + Connection: close deliberately avoids transfer-coded playback.
    my $request="$method $path HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n";
    $request.="Authorization: $authorization\r\n" if defined $authorization;
    $request.="Content-Type: application/json\r\nContent-Length: ".length($body)."\r\n\r\n$body";
    write_all($socket,$request);my ($first,$headers)=read_headers($socket);
    die "invalid native response\n" unless $first=~m{\AHTTP/1\.[01] (\d{3})[ \r]};my $code=0+$1;
    die "unsupported transfer coding\n" if exists $headers->{'transfer-encoding'};
    if($stream){return ($code,$headers,$socket);}
    my $result='';while(1){my $chunk=read_some($socket,65536);last if $chunk eq '';$result.=$chunk;die "native response too large\n" if length($result)>1048576;}
    close $socket;return ($code,$result);
}
sub native_json {
    my ($port,$path,$authorization)=@_;my ($code,$body)=native($port,'GET',$path,$authorization);
    die "native offline\n" unless $code==200;return JSON::PP::decode_json($body);
}
sub fresh_status {
    my ($root,$now)=@_;$now=time unless defined $now;
    my $state=private_json($root,'.local','recording-service','status.json');
    die "invalid status\n" unless ref($state) eq 'HASH';
    my $updated=$state->{updatedAt}//'';
    die "stale status\n" unless $updated=~/\A(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z\z/;
    my $epoch=timegm($6,$5,$4,$3,$2-1,$1);
    die "stale status\n" if $now-$epoch>30 || $epoch-$now>5;
    $state->{authLatchActive}=boolean($state->{authLatchActive} || -e File::Spec->catfile($root,'.local','recording-service','auth-stop.latch'));
    return $state;
}
sub may_enable {
    my ($state,$available)=@_;
    return 0 if $state->{authLatchActive}||$state->{recordingPaused};
    return 0 unless ($state->{state}//'')=~/\A(?:running|starting|degraded)\z/;
    return defined($available)&&$available>=15*1024**3;
}
sub status {
    my ($root)=@_;my $state=eval{fresh_status($root)};my $fresh=$state?1:0;
    $state=private_json($root,'.local','recording-service','status.json') unless $state;
    die "invalid status\n" unless ref($state)eq'HASH';
    $state->{authLatchActive}=boolean($state->{authLatchActive} || -e File::Spec->catfile($root,'.local','recording-service','auth-stop.latch'));
    my ($ready,$observed)=(0,undef);
    if($fresh){eval{my $path=native_json(9997,'/v3/paths/get/live');my $config=native_json(9997,'/v3/config/paths/get/live');$ready=$path->{ready}?1:0;$observed=boolean($config->{record});};}
    return {observed=>$observed,isOnline=>boolean($ready),isPaused=>boolean($state->{recordingPaused}),
        authLatched=>boolean($state->{authLatchActive}),availableBytes=>$state->{availableBytes},updatedAt=>$state->{updatedAt}};
}
sub set_recording {
    my ($root,$desired)=@_;
    my $safe=sub {return may_enable(fresh_status($root),AirRecordingSupervisor::check_available_disk_bytes($root,2,sub{Time::HiRes::time()}));};
    die "safety stop\n" if $desired&&!$safe->();
    my ($code)=native(9997,'PATCH','/v3/config/paths/patch/live',undef,JSON::PP::encode_json({record=>boolean($desired)}));
    die "native unavailable\n" unless $code==200;
    # Recheck after the effect so a concurrent supervisor pause is not undone.
    if($desired){my $still_safe=eval{$safe->()};if(!$still_safe){native(9997,'PATCH','/v3/config/paths/patch/live',undef,'{"record":false}');die "safety stop\n";}}
}
sub parse_query {
    my ($text)=@_;my %values;
    for my $pair(split /&/,$text){my ($key,$value)=split /=/,$pair,2;die "invalid query\n" unless defined $value;
        for($key,$value){die "invalid encoding\n" if /%(?![a-fA-F0-9]{2})/;s/%([a-fA-F0-9]{2})/chr(hex($1))/eg;}
        die "duplicate query\n" if exists $values{$key};$values{$key}=$value;}
    return \%values;
}
sub playback_query {
    my ($query)=@_;my $values=parse_query($query);
    die "invalid playback\n" unless keys(%$values)==2 && defined($values->{start}) && defined($values->{duration});
    die "invalid playback\n" unless $values->{start}=~/\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})\z/;
    die "invalid duration\n" unless $values->{duration}=~/\A\d{1,3}\z/ && $values->{duration}>=1 && $values->{duration}<=300;
    my $start=$values->{start};$start=~s/([^A-Za-z0-9_.~-])/sprintf('%%%02X',ord($1))/eg;
    return '/get?path=live&format=fmp4&start='.$start.'&duration='.$values->{duration};
}
sub json_response {
    my ($socket,$code,$object)=@_;my $body=JSON::PP::encode_json($object);
    $RESPONSE_STARTED=1;
    write_all($socket,"HTTP/1.1 $code Response\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: ".length($body)."\r\n\r\n$body");
}
sub handle {
    my ($socket,$root,$token,$authorization)=@_;
    my ($line,$headers)=read_headers($socket);
    die "invalid request\n" unless $line=~m{\A(GET|PUT) (/[^\s]*) HTTP/1\.[01]\z};my ($method,$target)=($1,$2);
    return json_response($socket,401,{error=>'unauthorized'}) unless constant_equal($headers->{authorization}//'','Bearer '.$token);
    alarm 330;
    die "invalid framing\n" if exists $headers->{'transfer-encoding'};
    my $length=$headers->{'content-length'}//0;die "invalid body\n" unless $length=~/\A\d{1,4}\z/ && $length<=1024;
    my $body='';while(length($body)<$length){my $chunk=read_some($socket,$length-length($body));die "short body\n" if $chunk eq '';$body.=$chunk;}
    if($method eq 'GET' && $target eq '/status'){return json_response($socket,200,status($root));}
    if($method eq 'PUT' && $target eq '/recording'){
        my $input=JSON::PP::decode_json($body);die "invalid body\n" unless ref($input)eq'HASH'&&keys(%$input)==1&&JSON::PP::is_bool($input->{desired});
        set_recording($root,$input->{desired});return json_response($socket,200,{ok=>JSON::PP::true});
    }
    if($method eq 'GET' && $target eq '/recordings'){
        my ($code,$raw)=native(9996,'GET','/list?path=live',$authorization);
        return json_response($socket,200,[]) if $code==404;
        die "native unavailable\n" unless $code==200;
        my $entries=JSON::PP::decode_json($raw);die "invalid list\n" unless ref($entries)eq'ARRAY'&&@$entries<=2000;
        my @safe;for my $entry(@$entries){die "invalid interval\n" unless ref($entry)eq'HASH'&&defined($entry->{start})&&defined($entry->{duration})&&$entry->{duration}=~/\A\d+(?:\.\d+)?\z/;push @safe,{start=>$entry->{start},duration=>0+$entry->{duration}};}
        return json_response($socket,200,\@safe);
    }
    if($method eq 'GET' && $target=~m{\A/playback\?(.*)\z}){
        my $path=playback_query($1);my ($code,$native_headers,$upstream)=native(9996,'GET',$path,$authorization,undef,1);
        if($code!=200){close $upstream;return json_response($socket,$code==404?404:503,{error=>'playback_unavailable'});}
        $RESPONSE_STARTED=1;
        write_all($socket,"HTTP/1.1 200 OK\r\nContent-Type: video/mp4\r\nAccept-Ranges: none\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n");
        # Fixed-size reads + blocking writes provide backpressure, no file/cache.
        while(1){my $chunk=read_some($upstream,65536);last if $chunk eq '';write_all($socket,$chunk);}
        close $upstream;return;
    }
    return json_response($socket,404,{error=>'not_found'});
}
sub run {
    my ($root)=@_;die "absolute workspace required\n" unless defined($root)&&$root=~m{\A/}&&abs_path($root)eq$root;
    my $config=private_json($root,'.local','web-gateway.json');
    die "invalid gateway token\n" unless ref($config)eq'HASH'&&defined($config->{token})&&$config->{token}=~/\A[A-Za-z0-9_-]{43,128}\z/;
    my $admin=private_json($root,'.local','recording-admin.json');my $user=$admin->{username}//$admin->{user};my $pass=$admin->{password}//$admin->{pass};
    die "invalid playback account\n" unless defined($user)&&defined($pass)&&length($user)&&length($pass)&&$user!~/[:\r\n]/&&$pass!~/[\r\n]/;
    my $authorization='Basic '.encode_base64($user.':'.$pass,'');
    my $listener=IO::Socket::INET->new(LocalAddr=>'127.0.0.1',LocalPort=>9900,Listen=>16,ReuseAddr=>1,Proto=>'tcp') or die "loopback listener unavailable\n";
    my %children;my $stop=0;$SIG{TERM}=$SIG{INT}=sub{$stop=1};$SIG{PIPE}='IGNORE';
    while(!$stop){
        for my $pid(keys %children){delete $children{$pid} if waitpid($pid,WNOHANG)==$pid;}
        next unless IO::Select->new($listener)->can_read(1);my $client=$listener->accept();next unless $client;
        if(keys(%children)>=8){eval{json_response($client,503,{error=>'busy'})};close $client;next;}
        my $pid=fork();if(!defined $pid){close $client;next;}
        if(!$pid){close $listener;$SIG{TERM}=$SIG{INT}='DEFAULT';$SIG{ALRM}=sub{die "request deadline\n"};alarm 10;
            eval{handle($client,$root,$config->{token},$authorization)};if($@&&!$RESPONSE_STARTED){eval{json_response($client,503,{error=>'unavailable'})};}
            close $client;POSIX::_exit(0);
        }
        $children{$pid}=1;close $client;
    }
    close $listener;kill 'TERM',keys %children if %children;for my $pid(keys %children){waitpid($pid,0);}
}
package main;
unless(caller){eval{AirWebGateway::run($ARGV[0])};if($@){print STDERR "Air web gateway failed; check private config and loopback services.\n";exit 1;}}
1;
