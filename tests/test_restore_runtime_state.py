"""Runtime state must never be silently replaced by an empty start.

restore_runtime_state.sh used to read any failed `git fetch` as "the branch
does not exist yet" and exit 0. A network blip then started the scan on empty
state - every cooldown gone, a burst of repeat alerts - and the persist step
overwrote the branch's alert records with only that run's rows.
"""
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/restore_runtime_state.sh"
WORKFLOWS = ROOT / ".github/workflows"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class RestoreScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = pathlib.Path(self.tmp.name)
        self.remote = base / "remote.git"
        self.work = base / "work"
        git(base, "init", "--quiet", "--bare", str(self.remote))
        git(base, "init", "--quiet", str(self.work))
        git(self.work, "remote", "add", "origin", str(self.remote))

    def run_restore(self, *files):
        env = dict(os.environ, VICTUS_RESTORE_RETRY_DELAYS="0 0")
        return subprocess.run(
            ["bash", str(SCRIPT), *files], cwd=self.work, env=env, capture_output=True, text=True
        )

    def push_state(self, name, content):
        seed = pathlib.Path(self.tmp.name) / "seed"
        git(pathlib.Path(self.tmp.name), "init", "--quiet", str(seed))
        (seed / name).write_text(content, encoding="utf-8")
        git(seed, "add", name)
        git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "state")
        git(seed, "push", "--quiet", str(self.remote), "HEAD:refs/heads/scanner-runtime-state")

    def test_a_missing_branch_is_a_fresh_start(self):
        result = self.run_restore("alert_state.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("does not exist yet", result.stdout)

    def test_an_existing_branch_is_restored(self):
        self.push_state("alert_state.json", '{"k": 1}')
        result = self.run_restore("alert_state.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / "alert_state.json").read_text(encoding="utf-8"), '{"k": 1}')

    def test_an_unreachable_remote_fails_the_job(self):
        git(self.work, "remote", "set-url", "origin", str(pathlib.Path(self.tmp.name) / "gone.git"))
        result = self.run_restore("alert_state.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("does not exist yet", result.stdout)
        self.assertFalse((self.work / "alert_state.json").exists())


class PersistStepTests(unittest.TestCase):
    """Every persist step runs after a failed scan, but never after a failed restore."""

    def test_persist_steps_run_always_but_only_after_a_good_restore(self):
        checked = 0
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            if "persist_runtime_state.sh" not in text or "restore_runtime_state.sh" not in text:
                continue
            if workflow.name == "fib_trendline_scan.yml":
                continue  # restore failing now stops its scan; its persist then has nothing to save
            checked += 1
            self.assertRegex(
                text, r"- name: Restore runtime state\n\s+id: restore\n", workflow.name
            )
            persist = re.search(r"- name: Persist runtime state\n\s+if: \$\{\{([^}]*)\}\}", text)
            self.assertIsNotNone(persist, workflow.name)
            self.assertIn("always()", persist.group(1), workflow.name)
            self.assertIn("steps.restore.outcome == 'success'", persist.group(1), workflow.name)
        self.assertGreaterEqual(checked, 7)


if __name__ == "__main__":
    unittest.main()
