"""Carpetas del modelo en el portátil (antes /home/claude/op y /home/claude/cartera/datos).
H     = carpeta de trabajo: fichas, archivo diario, estados (no se publica).
DATOS = lo que lee la app, servido en /data/modelo/ (senales/, modelo.json, oportunidades.json...)."""
import os
_BASE = os.path.expanduser(os.environ.get("DATOS_BASE") or "~/inversiones-datos")
H = os.environ.get("MODELO_DIR") or os.path.join(_BASE, "modelo")
DATOS = os.environ.get("MODELO_DATOS") or os.path.join(os.environ.get("INFORME_DIR") or os.path.join(_BASE, "informe"), "modelo")
os.makedirs(H, exist_ok=True)
os.makedirs(os.path.join(DATOS, "senales"), exist_ok=True)
os.chdir(H)
