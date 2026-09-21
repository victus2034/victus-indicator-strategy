#!/usr/bin/env bash
# Scan repeatedly for the length of one dispatched run.
#
# cron-job.org dispatches the 4h scanner every twenty minutes and the 30m
# scanner every ten, and each dispatch used to scan exactly once. A zone that
# price reaches between two scans is then seen only after the fact: DOGE on
# 21 Sep 2026 ran from ~1.2% away to the zone and back inside the gap between
# the 14:51 and 15:11 scans, and the alert (and GET READY behind it) landed at
# 15:11 - after the touch. The distance band is not the problem, the sampling
# is: 28% of zones enter the 0.20% band and touch inside one minute, and a
# twenty-minute gap misses most of the rest.
#
# So one dispatch now scans every INTERVAL seconds until LOOP seconds are up.
# The repository is public, so the extra runner minutes cost nothing, and the
# dispatch cadence itself (owned by cron-job.org) does not need to change.
#
# Usage: scan_loop.sh LOOP_SECONDS INTERVAL_SECONDS STATE_FILE RECORD_FILE... -- COMMAND...
#
# COMMAND is written out in the workflow (python scanner.py --once) rather than
# buried here, so tests/test_workflow_commands.py still checks it against the
# scanner's own argument parser.
#
# The first scan always runs, exactly as the old single `--once` did, and a
# failed scan never ends the loop - so the worst case is the old behaviour.
# New alert or watch rows are published the moment they appear, because
# entry_confirm reads them from the runtime-state branch and would otherwise
# not see an alert until this whole run ended. The state file (cooldowns) is
# saved with them, and the workflow's own final persist step saves it once
# more at the end.
set -uo pipefail

usage() {
  echo "usage: $0 LOOP_SECONDS INTERVAL_SECONDS STATE_FILE RECORD_FILE... -- COMMAND..." >&2
  exit 2
}
[ "$#" -ge 6 ] || usage

LOOP="$1"
INTERVAL="$2"
STATE_FILE="$3"
shift 3
RECORDS=()
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  RECORDS+=("$1")
  shift
done
[ "$#" -ge 2 ] && [ "$1" = "--" ] && [ "${#RECORDS[@]}" -ge 1 ] || usage
shift
SCAN_ARGV=("$@")

# Room to always leave for one more scan plus a publish before giving up.
SCAN_HEADROOM="${SCAN_LOOP_HEADROOM_SECONDS:-60}"
PERSIST_CMD="${SCAN_LOOP_PERSIST_COMMAND:-bash .github/scripts/persist_runtime_state.sh}"

records_fingerprint() {
  local file
  for file in "${RECORDS[@]}"; do
    if [ -f "${file}" ]; then
      cksum < "${file}"
    else
      echo "missing"
    fi
  done
}

START=${SECONDS}
COUNT=0
while :; do
  COUNT=$(( COUNT + 1 ))
  SCAN_START=${SECONDS}
  BEFORE="$(records_fingerprint)"

  echo "::group::scan ${COUNT} (t+$(( SCAN_START - START ))s)"
  "${SCAN_ARGV[@]}" || echo "::warning::scan ${COUNT} failed; the loop carries on."
  echo "::endgroup::"

  AFTER="$(records_fingerprint)"
  if [ "${BEFORE}" != "${AFTER}" ]; then
    echo "New alert/watch rows on scan ${COUNT}; publishing them now."
    ${PERSIST_CMD} "${STATE_FILE}" "${RECORDS[@]}" \
      || echo "::warning::could not publish mid-run; the final persist step will retry."
  fi

  ELAPSED=$(( SECONDS - SCAN_START ))
  WAIT=$(( INTERVAL - ELAPSED ))
  [ "${WAIT}" -lt 0 ] && WAIT=0

  # Another full scan (start after the wait, run, publish) must still fit.
  if [ $(( SECONDS - START + WAIT + ELAPSED + SCAN_HEADROOM )) -ge "${LOOP}" ]; then
    break
  fi
  sleep "${WAIT}"
done

echo "Scanned ${COUNT} time(s) in $(( SECONDS - START ))s."
