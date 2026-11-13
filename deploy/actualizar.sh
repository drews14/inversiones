#!/usr/bin/env bash
# Trae el informe diario y las mejoras desde GitHub. Si cambió el código del servidor, lo reinicia.
set -euo pipefail
cd "$(dirname "$0")/.."
before=$(git rev-parse HEAD)
git pull --ff-only -q
after=$(git rev-parse HEAD)
if [ "$before" != "$after" ] && git diff --name-only "$before" "$after" | grep -qE '^(server/|requirements)'; then
  .venv/bin/pip install -q -r requirements-server.txt
  sudo /usr/bin/systemctl restart inversiones-web.service
fi
