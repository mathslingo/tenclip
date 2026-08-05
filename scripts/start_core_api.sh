#!/usr/bin/env bash
# Install Core API deps and run Uvicorn on 127.0.0.1:8000
SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
cd -- "$SCRIPT_DIR/.." || exit 1
python3 -m pip install -r requirements-subproject-core-api.txt
exec python3 -m uvicorn subprojects.core_api.app:app --host 127.0.0.1 --port 8000
