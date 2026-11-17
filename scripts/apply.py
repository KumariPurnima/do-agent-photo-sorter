#!/usr/bin/env python3
"""Copy inbox files into sorted folders from labels; write CSV summaries."""

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _paths import OUTBOX, WORK, ensure_dirs, load_categories, write_progress  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def folder_name_map() -> dict[str, str]:
    data = load_categories()
    mapping = {f["id"]: f["name"] for f in data["folders"]}
    mapping["_Review/duplicates"] = data.get("review", {}).get("duplicates", "_Review/duplicates")
    return mapping


def main() -> int:
    ensure_dirs()
    manifest = {r["id"]: r for r in load_jsonl(WORK / "manifest.jsonl")}
    labels = load_jsonl(WORK / "labels.jsonl")
    names = folder_name_map()
    counts: Counter[str] = Counter()

    sorted_csv = WORK / "sorted.csv"
    with sorted_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "source", "folder", "dest"])
        writer.writeheader()
        for lab in labels:
            row = manifest[lab["id"]]
            folder_key = lab["folder"]
            folder_dir = names.get(folder_key, folder_key)
            dest_dir = OUTBOX / folder_dir
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / row["name"]
            # Avoid collisions
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                n = 2
                while True:
                    candidate = dest_dir / f"{stem}_{n}{suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    n += 1
            shutil.copy2(row["path"], dest)
            counts[folder_dir] += 1
            writer.writerow(
                {
                    "id": row["id"],
                    "source": row["rel"],
                    "folder": folder_dir,
                    "dest": str(dest.relative_to(OUTBOX)),
                }
            )

    dupes = WORK / "duplicates.json"
    dup_csv = WORK / "duplicates.csv"
    if dupes.exists():
        data = json.loads(dupes.read_text())
        with dup_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["group", "type", "keep", "member"])
            writer.writeheader()
            for g in data.get("groups", []):
                for member in g["members"]:
                    writer.writerow(
                        {
                            "group": g["id"],
                            "type": g["type"],
                            "keep": g["keep"],
                            "member": member,
                        }
                    )

    summary_lines = ["# Sort summary", "", "| Folder | Count |", "|---|---|"]
    for folder, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        summary_lines.append(f"| {folder} | {count} |")
    summary_lines += ["", f"Total files: {sum(counts.values())}", ""]
    (WORK / "SUMMARY.md").write_text("\n".join(summary_lines))

    write_progress("apply", folders=dict(counts), outbox=str(OUTBOX))
    print(f"copied {sum(counts.values())} files → {OUTBOX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
