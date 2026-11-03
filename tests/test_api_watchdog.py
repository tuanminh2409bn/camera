import contextlib
import io
import subprocess
import sys
import unittest
from unittest import mock
from scripts import api_watchdog


class WatchdogTest(unittest.TestCase):
    def test_unhealthy_api_terminates_only_owned_child(self):
        # Real child ownership, accelerated time and an unavailable health probe.
        # This does not exercise Linux systemd BindsTo, which has a separate gate.
        real_popen = subprocess.Popen
        owned = []
        unrelated = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'])

        def launch(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            owned.append(child)
            return child

        opener = mock.Mock()
        opener.open.side_effect = OSError('fixture offline')
        try:
            with mock.patch.object(api_watchdog.subprocess, 'Popen', side_effect=launch), \
                 mock.patch.object(api_watchdog.time, 'sleep'), \
                 mock.patch.object(api_watchdog.time, 'monotonic', side_effect=[0, 16, 16, 16]), \
                 mock.patch.object(api_watchdog.urllib.request, 'build_opener', return_value=opener), \
                 mock.patch.object(api_watchdog.signal, 'signal'), \
                 mock.patch.object(sys, 'argv', ['watchdog', sys.executable, '-c', 'import time; time.sleep(60)']), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(api_watchdog.main(), 1)
            self.assertEqual(opener.open.call_count, 3)
            self.assertEqual(len(owned), 1)
            self.assertIsNotNone(owned[0].poll())
            self.assertIsNone(unrelated.poll(), 'another process must not be signaled')
        finally:
            for child in owned + [unrelated]:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
