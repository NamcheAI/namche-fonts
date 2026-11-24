#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [[ -n "${PYTHON:-}" ]]; then
    exec "$PYTHON" scripts/build_googlefonts.py "$@"
fi

build_env=$(mktemp -d)
trap 'rm -rf "$build_env"' EXIT
python3 -m venv "$build_env"
"$build_env/bin/python" -m pip install -r requirements-open-build.txt
"$build_env/bin/python" scripts/build_googlefonts.py "$@"
