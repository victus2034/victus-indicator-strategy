"""Apply research/rebuild_since_sep1.py's patch to a scanner-runtime-state checkout.

Idempotent: a row is dropped or replaced by its id, so applying the same patch
again (say after a scan that started before the first apply saved its own copy
of a file over it) gives the same files. Rows appended since the patch was
built are left alone. The first apply keeps each touched file as
<name>.pre_rebuild_2026-10-11<ext>; a later apply never overwrites that backup.

    python research/apply_rebuild_patch.py --state /tmp/st --patch research/out/rebuild_sep1/patch.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

BACKUP_TAG = "pre_rebuild_2026-10-11"


def backup(path: Path) -> None:
    copy = path.with_name(f"{path.stem}.{BACKUP_TAG}{path.suffix}")
    if path.exists() and not copy.exists():
        shutil.copyfile(path, copy)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:   # LF on Windows too
        fh.write(text)
    os.replace(tmp, path)


def patch_jsonl(path: Path, id_key: str, drop, replace) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    drop = set(drop)
    out, dropped, replaced = [], 0, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        rid = str(row.get(id_key))
        if rid in drop:
            dropped += 1
            continue
        if rid in replace:
            new = json.dumps(replace[rid])
            replaced += new != line
            out.append(new)
            continue
        out.append(line)
    if dropped or replaced:
        backup(path)
        write_atomic(path, "\n".join(out) + "\n")
    return dropped, replaced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()
    state = Path(args.state)
    patch = json.loads(Path(args.patch).read_text(encoding="utf-8"))

    for name, part in patch["zone_logs"].items():
        print(name, patch_jsonl(state / name, "trade_id", part["drop"], part["replace"]))
    part = patch["finalized"]
    print("finalized", patch_jsonl(state / "daily_backtest_finalized_records.jsonl", "trade_id",
                                   part["drop"], part["replace"]))
    part = patch["fibtl_records"]
    print("fib/tl records", patch_jsonl(state / "fib_trendline_alert_records.jsonl", "id",
                                        part["drop"], part["replace"]))

    path = state / "fib_trendline_results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    part = patch["fibtl_results"]
    new = {k: v for k, v in results.items() if k not in set(part["drop"])}
    new.update(part["set"])
    if new != results:
        backup(path)
        write_atomic(path, json.dumps(new, indent=1, sort_keys=True))
    print("fib/tl results", len(results), "->", len(new))


if __name__ == "__main__":
    main()
