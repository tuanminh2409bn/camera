#!/usr/bin/env python3
"""Read-only operational checks; publish a private, bounded Admin snapshot."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
try:
    from scripts.metadata_backup import atomic_json, NAME
except ModuleNotFoundError:
    from metadata_backup import atomic_json, NAME

CODES = ('API', 'WEB_TLS', 'MEDIA', 'AUDIO', 'MEDIA_PROGRESS', 'AIR', 'AIR_AUTH',
         'AIR_DISK', 'RECORDING', 'SERVER_DISK', 'BACKUP', 'BACKUP_TIMER')
STATE_DIRECTORY = Path('/var/lib/devone-monitor')
CONFIG = Path('/etc/devone/server.json')


def stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace('+00:00', 'Z')


def read_json(path, limit=1048576):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > limit:
        raise ValueError('Unsafe monitor input')
    return json.loads(path.read_bytes())


def request_json(origin, path, headers=None):
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Upstream must be fixed loopback')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(origin.rstrip('/') + path, headers=headers or {})
    with opener.open(request, timeout=3) as response:
        body = response.read(1048577)
        if len(body) > 1048576:
            raise ValueError('Monitor response too large')
        return json.loads(body)


def web_tls(origin, now):
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('Invalid HTTPS origin')
    with socket.create_connection(('127.0.0.1', 443), timeout=3) as connection:
        with ssl.create_default_context().wrap_socket(connection, server_hostname=parsed.hostname) as secure:
            expires = ssl.cert_time_to_seconds(secure.getpeercert()['notAfter'])
            secure.sendall(('GET / HTTP/1.1\r\nHost: ' + parsed.hostname + '\r\nConnection: close\r\n\r\n').encode('ascii'))
            response = secure.recv(4096)
            days = math.floor((expires - now) / 86400)
            return {'ok': bool(re.match(rb'HTTP/1\.[01] 200\b', response)) and days >= 14, 'value': days}


def backup_healthy(status, directory, now):
    name = status.get('name', '')
    if not isinstance(name, str) or not NAME.fullmatch(name):
        return False
    path = directory / name
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != status.get('bytes'):
        return False
    last = datetime.fromisoformat(status['lastSuccess'].replace('Z', '+00:00')).timestamp()
    if last > now + 60 or now - last > 30 * 3600:
        return False
    local = datetime.fromtimestamp(now, ZoneInfo('Asia/Ho_Chi_Minh'))
    # Allow 30 minutes for the daily 02:15 backup to finish.
    due = local.replace(hour=2, minute=45, second=0, microsecond=0)
    if local < due:
        due -= timedelta(days=1)
    scheduled = due - timedelta(minutes=30)
    return last >= scheduled.timestamp()


def public_network_counter():
    routes = Path('/proc/net/route').read_text().splitlines()[1:]
    names = {line.split()[0] for line in routes if len(line.split()) >= 4 and line.split()[1] == '00000000' and int(line.split()[3], 16) & 1}
    if len(names) != 1:
        raise ValueError('Ambiguous public network interface')
    interface = names.pop()
    for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
        name, raw = line.split(':')
        if name.strip() == interface:
            return int(raw.split()[8])
    raise ValueError('Missing network counter')


def traffic_state(previous, counter, boot_id, now):
    month = datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m')
    old = previous or {}
    same_month = old.get('month') == month
    total = old.get('bytes', 0) if same_month else 0
    # Never add an unknown pre-monitor interval or assume a reset is billable.
    if same_month and old.get('bootId') == boot_id and counter >= old.get('counter', counter):
        total += counter - old['counter']
    return {'month': month, 'since': old.get('since', stamp(now)) if same_month else stamp(now),
            'bytes': total, 'counter': counter, 'bootId': boot_id}


def collect(config, previous, now):
    checks = {code: {'ok': False, 'value': None} for code in CODES}
    metadata = {}
    basic = 'Basic ' + base64.b64encode((config['mediaUser'] + ':' + config['mediaPassword']).encode()).decode()
    probes = {
        'api': lambda: request_json('http://127.0.0.1:3001', '/api/health'),
        'air': lambda: request_json(config['airOrigin'], '/status', {'Authorization': 'Bearer ' + config['airToken']}),
        'media': lambda: request_json(config['mediaApiOrigin'], '/v3/paths/get/live', {'Authorization': basic}),
        'web': lambda: web_tls(config['origin'], now),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {name: executor.submit(probe) for name, probe in probes.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except (OSError, ValueError, KeyError, TypeError):
                results[name] = None
    checks['API']['ok'] = isinstance(results.get('api'), dict) and results['api'].get('status') == 'ok'
    if results.get('web'):
        checks['WEB_TLS'] = results['web']
    air = results.get('air')
    if isinstance(air, dict):
        checks['AIR']['ok'] = air.get('isOnline') is True
        checks['AIR_AUTH']['ok'] = air.get('authLatched') is False
        available = air.get('availableBytes')
        checks['AIR_DISK'] = {'ok': type(available) is int and available >= 20 * 1024**3 and air.get('isPaused') is False, 'value': available if type(available) is int else None}
    media = results.get('media')
    if isinstance(media, dict):
        checks['MEDIA']['ok'] = media.get('ready') is True and 'H264' in media.get('tracks', [])
        checks['AUDIO']['ok'] = media.get('ready') is True and 'Opus' in media.get('tracks', [])
        counter, epoch = media.get('bytesReceived'), media.get('readyTime')
        if type(counter) is int and isinstance(epoch, str):
            old = previous.get('media', {})
            checks['MEDIA_PROGRESS']['ok'] = checks['MEDIA']['ok'] and (old.get('epoch') != epoch or counter > old.get('counter', -1))
            metadata['media'] = {'epoch': epoch, 'counter': counter}
    try:
        result = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-d', 'devone', '-Atqc', 'SELECT desired FROM recording_intent WHERE id=1'], capture_output=True, timeout=4)
        value = result.stdout.strip()
        checks['RECORDING']['ok'] = result.returncode == 0 and value in (b't', b'f') and isinstance(air, dict) and air.get('observed') is (value == b't')
    except (OSError, subprocess.SubprocessError):
        pass
    checks['SERVER_DISK'] = {'ok': shutil.disk_usage('/').free >= 10 * 1024**3, 'value': shutil.disk_usage('/').free}
    try:
        backup = read_json(Path('/var/backups/devone/status.json'))
        checks['BACKUP']['ok'] = backup_healthy(backup, Path('/var/backups/devone'), now)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        timer = subprocess.run(['systemctl', 'show', 'devone-backup.timer', '-p', 'ActiveState', '-p', 'UnitFileState'], capture_output=True, timeout=4)
        checks['BACKUP_TIMER']['ok'] = timer.returncode == 0 and b'ActiveState=active' in timer.stdout.splitlines() and b'UnitFileState=enabled' in timer.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        metadata['traffic'] = traffic_state(previous.get('traffic'), public_network_counter(), Path('/proc/sys/kernel/random/boot_id').read_text().strip(), now)
    except (OSError, ValueError, KeyError):
        pass
    return checks, metadata


def advance(previous, checks, metadata, now):
    prior = previous.get('checks', {})
    state, output, events = {}, [], list(previous.get('events', []))[-49:]
    for code in CODES:
        result, old = checks[code], prior.get(code, {})
        ok = result['ok'] is True
        failures = 0 if ok else min(old.get('failures', 0) + 1, 3)
        successes = min(old.get('successes', 0) + 1, 2) if ok else 0
        active = old.get('active', False)
        since = old.get('since')
        if not active and failures >= 3:
            active, since = True, stamp(now)
            events.append({'code': code, 'at': stamp(now), 'kind': 'firing'})
        elif active and successes >= 2:
            active, since = False, None
            events.append({'code': code, 'at': stamp(now), 'kind': 'resolved'})
        status = ('recovering' if ok else 'firing') if active else ('ok' if ok else 'pending')
        state[code] = {'active': active, 'since': since, 'failures': failures, 'successes': successes}
        value = result.get('value')
        output.append({'code': code, 'status': status, 'since': since,
                       'value': value if type(value) in (int, float) and math.isfinite(value) and abs(value) <= 10**18 else None})
    events = events[-50:]
    private = {'checks': state, 'events': events,
               **{key: previous[key] for key in ('media', 'traffic') if key in previous}, **metadata}
    traffic = metadata.get('traffic')
    public = {'updatedAt': stamp(now), 'checks': output, 'events': events,
              'traffic': {k: traffic[k] for k in ('month', 'since', 'bytes')} if traffic else None}
    return private, public


def main():
    os.umask(0o077)
    owner = pwd.getpwnam('devone')
    if not STATE_DIRECTORY.exists():
        STATE_DIRECTORY.mkdir(mode=0o710)
        STATE_DIRECTORY.chmod(0o710)
    os.chown(STATE_DIRECTORY, 0, owner.pw_gid)
    info = STATE_DIRECTORY.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o710 or info.st_uid != 0:
        raise ValueError('Unsafe monitor directory')
    with (STATE_DIRECTORY / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_file = STATE_DIRECTORY / 'state.json'
        previous = read_json(state_file) if state_file.exists() else {}
        now = time.time()
        checks, metadata = collect(read_json(CONFIG), previous, now)
        private, public = advance(previous, checks, metadata, now)
        atomic_json(state_file, private)
        # Group traversal exposes only this allowlisted 0600 snapshot. State
        # and the parent remain root-owned; the API cannot replace root inputs.
        atomic_json(STATE_DIRECTORY / 'status.json', public)
        os.chown(STATE_DIRECTORY / 'status.json', owner.pw_uid, owner.pw_gid)
        print('Operational status updated; no recording state changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        sys.exit('Operational monitor failed; Admin snapshot will expire. Private values omitted.')
