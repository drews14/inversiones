"use strict";

const FLAG = { US: "🇺🇸", ES: "🇪🇸", JP: "🇯🇵" };
const BLOCK_LABEL = { valuation: "Valoración", technical: "Sobreventa técnica", quality: "Calidad / fiabilidad", analysts: "Consenso analistas" };
const REC = { strong_buy: "Compra fuerte", buy: "Comprar", hold: "Mantener", underperform: "Infraponderar", sell: "Vender", none: "—" };

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
          <div class="opp-tk">${FLAG[o.market] || ""} ${esc(o.ticker)}</div>
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
    html += `<h2>Termómetro del mercado</h2><div class="card">
      <div class="gauge"><div class="gauge-value num">${s.value}</div>
        <div style="flex:1"><div style="font-weight:600;margin-bottom:8px">${esc(s.label)}</div>
        <div class="gauge-bar"><div class="gauge-dot" style="left:${s.value}%"></div></div></div></div>
      <div class="gauge-meta muted"><span>S&amp;P &gt; MM200: ${fmt(s.above200, 0)}%</span><span>&gt; MM50: ${fmt(s.above50, 0)}%</span><span>VIX ${fmt(s.vix, 1)}</span></div>
      <div class="muted" style="font-size:12px;margin-top:8px">${esc(s.note)}</div></div>`;
  }
  const key = (r.macro || []).filter((m) => ["CPIAUCSL", "FEDFUNDS", "T10Y2Y", "SPREAD_ES"].includes(m.id));
  if (key.length) {
    html += `<div class="grid2">${key.map((m) => `<div class="tile"><div class="t-label">${esc(m.label)}</div>
      <div class="t-val num">${fmt(m.value, m.id === "SPREAD_ES" ? 0 : 2)}</div>
      <div class="t-chg muted">antes ${fmt(m.prev, m.id === "SPREAD_ES" ? 0 : 2)} · ${esc(m.date)}</div></div>`).join("")}</div>`;
  }
  html += `<h2>Top oportunidades (${r.top.length})</h2>`;
  html += r.top.length ? `<div class="list" id="top-list">${r.top.map(oppRow).join("")}</div>`
    : `<div class="card empty">Hoy ninguna empresa supera el umbral mínimo.</div>`;
  html += `<p class="disclaimer">Analizadas ${r.analyzed} de ${r.universe_size} empresas · ${r.candidates} superan el umbral.
    Esto es un filtro automático según tus criterios, no una recomendación de inversión. Revisa siempre cada empresa antes de decidir.</p>`;
  el.innerHTML = html;
  const list = $("#top-list");
  if (list) bindOpps(list, r.top);
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

function renderMacro() {
  const r = report;
  let html = `<h2>Índices y activos</h2><div class="grid2">${(r.markets || []).map((m) => `<div class="tile">
      <div class="t-label">${esc(m.label)}</div><div class="t-val num">${fmt(m.value, m.value > 1000 ? 0 : 2)}</div>
      <div class="t-chg num"><span class="${cls(m.chg1d)}">${pct(m.chg1d)}</span> <span class="muted">· 1m ${pct(m.chg1m)}</span></div></div>`).join("")}</div>`;
  html += `<h2>Indicadores macro</h2><div class="list">${(r.macro || []).map((m) => {
    const d = m.value - m.prev;
    return `<div class="row"><div class="label">${esc(m.label)}<small>${esc(m.date)}</small></div>
      <div style="width:80px">${spark(m.history, { w: 80, h: 28, color: "var(--muted)" }).replace('class="spark"', 'class="spark" style="height:28px"')}</div>
      <div class="val num">${fmt(m.value, m.id === "SPREAD_ES" ? 0 : 2)}<small class="${d > 0 ? "down" : d < 0 ? "up" : "muted"}">${d > 0 ? "▲" : d < 0 ? "▼" : "="} ${fmt(Math.abs(d), m.id === "SPREAD_ES" ? 0 : 2)}</small></div></div>`;
  }).join("")}</div>`;
  for (const [sec, items] of Object.entries(r.market_news || {})) {
    if (items.length) html += `<h2>Noticias · ${esc(sec)}</h2>${newsList(items)}`;
  }
  $("#tab-macro").innerHTML = html;
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
      <div class="ring" style="--p:${o.score};width:58px;height:58px"><span class="num" style="width:46px;height:46px;font-size:18px">${Math.round(o.score)}</span></div>
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
    <h2>Por qué aparece</h2>
    <div class="card">${(o.reasons || []).length ? `<ul class="reasons">${o.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : `<span class="muted">Puntuación equilibrada en todos los bloques.</span>`}</div>
    <h2>Desglose de la nota</h2>
    <div class="card bars">${Object.keys(BLOCK_LABEL).map((k) => `<div class="bar"><div class="bar-top"><span>${BLOCK_LABEL[k]}</span><span class="num">${fmt(b[k], 1)} / ${max[k]}</span></div>
      <div class="track"><div class="fill" style="width:${Math.min(100, ((b[k] || 0) / max[k]) * 100)}%"></div></div></div>`).join("")}</div>
    <h2>Datos clave</h2>
    <div class="card kv num">
      <div><span>PER</span><span>${fmt(o.pe, 1)}</span></div>
      <div><span>ROE</span><span>${o.roe == null ? "—" : (o.roe * 100).toFixed(0) + "%"}</span></div>
      <div><span>RSI 14</span><span>${fmt(o.rsi, 0)}</span></div>
      <div><span>vs MM200</span><span class="${cls(o.vs_sma200)}">${pct(o.vs_sma200)}</span></div>
      <div><span>Desde máx. 52s</span><span class="down">${pct(o.drawdown, 0)}</span></div>
      <div><span>Potencial</span><span class="${cls(o.upside)}">${pct(o.upside, 0)}</span></div>
      <div><span>Analistas</span><span>${o.analysts ?? "—"}</span></div>
      <div><span>Consenso</span><span>${REC[o.recommendation] || esc(o.recommendation) || "—"}</span></div>
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
$("#sheet").addEventListener("click", (e) => {
  if (e.target.classList.contains("sheet-backdrop") || e.target.closest(".sheet-close")) closeSheet();
});
// El fondo oscuro no debe desplazar nada
$(".sheet-backdrop").addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });

// --- Deslizar hacia abajo para cerrar (solo cuando la ficha está arriba del todo)
(() => {
  const panel = $(".sheet-panel"), backdrop = $(".sheet-backdrop");
  let startY = 0, dy = 0, dragging = false, armed = false;
  panel.addEventListener("touchstart", (e) => {
    startY = e.touches[0].clientY; dy = 0; dragging = false;
    armed = panel.scrollTop <= 0;
  }, { passive: true });
  panel.addEventListener("touchmove", (e) => {
    if (!armed) return;
    dy = e.touches[0].clientY - startY;
    if (dy > 0) {
      dragging = true;
      e.preventDefault(); // evita el rebote que arrastraba la página de atrás
      panel.classList.add("dragging"); panel.classList.remove("snap");
      panel.style.transform = `translateY(${dy}px)`;
      backdrop.style.opacity = String(Math.max(0.2, 1 - dy / 400));
    } else if (dragging) {
      panel.style.transform = "";
    }
  }, { passive: false });
  panel.addEventListener("touchend", () => {
    if (!dragging) return;
    panel.classList.remove("dragging"); panel.classList.add("snap");
    if (dy > 110) {
      panel.style.transform = "translateY(100%)";
      setTimeout(closeSheet, 200);
    } else {
      panel.style.transform = "";
      backdrop.style.opacity = "";
    }
    dragging = false;
  });
})();
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

function setTab(name) {
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  if (name === "historico") renderHistorico();
  window.scrollTo(0, 0);
}
document.querySelectorAll(".tabbar button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));

function renderAll() {
  const g = new Date(report.generated_at);
  $("#title").textContent = viewingDate ? "Informe anterior" : "Oportunidades";
  $("#subtitle").textContent = `${g.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })} · ${g.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}`;
  renderHoy();
  renderMercados();
  renderMacro();
}

async function openReport(date) {
  try {
    report = await load(date);
    viewingDate = date;
    renderAll();
    setTab("hoy");
  } catch (e) {
    $("#subtitle").textContent = "No se pudo cargar el informe";
  }
}

$("#refresh").addEventListener("click", () => openReport(null));
openReport(null);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
