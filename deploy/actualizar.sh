#!/usr/bin/env bash
# Cada 10 minutos (temporizador de systemd):
#  1. Trae las mejoras desde GitHub y, si cambió el servidor, lo reinicia.
#  2. De lunes a viernes desde las 7:00 (hora de Madrid), genera el informe del día si aún no está hecho.
set -euo pipefail
cd "$(dirname "$0")/.."
DATOS="$HOME/inversiones-datos"
export INFORME_DIR="$DATOS/informe"

# Primera vez: copia los informes anteriores a la carpeta de datos del portátil
if [ ! -d "$INFORME_DIR" ]; then
  mkdir -p "$INFORME_DIR"
  cp -r docs/data/. "$INFORME_DIR/"
  cp data/isin.json "$DATOS/isin.json" 2>/dev/null || true
  NEW_DATA=1
fi

before=$(git rev-parse HEAD)
git pull --ff-only -q
after=$(git rev-parse HEAD)
if [ "${NEW_DATA:-0}" = 1 ] || { [ "$before" != "$after" ] && git diff --name-only "$before" "$after" | grep -qE '^(server/|requirements)'; }; then
  .venv/bin/pip install -q -r requirements-server.txt
  sudo /usr/bin/systemctl restart inversiones-web.service
fi

# ---- informe diario
hoy=$(TZ=Europe/Madrid date +%F)
dia=$(TZ=Europe/Madrid date +%u)
hora=$(TZ=Europe/Madrid date +%H%M)
intentos="$DATOS/intentos-$hoy"
if [ "$dia" -le 5 ] && [ "$hora" -ge 700 ] && [ "$hora" -lt 1300 ] \
   && [ ! -f "$INFORME_DIR/history/$hoy.json" ] && [ "$(cat "$intentos" 2>/dev/null || echo 0)" -lt 4 ]; then
  echo $(( $(cat "$intentos" 2>/dev/null || echo 0) + 1 )) > "$intentos"
  find "$DATOS" -maxdepth 1 -name 'intentos-*' ! -name "intentos-$hoy" -delete 2>/dev/null || true
  # Tema privado de ntfy y otros ajustes (no van en GitHub porque el repositorio es público)
  if [ -f "$DATOS/config.env" ]; then set -a; . "$DATOS/config.env"; set +a; fi
  if [ -z "${APP_URL:-}" ]; then
    APP_URL=$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print("https://" + json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)
    export APP_URL
  fi
  mkdir -p logs
  echo "=== $(date) ===" >> logs/informe.log
  timeout 50m .venv/bin/python screener/run.py --force >> logs/informe.log 2>&1 || echo "El informe falló (se reintenta en 10 min)" >> logs/informe.log
fi
