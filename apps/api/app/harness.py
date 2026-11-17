from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings, get_settings


@dataclass
class SortJob:
    id: str
    album_id: str
    status: str
    session_name: str
    created_at: str
    prompt: str
    message: str = ""
    doctl: bool = False
    session_id: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)


JOBS: dict[str, SortJob] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _doctl_env(settings: Settings, album_id: str) -> dict[str, str]:
    return {
        **os.environ,
        "DIGITALOCEAN_ACCESS_TOKEN": settings.digitalocean_token,
        "DIGITALOCEAN_TOKEN": settings.digitalocean_token,
        "HARNESS_INFERENCE_API_KEY": settings.harness_inference_api_key,
        "SPACES_KEY": settings.spaces_key,
        "SPACES_SECRET": settings.spaces_secret,
        "SPACES_BUCKET": settings.spaces_bucket,
        "SPACES_REGION": settings.spaces_region,
        "SPACES_ENDPOINT": settings.spaces_endpoint
        or f"https://{settings.spaces_region}.digitaloceanspaces.com",
        "SPACES_PREFIX": f"albums/{album_id}",
    }


def _run_doctl(
    settings: Settings,
    args: list[str],
    *,
    album_id: str = "default",
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    doctl = shutil.which(settings.doctl_bin)
    if not doctl:
        raise RuntimeError("doctl not found on PATH")
    return subprocess.run(
        [doctl, *args],
        capture_output=True,
        text=True,
        env=_doctl_env(settings, album_id),
        timeout=timeout,
    )


def create_job(album_id: str, custom_prompt: str | None = None) -> SortJob:
    settings = get_settings()
    job_id = uuid.uuid4().hex[:10]
    session_name = f"photo-sort-{album_id}-{job_id}"
    prompt_path = _repo_root() / "harness" / "prompts" / "sort-album.md"
    base_prompt = prompt_path.read_text() if prompt_path.exists() else "Sort the album."
    prompt = custom_prompt or (
        base_prompt
        + f"\n\nAlbum id: {album_id}\n"
        + f"Spaces prefix: albums/{album_id}\n"
        + "Sync inbox from Spaces into $PHOTO_SORTER_INBOX if the local inbox is empty, "
        + "then run the pipeline and sync sorted output back."
    )
    job = SortJob(
        id=job_id,
        album_id=album_id,
        status="queued",
        session_name=session_name,
        created_at=_now(),
        prompt=prompt,
        message="Job created",
    )
    JOBS[job_id] = job

    if settings.demo_mode or not settings.digitalocean_token:
        job.status = "running"
        job.message = (
            "Demo mode: Harness session simulated. "
            "Set DIGITALOCEAN_TOKEN and DEMO_MODE=false to launch a real session with doctl."
        )
        job.events.append({"at": _now(), "type": "demo", "text": job.message})
        return job

    launched = _create_session(settings, session_name, prompt, album_id)
    job.doctl = launched["ok"]
    job.status = "running" if launched["ok"] else "error"
    job.message = launched["message"]
    job.session_id = launched.get("session_id", "")
    job.events.append({"at": _now(), "type": "launch", "text": job.message})
    return job


def _create_session(
    settings: Settings, session_name: str, prompt: str, album_id: str
) -> dict[str, Any]:
    spec = _repo_root() / settings.harness_spec_path
    if not spec.exists():
        return {"ok": False, "message": f"Missing harness spec: {spec}"}

    args = [
        "harness-runtime",
        "create",
        "--spec",
        str(spec),
        "--name",
        session_name,
        "--prompt",
        prompt,
        "--on-hitl",
        "approve",
        "--interactive=false",
        "--resume-on-topoff",
        "-o",
        "json",
    ]
    # Fill secret slots from env without baking values into the checked-in YAML.
    if settings.harness_inference_api_key:
        args.extend(["--secret", f"HARNESS_INFERENCE_API_KEY={settings.harness_inference_api_key}"])
    if settings.spaces_key:
        args.extend(["--secret", f"SPACES_KEY={settings.spaces_key}"])
    if settings.spaces_secret:
        args.extend(["--secret", f"SPACES_SECRET={settings.spaces_secret}"])

    try:
        proc = _run_doctl(settings, args, album_id=album_id, timeout=360)
    except FileNotFoundError:
        return {"ok": False, "message": "doctl not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "doctl create timed out"}
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}

    if proc.returncode != 0:
        return {
            "ok": False,
            "message": proc.stderr.strip() or proc.stdout.strip() or "doctl create failed",
        }

    session_id = ""
    message = proc.stdout.strip() or f"Created session {session_name}"
    try:
        payload = json.loads(proc.stdout)
        if isinstance(payload, dict):
            session_id = str(
                payload.get("id")
                or payload.get("session_id")
                or payload.get("SessionID")
                or payload.get("sessionId")
                or ""
            )
            message = (
                payload.get("status")
                and f"Session {session_name} status={payload.get('status')} id={session_id or 'n/a'}"
            ) or message
        elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
            session_id = str(payload[0].get("id") or payload[0].get("session_id") or "")
    except json.JSONDecodeError:
        pass

    return {"ok": True, "message": message, "session_id": session_id}


def refresh_job(job_id: str) -> SortJob | None:
    job = JOBS.get(job_id)
    if not job:
        return None
    settings = get_settings()
    if settings.demo_mode or not settings.digitalocean_token or not job.doctl:
        return job

    target = job.session_id or job.session_name
    try:
        proc = _run_doctl(
            settings,
            ["harness-runtime", "show", target, "-o", "json"],
            album_id=job.album_id,
            timeout=60,
        )
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        job.message = str(exc)
        job.events.append({"at": _now(), "type": "poll_error", "text": job.message})
        return job

    if proc.returncode != 0:
        job.message = proc.stderr.strip() or proc.stdout.strip() or "show failed"
        job.events.append({"at": _now(), "type": "poll_error", "text": job.message})
        return job

    try:
        payload = json.loads(proc.stdout)
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        status = str(
            payload.get("status")
            or payload.get("State")
            or payload.get("state")
            or job.status
        ).lower()
        if payload.get("id") and not job.session_id:
            job.session_id = str(payload["id"])
        job.status = status
        job.message = f"Harness session {target}: {status}"
        job.events.append({"at": _now(), "type": "poll", "text": job.message})
    except json.JSONDecodeError:
        job.message = proc.stdout.strip()[:500]
    return job


def get_job(job_id: str) -> SortJob | None:
    return JOBS.get(job_id)


def list_jobs() -> list[dict]:
    return [asdict(j) for j in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)]


def job_status_payload(job: SortJob) -> dict:
    return asdict(job)
