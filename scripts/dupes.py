#!/usr/bin/env python3
"""Group exact and near-duplicate media from the scan manifest."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _paths import WORK, ensure_dirs, write_progress  # noqa: E402


def load_manifest() -> list[dict]:
    path = WORK / "manifest.jsonl"
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def hamming(a: str, b: str) -> int:
    return sum(ch1 != ch2 for ch1, ch2 in zip(a, b))


def main() -> int:
    ensure_dirs()
    rows = load_manifest()

    by_sha: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_sha[row["sha256"]].append(row)

    groups = []
    gid = 1
    seen = set()

    for sha, members in by_sha.items():
        if len(members) < 2:
            continue
        keep = sorted(members, key=lambda m: (-m["size"], m["rel"]))[0]
        groups.append(
            {
                "id": f"d{gid:04d}",
                "type": "exact",
                "keep": keep["id"],
                "members": [m["id"] for m in members],
            }
        )
        seen.update(m["id"] for m in members)
        gid += 1

    # Near-dupes via phash (images only)
    hashed = [r for r in rows if r.get("phash") and r["id"] not in seen]
    used = set()
    for i, a in enumerate(hashed):
        if a["id"] in used:
            continue
        cluster = [a]
        for b in hashed[i + 1 :]:
            if b["id"] in used:
                continue
            # Strict threshold: solid-color / tiny previews collide easily at higher distances.
            if hamming(a["phash"], b["phash"]) <= 3:
                cluster.append(b)
        if len(cluster) > 1:
            keep = sorted(cluster, key=lambda m: (-m["size"], m["rel"]))[0]
            groups.append(
                {
                    "id": f"d{gid:04d}",
                    "type": "near",
                    "keep": keep["id"],
                    "members": [m["id"] for m in cluster],
                }
            )
            used.update(m["id"] for m in cluster)
            seen.update(m["id"] for m in cluster)
            gid += 1

    out = WORK / "duplicates.json"
    payload = {"groups": groups, "duplicate_ids": sorted(seen)}
    out.write_text(json.dumps(payload, indent=2))
    write_progress("dupes", groups=len(groups), duplicate_files=len(seen))
    print(f"found {len(groups)} duplicate groups → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
