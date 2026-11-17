"""Shared path helpers for the photo-sorter pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(os.environ.get("PHOTO_SORTER_ROOT", Path(__file__).resolve().parents[1]))
INBOX = Path(os.environ.get("PHOTO_SORTER_INBOX", ROOT / "inbox"))
OUTBOX = Path(os.environ.get("PHOTO_SORTER_OUTBOX", ROOT / "sorted"))
WORK = Path(os.environ.get("PHOTO_SORTER_WORK", ROOT / "work"))
CATEGORIES = ROOT / "categories.json"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".gif", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def ensure_dirs() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "previews").mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)


def load_categories() -> dict:
    with CATEGORIES.open() as f:
        return json.load(f)


def folder_ids() -> list[str]:
    data = load_categories()
    return [f["id"] for f in data["folders"]]


def progress_path() -> Path:
    return WORK / "progress.json"


def write_progress(step: str, **extra) -> None:
    ensure_dirs()
    payload = {"step": step, **extra}
    progress_path().write_text(json.dumps(payload, indent=2))


def is_media(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS
