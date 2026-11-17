#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

mkdir -p inbox sorted work
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — fill in DigitalOcean and Spaces credentials for live mode."
fi

echo "Setup complete."
echo "Local UI:  source .venv/bin/activate && ./start.sh"
echo "Pipeline:  place files in ./inbox then python scripts/run_pipeline.py"
echo "Harness:   doctl harness-runtime launch --spec harness/photo-sorter.yaml --prompt \"\$(cat harness/prompts/sort-album.md)\""
