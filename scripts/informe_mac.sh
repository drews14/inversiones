#!/bin/bash
# Genera el informe diario en este Mac y lo publica en GitHub Pages.
# Lo lanza launchd de lunes a viernes a las 7:40 (ver scripts/instalar_mac.sh).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."

# Secretos locales (no se suben a GitHub): NTFY_TOPIC
[ -f .env ] && set -a && . ./.env && set +a
export APP_URL="https://drews14.github.io/inversiones/"

echo "=== $(date '+%F %T') ==="
git pull --rebase --quiet || true
.venv/bin/python -W ignore screener/run.py
git add docs/data
git diff --cached --quiet || git commit --quiet -m "Informe $(date +%F)"
git push --quiet
echo "Publicado"

# El log solo guarda las últimas 500 líneas
tail -n 500 logs/informe.log > logs/informe.tmp 2>/dev/null && mv logs/informe.tmp logs/informe.log || true
