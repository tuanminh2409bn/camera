#!/usr/bin/env python3
"""Fail closed on a dedicated SSH ingress that grants more than Air forwarding."""
import json
from pathlib import Path
import subprocess
import sys


def validate_policy(text):
    required = {
        'port': '2222', 'listenaddress': '0.0.0.0:2222', 'allowusers': 'devone-air',
        'permitrootlogin': 'no', 'authenticationmethods': 'publickey',
        'pubkeyauthentication': 'yes', 'passwordauthentication': 'no',
        'kbdinteractiveauthentication': 'no', 'permitemptypasswords': 'no',
        'allowtcpforwarding': 'remote', 'allowstreamlocalforwarding': 'no',
        'permitopen': 'none', 'gatewayports': 'no', 'maxsessions': '0',
        'permittty': 'no', 'permittunnel': 'no', 'x11forwarding': 'no',
        'allowagentforwarding': 'no', 'permituserrc': 'no',
        'permituserenvironment': 'no', 'strictmodes': 'yes',
        'authorizedkeysfile': '.ssh/authorized_keys',
    }
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(' ')
        if key not in required and key != 'permitlisten':
            continue
        if not separator or key in values:
            raise ValueError('Ambiguous SSH policy')
        values[key] = value.strip()
    if any(values.get(key) != value for key, value in required.items()):
        raise ValueError('SSH policy grants unexpected access')
    if set(values.get('permitlisten', '').split()) != {'127.0.0.1:18554', '127.0.0.1:19996'}:
        raise ValueError('Unexpected forwarding destination')
    return {'port': 2222, 'user': 'devone-air', 'keyOnly': True, 'shell': False,
            'rootLogin': False, 'reverseLoopbackPorts': [18554, 19996]}


def main():
    if len(sys.argv) != 2:
        raise ValueError('Provide the candidate SSH configuration path')
    path = Path(sys.argv[1])
    syntax = subprocess.run(['/usr/sbin/sshd', '-t', '-f', str(path)], capture_output=True, timeout=10)
    if syntax.returncode:
        raise ValueError('SSH configuration rejected')
    # Different origin addresses must yield the same restricted tunnel policy.
    for address in ('198.51.100.12', '203.0.113.22'):
        parsed = subprocess.run(['/usr/sbin/sshd', '-T', '-f', str(path), '-C', 'user=devone-air,host=camera,addr=' + address], capture_output=True, text=True, timeout=10)
        if parsed.returncode:
            raise ValueError('SSH effective policy rejected')
        result = validate_policy(parsed.stdout)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit('Roaming SSH candidate validation failed; details omitted.')
