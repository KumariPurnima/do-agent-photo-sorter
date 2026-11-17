# Agent Photo Sorter

**Built with DigitalOcean AI** — a cloud agent that turns a messy trip album into labeled folders.

Upload photos, launch a [Harness Runtime](https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/) session, and let the agent scan, find duplicates, classify with [Serverless Inference](https://docs.digitalocean.com/products/inference/) vision models, and write sorted copies to [Spaces](https://docs.digitalocean.com/products/spaces/). Pause mid-sort, resume from another device, and approve sensitive actions through [Action Gateway](https://docs.digitalocean.com/products/managed-agents/action-gateway/).

## Product map

| Layer | DigitalOcean product |
| --- | --- |
| Sort agent + pause/resume/checkpoint | **Harness Runtime** (hero) |
| Vision labeling + coding model | **Serverless Inference** |
| Governed tool calls | **Action Gateway** |
| Album storage | **Spaces** |
| Dashboard / API | **App Platform** |

Optional next step: connect [Agent Data Services](https://docs.digitalocean.com/products/agent-data-services/) for ingest-time enrichment when your team has access.

## Quick start (local)

```bash
./setup.sh
source .venv/bin/activate
./start.sh
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). With `DEMO_MODE=true` (default), the UI runs without Spaces or `doctl`.

### Run the pipeline on a folder

```bash
# put media in ./inbox
python scripts/run_pipeline.py
# results in ./sorted and ./work/SUMMARY.md
```

Set `HARNESS_INFERENCE_API_KEY` (and optionally `PHOTO_SORTER_VLM_MODEL`) so `scripts/label.py` uses a vision-language model. Without a key, heuristic labels still produce a full dry-run.

### Launch on Harness Runtime

```bash
export HARNESS_INFERENCE_API_KEY=<model-access-key>
# optional Spaces sync
export SPACES_KEY=... SPACES_SECRET=... SPACES_BUCKET=... SPACES_REGION=nyc3

doctl auth init   # if needed

# Unattended create (what the API uses)
doctl harness-runtime create --spec harness/photo-sorter.yaml \
  --prompt "$(cat harness/prompts/sort-album.md)" \
  --on-hitl approve --interactive=false

# Later: interactive attach / resume
doctl harness-runtime launch <session-name>
```

Optional Action Gateway Toolbelt publish: `pip install pydo && python scripts/create_toolbelt.py`.

Disconnect anytime; the session can idle-suspend and be resumed later. See the [Harness Runtime quickstart](https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/).

## Repository layout

```text
apps/
  api/                 FastAPI control plane (albums, presign, sort jobs)
  web/                 Dashboard UI
harness/
  photo-sorter.yaml    Harness Runtime environment spec
  prompts/             Default sort prompt
  skills/              Agent playbook
scripts/               scan → dupes → label → apply → Spaces sync
infra/app-spec.yaml    App Platform blueprint
categories.json        Editable folder taxonomy
```

## Password protection

Set `APP_USERNAME` / `APP_PASSWORD` to enable HTTP Basic Auth on the site. `/api/health` stays open for App Platform health checks. Locally, leave `APP_PASSWORD` empty to skip the login prompt.

## Live mode checklist

1. Create a private Spaces bucket and Spaces access keys.
2. Create a Serverless Inference model access key.
3. Install and authenticate `doctl` with Harness Runtime access.
4. Copy `.env.example` → `.env` and set:
   - `DEMO_MODE=false`
   - `DIGITALOCEAN_TOKEN`
   - `HARNESS_INFERENCE_API_KEY`
   - Spaces variables
5. Deploy with App Platform using `infra/app-spec.yaml`, or keep running `./start.sh` locally.

## Customize folders

Edit `categories.json` — each entry needs an `id`, display `name`, and short `description` the vision model uses when labeling.

## Security notes

- Originals are read-only; the pipeline copies into `sorted/` (and Spaces `…/sorted/`).
- Spaces objects are private; the API serves short-lived signed GET URLs.
- Harness permissions deny destructive `rm -rf` patterns; shell defaults are still reviewable in the environment spec.
- Action Gateway is enabled via `tools: [do.actions]` — tighten with a Toolbelt and allow/ask/deny rules before production.

## License

MIT — see `LICENSE`.
