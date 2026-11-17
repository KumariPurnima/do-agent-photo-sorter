#!/usr/bin/env python3
"""Publish the photo-sorter Action Gateway Toolbelt (optional)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "harness" / "toolbelt.photo-sorter.json"


def main() -> int:
    token = os.environ.get("DIGITALOCEAN_TOKEN") or os.environ.get("DIGITALOCEAN_ACCESS_TOKEN")
    if not token:
        print("Set DIGITALOCEAN_TOKEN first", file=sys.stderr)
        return 1

    try:
        from pydo.action_gateway import ActionGatewayClient
    except ImportError:
        print("Install pydo first: pip install pydo", file=sys.stderr)
        return 1

    payload = json.loads(SPEC.read_text())
    client = ActionGatewayClient(token=token)
    toolbelt = client.create_toolbelt(name=payload["name"], tools=payload["tools"])
    ref = getattr(toolbelt, "ref", None) or getattr(toolbelt, "reference", None) or toolbelt
    print(f"Created Toolbelt: {ref}")
    print('Update harness/photo-sorter.yaml tools to: do.actions: ["toolbelt:photo-sorter@v1"]')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
