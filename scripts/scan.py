#!/usr/bin/env python3
"""Scan inbox media, write manifest + JPEG previews + perceptual hashes."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _paths import INBOX, WORK, ensure_dirs, is_media, is_video, write_progress  # noqa: E402

try:
    import imagehash
except ImportError:  # pragma: no cover
    imagehash = None


def file_sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def make_preview(src: Path, dest: Path, max_size: int = 512) -> bool:
    if is_video(src):
        return False
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((max_size, max_size))
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest, format="JPEG", quality=85)
            return True
    except (UnidentifiedImageError, OSError):
        return False


def perceptual_hash(preview: Path | None, original: Path) -> str | None:
    if imagehash is None:
        return None
    target = preview if preview and preview.exists() else original
    if is_video(original) and (preview is None or not preview.exists()):
        return None
    try:
        with Image.open(target) as im:
            return str(imagehash.phash(im))
    except (UnidentifiedImageError, OSError):
        return None


def main() -> int:
    ensure_dirs()
    manifest = WORK / "manifest.jsonl"
    rows = []
    files = sorted(p for p in INBOX.rglob("*") if p.is_file() and is_media(p))

    for idx, path in enumerate(files, start=1):
        rel = path.relative_to(INBOX).as_posix()
        preview = WORK / "previews" / f"{idx:05d}.jpg"
        has_preview = make_preview(path, preview)
        row = {
            "id": f"m{idx:05d}",
            "path": str(path),
            "rel": rel,
            "name": path.name,
            "ext": path.suffix.lower(),
            "size": path.stat().st_size,
            "sha256": file_sha256(path),
            "kind": "video" if is_video(path) else "image",
            "preview": str(preview) if has_preview else None,
            "phash": perceptual_hash(preview if has_preview else None, path),
        }
        rows.append(row)

    with manifest.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    write_progress("scan", files=len(rows), manifest=str(manifest))
    print(f"scanned {len(rows)} files → {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
