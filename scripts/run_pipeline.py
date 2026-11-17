#!/usr/bin/env python3
"""Run the full local sort pipeline in order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ["scan.py", "dupes.py", "label.py", "apply.py"]


def main() -> int:
    for step in STEPS:
        print(f"\n=== {step} ===")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / step)], cwd=ROOT)
        if proc.returncode != 0:
            return proc.returncode
    if all(os_key in __import__("os").environ for os_key in ("SPACES_KEY", "SPACES_SECRET", "SPACES_BUCKET")):
        print("\n=== sync_spaces.py ===")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_spaces.py")], cwd=ROOT)
        if proc.returncode != 0:
            return proc.returncode
    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
