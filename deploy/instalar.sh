#!/usr/bin/env bash
# Instala el servidor de «Oportunidades» en un Linux (Ubuntu/Debian) como servicio que arranca solo.
# Uso (en el portátil):  bash deploy/instalar.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
echo "Instalando en $DIR para el usuario $USER_NAME"

sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git

cd "$DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-server.txt

# Servicio web (arranca con el portátil y se reinicia si falla)
sudo tee /etc/systemd/system/inversiones-web.service >/dev/null <<UNIT
[Unit]
Description=Oportunidades - app y simulador
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# Cada 10 minutos trae de GitHub el informe nuevo y las mejoras de la app
sudo tee /etc/systemd/system/inversiones-actualizar.service >/dev/null <<UNIT
[Unit]
Description=Oportunidades - traer informe y cambios de GitHub

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=/bin/bash $DIR/deploy/actualizar.sh
UNIT
sudo tee /etc/systemd/system/inversiones-actualizar.timer >/dev/null <<UNIT
[Unit]
Description=Oportunidades - actualizar cada 10 minutos

[Timer]
OnBootSec=1min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
UNIT

# Permiso SOLO para reiniciar este servicio sin contraseña (lo usa la actualización automática)
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/systemctl restart inversiones-web.service" | sudo tee /etc/sudoers.d/inversiones >/dev/null
sudo chmod 440 /etc/sudoers.d/inversiones
sudo visudo -cf /etc/sudoers.d/inversiones >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now inversiones-web.service inversiones-actualizar.timer
echo
echo "Listo. La app responde en http://127.0.0.1:8000"
echo "Siguiente paso: crea tu usuario con   .venv/bin/python -m server.admin crear-admin"
