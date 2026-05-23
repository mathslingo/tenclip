#!/usr/bin/env bash
# Install web/ deps and run Vite (default port 5174 in web/vite.config.ts)
SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
cd -- "$SCRIPT_DIR/../web" || exit 1
npm install
exec npm run dev -- --host 127.0.0.1
