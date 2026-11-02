#!/usr/bin/env perl
use strict;
use warnings;

use Digest::SHA ();
use Fcntl qw(:DEFAULT :flock);
use File::Spec ();
use File::Temp qw(tempdir);
use FindBin;
use JSON::PP ();
use POSIX qw(:sys_wait_h);
use Test::More;
use Time::HiRes ();

my $SCRIPT_PATH = File::Spec->catfile($FindBin::Bin, '..', 'scripts', 'air_recording_supervisor.pl');
ok(-f $SCRIPT_PATH, 'supervisor script exists');
require $SCRIPT_PATH;

sub write_file_mode {
    my ($path, $content, $mode) = @_;
    open(my $fh, '>', $path) or die "open $path: $!";
    binmode($fh);
    print {$fh} $content;
    close($fh) or die "close $path: $!";
    chmod($mode, $path) or die "chmod $path: $!";
    return $path;
}

sub sha256_file {
    my ($path) = @_;
    open(my $fh, '<', $path) or die "open $path: $!";
    binmode($fh);
    my $hex = lc(Digest::SHA->new(256)->addfile($fh)->hexdigest());
    close($fh);
    return $hex;
}

sub read_json_file {
    my ($path) = @_;
    open(my $fh, '<', $path) or die "open $path: $!";
    local $/;
    my $raw = <$fh>;
    close($fh);
    return JSON::PP::decode_json($raw);
}

sub slurp_file {
    my ($path) = @_;
    return '' unless -e $path;
    open(my $fh, '<', $path) or die "open $path: $!";
    local $/;
    my $raw = <$fh>;
    close($fh);
    return defined($raw) ? $raw : '';
}

sub setup_fixture_workspace {
    my (%args) = @_;
    my $base = tempdir(CLEANUP => 1);
    my $ws   = File::Spec->catdir($base, 'workspace');
    mkdir($ws, 0755) or die "mkdir ws: $!";

    my $local_dir = File::Spec->catdir($ws, '.local');
    mkdir($local_dir, 0700) or die "mkdir .local: $!";
    chmod(0700, $local_dir);

    my $tools_dir = File::Spec->catdir($local_dir, 'tools');
    mkdir($tools_dir, 0700) or die "mkdir tools: $!";
    my $mtx_dir = File::Spec->catdir($tools_dir, 'mediamtx-1.21.3');
    mkdir($mtx_dir, 0700) or die "mkdir mediamtx-1.21.3: $!";

    my $cam_user  = $args{cam_user}  || 'cam_oper_test';
    my $cam_pass  = $args{cam_pass}  || 'Cam!Pass#2026:Secret@99';
    my $play_user = $args{play_user} || 'playback_viewer';
    my $play_pass = $args{play_pass} || 'Play$Pass%2026^Priv!88';

    my $cam_json = JSON::PP::encode_json({
        scheme    => 'rtsp',
        host      => '192.168.0.101',
        port      => 554,
        channel   => '101',
        username  => $cam_user,
        password  => $cam_pass,
        transport => 'tcp',
    });
    write_file_mode(File::Spec->catfile($local_dir, 'camera-source.json'), $cam_json, 0600);

    my $admin_json = JSON::PP::encode_json({
        username => $play_user,
        password => $play_pass,
    });
    write_file_mode(File::Spec->catfile($local_dir, 'recording-admin.json'), $admin_json, 0600);

    my $enc_user = AirRecordingSupervisor::uri_escape_upper($cam_user);
    my $enc_pass = AirRecordingSupervisor::uri_escape_upper($cam_pass);
    my $yml = join("\n",
        "logLevel: info",
        "api: yes",
        "apiAddress: 127.0.0.1:9997",
        "playback: yes",
        "playbackAddress: 127.0.0.1:9996",
        "authInternalUsers:",
        "  - user: $play_user",
        "    pass: \"$play_pass\"",
        "paths:",
        "  live:",
        "    source: \"rtsp://$enc_user:$enc_pass\@192.168.0.101:554/Streaming/Channels/101\"",
        "    sourceOnDemand: no",
        "    record: yes",
        "",
    );
    write_file_mode(File::Spec->catfile($local_dir, 'mediamtx.recording.poc.yml'), $yml, 0600);

    my $child_body = $args{child_script} || <<'PERL';
$|=1;
print "2026/11/02 12:00:00 INF [path live] [RTSP source] started\n";
select(undef, undef, undef, 0.25);
exit 0;
PERL
    my $bin_path = File::Spec->catfile($mtx_dir, 'mediamtx');
    my $script_text = "#!/usr/bin/perl\nuse strict;\nuse warnings;\n" . $child_body;
    write_file_mode($bin_path, $script_text, 0700);
    my $bin_sha = sha256_file($bin_path);

    return {
        base      => $base,
        workspace => $ws,
        bin_path  => $bin_path,
        bin_sha   => $bin_sha,
        cam_user  => $cam_user,
        cam_pass  => $cam_pass,
        play_user => $play_user,
        play_pass => $play_pass,
        enc_pass  => $enc_pass,
    };
}

subtest 'CLI argument validation' => sub {
    eval { AirRecordingSupervisor::parse_cli_args() };
    like($@, qr/workspace/i, 'missing --workspace rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', 'relative/path') };
    like($@, qr/absolute/i, 'relative --workspace rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/../etc') };
    like($@, qr/traversal/i, 'dot-dot traversal rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', "/tmp/bad\npath") };
    like($@, qr/control/i, 'control chars in --workspace rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/ok', '--duration', '0') };
    like($@, qr/duration/i, 'zero duration rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/ok', '--duration', '-5') };
    like($@, qr/duration/i, 'negative duration rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/ok', '--duration', '999999') };
    like($@, qr/duration/i, 'excessive duration rejected');

    eval { AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/ok', 'extra_arg') };
    like($@, qr/Usage/i, 'extra positional argument rejected');

    my $ok = AirRecordingSupervisor::parse_cli_args('--workspace', '/tmp/valid', '--duration', '1.5');
    is($ok->{workspace}, '/tmp/valid', 'parsed workspace');
    is($ok->{duration}, 1.5, 'parsed fractional duration');
};

subtest 'Secret redaction including URL-encoded, split chunks, oversized lines, and log rotation' => sub {
    my $fx = setup_fixture_workspace(
        child_script => <<'PERL',
$|=1;
syswrite(STDOUT, "2026/11/02 12:00:00 INF Connecting rtsp://cam_oper_test:Cam%21Pass%232026");
select(undef, undef, undef, 0.04);
syswrite(STDOUT, "%3ASecret%4099\@192.168.0.101:554/Streaming/Channels/101\n");
my $huge = "X" x 300 . "Cam!Pass#2026:Secret\@99" . ("Y" x 300) . "\n";
syswrite(STDOUT, $huge);
syswrite(STDOUT, "2026/11/02 12:00:01 INF Raw playback secret Play\$Pass%2026^Priv!88 and lower cam%21pass%232026%3asecret%4099\n");
select(undef, undef, undef, 5);
PERL
    );

    my $secrets = [$fx->{cam_user}, $fx->{cam_pass}, $fx->{play_user}, $fx->{play_pass}];
    my $sample = "url=rtsp://$fx->{cam_user}:$fx->{enc_pass}\@192.168.0.101:554/live "
               . "raw=$fx->{cam_pass} play=$fx->{play_pass} "
               . "lower=" . AirRecordingSupervisor::uri_escape_lower($fx->{cam_pass});
    my $redacted = AirRecordingSupervisor::redact_text($sample, $secrets);
    unlike($redacted, qr/\Q$fx->{cam_pass}\E/, 'raw camera password redacted');
    unlike($redacted, qr/\Q$fx->{enc_pass}\E/i, 'URL-encoded camera password redacted');
    unlike($redacted, qr/\Q$fx->{play_pass}\E/, 'playback password redacted');
    unlike($redacted, qr/\Q$fx->{cam_user}\E/, 'camera username redacted');
    like($redacted, qr{rtsp://\[REDACTED\]\@192\.168\.0\.101:554/live}, 'RTSP userinfo redacted');

    my $rc = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx->{workspace},
        duration         => 0.25,
        expected_sha256  => $fx->{bin_sha},
        disk_check_fn    => sub { return 30 * 1024 * 1024 * 1024 },
        max_line_bytes   => 256,
        max_log_bytes    => 350,
        term_timeout_sec => 0.3,
        kill_timeout_sec => 0.2,
    });
    is($rc, 0, 'bounded supervisor run exited 0');

    my $sdir = File::Spec->catdir($fx->{workspace}, '.local', 'recording-service');
    my $combined_logs = '';
    for my $name ('supervisor.log', 'supervisor.log.1', 'supervisor.log.2') {
        my $p = File::Spec->catfile($sdir, $name);
        if (-e $p) {
            my @st = lstat($p);
            is(($st[2] & 07777), 0600, "$name has mode 0600");
            $combined_logs .= slurp_file($p);
        }
    }
    ok(-e File::Spec->catfile($sdir, 'supervisor.log.1'), 'log rotation created supervisor.log.1');
    unlike($combined_logs, qr/\Q$fx->{cam_pass}\E/, 'split-chunk/oversized camera password not in logs');
    unlike($combined_logs, qr/Cam%21Pass/i, 'split-chunk URL-encoded password not in logs');
    unlike($combined_logs, qr/Secret%4099/i, 'second half of split credential not in logs');
    unlike($combined_logs, qr/\Q$fx->{play_pass}\E/, 'playback password not in logs');
    like($combined_logs, qr/dropped oversized child log line/, 'oversized line safely dropped');
    unlike($combined_logs, qr/X{100}|Y{100}/, 'oversized payload discarded rather than truncated');
};

subtest 'Path, permission, symlink, and binary SHA256 guards' => sub {
    my $fx = setup_fixture_workspace();

    # Default pinned SHA256 rejects unverified binary
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace     => $fx->{workspace},
            duration      => 0.1,
            disk_check_fn => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/SHA256 mismatch/i, 'mismatch against pinned binary SHA256 rejected');

    # Insecure .local mode
    chmod(0755, File::Spec->catdir($fx->{workspace}, '.local'));
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.1,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/0700/, 'insecure .local mode 0755 rejected');
    chmod(0700, File::Spec->catdir($fx->{workspace}, '.local'));

    # Insecure camera-source.json mode
    my $cam_file = File::Spec->catfile($fx->{workspace}, '.local', 'camera-source.json');
    chmod(0644, $cam_file);
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.1,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/0600/, 'insecure camera-source.json mode 0644 rejected');
    chmod(0600, $cam_file);

    # Symlinked workspace root
    my $ws_link = File::Spec->catfile($fx->{base}, 'ws_symlink');
    symlink($fx->{workspace}, $ws_link) or die "symlink: $!";
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $ws_link,
            duration        => 0.1,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/symlink/i, 'symlinked workspace root rejected');

    # Insecure existing service file in .local/recording-service
    my $sdir = File::Spec->catdir($fx->{workspace}, '.local', 'recording-service');
    mkdir($sdir, 0700);
    chmod(0700, $sdir);
    my $bad_status = File::Spec->catfile($sdir, 'status.json');
    write_file_mode($bad_status, '{}', 0644);
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.1,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/0600/, 'insecure existing status.json rejected');
    unlink($bad_status);

    # Symlink inside .local/recording-service
    my $outside = write_file_mode(File::Spec->catfile($fx->{base}, 'outside.txt'), 'secret', 0600);
    symlink($outside, $bad_status) or die "symlink status: $!";
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.1,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/symlink/i, 'symlinked service file rejected');
    unlink($bad_status);
};

subtest 'Duplicate lock exclusion via nonblocking flock' => sub {
    my $fx = setup_fixture_workspace();
    my $sdir = File::Spec->catdir($fx->{workspace}, '.local', 'recording-service');
    mkdir($sdir, 0700);
    chmod(0700, $sdir);
    my $lock_path = File::Spec->catfile($sdir, 'supervisor.lock');
    sysopen(my $held_fh, $lock_path, O_RDWR | O_CREAT, 0600) or die "sysopen lock: $!";
    chmod(0600, $lock_path);
    ok(flock($held_fh, LOCK_EX | LOCK_NB), 'test harness acquired lock');

    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.2,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/already holding supervisor\.lock/i, 'second instance refused when lock is held');
    close($held_fh);
};

subtest 'Playback HTTP 401 vs camera RTSP 401 distinction, transient loss, and persisted auth latch' => sub {
    # 1. Playback HTTP 401 and transient RTSP loss should NOT trigger auth latch
    my $fx_play = setup_fixture_workspace(
        child_script => <<'PERL',
$|=1;
print "2026/11/02 12:00:00 INF [playback] [conn 127.0.0.1:54321] HTTP 401 Unauthorized on /get?path=live\n";
print "2026/11/02 12:00:01 ERR [path live] [RTSP source] dial tcp 192.168.0.101:554: i/o timeout\n";
select(undef, undef, undef, 10);
PERL
    );

    my $rc_play = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx_play->{workspace},
        duration         => 0.25,
        expected_sha256  => $fx_play->{bin_sha},
        disk_check_fn    => sub { return 30 * 1024 * 1024 * 1024 },
        term_timeout_sec => 0.3,
        kill_timeout_sec => 0.2,
    });
    is($rc_play, 0, 'playback 401 and transient timeout did not abort run');
    my $sdir_play = File::Spec->catdir($fx_play->{workspace}, '.local', 'recording-service');
    ok(!-e File::Spec->catfile($sdir_play, 'auth-stop.latch'), 'no auth latch created for playback 401');
    my $log_play = slurp_file(File::Spec->catfile($sdir_play, 'supervisor.log'));
    like($log_play, qr/\[playback\]/, 'playback log recorded');

    is(
        AirRecordingSupervisor::classify_child_log_line(
            '2026/11/02 12:00:01 ERR [path live] [RTSP source] dial tcp 192.168.0.101:554: i/o timeout'
        ),
        'source_transient_error',
        'transient timeout classified as source_transient_error'
    );
    is(
        AirRecordingSupervisor::classify_child_log_line(
            '2026/11/02 12:00:01 INF [playback] 127.0.0.1:9996 401 Unauthorized'
        ),
        'playback_or_local_http',
        'playback 401 classified as playback_or_local_http'
    );

    # 2. Camera RTSP source 401 triggers fast stop and persists auth-stop.latch
    my $fx_auth = setup_fixture_workspace(
        child_script => <<'PERL',
$|=1;
print "2026/11/02 12:00:00 ERR [path live] [RTSP source] bad status code: 401 (Unauthorized)\n";
select(undef, undef, undef, 10);
PERL
    );

    my $t0 = Time::HiRes::time();
    my $rc_auth = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx_auth->{workspace},
        duration         => 8.0,
        expected_sha256  => $fx_auth->{bin_sha},
        disk_check_fn    => sub { return 30 * 1024 * 1024 * 1024 },
        term_timeout_sec => 0.3,
        kill_timeout_sec => 0.2,
    });
    my $elapsed = Time::HiRes::time() - $t0;
    is($rc_auth, 0, 'camera auth rejection exits cleanly after persisting latch');
    ok($elapsed < 3.0, 'stopped well before 5-second native retry');

    my $sdir_auth  = File::Spec->catdir($fx_auth->{workspace}, '.local', 'recording-service');
    my $latch_file = File::Spec->catfile($sdir_auth, 'auth-stop.latch');
    ok(-f $latch_file, 'auth-stop.latch persisted');
    is(((lstat($latch_file))[2] & 07777), 0600, 'auth-stop.latch has mode 0600');

    my $st_auth = read_json_file(File::Spec->catfile($sdir_auth, 'status.json'));
    is($st_auth->{reason}, 'camera_auth_failed', 'status.json records camera_auth_failed');
    ok($st_auth->{authLatchActive}, 'status.json marks authLatchActive true');

    # Subsequent invocation refuses to reconnect while latch exists
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx_auth->{workspace},
            duration        => 0.2,
            expected_sha256 => $fx_auth->{bin_sha},
            disk_check_fn   => sub { return 30 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/auth latch is active/i, 'subsequent run refused while auth-stop.latch exists');
};

subtest 'Disk reserve check before start, low-disk pause via API, and failed-pause child termination' => sub {
    my $fx = setup_fixture_workspace(
        child_script => <<'PERL',
$|=1;
print "2026/11/02 12:00:00 INF [path live] [RTSP source] is publishing\n";
select(undef, undef, undef, 10);
PERL
    );

    # 1. Pre-start low disk refuses startup
    eval {
        AirRecordingSupervisor::run_supervisor({
            workspace       => $fx->{workspace},
            duration        => 0.2,
            expected_sha256 => $fx->{bin_sha},
            disk_check_fn   => sub { return 10 * 1024 * 1024 * 1024 },
        });
    };
    like($@, qr/disk_low/i, 'startup refused when available space < 15 GiB');
    my $sdir = File::Spec->catdir($fx->{workspace}, '.local', 'recording-service');
    my $st_pre = read_json_file(File::Spec->catfile($sdir, 'status.json'));
    is($st_pre->{reason}, 'disk_low', 'pre-start status records disk_low');

    # 2. During-run low disk triggers pause once and keeps running without re-enabling
    my @disk_samples = (
        20 * 1024 * 1024 * 1024,
        12 * 1024 * 1024 * 1024,
        25 * 1024 * 1024 * 1024,
    );
    my $pause_calls = 0;
    my $rc_pause = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx->{workspace},
        duration         => 0.35,
        expected_sha256  => $fx->{bin_sha},
        disk_interval    => 0.08,
        disk_check_fn    => sub { return @disk_samples ? shift(@disk_samples) : (25 * 1024 * 1024 * 1024) },
        pause_api_fn     => sub { $pause_calls++; return 1 },
        term_timeout_sec => 0.3,
        kill_timeout_sec => 0.2,
    });
    is($rc_pause, 0, 'supervisor continued running until duration after successful pause');
    is($pause_calls, 1, 'pause API called exactly once and not re-enabled');
    my $st_paused = read_json_file(File::Spec->catfile($sdir, 'status.json'));
    ok($st_paused->{recordingPaused}, 'recordingPaused stays true at end of run');

    # 3. During-run low disk when pause API fails terminates child immediately
    my @fail_samples = (
        20 * 1024 * 1024 * 1024,
        11 * 1024 * 1024 * 1024,
    );
    my $rc_fail = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx->{workspace},
        duration         => 5.0,
        expected_sha256  => $fx->{bin_sha},
        disk_interval    => 0.08,
        disk_check_fn    => sub { return @fail_samples ? shift(@fail_samples) : (11 * 1024 * 1024 * 1024) },
        pause_api_fn     => sub { return 0 },
        term_timeout_sec => 0.3,
        kill_timeout_sec => 0.2,
    });
    is($rc_fail, 1, 'failed pause returns non-zero after terminating child');
    my $st_fail = read_json_file(File::Spec->catfile($sdir, 'status.json'));
    is($st_fail->{reason}, 'disk_low_pause_failed', 'status records disk_low_pause_failed');
};

subtest 'Owned child TERM/KILL cleanup and unexpected native child exit' => sub {
    my $base = tempdir(CLEANUP => 1);
    my $pid_file = File::Spec->catfile($base, 'child.pid');

    # 1. Child that ignores SIGTERM is cleaned up via bounded SIGKILL
    my $fx_stubborn = setup_fixture_workspace(
        child_script => sprintf(<<'PERL', $pid_file),
$|=1;
$SIG{TERM} = 'IGNORE';
open(my $pf, '>', '%s') or die "pid file open failed";
print {$pf} "$$\n";
close($pf);
print "2026/11/02 12:00:00 INF stubborn child started\n";
select(undef, undef, undef, 30);
PERL
    );

    my $rc_stub = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx_stubborn->{workspace},
        duration         => 0.15,
        expected_sha256  => $fx_stubborn->{bin_sha},
        disk_check_fn    => sub { return 30 * 1024 * 1024 * 1024 },
        term_timeout_sec => 0.15,
        kill_timeout_sec => 0.2,
    });
    is($rc_stub, 0, 'stubborn child stopped on duration expiry');
    my $stub_pid = int(slurp_file($pid_file) || 0);
    ok($stub_pid > 0, 'captured stubborn child PID');
    is(kill(0, $stub_pid), 0, 'stubborn child is no longer alive after cleanup');

    # 2. Bounded auxiliary command timeout cleans up hanging subprocess
    my $aux_res = AirRecordingSupervisor::run_bounded_aux_command(
        [$^X, '-e', 'select(undef, undef, undef, 10)'],
        0.15
    );
    ok($aux_res->{timed_out}, 'hanging auxiliary command timed out and was cleaned up');

    # 3. Unexpected child exit is reported honestly
    my $fx_crash = setup_fixture_workspace(
        child_script => <<'PERL',
$|=1;
print "2026/11/02 12:00:00 ERR fatal startup error\n";
exit 7;
PERL
    );
    my $rc_crash = AirRecordingSupervisor::run_supervisor({
        workspace        => $fx_crash->{workspace},
        duration         => 5.0,
        expected_sha256  => $fx_crash->{bin_sha},
        disk_check_fn    => sub { return 30 * 1024 * 1024 * 1024 },
        term_timeout_sec => 0.2,
        kill_timeout_sec => 0.2,
    });
    is($rc_crash, 1, 'unexpected child exit returns non-zero');
    my $sdir_crash = File::Spec->catdir($fx_crash->{workspace}, '.local', 'recording-service');
    my $st_crash   = read_json_file(File::Spec->catfile($sdir_crash, 'status.json'));
    is($st_crash->{state}, 'failed', 'status state is failed');
    is($st_crash->{reason}, 'unexpected_child_exit', 'status reason is unexpected_child_exit');
    is($st_crash->{childExitCode}, 7, 'childExitCode 7 recorded in status.json');
};

subtest 'Actual v1.21.3 recovery log restores source readiness' => sub {
    is(
        AirRecordingSupervisor::classify_child_log_line(
            '2026/11/02 15:24:40 INF [path live] stream is available and online, 1 track (H264)'
        ),
        'source_ready',
        'actual native recovery line is recognized'
    );
};

subtest 'Pause API cannot inherit curlrc or proxy routing' => sub {
    my $captured;
    {
        no warnings 'redefine'; # Scope the test-only boundary spy.
        local *AirRecordingSupervisor::run_bounded_aux_command = sub {
            $captured = [ @{$_[0]} ];
            return { ok => 1, timed_out => 0, stdout => '200' };
        };
        ok(AirRecordingSupervisor::pause_recording_via_api(), 'successful loopback pause');
    }
    is($captured->[1], '-q', 'curl configuration disabled before other options');
    like(join("\0", @$captured), qr/--noproxy\0\*/, 'loopback never routed through a proxy');
};

subtest 'Native child uses workspace, private umask and no MTX environment overrides' => sub {
    require Cwd;
    my $fx = setup_fixture_workspace(child_script => <<'PERL');
use Cwd ();
use JSON::PP ();
open(my $out, '>', '.local/child-context.json') or die "context open failed";
print {$out} JSON::PP::encode_json({
    cwd => Cwd::getcwd(),
    has_override => exists($ENV{MTX_APIADDRESS}) ? 1 : 0,
});
close($out);
$|=1;
print "INF [path live] stream is available and online, 1 track (H264)\n";
select(undef, undef, undef, 2);
PERL
    my $caller = File::Spec->catdir($fx->{base}, 'caller');
    mkdir($caller, 0700) or die "mkdir caller: $!";
    mkdir(File::Spec->catdir($caller, '.local'), 0700) or die "mkdir caller local: $!";
    my $previous = Cwd::getcwd();
    my $previous_umask = umask(0022);
    my ($rc, $error);
    {
        local $ENV{MTX_APIADDRESS} = '0.0.0.0:9997';
        eval {
            chdir($caller) or die "chdir caller: $!";
            $rc = AirRecordingSupervisor::run_supervisor({
                workspace => $fx->{workspace}, duration => 0.2,
                expected_sha256 => $fx->{bin_sha},
                disk_check_fn => sub { 30 * 1024 * 1024 * 1024 },
                term_timeout_sec => 0.15, kill_timeout_sec => 0.2,
            });
        };
        $error = $@;
    }
    chdir($previous) or die "restore cwd: $!";
    umask($previous_umask);
    is($error, '', 'run did not throw');
    is($rc, 0, 'bounded native child completed');
    my $probe = File::Spec->catfile($fx->{workspace}, '.local', 'child-context.json');
    ok(-f $probe, 'relative child output confined to workspace');
    my $context = -f $probe ? read_json_file($probe) : {};
    is($context->{cwd}, Cwd::abs_path($fx->{workspace}), 'child working directory is workspace');
    is($context->{has_override}, 0, 'environment cannot override loopback config');
    my $mode = -f $probe ? ((stat($probe))[2] & 07777) : undef;
    is($mode, 0600, 'child output is private even with caller umask 0022');
    ok(!-e File::Spec->catfile($caller, '.local', 'child-context.json'), 'caller directory untouched');
};

subtest 'Aux timeout remains bounded when a descendant holds stdout open' => sub {
    my $t0 = Time::HiRes::time();
    my $result = AirRecordingSupervisor::run_bounded_aux_command([
        $^X, '-e',
        'my $p=fork(); defined($p) or exit 127; if(!$p){select(undef,undef,undef,2);exit 0;} exit 0;',
    ], 0.15);
    my $elapsed = Time::HiRes::time() - $t0;
    ok($result->{timed_out}, 'held pipe is treated as an unfinished timed-out command');
    ok($elapsed < 1.2, 'does not block until descendant closes stdout');
};

subtest 'Unterminated credential fragment is not persisted at child EOF' => sub {
    my $fx = setup_fixture_workspace(child_script => <<'PERL');
syswrite(STDOUT, "partial Cam!Pass#");
exit 0;
PERL
    AirRecordingSupervisor::run_supervisor({
        workspace => $fx->{workspace}, duration => 2,
        expected_sha256 => $fx->{bin_sha},
        disk_check_fn => sub { 30 * 1024 * 1024 * 1024 },
        term_timeout_sec => 0.15, kill_timeout_sec => 0.2,
    });
    my $log = slurp_file(File::Spec->catfile($fx->{workspace}, '.local', 'recording-service', 'supervisor.log'));
    unlike($log, qr/Cam!Pass#/, 'partial credential never written');
};

subtest 'Healthy status reflects periodic disk observations' => sub {
    my $fx = setup_fixture_workspace(child_script => <<'PERL');
$|=1;
print "INF [path live] stream is available and online, 1 track (H264)\n";
select(undef, undef, undef, 2);
PERL
    my @available = map { $_ * 1024 * 1024 * 1024 } (30, 29, 28);
    my @observed;
    my $real_writer = \&AirRecordingSupervisor::write_status_json;
    {
        no warnings 'redefine'; # Observe real status writes, not a production bypass.
        local *AirRecordingSupervisor::write_status_json = sub {
            push @observed, { %{$_[1]} };
            return $real_writer->(@_);
        };
        AirRecordingSupervisor::run_supervisor({
            workspace => $fx->{workspace}, duration => 0.3,
            expected_sha256 => $fx->{bin_sha}, disk_interval => 0.06,
            disk_check_fn => sub { @available ? shift(@available) : 28 * 1024 * 1024 * 1024 },
            term_timeout_sec => 0.15, kill_timeout_sec => 0.2,
        });
    }
    ok(scalar(grep { $_->{state} eq 'running' && $_->{availableBytes} == 29 * 1024 * 1024 * 1024 } @observed),
        'running status updates with current free space');
};

done_testing();
