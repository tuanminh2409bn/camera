#!/usr/bin/env python3
"""Install a home-volume mirror with a dedicated, ciphertext-only SSH key.

Run only after explicit operator authorization to create this SSH credential.
"""
import base64
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import time
try:
    from scripts import metadata_backup_client as client
    from scripts import metadata_backup as backup
except ModuleNotFoundError:
    import metadata_backup_client as client
    import metadata_backup as backup


def install():
    os.umask(0o077)
    runtime = client.MIRROR_RUNTIME
    backup.private_directory(runtime)
    keys = runtime / 'ssh'
    backup.private_directory(keys)
    key = keys / 'id_ed25519_mirror'
    if not key.exists():
        client.checked(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'camera-ciphertext-mirror', '-f', str(key)])
    backup.private_file(key)
    public = key.with_suffix('.pub').read_text().strip()
    if not public.startswith('ssh-ed25519 ') or len(public.split()) != 3:
        raise ValueError('Unexpected mirror public key')
    trusted = client.SSH_DIR / 'known_hosts'
    backup.private_file(trusted)
    (keys / 'known_hosts').write_bytes(trusted.read_bytes())
    (keys / 'known_hosts').chmod(0o600)
    helper = (client.ROOT / 'scripts/metadata_backup_download.py').read_bytes()
    payload = {'key': public, 'helper': base64.b64encode(helper).decode()}
    remote = 'payload=' + repr(payload) + '\n' + r'''
import pathlib,subprocess,base64,os
os.umask(0o077)
path=pathlib.Path('/opt/devone/ops/metadata_backup_download.py')
path.write_bytes(base64.b64decode(payload['helper']));path.chmod(0o644)
line='restrict,from="113.22.46.6",command="/usr/bin/python3 /opt/devone/ops/metadata_backup_download.py" '+payload['key']
auth=pathlib.Path('/root/.ssh/authorized_keys');before=auth.read_text()
if payload['key'] not in before:
 with auth.open('a') as f:f.write(('' if before.endswith('\n') else '\n')+line+'\n')
auth.chmod(0o600)
p=subprocess.run(['/usr/sbin/sshd','-t'],capture_output=True,timeout=10)
assert p.returncode==0
print('Ciphertext-only mirror key installed.')
'''
    print(client.checked(client.SSH + ['python3 -'], input=remote.encode()).decode().strip())
    source = runtime / 'scripts'
    source.mkdir(mode=0o700, exist_ok=True)
    for name in ('metadata_backup.py', 'metadata_backup_client.py'):
        target = source / name
        target.write_bytes((client.ROOT / 'scripts' / name).read_bytes())
        target.chmod(0o600)
    program = source / 'metadata_backup_client.py'
    # Verify both the allowed transfer and denied shell before loading launchd.
    spec = importlib.util.spec_from_file_location('installed_mirror', program)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    denied = subprocess.run(module.SSH + ['id'], capture_output=True, timeout=15)
    if denied.returncode == 0:
        raise RuntimeError('Mirror shell denial failed')
    listing = module.mirror()
    if not listing:
        raise RuntimeError('Mirror returned no backup')
    plist = Path.home() / 'Library/LaunchAgents' / (client.LABEL + '.plist')
    if plist.exists():
        value = plistlib.loads(plist.read_bytes())
        allowed = (str(client.ROOT / 'scripts/metadata_backup_client.py'), str(program))
        if value.get('Label') != client.LABEL or value.get('ProgramArguments', [None, None])[1] not in allowed:
            raise ValueError('Unrecognized existing agent')
        old = client.DESTINATION / 'mirror-agent-before-home-runtime.plist'
        if not old.exists():
            old.write_bytes(plist.read_bytes())
            old.chmod(0o600)
        target = 'gui/' + str(os.getuid()) + '/' + client.LABEL
        state = subprocess.run(['/bin/launchctl', 'print', target], capture_output=True)
        if not state.returncode:
            match = re.search(rb'^\s*pid = (\d+)$', state.stdout, re.M)
            previous_pid = int(match[1]) if match else None
            client.checked(['/bin/launchctl', 'bootout', target])
            for _ in range(100):
                alive = False
                if previous_pid:
                    try:
                        os.kill(previous_pid, 0)
                        alive = True
                    except ProcessLookupError:
                        pass
                if subprocess.run(['/bin/launchctl', 'print', target], capture_output=True).returncode and not alive:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('Previous backup job did not exit')
        plist.unlink()
    module.install_agent()
    backup.atomic_json(runtime / 'installation.json', {'installed': True, 'restrictedSsh': True, 'shellDenied': True, 'mirrorFiles': len(listing), 'retentionDays': 30})
    print(json.dumps({'installed': True, 'shellDenied': True, 'mirrorDirectory': str(module.DESTINATION)}))


if __name__ == '__main__':
    install()
