"""record_watch_candidate must never leave crypto_watch_records.jsonl empty.

A plain write_text() truncates the file to 0 bytes before writing the new
content. A run killed mid-write (runner timeout, manual cancel) then leaves
the file empty, and entry_confirm loses every candidate it was tracking.
Writing to a temp file next to the target and renaming over it is atomic on
the same filesystem, so a crash mid-write leaves the OLD content in place,
never nothing.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scanner

RESULT = {"symbol": "BTCUSD", "price": 100.0, "exchange": "delta_india"}
ZONE = {"bottom": 99.0, "top": 99.5}


class WatchRecordAtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = Path(self.tmpdir.name) / "crypto_watch_records.jsonl"

    def _write(self, now_ts):
        with patch.object(scanner, "WATCH_RECORD_FILE", self.path):
            scanner.record_watch_candidate(RESULT, "demand", ZONE, 0.5, now_ts)

    def test_writes_a_valid_row(self):
        self._write(1000.0)
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "BTCUSD")

    def test_appends_across_calls_without_truncating(self):
        self._write(1000.0)
        self._write(1001.0)
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 2)

    def test_no_stray_temp_files_left_behind(self):
        self._write(1000.0)
        self._write(1001.0)
        leftovers = [p for p in Path(self.tmpdir.name).iterdir() if p != self.path]
        self.assertEqual(leftovers, [], f"temp file(s) not cleaned up: {leftovers}")

    def test_a_crash_mid_write_leaves_the_old_content_intact(self):
        # Simulate the process dying after the temp file is written but
        # before the atomic rename - the one moment a plain write_text()
        # would already have destroyed the original.
        self._write(1000.0)
        original = self.path.read_text(encoding="utf-8")

        class Boom(OSError):
            pass

        with patch.object(scanner, "WATCH_RECORD_FILE", self.path), \
             patch.object(Path, "replace", side_effect=Boom("simulated crash")):
            scanner.record_watch_candidate(RESULT, "demand", ZONE, 0.5, 1001.0)

        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_a_crash_mid_write_does_not_leave_a_temp_file(self):
        with patch.object(scanner, "WATCH_RECORD_FILE", self.path), \
             patch.object(Path, "replace", side_effect=OSError("simulated crash")):
            scanner.record_watch_candidate(RESULT, "demand", ZONE, 0.5, 1000.0)
        leftovers = list(Path(self.tmpdir.name).iterdir())
        self.assertEqual(leftovers, [], f"temp file(s) not cleaned up: {leftovers}")


if __name__ == "__main__":
    unittest.main()
