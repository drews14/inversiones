# Oportunidades de compra · informe diario

Web app para iPhone que cada día laborable, a las 8:00 (hora de Madrid), analiza unas 780 empresas
(S&P 500 + Nasdaq 100, IBEX 35 y Nikkei 225), las puntúa de 0 a 100 y te envía una notificación con las mejores.

> Es un filtro automático basado en tus criterios, **no una recomendación de inversión**.

## Cómo puntúa (0-100)

| Bloque (25 pts c/u) | Qué mira |
|---|---|
| Valoración | PER frente a la mediana de su sector, PEG y rentabilidad por flujo de caja libre (FCF yield) |
| Sobreventa técnica | RSI 14, caída desde máximos de 52 semanas y distancia a la media de 200 sesiones |
| Calidad / fiabilidad | ROE, deuda/patrimonio (no se aplica a bancos), margen neto y crecimiento del beneficio |
| Analistas | Potencial hasta el precio objetivo medio, consenso y número de analistas |

- Prioridad de mercado al ordenar: EE. UU. ×1,00 · España ×0,92 · Japón ×0,88.
- Alertas: «cuchillo cayendo», trampa de valor, deuda alta, pérdidas y resultados próximos.
- Macro: IPC general y subyacente de EE. UU., PCE, Fed, paro, curva 10a-2a, IPC de la zona euro, BCE, bono español y prima de riesgo, índices, VIX, dólar, petróleo y oro.
- Termómetro propio (0-100): % del S&P 500 por encima de sus medias de 50 y 200 sesiones, combinado con el VIX.
- Noticias: Google News (por empresa y de mercado).

Todo se ajusta en [`screener/config.py`](screener/config.py).

## Puesta en marcha (una sola vez, unos 10 minutos)

1. **Crea un repositorio en GitHub**, por ejemplo `inversiones`. Tiene que ser *público* para usar GitHub Pages gratis.
2. **Sube esta carpeta** al repositorio:
   ```bash
   cd ~/Documents/inversiones
   git init -b main && git add . && git commit -m "Primera versión"
   git remote add origin https://github.com/TU_USUARIO/inversiones.git
   git push -u origin main
   ```
3. **Activa GitHub Pages**: Settings → Pages → *Deploy from a branch* → `main` / carpeta `/docs`.
   La app quedará en `https://TU_USUARIO.github.io/inversiones/`.
4. **Notificaciones**:
   - Instala **ntfy** desde la App Store y suscríbete al canal que te he dado (`NTFY_TOPIC`).
     Trátalo como una contraseña: cualquiera que conozca el nombre puede leer los avisos.
   - En GitHub: Settings → Secrets and variables → Actions → *New repository secret*.
     Nombre `NTFY_TOPIC`, valor: el nombre del canal.
5. **Pruébalo**: Actions → *Informe diario* → *Run workflow*. En unos 4 minutos te llega la notificación.
6. **En el iPhone**: abre la URL en Safari → Compartir → *Añadir a pantalla de inicio*.

## Uso local

```bash
.venv/bin/python screener/run.py --no-notify   # genera docs/data/report.json
.venv/bin/python -m http.server 8765 --directory docs
```

## Ejecución desde el Mac (modo actual)

Las Actions de GitHub están bloqueadas en la cuenta, así que el informe lo genera el Mac:

- Tarea de launchd: `~/Library/LaunchAgents/com.inversiones.informe.plist`, de lunes a viernes a las 7:40.
- Se ejecuta desde una copia fuera de Documentos (`~/.inversiones-informe`), porque macOS bloquea que las tareas programadas accedan a Documentos.
- Registro: `~/.inversiones-informe/logs/informe.log`.
- Lanzarlo a mano: `launchctl kickstart gui/$(id -u)/com.inversiones.informe`
- Desactivarlo: `launchctl bootout gui/$(id -u)/com.inversiones.informe`
- Si cambias el código en Documentos, haz `git push`; la copia del Mac hace `git pull` antes de cada informe.
- Para volver a la nube cuando GitHub desbloquee la cuenta: `gh workflow enable "Informe diario"` y desactiva la tarea del Mac.
