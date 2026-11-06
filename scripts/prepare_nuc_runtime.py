#!/usr/bin/env python3
"""Prepare a private Linux edge bundle; never install, create keys or start services."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path

try:
    from scripts import poc
except ModuleNotFoundError:
    import poc


WORKSPACE = '/var/lib/devone-edge/camera'
SERVICE_USER = 'devone-edge'
SCRIPTS = (
    'air_recording_supervisor.pl', 'air_login_supervisor.pl',
    'camera_roaming_proxy.pl', 'air_web_gateway.pl',
    'poc.py', 'render_deployment.py',
)


def render_units():
    scripts = WORKSPACE + '/scripts/'
    roles = {
        'source': ('verified camera source proxy',
                   '/usr/bin/perl ' + scripts + 'camera_roaming_proxy.pl ' + WORKSPACE,
                   '', 'always', 5),
        'recording': ('managed MediaMTX supervisor',
                      '/usr/bin/perl ' + scripts + 'air_login_supervisor.pl --workspace ' + WORKSPACE,
                      'devone-edge-source.service', 'on-failure', 60),
        'gateway': ('authenticated loopback gateway',
                    '/usr/bin/perl ' + scripts + 'air_web_gateway.pl ' + WORKSPACE,
                    'devone-edge-recording.service', 'always', 10),
        'live-tunnel': ('outbound live tunnel',
                        '/usr/bin/ssh -N -F ' + WORKSPACE + '/.local/ssh/server-tunnel/config devone-server',
                        'devone-edge-gateway.service', 'always', 15),
        'maintenance-relay': ('outbound maintenance relay',
                              '/usr/bin/ssh -N -F ' + WORKSPACE + '/.local/ssh/maintenance-relay/config camera-maint-relay',
                              '', 'always', 30),
    }
    units = {}
    for name, (description, command, dependency, restart, delay) in roles.items():
        # Network outages must not exhaust a tunnel's restart budget. A camera
        # auth stop returns success from the managed entry point, so on-failure
        # leaves the recorder stopped until an operator reviews its latch.
        interval = 0 if name in ('live-tunnel', 'maintenance-relay') else 300
        text = f'''[Unit]
Description=DEV.ONE NUC {description}
Wants=network-online.target {dependency}
After=network-online.target {dependency}
StartLimitIntervalSec={interval}
StartLimitBurst=5

[Service]
Type=simple
User={SERVICE_USER}
Group={SERVICE_USER}
WorkingDirectory={WORKSPACE}
Environment=LC_ALL=C LANG=C
ExecStart={command}
Restart={restart}
RestartSec={delay}
TimeoutStopSec=15
KillMode=control-group
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
ReadWritePaths={WORKSPACE}/.local
ReadOnlyPaths={WORKSPACE}/.local/tools {WORKSPACE}/.local/ssh
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
'''
        units['devone-edge-' + name + '.service'] = text.encode()
    return units


def render_tunnel_profiles(server_ip):
    try:
        address = ipaddress.ip_address(server_ip)
    except ValueError:
        raise poc.PocError('A public VPS IPv4 address is required.') from None
    if address.version != 4 or not address.is_global:
        raise poc.PocError('A public VPS IPv4 address is required.')
    profiles = {}
    for role, alias, user, forwards in (
        ('server-tunnel', 'devone-server', 'devone-air', (
            '127.0.0.1:18554 127.0.0.1:8554', '127.0.0.1:19996 127.0.0.1:9900')),
        ('maintenance-relay', 'camera-maint-relay', 'camera-maint-relay', (
            '127.0.0.1:19022 127.0.0.1:22',)),
    ):
        directory = WORKSPACE + '/.local/ssh/' + role
        forward_text = ''.join('    RemoteForward ' + value + '\n' for value in forwards)
        profiles[role] = f'''Host {alias}
    HostName {address}
    Port 2222
    User {user}
    HostKeyAlias {address}
    HostKeyAlgorithms ssh-ed25519
    IdentityFile {directory}/id_ed25519
    UserKnownHostsFile {directory}/known_hosts
    GlobalKnownHostsFile /dev/null
    IdentitiesOnly yes
    IdentityAgent none
    BatchMode yes
    PreferredAuthentications publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    StrictHostKeyChecking yes
    UpdateHostKeys no
    ForwardAgent no
    ForwardX11 no
    RequestTTY no
    SessionType none
    ExitOnForwardFailure yes
    ServerAliveInterval 15
    ServerAliveCountMax 3
    ConnectTimeout 8
    ConnectionAttempts 1
    TCPKeepAlive yes
    Compression no
    LogLevel ERROR
{forward_text}'''.encode()
    return profiles


def prepare(output, *, server_ip, source_root=poc.REPO_ROOT):
    profiles = render_tunnel_profiles(server_ip)
    output = poc.validate_private_output_path(Path(output), workspace_root=source_root)
    if output.exists():
        raise poc.PocError('Refusing to overwrite a bundle; use a new output directory.')
    current = source_root.resolve()
    for part in output.relative_to(current).parts[:-1]:
        current = current / part
        current.mkdir(mode=0o700, exist_ok=True)
        if current.stat().st_mode & 0o077:
            raise poc.PocError('Bundle ancestors must be private directories with mode 0700.')
    output.mkdir(mode=0o700)
    entries = []

    def write(relative, payload, destination, mode, owner, group):
        target = output / relative
        target.parent.mkdir(mode=0o700, exist_ok=True)
        with target.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        entries.append({'file': relative, 'destination': destination,
                        'sha256': hashlib.sha256(payload).hexdigest(),
                        'mode': mode, 'owner': owner, 'group': group})

    for name in SCRIPTS:
        write('scripts/' + name, (source_root / 'scripts' / name).read_bytes(),
              WORKSPACE + '/scripts/' + name, '0640', 'root', SERVICE_USER)
    for name, payload in render_units().items():
        write('systemd/' + name, payload, '/etc/systemd/system/' + name, '0644', 'root', 'root')
    for role, payload in profiles.items():
        write('profiles/' + role + '.config', payload, WORKSPACE + '/.local/ssh/' + role + '/config',
              '0600', SERVICE_USER, SERVICE_USER)
    manifest = {
        'workspace': WORKSPACE, 'serviceUser': SERVICE_USER, 'installed': False,
        'recordingOnStart': False, 'includesCredentials': False, 'files': entries,
        'nativePlatform': 'linux_amd64', 'mediaVersion': poc.MEDIAMTX_VERSION,
        'serverIp': str(ipaddress.ip_address(server_ip)),
        'archiveSha256': poc.MEDIAMTX_RELEASES['linux_amd64']['sha256'],
        'requires': [
            'Linux amd64 NUC with existing Perl/Python/curl/iproute2/OpenSSH',
            'Dedicated unprivileged service user and root-owned source',
            'Private config, verified camera identity and record=false before startup',
            'Separate service keys and verified VPS host trust',
            'VPS loopback ports 18554/19996/19022 free before cutover',
            'Review and privileged installation on NUC; preparation does not install',
        ],
    }
    with (output / 'manifest.json').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write((json.dumps(manifest, indent=2) + '\n').encode())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New ignored .local/ directory')
    parser.add_argument('--server-ip', required=True, help='Approved public VPS IPv4 address')
    args = parser.parse_args()
    try:
        output = prepare(args.output, server_ip=args.server_ip)
    except (poc.PocError, OSError, ValueError, KeyError):
        parser.exit(1, 'Unable to prepare NUC bundle; check source and private output path.\n')
    print('Prepared only, not installed: ' + str(output))


if __name__ == '__main__':
    main()
