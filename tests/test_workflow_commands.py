"""Every command a workflow runs must be one its script accepts.

paper_trading's --timeframe choices were derived from a dict in another
module. That dict grew a market layer, the choices silently became
{crypto, nse}, and every scheduled tick died on `--timeframe 30m` - its
own default. Nothing in the suite touched an argument parser, so it took a
Discord failure notice to find out.
"""
import importlib
import pathlib
import re
import shlex
import unittest

WORKFLOWS = pathlib.Path(".github/workflows")


def scheduled_commands():
    """(workflow, script, argv) for every python call in every workflow."""
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        joined = workflow.read_text(encoding="utf-8").replace("\\n", " ")
        for line in joined.splitlines():
            match = re.search(r"python\s+([a-z_]+\.py)(.*)", line)
            if not match:
                continue
            script, rest = match.group(1), match.group(2).strip()
            # ${VAR:-default} is what a scheduled run gets: the default.
            rest = re.sub(r"\$\{[A-Z_]+:-([^}]*)\}", r"\1", rest)
            try:
                tokens = shlex.split(rest)
            except ValueError:
                continue
            # A value that is still a shell variable cannot be checked,
            # and dropping it alone would orphan its flag into looking
            # like a flag with a missing argument.
            cleaned = []
            skip_next = False
            for index, token in enumerate(tokens):
                if skip_next:
                    skip_next = False
                    continue
                following = tokens[index + 1] if index + 1 < len(tokens) else ""
                if token.startswith("--") and "$" in following:
                    skip_next = True
                    continue
                if "$" in token:
                    continue
                cleaned.append(token)
            yield workflow.name, script, cleaned


class EntryConfirmPriceSourceTests(unittest.TestCase):
    """entry_confirm must judge entries against a live price, not a stale candle.

    scanner.live_ticker_price falls back to the close of the last COMPLETED
    candle unless USE_LIVE_TICKER is set, and scanner's own default timeframe
    is 4h. With neither exported, a 30m zone was measured against a candle up
    to four hours old: DOGE on 7 Sep alerted at 18:52 sitting 0.01% off its
    entry, was judged at 18:55 against the 17:30 close, read as 0.71% past
    entry and outside the approach band, and never pinged at all. Thirty-six
    percent of watched zones were going silent this way.
    """

    def setUp(self):
        self.yaml = (WORKFLOWS / "entry_confirm.yml").read_text(encoding="utf-8")

    def test_the_live_ticker_is_enabled(self):
        self.assertIn('VICTUS_USE_LIVE_TICKER: "true"', self.yaml)

    def test_the_candle_fallback_is_not_left_at_4h(self):
        self.assertIn('VICTUS_TIMEFRAME: "30m"', self.yaml)

    def test_the_fallback_would_be_stale_without_the_flag(self):
        # Guards the mechanism itself: if this default ever flips, the two
        # assertions above stop being load-bearing and should be revisited.
        import scanner

        self.assertEqual(
            scanner.live_ticker_price("binance", "BTCUSD", 123.0),
            (123.0, "candle_close"),
            "with USE_LIVE_TICKER off the candle close is returned verbatim",
        )


class WorkflowCommandTests(unittest.TestCase):
    def test_every_referenced_script_exists(self):
        for workflow, script, _ in scheduled_commands():
            with self.subTest(workflow=workflow, script=script):
                self.assertTrue(
                    pathlib.Path(script).exists(),
                    f"{workflow} runs {script}, which is not in the repo",
                )

    def test_every_scheduled_command_parses(self):
        for workflow, script, tokens in scheduled_commands():
            module = importlib.import_module(script[:-3])
            parse_args = getattr(module, "parse_args", None)
            if parse_args is None:
                continue
            with self.subTest(workflow=workflow, script=script, argv=tokens):
                try:
                    parse_args(tokens)
                except SystemExit as exit_error:
                    self.fail(
                        f"{workflow} runs `{script} {' '.join(tokens)}` "
                        f"but its own parser rejects it ({exit_error})"
                    )

    def test_the_commands_are_actually_being_found(self):
        # A regex that quietly matched nothing would make the tests above
        # pass while checking not one command.
        found = {script for _, script, _ in scheduled_commands()}
        self.assertIn("scanner.py", found)
        self.assertIn("paper_trading.py", found)
        self.assertGreaterEqual(len(found), 6)


if __name__ == "__main__":
    unittest.main()
