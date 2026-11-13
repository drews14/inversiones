"use strict";
// Simulador y carteras: solo funciona cuando la app se sirve desde el servidor propio (no en GitHub Pages).
(() => {
  const API = "api/";
  const S = { server: false, me: null, accounts: [], current: null, detail: null, quotes: {}, es: null, watch: [] };
  const el = () => document.querySelector("#tab-simulador");
  const eur = (v, d = 2) => (v == null ? "—" : `${fmt(v, d)} €`);
  const signed = (v, d = 2) => (v == null ? "—" : `${v > 0 ? "+" : ""}${fmt(v, d)} €`);

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
    document.querySelector("#tab-btn-sim").hidden = !S.server;
    document.body.classList.toggle("has-server", S.server);
  }

  async function show() {
    if (!S.server) return;
    try {
      S.me = await api("me");
    } catch (e) {
      S.me = null;
      return renderLogin();
    }
    await loadAccounts();
  }

  async function loadAccounts() {
    S.accounts = await api("accounts");
    if (!S.current || !S.accounts.some((a) => a.id === S.current)) S.current = S.accounts[0]?.id;
    await loadDetail();
  }

  async function loadDetail() {
    if (!S.current) return render();
    S.detail = await api(`accounts/${S.current}`);
    for (const p of S.detail.positions) if (p.quote) S.quotes[p.ticker] = p.quote;
    render();
    startStream();
  }

  // ---------------------------------------------------------------- precios en directo (SSE)
  function startStream() {
    if (S.es) S.es.close();
    const extra = S.watch.join(",");
    S.es = new EventSource(`${API}stream?tickers=${encodeURIComponent(extra)}`);
    S.es.onmessage = (ev) => {
      try {
        Object.assign(S.quotes, JSON.parse(ev.data));
        updateLive();
      } catch {}
    };
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && S.es) { S.es.close(); S.es = null; }
    else if (document.visibilityState === "visible" && S.me && S.detail) startStream();
  });

  function liveBadge(q) {
    if (!q) return "";
    return q.realtime ? `<span class="live on">En directo</span>` : `<span class="live">~15 min</span>`;
  }

  // Recalcula valores con la última cotización sin pedir nada al servidor
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
    if (!S.detail || document.querySelector("#tab-simulador:not(.active)")) return;
    recalc();
    const sum = document.querySelector("#sim-summary");
    if (sum) sum.outerHTML = summaryHtml();
    const list = document.querySelector("#sim-positions");
    if (list) { list.outerHTML = positionsHtml(); bindPositions(); }
    const tq = document.querySelector("#trade-quote");
    if (tq && tq.dataset.ticker && S.quotes[tq.dataset.ticker]) tq.innerHTML = quoteHtml(S.quotes[tq.dataset.ticker]);
  }

  // ---------------------------------------------------------------- login / registro
  function renderLogin(mode = "login", msg = "") {
    el().innerHTML = `<h2>${mode === "login" ? "Inicia sesión" : "Crear cuenta con invitación"}</h2>
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
      const f = Object.fromEntries(new FormData(e.target));
      try {
        await api(mode === "login" ? "login" : "register", { method: "POST", body: f });
        await show();
      } catch (err) { renderLogin(mode, err.message); }
    };
  }

  // ---------------------------------------------------------------- vista principal
  function summaryHtml() {
    const d = S.detail;
    return `<div class="card sim-summary" id="sim-summary">
      <div class="sim-total"><small>${d.kind === "sim" ? "Valor de la cartera" : "Valor de tus acciones"}</small>
        <b class="num">${eur(d.total)}</b>
        <span class="num ${cls(d.pnl_total)}">${signed(d.pnl_total)} (${pct(d.pnl_total_pct, 2)})</span></div>
      <div class="sim-grid num">
        ${d.kind === "sim" ? `<div><small>Efectivo</small>${eur(d.cash)}</div>` : `<div><small>Invertido</small>${eur(d.invested)}</div>`}
        <div><small>En acciones</small>${eur(d.positions_value)}</div>
        <div><small>Ganancia abierta</small><span class="${cls(d.pnl_open)}">${signed(d.positions_value - d.invested)}</span></div>
        <div><small>Ya realizada</small><span class="${cls(d.pnl_realized)}">${signed(d.pnl_realized)}</span></div>
      </div>
      ${d.kind === "sim" ? `<small class="muted">Empezaste con ${eur(d.start_cash, 0)} ficticios · comisión ${eur(d.fee_eur)} por operación</small>` : `<small class="muted">Registro de tus operaciones reales · comisiones pagadas ${eur(d.fees)}</small>`}
    </div>`;
  }

  function positionsHtml() {
    const d = S.detail;
    if (!d.positions.length) return `<div class="card empty" id="sim-positions">Todavía no tienes acciones en esta cartera.</div>`;
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
        </div>
        <div class="opp-name num" style="margin-top:4px">Ahora ${q ? money(q.price, q.currency) : "—"} ${q && q.chg_day != null ? `<span class="${cls(q.chg_day)}">${pct(q.chg_day, 2)} hoy</span>` : ""}</div>
        </div></button>`;
    }).join("")}</div>`;
  }

  function bindPositions() {
    document.querySelectorAll("#sim-positions .pos").forEach((b) => b.addEventListener("click", () => {
      const p = S.detail.positions[+b.dataset.i];
      openTrade(p.ticker, p.name);
    }));
  }

  function render() {
    const d = S.detail;
    const accs = S.accounts.map((a) => `<button class="acc-chip ${a.id === S.current ? "active" : ""}" data-acc="${a.id}">
      ${esc(a.name)} <span class="kind ${a.kind}">${a.kind === "sim" ? "Ficticia" : "Real"}</span></button>`).join("");
    el().innerHTML = `
      <div class="acc-row">${accs}<button class="acc-chip add" id="acc-new">+ Nueva</button></div>
      ${d ? `${summaryHtml()}
        <div class="sim-actions"><button class="btn primary" id="sim-buy">${d.kind === "sim" ? "Comprar (simulado)" : "Apuntar compra o venta"}</button></div>
        <h2>Posiciones</h2>${positionsHtml()}
        <h2>Operaciones</h2>${tradesHtml()}` : `<div class="card empty">Crea una cartera para empezar.</div>`}
      <div class="sim-foot">
        <span class="muted">Sesión: ${esc(S.me.username)}</span>
        ${S.me.is_admin ? `<button class="link" id="sim-invite">Invitar a un amigo</button>` : ""}
        ${d && d.kind === "real" ? `<button class="link danger" id="acc-del">Borrar esta cartera</button>` : ""}
        <button class="link" id="sim-logout">Cerrar sesión</button>
      </div>
      <p class="disclaimer">EE. UU. y divisas en directo; Europa y Japón con unos 15 minutos de retraso (Yahoo Finance). Las carteras ficticias no mueven dinero real.</p>`;
    el().querySelectorAll("[data-acc]").forEach((b) => b.onclick = async () => { S.current = +b.dataset.acc; await loadDetail(); });
    document.querySelector("#acc-new").onclick = newAccount;
    document.querySelector("#sim-buy")?.addEventListener("click", () => openTrade());
    document.querySelector("#sim-logout").onclick = async () => { await api("logout", { method: "POST" }); S.es?.close(); S.me = null; renderLogin(); };
    document.querySelector("#sim-invite")?.addEventListener("click", invite);
    document.querySelector("#acc-del")?.addEventListener("click", deleteAccount);
    bindPositions();
    el().querySelectorAll("[data-deltrade]").forEach((b) => b.onclick = async () => {
      if (!confirm("¿Borrar esta operación de tu registro?")) return;
      await api(`accounts/${S.current}/trades/${b.dataset.deltrade}`, { method: "DELETE" });
      await loadAccounts();
    });
  }

  function tradesHtml() {
    const t = S.detail.trades || [];
    if (!t.length) return `<div class="card empty">Sin operaciones todavía.</div>`;
    return `<div class="list">${t.slice(0, 50).map((x) => `<div class="row trade">
      <div class="label"><b class="${x.side === "buy" ? "up" : "down"}">${x.side === "buy" ? "Compra" : "Venta"}</b> ${esc(x.ticker)}
        <small>${new Date(x.ts * 1000).toLocaleString("es-ES", { day: "numeric", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit" })}${x.note ? " · " + esc(x.note) : ""}</small></div>
      <div class="val num">${fmt(x.qty, x.qty % 1 ? 4 : 0)} × ${money(x.price, x.currency)}<small class="muted">${eur((x.qty * x.price) / x.fx_eur)}</small></div>
      ${S.detail.kind === "real" ? `<button class="link danger" data-deltrade="${x.id}" aria-label="Borrar">×</button>` : ""}
    </div>`).join("")}</div>`;
  }

  // ---------------------------------------------------------------- acciones
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
        S.current = null;
        await loadAccounts();
        S.current = S.accounts[S.accounts.length - 1].id;
        await loadDetail();
      } catch (err) { document.querySelector("#acc-err").textContent = err.message; }
    };
  }

  async function deleteAccount() {
    if (!confirm("¿Borrar esta cartera y todas sus operaciones? No se puede deshacer.")) return;
    await api(`accounts/${S.current}`, { method: "DELETE" });
    S.current = null;
    await loadAccounts();
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

  function quoteHtml(q) {
    return `<div class="tq-top"><b>${esc(q.ticker)}</b> ${liveBadge(q)}<div class="muted">${esc(q.name || "")}</div></div>
      <div class="tq-price num">${money(q.price, q.currency)} ${q.chg_day != null ? `<span class="${cls(q.chg_day)}">${pct(q.chg_day, 2)} hoy</span>` : ""}</div>
      ${q.currency !== "EUR" && q.price_eur != null ? `<div class="muted num">≈ ${eur(q.price_eur)} por acción (cambio ${fmt(q.fx_eur, 4)} ${esc(q.currency)}/€)</div>` : ""}`;
  }

  async function openTrade(ticker, name) {
    const d = S.detail;
    if (!d) return toast("Crea primero una cartera");
    const real = d.kind === "real";
    showSheet(`<h3>${real ? "Apuntar operación real" : "Operación simulada"} · ${esc(d.name)}</h3>
      ${ticker ? "" : `<label class="form">Buscar empresa o ETF<input id="t-search" placeholder="Nombre o ticker: Apple, Inditex, ADS.DE…" autocomplete="off"></label>
      <div class="list" id="t-results"></div>`}
      <div class="card" id="trade-quote" data-ticker="${esc(ticker || "")}" ${ticker ? "" : "hidden"}></div>
      <form class="form" id="trade-form" ${ticker ? "" : "hidden"}>
        <div class="seg"><button type="button" data-side="buy" class="active">Comprar</button><button type="button" data-side="sell">Vender</button></div>
        <div class="seg seg-small"><button type="button" data-how="eur" class="active">Importe en €</button><button type="button" data-how="qty">Nº de acciones</button></div>
        <label id="f-amount">Importe (€)<input name="amount" type="number" min="0" step="any" inputmode="decimal" placeholder="Ej.: 500"></label>
        <label id="f-qty" hidden>Acciones<input name="qty" type="number" min="0" step="any" inputmode="decimal" placeholder="Ej.: 3"></label>
        ${real ? `<label>Precio al que operaste (en su moneda, vacío = precio actual)<input name="price" type="number" min="0" step="any" inputmode="decimal"></label>
          <label>Fecha<input name="date" type="date"></label>` : ""}
        <label>Nota (opcional)<input name="note" maxlength="200" placeholder="Por qué compro / vendo"></label>
        <p class="muted" id="t-estimate"></p>
        <p class="form-error" id="t-err"></p>
        <button class="btn primary" type="submit" id="t-submit">${real ? "Guardar operación" : "Confirmar operación simulada"}</button>
        ${real ? "" : `<p class="muted" style="font-size:13px">Se ejecuta al precio de mercado actual y se cobra la comisión de ${eur(d.fee_eur)}. No es dinero real.</p>`}
      </form>`);
    let side = "buy", how = "eur", current = ticker;
    const form = document.querySelector("#trade-form");
    const setTicker = async (t) => {
      current = t;
      const box = document.querySelector("#trade-quote");
      box.hidden = false; box.dataset.ticker = t; box.innerHTML = `<span class="muted">Cargando precio…</span>`;
      try {
        const q = await api(`quote/${encodeURIComponent(t)}`);
        S.quotes[t] = q; box.innerHTML = quoteHtml(q); form.hidden = false;
        if (!S.watch.includes(t)) { S.watch.push(t); startStream(); }
        estimate();
      } catch (err) { box.innerHTML = `<span class="form-error">${esc(err.message)}</span>`; }
    };
    const estimate = () => {
      const q = S.quotes[current], out = document.querySelector("#t-estimate");
      if (!q || !q.price_eur) return (out.textContent = "");
      const v = parseFloat((how === "eur" ? form.amount : form.qty).value);
      if (!v) return (out.textContent = "");
      const priceEur = real && form.price?.value ? parseFloat(form.price.value) / q.fx_eur : q.price_eur;
      out.textContent = how === "eur" ? `≈ ${fmt(v / priceEur, 4)} acciones + ${eur(d.fee_eur)} de comisión` : `≈ ${eur(v * priceEur)} + ${eur(d.fee_eur)} de comisión`;
    };
    if (ticker) setTicker(ticker);
    const search = document.querySelector("#t-search");
    if (search) {
      let timer;
      search.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
          const q = search.value.trim(), box = document.querySelector("#t-results");
          if (q.length < 2) return (box.innerHTML = "");
          try {
            const res = await api(`search?q=${encodeURIComponent(q)}`);
            box.innerHTML = res.length ? res.map((r) => `<button class="row" data-t="${esc(r.ticker)}" style="width:100%;text-align:left">
              <div class="label"><b>${esc(r.ticker)}</b> ${esc(r.name)}<small>${esc(r.exchange || "")} · ${r.type === "ETF" ? "ETF" : "Acción"}</small></div><div class="val muted">›</div></button>`).join("")
              : `<div class="row muted">Sin resultados</div>`;
            box.querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { box.innerHTML = ""; search.value = b.dataset.t; setTicker(b.dataset.t); });
          } catch (err) { box.innerHTML = `<div class="row form-error">${esc(err.message)}</div>`; }
        }, 350);
      };
      search.focus();
    }
    form.querySelectorAll("[data-side]").forEach((b) => b.onclick = () => {
      side = b.dataset.side; form.querySelectorAll("[data-side]").forEach((x) => x.classList.toggle("active", x === b));
    });
    form.querySelectorAll("[data-how]").forEach((b) => b.onclick = () => {
      how = b.dataset.how; form.querySelectorAll("[data-how]").forEach((x) => x.classList.toggle("active", x === b));
      document.querySelector("#f-amount").hidden = how !== "eur"; document.querySelector("#f-qty").hidden = how !== "qty"; estimate();
    });
    form.oninput = estimate;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const v = Object.fromEntries(new FormData(form));
      const body = { ticker: current, side, note: v.note || null };
      if (how === "eur") body.amount_eur = parseFloat(v.amount); else body.qty = parseFloat(v.qty);
      if (real) { if (v.price) body.price = parseFloat(v.price); if (v.date) body.date = v.date; }
      const btn = document.querySelector("#t-submit"); btn.disabled = true;
      try {
        const r = await api(`accounts/${S.current}/trades`, { method: "POST", body });
        closeSheet();
        toast(`${side === "buy" ? "Compra" : "Venta"}: ${fmt(r.qty, r.qty % 1 ? 4 : 0)} ${r.ticker} a ${money(r.price, r.currency)}`);
        await loadAccounts();
      } catch (err) { document.querySelector("#t-err").textContent = err.message; btn.disabled = false; }
    };
  }

  // Botón «Simular compra» desde las fichas de empresa del informe
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-simbuy]");
    if (!b) return;
    e.preventDefault();
    if (!S.me) { try { S.me = await api("me"); } catch { closeSheet(); setTab("simulador"); return toast("Inicia sesión para simular"); } }
    if (!S.detail) await loadAccounts();
    openTrade(b.dataset.simbuy);
  });

  window.Sim = { show, detect, get server() { return S.server; } };
  detect();
})();
