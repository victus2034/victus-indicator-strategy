#!/usr/bin/env bash
# Fire any daily or weekly workflow that has missed its slot.
#
# The eight alert workflows are dispatched by cron-job.org and land on time.
# The daily and weekly ones were left on GitHub's own scheduler, which is not
# so much a scheduler as a suggestion: across nine days the daily astrology
# briefing was 4h42m late on its best day and 11h35m on its worst, and never
# once ran at 07:00. The daily backtest had been moved to cron-job.org and
# then simply stopped being dispatched on 4 Sep, silent for two days.
#
# So this runs off the back of the crypto scanner, which cron-job.org keeps
# alive every twenty minutes, and asks one question per job: has it run since
# the time it was due today? If not, dispatch it.
#
# The scanner is dark 01:00-08:00 IST, so nothing due in that window can be
# caught until it wakes. Everything due in waking hours lands within twenty
# minutes; the 07:00 astrology briefing goes out at first light, ~08:10.
#
# IST is computed as a fixed +05:30 rather than through TZ, deliberately.
# India has no DST, and a missing tz database makes TZ fail silently by
# falling back to UTC - which would put every due time 5h30m out and fire
# each job at the wrong hour, with nothing in the log to say why.
set -uo pipefail

API="https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows"
IST_OFFSET=19800          # +05:30 in seconds
NOW=$(date -u +%s)
IST_NOW=$(( NOW + IST_OFFSET ))
IST_MIDNIGHT=$(( IST_NOW - IST_NOW % 86400 ))
IST_DOW=$(date -u -d "@${IST_NOW}" +%u)     # 1=Mon .. 7=Sun, in IST
STATUS=0

ist_clock() { date -u -d "@$(( $1 + IST_OFFSET ))" '+%H:%M'; }

# dispatch_if_overdue <workflow file> <HH:MM IST> [ISO weekday 1-7]
dispatch_if_overdue() {
  local wf="$1" at="$2" dow="${3:-}"

  if [ -n "${dow}" ] && [ "${IST_DOW}" != "${dow}" ]; then
    printf '  %-32s skipped - not its weekday\n' "${wf}"
    return 0
  fi

  local hh=${at%%:*} mm=${at##*:} due
  due=$(( IST_MIDNIGHT + 10#${hh} * 3600 + 10#${mm} * 60 - IST_OFFSET ))

  if [ "${NOW}" -lt "${due}" ]; then
    printf '  %-32s not due yet (%s IST)\n' "${wf}" "${at}"
    return 0
  fi

  local body last
  body=$(curl -sS -H "Authorization: Bearer ${GH_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "${API}/${wf}/runs?per_page=1") || {
      echo "::warning::${wf}: could not read run history; leaving it alone"
      STATUS=1; return 0; }

  last=$(printf '%s' "${body}" | jq -r '.workflow_runs[0].created_at // empty')

  if [ -n "${last}" ]; then
    local last_epoch
    last_epoch=$(date -u -d "${last}" +%s) || last_epoch=0
    if [ "${last_epoch}" -ge "${due}" ]; then
      printf '  %-32s already ran at %s IST\n' "${wf}" "$(ist_clock "${last_epoch}")"
      return 0
    fi
    printf '  %-32s OVERDUE - due %s IST, last ran %s\n' \
      "${wf}" "${at}" "$(date -u -d "@${last_epoch}" '+%d %b')"
  else
    printf '  %-32s OVERDUE - due %s IST, no run on record\n' "${wf}" "${at}"
  fi

  if curl -sS -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer ${GH_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "${API}/${wf}/dispatches" \
      -d "{\"ref\":\"${GITHUB_REF_NAME:-main}\"}" | grep -q '^2'; then
    echo "::notice::Dispatched ${wf}, which had missed its ${at} IST slot."
  else
    echo "::warning::${wf}: dispatch request was refused"
    STATUS=1
  fi
}

echo "IST now $(ist_clock "${NOW}") (weekday ${IST_DOW})"

# The times these workflows' own cron lines named, kept in IST because that is
# the timezone every alert in this repo is written for.
dispatch_if_overdue daily_astrology.yml         "07:00"
dispatch_if_overdue daily_backtest_summary.yml  "16:35"
dispatch_if_overdue weekly_astrology.yml        "19:00" 7   # Sunday
dispatch_if_overdue weekly_backtest_summary.yml "17:00" 5   # Friday

exit "${STATUS}"
