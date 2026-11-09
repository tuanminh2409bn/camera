import json
import unittest
from scripts import poc, render_deployment as renderer


class DeploymentConfigTest(unittest.TestCase):
    def test_air_recording_is_reproducible_and_stays_loopback(self):
        source = poc.validate_source_config({'scheme': 'rtsp', 'host': '192.168.1.64', 'port': 554,
            'channel': '101', 'username': 'fixture-user', 'password': 'Fixture-password-123!', 'transport': 'tcp'})
        config = renderer.air_config(source, {'username': 'playback', 'password': 'Fixture-password-123!'})
        for required in ['playbackAddress: 127.0.0.1:9996', 'record: yes', 'recordSegmentDuration: 1m',
                         'recordDeleteAfter: 1d', 'recordPartDuration: 1s', 'recordMaxPartSize: 10M', 'action: playback', 'path: live']:
            self.assertIn(required, config)
        self.assertNotIn('0.0.0.0', config)
        self.assertEqual(config.count('record: yes'), 1)

    def test_server_never_records_and_exposes_only_ice_ports(self):
        config = json.loads(renderer.server_config({'username': 'backend', 'password': 'Fixture-password-123!'}, '8.8.8.8'))
        self.assertFalse(config['pathDefaults']['record'])
        self.assertFalse(config['paths']['live']['record'])
        self.assertFalse(config['playback'])
        self.assertEqual(config['apiAddress'], '127.0.0.1:9997')
        self.assertEqual(config['webrtcAddress'], '127.0.0.1:8889')
        self.assertEqual(config['paths']['live']['source'], 'rtsp://127.0.0.1:18554/live')
        self.assertEqual(config['authInternalUsers'][0]['ips'], ['127.0.0.1'])
        self.assertEqual(config['pathDefaults']['maxReaders'], 200)

    def test_audio_adapter_publishes_only_on_loopback_without_granting_viewer_access(self):
        config = json.loads(renderer.server_config(
            {'username': 'backend', 'password': 'Fixture-password-123!'}, '8.8.8.8', audio=True))
        self.assertTrue(config['rtsp'])
        self.assertEqual(config['rtspAddress'], '127.0.0.1:18555')
        self.assertEqual(config['rtspTransports'], ['tcp'])
        self.assertEqual(config['paths']['live']['source'], 'publisher')
        self.assertFalse(config['paths']['live']['record'])
        self.assertFalse(config['pathDefaults']['record'])
        publisher = [u for u in config['authInternalUsers'] if u['user'] == 'any']
        self.assertEqual(len(publisher), 1)
        self.assertEqual(publisher[0]['ips'], ['127.0.0.1'])
        self.assertEqual(publisher[0]['permissions'], [{'action': 'publish', 'path': 'live'}])
        backend = [u for u in config['authInternalUsers'] if u['user'] == 'backend'][0]
        self.assertEqual(backend['permissions'], [{'action': 'read', 'path': 'live'}, {'action': 'api'}])

    def test_rejects_anonymous_weak_or_injected_credentials_and_nonpublic_ip(self):
        for bad in [{'username':'any','password':'Fixture-password-123!'}, {'username':'a\nfoo','password':'Fixture-password-123!'},
                    {'username':'backend','password':'short'}]:
            with self.assertRaises(poc.PocError):
                renderer.server_config(bad, '8.8.8.8')
        with self.assertRaises(poc.PocError):
            renderer.server_config({'username':'backend','password':'Fixture-password-123!'}, '127.0.0.1')

    def test_standard_quality_uses_verified_proxy_and_disables_recording(self):
        source = poc.validate_source_config({'scheme': 'rtsp', 'host': '127.0.0.1', 'port': 18556,
            'channel': '101', 'username': 'fixture-user', 'password': 'Fixture-password-123!'})
        account = {'username': 'backend', 'password': 'Fixture-password-123!'}
        edge = renderer.air_config(source, account, standard=True)
        self.assertNotIn('record: yes', edge)
        self.assertIn('/Streaming/Channels/101', edge)
        self.assertIn('  live-standard:', edge)
        self.assertIn('@127.0.0.1:18556/Streaming/Channels/102', edge)
        self.assertIn('action: read\n        path: live-standard', edge)
        with self.assertRaises(poc.PocError):
            renderer.air_config({**source, 'host': '192.168.1.64'}, account, standard=True)
        with self.assertRaises(poc.PocError):
            renderer.server_config(account, '8.8.8.8', standard=True)
        server = json.loads(renderer.server_config(account, '8.8.8.8', audio=True, standard=True))
        self.assertEqual(server['rtspAddress'], '127.0.0.1:18555')
        self.assertFalse(server['paths']['live-standard']['record'])
        for user, action in zip(server['authInternalUsers'], ('read', 'publish')):
            self.assertIn({'action': action, 'path': 'live-standard'}, user['permissions'])

        unit = (poc.REPO_ROOT / 'infra/server/devone-audio-standard.service.example').read_text()
        self.assertIn('rtsp://127.0.0.1:18554/live-standard', unit)
        self.assertIn('rtsp://127.0.0.1:18555/live-standard', unit)
        self.assertIn('-c:v copy -c:a libopus', unit)
