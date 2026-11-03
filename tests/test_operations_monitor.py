from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from scripts import operations_monitor as monitor


class OperationsMonitorTest(unittest.TestCase):
    def checks(self, failed=None):
        return {code: {'ok': code != failed, 'value': None} for code in monitor.CODES}

    def test_incident_requires_three_failures_and_two_recoveries_without_duplicates(self):
        state = {}
        for n in range(3):
            state, output = monitor.advance(state, self.checks('AIR'), {}, 1000 + n * 60)
        self.assertEqual([e['kind'] for e in output['events']], ['firing'])
        self.assertEqual(next(x for x in output['checks'] if x['code'] == 'AIR')['status'], 'firing')
        for n in range(10):
            state, output = monitor.advance(state, self.checks('AIR'), {}, 2000 + n * 60)
        self.assertEqual(len(output['events']), 1)
        state, output = monitor.advance(state, self.checks(), {}, 3000)
        self.assertEqual(next(x for x in output['checks'] if x['code'] == 'AIR')['status'], 'recovering')
        state, output = monitor.advance(state, self.checks(), {}, 3060)
        self.assertEqual([e['kind'] for e in output['events']], ['firing', 'resolved'])

    def test_transient_failure_is_pending_and_cannot_create_false_recovery(self):
        state, output = monitor.advance({}, self.checks('AUDIO'), {}, 1000)
        self.assertEqual(next(x for x in output['checks'] if x['code'] == 'AUDIO')['status'], 'pending')
        state, output = monitor.advance(state, self.checks(), {}, 1060)
        self.assertEqual(output['events'], [])

    def test_payload_excludes_internal_metadata_logs_and_non_numeric_values(self):
        checks = self.checks()
        checks['API']['value'] = 'private-url-must-never-leak'
        checks['AIR']['value'] = float('nan')
        state, output = monitor.advance({}, checks, {'media': {'epoch': 'internal', 'counter': 1}, 'private': 'fixture-secret', 'traffic': {'month': '2026-11', 'since': monitor.stamp(1), 'bytes': 123, 'counter': 999, 'bootId': 'private-boot-id'}}, 1000)
        text = json.dumps(output)
        self.assertNotIn('fixture-secret', text)
        self.assertNotIn('private-url', text)
        self.assertNotIn('bootId', text)
        self.assertNotIn('counter', text)
        self.assertNotIn('NaN', text)

    def test_history_is_bounded(self):
        state = {}
        for n in range(300):
            checks = self.checks('AIR') if n % 5 < 3 else self.checks()
            state, output = monitor.advance(state, checks, {}, n * 60)
        self.assertEqual(len(output['events']), 50)

    def test_traffic_reset_and_month_change_do_not_double_count(self):
        first = monitor.traffic_state(None, 100000, 'boot-a', 1793664000)
        self.assertEqual(first['bytes'], 0)
        second = monitor.traffic_state(first, 100250, 'boot-a', 1793664060)
        self.assertEqual(second['bytes'], 250)
        restarted = monitor.traffic_state(second, 100, 'boot-b', 1793664120)
        self.assertEqual(restarted['bytes'], 250)
        reset = monitor.traffic_state(restarted, 50, 'boot-b', 1793664180)
        self.assertEqual(reset['bytes'], 250)
        new_month = monitor.traffic_state(reset, 999, 'boot-b', 1796256000)
        self.assertEqual(new_month['bytes'], 0)
        self.assertNotEqual(new_month['month'], reset['month'])

    def test_temporarily_missing_counter_preserves_history_but_does_not_publish_stale_traffic(self):
        traffic = monitor.traffic_state(None, 100, 'boot-a', 1793664000)
        traffic = monitor.traffic_state(traffic, 200, 'boot-a', 1793664060)
        state, public = monitor.advance({'traffic': traffic}, self.checks(), {}, 1793664120)
        self.assertIsNone(public['traffic'])
        resumed = monitor.traffic_state(state['traffic'], 250, 'boot-a', 1793664180)
        self.assertEqual(resumed['bytes'], 150)

    def test_missing_backup_detected_at_first_daily_deadline_with_grace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = 'metadata-20261103T073257Z-0123abcd.zip.gpg'
            path = root / name
            path.write_bytes(b'ciphertext')
            path.chmod(0o600)
            status = {'name': name, 'bytes': 10, 'lastSuccess': '2026-11-03T07:32:57Z'}
            before = datetime(2026, 11, 3, 19, 44, tzinfo=timezone.utc).timestamp()
            after = datetime(2026, 11, 3, 19, 45, tzinfo=timezone.utc).timestamp()
            self.assertTrue(monitor.backup_healthy(status, root, before))
            self.assertFalse(monitor.backup_healthy(status, root, after))
            status['lastSuccess'] = '2026-11-03T19:15:30Z'
            self.assertTrue(monitor.backup_healthy(status, root, after))
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                monitor.backup_healthy(status, root, after)

    def test_unsafe_status_and_non_loopback_probes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{}')
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                monitor.read_json(path)
            path.chmod(0o600)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                monitor.read_json(link)
        for origin in ('http://example.com', 'http://user:secret@127.0.0.1:9997', 'http://127.0.0.1:9997/other'):
            with self.assertRaises(ValueError):
                monitor.request_json(origin, '/status')
