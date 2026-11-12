"use strict";

const FLAG = { US: "🇺🇸", ES: "🇪🇸", JP: "🇯🇵" };
const BLOCK_LABEL = { valuation: "Valoración", technical: "Sobreventa técnica", quality: "Calidad / fiabilidad", analysts: "Consenso analistas" };
const TIMING = {
  giro: { text: "Señal de giro", cls: "t-giro", help: "Hay señales de que la caída se está frenando." },
  vigilar: { text: "Vigilar", cls: "t-vigilar", help: "Señales mixtas: buena candidata, pero aún sin confirmación clara." },
  esperar: { text: "Esperar", cls: "t-esperar", help: "La caída todavía no muestra señales de frenar." },
};
const timingPill = (t) => (t && TIMING[t.label] ? `<span class="tpill ${TIMING[t.label].cls}">${TIMING[t.label].text}</span>` : "");
const REC = { strong_buy: "Compra fuerte", buy: "Comprar", hold: "Mantener", underperform: "Infraponderar", sell: "Vender", none: "—" };

// La app de Trade Republic no tiene enlaces directos públicos: copiamos el ISIN y abrimos la App Store,
// donde el botón «Abrir» lanza la app; allí basta con pegar el ISIN en el buscador.
const TR_APPSTORE = "https://apps.apple.com/es/app/id1410703839";
const trButton = (isin) => `<button class="btn primary" data-tr="${esc(isin)}">Copiar ISIN y abrir Trade Republic</button>
  <p class="tr-help">Se copia el código de la empresa. En la pantalla que se abre pulsa <b>Abrir</b> y, dentro de Trade Republic, pega el código en el buscador 🔍.</p>`;

function toast(msg) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2500);
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-tr]");
  if (!b) return;
  e.preventDefault();
  try { await navigator.clipboard.writeText(b.dataset.tr); toast(`ISIN ${b.dataset.tr} copiado`); } catch {}
  setTimeout(() => { window.location.href = TR_APPSTORE; }, 350);
});

let report = null;
let viewingDate = null; // null = informe de hoy
let marketSel = "US";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v, d = 1) => (v == null ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
const cls = (v) => (v == null ? "" : v >= 0 ? "up" : "down");
const fmt = (v, d = 2) => (v == null ? "—" : Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d }));
const money = (v, cur) => (v == null ? "—" : `${fmt(v, v >= 1000 ? 0 : 2)} ${cur === "USD" ? "$" : cur === "EUR" ? "€" : cur === "JPY" ? "¥" : cur || ""}`);

async function load(date) {
  const url = date ? `data/history/${date}.json` : "data/report.json";
  const res = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(res.status);
  return res.json();
}

function spark(values, { w = 300, h = 64, color } = {}) {
  const v = (values || []).filter((x) => x != null);
  if (v.length < 2) return "";
  const min = Math.min(...v), max = Math.max(...v), r = max - min || 1;
  const pts = v.map((y, i) => `${((i / (v.length - 1)) * w).toFixed(1)},${(h - 4 - ((y - min) / r) * (h - 8)).toFixed(1)}`).join(" ");
  const c = color || (v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${c}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
}

function oppRow(o, i) {
  const chips = (o.reasons || []).slice(0, 2).map((r) => `<span class="chip">${esc(r)}</span>`).join("")
    + (o.flags || []).slice(0, 1).map((f) => `<span class="chip warn">⚠ ${esc(f)}</span>`).join("");
  return `<button class="opp" data-i="${i}">
    <div class="ring" style="--p:${o.score}"><span class="num">${Math.round(o.score)}</span></div>
    <div class="opp-main">
      <div class="opp-head">
        <div style="min-width:0">
          <div class="opp-tk">${FLAG[o.market] || ""} ${esc(o.ticker)} ${timingPill(o.timing)}</div>
          <div class="opp-name">${esc(o.name)}</div>
        </div>
        <div class="opp-price num">${money(o.price, o.currency)}<br><span class="${cls(o.chg1d)}">${pct(o.chg1d)}</span></div>
      </div>
      <div class="chips">${chips}</div>
    </div>
  </button>`;
}

let currentList = [];
function bindOpps(container, list) {
  container.querySelectorAll(".opp").forEach((b) => b.addEventListener("click", () => openDetail(list[+b.dataset.i])));
}

function renderHoy() {
  const r = report, s = r.sentiment;
  const el = $("#tab-hoy");
  let html = "";
  if (s) {
    html += `<h2>Termómetro del mercado ${infoBtn("sentiment")}</h2><div class="card">
      <div class="gauge"><div class="gauge-value num">${s.value}</div>
        <div style="flex:1"><div style="font-weight:600;margin-bottom:8px">${esc(s.label)}</div>
        <div class="gauge-bar"><div class="gauge-dot" style="left:${s.value}%"></div></div></div></div>
      <div class="gauge-meta muted"><span>S&amp;P &gt; MM200: ${fmt(s.above200, 0)}%</span><span>&gt; MM50: ${fmt(s.above50, 0)}%</span><span>VIX ${fmt(s.vix, 1)}</span></div>
      <div class="muted" style="font-size:12px;margin-top:8px">${esc(s.note)}</div></div>`;
  }
  const top5 = r.top.slice(0, 5);
  html += `<h2>Las 5 mejores de hoy ${infoBtn("score")}</h2>`;
  html += top5.length ? `<div class="list" id="top-list">${top5.map(oppRow).join("")}</div>`
    : `<div class="card empty">Hoy ninguna empresa supera el umbral mínimo.</div>`;
  html += `<p class="disclaimer">Analizadas ${r.analyzed} de ${r.universe_size} empresas · ${r.candidates} superan el umbral.
    Esto es un filtro automático según tus criterios, no una recomendación de inversión. Revisa siempre cada empresa antes de decidir.</p>`;
  el.innerHTML = html;
  const list = $("#top-list");
  if (list) bindOpps(list, top5);
}

function renderMercados() {
  const el = $("#tab-mercados");
  const list = report.by_market?.[marketSel] || [];
  el.innerHTML = `<div class="seg">${["US", "ES", "JP"].map((m) => `<button data-m="${m}" class="${m === marketSel ? "active" : ""}">${FLAG[m]} ${{ US: "EE. UU.", ES: "España", JP: "Japón" }[m]}</button>`).join("")}</div>
    <h2>Mejores de ${{ US: "S&P 500 / Nasdaq 100", ES: "IBEX 35", JP: "Nikkei 225" }[marketSel]}</h2>
    ${list.length ? `<div class="list" id="mk-list">${list.map(oppRow).join("")}</div>` : `<div class="card empty">Sin candidatas hoy.</div>`}`;
  el.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { marketSel = b.dataset.m; renderMercados(); }));
  const l = $("#mk-list");
  if (l) bindOpps(l, list);
}

function newsList(items) {
  return `<div class="list news">${items.map((n) => `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}
    <small>${esc(n.publisher || "")}${n.date ? " · " + new Date(n.date).toLocaleDateString("es-ES", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : ""}</small></a>`).join("")}</div>`;
}

function renderBolsas() {
  const r = report;
  let html = `<h2>Índices y activos</h2><div class="grid2">${(r.markets || []).map((m) => `<div class="tile">
      <div class="t-label">${esc(m.label)} ${infoBtn(m.ticker)}</div><div class="t-val num">${fmt(m.value, m.value > 1000 ? 0 : 2)}</div>
      <div class="t-chg num"><span class="${cls(m.chg1d)}">${pct(m.chg1d)}</span> <span class="muted">· 1m ${pct(m.chg1m)}</span></div></div>`).join("")}</div>`;
  for (const [sec, items] of Object.entries(r.market_news || {})) {
    if (items.length) html += `<h2>Noticias · ${esc(sec)}</h2>${newsList(items)}`;
  }
  $("#tab-bolsas").innerHTML = html;
}

const ECON_GROUPS = [
  ["Estados Unidos", ["CPIAUCSL", "CPILFESL", "PCEPILFE", "FEDFUNDS", "UNRATE", "T10Y2Y"]],
  ["Europa y España", ["CP0000EZ19M086NEST", "ECBDFR", "IRLTLT01ESM156N", "IRLTLT01DEM156N", "SPREAD_ES"]],
];

function renderEconomia() {
  const macro = Object.fromEntries((report.macro || []).map((m) => [m.id, m]));
  let html = "";
  for (const [title, ids] of ECON_GROUPS) {
    const rows = ids.map((id) => macro[id]).filter(Boolean);
    if (!rows.length) continue;
    html += `<h2>${title}</h2><div class="list">${rows.map((m) => {
      const d = m.value - m.prev, dec = m.id === "SPREAD_ES" ? 0 : 2;
      return `<div class="row"><div class="label">${esc(m.label)} ${infoBtn(m.id)}<small>${esc(m.date)}</small></div>
        <div style="width:72px">${spark(m.history, { w: 72, h: 28, color: "var(--muted)" }).replace('class="spark"', 'class="spark" style="height:28px"')}</div>
        <div class="val num">${fmt(m.value, dec)}<small class="muted">${d > 0 ? "▲" : d < 0 ? "▼" : "="} desde ${fmt(m.prev, dec)}</small></div></div>`;
    }).join("")}</div>`;
  }
  html += `<p class="disclaimer">Datos oficiales de la Reserva Federal de St. Louis (FRED). Se publican con retraso: cada fila indica el mes o día del último dato.</p>`;
  $("#tab-economia").innerHTML = html;
}

async function renderHistorico() {
  const el = $("#tab-historico");
  el.innerHTML = `<h2>Informes anteriores</h2><div class="card empty">Cargando…</div>`;
  try {
    const res = await fetch(`data/history/index.json?t=${Date.now()}`, { cache: "no-store" });
    const dates = (await res.json()).reverse();
    el.innerHTML = `<h2>Informes anteriores</h2><div class="list">${dates.map((d) => `<button class="row" data-d="${d}" style="width:100%;text-align:left">
      <div class="label">${new Date(d + "T08:00").toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })}</div>
      <div class="val muted">${viewingDate === d ? "Viendo" : "›"}</div></button>`).join("")}</div>
      ${viewingDate ? `<p style="text-align:center;margin-top:16px"><button class="chip" id="back-today" style="padding:8px 14px">Volver al informe de hoy</button></p>` : ""}`;
    el.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => openReport(b.dataset.d)));
    $("#back-today")?.addEventListener("click", () => openReport(null));
  } catch {
    el.innerHTML = `<h2>Informes anteriores</h2><div class="card empty">Aún no hay histórico.</div>`;
  }
}

function openDetail(o) {
  const b = o.blocks || {};
  const max = report.weights || { valuation: 25, technical: 25, quality: 25, analysts: 25 };
  $("#sheet-body").innerHTML = `
    <div class="detail-head"><div>
      <h3>${FLAG[o.market] || ""} ${esc(o.ticker)}</h3>
      <div class="muted">${esc(o.name)}</div>
      <div class="muted" style="font-size:12px">${esc(o.index)} · ${esc(o.sector)}</div></div>
      <div class="ring" data-g="score" style="--p:${o.score};width:58px;height:58px;cursor:pointer"><span class="num" style="width:46px;height:46px;font-size:18px">${Math.round(o.score)}</span></div>
    </div>
    <div class="card" style="margin-top:14px">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <div class="num" style="font-size:22px;font-weight:700">${money(o.price, o.currency)}</div>
        <div class="num"><span class="${cls(o.chg1d)}">${pct(o.chg1d)} hoy</span> · <span class="${cls(o.chg1m)}">${pct(o.chg1m)} 1m</span></div>
      </div>
      ${spark(o.spark)}
      <div class="muted" style="font-size:12px">Últimas 60 sesiones</div>
    </div>
    ${(o.flags || []).length ? `<div class="card" style="background:var(--warn-soft)"><ul class="reasons" style="color:var(--warn)">${o.flags.map((f) => `<li>${esc(f)}</li>`).join("")}</ul></div>` : ""}
    ${(o.basic?.fall || []).length ? `<h2>Por qué ha bajado</h2><div class="card"><ul class="reasons">${o.basic.fall.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
    ${o.timing ? `<h2>Momento de entrada ${infoBtn("timing")}</h2>
    <div class="card">
      <div style="display:flex;align-items:center;gap:10px">${timingPill(o.timing)}<span class="muted" style="font-size:13px">${TIMING[o.timing.label].help}</span></div>
      ${o.timing.positive.length ? `<ul class="reasons sig-pos">${o.timing.positive.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${o.timing.negative.length ? `<ul class="reasons sig-neg">${o.timing.negative.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${(o.basic?.when_good || []).length ? `<div class="when-good"><b>Sería mejor momento:</b><ul class="reasons">${o.basic.when_good.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
    </div>` : ""}
    <h2>Por qué aparece</h2>
    <div class="card">${(o.reasons || []).length ? `<ul class="reasons">${o.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : `<span class="muted">Puntuación equilibrada en todos los bloques.</span>`}</div>
    <h2>Desglose de la nota ${infoBtn("score")}</h2>
    <div class="card bars">${Object.keys(BLOCK_LABEL).map((k) => `<div class="bar"><div class="bar-top"><span>${BLOCK_LABEL[k]} ${infoBtn(k)}</span><span class="num">${fmt(b[k], 1)} / ${max[k]}</span></div>
      <div class="track"><div class="fill" style="width:${Math.min(100, ((b[k] || 0) / max[k]) * 100)}%"></div></div></div>`).join("")}</div>
    <h2>Datos clave</h2>
    <div class="card kv num">
      <div><span>PER ${infoBtn("pe")}</span><span>${fmt(o.pe, 1)}</span></div>
      <div><span>ROE ${infoBtn("roe")}</span><span>${o.roe == null ? "—" : (o.roe * 100).toFixed(0) + "%"}</span></div>
      <div><span>RSI 14 ${infoBtn("rsi")}</span><span>${fmt(o.rsi, 0)}</span></div>
      <div><span>vs MM200 ${infoBtn("sma200")}</span><span class="${cls(o.vs_sma200)}">${pct(o.vs_sma200)}</span></div>
      <div><span>Desde máx. 52s ${infoBtn("drawdown")}</span><span class="down">${pct(o.drawdown, 0)}</span></div>
      <div><span>Potencial ${infoBtn("upside")}</span><span class="${cls(o.upside)}">${pct(o.upside, 0)}</span></div>
      <div><span>Analistas ${infoBtn("analysts_n")}</span><span>${o.analysts ?? "—"}</span></div>
      <div><span>Consenso ${infoBtn("consensus")}</span><span>${REC[o.recommendation] || esc(o.recommendation) || "—"}</span></div>
    </div>
    <div class="actions">
      ${o.isin ? `${trButton(o.isin)}
        <div class="btn-row"><button class="btn" data-copy="${esc(o.isin)}">Copiar ISIN · ${esc(o.isin)}</button>${infoBtn("isin")}</div>
        <a class="btn" href="https://app.traderepublic.com/instrument/${esc(o.isin)}" target="_blank" rel="noopener">Abrir en la web de Trade Republic</a>` : ""}
      <a class="btn" href="https://finance.yahoo.com/quote/${encodeURIComponent(o.ticker)}" target="_blank" rel="noopener">Ver en Yahoo Finance</a>
    </div>
    ${(o.news || []).length ? `<h2>Noticias</h2>${newsList(o.news)}` : ""}
    <p class="disclaimer">Datos de Yahoo Finance, FRED y Google News. Pueden tener retrasos o errores.</p>`;
  const sh = $("#sheet");
  if (sh.hidden) lockScroll();
  sh.hidden = false;
  const panel = sh.querySelector(".sheet-panel");
  panel.style.transform = "";
  panel.scrollTop = 0;
}

// --- Bloqueo del fondo: en iOS Safari overflow:hidden no basta, hay que fijar el body
let savedScrollY = 0;
function lockScroll() {
  savedScrollY = window.scrollY;
  document.body.style.top = `-${savedScrollY}px`;
  document.body.classList.add("locked");
}
function unlockScroll() {
  document.body.classList.remove("locked");
  document.body.style.top = "";
  window.scrollTo(0, savedScrollY);
}

function closeSheet() {
  const sh = $("#sheet");
  if (sh.hidden) return;
  sh.hidden = true;
  sh.querySelector(".sheet-panel").style.transform = "";
  sh.querySelector(".sheet-backdrop").style.opacity = "";
  unlockScroll();
}
$("#sheet").addEventListener("click", async (e) => {
  const cp = e.target.closest("[data-copy]");
  if (cp) {
    try { await navigator.clipboard.writeText(cp.dataset.copy); cp.textContent = "ISIN copiado ✓"; }
    catch { cp.textContent = cp.dataset.copy; }
    return;
  }
  if (e.target.classList.contains("sheet-backdrop") || e.target.closest(".sheet-close")) closeSheet();
});
// El fondo oscuro no debe desplazar nada
$(".sheet-backdrop").addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });

// --- Deslizar hacia abajo para cerrar
// Tirador: zona de arrastre propia con Pointer Events (fiable en iOS, sin conflicto con el scroll).
// Contenido: solo arrastra si la ficha está arriba del todo; si no, desplaza el contenido.
(() => {
  const panel = $(".sheet-panel"), backdrop = $(".sheet-backdrop"), handle = $(".sheet-top");
  let startY = 0, lastY = 0, lastT = 0, vel = 0, dy = 0, dragging = false;

  const begin = (y) => { startY = lastY = y; lastT = performance.now(); vel = 0; dy = 0; dragging = false; };
  const move = (y) => {
    const now = performance.now();
    vel = (y - lastY) / Math.max(1, now - lastT); // px/ms, positivo hacia abajo
    lastY = y; lastT = now;
    dy = Math.max(0, y - startY);
    if (!dragging && dy < 4) return false;
    dragging = true;
    panel.classList.add("dragging"); panel.classList.remove("snap");
    panel.style.transform = `translateY(${dy}px)`;
    backdrop.style.opacity = String(Math.max(0.15, 1 - dy / 450));
    return true;
  };
  const end = () => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("dragging"); panel.classList.add("snap");
    // Cierra si se arrastra lo suficiente o con un gesto rápido hacia abajo
    if (dy > 90 || (dy > 25 && vel > 0.45)) {
      panel.style.transform = "translateY(100%)";
      backdrop.style.opacity = "0";
      setTimeout(closeSheet, 200);
    } else {
      panel.style.transform = "";
      backdrop.style.opacity = "";
    }
  };

  // 1) Tirador
  handle.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".sheet-close")) return;
    handle.setPointerCapture(e.pointerId);
    begin(e.clientY);
    e.preventDefault();
  });
  handle.addEventListener("pointermove", (e) => { if (handle.hasPointerCapture(e.pointerId)) move(e.clientY); });
  handle.addEventListener("pointerup", end);
  handle.addEventListener("pointercancel", end);

  // 2) Resto de la ficha (táctil)
  let armed = false;
  panel.addEventListener("touchstart", (e) => {
    if (e.target.closest(".sheet-top")) { armed = false; return; }
    armed = panel.scrollTop <= 0;
    begin(e.touches[0].clientY);
  }, { passive: true });
  panel.addEventListener("touchmove", (e) => {
    if (!armed) return;
    const y = e.touches[0].clientY;
    if (y - startY > 0) {
      e.preventDefault(); // evita el rebote que arrastraba la página de atrás
      move(y);
    } else if (!dragging) {
      armed = false; // el gesto va hacia arriba: dejar que desplace el contenido
    }
  }, { passive: false });
  panel.addEventListener("touchend", end);
  panel.addEventListener("touchcancel", end);
})();
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

// --- Vista básica (lenguaje sencillo, sin cifras)
const COUNTRY = { US: "Estados Unidos", ES: "España", JP: "Japón" };
const LEVEL3 = { baja: 1, media: 2, alta: 3, bajo: 1, medio: 2, alto: 3 };

function meter(label, value, kind) {
  const n = LEVEL3[value] || 0;
  return `<div class="meter"><span class="meter-label">${label}</span>
    <span class="dots ${kind}">${[1, 2, 3].map((i) => `<i class="${i <= n ? "on" : ""}"></i>`).join("")}</span>
    <span class="meter-val">${esc(value[0].toUpperCase() + value.slice(1))}</span></div>`;
}

function renderBasico() {
  const r = report, bm = r.basic_market || { lines: [] };
  let html = `<div class="b-card b-intro"><h3>¿Cómo está la bolsa hoy?</h3>
    ${bm.lines.map((l) => `<p>${esc(l)}</p>`).join("")}
    ${(r.basic_news || []).length ? `<h4>Titulares del día</h4><ul class="b-news">${r.basic_news.slice(0, 3).map((n) => `<li><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></li>`).join("")}</ul>` : ""}
  </div>`;
  html += `<h2 class="b-h2">Empresas interesantes hoy</h2>`;
  const list = r.top.slice(0, 5).filter((o) => o.basic);
  if (!list.length) html += `<div class="b-card"><p>Hoy no hay ninguna empresa que destaque claramente.</p></div>`;
  for (const o of list) {
    const b = o.basic;
    const name = o.short && o.market === "ES" ? o.short : String(o.name).replace(/,? (Inc\.?|Corporation|Corp\.?|S\.A\.?|plc|Ltd\.?)$/i, "");
    html += `<article class="b-card">
      <div class="b-head"><div><h3>${esc(name)}</h3>
        <div class="b-sub">${FLAG[o.market] || ""} ${COUNTRY[o.market] || ""}${b.what ? " · " + esc(b.what) : ""}</div></div></div>
      <div class="b-moment b-${esc(o.timing?.label || "")}">${esc(b.moment)}</div>
      ${b.moment_text ? `<p class="b-moment-text">${esc(b.moment_text)}</p>` : ""}
      <div class="meters">${meter("Posible ganancia", b.gain, "gain")}${meter("Riesgo", b.risk, "risk")}</div>
      <h4>👍 Por qué sí</h4><ul class="b-list yes">${b.why_yes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      ${(b.fall || []).length ? `<h4>📉 Por qué ha bajado</h4>${(b.fall || []).length ? `<ul class="b-list dot">${b.fall.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}` : ""}
      ${(b.wait || []).length ? `<h4>⏳ Por qué esperar</h4>${(b.wait || []).length ? `<ul class="b-list no">${b.wait.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}` : ""}
      ${(b.good_now || []).length ? `<h4>✅ Lo que ya va bien</h4>${(b.good_now || []).length ? `<ul class="b-list yes">${b.good_now.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}` : ""}
      ${(b.when_good || []).length ? `<h4>🔔 Sería mejor momento…</h4>${(b.when_good || []).length ? `<ul class="b-list bell">${b.when_good.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}` : ""}
      <h4>⚠️ Precaución</h4>
      <ul class="b-list warn">${(b.caution || b.why_no || []).map((x) => `<li>${esc(x)}</li>`).join("")}<li>Ninguna acción es segura: pon solo una parte pequeña de tus ahorros en cada empresa.</li></ul>
      <h4>📰 Qué dicen las noticias</h4><p>${esc(b.news_text)}</p>
      ${b.news.length ? `<ul class="b-news">${b.news.map((n) => `<li><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></li>`).join("")}</ul>` : ""}
      ${o.isin ? trButton(o.isin) : ""}
    </article>`;
  }
  html += `<div class="b-card b-warn"><p><strong>Recuerda:</strong> esto no es un consejo de inversión, solo un resumen automático.
    Invierte únicamente dinero que no vayas a necesitar, no lo pongas todo en una sola empresa y, si tienes dudas, pregunta antes de comprar.</p></div>`;
  $("#tab-basico").innerHTML = html;
}

// --- Modo básico / experto
let mode = "experto";
try { mode = localStorage.getItem("modo") || "experto"; } catch {}
let expertTab = "hoy";

function applyMode() {
  document.body.classList.toggle("basic", mode === "basico");
  document.querySelectorAll(".mode button").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  if (mode === "basico") {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-basico"));
    $("#title").textContent = viewingDate ? "Informe anterior" : "Hoy";
  } else {
    $("#title").textContent = viewingDate ? "Informe anterior" : "Oportunidades";
    setTab(expertTab, false);
  }
}
document.querySelectorAll(".mode button").forEach((b) => b.addEventListener("click", () => {
  mode = b.dataset.mode;
  try { localStorage.setItem("modo", mode); } catch {}
  applyMode();
  window.scrollTo(0, 0);
}));

function setTab(name, scroll = true) {
  expertTab = name;
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  if (name === "historico") renderHistorico();
  if (scroll) window.scrollTo(0, 0);
}
document.querySelectorAll(".tabbar button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));

function renderAll() {
  const g = new Date(report.generated_at);
  $("#title").textContent = viewingDate ? "Informe anterior" : "Oportunidades";
  $("#subtitle").textContent = `${g.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })} · ${g.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}`;
  renderHoy();
  renderMercados();
  renderBolsas();
  renderEconomia();
  renderBasico();
  applyMode();
}

async function openReport(date) {
  try {
    report = await load(date);
    viewingDate = date;
    expertTab = "hoy";
    renderAll();
  } catch (e) {
    $("#subtitle").textContent = "No se pudo cargar el informe";
  }
}

$("#refresh").addEventListener("click", () => openReport(null));
openReport(null);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
