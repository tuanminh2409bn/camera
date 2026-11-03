#!/usr/bin/env python3
"""Owner-operated encrypted export/import for Mini connection and backup keys."""
import argparse
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import sys

try:
    from .camera_management import ROOT, private_read, private_directory
except ImportError:
    from camera_management import ROOT, private_read, private_directory

MAX_MEMBER = 1024*1024
MAX_ARCHIVE = 20*1024*1024


def destinations(home=None, project=None):
    home = Path(home) if home else Path.home()
    project = Path(project) if project else ROOT
    remote = home/'Library/Application Support/CameraRemote'
    result = {'remote/ssh_config': home/'.ssh/camera-management/config'}
    for name in ('mini-jump', 'mini-jump.pub', 'air-admin', 'air-admin.pub', 'server.known_hosts', 'air.known_hosts'):
        result['remote/ssh/'+name] = remote/'ssh'/name
    for name in ('id_ed25519_recovery_20261103', 'known_hosts'):
        result['operator/'+name] = project/'.local/ssh/server-operator'/name
    for name in ('id_ed25519', 'known_hosts'):
        result['air-lan/'+name] = project/'.local/ssh/air-poc'/name
    result['backup/metadata-secret-key.asc'] = project/'.local/production-backups/metadata-secret-key.asc'
    for name in ('id_ed25519_mirror', 'known_hosts'):
        result['mirror/'+name] = home/'Library/Application Support/CameraBackup/ssh'/name
    return result


def pack(items):
    allowed = destinations()
    if not set(items) <= set(allowed) or not {'remote/ssh_config', 'remote/ssh/mini-jump', 'remote/ssh/air-admin'} <= set(items):
        raise ValueError('Recovery members invalid')
    manifest = {name: hashlib.sha256(body).hexdigest() for name, body in items.items()}
    contents = dict(items)
    contents['manifest.json'] = json.dumps({'version': 1, 'sha256': manifest}).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name, body in contents.items():
            if len(body) > MAX_MEMBER:
                raise ValueError('Recovery member too large')
            info = tarfile.TarInfo(name);info.mode=0o600;info.size=len(body)
            archive.addfile(info, io.BytesIO(body))
    return output.getvalue()


def unpack(body):
    if len(body)>MAX_ARCHIVE:
        raise ValueError('Recovery archive too large')
    allowed = set(destinations()) | {'manifest.json'}
    result = {}
    # Never extract tar paths. Reject size/name/type before reading a member.
    with tarfile.open(fileobj=io.BytesIO(body), mode='r|gz') as archive:
        for member in archive:
            if member.name not in allowed or member.name in result or not member.isreg() or member.size>MAX_MEMBER:
                raise ValueError('Unsafe recovery member')
            result[member.name] = archive.extractfile(member).read(MAX_MEMBER+1)
    manifest = json.loads(result.pop('manifest.json'))
    if manifest.get('version')!=1 or manifest.get('sha256')!={n:hashlib.sha256(b).hexdigest() for n,b in result.items()}:
        raise ValueError('Recovery checksum mismatch')
    if not {'remote/ssh_config', 'remote/ssh/mini-jump', 'remote/ssh/air-admin'} <= set(result):
        raise ValueError('Required management keys missing')
    return result


def crypt(body, password, decrypt=False):
    if not 16<=len(password)<=1024 or any(x in password for x in '\r\n\0'):
        raise ValueError('Recovery passphrase needs 16-1024 characters')
    gpg = shutil.which('gpg')
    if not gpg:
        raise ValueError('GnuPG is required; install the approved official package first')
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, password.encode()+b'\n');os.close(write_fd);write_fd=None
        with tempfile.TemporaryDirectory(prefix='camera-gpg-') as temp:
            args = [gpg, '--no-options', '--homedir', temp, '--batch', '--pinentry-mode', 'loopback',
                    '--passphrase-fd', str(read_fd), '--no-symkey-cache']
            args += ['--max-output', str(MAX_ARCHIVE), '--decrypt'] if decrypt else ['--cipher-algo', 'AES256', '--compress-algo', 'none', '--symmetric']
            p = subprocess.run(args, input=body, capture_output=True, pass_fds=(read_fd,), timeout=45)
            if p.returncode or len(p.stdout)>MAX_ARCHIVE:
                raise ValueError('Recovery encryption/decryption failed')
            return p.stdout
    finally:
        os.close(read_fd)
        if write_fd is not None:os.close(write_fd)


def restore(items, targets):
    # Preflight every destination before writing any key. Never overwrite a
    # different existing credential or follow a link in a destination path.
    for name, body in items.items():
        path = targets[name]
        for parent in (path, *path.parents):
            if parent.is_symlink():raise ValueError('Symlink in restore destination')
        if path.exists() and private_read(path)!=body:
            raise ValueError('Existing credential differs; restore stopped without overwriting it')
    for name, body in items.items():
        path = targets[name]
        if path.exists():continue
        private_directory(path.parent)
        # O_EXCL also prevents a credential created after preflight from being
        # replaced. No unlink/replace of an existing credential is permitted.
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as output:
            output.write(body);output.flush();os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'verify', 'restore'])
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    if not sys.stdin.isatty():raise ValueError('Run recovery directly in your Terminal')
    os.umask(0o077)
    password = getpass.getpass('Passphrase riêng cho gói khôi phục (ít nhất16ký tự): ')
    if args.action=='export':
        if password!=getpass.getpass('Nhập lại passphrase: '):raise ValueError('Passphrases differ')
        if args.file.exists() or args.file.is_symlink():raise ValueError('Output already exists')
        items = {n:private_read(p) for n,p in destinations().items() if p.exists()}
        encrypted = crypt(pack(items), password)
        if unpack(crypt(encrypted,password,True))!=items:raise ValueError('Recovery roundtrip failed')
        private_directory(args.file.resolve().parent)
        fd=os.open(args.file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as output:output.write(encrypted);output.flush();os.fsync(output.fileno())
        print('Đã xuất và kiểm giải mã/checksum gói khôi phục. Hãy giữ một bản ngoài Mini, mật khẩu lưu riêng.')
    else:
        items=unpack(crypt(private_read(args.file),password,True))
        if args.action=='restore':restore(items,destinations())
        print('Gói khôi phục hợp lệ; '+str(len(items))+' tệp. Không tự cài agent hay đổi quyền máy chủ.')


if __name__=='__main__':
    try:main()
    except (KeyboardInterrupt,EOFError):sys.exit(130)
    except (ValueError,OSError,KeyError,tarfile.TarError,subprocess.SubprocessError):
        sys.exit('Recovery failed. Kiểm passphrase/GnuPG/quyền tệp trong Terminal; không gửi khóa hoặc mật khẩu vào chat.')
