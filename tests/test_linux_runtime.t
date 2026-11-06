#!/usr/bin/env perl
use strict;
use warnings;
use Test::More;
use FindBin;
use File::Spec ();
use JSON::PP ();

require File::Spec->catfile($FindBin::Bin, '..', 'scripts', 'camera_roaming_proxy.pl');

subtest 'native binary pins reject the wrong operating system and CPU' => sub {
    is(AirRecordingSupervisor::platform_binary_sha256('linux', 'x86_64'),
        'bfa372a169751bbf6da2ebddcbcd2f7d3ab3dca3cc553022162eda36fe03e73d',
        'NUC uses the verified official Linux amd64 binary');
    is(AirRecordingSupervisor::platform_binary_sha256('darwin', 'x86_64'),
        AirRecordingSupervisor::PINNED_MEDIAMTX_SHA256(), 'existing Intel Mac pin preserved');
    for my $target (['linux', 'aarch64'], ['darwin', 'arm64'], ['MSWin32', 'AMD64']) {
        eval { AirRecordingSupervisor::platform_binary_sha256(@$target) };
        like($@, qr/Unsupported/, 'unverified supervisor target rejected');
    }
};

subtest 'Linux discovery uses only live physical IPv4 interfaces' => sub {
    my %physical = map { $_ => 1 } qw(wlo1 enp1s0 eno2 wlan0);
    my $address = sub { return { family => 'inet', local => $_[0], prefixlen => $_[1], scope => 'global' }; };
    my $interface = sub {
        return { ifname => $_[0], flags => ['UP', 'LOWER_UP', 'MULTICAST'], addr_info => [$_[1]] };
    };
    my $wifi = $interface->('wlo1', $address->('192.168.1.22', 24));
    my $ethernet = $interface->('enp1s0', $address->('10.20.1.10', 16));
    my $raw = JSON::PP::encode_json([
        $wifi, $ethernet,
        $interface->('docker0', $address->('172.17.0.1', 16)),
        { %{$interface->('eno2', $address->('192.168.2.10', 24))}, flags => ['UP'] },
        $interface->('wlan0', { family => 'inet6', local => '::1', prefixlen => 128, scope => 'host' }),
        $interface->('../wlo1', $address->('192.168.3.10', 24)),
    ]);
    my $networks = CameraRoamingProxy::parse_linux_networks($raw, sub { $physical{$_[0]} });
    is_deeply($networks, [
        { interface => 'wlo1', address => '192.168.1.22', mask => 0xffffff00 },
        { interface => 'enp1s0', address => '10.20.1.10', mask => 0xffff0000 },
    ], 'Wi-Fi and Ethernet supported; virtual/down/IPv6/unsafe names excluded');
    ok(CameraRoamingProxy::local_destination('10.20.9.64', $networks), 'customer subnet remains discoverable');
    ok(!CameraRoamingProxy::local_destination('172.17.0.64', $networks), 'container network cannot supply a camera');
    for my $bad ('{', '{}', JSON::PP::encode_json([{ %$wifi, addr_info => [$address->('192.168.1.22', 33)] }]),
                 JSON::PP::encode_json([{ %$wifi, addr_info => [$address->('127.0.0.1', 24)] }]),
                 JSON::PP::encode_json([{ %$wifi, addr_info => [$address->('192.168.1.022', 24)] }])) {
        is_deeply(CameraRoamingProxy::parse_linux_networks($bad, sub { 1 }), [], 'invalid discovery input fails closed');
    }
};

subtest 'probe UUID has the RFC 4122 version and variant without uuidgen' => sub {
    my %seen;
    for (1..8) {
        my $uuid = CameraRoamingProxy::new_probe_uuid();
        like($uuid, qr/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/,
            'valid version 4 UUID');
        ok(!$seen{$uuid}++, 'independent probe identifier');
    }
};

done_testing;
