#!/usr/bin/env python3
"""Render private candidate configs; never start services or overwrite runtime."""
import argparse
import ipaddress
import json
import re
from pathlib import Path
try:
    from scripts import poc
except ModuleNotFoundError:
    import poc


def account(raw):
    if not isinstance(raw, dict):
        raise poc.PocError('Invalid account input.')
    user, password = raw.get('username', raw.get('user')), raw.get('password', raw.get('pass'))
    if not isinstance(user, str) or not re.fullmatch(r'[A-Za-z0-9._-]{3,64}', user) or user == 'any':
        raise poc.PocError('Invalid account username.')
    if not isinstance(password, str) or len(password) < 16 or re.search(r'[\x00-\x1f\x7f]', password):
        raise poc.PocError('Invalid account password.')
    return user, password


def air_config(source, playback):
    user, password = account(playback)
    text = poc.render_mediamtx_config(source, target='native')
    text = text.replace('playback: no', 'playback: yes\nplaybackAddress: 127.0.0.1:9996')
    # Only the live path records. Global defaults remain record:false.
    text = text.replace('    record: no\n    maxReaders: 0', '\n'.join([
        '    record: yes', '    recordPath: ./.local/recordings/%path/%Y-%m-%d_%H-%M-%S-%f_%z',
        '    recordFormat: fmp4', '    recordPartDuration: 1s', '    recordSegmentDuration: 1m',
        '    recordMaxPartSize: 10M', '    recordDeleteAfter: 1d', '    maxReaders: 0']))
    playback_user = '\n'.join([
        '  - user: ' + json.dumps(user), '    pass: ' + json.dumps(password),
        "    ips: ['127.0.0.1', '::1']", '    permissions:', '      - action: playback', '        path: live', ''])
    return text.replace('\npathDefaults:', '\n' + playback_user + '\npathDefaults:')


def server_config(backend, public_ip, *, audio=False):
    user, password = account(backend)
    address = ipaddress.ip_address(public_ip)
    if not address.is_global or address.version != 4:
        raise poc.PocError('A public IPv4 address is required for deployment.')
    # JSON is valid YAML, parsed natively by MediaMTX. Never send this file to Air.
    config = {
        'logLevel': 'warn', 'api': True, 'apiAddress': '127.0.0.1:9997',
        'metrics': False, 'pprof': False, 'rtsp': False, 'rtmp': False,
        'hls': False, 'srt': False, 'moq': False, 'playback': False,
        'webrtc': True, 'webrtcAddress': '127.0.0.1:8889',
        'webrtcLocalUDPAddress': ':8189', 'webrtcLocalTCPAddress': ':8189',
        'webrtcIPsFromInterfaces': False, 'webrtcAdditionalHosts': [public_ip], 'webrtcICEServers2': [],
        'authMethod': 'internal', 'authInternalUsers': [{
            'user': user, 'pass': password, 'ips': ['127.0.0.1'],
            'permissions': [{'action': 'read', 'path': 'live'}, {'action': 'api'}]}],
        'pathDefaults': {'record': False, 'maxReaders': 200},
        'paths': {'live': {'source': 'rtsp://127.0.0.1:18554/live', 'rtspTransport': 'tcp',
                           'sourceOnDemand': False, 'alwaysAvailable': False, 'record': False}},
    }
    if audio:
        # FFmpeg copies H264 and converts only AAC audio to Opus. Its publisher
        # is local-only; anonymous users still cannot read live or call the API.
        config.update(rtsp=True, rtspAddress='127.0.0.1:18555', rtspTransports=['tcp'])
        config['paths']['live']['source'] = 'publisher'
        config['authInternalUsers'].append({
            'user': 'any', 'pass': '', 'ips': ['127.0.0.1'],
            'permissions': [{'action': 'publish', 'path': 'live'}]})
    return json.dumps(config, indent=2) + '\n'


def read_private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise poc.PocError('Input must be a private regular file with mode 0600.')
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    air = sub.add_parser('air')
    air.add_argument('--source-file', type=Path, required=True)
    air.add_argument('--playback-account', type=Path, required=True)
    server = sub.add_parser('server')
    server.add_argument('--backend-account', type=Path, required=True)
    server.add_argument('--public-ip', required=True)
    server.add_argument('--with-audio', action='store_true', help='Prepare loopback-only audio-adapter publishing')
    for child in (air, server):
        child.add_argument('--output', type=Path, required=True, help='New candidate file under .local/')
    args = parser.parse_args()
    try:
        output = poc.validate_private_output_path(args.output, workspace_root=poc.REPO_ROOT)
        if output.exists():
            raise poc.PocError('Refusing to overwrite an existing file; choose a new candidate name.')
        if args.kind == 'air':
            result = air_config(poc.load_source_file(args.source_file), read_private(args.playback_account))
        else:
            result = server_config(read_private(args.backend_account), args.public_ip, audio=args.with_audio)
        poc.atomic_write_private(output, result, workspace_root=poc.REPO_ROOT)
        print('Private candidate written. No service started or runtime changed.')
    except (poc.PocError, ValueError, OSError):
        parser.exit(1, 'Configuration rejected. Check input, permissions and candidate path; values omitted.\n')


if __name__ == '__main__':
    main()
