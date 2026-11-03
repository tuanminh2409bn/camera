#!/usr/bin/env python3
"""Prepare a private, reviewable Air login bundle; never install or start it."""
import argparse
import hashlib
import json
import os
import plistlib
from pathlib import Path

try:
    from scripts import poc
except ModuleNotFoundError:
    import poc

TARGET = '/Users/macbook/Developer/camera'
RUNTIME = TARGET + '/.local/air-autostart-runtime'
SCRIPTS = ('air_recording_supervisor.pl', 'air_login_supervisor.pl', 'air_web_gateway.pl')


def render_agents(source_root):
    agents = {}
    for name in ('recording-login', 'web-gateway', 'server-tunnel'):
        raw = (source_root / 'infra' / 'macos' / (name + '.plist.example')).read_bytes()
        agent = plistlib.loads(raw.replace(b'__WORKSPACE__', TARGET.encode()))
        if name == 'web-gateway':
            agent['ProgramArguments'][1] = RUNTIME + '/air_web_gateway.pl'
        agent['EnvironmentVariables'] = {'LC_ALL': 'C', 'LANG': 'C'}
        agent['LimitLoadToSessionType'] = 'Aqua'
        agents[agent['Label'] + '.plist'] = plistlib.dumps(agent)
    return agents


def prepare(output, source_root=poc.REPO_ROOT):
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

    def write(relative, payload, destination):
        target = output / relative
        target.parent.mkdir(mode=0o700, exist_ok=True)
        with target.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        entries.append({'file': relative, 'destination': destination,
                        'sha256': hashlib.sha256(payload).hexdigest(), 'mode': '0600'})

    for name in SCRIPTS:
        write('runtime/' + name, (source_root / 'scripts' / name).read_bytes(), RUNTIME + '/' + name)
    for name, payload in render_agents(source_root).items():
        write('launchagents/' + name, payload, '/Users/macbook/Library/LaunchAgents/' + name)
    manifest = {'workspace': TARGET, 'installed': False, 'files': entries,
                'requires': ['Explicit approval before installing LaunchAgents and restarting Air services',
                             'Air powered on, lid open and user logged in',
                             'Existing private config, SSH trust and tools on Air'],
                'recordingOnStart': False, 'retention': '1d', 'cleanupIntervalMaximumSeconds': 1800}
    with (output / 'manifest.json').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write((json.dumps(manifest, indent=2) + '\n').encode())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New ignored .local/ directory')
    args = parser.parse_args()
    try:
        output = prepare(args.output)
    except (poc.PocError, OSError, ValueError):
        parser.exit(1, 'Unable to prepare Air bundle; check source and private output path.\n')
    print('Prepared only, not installed: ' + str(output))


if __name__ == '__main__':
    main()
