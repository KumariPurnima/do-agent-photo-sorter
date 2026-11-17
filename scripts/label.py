#!/usr/bin/env python3
"""Label media into category folder ids via DigitalOcean Inference VLMs (or heuristics)."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _paths import WORK, ensure_dirs, folder_ids, load_categories, write_progress  # noqa: E402

INFERENCE_URL = os.environ.get(
    "INFERENCE_URL", "https://inference.do-ai.run/v1/chat/completions"
)
MODEL = os.environ.get(
    "PHOTO_SORTER_VLM_MODEL",
    os.environ.get("HARNESS_INFERENCE_MODEL", "nemotron-3.5-super-vl"),
)
API_KEY = os.environ.get("HARNESS_INFERENCE_API_KEY") or os.environ.get("MODEL_ACCESS_KEY")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def heuristic_label(row: dict, valid: set[str]) -> str:
    name = row["name"].lower()
    if row["kind"] == "video":
        return "videos" if "videos" in valid else "other"
    if "screenshot" in name or name.startswith("screen"):
        return "screenshots" if "screenshots" in valid else "other"
    if "selfie" in name:
        return "selfies" if "selfies" in valid else "other"
    if any(k in name for k in ("food", "dinner", "lunch", "brunch", "coffee")):
        return "food" if "food" in valid else "other"
    if any(k in name for k in ("beach", "mountain", "sunset", "temple", "trail")):
        return "travel" if "travel" in valid else "other"
    return "other" if "other" in valid else next(iter(valid))


def encode_preview(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def vision_label_batch(batch: list[dict], valid: list[str], categories: dict) -> dict[str, str]:
    if not API_KEY:
        return {}

    catalog = "\n".join(
        f"- {f['id']}: {f['name']} — {f['description']}" for f in categories["folders"]
    )
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Classify each image into exactly one folder id from this catalog:\n"
                f"{catalog}\n\n"
                "Reply with JSON only: {\"labels\":[{\"id\":\"m00001\",\"folder\":\"travel\"}, ...]}\n"
                f"Valid folder ids: {', '.join(valid)}"
            ),
        }
    ]
    for row in batch:
        uri = encode_preview(row.get("preview"))
        content.append({"type": "text", "text": f"id={row['id']} name={row['name']}"})
        if uri:
            content.append({"type": "image_url", "image_url": {"url": uri}})

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 800,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(INFERENCE_URL, headers=headers, json=payload)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    data = json.loads(match.group(0))
    out: dict[str, str] = {}
    for item in data.get("labels", []):
        folder = item.get("folder")
        mid = item.get("id")
        if mid and folder in valid:
            out[mid] = folder
    return out


def main() -> int:
    ensure_dirs()
    categories = load_categories()
    valid = folder_ids()
    valid_set = set(valid)

    manifest = load_jsonl(WORK / "manifest.jsonl")
    dupes = {}
    dup_path = WORK / "duplicates.json"
    if dup_path.exists():
        dupes = json.loads(dup_path.read_text())
    duplicate_ids = set(dupes.get("duplicate_ids", []))
    keep_ids = {g["keep"] for g in dupes.get("groups", [])}

    # Only label non-duplicates, plus the canonical keep from each group.
    to_label = [
        r
        for r in manifest
        if r["id"] not in duplicate_ids or r["id"] in keep_ids
    ]

    labels: dict[str, str] = {}
    batch_size = 8
    vision_batches = 0

    for i in range(0, len(to_label), batch_size):
        batch = to_label[i : i + batch_size]
        images = [r for r in batch if r["kind"] == "image" and r.get("preview")]
        mapped = vision_label_batch(images, valid, categories) if images else {}
        if mapped:
            vision_batches += 1
        for row in batch:
            if row["id"] in mapped:
                labels[row["id"]] = mapped[row["id"]]
            else:
                labels[row["id"]] = heuristic_label(row, valid_set)

    # Duplicates go to review folder (except keep, which gets a normal label already).
    review = categories.get("review", {}).get("duplicates", "_Review/duplicates")
    out_path = WORK / "labels.jsonl"
    with out_path.open("w") as f:
        for row in manifest:
            if row["id"] in duplicate_ids and row["id"] not in keep_ids:
                folder = review
            else:
                folder = labels.get(row["id"], heuristic_label(row, valid_set))
            f.write(json.dumps({"id": row["id"], "folder": folder, "rel": row["rel"]}) + "\n")

    write_progress(
        "label",
        labeled=len(manifest),
        vision_batches=vision_batches,
        used_inference=bool(API_KEY),
    )
    print(f"labeled {len(manifest)} files → {out_path} (vision_batches={vision_batches})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
