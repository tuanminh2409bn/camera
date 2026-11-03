#!/usr/bin/env python3
"""Own one API child; exit on hung authorization so systemd stops bound media."""
import json
import signal
import subprocess
import sys
import time
import urllib.request


def main():
    if len(sys.argv) < 2:
        return 2
    child = subprocess.Popen(sys.argv[1:], start_new_session=True)
    stopped = False

    def stop(_signal=None, _frame=None):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    failures = 0
    started = time.monotonic()
    try:
        while not stopped and child.poll() is None:
            time.sleep(2)
            try:
                with opener.open('http://127.0.0.1:3001/api/health', timeout=2) as response:
                    healthy = json.loads(response.read(1024)).get('status') == 'ok'
                failures = 0 if healthy else failures + 1
            except (OSError, ValueError):
                failures += 1
            if time.monotonic() - started > 15 and failures >= 3:
                sys.stderr.write('API health deadline exceeded; stopping owned process.\n')
                break
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return 0 if stopped else 1


if __name__ == '__main__':
    sys.exit(main())
