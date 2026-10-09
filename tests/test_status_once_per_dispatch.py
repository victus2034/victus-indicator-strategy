"""Status posts go out once per scan_loop.sh dispatch, not on every pass (2026-10-09)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nse_scanner
import scanner


class FirstPassTests(unittest.TestCase):
    def test_outside_the_loop_every_pass_is_first(self):
        with patch.dict(os.environ, {"SCAN_LOOP_STOP_FILE": ""}):
            self.assertTrue(scanner.first_pass_this_loop("status-4h"))
            self.assertTrue(scanner.first_pass_this_loop("status-4h"))

    def test_inside_the_loop_only_the_first_pass_is(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = str(Path(folder) / "stop")
            with patch.dict(os.environ, {"SCAN_LOOP_STOP_FILE": stop}):
                self.assertTrue(scanner.first_pass_this_loop("status-4h"))
                self.assertFalse(scanner.first_pass_this_loop("status-4h"))
                self.assertTrue(scanner.first_pass_this_loop("status-30m"))

    def test_nse_shares_the_helper(self):
        self.assertIs(nse_scanner.first_pass_this_loop, scanner.first_pass_this_loop)


if __name__ == "__main__":
    unittest.main()
