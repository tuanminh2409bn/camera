import configparser
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import poc, prepare_nuc_runtime as preparation


def parse_unit(raw):
    unit = configparser.ConfigParser(interpolation=None)
    unit.optionxform = str
    unit.read_string(raw.decode())
    return unit


class NucRuntimePreparationTests(unittest.TestCase):
    def test_openssh_parses_linux_tunnels_with_only_their_assigned_forwards(self):
        profiles = preparation.render_tunnel_profiles('1.1.1.1')
        with tempfile.TemporaryDirectory() as temporary:
            for role, (alias, user, forwards) in {
                'server-tunnel': ('devone-server', 'devone-air', {
                    '127.0.0.1:18554 127.0.0.1:8554', '127.0.0.1:19996 127.0.0.1:9900'}),
                'maintenance-relay': ('camera-maint-relay', 'camera-maint-relay', {
                    '127.0.0.1:19022 127.0.0.1:22'}),
            }.items():
                path = Path(temporary) / role
                path.write_bytes(profiles[role])
                result = subprocess.run(['/usr/bin/ssh', '-G', '-F', str(path), alias],
                                        text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                pairs = [line.split(' ', 1) for line in result.stdout.splitlines() if ' ' in line]
                config = dict(pairs)
                self.assertEqual(config['user'], user)
                self.assertEqual(config['port'], '2222')
                self.assertEqual(config['passwordauthentication'], 'no')
                self.assertEqual(config['kbdinteractiveauthentication'], 'no')
                self.assertEqual(config['batchmode'], 'yes')
                self.assertEqual(config['stricthostkeychecking'], 'true')
                self.assertEqual(config['exitonforwardfailure'], 'yes')
                self.assertEqual(config['forwardagent'], 'no')
                actual_forwards = {value.replace('[', '').replace(']', '')
                                   for key, value in pairs if key == 'remoteforward'}
                self.assertEqual(actual_forwards, forwards)
                self.assertFalse(any(key == 'localforward' for key, _ in pairs))

    def test_tunnel_rejects_nonpublic_or_injected_server_addresses(self):
        for address in ('192.168.1.22', '203.0.113.5', '::1', '1.1.1.1\nUser root'):
            with self.subTest(address=address), self.assertRaises(poc.PocError):
                preparation.render_tunnel_profiles(address)

    def test_services_boot_without_login_and_preserve_auth_fail_stop(self):
        units = {name: parse_unit(raw) for name, raw in preparation.render_units().items()}
        self.assertEqual(set(units), {
            'devone-edge-recording.service', 'devone-edge-source.service',
            'devone-edge-gateway.service', 'devone-edge-live-tunnel.service',
            'devone-edge-maintenance-relay.service',
        })
        recorder = units['devone-edge-recording.service']
        self.assertEqual(recorder['Service']['Restart'], 'on-failure')
        self.assertIn('air_login_supervisor.pl --workspace ', recorder['Service']['ExecStart'])
        self.assertNotIn('RestartForceExitStatus', recorder['Service'])
        for unit in units.values():
            self.assertEqual(unit['Install']['WantedBy'], 'multi-user.target')
            service = unit['Service']
            self.assertEqual(service['User'], 'devone-edge')
            self.assertEqual(service['WorkingDirectory'], preparation.WORKSPACE)
            self.assertEqual(service['UMask'], '0077')
            self.assertEqual(service['KillMode'], 'control-group')
            self.assertEqual(service['NoNewPrivileges'], 'yes')
            self.assertEqual(service['ProtectHome'], 'yes')
            self.assertEqual(service['ProtectSystem'], 'strict')
            self.assertIn('AF_NETLINK', service['RestrictAddressFamilies'])
            self.assertEqual(service['CapabilityBoundingSet'], '')
            self.assertNotIn('/Users/', service['ExecStart'])

    def test_tunnels_have_separate_profiles_and_retry_disconnects(self):
        units = {name: parse_unit(raw) for name, raw in preparation.render_units().items()}
        live = units['devone-edge-live-tunnel.service']['Service']
        relay = units['devone-edge-maintenance-relay.service']['Service']
        self.assertIn('/ssh/server-tunnel/config', live['ExecStart'])
        self.assertIn('/ssh/maintenance-relay/config', relay['ExecStart'])
        for service in (live, relay):
            self.assertEqual(service['Restart'], 'always')
            self.assertIn('/usr/bin/ssh -N -F ', service['ExecStart'])

    def test_bundle_is_private_reviewable_and_contains_no_credentials(self):
        (poc.REPO_ROOT / '.local').mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=poc.REPO_ROOT / '.local') as temporary:
            output = preparation.prepare(Path(temporary) / 'bundle', server_ip='1.1.1.1')
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertFalse(manifest['installed'])
            self.assertFalse(manifest['recordingOnStart'])
            self.assertFalse(manifest['includesCredentials'])
            self.assertEqual(manifest['workspace'], preparation.WORKSPACE)
            self.assertEqual(len(manifest['files']), len(preparation.SCRIPTS) + 7)
            for entry in manifest['files']:
                path = output / entry['file']
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
                self.assertTrue(entry['destination'].startswith(('/var/lib/devone-edge/', '/etc/systemd/system/')))
                if entry['file'].startswith('scripts/'):
                    self.assertEqual((entry['owner'], entry['group'], entry['mode']),
                                     ('root', 'devone-edge', '0640'))
                elif entry['file'].startswith('profiles/'):
                    self.assertEqual((entry['owner'], entry['mode']), ('devone-edge', '0600'))
            with self.assertRaises(poc.PocError):
                preparation.prepare(output, server_ip='1.1.1.1')

    def test_unsafe_bundle_paths_are_rejected_without_mutating_them(self):
        (poc.REPO_ROOT / '.local').mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=poc.REPO_ROOT / '.local') as temporary:
            shared = Path(temporary) / 'shared'
            shared.mkdir(mode=0o755)
            shared.chmod(0o755)
            with self.assertRaises(poc.PocError):
                preparation.prepare(shared / 'bundle', server_ip='1.1.1.1')
            self.assertEqual(shared.stat().st_mode & 0o777, 0o755)
            link = Path(temporary) / 'link'
            link.symlink_to(temporary, target_is_directory=True)
            with self.assertRaises(poc.PocError):
                preparation.prepare(link / 'bundle', server_ip='1.1.1.1')
        with self.assertRaises(poc.PocError):
            preparation.prepare(poc.REPO_ROOT / 'public-nuc-bundle', server_ip='1.1.1.1')
