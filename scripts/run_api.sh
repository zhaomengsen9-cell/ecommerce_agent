#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

exec uvicorn ecommerce_agent.backend.main:app --host 0.0.0.0 --port 8000 --reload
