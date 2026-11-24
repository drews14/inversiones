#!/usr/bin/env bash
# Modelo de oportunidades y riesgo (el de «Mi cartera»), una vez por día laborable.
# Lo lanza cron cada 10 minutos entre las 6:30 y las 13:59 (hora de Madrid); si ya está hecho, en marcha
# o lleva 3 intentos, no hace nada. La descarga de las ~1.500 fichas tarda alrededor de una hora.
# Uso manual: bash modelo/diario.sh --force
set -uo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=python3
DATOS="${DATOS_BASE:-$HOME/inversiones-datos}"; export DATOS_BASE="$DATOS"
export INFORME_DIR="$DATOS/informe"
W="$DATOS/modelo"; mkdir -p "$W" logs
hoy=$(TZ=Europe/Madrid date +%F); dia=$(TZ=Europe/Madrid date +%u); hora=$(TZ=Europe/Madrid date +%H%M)
FORCE=0; [ "${1:-}" = "--force" ] && FORCE=1
if [ $FORCE = 0 ]; then
  [ "$dia" -le 5 ] && [ "$hora" -ge 630 ] && [ "$hora" -lt 1400 ] || exit 0
  [ -f "$W/hecho-$hoy" ] && exit 0
  n=$(cat "$W/intentos-$hoy" 2>/dev/null || echo 0); [ "$n" -lt 3 ] || exit 0
fi
exec 9>"$W/.lock"; flock -n 9 || exit 0          # ya hay uno en marcha
[ $FORCE = 1 ] || echo $(( $(cat "$W/intentos-$hoy" 2>/dev/null || echo 0) + 1 )) > "$W/intentos-$hoy"
find "$W" -maxdepth 1 \( -name 'intentos-*' -o -name 'hecho-*' \) ! -name "*-$hoy" -delete 2>/dev/null || true
exec >>"$REPO/logs/modelo.log" 2>&1
paso() { echo "--- $(date '+%H:%M:%S') $*"; }
echo "=== $(date) modelo $hoy"
set -e
if [ "$dia" = 1 ] || [ ! -f "$W/universo.json" ]; then paso universo; "$PY" modelo/universo.py; fi
paso fichas
"$PY" modelo/fetch3.py "$hoy" || { paso "fichas: más de un 5 % de fallos, reintento"; "$PY" modelo/fetch3.py "$hoy" || true; }
paso bench;    "$PY" modelo/bench.py "$hoy" || true
paso regimen;  REG_FECHA="$hoy" REG_EXTRA="$("$PY" modelo/reg_extra.py)" "$PY" modelo/regimen.py
if [ ! -f "$W/serie_hist.json" ]; then paso "relleno de precios diarios"; "$PY" modelo/serie_relleno.py || true; fi
paso v3;       "$PY" modelo/v3.py "$hoy"
paso simulador; "$PY" modelo/sim_data3.py "$hoy"
paso "cartera del modelo"; "$PY" modelo/cartera_modelo.py "$hoy"
touch "$W/hecho-$hoy"
paso "listo"
