#!/usr/bin/env bash
set -euo pipefail

BRANCH="${VICTUS_RUNTIME_STATE_BRANCH:-scanner-runtime-state}"
# Seconds between attempts; overridable so tests do not sleep.
RETRY_DELAYS=(${VICTUS_RESTORE_RETRY_DELAYS:-2 4 8})

if [ "$#" -eq 0 ]; then
  echo "No runtime files requested."
  exit 0
fi

# A failed fetch used to be read as "the branch does not exist yet", so a
# network blip started the run on empty state: cooldowns reset (a burst of
# repeat alerts) and the persist step then overwrote the branch's alert
# records with only this run's rows. Only a remote that answers and has no
# such branch counts as "not there yet"; anything else retries, then fails
# the job before a scan can run.
attempt=0
while :; do
  set +e
  git ls-remote --exit-code --heads origin "${BRANCH}" >/dev/null 2>&1
  status=$?
  set -e
  if [ "${status}" -eq 2 ]; then
    echo "Runtime state branch ${BRANCH} does not exist yet."
    exit 0
  fi
  if [ "${status}" -eq 0 ] && git fetch --quiet origin "${BRANCH}"; then
    break
  fi
  if [ "${attempt}" -ge "${#RETRY_DELAYS[@]}" ]; then
    echo "::error::Could not fetch runtime state branch ${BRANCH}; stopping rather than starting from empty state."
    exit 1
  fi
  echo "::warning::Fetching ${BRANCH} failed; retrying in ${RETRY_DELAYS[${attempt}]}s."
  sleep "${RETRY_DELAYS[${attempt}]}"
  attempt=$(( attempt + 1 ))
done

for file in "$@"; do
  if git cat-file -e "origin/${BRANCH}:${file}" 2>/dev/null; then
    mkdir -p "$(dirname "${file}")"
    git show "origin/${BRANCH}:${file}" > "${file}"
    echo "Restored ${file} from ${BRANCH}."
  else
    echo "No saved runtime state for ${file}."
  fi
done
