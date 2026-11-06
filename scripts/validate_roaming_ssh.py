#!/usr/bin/env python3
"""Fail closed on a dedicated SSH ingress that grants more than Air forwarding."""
import json
import argparse
from pathlib import Path
import subprocess
import sys


def validate_policy(text, user='devone-air', management=False):
    policies = {'devone-air': ('remote', 'none', {'127.0.0.1:18554', '127.0.0.1:19996'})}
    if management:
        policies.update({'camera-maint-relay': ('remote', 'none', {'127.0.0.1:19022'}),
                         'camera-maint-jump': ('local', '127.0.0.1:19022', {'none'})})
    if user not in policies:
        raise ValueError('Unknown SSH principal')
    forwarding, destination, listeners = policies[user]
    required = {
        'port': '2222', 'listenaddress': '0.0.0.0:2222', 'allowusers': ' '.join(policies),
        'permitrootlogin': 'no', 'authenticationmethods': 'publickey',
        'pubkeyauthentication': 'yes', 'passwordauthentication': 'no',
        'kbdinteractiveauthentication': 'no', 'permitemptypasswords': 'no',
        'allowtcpforwarding': forwarding, 'allowstreamlocalforwarding': 'no',
        'permitopen': destination, 'gatewayports': 'no', 'maxsessions': '0',
        'permittty': 'no', 'permittunnel': 'no', 'x11forwarding': 'no',
        'allowagentforwarding': 'no', 'permituserrc': 'no',
        'permituserenvironment': 'no', 'strictmodes': 'yes',
        'authorizedkeysfile': '.ssh/authorized_keys',
    }
    values = {}
    allowed_users = []
    for line in text.splitlines():
        key, separator, value = line.partition(' ')
        if key not in required and key != 'permitlisten':
            continue
        if not separator:
            raise ValueError('Ambiguous SSH policy')
        if key == 'allowusers':
            # sshd -T emits one line per AllowUsers entry on OpenSSH 9.6.
            # Do not turn this into a set: duplicate/extra names must fail too.
            allowed_users.extend(value.split())
            continue
        if key in values:
            raise ValueError('Ambiguous SSH policy')
        values[key] = value.strip()
    values['allowusers'] = ' '.join(allowed_users)
    if any(values.get(key) != value for key, value in required.items()):
        raise ValueError('SSH policy grants unexpected access')
    if set(values.get('permitlisten', '').split()) != listeners:
        raise ValueError('Unexpected forwarding destination')
    return {'port': 2222, 'user': user, 'keyOnly': True, 'shell': False,
            'rootLogin': False, 'reverseLoopbackPorts': sorted(int(x.rsplit(':', 1)[1]) for x in listeners if x != 'none'),
            'directLoopbackPorts': [] if destination == 'none' else [19022]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--management', action='store_true')
    args = parser.parse_args()
    path = args.config
    syntax = subprocess.run(['/usr/sbin/sshd', '-t', '-f', str(path)], capture_output=True, timeout=10)
    if syntax.returncode:
        raise ValueError('SSH configuration rejected')
    # Different origin addresses must yield the same restricted tunnel policy.
    users = ['devone-air', 'camera-maint-relay', 'camera-maint-jump'] if args.management else ['devone-air']
    results = {}
    for user in users:
        for address in ('198.51.100.12', '203.0.113.22'):
            parsed = subprocess.run(['/usr/sbin/sshd', '-T', '-f', str(path), '-C', 'user='+user+',host=camera,addr=' + address], capture_output=True, text=True, timeout=10)
            if parsed.returncode:
                raise ValueError('SSH effective policy rejected')
            results[user] = validate_policy(parsed.stdout, user, args.management)
    print(json.dumps(results if args.management else results['devone-air']))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit('Roaming SSH candidate validation failed; details omitted.')
