# Architecture

Agent Photo Sorter is a DigitalOcean AI reference app. **Harness Runtime** is the product centerpiece: each album sort is an isolated microVM session that can pause, resume, checkpoint, and fork.

```text
Browser (App Platform UI)
    │  create album + presigned PUT
    ▼
Spaces  albums/<id>/inbox/…
    │
    │  API starts Harness session
    ▼
Harness Runtime (claude-code)
    │  pull inbox → run scripts → write sorted/
    │  Inference VLMs for labels
    │  Action Gateway for governed tools
    ▼
Spaces  albums/<id>/sorted/… + work artifacts
    │
    ▼
Dashboard lists folders via signed URLs
```

## Why Harness Runtime

- Long-running album sorts should not depend on a laptop staying awake.
- Session lifecycle (idle suspend, resume, checkpoint) maps cleanly to “start sort → leave → come back”.
- The same environment config can spawn one session per tenant/album.
- Model traffic bills through DigitalOcean Serverless Inference via `HARNESS_INFERENCE_*`.

## Control plane vs agent plane

| Plane | Responsibility |
| --- | --- |
| App Platform API/UI | Auth UX, album IDs, presign, job records, browse sorted output |
| Harness session | Scan, hash, dedupe, vision label, copy into folders, Spaces sync |
| Action Gateway | Optional governed connectors (notify, tickets, custom MCP) |

## Extension ideas

- Persistent workspaces so album files survive session teardown.
- Webhook trigger when new objects land in Spaces.
- ADS multimodal ingest for catalog search across all albums.
- Fork a checkpoint to A/B test alternate `categories.json` schemes.
