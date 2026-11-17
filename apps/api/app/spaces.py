from __future__ import annotations

import mimetypes
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config

from .config import get_settings


@lru_cache
def _s3(settings_key: str):
    settings = get_settings()
    endpoint = settings.spaces_endpoint or f"https://{settings.spaces_region}.digitaloceanspaces.com"
    return boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=endpoint,
        aws_access_key_id=settings.spaces_key,
        aws_secret_access_key=settings.spaces_secret,
        config=Config(signature_version="s3v4"),
    )


def s3_client():
    settings = get_settings()
    return _s3(f"{settings.spaces_region}:{settings.spaces_key}:{settings.spaces_endpoint}")


def album_prefix(album_id: str) -> str:
    return f"albums/{album_id}"


def create_album_id() -> str:
    return uuid.uuid4().hex[:12]


def presign_upload(album_id: str, filename: str, content_type: str | None = None) -> dict:
    settings = get_settings()
    if not settings.spaces_bucket or not settings.spaces_key:
        raise RuntimeError("Spaces is not configured")
    key = f"{album_prefix(album_id)}/inbox/{filename}"
    ctype = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    url = s3_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.spaces_bucket,
            "Key": key,
            "ContentType": ctype,
            "ACL": "private",
        },
        ExpiresIn=3600,
    )
    return {"upload_url": url, "key": key, "content_type": ctype}


def list_sorted(album_id: str) -> list[dict]:
    settings = get_settings()
    if not settings.spaces_bucket or not settings.spaces_key:
        return []
    prefix = f"{album_prefix(album_id)}/sorted/"
    paginator = s3_client().get_paginator("list_objects_v2")
    items: list[dict] = []
    for page in paginator.paginate(Bucket=settings.spaces_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel = key[len(prefix) :]
            if not rel or rel.endswith("/"):
                continue
            folder = rel.split("/", 1)[0] if "/" in rel else "Other"
            items.append({"key": key, "rel": rel, "folder": folder, "size": obj["Size"]})
    return items


def presign_get(key: str, expires: int = 3600) -> str:
    settings = get_settings()
    return s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.spaces_bucket, "Key": key},
        ExpiresIn=expires,
    )
