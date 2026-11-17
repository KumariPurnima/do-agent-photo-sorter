# Photo sort skill

## Inputs
- Inbox: `$PHOTO_SORTER_INBOX` (or `./inbox`)
- Categories: `categories.json`
- Work dir: `$PHOTO_SORTER_WORK` (or `./work`)

## Pipeline
| Step | Script | Output |
|------|--------|--------|
| Scan | `scripts/scan.py` | `work/manifest.jsonl`, `work/previews/` |
| Dupes | `scripts/dupes.py` | `work/duplicates.json` |
| Label | `scripts/label.py` | `work/labels.jsonl` |
| Apply | `scripts/apply.py` | `$PHOTO_SORTER_OUTBOX/<folder>/…`, CSVs |
| Sync | `scripts/sync_spaces.py` | Spaces mirror (optional) |

## Labeling rules
- Prefer folder `id` values from `categories.json`.
- Videos → `videos` unless clearly a screenshot recording of a UI.
- Near-duplicates and exact duplicates → `_Review/duplicates`; keep the highest-resolution / earliest file as canonical in `duplicates.json`.
- Uncertain → `other`.

## Vision labeling
`scripts/label.py` calls DigitalOcean Serverless Inference multimodal chat completions when `HARNESS_INFERENCE_API_KEY` (or `MODEL_ACCESS_KEY`) is set. It batches small JPEG previews and asks for a single folder id per file.

Fallback without a key: heuristic labels from EXIF / filename / media type so local demos still run.

## Safety
- Read originals only; write copies under outbox/work.
- Deny destructive shell (`rm -rf` of roots).
- Keep a resumeable `work/progress.json`.
