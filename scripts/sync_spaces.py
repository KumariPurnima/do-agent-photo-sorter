#!/usr/bin/env python3
"""Mirror sorted/ and work CSV artifacts to DigitalOcean Spaces."""

from __future__ import annotations

import mimetypes
import os
import sys
from pathlib import Path

import boto3
from botocore.client import Config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _paths import OUTBOX, WORK, write_progress  # noqa: E402


def client():
    key = os.environ.get("SPACES_KEY")
    secret = os.environ.get("SPACES_SECRET")
    region = os.environ.get("SPACES_REGION", "nyc3")
    endpoint = os.environ.get(
        "SPACES_ENDPOINT", f"https://{region}.digitaloceanspaces.com"
    )
    if not key or not secret:
        raise SystemExit("SPACES_KEY and SPACES_SECRET are required for sync")
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )


def upload_tree(s3, bucket: str, prefix: str, local: Path) -> int:
    count = 0
    if not local.exists():
        return 0
    for path in local.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local).as_posix()
        key = f"{prefix.rstrip('/')}/{rel}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"},
        )
        count += 1
    return count


def main() -> int:
    bucket = os.environ.get("SPACES_BUCKET")
    prefix = os.environ.get("SPACES_PREFIX", "albums/default")
    if not bucket:
        raise SystemExit("SPACES_BUCKET is required")

    s3 = client()
    sorted_count = upload_tree(s3, bucket, f"{prefix}/sorted", OUTBOX)
    artifact_count = 0
    for name in ("sorted.csv", "duplicates.csv", "SUMMARY.md", "progress.json"):
        path = WORK / name
        if path.exists():
            s3.upload_file(
                str(path),
                bucket,
                f"{prefix}/work/{name}",
                ExtraArgs={"ACL": "private"},
            )
            artifact_count += 1

    write_progress(
        "sync_spaces",
        bucket=bucket,
        prefix=prefix,
        sorted_objects=sorted_count,
        artifacts=artifact_count,
    )
    print(f"synced {sorted_count} sorted files + {artifact_count} artifacts to s3://{bucket}/{prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
