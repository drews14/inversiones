"use strict";
// Modo Simulador: carteras ficticias y reales con gráficas y precios en directo.
// Solo existe cuando la app se sirve desde el servidor propio (no en GitHub Pages).
(() => {
  const API = "api/";
  const S = {
    server: false, me: null, accounts: [], current: null, detail: null, quotes: {}, es: null, watch: [],
    tab: "cartera", range: "1mo", hist: null, valueRange: "1mo",
  };
  const rep = () => (typeof report !== "undefined" && report) || {};
  const root = () => document.querySelector("#tab-simulador");
  const eur = (v, d = 2) => (v == null ? "—" : `${fmt(v, d)} €`);
  const signed = (v, d = 2) => (v == null ? "—" : `${v > 0 ? "+" : ""}${fmt(v, d)} €`);
  const RANGE_LABEL = { "1d": "1D", "5d": "1S", "1mo": "1M", "3mo": "3M", "1y": "1A", "5y": "5A", max: "Todo" };

  async function api(path, opts = {}) {
    const res = await fetch(API + path, {
      method: opts.method || "GET", credentials: "same-origin",
      headers: opts.body ? { "Content-Type": "application/json" } : {},
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch {}
    if (!res.ok) {
      const err = new Error((data && (data.error || (Array.isArray(data.detail) ? "Revisa los datos" : data.detail))) || `Error ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  // ---------------------------------------------------------------- arranque
  async function detect() {
    try {
      const r = await fetch(API + "health", { cache: "no-store" });
      S.server = r.ok && (await r.json()).server === true;
    } catch { S.server = false; }
    document.querySelector("#mode-sim").hidden = !S.server;
    let saved = null;
    try { saved = localStorage.getItem("modo"); } catch {}
    if (S.server && saved === "simulador" && window.setMode) window.setMode("simulador");
  }

  async function show() {
    if (!S.server) return;
    try { S.me = await api("me"); } catch { S.me = null; return renderLogin(); }
    await loadAccounts();
  }

  async function loadAccounts() {
    S.accounts = await api("accounts");
    if (!S.current || !S.accounts.some((a) => a.id === S.current)) S.current = S.accounts[0]?.id;
    await loadDetail();
  }

  async function loadDetail() {
    if (!S.current) { S.detail = null; return render(); }
    S.detail = await api(`accounts/${S.current}`);
    for (const p of S.detail.positions) if (p.quote) S.quotes[p.ticker] = p.quote;
    // cartera recién creada: empieza mostrando el día de hoy
    if (!S.rangeChosen) {
      const first = Math.min(...(S.detail.trades || []).map((t) => t.ts), Date.now() / 1000);
      S.range = Date.now() / 1000 - first < 2 * 86400 ? "1d" : "1mo";
    }
    render();
    startStream();
    loadHistory();
  }

  async function loadHistory() {
    const box = document.querySelector("#pf-chart");
    if (!box || !S.current) return;
    try {
      S.hist = await api(`accounts/${S.current}/history?range=${S.range}`);
      drawPortfolioChart();
    } catch { box.innerHTML = `<div class="chart-empty">No se pudo cargar la evolución</div>`; }
  }

  // ---------------------------------------------------------------- tabbar propio
  document.querySelectorAll("#sim-tabbar button").forEach((b) => b.addEventListener("click", () => {
    S.tab = b.dataset.stab;
    document.querySelectorAll("#sim-tabbar button").forEach((x) => x.classList.toggle("active", x === b));
    render();
    window.scrollTo(0, 0);
  }));

  // ---------------------------------------------------------------- precios en directo (SSE)
  function startStream() {
    if (S.es) S.es.close();
    S.es = new EventSource(`${API}stream?tickers=${encodeURIComponent(S.watch.join(","))}`);
    S.es.onmessage = (ev) => {
      try { Object.assign(S.quotes, JSON.parse(ev.data)); updateLive(); } catch {}
    };
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && S.es) { S.es.close(); S.es = null; }
    else if (document.visibilityState === "visible" && S.me && window.getMode?.() === "simulador") startStream();
  });

  const liveBadge = (q) => (!q ? "" : q.realtime ? `<span class="live on">En directo</span>` : `<span class="live">~15 min</span>`);

  function recalc() {
    const d = S.detail;
    if (!d) return;
    let value = 0;
    for (const p of d.positions) {
      const q = S.quotes[p.ticker];
      if (q && q.price_eur != null) {
        p.quote = q;
        p.value_eur = p.qty * q.price_eur;
        p.pnl_eur = p.value_eur - p.cost_eur;
        p.pnl_pct = p.cost_eur ? p.pnl_eur / p.cost_eur : null;
      }
      value += p.value_eur || 0;
    }
    d.positions_value = value;
    if (d.kind === "sim") {
      d.total = d.cash + value;
      d.pnl_total = d.total - d.start_cash;
      d.pnl_total_pct = d.start_cash ? d.pnl_total / d.start_cash : null;
    } else {
      d.total = value;
      d.pnl_total = value - d.invested + d.pnl_realized - d.fees;
      d.pnl_total_pct = d.invested ? d.pnl_total / d.invested : null;
    }
  }

  function updateLive() {
    if (window.getMode?.() !== "simulador") return;
    recalc();
    if (S.tab === "cartera" && S.detail && !S.scrubbing) {
      const h = document.querySelector("#pf-hero"); if (h) h.outerHTML = heroHtml();
      const l = document.querySelector("#sim-positions"); if (l) { l.outerHTML = positionsHtml(); bindPositions(); }
    }
    document.querySelectorAll("[data-live-q]").forEach((e) => {
      const q = S.quotes[e.dataset.liveQ];
      if (q) e.innerHTML = `${money(q.price, q.currency)} ${q.chg_day != null ? `<span class="${cls(q.chg_day)}">${pct(q.chg_day, 2)}</span>` : ""}`;
    });
    const tq = document.querySelector("#trade-quote");
    if (tq && tq.dataset.ticker && S.quotes[tq.dataset.ticker]) tq.innerHTML = quoteHtml(S.quotes[tq.dataset.ticker]);
  }

  // ---------------------------------------------------------------- login / registro
  function renderLogin(mode = "login", msg = "") {
    document.querySelector("#sim-tabbar").hidden = true;
    root().innerHTML = `<h2>${mode === "login" ? "Inicia sesión" : "Crear cuenta con invitación"}</h2>
      <form class="card form" id="auth-form" autocomplete="on">
        ${mode === "register" ? `<label>Código de invitación<input name="invite" required autocomplete="off" autocapitalize="characters"></label>` : ""}
        <label>Usuario<input name="username" required minlength="3" maxlength="30" autocomplete="username" autocapitalize="none"></label>
        <label>Contraseña<input name="password" type="password" required minlength="8" autocomplete="${mode === "login" ? "current-password" : "new-password"}"></label>
        ${msg ? `<p class="form-error">${esc(msg)}</p>` : ""}
        <button class="btn primary" type="submit">${mode === "login" ? "Entrar" : "Crear cuenta"}</button>
      </form>
      <p style="text-align:center"><button class="link" id="auth-switch">${mode === "login" ? "Tengo un código de invitación" : "Ya tengo cuenta"}</button></p>
      <p class="disclaimer">Cada persona tiene su propio usuario y nadie ve las carteras de los demás.</p>`;
    document.querySelector("#auth-switch").onclick = () => renderLogin(mode === "login" ? "register" : "login");
    document.querySelector("#auth-form").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(mode === "login" ? "login" : "register", { method: "POST", body: Object.fromEntries(new FormData(e.target)) });
        document.querySelector("#sim-tabbar").hidden = false;
        await show();
      } catch (err) { renderLogin(mode, err.message); }
    };
  }

  // ---------------------------------------------------------------- pestaña Cartera
  function accountChips() {
    return `<div class="acc-row">${S.accounts.map((a) => `<button class="acc-chip ${a.id === S.current ? "active" : ""}" data-acc="${a.id}">
      ${esc(a.name)} <span class="kind ${a.kind}">${a.kind === "sim" ? "Ficticia" : "Real"}</span></button>`).join("")}
      <button class="acc-chip add" data-new-acc>+ Nueva</button></div>`;
  }

  function heroHtml(scrub) {
    const d = S.detail;
    let val = d.total, pnl = d.pnl_total, pp = d.pnl_total_pct, when = d.kind === "sim" ? "Valor de la cartera" : "Valor de tus acciones";
    if (scrub) {
      val = scrub.v;
      const base = d.kind === "sim" ? d.start_cash : scrub.inv;
      pnl = base != null ? val - base : null;
      pp = base ? pnl / base : null;
      when = new Date(scrub.t * 1000).toLocaleString("es-ES", { day: "numeric", month: "short", year: S.range === "5y" || S.range === "max" ? "numeric" : undefined, hour: S.range === "1d" || S.range === "5d" ? "2-digit" : undefined, minute: S.range === "1d" || S.range === "5d" ? "2-digit" : undefined });
    }
    return `<div class="hero" id="pf-hero"><small>${esc(when)}</small><b class="num">${eur(val)}</b>
      <span class="num ${cls(pnl)}">${signed(pnl)} (${pct(pp, 2)}) <span class="muted">${scrub ? "" : "total"}</span></span></div>`;
  }

  function rangeChips(cur, attr, list) {
    return `<div class="range-row">${list.map((r) => `<button ${attr}="${r}" class="${r === cur ? "active" : ""}">${RANGE_LABEL[r]}</button>`).join("")}</div>`;
  }

  function slotsByEntity() {
    // el color sigue a la empresa (orden de primera compra), nunca a su posición en el ranking
    const order = [];
    for (const t of [...(S.detail.trades || [])].reverse()) if (!order.includes(t.ticker)) order.push(t.ticker);
    return Object.fromEntries(order.map((t, i) => [t, i < 7 ? i + 1 : null]));
  }

  function allocItems() {
    const d = S.detail, slots = slotsByEntity();
    const items = d.positions.map((p) => ({ label: esc(p.ticker), value: p.value_eur || 0, slot: slots[p.ticker] }));
    const named = items.filter((i) => i.slot), rest = items.filter((i) => !i.slot);
    if (rest.length) named.push({ label: "Otros", value: rest.reduce((a, b) => a + b.value, 0), slot: 8 });
    if (d.kind === "sim" && d.cash > 0.5) named.push({ label: "Efectivo", value: d.cash, slot: null });
    return named;
  }

  function positionsHtml() {
    const d = S.detail;
    if (!d.positions.length) return `<div class="card empty" id="sim-positions">Todavía no tienes acciones en esta cartera. Ve a <b>Mercado</b> para comprar.</div>`;
    return `<div class="list" id="sim-positions">${d.positions.map((p, i) => {
      const q = p.quote;
      return `<button class="opp pos" data-i="${i}">
        <div class="opp-main"><div class="opp-head">
          <div style="min-width:0"><div class="opp-tk">${esc(p.ticker)} ${liveBadge(q)}</div>
            <div class="opp-name">${esc(p.name || "")}</div>
            <div class="opp-name num">${fmt(p.qty, p.qty % 1 ? 4 : 0)} acc. · medio ${money(p.avg_price, p.currency)}</div></div>
          <div class="opp-price num"><b>${eur(p.value_eur)}</b><br>
            <span class="${cls(p.pnl_eur)}">${signed(p.pnl_eur)}</span><br>
            <small class="${cls(p.pnl_pct)}">${pct(p.pnl_pct, 2)}</small></div>
        </div></div></button>`;
    }).join("")}</div>`;
  }

  function bindPositions() {
    document.querySelectorAll("#sim-positions .pos").forEach((b) => b.addEventListener("click", () => {
      const p = S.detail.positions[+b.dataset.i];
      openValue(p.ticker, p.name);
    }));
  }

  function renderCartera() {
    const d = S.detail;
    if (!d) return `${accountChips()}<div class="card empty">Crea una cartera para empezar.</div>`;
    return `${accountChips()}
      <div class="card pf-card">${heroHtml()}
        <div id="pf-chart" class="chart-box"><div class="chart-empty">Cargando…</div></div>
        ${rangeChips(S.range, "data-range", ["1d", "5d", "1mo", "3mo", "1y", "max"])}
      </div>
      <div class="sim-grid card num">
        ${d.kind === "sim" ? `<div><small>Efectivo</small>${eur(d.cash)}</div>` : `<div><small>Invertido</small>${eur(d.invested)}</div>`}
        <div><small>En acciones</small>${eur(d.positions_value)}</div>
        <div><small>Ganancia abierta</small><span class="${cls(d.positions_value - d.invested)}">${signed(d.positions_value - d.invested)}</span></div>
        <div><small>Ya realizada</small><span class="${cls(d.pnl_realized)}">${signed(d.pnl_realized)}</span></div>
      </div>
      ${d.positions.length || d.kind === "sim" ? `<h2>Reparto</h2><div class="card" id="pf-alloc"></div>` : ""}
      <h2>Posiciones</h2>${positionsHtml()}
      <div class="sim-actions"><button class="btn primary" data-open-trade>${d.kind === "sim" ? "Comprar (simulado)" : "Apuntar compra o venta"}</button></div>
      <p class="disclaimer">${d.kind === "sim" ? `Cartera ficticia: empezaste con ${eur(d.start_cash, 0)} de mentira · comisión ${eur(d.fee_eur)} por operación.` : "Cartera real: registro de tus operaciones; la app no mueve dinero."}</p>`;
  }

  function drawPortfolioChart() {
    const box = document.querySelector("#pf-chart");
    if (!box || !S.hist) return;
    const pts = S.hist.points || [];
    const intraday = S.range === "1d" || S.range === "5d";
    Charts.line(box, pts, {
      height: 190, label: "Evolución del valor de la cartera",
      base: S.detail.kind === "sim" ? S.detail.start_cash : (pts[0]?.inv ?? null),
      fmtV: (v) => fmt(v, v >= 1000 ? 0 : 2),
      fmtT: (t) => new Date(t * 1000).toLocaleString("es-ES", intraday ? { hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short" }),
      tipT: (t) => new Date(t * 1000).toLocaleString("es-ES", intraday ? { weekday: "short", hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short", year: "2-digit" }),
      onScrub: (p) => {
        S.scrubbing = !!p;
        const h = document.querySelector("#pf-hero");
        if (h) h.outerHTML = heroHtml(p);
      },
    });
  }

  // ---------------------------------------------------------------- pestaña Mercado
  function marketRow(t, name, extra = "") {
    const q = S.quotes[t];
    return `<button class="row mk-row" data-val="${esc(t)}" data-name="${esc(name || "")}" style="width:100%;text-align:left">
      <div class="label"><b>${esc(t)}</b> ${extra}<small>${esc(name || "")}</small></div>
      <div class="val num" data-live-q="${esc(t)}">${q ? `${money(q.price, q.currency)} ${q.chg_day != null ? `<span class="${cls(q.chg_day)}">${pct(q.chg_day, 2)}</span>` : ""}` : "›"}</div></button>`;
  }

  function renderMercado() {
    const r = rep() || {};
    const opp = (r.top || []).slice(0, 5), risk = (r.risk_top || []).slice(0, 5);
    const ts = [...opp, ...risk].map((o) => o.ticker);
    const fresh = ts.filter((t) => !S.watch.includes(t));
    if (fresh.length) { S.watch.push(...fresh); startStream(); }
    return `<label class="form search-box"><input id="mk-search" placeholder="Busca cualquier empresa o ETF: Apple, Inditex, ADS.DE…" autocomplete="off" enterkeyhint="search"></label>
      <div class="list" id="mk-results"></div>
      ${opp.length ? `<h2>Oportunidades del informe de hoy</h2><div class="list">${opp.map((o) => marketRow(o.ticker, o.name, `<span class="tpill t-giro">${Math.round(o.score)}</span>`)).join("")}</div>` : ""}
      ${risk.length ? `<h2>Empiezan a caer</h2><div class="list">${risk.map((o) => marketRow(o.ticker, o.name, `<span class="tpill r-alta">${o.risk.score}</span>`)).join("")}</div>` : ""}
      <p class="disclaimer">EE. UU. y divisas en directo; Europa y Japón con unos 15 minutos de retraso.</p>`;
  }

  function bindMercado() {
    const search = document.querySelector("#mk-search");
    let timer;
    search.oninput = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = search.value.trim(), box = document.querySelector("#mk-results");
        if (q.length < 2) return (box.innerHTML = "");
        try {
          const res = await api(`search?q=${encodeURIComponent(q)}`);
          box.innerHTML = res.length ? res.map((x) => marketRow(x.ticker, `${x.name} · ${x.exchange || ""}${x.type === "ETF" ? " · ETF" : ""}`)).join("") : `<div class="row muted">Sin resultados</div>`;
          bindRows(box);
        } catch (err) { box.innerHTML = `<div class="row form-error">${esc(err.message)}</div>`; }
      }, 350);
    };
    bindRows(root());
  }

  function bindRows(scope) {
    scope.querySelectorAll("[data-val]").forEach((b) => b.onclick = () => openValue(b.dataset.val, b.dataset.name));
  }

  // ---------------------------------------------------------------- ficha de un valor (gráfica + comprar/vender)
  async function openValue(ticker, name) {
    if (!S.watch.includes(ticker)) { S.watch.push(ticker); startStream(); }
    const fromReport = [...(rep().top || []), ...Object.values(rep().by_market || {}).flat(), ...(rep().risk_top || [])].find((o) => o.ticker === ticker);
    const pos = S.detail?.positions.find((p) => p.ticker === ticker);
    showSheet(`<div class="val-head"><div><h3>${esc(ticker)}</h3><div class="muted">${esc(fromReport?.name || name || "")}</div></div>
        <div id="val-live" class="num" data-live-q="${esc(ticker)}"><span class="muted">Cargando…</span></div></div>
      <div class="card"><div class="hero" id="val-hero"></div>
        <div id="val-chart" class="chart-box"><div class="chart-empty">Cargando…</div></div>
        ${rangeChips(S.valueRange, "data-vrange", ["1d", "5d", "1mo", "1y", "5y"])}</div>
      ${pos ? `<h2>Tu posición en «${esc(S.detail.name)}»</h2><div class="card sim-grid num" style="margin:0">
        <div><small>Acciones</small>${fmt(pos.qty, pos.qty % 1 ? 4 : 0)}</div><div><small>Precio medio</small>${money(pos.avg_price, pos.currency)}</div>
        <div><small>Valor</small>${eur(pos.value_eur)}</div><div><small>Ganancia</small><span class="${cls(pos.pnl_eur)}">${signed(pos.pnl_eur)} (${pct(pos.pnl_pct, 1)})</span></div></div>` : ""}
      ${fromReport ? `<h2>En el informe de hoy</h2><div class="card kv num">
        <div><span>Nota de oportunidad</span><span>${Math.round(fromReport.score)}/100</span></div>
        ${fromReport.timing ? `<div><span>Momento de entrada</span><span>${({ giro: "Señal de giro", vigilar: "Vigilar", esperar: "Esperar" })[fromReport.timing.label]}</span></div>` : ""}
        ${fromReport.risk ? `<div><span>Riesgo de caída</span><span class="down">${fromReport.risk.score}/100</span></div>` : ""}
        ${fromReport.target ? `<div><span>Precio objetivo</span><span>${money(fromReport.target, fromReport.currency)}</span></div>` : ""}</div>` : ""}
      <div class="trade-btns">
        <button class="btn primary" data-trade-side="buy">Comprar</button>
        ${pos ? `<button class="btn sell" data-trade-side="sell">Vender</button>` : ""}
      </div>
      <p class="disclaimer">${S.detail?.kind === "real" ? "Cartera real: solo se apunta la operación, no se mueve dinero." : "Simulación con dinero ficticio a precio de mercado."}</p>`);
    document.querySelectorAll("[data-trade-side]").forEach((b) => b.onclick = () => openTrade(ticker, b.dataset.tradeSide));
    document.querySelectorAll("[data-vrange]").forEach((b) => b.onclick = () => {
      S.valueRange = b.dataset.vrange;
      document.querySelectorAll("[data-vrange]").forEach((x) => x.classList.toggle("active", x === b));
      drawValue(ticker);
    });
    try {
      const q = await api(`quote/${encodeURIComponent(ticker)}`);
      S.quotes[ticker] = q;
      updateLive();
    } catch (err) { document.querySelector("#val-live").innerHTML = `<span class="form-error">${esc(err.message)}</span>`; }
    drawValue(ticker);
  }

  async function drawValue(ticker) {
    const box = document.querySelector("#val-chart"), hero = document.querySelector("#val-hero");
    if (!box) return;
    box.innerHTML = `<div class="chart-empty">Cargando…</div>`;
    const rng = S.valueRange, intraday = rng === "1d" || rng === "5d";
    try {
      const { points } = await api(`history/${encodeURIComponent(ticker)}?range=${rng}`);
      const q = S.quotes[ticker], cur = q?.currency;
      const setHero = (p) => {
        const first = points[0]?.v, v = p ? p.v : points[points.length - 1]?.v;
        const ch = first ? v / first - 1 : null;
        hero.innerHTML = `<small>${p ? new Date(p.t * 1000).toLocaleString("es-ES", intraday ? { weekday: "short", hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short", year: "numeric" }) : `Variación en ${RANGE_LABEL[rng]}`}</small>
          <b class="num">${money(v, cur)}</b><span class="num ${cls(ch)}">${pct(ch, 2)}</span>`;
      };
      setHero(null);
      Charts.line(box, points, {
        height: 200, label: `Precio de ${ticker}`,
        fmtV: (v) => fmt(v, v >= 1000 ? 0 : 2),
        fmtT: (t) => new Date(t * 1000).toLocaleString("es-ES", intraday ? { hour: "2-digit", minute: "2-digit" } : rng === "5y" ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" }),
        tipT: (t) => new Date(t * 1000).toLocaleString("es-ES", intraday ? { hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short", year: "2-digit" }),
        onScrub: setHero,
      });
    } catch (err) { box.innerHTML = `<div class="chart-empty">${esc(err.message)}</div>`; }
  }

  // ---------------------------------------------------------------- formulario de operación
  function quoteHtml(q) {
    return `<div class="tq-top"><b>${esc(q.ticker)}</b> ${liveBadge(q)}<div class="muted">${esc(q.name || "")}</div></div>
      <div class="tq-price num">${money(q.price, q.currency)} ${q.chg_day != null ? `<span class="${cls(q.chg_day)}">${pct(q.chg_day, 2)} hoy</span>` : ""}</div>
      ${q.currency !== "EUR" && q.price_eur != null ? `<div class="muted num">≈ ${eur(q.price_eur)} por acción (cambio ${fmt(q.fx_eur, 4)} ${esc(q.currency)}/€)</div>` : ""}`;
  }

  async function openTrade(ticker, side = "buy") {
    const d = S.detail;
    if (!d) return toast("Crea primero una cartera");
    const real = d.kind === "real";
    if (!ticker) { S.tab = "mercado"; selectTab(); return toast("Busca el valor que quieres comprar"); }
    const pos = d.positions.find((p) => p.ticker === ticker);
    showSheet(`<h3>${real ? "Apuntar operación real" : "Operación simulada"} · ${esc(d.name)}</h3>
      <div class="card" id="trade-quote" data-ticker="${esc(ticker)}"><span class="muted">Cargando precio…</span></div>
      <form class="form" id="trade-form">
        <div class="seg"><button type="button" data-side="buy" class="${side === "buy" ? "active" : ""}">Comprar</button><button type="button" data-side="sell" class="${side === "sell" ? "active" : ""}">Vender</button></div>
        <div class="seg seg-small"><button type="button" data-how="eur" class="active">Importe en €</button><button type="button" data-how="qty">Nº de acciones</button></div>
        <label id="f-amount">Importe (€)<input name="amount" type="number" min="0" step="any" inputmode="decimal" placeholder="Ej.: 500"></label>
        <label id="f-qty" hidden>Acciones${pos ? ` (tienes ${fmt(pos.qty, pos.qty % 1 ? 4 : 0)})` : ""}<input name="qty" type="number" min="0" step="any" inputmode="decimal" placeholder="Ej.: 3"></label>
        ${pos ? `<button type="button" class="link" id="sell-all" ${side === "sell" ? "" : "hidden"}>Vender todo</button>` : ""}
        ${real ? `<label>Precio al que operaste (en su moneda, vacío = precio actual)<input name="price" type="number" min="0" step="any" inputmode="decimal"></label>
          <label>Fecha<input name="date" type="date"></label>` : ""}
        <label>Nota (opcional)<input name="note" maxlength="200" placeholder="Por qué compro / vendo"></label>
        <p class="muted" id="t-estimate"></p>
        <p class="form-error" id="t-err"></p>
        <button class="btn primary" type="submit" id="t-submit">${real ? "Guardar operación" : "Confirmar operación simulada"}</button>
        ${real ? "" : `<p class="muted" style="font-size:13px">Se ejecuta al precio de mercado actual con ${eur(d.fee_eur)} de comisión. No es dinero real.</p>`}
      </form>`);
    let how = "eur";
    const form = document.querySelector("#trade-form");
    const estimate = () => {
      const q = S.quotes[ticker], out = document.querySelector("#t-estimate");
      if (!q || !q.price_eur) return (out.textContent = "");
      const v = parseFloat((how === "eur" ? form.amount : form.qty).value);
      if (!v) return (out.textContent = "");
      const priceEur = real && form.price?.value ? parseFloat(form.price.value) / q.fx_eur : q.price_eur;
      out.textContent = how === "eur" ? `≈ ${fmt(v / priceEur, 4)} acciones + ${eur(d.fee_eur)} de comisión` : `≈ ${eur(v * priceEur)} + ${eur(d.fee_eur)} de comisión`;
    };
    const setHow = (h) => {
      how = h;
      form.querySelectorAll("[data-how]").forEach((x) => x.classList.toggle("active", x.dataset.how === h));
      document.querySelector("#f-amount").hidden = h !== "eur"; document.querySelector("#f-qty").hidden = h !== "qty"; estimate();
    };
    try {
      const q = await api(`quote/${encodeURIComponent(ticker)}`);
      S.quotes[ticker] = q;
      document.querySelector("#trade-quote").innerHTML = quoteHtml(q);
    } catch (err) { document.querySelector("#trade-quote").innerHTML = `<span class="form-error">${esc(err.message)}</span>`; }
    form.querySelectorAll("[data-side]").forEach((b) => b.onclick = () => {
      side = b.dataset.side; form.querySelectorAll("[data-side]").forEach((x) => x.classList.toggle("active", x === b));
      const sa = document.querySelector("#sell-all"); if (sa) sa.hidden = side !== "sell";
    });
    form.querySelectorAll("[data-how]").forEach((b) => b.onclick = () => setHow(b.dataset.how));
    document.querySelector("#sell-all")?.addEventListener("click", () => { setHow("qty"); form.qty.value = pos.qty; estimate(); });
    form.oninput = estimate;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const v = Object.fromEntries(new FormData(form));
      const body = { ticker, side, note: v.note || null };
      if (how === "eur") body.amount_eur = parseFloat(v.amount); else body.qty = parseFloat(v.qty);
      if (real) { if (v.price) body.price = parseFloat(v.price); if (v.date) body.date = v.date; }
      const btn = document.querySelector("#t-submit"); btn.disabled = true;
      try {
        const r = await api(`accounts/${S.current}/trades`, { method: "POST", body });
        closeSheet();
        toast(`${side === "buy" ? "Compra" : "Venta"}: ${fmt(r.qty, r.qty % 1 ? 4 : 0)} ${r.ticker} a ${money(r.price, r.currency)}`);
        S.tab = "cartera"; selectTab();
        await loadAccounts();
      } catch (err) { document.querySelector("#t-err").textContent = err.message; btn.disabled = false; }
    };
  }

  // ---------------------------------------------------------------- pestaña Operaciones
  function renderOperaciones() {
    const d = S.detail;
    if (!d) return `${accountChips()}<div class="card empty">Sin carteras.</div>`;
    const t = d.trades || [];
    const groups = {};
    for (const x of t) {
      const k = new Date(x.ts * 1000).toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
      (groups[k] ||= []).push(x);
    }
    return `${accountChips()}
      <div class="card sim-grid num" style="margin-top:0"><div><small>Operaciones</small>${t.length}</div><div><small>Comisiones</small>${eur(d.fees)}</div>
        <div><small>Ganancia realizada</small><span class="${cls(d.pnl_realized)}">${signed(d.pnl_realized)}</span></div><div><small>Tipo</small>${d.kind === "sim" ? "Ficticia" : "Real"}</div></div>
      ${t.length ? Object.entries(groups).map(([day, xs]) => `<h2>${esc(day)}</h2><div class="list">${xs.map((x) => `<div class="row trade">
        <div class="label"><b class="${x.side === "buy" ? "up" : "down"}">${x.side === "buy" ? "▲ Compra" : "▼ Venta"}</b> ${esc(x.ticker)}
          <small>${new Date(x.ts * 1000).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}${x.note ? " · " + esc(x.note) : ""}</small></div>
        <div class="val num">${fmt(x.qty, x.qty % 1 ? 4 : 0)} × ${money(x.price, x.currency)}<small class="muted">${eur((x.qty * x.price) / x.fx_eur)}</small></div>
        ${d.kind === "real" ? `<button class="link danger" data-deltrade="${x.id}" aria-label="Borrar">×</button>` : ""}</div>`).join("")}</div>`).join("")
      : `<div class="card empty">Sin operaciones todavía.</div>`}`;
  }

  // ---------------------------------------------------------------- pestaña Cuenta
  function renderCuenta() {
    const d = S.detail;
    return `<h2>Tu cuenta</h2><div class="card kv"><div><span>Usuario</span><span>${esc(S.me.username)}</span></div>
        <div><span>Carteras</span><span>${S.accounts.length}</span></div></div>
      <h2>Carteras</h2><div class="list">${S.accounts.map((a) => `<div class="row"><div class="label">${esc(a.name)} <span class="kind ${a.kind}">${a.kind === "sim" ? "Ficticia" : "Real"}</span>
        <small class="num">${eur(a.total)} · ${signed(a.pnl_total)}</small></div>
        <button class="link danger" data-del-acc="${a.id}">Borrar</button></div>`).join("")}</div>
      <div class="sim-actions"><button class="btn" data-new-acc>Nueva cartera</button></div>
      ${S.me.is_admin ? `<h2>Amigos</h2><div class="card"><p class="m-p">Genera un código de un solo uso y pásaselo junto con la dirección de la app.</p>
        <div class="sim-actions"><button class="btn primary" id="sim-invite">Invitar a un amigo</button></div></div>` : ""}
      <h2>Precios</h2><div class="card"><ul class="reasons"><li>EE. UU. y divisas: en directo.</li><li>Europa y Japón: con unos 15 minutos de retraso (licencias de las bolsas).</li>
        <li>En carteras ficticias se compra y vende al precio del momento con ${eur(d?.fee_eur ?? 1)} de comisión.</li></ul></div>
      <div class="sim-actions"><button class="btn" id="sim-logout">Cerrar sesión</button></div>`;
  }

  // ---------------------------------------------------------------- render general
  function selectTab() {
    document.querySelectorAll("#sim-tabbar button").forEach((x) => x.classList.toggle("active", x.dataset.stab === S.tab));
    render();
  }

  function render() {
    if (!S.me) return renderLogin();
    document.querySelector("#sim-tabbar").hidden = window.getMode?.() !== "simulador";
    const html = { cartera: renderCartera, mercado: renderMercado, operaciones: renderOperaciones, cuenta: renderCuenta }[S.tab]();
    root().innerHTML = html;
    root().querySelectorAll("[data-acc]").forEach((b) => b.onclick = async () => { S.current = +b.dataset.acc; await loadDetail(); });
    root().querySelectorAll("[data-new-acc]").forEach((b) => b.onclick = newAccount);
    root().querySelector("[data-open-trade]")?.addEventListener("click", () => { S.tab = "mercado"; selectTab(); });
    root().querySelectorAll("[data-range]").forEach((b) => b.onclick = () => {
      S.range = b.dataset.range;
      S.rangeChosen = true;
      root().querySelectorAll("[data-range]").forEach((x) => x.classList.toggle("active", x === b));
      document.querySelector("#pf-chart").innerHTML = `<div class="chart-empty">Cargando…</div>`;
      loadHistory();
    });
    root().querySelectorAll("[data-deltrade]").forEach((b) => b.onclick = async () => {
      if (!confirm("¿Borrar esta operación de tu registro?")) return;
      await api(`accounts/${S.current}/trades/${b.dataset.deltrade}`, { method: "DELETE" });
      await loadAccounts();
    });
    root().querySelectorAll("[data-del-acc]").forEach((b) => b.onclick = async () => {
      if (!confirm("¿Borrar esta cartera y todas sus operaciones? No se puede deshacer.")) return;
      await api(`accounts/${b.dataset.delAcc}`, { method: "DELETE" });
      S.current = null;
      await loadAccounts();
    });
    root().querySelector("#sim-invite")?.addEventListener("click", invite);
    root().querySelector("#sim-logout")?.addEventListener("click", async () => {
      await api("logout", { method: "POST" }); S.es?.close(); S.me = null; renderLogin();
    });
    if (S.tab === "cartera" && S.detail) {
      bindPositions();
      const a = document.querySelector("#pf-alloc"); if (a) Charts.alloc(a, allocItems());
      if (S.hist) drawPortfolioChart();
    }
    if (S.tab === "mercado") bindMercado();
  }

  async function newAccount() {
    showSheet(`<h3>Nueva cartera</h3>
      <form class="form" id="acc-form">
        <label>Nombre<input name="name" required maxlength="40" placeholder="Ej.: Trade Republic, Prueba agresiva"></label>
        <label>Tipo<select name="kind"><option value="sim">Ficticia (simulador con dinero de mentira)</option><option value="real">Real (registro de mis operaciones reales)</option></select></label>
        <label id="cash-field">Dinero ficticio inicial (€)<input name="start_cash" type="number" min="0" step="100" value="10000" inputmode="decimal"></label>
        <label>Comisión por operación (€)<input name="fee_eur" type="number" min="0" step="0.5" value="1" inputmode="decimal"></label>
        <p class="form-error" id="acc-err"></p>
        <button class="btn primary" type="submit">Crear</button>
      </form>`);
    const f = document.querySelector("#acc-form");
    f.kind.onchange = () => { document.querySelector("#cash-field").hidden = f.kind.value !== "sim"; };
    f.onsubmit = async (e) => {
      e.preventDefault();
      const v = Object.fromEntries(new FormData(f));
      try {
        await api("accounts", { method: "POST", body: { name: v.name, kind: v.kind, start_cash: +v.start_cash || 0, fee_eur: +v.fee_eur || 0 } });
        closeSheet();
        S.accounts = await api("accounts");
        S.current = S.accounts[S.accounts.length - 1].id;
        S.tab = "cartera"; selectTab();
        await loadDetail();
      } catch (err) { document.querySelector("#acc-err").textContent = err.message; }
    };
  }

  async function invite() {
    try {
      const { code } = await api("invites", { method: "POST" });
      showSheet(`<h3>Invitar a un amigo</h3>
        <p>Pásale este código y la dirección de la app. Sirve para una sola persona.</p>
        <div class="invite-code num">${esc(code)}</div>
        <button class="btn" data-copy="${esc(code)}">Copiar código</button>`);
    } catch (err) { toast(err.message); }
  }

  // Botón «Simular compra» desde las fichas de empresa del informe
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-simbuy]");
    if (!b) return;
    e.preventDefault();
    closeSheet();
    window.setMode?.("simulador");
    if (!S.me) { try { S.me = await api("me"); } catch { return toast("Inicia sesión para simular"); } }
    if (!S.detail) await loadAccounts();
    openValue(b.dataset.simbuy);
  });

  window.addEventListener("resize", () => { if (S.tab === "cartera") drawPortfolioChart(); });
  window.Sim = { show, detect, get server() { return S.server; } };
  detect();
})();
