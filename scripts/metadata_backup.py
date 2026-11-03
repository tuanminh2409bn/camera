#!/usr/bin/env python3
"""Encrypted metadata backups. No video, plaintext dump file, or private key on VPS."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone

NAME = re.compile(r'metadata-(\d{8}T\d{6}Z)-[0-9a-f]{8}\.zip\.gpg\Z')
CONFIG_NAMES = ('server.json', 'mediamtx.json', 'air-gateway.json')
DIRECTORY = Path('/var/backups/devone')
KEYRING = Path('/var/lib/devone-backup/gnupg')
RECIPIENT_FILE = Path('/etc/devone/backup-recipient.json')


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
        raise ValueError('Unsafe backup directory')


def private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise ValueError('Unsafe backup file')
    return info


def atomic_json(path, value):
    pending = path.with_name('.pending-' + secrets.token_hex(12))
    try:
        with pending.open('x', encoding='utf-8') as out:
            os.chmod(pending, 0o600)
            json.dump(value, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def digest_stream(stream, output=None):
    digest, size = hashlib.sha256(), 0
    while True:
        block = stream.read(65536)
        if not block:
            return {'sha256': digest.hexdigest(), 'bytes': size}
        size += len(block)
        digest.update(block)
        if output is not None:
            output.write(block)


def archive_metadata(output, configs, dump_command):
    """Stream a custom-format pg_dump directly through ZIP into GPG stdin."""
    files = {}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name in CONFIG_NAMES:
            body = configs[name]
            json.loads(body)
            archive.writestr(name, body)
            files[name] = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        child = subprocess.Popen(dump_command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with archive.open('database.dump', 'w', force_zip64=True) as member:
                files['database.dump'] = digest_stream(child.stdout, member)
            if child.wait(timeout=30) != 0 or not files['database.dump']['bytes']:
                raise RuntimeError('Database dump failed')
        finally:
            child.stdout.close()
            if child.poll() is None:
                child.kill()
                child.wait()
        archive.writestr('manifest.json', json.dumps({'version': 1, 'createdAt': datetime.now(timezone.utc).isoformat(), 'files': files}))


def validate_archive(path):
    """Validate all members before allowing any restore; never extract paths."""
    expected = {*CONFIG_NAMES, 'database.dump', 'manifest.json'}
    with zipfile.ZipFile(path) as archive:
        items = archive.infolist()
        if len(items) != len(expected) or {i.filename for i in items} != expected:
            raise ValueError('Unexpected backup members')
        for item in items:
            kind = stat.S_IFMT(item.external_attr >> 16)
            limit = 4 * 1024**3 if item.filename == 'database.dump' else 4 * 1024**2
            if kind not in (0, stat.S_IFREG) or item.file_size > limit or item.flag_bits & 1:
                raise ValueError('Unsafe backup member')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('version') != 1 or set(manifest.get('files', {})) != expected - {'manifest.json'}:
            raise ValueError('Unsupported backup manifest')
        for name, expected_digest in manifest['files'].items():
            with archive.open(name) as source:
                if digest_stream(source) != expected_digest:
                    raise ValueError('Backup checksum mismatch')
        for name in CONFIG_NAMES:
            if not isinstance(json.loads(archive.read(name)), dict):
                raise ValueError('Invalid configuration')
        return manifest


def list_backups(directory):
    result = []
    for path in sorted(directory.iterdir()):
        if not NAME.fullmatch(path.name):
            continue
        try:
            info = private_file(path)
            sidecar = path.with_name(path.name + '.json')
            private_file(sidecar)
            metadata = json.loads(sidecar.read_text())
        except (OSError, ValueError):
            continue
        if metadata.get('name') == path.name and metadata.get('bytes') == info.st_size and re.fullmatch(r'[a-f0-9]{64}', str(metadata.get('sha256', ''))):
            result.append(metadata)
    return result


def prune(directory, days, now=None):
    cutoff = (time.time() if now is None else now) - days * 86400
    for item in list_backups(directory):
        match = NAME.fullmatch(item['name'])
        created = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()
        if created < cutoff:
            (directory / item['name']).unlink()
            (directory / (item['name'] + '.json')).unlink()


def create_backup():
    private_directory(DIRECTORY)
    private_directory(KEYRING)
    private_file(RECIPIENT_FILE)
    recipient = json.loads(RECIPIENT_FILE.read_text())['fingerprint']
    if not re.fullmatch(r'[A-F0-9]{40}', recipient):
        raise ValueError('Invalid pinned recipient')
    if shutil.disk_usage(DIRECTORY).free < 5 * 1024**3:
        raise RuntimeError('Insufficient backup reserve')
    configs = {}
    for name in CONFIG_NAMES:
        path = Path('/etc/devone') / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4 * 1024**2:
            raise ValueError('Unsafe source configuration')
        configs[name] = path.read_bytes()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = 'metadata-' + stamp + '-' + secrets.token_hex(4) + '.zip.gpg'
    pending = DIRECTORY / ('.pending-' + secrets.token_hex(12) + '.gpg')
    try:
        with pending.open('xb') as output:
            os.chmod(pending, 0o600)
            child = subprocess.Popen(['/usr/bin/gpg', '--no-options', '--homedir', str(KEYRING), '--batch', '--no-auto-key-retrieve', '--trust-model', 'always', '--recipient', recipient, '--cipher-algo', 'AES256', '--compress-algo', 'none', '--encrypt'], stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL)
            try:
                archive_metadata(child.stdin, configs, ['runuser', '-u', 'postgres', '--', 'pg_dump', '--format=custom', '--no-owner', '--no-acl', '--lock-wait-timeout=5000', 'devone'])
                child.stdin.close()
                if child.wait(timeout=30):
                    raise RuntimeError('Encryption failed')
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
            output.flush()
            os.fsync(output.fileno())
        if any((Path('/etc/devone') / n).read_bytes() != body for n, body in configs.items()):
            raise RuntimeError('Configuration changed during backup')
        with pending.open('rb') as source:
            result = {'name': name, **digest_stream(source)}
        os.replace(pending, DIRECTORY / name)
        atomic_json(DIRECTORY / (name + '.json'), result)
        atomic_json(DIRECTORY / 'status.json', {'lastSuccess': datetime.now(timezone.utc).isoformat(), **result})
        prune(DIRECTORY, 14)
        return result
    finally:
        pending.unlink(missing_ok=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'list', 'stream'])
    parser.add_argument('name', nargs='?')
    args = parser.parse_args()
    private_directory(DIRECTORY)
    with (DIRECTORY / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if args.action == 'create' else fcntl.LOCK_SH)
        if args.action == 'create':
            print(json.dumps(create_backup()))
        elif args.action == 'list':
            print(json.dumps(list_backups(DIRECTORY)))
        else:
            if not args.name or not NAME.fullmatch(args.name):
                raise ValueError('Invalid backup name')
            path = DIRECTORY / args.name
            private_file(path)
            with path.open('rb') as source:
                digest_stream(source, sys.stdout.buffer)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, zipfile.BadZipFile):
        sys.exit('Metadata backup failed; previous backups retained. Review private status and service state.')
