use strict;
use warnings;
use Test::More;
use File::Temp qw(tempdir);
use File::Path qw(make_path);
use File::Spec;
use Cwd qw(abs_path);
use File::Basename qw(dirname);
use JSON::PP;
use Socket qw(AF_UNIX SOCK_STREAM PF_UNSPEC);
require File::Spec->catfile(dirname(dirname(abs_path(__FILE__))),'scripts','air_web_gateway.pl');

ok(AirWebGateway::constant_equal('abc','abc'),'matching token');
ok(!AirWebGateway::constant_equal('abc','abd'),'mismatched token');
ok(!AirWebGateway::constant_equal('abc','abcd'),'length mismatch');
my $state={state=>'running',recordingPaused=>0,authLatchActive=>0};
ok(AirWebGateway::may_enable($state,16*1024**3),'healthy enable');
ok(!AirWebGateway::may_enable($state,14*1024**3),'disk reserve enforced');
ok(!AirWebGateway::may_enable($state,undef),'unknown disk fails closed');
for my $key(qw(recordingPaused authLatchActive)){my %unsafe=(%$state,$key=>1);ok(!AirWebGateway::may_enable(\%unsafe,99*1024**3),"$key cannot be overridden");}
is(AirWebGateway::playback_query('start=2026-11-02T00%3A00%3A00Z&duration=60'),'/get?path=live&format=fmp4&start=2026-11-02T00%3A00%3A00Z&duration=60','fixed native playback target');
for my $query('start=../../secret&duration=1','start=2026-11-02T00:00:00Z&duration=301','start=2026-11-02T00:00:00Z&duration=1&url=http://evil','start=2026-11-02T00:00:00Z&duration=1&duration=2','start=%ZZ&duration=1'){
    eval{AirWebGateway::playback_query($query)};ok($@,'rejects unsafe query');
}
my $root=tempdir(CLEANUP=>1);chmod 0700,$root;make_path("$root/.local/recording-service",{mode=>0700});
my $path="$root/.local/recording-service/status.json";
open my $out,'>',$path or die;print $out encode_json({%$state,updatedAt=>'2026-11-02T00:00:00Z'});close $out;chmod 0600,$path;
my $now=Time::Local::timegm(0,0,0,2,10,2026);
ok(AirWebGateway::fresh_status($root,$now+20),'fresh supervisor status');
eval{AirWebGateway::fresh_status($root,$now+31)};ok($@,'stale status fails closed');
open my $latch,'>',"$root/.local/recording-service/auth-stop.latch" or die;close $latch;chmod 0600,"$root/.local/recording-service/auth-stop.latch";
ok(AirWebGateway::fresh_status($root,$now)->{authLatchActive},'latch file overrides healthy status snapshot');

sub request_fixture {
    my ($request)=@_;
    socketpair(my $client,my $server,AF_UNIX,SOCK_STREAM,PF_UNSPEC) or die;
    AirWebGateway::write_all($client,$request);shutdown($client,1);
    local $AirWebGateway::RESPONSE_STARTED=0;
    my $error='';eval{AirWebGateway::handle($server,$root,'fixture-token','Basic PRIVATE_PLAYBACK_AUTH')};$error=$@;alarm 0;
    close $server;my $response='';while(1){my $chunk=AirWebGateway::read_some($client,65536);last if $chunk eq '';$response.=$chunk;}close $client;
    return ($response,$error);
}
my ($response,$error)=request_fixture("GET /status HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer wrong\r\n\r\n");
like($response,qr/HTTP\/1.1 401/,'HTTP unauthorized fails before private status access');
unlike($response,qr/fixture-token|PRIVATE_PLAYBACK_AUTH/,'HTTP error does not expose credentials');
($response,$error)=request_fixture("GET /status HTTP/1.1\r\nAuthorization: Bearer fixture-token\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n");
like($error,qr/duplicate header/,'ambiguous request framing rejected');
($response,$error)=request_fixture("GET /status HTTP/1.1\r\nAuthorization: Bearer fixture-token\r\nTransfer-Encoding: chunked\r\n\r\n");
like($error,qr/invalid framing/,'transfer-coded request rejected');
($response,$error)=request_fixture("GET /proxy?url=http://evil HTTP/1.1\r\nAuthorization: Bearer fixture-token\r\n\r\n");
like($response,qr/HTTP\/1.1 404/,'no arbitrary proxy endpoint');
{
    no warnings 'redefine';
    local *AirWebGateway::native=sub {
        my ($port,$method,$path,$auth,$body,$stream)=@_;
        is($port,9996,'playback uses fixed native port');
        like($path,qr{^/get\?path=live&format=fmp4&start=},'playback uses fixed live path');
        is($auth,'Basic PRIVATE_PLAYBACK_AUTH','credential supplied only to native');
        socketpair(my $writer,my $reader,AF_UNIX,SOCK_STREAM,PF_UNSPEC) or die;
        AirWebGateway::write_all($writer,'fixture-media-bytes');close $writer;
        return (200,{},$reader);
    };
    ($response,$error)=request_fixture("GET /playback?start=2026-11-02T00%3A00%3A00Z&duration=60 HTTP/1.1\r\nAuthorization: Bearer fixture-token\r\nRange: bytes=100-\r\n\r\n");
    is($error,'','stream completes without a file');
    like($response,qr/HTTP\/1.1 200.*Accept-Ranges: none.*\r\n\r\nfixture-media-bytes\z/s,'native no-range response streams unchanged');
    unlike($response,qr/PRIVATE_PLAYBACK_AUTH/,'playback credential never reaches client');
}
{
    no warnings 'redefine';my $reads=0;my @writes;
    local *AirWebGateway::fresh_status=sub {return {state=>'running',recordingPaused=>($reads++?1:0),authLatchActive=>0};};
    local *AirRecordingSupervisor::check_available_disk_bytes=sub{return 99*1024**3;};
    local *AirWebGateway::native=sub {push @writes,decode_json($_[4])->{record}?1:0;return (200,'');};
    eval{AirWebGateway::set_recording($root,1)};
    like($@,qr/safety stop/,'concurrent supervisor pause rejects enable');
    is_deeply(\@writes,[1,0],'gateway restores record:false when pause races enable');
}
done_testing();
