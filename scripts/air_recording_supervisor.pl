#!/usr/bin/env perl
package AirRecordingSupervisor;

use strict;
use warnings;

use Digest::SHA ();
use Encode ();
use Fcntl qw(:DEFAULT :flock :seek);
use File::Spec ();
use File::Temp ();
use Getopt::Long qw(GetOptionsFromArray);
use IO::Select ();
use JSON::PP ();
use POSIX qw(:sys_wait_h :errno_h strftime);
use Time::HiRes ();

# A leader is not reaped until its process group has been cleaned. Its PID
# therefore cannot be recycled between a timeout and the final group signal.
my %OWNED_CHILDREN;

use constant {
    PINNED_MEDIAMTX_SHA256   => '2d21dd021fa7d0e667b24f8850555f29d718424c19d5ce9e18163a8b893034fd',
    PINNED_LINUX_AMD64_SHA256 => 'bfa372a169751bbf6da2ebddcbcd2f7d3ab3dca3cc553022162eda36fe03e73d',
    RESERVE_BYTES            => 15 * 1024 * 1024 * 1024,
    MAX_DURATION_SEC         => 86400,
    DEFAULT_DISK_CHECK_SEC   => 10.0,
    DEFAULT_MAX_LOG_BYTES    => 5 * 1024 * 1024,
    DEFAULT_LOG_ROTATIONS    => 2,
    DEFAULT_MAX_LINE_BYTES   => 4096,
    DEFAULT_AUX_TIMEOUT_SEC  => 1.2,
    DEFAULT_TERM_TIMEOUT_SEC => 2.0,
    DEFAULT_KILL_TIMEOUT_SEC => 1.0,
    PATCH_LIVE_URL           => 'http://127.0.0.1:9997/v3/config/paths/patch/live',
    PATCH_LIVE_BODY          => '{"record":false}',
    DF_BIN                   => '/bin/df',
    CURL_BIN                 => '/usr/bin/curl',
};

sub _o_nofollow {
    my $val = eval { Fcntl::O_NOFOLLOW() };
    return defined($val) ? $val : 0;
}

sub _fd_cloexec {
    my ($fh) = @_;
    eval {
        my $flags = fcntl($fh, F_GETFD, 0);
        if (defined $flags) {
            fcntl($fh, F_SETFD, $flags | FD_CLOEXEC);
        }
    };
    return;
}

sub _iso_utc {
    my ($epoch) = @_;
    $epoch = time() unless defined $epoch;
    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(int($epoch)));
}

sub uri_escape_upper {
    my ($str) = @_;
    return '' unless defined $str;
    my $out = Encode::encode_utf8($str);
    $out =~ s/([^A-Za-z0-9\-_.~])/sprintf("%%%02X", ord($1))/ge;
    return $out;
}

sub uri_escape_lower {
    my ($str) = @_;
    return '' unless defined $str;
    my $out = Encode::encode_utf8($str);
    $out =~ s/([^A-Za-z0-9\-_.~])/sprintf("%%%02x", ord($1))/ge;
    return $out;
}

sub uri_unescape {
    my ($str) = @_;
    return '' unless defined $str;
    my $out = $str;
    $out =~ s/%([0-9A-Fa-f]{2})/chr(hex($1))/ge;
    return $out;
}

sub _secret_flex_regex {
    my ($secret) = @_;
    return undef unless defined($secret) && length($secret) > 0;
    my @parts;
    for my $ch (split //, Encode::encode_utf8($secret)) {
        my $hex = sprintf('%02x', ord($ch));
        my $literal = quotemeta($ch);
        push @parts, "(?:$literal|%(?i:$hex))";
    }
    my $pat = join('', @parts);
    return qr/$pat/;
}

sub redact_text {
    my ($text, $secrets_ref) = @_;
    return '' unless defined($text) && length($text) > 0;
    my $out = $text;

    if ($secrets_ref && ref($secrets_ref) eq 'ARRAY') {
        my %seen;
        my @unique = grep { defined($_) && length($_) > 0 && !$seen{$_}++ } @$secrets_ref;
        @unique = sort { length($b) <=> length($a) } @unique;
        for my $sec (@unique) {
            for my $variant ($sec, Encode::encode_utf8($sec), uri_escape_upper($sec), uri_escape_lower($sec), uri_unescape($sec)) {
                next unless defined($variant) && length($variant) > 0;
                $out =~ s/\Q$variant\E/[REDACTED]/g;
                if ($variant =~ /%[0-9A-Fa-f]{2}/) {
                    $out =~ s/\Q$variant\E/[REDACTED]/gi;
                }
            }
            my $flex_re = _secret_flex_regex($sec);
            if ($flex_re) {
                $out =~ s/$flex_re/[REDACTED]/g;
            }
        }
    }
    # Remove known secrets first, so delimiters inside a raw password cannot
    # make the generic URL/key filters leave a credential fragment behind.
    $out =~ s{((?:rtsps?|https?|whips?)://)([^/\s\@]+)\@}{$1\[REDACTED]\@}gi;
    $out =~ s{((?:rtsps?|https?|whips?)://)([^\s/\@]+:[^\s/\@]*)(?=\s|/|\z)}{$1\[REDACTED]}gi;
    $out =~ s{\b(password|passwd|pass|secret|token|whipBearerToken|authorization)(\s*[:=]\s*)(?:(?:Bearer|Basic|Digest)\s+)?([^\s&"',;]+)}{$1$2\[REDACTED]}gi;
    return $out;
}

sub parse_cli_args {
    my (@argv) = @_;
    my $workspace;
    my $duration;
    my @copy = @argv;
    my $ok = GetOptionsFromArray(
        \@copy,
        'workspace=s' => \$workspace,
        'duration=s'  => \$duration,
    );
    if (!$ok || @copy) {
        die "Usage: perl scripts/air_recording_supervisor.pl --workspace ABS_PATH [--duration SECONDS]\n";
    }
    if (!defined($workspace) || $workspace eq '') {
        die "Invalid --workspace: absolute workspace path is required.\n";
    }
    if ($workspace =~ /[\x00-\x1f\x7f]/) {
        die "Invalid --workspace: control characters are not allowed.\n";
    }
    if (!File::Spec->file_name_is_absolute($workspace) || $workspace !~ m{\A/}) {
        die "Invalid --workspace: path must be absolute.\n";
    }
    my @parts = grep { length($_) > 0 } split(m{/+}, $workspace);
    if (grep { $_ eq '.' || $_ eq '..' } @parts) {
        die "Invalid --workspace: relative traversal segments are not allowed.\n";
    }

    my $duration_num;
    if (defined $duration) {
        if ($duration !~ /\A(?:0|[1-9]\d*)(?:\.\d+)?\z/) {
            die "Invalid --duration: must be a positive finite number of seconds.\n";
        }
        $duration_num = $duration + 0.0;
        if ($duration_num <= 0 || $duration_num > MAX_DURATION_SEC) {
            die sprintf("Invalid --duration: must be > 0 and <= %d seconds.\n", MAX_DURATION_SEC);
        }
    }
    return {
        workspace => $workspace,
        duration  => $duration_num,
    };
}

sub validate_no_symlink_chain {
    my ($workspace_root, @rel_parts) = @_;
    my @ws_stat = lstat($workspace_root);
    if (!@ws_stat) {
        die "Workspace root does not exist.\n";
    }
    if (-l _) {
        die "Refusing symlinked workspace root.\n";
    }
    if (!-d _) {
        die "Workspace root is not a directory.\n";
    }
    my $cur = $workspace_root;
    for my $part (@rel_parts) {
        if (!defined($part) || $part eq '' || $part eq '.' || $part eq '..' || $part =~ m{/}) {
            die "Invalid relative path segment.\n";
        }
        $cur = File::Spec->catfile($cur, $part);
        my @st = lstat($cur);
        if (@st && -l _) {
            die "Refusing symlink in path: $part\n";
        }
    }
    return $cur;
}

sub require_private_dir {
    my ($workspace_root, $create_if_missing, @rel_parts) = @_;
    my $path = validate_no_symlink_chain($workspace_root, @rel_parts);
    my @st = lstat($path);
    if (!@st) {
        if (!$create_if_missing) {
            die "Required private directory missing: " . join('/', @rel_parts) . "\n";
        }
        if (!mkdir($path, 0700)) {
            die "Failed to create private directory " . join('/', @rel_parts) . ": $!\n";
        }
        chmod(0700, $path) or die "Failed to set mode 0700 on " . join('/', @rel_parts) . ": $!\n";
        @st = lstat($path);
    }
    if (-l _) {
        die "Refusing symlinked directory: " . join('/', @rel_parts) . "\n";
    }
    if (!-d _) {
        die "Path is not a directory: " . join('/', @rel_parts) . "\n";
    }
    my $mode = $st[2] & 07777;
    if ($mode != 0700) {
        die sprintf("Directory %s must have mode 0700 (got %04o).\n", join('/', @rel_parts), $mode);
    }
    return $path;
}

sub require_private_file_0600 {
    my ($workspace_root, @rel_parts) = @_;
    my $path = validate_no_symlink_chain($workspace_root, @rel_parts);
    my @st = lstat($path);
    if (!@st) {
        die "Required private input missing: " . join('/', @rel_parts) . "\n";
    }
    if (-l _ || !-f _) {
        die "Required private input must be a regular non-symlink file: " . join('/', @rel_parts) . "\n";
    }
    my $mode = $st[2] & 07777;
    if ($mode != 0600) {
        die sprintf("Private file %s must have mode 0600 (got %04o).\n", join('/', @rel_parts), $mode);
    }
    return $path;
}

sub read_private_file {
    my ($path) = @_;
    my $flags = O_RDONLY | _o_nofollow();
    sysopen(my $fh, $path, $flags) or die "Unable to open private file: $!\n";
    my @st = stat($fh);
    if (!@st || !-f _) {
        close($fh);
        die "Opened path is not a regular file.\n";
    }
    if (($st[2] & 07777) != 0600) {
        close($fh);
        die "Opened private file does not have mode 0600.\n";
    }
    local $/;
    my $content = <$fh>;
    close($fh);
    return defined($content) ? $content : '';
}

sub validate_service_directory_files {
    my ($workspace_root) = @_;
    my $service_dir = require_private_dir($workspace_root, 1, '.local', 'recording-service');
    opendir(my $dh, $service_dir) or die "Unable to inspect service directory: $!\n";
    my @entries = grep { $_ ne '.' && $_ ne '..' } readdir($dh);
    closedir($dh);

    for my $entry (@entries) {
        my $full = File::Spec->catfile($service_dir, $entry);
        my @st = lstat($full);
        if (!@st) {
            die "Unable to stat service file $entry: $!\n";
        }
        if (-l _) {
            die "Refusing symlinked service file: $entry\n";
        }
        if (!-f _) {
            die "Refusing non-regular entry in service directory: $entry\n";
        }
        my $mode = $st[2] & 07777;
        if ($entry eq 'launchd.stdout.log' || $entry eq 'launchd.stderr.log') {
            if (($mode & 0022) != 0) {
                die sprintf("Insecure writable launchd log %s (mode %04o).\n", $entry, $mode);
            }
            if ($mode != 0600) {
                chmod(0600, $full) or die "Failed to enforce 0600 on $entry: $!\n";
            }
        } else {
            if ($mode != 0600) {
                die sprintf("Existing service file %s must have mode 0600 (got %04o).\n", $entry, $mode);
            }
        }
    }
    return $service_dir;
}

sub load_and_extract_secrets {
    my ($workspace_root) = @_;
    my $cam_path   = require_private_file_0600($workspace_root, '.local', 'camera-source.json');
    my $admin_path = require_private_file_0600($workspace_root, '.local', 'recording-admin.json');
    my $cfg_path   = require_private_file_0600($workspace_root, '.local', 'mediamtx.recording.poc.yml');

    my $cam_raw   = read_private_file($cam_path);
    my $admin_raw = read_private_file($admin_path);
    my $cfg_raw   = read_private_file($cfg_path);

    my $cam_obj = eval { JSON::PP::decode_json($cam_raw) };
    if ($@ || ref($cam_obj) ne 'HASH') {
        die "Invalid JSON object in .local/camera-source.json\n";
    }
    my $cam_user = $cam_obj->{username};
    my $cam_pass = $cam_obj->{password};
    if (!defined($cam_user) || ref($cam_user) || $cam_user eq '' || $cam_user =~ /[\x00-\x1f\x7f]/) {
        die "Invalid camera username in .local/camera-source.json\n";
    }
    if (!defined($cam_pass) || ref($cam_pass) || $cam_pass eq '' || $cam_pass =~ /[\x00-\x1f\x7f]/) {
        die "Invalid camera password in .local/camera-source.json\n";
    }

    my $admin_obj = eval { JSON::PP::decode_json($admin_raw) };
    if ($@ || ref($admin_obj) ne 'HASH') {
        die "Invalid JSON object in .local/recording-admin.json\n";
    }
    my $adm_user = defined($admin_obj->{username}) ? $admin_obj->{username} : $admin_obj->{user};
    my $adm_pass = defined($admin_obj->{password}) ? $admin_obj->{password} : $admin_obj->{pass};
    if (!defined($adm_user) || ref($adm_user) || $adm_user eq '' || $adm_user =~ /[\x00-\x1f\x7f]/) {
        die "Invalid playback username in .local/recording-admin.json\n";
    }
    if (!defined($adm_pass) || ref($adm_pass) || $adm_pass eq '' || $adm_pass =~ /[\x00-\x1f\x7f]/) {
        die "Invalid playback password in .local/recording-admin.json\n";
    }

    if ($cfg_raw !~ /\bsourceOnDemand\s*:\s*no\b/ && $cfg_raw !~ /\bpaths\s*:/) {
        die "Invalid MediaMTX recording configuration in .local/mediamtx.recording.poc.yml\n";
    }

    my @secrets = ($cam_user, $cam_pass, $adm_user, $adm_pass);
    for my $obj ($cam_obj, $admin_obj) {
        for my $k (keys %$obj) {
            my $v = $obj->{$k};
            if (defined($v) && !ref($v) && length($v) > 0 && $k =~ /(?:user|pass|secret|token|key|pwd|url)/i) {
                push @secrets, $v;
            }
        }
    }

    while ($cfg_raw =~ m{((?:rtsps?|https?|whips?)://[^\s"']+)}gi) {
        my $url = $1;
        push @secrets, $url;
        if ($url =~ m{\A(?:rtsps?|https?|whips?)://([^/\s\@]+)\@}i) {
            my $userinfo = $1;
            push @secrets, $userinfo, uri_unescape($userinfo);
            my ($u, $p) = split(/:/, $userinfo, 2);
            for my $part ($u, $p) {
                if (defined($part) && length($part) > 0) {
                    push @secrets, $part, uri_unescape($part);
                }
            }
        }
    }

    # Accept the RFC 6750 bearer alphabet in plain or simply quoted scalars.
    # Refuse YAML aliases/block scalars instead of starting with an unknown
    # secret that could escape redaction. No YAML dependency is needed here.
    for my $line (split(/\r?\n/, $cfg_raw)) {
        next if $line =~ /^\h*#/;
        if ($line =~ /whipBearerToken/i && $line !~ /^\h*(?:-\h+)?whipBearerToken\h*:/i) {
            die "Unsupported whipBearerToken mapping in recording configuration.\n";
        }
    }
    while ($cfg_raw =~ m{^\h*(?:-\h+)?whipBearerToken\h*:\h*([^\r\n]*)}gmi) {
        my $scalar = $1;
        next if $scalar =~ /\A(?:""|'')?\h*(?:#.*)?\z/;
        my $token;
        if ($scalar =~ /\A([A-Za-z0-9._~+\/-]+=*)\h*(?:#.*)?\z/
            || $scalar =~ /\A"([A-Za-z0-9._~+\/-]+=*)"\h*(?:#.*)?\z/
            || $scalar =~ /\A'([A-Za-z0-9._~+\/-]+=*)'\h*(?:#.*)?\z/) {
            $token = $1;
        } else {
            die "Unsupported whipBearerToken scalar in recording configuration.\n";
        }
        push @secrets, $token;
    }

    while ($cfg_raw =~ m{^\s*(?:user|pass)\s*:\s*["']?([^"'\r\n#]+)["']?}gmi) {
        my $val = $1;
        $val =~ s/\s+\z//;
        if (length($val) > 0 && $val ne 'any' && $val ne '~' && $val ne 'null') {
            push @secrets, $val;
        }
    }

    my %seen;
    my @dedup = grep { defined($_) && length($_) > 0 && !$seen{$_}++ } @secrets;
    return {
        config_path => $cfg_path,
        secrets     => \@dedup,
    };
}

sub platform_binary_sha256 {
    my ($system, $machine) = @_;
    $system = lc(defined($system) ? $system : $^O);
    $machine = lc(defined($machine) ? $machine : (POSIX::uname())[4]);
    if ($machine eq 'x86_64' || $machine eq 'amd64') {
        return PINNED_MEDIAMTX_SHA256 if $system eq 'darwin';
        return PINNED_LINUX_AMD64_SHA256 if $system eq 'linux';
    }
    die "Unsupported native supervisor platform.\n";
}

sub verify_mediamtx_binary {
    my ($workspace_root, $expected_sha256) = @_;
    $expected_sha256 = platform_binary_sha256() unless defined $expected_sha256;
    my $bin_path = validate_no_symlink_chain(
        $workspace_root, '.local', 'tools', 'mediamtx-1.21.3', 'mediamtx'
    );
    my @st = lstat($bin_path);
    if (!@st || -l _ || !-f _) {
        die "Pinned MediaMTX binary missing or not a regular non-symlink file.\n";
    }
    my $mode = $st[2] & 07777;
    if (($mode & 0111) == 0) {
        die "Pinned MediaMTX binary is not executable.\n";
    }
    if (($mode & 0022) != 0) {
        die sprintf("Pinned MediaMTX binary has insecure writable permissions (%04o).\n", $mode);
    }

    my $flags = O_RDONLY | _o_nofollow();
    sysopen(my $fh, $bin_path, $flags) or die "Failed to open MediaMTX binary for hashing: $!\n";
    binmode($fh);
    my $sha = Digest::SHA->new(256);
    $sha->addfile($fh);
    my $digest = lc($sha->hexdigest());
    close($fh);

    if ($digest ne lc($expected_sha256)) {
        die sprintf(
            "MediaMTX binary SHA256 mismatch (expected %s, got %s).\n",
            lc($expected_sha256), $digest
        );
    }
    return $bin_path;
}

sub atomic_write_private_file {
    my ($service_dir, $filename, $content) = @_;
    if ($filename =~ m{/} || $filename eq '.' || $filename eq '..') {
        die "Invalid service filename.\n";
    }
    my @dir_st = lstat($service_dir);
    if (!@dir_st || -l _ || !-d _ || (($dir_st[2] & 07777) != 0700)) {
        die "Service directory is missing, symlinked, or does not have mode 0700.\n";
    }
    my $target = File::Spec->catfile($service_dir, $filename);
    my @t_st = lstat($target);
    if (@t_st) {
        if (-l _ || !-f _) {
            die "Refusing to overwrite symlink or non-regular file: $filename\n";
        }
        if (($t_st[2] & 07777) != 0600) {
            die "Refusing to overwrite file with insecure permissions: $filename\n";
        }
    }

    my $tmp_name = sprintf('.%s.%d.%d.tmp', $filename, $$, int(Time::HiRes::time() * 1000000));
    my $tmp_path = File::Spec->catfile($service_dir, $tmp_name);
    my $flags = O_WRONLY | O_CREAT | O_EXCL | _o_nofollow();
    sysopen(my $fh, $tmp_path, $flags, 0600) or die "Failed to create temporary file in service dir: $!\n";
    eval {
        chmod(0600, $fh);
        my $len = length($content);
        my $off = 0;
        while ($off < $len) {
            my $w = syswrite($fh, $content, $len - $off, $off);
            die "Failed to write temporary service file: $!\n" unless defined $w;
            $off += $w;
        }
        close($fh) or die "Failed to close temporary service file: $!\n";
        chmod(0600, $tmp_path) or die "Failed to chmod 0600 temporary service file: $!\n";
        rename($tmp_path, $target) or die "Failed to rename temporary service file into place: $!\n";
        chmod(0600, $target) or die "Failed to verify 0600 on service file: $!\n";
    };
    if (my $err = $@) {
        unlink($tmp_path) if -e $tmp_path;
        die $err;
    }
    my @final_st = lstat($target);
    if (!@final_st || -l _ || !-f _ || (($final_st[2] & 07777) != 0600)) {
        die "Failed to enforce 0600 permissions on $filename\n";
    }
    return $target;
}

sub write_status_json {
    my ($service_dir, $fields) = @_;
    my $pid_val = exists($fields->{pid}) ? $fields->{pid} : $$;
    my $paused  = $fields->{recordingPaused} ? JSON::PP::true : JSON::PP::false;
    my $latched = $fields->{authLatchActive} ? JSON::PP::true : JSON::PP::false;
    my $payload = {
        state           => defined($fields->{state})  ? "$fields->{state}"  : 'unknown',
        reason          => defined($fields->{reason}) ? "$fields->{reason}" : '',
        PID             => $pid_val,
        pid             => $pid_val,
        supervisorPid   => $$,
        mediamtxPid     => $fields->{mediamtxPid},
        recordingPaused => $paused,
        authLatchActive => $latched,
        reserveBytes    => RESERVE_BYTES,
        availableBytes  => $fields->{availableBytes},
        updatedAt       => _iso_utc($fields->{now}),
    };
    if (defined $fields->{childExitCode}) {
        $payload->{childExitCode} = $fields->{childExitCode} + 0;
    }
    if (defined $fields->{childSignal}) {
        $payload->{childSignal} = $fields->{childSignal} + 0;
    }
    my $json = JSON::PP->new->utf8->canonical->pretty->encode($payload);
    return atomic_write_private_file($service_dir, 'status.json', $json);
}

sub append_bounded_log {
    my ($service_dir, $line, $secrets_ref, $opts) = @_;
    $opts ||= {};
    my $max_bytes = $opts->{max_log_bytes} || DEFAULT_MAX_LOG_BYTES;
    my $rotations = exists($opts->{log_rotations}) ? $opts->{log_rotations} : DEFAULT_LOG_ROTATIONS;
    my $now       = $opts->{now};

    my $clean = redact_text($line, $secrets_ref);
    $clean =~ s/[\r\n]+\z//;
    my $entry = sprintf("%s %s\n", _iso_utc($now), $clean);
    if (length($entry) > $max_bytes) {
        $entry = substr($entry, 0, $max_bytes - 1) . "\n";
    }

    my $log_path = File::Spec->catfile($service_dir, 'supervisor.log');
    my @st = lstat($log_path);
    if (@st) {
        if (-l _ || !-f _ || (($st[2] & 07777) != 0600)) {
            die "Refusing to write to insecure or symlinked supervisor.log\n";
        }
        if ($st[7] + length($entry) > $max_bytes && $st[7] > 0) {
            for (my $i = $rotations; $i >= 1; $i--) {
                my $src = ($i == 1)
                    ? $log_path
                    : File::Spec->catfile($service_dir, "supervisor.log." . ($i - 1));
                my $dst = File::Spec->catfile($service_dir, "supervisor.log.$i");
                my @dst_st = lstat($dst);
                if (@dst_st && (-l _ || !-f _ || (($dst_st[2] & 07777) != 0600))) {
                    die "Refusing to rotate into insecure or symlinked supervisor.log.$i\n";
                }
                my @src_st = lstat($src);
                if (@src_st) {
                    if (-l _ || !-f _ || (($src_st[2] & 07777) != 0600)) {
                        die "Refusing to rotate insecure or symlinked log file\n";
                    }
                    rename($src, $dst) or die "Failed to rotate log file: $!\n";
                    chmod(0600, $dst) or die "Failed to enforce 0600 on rotated log: $!\n";
                }
            }
        }
    }

    my $flags = O_WRONLY | O_CREAT | O_APPEND | _o_nofollow();
    sysopen(my $fh, $log_path, $flags, 0600) or die "Failed to open supervisor.log: $!\n";
    chmod(0600, $fh);
    my $len = length($entry);
    my $off = 0;
    while ($off < $len) {
        my $w = syswrite($fh, $entry, $len - $off, $off);
        last unless defined $w;
        $off += $w;
    }
    close($fh);
    chmod(0600, $log_path);
    return $clean;
}

sub classify_child_log_line {
    my ($line) = @_;
    return 'normal' unless defined($line) && length($line) > 0;

    # Native v1.21.3 forward logs share [path live] with the camera source.
    # Destination auth, network, and recovery messages describe only outbound
    # delivery; they must never latch, degrade, or restore the local source.
    if ($line =~ m{\[(?:whips?|rtsps?|rtmps?|srt|moqt)\s+dest\s+\d+\s+[0-9a-f]{8}\]}i) {
        return 'forward_destination';
    }

    # Playback, WebRTC, or control API listener lines must never be confused with RTSP camera source auth.
    if ($line =~ m{\[(?:playback|webrtc|api|hls|rtmp|srt)\]}i
        || $line =~ m{\b127\.0\.0\.1:(?:9996|9997|8889|8554)\b}
        || $line =~ m{\b(?:GET|HEAD|POST|PATCH|PUT|DELETE|OPTIONS)\s+/(?:get|list|v3/)}i
        || $line =~ m{\bplayback\b.*\b(?:401|403|unauthorized|forbidden|auth)}i
        || $line =~ m{\bhttp(?:/1\.[01])?\s+(?:status\s+)?(?:401|403)\b}i)
    {
        return 'playback_or_local_http';
    }

    # Camera RTSP source authentication failure (401/403/unauthorized/forbidden/auth failure)
    my $is_source_context = (
        $line =~ m{\[rtsp\s+source\]}i
        || $line =~ m{\[path\s+live\]}i
        || $line =~ m{\brtsp\s+source\b}i
        || $line =~ m{\brtsp/1\.0\s+(?:401|403)\b}i
        || $line =~ m{\b(?:describe|setup|play)\b.*\b(?:401|403|unauthorized|forbidden)\b}i
    );
    my $is_auth_rejection = (
        $line =~ m{\bbad\s+status\s+code:\s*(?:401|403)\b}i
        || $line =~ m{\bstatus\s+code[:\s]+(?:401|403)\b}i
        || $line =~ m{\brtsp/1\.0\s+(?:401|403)\b}i
        || $line =~ m{\b(?:401\s+unauthorized|403\s+forbidden)\b}i
        || $line =~ m{\b(?:unauthorized|forbidden)\b}i
        || $line =~ m{\bauth(?:entication|orization)?\s+(?:fail(?:ed|ure)?|error|denied|rejected)\b}i
    );
    if ($is_source_context && $is_auth_rejection) {
        return 'camera_auth_failure';
    }

    # Source recovered / publishing ready
    if ($line =~ m{\[rtsp\s+source\]\s+(?:is\s+publishing|ready)\b}i
        || $line =~ m{\[path\s+live\].*\bis\s+publishing\b}i
        || $line =~ m{\[path\s+live\].*\bstream is available and online\b}i
        || $line =~ m{\bsource\s+ready\b}i)
    {
        return 'source_ready';
    }

    # Transient LAN / camera RTSP source loss
    if ($is_source_context
        && ($line =~ m{\bERR\b}
            || $line =~ m{\b(?:i/o\s+timeout|timed\s+out|connection\s+refused|connection\s+reset|no\s+route\s+to\s+host|network\s+is\s+unreachable|eof|closed|terminated|not\s+ready|read\s+error|dial\s+tcp)\b}i))
    {
        return 'source_transient_error';
    }

    return 'normal';
}

sub terminate_owned_process {
    my ($pid, $pgid, $term_timeout, $kill_timeout, $clock_fn) = @_;
    return 0 unless defined($pid) && $pid > 0;
    die "Refusing to signal an unowned child.\n" unless exists $OWNED_CHILDREN{$pid};
    $term_timeout = DEFAULT_TERM_TIMEOUT_SEC unless defined($term_timeout) && $term_timeout >= 0;
    $kill_timeout = DEFAULT_KILL_TIMEOUT_SEC unless defined($kill_timeout) && $kill_timeout >= 0;
    $clock_fn ||= \&Time::HiRes::time;

    my $owned_group = $OWNED_CHILDREN{$pid};
    if (defined($owned_group) && $owned_group > 0) {
        kill('TERM', -$owned_group);
    }
    kill('TERM', $pid);

    my $deadline = $clock_fn->() + $term_timeout;
    while ($clock_fn->() < $deadline) {
        Time::HiRes::sleep(0.03);
    }
    if (defined($owned_group) && $owned_group > 0) {
        kill('KILL', -$owned_group);
    }
    kill('KILL', $pid);

    my $kill_deadline = $clock_fn->() + $kill_timeout;
    while ($clock_fn->() < $kill_deadline) {
        my $w = waitpid($pid, WNOHANG);
        if ($w == $pid) {
            my $status = $?;
            delete $OWNED_CHILDREN{$pid};
            return $status;
        }
        if ($w == -1) {
            delete $OWNED_CHILDREN{$pid};
            die "Owned child was unexpectedly reaped elsewhere.\n";
        }
        Time::HiRes::sleep(0.02);
    }
    die "Owned child did not exit within the cleanup deadline.\n";
}

sub run_bounded_aux_command {
    my ($argv_ref, $timeout_sec, $clock_fn) = @_;
    if (!ref($argv_ref) || ref($argv_ref) ne 'ARRAY' || !@$argv_ref) {
        return { ok => 0, timed_out => 0, exit_code => -1, stdout => '' };
    }
    $timeout_sec = DEFAULT_AUX_TIMEOUT_SEC unless defined($timeout_sec) && $timeout_sec > 0;
    $clock_fn ||= \&Time::HiRes::time;
    local $SIG{CHLD} = 'DEFAULT';

    pipe(my $r_fh, my $w_fh) or return { ok => 0, timed_out => 0, exit_code => -1, stdout => '' };
    _fd_cloexec($r_fh);

    my $pid = fork();
    if (!defined $pid) {
        close($r_fh);
        close($w_fh);
        return { ok => 0, timed_out => 0, exit_code => -1, stdout => '' };
    }
    if ($pid == 0) {
        eval { POSIX::setpgid(0, 0) == 0 } or POSIX::_exit(126);
        close($r_fh);
        open(STDIN, '<', '/dev/null') or POSIX::_exit(126);
        open(STDOUT, '>&', $w_fh)     or POSIX::_exit(126);
        open(STDERR, '>', '/dev/null') or POSIX::_exit(126);
        close($w_fh);
        my $prog = $argv_ref->[0];
        exec { $prog } @$argv_ref or POSIX::_exit(127);
    }

    eval { POSIX::setpgid($pid, $pid) };
    $OWNED_CHILDREN{$pid} = getpgrp($pid) == $pid ? $pid : undef;
    close($w_fh);

    my $sel = IO::Select->new($r_fh);
    my $deadline = $clock_fn->() + $timeout_sec;
    my $stdout = '';
    my $eof = 0;

    while (!$eof) {
        my $rem = $deadline - $clock_fn->();
        last if $rem <= 0;
        my @ready = $sel->can_read($rem > 0.1 ? 0.1 : $rem);
        if (@ready) {
            my $buf = '';
            my $n = sysread($r_fh, $buf, 4096);
            if (!defined $n) {
                next if $! == EINTR;
                last;
            }
            if ($n == 0) {
                $eof = 1;
                last;
            }
            if (length($stdout) < 16384) {
                $stdout .= substr($buf, 0, 16384 - length($stdout));
            }
        }
    }

    close($r_fh);
    my $status = terminate_owned_process($pid, $pid, 0.2, 0.2, $clock_fn);
    return {
        ok        => ($eof && $status == 0 ? 1 : 0),
        timed_out => ($eof ? 0 : 1),
        exit_code => ($status >> 8),
        stdout    => $stdout,
    };
}

sub check_available_disk_bytes {
    my ($workspace_root, $timeout_sec, $clock_fn) = @_;
    if (!-x DF_BIN) {
        return undef;
    }
    my $res = run_bounded_aux_command([DF_BIN, '-k', '-P', $workspace_root], $timeout_sec, $clock_fn);
    return undef if !$res || !$res->{ok} || $res->{timed_out};
    my @lines = grep { /\S/ } split(/\r?\n/, $res->{stdout} // '');
    return undef if @lines < 2;
    my $last = $lines[-1];
    if ($last =~ /\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+%/) {
        my $avail_kb = $3 + 0;
        return $avail_kb * 1024;
    }
    return undef;
}

sub pause_recording_via_api {
    my ($timeout_sec, $clock_fn) = @_;
    if (!-x CURL_BIN) {
        return 0;
    }
    my $argv = [
        CURL_BIN,
        '-q',
        '--noproxy', '*',
        '--max-redirs', '0',
        '-sS',
        '--connect-timeout', '1',
        '--max-time', '1',
        '-o', '/dev/null',
        '-w', '%{http_code}',
        '-X', 'PATCH',
        '-H', 'Content-Type: application/json',
        '-d', PATCH_LIVE_BODY,
        PATCH_LIVE_URL,
    ];
    my $res = run_bounded_aux_command($argv, $timeout_sec, $clock_fn);
    return 0 if !$res || !$res->{ok} || $res->{timed_out};
    my $http_code = $res->{stdout} // '';
    $http_code =~ s/\s+//g;
    return ($http_code eq '200') ? 1 : 0;
}

sub run_supervisor {
    my ($opts) = @_;
    $opts ||= {};
    local $SIG{CHLD} = 'DEFAULT';
    my $workspace = $opts->{workspace};
    my $duration  = $opts->{duration};
    # Used only by the login-service entry point. Recording starts disabled
    # before native exec, then the authenticated server reconciles its intent.
    my $managed_start = $opts->{managed_start} ? 1 : 0;

    my $parsed = parse_cli_args(
        '--workspace' => (defined($workspace) ? $workspace : ''),
        (defined($duration) ? ('--duration' => $duration) : ()),
    );
    $workspace = $parsed->{workspace};
    $duration  = $parsed->{duration};

    my $clock_fn         = $opts->{clock_fn}         || \&Time::HiRes::time;
    my $disk_check_fn    = $opts->{disk_check_fn};
    my $pause_api_fn     = $opts->{pause_api_fn};
    my $expected_sha256  = $opts->{expected_sha256}  || platform_binary_sha256();
    my $disk_interval    = $opts->{disk_interval}    || DEFAULT_DISK_CHECK_SEC;
    my $max_log_bytes    = $opts->{max_log_bytes}    || DEFAULT_MAX_LOG_BYTES;
    my $log_rotations    = exists($opts->{log_rotations}) ? $opts->{log_rotations} : DEFAULT_LOG_ROTATIONS;
    my $max_line_bytes   = $opts->{max_line_bytes}   || DEFAULT_MAX_LINE_BYTES;
    my $aux_timeout_sec  = $opts->{aux_timeout_sec}  || DEFAULT_AUX_TIMEOUT_SEC;
    my $term_timeout_sec = $opts->{term_timeout_sec} || DEFAULT_TERM_TIMEOUT_SEC;
    my $kill_timeout_sec = $opts->{kill_timeout_sec} || DEFAULT_KILL_TIMEOUT_SEC;

    require_private_dir($workspace, 0, '.local');
    my $service_dir = validate_service_directory_files($workspace);

    my $secret_info = load_and_extract_secrets($workspace);
    my $config_path = $secret_info->{config_path};
    my $secrets_ref = $secret_info->{secrets};

    my $mediamtx_bin = verify_mediamtx_binary($workspace, $expected_sha256);

    # Acquire exclusive nonblocking flock before mutating any state
    my $lock_path = File::Spec->catfile($service_dir, 'supervisor.lock');
    my @lock_st = lstat($lock_path);
    if (@lock_st && (-l _ || !-f _ || (($lock_st[2] & 07777) != 0600))) {
        die "Refusing insecure or symlinked supervisor.lock\n";
    }
    my $lock_flags = O_RDWR | O_CREAT | _o_nofollow();
    sysopen(my $lock_fh, $lock_path, $lock_flags, 0600) or die "Unable to open supervisor.lock: $!\n";
    chmod(0600, $lock_fh);
    chmod(0600, $lock_path);
    _fd_cloexec($lock_fh);

    if (!flock($lock_fh, LOCK_EX | LOCK_NB)) {
        close($lock_fh);
        die "Another air_recording_supervisor instance is already holding supervisor.lock.\n";
    }

    my $log_opts = {
        max_log_bytes => $max_log_bytes,
        log_rotations => $log_rotations,
    };

    # Check persisted operator-attention auth latch
    my $latch_path = File::Spec->catfile($service_dir, 'auth-stop.latch');
    my @latch_st = lstat($latch_path);
    if (@latch_st) {
        if (-l _ || !-f _ || (($latch_st[2] & 07777) != 0600)) {
            close($lock_fh);
            die "Refusing insecure or symlinked auth-stop.latch\n";
        }
        $log_opts->{now} = $clock_fn->();
        append_bounded_log(
            $service_dir,
            "[supervisor] refusing startup: operator-attention auth-stop.latch is present",
            $secrets_ref,
            $log_opts
        );
        write_status_json($service_dir, {
            state           => 'stopped',
            reason          => 'auth_latch_present',
            pid             => $$,
            mediamtxPid     => undef,
            recordingPaused => 1,
            authLatchActive => 1,
            availableBytes  => undef,
            now             => $clock_fn->(),
        });
        close($lock_fh);
        return 0 if $managed_start; # SuccessfulExit=false must not retry auth.
        die "Refusing to reconnect: operator-attention auth latch is active (.local/recording-service/auth-stop.latch).\n";
    }

    # Check available disk space before starting
    my $avail_bytes = $disk_check_fn
        ? $disk_check_fn->($workspace)
        : check_available_disk_bytes($workspace, $aux_timeout_sec, $clock_fn);

    my $startup_disk_unsafe = !defined($avail_bytes) || $avail_bytes < RESERVE_BYTES;
    if ($startup_disk_unsafe && !$managed_start) {
        my $reason = defined($avail_bytes) ? 'disk_low' : 'disk_unknown';
        $log_opts->{now} = $clock_fn->();
        append_bounded_log(
            $service_dir,
            "[supervisor] refusing startup due to $reason",
            $secrets_ref,
            $log_opts
        );
        write_status_json($service_dir, {
            state           => 'stopped',
            reason          => $reason,
            pid             => $$,
            mediamtxPid     => undef,
            recordingPaused => 0,
            authLatchActive => 0,
            availableBytes  => $avail_bytes,
            now             => $clock_fn->(),
        });
        close($lock_fh);
        die "Refusing startup: insufficient or unknown disk space ($reason).\n";
    }

    my $stop_signal;
    local $SIG{TERM} = sub { $stop_signal = 'TERM' };
    local $SIG{INT}  = sub { $stop_signal = 'INT'  };
    local $SIG{HUP}  = sub { $stop_signal = 'HUP'  };

    # Spawn owned MediaMTX child in its own process group
    pipe(my $child_r, my $child_w) or do {
        close($lock_fh);
        die "Failed to create child output pipe: $!\n";
    };
    _fd_cloexec($child_r);

    my $child_pid = fork();
    if (!defined $child_pid) {
        close($child_r);
        close($child_w);
        close($lock_fh);
        die "Failed to fork MediaMTX child: $!\n";
    }

    if ($child_pid == 0) {
        close($lock_fh);
        close($child_r);
        eval { POSIX::setpgid(0, 0) == 0 } or POSIX::_exit(126);
        chdir($workspace) or POSIX::_exit(126);
        umask(0077);
        delete @ENV{grep { /^MTX_/ } keys %ENV};
        $ENV{MTX_PATHS_LIVE_RECORD} = 'false' if $managed_start;
        open(STDIN, '<', '/dev/null') or POSIX::_exit(126);
        open(STDOUT, '>&', $child_w)  or POSIX::_exit(126);
        open(STDERR, '>&', $child_w)  or POSIX::_exit(126);
        close($child_w);
        exec { $mediamtx_bin } ($mediamtx_bin, $config_path) or POSIX::_exit(127);
    }

    eval { POSIX::setpgid($child_pid, $child_pid) };
    $OWNED_CHILDREN{$child_pid} = getpgrp($child_pid) == $child_pid ? $child_pid : undef;
    close($child_w);

    my $child_pgid    = $child_pid;
    my $child_reaped  = 0;
    my $child_status  = undef;
    # With recording disabled before exec, native can safely clean expired
    # segments even at low disk. Keep enabling blocked until operator recovery.
    my $recording_paused  = $startup_disk_unsafe ? 1 : 0;
    my $auth_latch_active = 0;
    my $current_state     = $recording_paused ? 'paused' : 'starting';
    my $current_reason    = $recording_paused
        ? (defined($avail_bytes) ? 'disk_low' : 'disk_unknown') : 'source-not-ready';

    my $cleanup_child = sub {
        if (!$child_reaped && defined($child_pid) && $child_pid > 0) {
            $child_status = terminate_owned_process(
                $child_pid, $child_pgid, $term_timeout_sec, $kill_timeout_sec, $clock_fn
            );
            $child_reaped = 1;
        }
    };

    my $exit_code = 0;
    eval {
        my $now = $clock_fn->();
        $log_opts->{now} = $now;
        append_bounded_log(
            $service_dir,
            "[supervisor] started MediaMTX child pid=$child_pid",
            $secrets_ref,
            $log_opts
        );
        write_status_json($service_dir, {
            state           => $current_state,
            reason          => $current_reason,
            pid             => $$,
            mediamtxPid     => $child_pid,
            recordingPaused => $recording_paused,
            authLatchActive => $auth_latch_active,
            availableBytes  => $avail_bytes,
            now             => $now,
        });

        my $deadline       = defined($duration) ? ($now + $duration) : undef;
        my $next_disk_time = $now + $disk_interval;
        my $sel            = IO::Select->new($child_r);
        my $pending        = '';
        my $discard_line   = 0;
        my $pipe_eof       = 0;
        my $stop_reason    = undef;

        my $process_line = sub {
            my ($raw_line) = @_;
            $raw_line =~ s/\r\z//;
            my $class = classify_child_log_line($raw_line);
            $log_opts->{now} = $clock_fn->();
            append_bounded_log($service_dir, $raw_line, $secrets_ref, $log_opts);

            if ($class eq 'camera_auth_failure') {
                $auth_latch_active = 1;
                $current_state     = 'stopped';
                $current_reason    = 'camera_auth_failed';
                $stop_reason       = 'camera_auth_failed';
                my $latch_content = JSON::PP->new->utf8->canonical->pretty->encode({
                    reason    => 'camera_auth_failed',
                    latchedAt => _iso_utc($clock_fn->()),
                    pid       => $$,
                });
                atomic_write_private_file($service_dir, 'auth-stop.latch', $latch_content);
                append_bounded_log(
                    $service_dir,
                    "[supervisor] camera RTSP authentication failure detected; stopping child and persisting auth-stop.latch",
                    $secrets_ref,
                    $log_opts
                );
                return 0;
            } elsif ($class eq 'source_transient_error') {
                if (!$recording_paused && $current_state ne 'degraded') {
                    $current_state  = 'degraded';
                    $current_reason = 'source-not-ready';
                    write_status_json($service_dir, {
                        state           => $current_state,
                        reason          => $current_reason,
                        pid             => $$,
                        mediamtxPid     => $child_pid,
                        recordingPaused => $recording_paused,
                        authLatchActive => $auth_latch_active,
                        availableBytes  => $avail_bytes,
                        now             => $clock_fn->(),
                    });
                }
            } elsif ($class eq 'source_ready') {
                if (!$recording_paused && ($current_state eq 'degraded' || $current_state eq 'starting')) {
                    $current_state  = 'running';
                    $current_reason = 'ok';
                    write_status_json($service_dir, {
                        state           => $current_state,
                        reason          => $current_reason,
                        pid             => $$,
                        mediamtxPid     => $child_pid,
                        recordingPaused => $recording_paused,
                        authLatchActive => $auth_latch_active,
                        availableBytes  => $avail_bytes,
                        now             => $clock_fn->(),
                    });
                }
            }
            return 1;
        };

        my $drain_pipe_nonblocking = sub {
            my ($wait_sec) = @_;
            $wait_sec = 0 unless defined($wait_sec) && $wait_sec > 0;
            return 1 if $pipe_eof;
            my @ready = $sel->can_read($wait_sec);
            return 1 unless @ready;
            my $chunk = '';
            my $n = sysread($child_r, $chunk, 8192);
            if (!defined $n) {
                return 1 if $! == EINTR;
                $pipe_eof = 1;
                return 1;
            }
            if ($n == 0) {
                $pipe_eof = 1;
                if (length($pending) > 0 || $discard_line) {
                    append_bounded_log($service_dir,
                        '[supervisor] dropped incomplete child log line', $secrets_ref, $log_opts);
                }
                $pending = '';
                $discard_line = 0;
                return 1;
            }
            $pending .= $chunk;
            while ($pending =~ s/\A([^\n]*)\n//) {
                my $line = $1;
                if ($discard_line || length($line) > $max_line_bytes) {
                    $discard_line = 0;
                    $log_opts->{now} = $clock_fn->();
                    append_bounded_log(
                        $service_dir,
                        "[supervisor] dropped oversized child log line",
                        $secrets_ref,
                        $log_opts
                    );
                    next;
                }
                if (!$process_line->($line)) {
                    return 0;
                }
            }
            if (length($pending) > $max_line_bytes) {
                $pending = '';
                $discard_line = 1;
            }
            return 1;
        };

        while (1) {
            if (defined $stop_signal) {
                $stop_reason    = 'signal_received';
                $current_state  = 'stopped';
                $current_reason = 'signal_received';
                last;
            }

            my $now_loop = $clock_fn->();
            if (defined($deadline) && $now_loop >= $deadline) {
                $stop_reason    = 'duration_elapsed';
                $current_state  = 'stopped';
                $current_reason = 'duration_elapsed';
                last;
            }

            my $wait = 0.1;
            if (defined $deadline) {
                my $rem_d = $deadline - $now_loop;
                $wait = $rem_d if $rem_d < $wait;
            }
            my $rem_disk = $next_disk_time - $now_loop;
            if ($rem_disk < $wait) {
                $wait = $rem_disk > 0 ? $rem_disk : 0;
            }
            $wait = 0 if $wait < 0;

            if (!$drain_pipe_nonblocking->($wait)) {
                last;
            }

            if ($pipe_eof) {
                if (!defined $stop_reason) {
                    $stop_reason    = 'unexpected_child_exit';
                    $current_state  = 'failed';
                    $current_reason = 'unexpected_child_exit';
                    $exit_code      = 1;
                }
                last;
            }

            $now_loop = $clock_fn->();
            if ($now_loop >= $next_disk_time) {
                $next_disk_time = $now_loop + $disk_interval;
                $avail_bytes = $disk_check_fn
                    ? $disk_check_fn->($workspace)
                    : check_available_disk_bytes($workspace, $aux_timeout_sec, $clock_fn);

                # Check child output immediately after df before taking further action
                if (!$drain_pipe_nonblocking->(0)) {
                    last;
                }

                if (!defined($avail_bytes) || $avail_bytes < RESERVE_BYTES) {
                    if (!$recording_paused) {
                        my $paused_ok = $pause_api_fn
                            ? $pause_api_fn->()
                            : pause_recording_via_api($aux_timeout_sec, $clock_fn);

                        if ($paused_ok) {
                            $recording_paused = 1;
                            $current_state    = 'paused';
                            $current_reason   = 'disk_low';
                            $log_opts->{now}  = $clock_fn->();
                            append_bounded_log(
                                $service_dir,
                                "[supervisor] low disk space detected; recording paused via loopback API (live/playback retained)",
                                $secrets_ref,
                                $log_opts
                            );
                            write_status_json($service_dir, {
                                state           => $current_state,
                                reason          => $current_reason,
                                pid             => $$,
                                mediamtxPid     => $child_pid,
                                recordingPaused => $recording_paused,
                                authLatchActive => $auth_latch_active,
                                availableBytes  => $avail_bytes,
                                now             => $clock_fn->(),
                            });
                        } else {
                            $current_state  = 'stopped';
                            $current_reason = 'disk_low_pause_failed';
                            $stop_reason    = 'disk_low_pause_failed';
                            $exit_code      = 1;
                            $log_opts->{now} = $clock_fn->();
                            append_bounded_log(
                                $service_dir,
                                "[supervisor] low disk space and recording pause could not be confirmed; terminating MediaMTX child",
                                $secrets_ref,
                                $log_opts
                            );
                            last;
                        }
                    }
                }
                write_status_json($service_dir, {
                    state => $current_state, reason => $current_reason,
                    pid => $$, mediamtxPid => $child_pid,
                    recordingPaused => $recording_paused, authLatchActive => $auth_latch_active,
                    availableBytes => $avail_bytes, now => $clock_fn->(),
                });
            }
        }

        $cleanup_child->();
        while (!$pipe_eof) {
            last unless $sel->can_read(0);
            last unless $drain_pipe_nonblocking->(0);
        }
        close($child_r);

        my $child_exit_code = defined($child_status) ? ($child_status >> 8) : undef;
        my $child_sig       = defined($child_status) ? ($child_status & 127) : undef;

        $log_opts->{now} = $clock_fn->();
        append_bounded_log(
            $service_dir,
            sprintf("[supervisor] exiting state=%s reason=%s", $current_state, $current_reason),
            $secrets_ref,
            $log_opts
        );
        write_status_json($service_dir, {
            state           => $current_state,
            reason          => $current_reason,
            pid             => $$,
            mediamtxPid     => undef,
            recordingPaused => $recording_paused,
            authLatchActive => $auth_latch_active,
            availableBytes  => $avail_bytes,
            childExitCode   => $child_exit_code,
            childSignal     => $child_sig,
            now             => $clock_fn->(),
        });
    };
    my $err = $@;
    $cleanup_child->();
    eval { close($child_r) };
    eval { close($lock_fh) };
    if ($err) {
        die $err;
    }
    return $exit_code;
}

sub cli_main {
    my (@argv) = @_;
    my $code = eval {
        my $parsed = parse_cli_args(@argv);
        return run_supervisor($parsed);
    };
    if (my $err = $@) {
        my $msg = "$err";
        $msg =~ s/[\r\n]+\z//;
        $msg = redact_text($msg, []);
        print STDERR "ERROR: $msg\n";
        return 2;
    }
    return defined($code) ? $code : 0;
}

package main;

unless (caller) {
    exit(AirRecordingSupervisor::cli_main(@ARGV));
}

1;
