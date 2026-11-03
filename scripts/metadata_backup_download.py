#!/usr/bin/env python3
"""Forced SSH command: expose only encrypted backup inventory and bytes."""
import os
import subprocess
import sys
try:
    from scripts.metadata_backup import NAME
except ModuleNotFoundError:
    from metadata_backup import NAME


def arguments(command):
    if command == 'list':
        return ['list']
    if command.startswith('stream ') and NAME.fullmatch(command[7:]):
        return ['stream', command[7:]]
    raise ValueError('Backup command rejected')


if __name__ == '__main__':
    try:
        args = arguments(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
        sys.exit(subprocess.run(['/usr/bin/python3', '/opt/devone/ops/metadata_backup.py', *args], stdin=subprocess.DEVNULL, timeout=600).returncode)
    except (ValueError, OSError, subprocess.SubprocessError):
        sys.exit('Only encrypted backup list/stream commands are permitted.')
