#!/usr/bin/env python3
"""Mini-side setup and clients for the separately authenticated Air management path."""
import argparse
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path.home() / 'Library/Application Support/CameraRemote'
# ProxyJump's generated child command on the supplied macOS OpenSSH does not
# quote a spaced -F path. Keep the profile under .ssh; keys may stay in Library.
PROFILE = Path.home() / '.ssh/camera-management/config'


def private_directory(path):
    path = Path(path)
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('Symlink in management path')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Management directory must be owned by you and mode 0700')
    return path


def private_read(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Symlink in private file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 1024*1024:
            raise ValueError('Unsafe private file')
        with os.fdopen(fd, 'rb', closefd=False) as source:
            return source.read(1024*1024+1)
    finally:
        os.close(fd)


def private_write(path, body):
    path = Path(path)
    private_directory(path.parent)
    if path.exists() or path.is_symlink():
        private_read(path)
    tmp = path.with_name(path.name+'.new-'+str(os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def render_config():
    # ~ is expanded by OpenSSH, keeping this config portable after a user-account
    # or checkout-path change. HostKeyAlias reuses the existing trusted identities.
    return '''Host camera-maint-jump
    HostName 168.144.137.69
    Port 2222
    User camera-maint-jump
    HostKeyAlias 168.144.137.69
    IdentityFile "~/Library/Application Support/CameraRemote/ssh/mini-jump"
    UserKnownHostsFile "~/Library/Application Support/CameraRemote/ssh/server.known_hosts"

Host camera-air
    HostName 127.0.0.1
    Port 19022
    User macbook
    ProxyJump camera-maint-jump
    HostKeyAlias 192.168.1.12
    IdentityFile "~/Library/Application Support/CameraRemote/ssh/air-admin"
    UserKnownHostsFile "~/Library/Application Support/CameraRemote/ssh/air.known_hosts"

Host *
    IdentitiesOnly yes
    IdentityAgent none
    UseKeychain yes
    BatchMode yes
    StrictHostKeyChecking yes
    GlobalKnownHostsFile /dev/null
    ForwardAgent no
    ForwardX11 no
    ExitOnForwardFailure yes
    ServerAliveInterval 15
    ServerAliveCountMax 3
    ConnectTimeout 8
'''


def setup():
    if not sys.stdin.isatty():
        raise ValueError('Run setup directly in your Terminal')
    directory = private_directory(RUNTIME)
    keys = private_directory(directory/'ssh')
    for name in ('mini-jump', 'air-admin'):
        key = keys/name
        if not key.exists():
            print('Tạo khóa '+name+'. Hãy tự đặt passphrase và lưu trong trình quản lý mật khẩu.')
            subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-a', '100', '-C', 'camera-'+name, '-f', str(key)], check=True)
        private_read(key)
        # An empty passphrase must NOT decrypt a Mini management key.
        probe = subprocess.run(['/usr/bin/ssh-keygen', '-y', '-P', '', '-f', str(key)], capture_output=True, timeout=5)
        if probe.returncode == 0:
            raise ValueError('Khóa phải có passphrase. Chạy ssh-keygen -p -f "'+str(key)+'" rồi chạy setup lại.')
        print('Nhập lại passphrase để lưu khóa '+name+' trong Keychain của Mini.')
        subprocess.run(['/usr/bin/ssh-add', '--apple-use-keychain', '-t', '4h', str(key)], check=True)
        public = key.with_suffix('.pub')
        public.chmod(0o600)
    for name, source in [('server.known_hosts', ROOT/'.local/ssh/server-operator/known_hosts'),
                         ('air.known_hosts', ROOT/'.local/ssh/air-poc/known_hosts')]:
        private_write(keys/name, private_read(source))
    private_directory(PROFILE.parent)
    private_write(PROFILE, render_config().encode())
    subprocess.run(['/usr/bin/ssh', '-G', '-F', str(PROFILE), 'camera-air'], check=True, stdout=subprocess.DEVNULL)
    print('Đã chuẩn bị hai khóa Mini và cấu hình. Khóa chưa tự được thêm vào VPS/Air.')


def ssh_args():
    private_read(PROFILE)
    return ['/usr/bin/ssh', '-F', str(PROFILE)]


def screen():
    # Do not open a GUI against an existing/unowned listener.
    with socket.socket() as check:
        check.bind(('127.0.0.1', 15900))
    child = subprocess.Popen(ssh_args()+['-N', '-L', '127.0.0.1:15900:127.0.0.1:5900', 'camera-air'], start_new_session=True)
    def interrupted(*_):
        raise KeyboardInterrupt
    old = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)}
    try:
        ready = False
        for _ in range(100):
            if child.poll() is not None:
                raise ValueError('Không mở được SSH; kiểm khóa/relay trước khi mở màn hình')
            result = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(child.pid), '-iTCP:15900', '-sTCP:LISTEN', '-Fn'], capture_output=True, timeout=2)
            if b'n127.0.0.1:15900\n' in result.stdout:
                ready = True
                break
            time.sleep(.1)
        if not ready:
            raise ValueError('Không xác minh được listener của SSH')
        subprocess.run(['/usr/bin/open', '-b', 'com.apple.ScreenSharing', 'vnc://127.0.0.1:15900'], check=True)
        input('Nhập tài khoản Air trong Screen Sharing. Giữ Terminal mở; Enter tại đây để kết thúc.\n')
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'ssh', 'sftp', 'screen'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'setup':
        setup()
    elif args.action == 'ssh':
        os.execv('/usr/bin/ssh', ssh_args()+['camera-air'])
    elif args.action == 'sftp':
        os.execv('/usr/bin/sftp', ['/usr/bin/sftp', '-F', str(PROFILE), 'camera-air'])
    else:
        screen()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit(130)
    except (ValueError, OSError, subprocess.SubprocessError):
        sys.exit('Camera management failed. Kiểm khóa/cấu hình trong Terminal; không gửi bí mật vào chat.')
