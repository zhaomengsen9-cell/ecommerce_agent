#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

python_bin="python"

"$python_bin" -m compileall agent_console
"$python_bin" scripts/check_dependencies.py
"$python_bin" scripts/smoke_check.py
