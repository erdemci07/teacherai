#!/usr/bin/env sh
set -eu

VENV_DIR="${TEACHERAI_API_VENV:-.venv}"
PYTHON_BIN="${PYTHON:-python3}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -q -r apps/api/requirements.txt
exec "$VENV_DIR/bin/python" -m uvicorn apps.api.app.main:app --reload --host 0.0.0.0 --port 8000
