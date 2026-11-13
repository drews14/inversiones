"use strict";
// Gráficas en SVG sin dependencias: línea con área y cruceta táctil, y barra de reparto apilada.
// Reglas: una sola serie por gráfica (sin leyenda, el título la nombra), líneas de 2 px,
// rejilla discreta, textos en tinta de texto (nunca del color de la serie).

const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const nf = (v, d = 2) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });

  function niceTicks(min, max, n = 3) {
    const span = max - min || Math.abs(max) || 1;
    const step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
    const make = (st) => {
      const out = [];
      for (let k = Math.ceil(min / st); k * st <= max + st * 1e-6 && out.length < 8; k++) out.push(+(k * st).toFixed(10));
      return out;
    };
    let out = make(step);
    if (out.length < 3) out = make(step / 2);   // siempre al menos 2-3 referencias
    return out;
  }

  /**
   * line(el, points, opts)
   *  points: [{t (segundos), v}]
   *  opts: { height, base (línea de referencia), fmtV(v), fmtT(t), onScrub(p|null), intraday }
   */
  function line(el, points, opts = {}) {
    el.innerHTML = "";
    el.classList.add("chart");
    if (!points || points.length < 2) {
      el.innerHTML = `<div class="chart-empty">Sin datos suficientes para este periodo</div>`;
      return;
    }
    const W = el.clientWidth || 340, H = opts.height || 200;
    const padL = 4, padR = 52, padT = 12, padB = 22;
    const vs = points.map((p) => p.v);
    let lo = Math.min(...vs), hi = Math.max(...vs);
    if (opts.base != null) { lo = Math.min(lo, opts.base); hi = Math.max(hi, opts.base); }
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.01 || 1;
    lo -= pad; hi += pad;
    const t0 = points[0].t, t1 = points[points.length - 1].t;
    // eje X por índice (sin huecos de fines de semana / noches)
    const x = (i) => padL + (i / (points.length - 1)) * (W - padL - padR);
    const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
    const up = points[points.length - 1].v >= (opts.base ?? points[0].v);
    const color = up ? "var(--up)" : "var(--down)";
    const fmtV = opts.fmtV || ((v) => nf(v));
    const fmtT = opts.fmtT || ((t) => new Date(t * 1000).toLocaleDateString("es-ES", { day: "numeric", month: "short" }));

    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("width", W);
    svg.setAttribute("height", H);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", opts.label || "Gráfica");
    const id = "g" + Math.random().toString(36).slice(2, 8);
    let html = `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".18"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
    // rejilla + etiquetas eje Y (derecha)
    for (const tv of niceTicks(lo, hi, 3)) {
      const yy = y(tv).toFixed(1);
      html += `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}" class="c-grid"/>
        <text x="${W - padR + 6}" y="${yy}" class="c-axis" dominant-baseline="middle">${fmtV(tv)}</text>`;
    }
    // etiquetas eje X: inicio, medio, fin
    const seen = new Set();
    const idx = points.length >= 5 ? [0, Math.floor((points.length - 1) / 2), points.length - 1] : [0, points.length - 1];
    idx.forEach((i, k) => {
      const lab = fmtT(points[i].t);
      if (seen.has(lab)) return;
      seen.add(lab);
      const anchor = i === 0 ? "start" : i === points.length - 1 ? "end" : "middle";
      html += `<text x="${x(i)}" y="${H - 6}" class="c-axis" text-anchor="${anchor}">${lab}</text>`;
    });
    if (opts.base != null) {
      const yb = y(opts.base).toFixed(1);
      html += `<line x1="${padL}" x2="${W - padR}" y1="${yb}" y2="${yb}" class="c-base"/>`;
    }
    const d = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    html += `<path d="${d}L${x(points.length - 1).toFixed(1)},${H - padB}L${x(0).toFixed(1)},${H - padB}Z" fill="url(#${id})"/>
      <path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      <g class="c-cross" visibility="hidden"><line class="c-cross-line" y1="${padT}" y2="${H - padB}"/>
        <circle r="5" class="c-dot" stroke="${color}"/></g>`;
    svg.innerHTML = html;
    el.appendChild(svg);
    const tip = document.createElement("div");
    tip.className = "c-tip";
    tip.hidden = true;
    el.appendChild(tip);

    // cruceta: el área de toque es toda la gráfica (más grande que la línea)
    const cross = svg.querySelector(".c-cross"), cl = cross.querySelector("line"), dot = cross.querySelector("circle");
    const at = (clientX) => {
      const r = svg.getBoundingClientRect();
      const px = ((clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(points.length - 1, Math.round(((px - padL) / (W - padL - padR)) * (points.length - 1))));
      const p = points[i];
      cross.setAttribute("visibility", "visible");
      cl.setAttribute("x1", x(i)); cl.setAttribute("x2", x(i));
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(p.v));
      tip.hidden = false;
      tip.textContent = `${fmtV(p.v)} · ${opts.tipT ? opts.tipT(p.t) : fmtT(p.t)}`;
      const left = Math.min(Math.max((x(i) / W) * r.width - tip.offsetWidth / 2, 0), r.width - tip.offsetWidth);
      tip.style.left = `${left}px`;
      opts.onScrub?.(p, i);
    };
    const leave = () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; opts.onScrub?.(null); };
    svg.addEventListener("pointerdown", (e) => { at(e.clientX); });
    svg.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse" || e.buttons || e.pressure) at(e.clientX); });
    svg.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") leave(); });
    svg.addEventListener("pointercancel", leave);
    svg.addEventListener("pointerleave", leave);
    svg.addEventListener("touchmove", (e) => { if (e.touches[0]) at(e.touches[0].clientX); }, { passive: true });
    return { up };
  }

  /**
   * alloc(el, items): barra apilada al 100 % + leyenda con nombre y porcentaje.
   *  items: [{label, value, slot (1-8) | null para gris}]
   */
  function alloc(el, items) {
    const total = items.reduce((a, b) => a + Math.max(0, b.value), 0);
    if (!total) { el.innerHTML = ""; return; }
    const seg = items.filter((i) => i.value > 0).map((i) => {
      const pctv = (i.value / total) * 100;
      return `<i style="width:${pctv}%;background:${i.slot ? `var(--c${i.slot})` : "var(--c-neutral)"}" title="${i.label}"></i>`;
    }).join("");
    const legend = items.filter((i) => i.value > 0).map((i) => `<li><span class="sw" style="background:${i.slot ? `var(--c${i.slot})` : "var(--c-neutral)"}"></span>
      <span class="lg-name">${i.label}</span><span class="lg-val num">${nf((i.value / total) * 100, 1)} %</span></li>`).join("");
    el.innerHTML = `<div class="alloc-bar" role="img" aria-label="Reparto de la cartera">${seg}</div><ul class="alloc-legend">${legend}</ul>`;
  }

  return { line, alloc };
})();
