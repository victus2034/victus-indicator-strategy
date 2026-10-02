import importlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nse_scanner

ROOT = Path(__file__).resolve().parents[1]


class NseScanLoopTests(unittest.TestCase):
    def test_interval_follows_env(self):
        import nse_config

        with patch.dict(os.environ, {"VICTUS_MIN_SCAN_INTERVAL_SECONDS": "60"}):
            self.assertEqual(importlib.reload(nse_config).MIN_SCAN_INTERVAL_SECONDS, 60)
        with patch.dict(os.environ, {"VICTUS_MIN_SCAN_INTERVAL_SECONDS": ""}):
            self.assertEqual(importlib.reload(nse_config).MIN_SCAN_INTERVAL_SECONDS, 8 * 60)

    def test_helpers_are_noops_outside_the_loop(self):
        with patch.dict(os.environ, {"SCAN_LOOP_STOP_FILE": ""}):
            nse_scanner.stop_scan_loop()
            self.assertTrue(nse_scanner.first_pass_this_loop("preopen"))
            self.assertTrue(nse_scanner.first_pass_this_loop("preopen"))

    def test_preopen_status_once_per_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = str(Path(tmp) / "stop")
            with patch.dict(os.environ, {"SCAN_LOOP_STOP_FILE": stop}):
                self.assertTrue(nse_scanner.first_pass_this_loop("preopen"))
                self.assertFalse(nse_scanner.first_pass_this_loop("preopen"))
                nse_scanner.stop_scan_loop()
            self.assertTrue(Path(stop).exists())

    def test_loop_ends_when_a_scan_asks(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("state.json", "records.jsonl"):
                Path(tmp, name).touch()
            scan = 'echo scan; touch "$SCAN_LOOP_STOP_FILE"'
            env = dict(os.environ, SCAN_LOOP_PERSIST_COMMAND="true", SCAN_LOOP_HEADROOM_SECONDS="0")
            env.pop("SCAN_LOOP_STOP_FILE", None)
            out = subprocess.run(
                ["bash", str(ROOT / ".github/scripts/scan_loop.sh"), "60", "1",
                 "state.json", "records.jsonl", "--", "bash", "-c", scan],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=30,
            ).stdout
            self.assertIn("Scanned 1 time(s)", out)


if __name__ == "__main__":
    unittest.main()
