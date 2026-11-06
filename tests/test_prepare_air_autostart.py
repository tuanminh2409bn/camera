import hashlib
import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from scripts import poc, prepare_air_autostart as preparation


class AirAutostartPreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (poc.REPO_ROOT / '.local').mkdir(mode=0o700, exist_ok=True)

    def test_bundle_copies_exact_source_and_never_installs(self):
        with tempfile.TemporaryDirectory(dir=poc.REPO_ROOT / '.local') as tmp:
            output = preparation.prepare(Path(tmp) / 'bundle')
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertFalse(manifest['installed'])
            self.assertFalse(manifest['recordingOnStart'])
            for entry in manifest['files']:
                file = output / entry['file']
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), entry['sha256'])
                if entry['file'].startswith('runtime/'):
                    self.assertEqual(file.read_bytes(), (poc.REPO_ROOT / 'scripts' / file.name).read_bytes())
            with self.assertRaises(poc.PocError):
                preparation.prepare(output)

    def test_login_agents_restart_crashes_but_respect_auth_stop(self):
        agents = {name: plistlib.loads(payload) for name, payload in preparation.render_agents(poc.REPO_ROOT).items()}
        self.assertEqual(len(agents), 3)
        recorder = agents['com.devone.camera.air-recording-supervisor.plist']
        self.assertEqual(recorder['KeepAlive'], {'SuccessfulExit': False})
        self.assertEqual(recorder['ThrottleInterval'], 60)
        self.assertIn(preparation.RUNTIME + '/air_login_supervisor.pl', recorder['ProgramArguments'])
        gateway = agents['com.devone.camera.web-gateway.plist']
        self.assertEqual(gateway['ProgramArguments'][1], preparation.RUNTIME + '/air_web_gateway.pl')
        for agent in agents.values():
            self.assertTrue(agent['RunAtLoad'])
            self.assertEqual(agent['LimitLoadToSessionType'], 'Aqua')
            self.assertEqual(agent['WorkingDirectory'], preparation.TARGET)
            self.assertEqual(agent['Umask'], 63)

    def test_rejects_output_outside_private_workspace_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=poc.REPO_ROOT / '.local') as tmp:
            link = Path(tmp) / 'link'
            link.symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(poc.PocError):
                preparation.prepare(link / 'bundle')
        with self.assertRaises(poc.PocError):
            preparation.prepare(poc.REPO_ROOT / 'autostart-public-bundle')
