#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
exec uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8080 --reload
