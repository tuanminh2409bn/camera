import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import camera_management as client
from scripts.camera_management import private_directory, private_read, private_write, render_config


class ManagementClientTests(unittest.TestCase):
    def test_real_openssh_parses_portable_config_with_spaced_paths(self):
        with tempfile.TemporaryDirectory(prefix='camera management ') as tmp:
            p = Path(tmp)/'ssh config'
            p.write_text(render_config())
            for host, user, destination, port in [('camera-air', 'macbook', '127.0.0.1', '19022'),
                                                  ('camera-maint-jump', 'camera-maint-jump', '168.144.137.69', '2222')]:
                result = subprocess.run(['/usr/bin/ssh', '-G', '-F', str(p), host], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0)
                parsed = dict(line.split(' ', 1) for line in result.stdout.splitlines() if ' ' in line)
                for key, expected in [('user', user), ('hostname', destination), ('port', port),
                                      ('forwardagent', 'no'), ('batchmode', 'yes'), ('stricthostkeychecking', 'true')]:
                    self.assertEqual(parsed[key], expected)
                if host == 'camera-air':
                    self.assertEqual(parsed['proxyjump'], 'camera-maint-jump')
                    self.assertEqual(parsed['hostkeyalias'], '192.168.1.12')

    def test_private_write_replaces_only_valid_owned_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = private_directory(Path(tmp).resolve()/'runtime')
            p = root/'settings'
            private_write(p, b'first');private_write(p, b'next')
            self.assertEqual(private_read(p), b'next')
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            p.chmod(0o644)
            with self.assertRaises(ValueError):
                private_write(p, b'bad')
            self.assertEqual(p.read_bytes(), b'next')

    def test_symlink_file_and_parent_cannot_redirect_private_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = private_directory(Path(tmp).resolve()/'runtime')
            target = Path(tmp)/'unrelated';target.write_bytes(b'keep')
            (root/'link').symlink_to(target)
            with self.assertRaises(ValueError):
                private_write(root/'link', b'bad')
            (root/'redirect').symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                private_write(root/'redirect'/'other', b'bad')
            self.assertEqual(target.read_bytes(), b'keep')

    def test_shared_directory_is_rejected_without_chmod_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'runtime';p.mkdir();p.chmod(0o755)
            with self.assertRaises(ValueError):
                private_directory(p)
            self.assertEqual(p.stat().st_mode & 0o777, 0o755)

    def test_nested_proxy_process_reads_its_profile_without_spaced_F_failure(self):
        # The jump transport exits locally before authentication: no network or
        # real key is used. This checks the actual child ssh process, not -G only.
        with tempfile.TemporaryDirectory(prefix='camera-proxy-') as tmp:
            home = Path(tmp).resolve()
            profile = home/'.ssh/camera-management/config'
            runtime = home/'Library/Application Support/CameraRemote'
            text = 'Host camera-maint-jump\n    ProxyCommand /usr/bin/true\n'+render_config()
            private_write(profile, text.encode())
            private_write(runtime/'ssh_config', text.encode())
            with patch.object(client, 'PROFILE', profile), patch.object(client, 'RUNTIME', runtime):
                p = subprocess.run(client.ssh_args()+['-vv', '-T', 'camera-air', 'true'], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(p.returncode, 0)  # Mock transport deliberately has no SSH server.
            self.assertNotIn("Can't open user config file", p.stderr)
            self.assertIn('Executing proxy command: exec /usr/bin/true', p.stderr)
