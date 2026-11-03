#!/usr/bin/env python3
"""Owner-controlled backup key setup, encrypted mirror and isolated restore check."""
import argparse
import base64
import fcntl
import getpass
import hmac
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import zipfile
try:
    from scripts import metadata_backup as backup
except ModuleNotFoundError:
    import metadata_backup as backup

ROOT = Path(__file__).resolve().parents[1]
MIRROR_RUNTIME = Path.home() / 'Library/Application Support/CameraBackup'
MIRROR_ONLY = ROOT == MIRROR_RUNTIME
DESTINATION = ROOT / 'archives' if MIRROR_ONLY else ROOT / '.local/production-backups'
KEYRING = ROOT / '.local/backup-keyring'
GPG = '/opt/homebrew/bin/gpg'
LABEL = 'com.camera.metadata-backup'
SSH_DIR = ROOT / 'ssh' if MIRROR_ONLY else ROOT / '.local/ssh/server-operator'
IDENTITY = SSH_DIR / ('id_ed25519_mirror' if MIRROR_ONLY else 'id_ed25519_recovery_20261103')
SSH = ['/usr/bin/ssh', '-T', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'UseKeychain=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'UserKnownHostsFile="' + str(SSH_DIR / 'known_hosts') + '"', '-o', 'ConnectTimeout=8', '-o', 'ForwardAgent=no', '-i', str(IDENTITY), 'root@168.144.137.69']


def checked(args, **kwargs):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError('Operation failed; secret values omitted')
    return result.stdout


def gpg(args, phrase=None, **kwargs):
    command = [GPG, '--no-options', '--homedir', str(KEYRING), '--batch', '--yes', '--no-auto-key-retrieve']
    if phrase is None:
        return checked(command + args, **kwargs)
    read, write = os.pipe()
    try:
        os.write(write, phrase + b'\n')
        os.close(write)
        write = -1
        return checked(command + ['--pinentry-mode', 'loopback', '--passphrase-fd', str(read)] + args, pass_fds=(read,), **kwargs)
    finally:
        os.close(read)
        if write >= 0:
            os.close(write)


def clear_agent():
    checked(['/opt/homebrew/bin/gpgconf', '--homedir', str(KEYRING), '--kill', 'gpg-agent'])


def fingerprint():
    records = gpg(['--with-colons', '--list-keys']).decode().splitlines()
    values = [s.split(':')[9] for s in records if s.startswith('fpr:')]
    if len(values) != 1 or not re.fullmatch(r'[A-F0-9]{40}', values[0]):
        raise ValueError('Expected one dedicated backup key')
    return values[0]


def deploy(public, recipient):
    resources = {
        '/opt/devone/ops/metadata_backup.py': (ROOT / 'scripts/metadata_backup.py').read_bytes(),
        '/opt/devone/ops/metadata_restore_check.py': (ROOT / 'scripts/metadata_restore_check.py').read_bytes(),
        '/etc/systemd/system/devone-backup.service': (ROOT / 'infra/server/devone-backup.service.example').read_bytes(),
        '/etc/systemd/system/devone-backup.timer': (ROOT / 'infra/server/devone-backup.timer.example').read_bytes(),
    }
    payload = {'resources': {k: base64.b64encode(v).decode() for k, v in resources.items()}, 'public': base64.b64encode(public).decode(), 'recipient': recipient}
    source = 'payload=' + repr(payload) + '\n' + r'''
import base64,json,pathlib,subprocess,os,re
os.umask(0o077)
def run(args,**kwargs):
 p=subprocess.run(args,capture_output=True,timeout=90,**kwargs)
 if p.returncode:raise RuntimeError('Backup deployment failed; values omitted')
 return p.stdout
home=pathlib.Path('/var/lib/devone-backup/gnupg');home.mkdir(parents=True,mode=0o700,exist_ok=True);home.chmod(0o700);home.parent.chmod(0o700)
destination=pathlib.Path('/var/backups/devone');destination.mkdir(mode=0o700,exist_ok=True);destination.chmod(0o700)
public=base64.b64decode(payload['public']);recipient=payload['recipient'];assert re.fullmatch(r'[A-F0-9]{40}',recipient)
gpg=['/usr/bin/gpg','--no-options','--homedir',str(home),'--batch']
records=run(gpg+['--with-colons','--import-options','show-only','--import'],input=public).decode().splitlines()
assert [s.split(':')[9] for s in records if s.startswith('fpr:')]==[recipient]
pin=pathlib.Path('/etc/devone/backup-recipient.json')
if pin.exists():assert json.loads(pin.read_text())['fingerprint']==recipient
run(gpg+['--import'],input=public)
assert b'sec:' not in run(gpg+['--with-colons','--list-secret-keys'])
pin.write_text(json.dumps({'fingerprint':recipient}));pin.chmod(0o600)
ops=pathlib.Path('/opt/devone/ops');ops.mkdir(mode=0o755,exist_ok=True)
for name,body in payload['resources'].items():
 path=pathlib.Path(name);tmp=path.with_name(path.name+'.candidate');tmp.write_bytes(base64.b64decode(body));tmp.chmod(0o644);os.replace(tmp,path)
run(['systemd-analyze','verify','/etc/systemd/system/devone-backup.service','/etc/systemd/system/devone-backup.timer'])
run(['systemctl','daemon-reload']);run(['systemctl','start','devone-backup.service'])
print(json.dumps({'firstBackupCreated':True,'serverHasPrivateKey':False}))
'''
    print(checked(SSH + ['python3 -'], input=source.encode()).decode().strip())


def mirror():
    backup.private_directory(DESTINATION)
    with (DESTINATION / '.mirror.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        listing = json.loads(checked(SSH + ['list' if MIRROR_ONLY else 'python3 /opt/devone/ops/metadata_backup.py list']))
        if not isinstance(listing, list) or len(listing) > 1000:
            raise ValueError('Invalid backup listing')
        for item in listing:
            name = item.get('name', '')
            size = item.get('bytes')
            if not backup.NAME.fullmatch(name) or not isinstance(size, int) or not 256 <= size <= 4 * 1024**3 or not re.fullmatch(r'[a-f0-9]{64}', item.get('sha256', '')):
                raise ValueError('Invalid backup descriptor')
            target = DESTINATION / name
            if target.exists() or target.is_symlink():
                backup.private_file(target)
                with target.open('rb') as source:
                    if backup.digest_stream(source) != {k: item[k] for k in ('sha256', 'bytes')}:
                        raise ValueError('Existing mirror checksum mismatch')
                continue
            if shutil.disk_usage(DESTINATION).free < size + 2 * 1024**3:
                raise RuntimeError('Insufficient mirror reserve')
            pending = DESTINATION / ('.mirror-' + secrets.token_hex(12))
            try:
                with pending.open('xb') as output:
                    os.chmod(pending, 0o600)
                    command = ('stream ' if MIRROR_ONLY else 'python3 /opt/devone/ops/metadata_backup.py stream ') + name
                    result = subprocess.run(SSH + [command], stdout=output, stderr=subprocess.DEVNULL, timeout=600)
                    output.flush()
                    os.fsync(output.fileno())
                with pending.open('rb') as source:
                    actual = backup.digest_stream(source)
                if result.returncode or actual != {k: item[k] for k in ('sha256', 'bytes')}:
                    raise RuntimeError('Mirror transfer failed')
                os.replace(pending, target)
                backup.atomic_json(DESTINATION / (name + '.json'), item)
            finally:
                pending.unlink(missing_ok=True)
        if listing:
            backup.prune(DESTINATION, 30)
            backup.atomic_json(DESTINATION / 'mirror-status.json', {'lastSuccess': backup.datetime.now(backup.timezone.utc).isoformat(), 'latest': listing[-1]['name']})
        return listing


def restore_check(path, phrase):
    backup.private_file(path)
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=DESTINATION) as folder:
        plain = Path(folder) / 'metadata.zip'
        gpg(['--output', str(plain), '--decrypt', str(path)], phrase)
        plain.chmod(0o600)
        manifest = backup.validate_archive(plain)
        with zipfile.ZipFile(plain) as archive:
            config = json.loads(archive.read('server.json'))
            header = json.dumps({'encryptionKey': config['encryptionKey'], 'dumpSha256': manifest['files']['database.dump']['sha256']}).encode() + b'\n'
            child = subprocess.Popen(SSH + ['python3 /opt/devone/ops/metadata_restore_check.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                child.stdin.write(header)
                with archive.open('database.dump') as source:
                    backup.digest_stream(source, child.stdin)
                child.stdin.close()
                result = child.stdout.read(65536)
                if child.wait(timeout=120):
                    raise RuntimeError('Isolated restore failed')
                report = json.loads(result)
                if not report.get('restored') or not report.get('mfaDecrypt'):
                    raise RuntimeError('Restore evidence incomplete')
                backup.atomic_json(DESTINATION / 'restore-status.json', {'backup': path.name, **report})
                print(json.dumps(report))
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()


def install_agent():
    if not MIRROR_ONLY:
        raise ValueError('Install the restricted home-volume mirror first')
    # launchd must be able to open its log before starting the process, even
    # while the external project volume is not mounted at login.
    runtime = Path.home() / 'Library/Logs/CameraMetadataBackup'
    backup.private_directory(runtime)
    log = runtime / 'mirror.log'
    if not log.exists():
        log.touch(mode=0o600)
    backup.private_file(log)
    path = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    data = {'Label': LABEL, 'ProgramArguments': ['/usr/bin/python3', str(Path(__file__).resolve()), 'mirror'], 'RunAtLoad': True, 'StartInterval': 3600, 'ThrottleInterval': 60, 'StandardOutPath': str(log), 'StandardErrorPath': str(log), 'Umask': 0o077}
    if path.exists():
        if plistlib.loads(path.read_bytes()) != data:
            raise ValueError('Existing backup agent differs; review required')
    else:
        path.write_bytes(plistlib.dumps(data))
        path.chmod(0o600)
    domain = 'gui/' + str(os.getuid())
    state = subprocess.run(['/bin/launchctl', 'print', domain + '/' + LABEL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if state.returncode:
        checked(['/bin/launchctl', 'bootstrap', domain, str(path)])


def setup():
    print('Tạo khóa sao lưu riêng trên Mini; VPS chỉ nhận public key. Không gửi mật khẩu vào chat.')
    phrase = getpass.getpass('Passphrase sao lưu (ít nhất 16 ký tự, lưu vào nơi an toàn): ').encode()
    if not 16 <= len(phrase) <= 1024 or b'\n' in phrase or b'\r' in phrase:
        raise ValueError('Passphrase chưa đủ dài hoặc chứa ký tự xuống dòng')
    if not hmac.compare_digest(phrase, getpass.getpass('Nhập lại passphrase: ').encode()):
        raise ValueError('Hai passphrase chưa khớp')
    backup.private_directory(DESTINATION)
    backup.private_directory(KEYRING)
    if not any(s.startswith('pub:') for s in gpg(['--with-colons', '--list-keys']).decode().splitlines()):
        gpg(['--quick-generate-key', 'Camera metadata backup (local only)', 'rsa3072', 'encrypt', '0'], phrase)
    recipient = fingerprint()
    canary = secrets.token_bytes(32)
    cipher = gpg(['--trust-model', 'always', '--recipient', recipient, '--encrypt'], input=canary)
    clear_agent()
    try:
        gpg(['--decrypt'], b'deliberately-wrong-fixture-passphrase', input=cipher)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('Key did not reject wrong passphrase')
    clear_agent()
    if gpg(['--decrypt'], phrase, input=cipher) != canary:
        raise RuntimeError('Key verification failed')
    secret = DESTINATION / 'metadata-secret-key.asc'
    if not secret.exists():
        secret.write_bytes(gpg(['--armor', '--export-secret-keys', recipient], phrase))
        secret.chmod(0o600)
    backup.private_file(secret)
    public = gpg(['--armor', '--export', recipient])
    deploy(public, recipient)
    items = mirror()
    if not items:
        raise RuntimeError('No saved backup to restore')
    restore_check(DESTINATION / items[-1]['name'], phrase)
    # Schedule only after the first real saved backup passes decryption/restore.
    checked(SSH + ['systemctl enable --now devone-backup.timer'])
    installed = MIRROR_RUNTIME / 'installation.json'
    mini_ready = installed.is_file() and json.loads(installed.read_text()).get('restrictedSsh') is True
    if mini_ready:
        checked(['/usr/bin/python3', str(MIRROR_RUNTIME / 'scripts/metadata_backup_client.py'), 'mirror'])
    clear_agent()
    backup.atomic_json(DESTINATION / 'setup-status.json', {'complete': mini_ready, 'vpsComplete': True, 'miniMirror': mini_ready, 'fingerprint': recipient, 'serverPrivateKey': False, 'dailyVietnamTime': '02:15', 'serverRetentionDays': 14, 'miniRetentionDays': 30})
    print('Đã hoàn tất backup VPS và phục hồi thử độc lập, kiểm tra giải mã MFA thành công.')
    if not mini_ready:
        print('Chưa cài bộ lấy backup trên Mini. Cần duyệt khóa SSH chỉ tải bản mã hóa rồi chạy scripts/install_backup_mirror.py.')
    print('Giữ passphrase và tập tin khóa riêng mã hóa ở hai nơi an toàn khác nhau:', secret)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'mirror'])
    args = parser.parse_args()
    if MIRROR_ONLY and args.action != 'mirror':
        raise ValueError('Installed mirror cannot manage backup keys')
    if args.action == 'setup':
        setup()
    else:
        mirror()
        print('Encrypted backup mirror verified.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile):
        sys.exit('Sao lưu chưa hoàn tất; giữ nguyên các bản cũ. Kiểm tra SSH/Keychain, dung lượng và trạng thái dịch vụ; không gửi bí mật vào chat.')
