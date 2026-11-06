#!/usr/bin/env python3
"""Check the deployed MediaMTX sandbox can query Linux network routes."""
import argparse
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--unit-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "infra/server/devone-media.service.example",
    )
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() != 0 or not shutil.which("systemd-run"):
        parser.error("Run as root on a Linux host with systemd.")

    unit = configparser.ConfigParser(interpolation=None)
    if not unit.read(args.unit_file) or not unit.has_section("Service"):
        parser.error("MediaMTX service unit is unavailable or invalid.")
    user = unit.get("Service", "User")
    families = unit.get("Service", "RestrictAddressFamilies")
    child = """import socket, sys
try:
    with open('/proc/self/status', encoding='ascii') as source:
        effective = next(line.split()[1] for line in source if line.startswith('CapEff:'))
    if int(effective, 16) != 0:
        raise RuntimeError('probe has unexpected capabilities')
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE) as sock:
        sock.bind((0, 0))
except OSError as error:
    print('NETLINK_ERROR=' + str(error.errno))
    sys.exit(1)
print('NETLINK_OK')
"""
    result = subprocess.run(
        [
            "systemd-run", "--quiet", "--wait", "--pipe", "--collect",
            "-p", "User=" + user,
            "-p", "NoNewPrivileges=yes",
            "-p", "RestrictAddressFamilies=" + families,
            "/usr/bin/python3", "-c", child,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0 or "NETLINK_OK" not in result.stdout.splitlines():
        print("Media sandbox cannot open an unprivileged NETLINK_ROUTE socket.", file=sys.stderr)
        return 1
    print("Media sandbox can open an unprivileged NETLINK_ROUTE socket.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
