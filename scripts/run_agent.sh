#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

exec python -m agent_console.agents.main_agent "$@"
