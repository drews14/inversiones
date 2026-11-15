"use strict";
// Resumen del día listo para pegar en WhatsApp (formato *negrita* y _cursiva_ de WhatsApp, sin emojis).

const WA = (() => {
  const pc = (v, d = 1) => (v == null ? "" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d).replace(".", ",")} %`);
  const cleanName = (o) => (o.short || String(o.name).replace(/,? (Inc\.?|Corporation|Corp\.?|S\.A\.?|plc|Ltd\.?|Group)$/i, "")).trim();
  const COUNTRY = { US: "EE. UU.", ES: "España", JP: "Japón" };
  const MOMENT = { giro: "parece que deja de caer", vigilar: "vigilar, aún sin confirmar", esperar: "mejor esperar, sigue cayendo" };

  function appUrl() {
    const here = location.origin + location.pathname.replace(/index\.html$/, "");
    return here.startsWith("http") ? here : "https://drews14.github.io/inversiones/";
  }

  function text(r) {
    const d = new Date(r.generated_at);
    const day = d.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
    const L = [`*Resumen de bolsa · ${day}*`, ""];

    // Mercado
    const bm = r.basic_market || { lines: [] };
    const idx = (r.markets || []).filter((m) => ["^GSPC", "^NDX", "^IBEX", "^N225"].includes(m.ticker));
    L.push("*Cómo está el mercado*");
    if (idx.length) L.push(idx.map((m) => `${m.label} ${pc(m.chg1d)}`).join(" · "));
    if (r.sentiment) L.push(`Ambiente: ${r.sentiment.label.toLowerCase()} (${r.sentiment.value}/100)`);
    bm.lines.slice(0, 3).forEach((l) => L.push(`- ${l}`));
    L.push("");

    // Oportunidades / posibles subidas
    const top = (r.top || []).slice(0, 5);
    L.push("*Posibles subidas: oportunidades del día*");
    if (!top.length) L.push("Hoy ninguna empresa destaca claramente.");
    top.forEach((o, i) => {
      const parts = [`${i + 1}. *${cleanName(o)}* (${COUNTRY[o.market] || o.market}) · nota ${Math.round(o.score)}/100`];
      if (o.upside != null && o.analysts) parts.push(`los analistas le ven ${pc(o.upside, 0)}`);
      const m = MOMENT[o.timing?.label];
      if (m) parts.push(m);
      L.push(parts.join(" · "));
    });
    L.push("");

    // Riesgo de caída fuerte
    const risk = (r.risk_top || []).filter((o) => o.risk && o.risk.score >= 55).slice(0, 5);
    if (risk.length) {
      L.push("*Cuidado: empiezan a caer*");
      risk.forEach((o) => {
        const why = (o.risk.plain || o.risk.signals || [])[0];
        L.push(`- *${cleanName(o)}* (${COUNTRY[o.market] || o.market})${why ? `: ${why.replace(/\.$/, "").toLowerCase()}` : ""}`);
      });
      L.push("");
    }

    // Avisos: resultados próximos y caídas muy bruscas
    const warn = new Map();  // una línea por empresa y tipo de aviso
    for (const o of [...(r.top || []).slice(0, 5), ...risk]) {
      for (const f of [...(o.flags || []), ...((o.risk && o.risk.flags) || [])]) {
        const days = (f.match(/resultados en (\d+) d/i) || [])[1];
        if (/resultados/i.test(f)) warn.set(o.ticker + "r", `${cleanName(o)}: presenta resultados${days ? ` en ${days} días` : " pronto"}, puede moverse mucho`);
        else if (/cuchillo/i.test(f)) warn.set(o.ticker + "c", `${cleanName(o)}: ha caído más de un 25 % en un mes, puede seguir bajando`);
      }
    }
    if (warn.size) {
      L.push("*Ojo esta semana*");
      [...warn.values()].slice(0, 4).forEach((w) => L.push(`- ${w}`));
      L.push("");
    }

    // Noticias
    const news = (r.basic_news || []).slice(0, 3);
    if (news.length) {
      L.push("*Noticias*");
      news.forEach((n) => L.push(`- ${n.title}`));
      L.push("");
    }

    L.push("_Nadie puede predecir la bolsa: son señales para vigilar, no consejos de inversión. Revisa antes de comprar._");
    L.push(`Más detalle: ${appUrl()}`);
    return L.join("\n");
  }

  function open(r) {
    const t = text(r);
    const body = document.getElementById("sheet-body");
    body.innerHTML = `<h2 style="margin-top:4px">Resumen para WhatsApp</h2>
      <p class="muted" style="font-size:14px">Pulsa el botón verde, elige el grupo de tus amigos y envía.</p>
      <a class="btn primary" href="https://wa.me/?text=${encodeURIComponent(t)}">Enviar por WhatsApp</a>
      <div class="btn-row" style="margin-top:8px"><button class="btn" data-wa-copy>Copiar texto</button>
        ${navigator.share ? `<button class="btn" data-wa-share>Más opciones</button>` : ""}</div>
      <pre class="wa-preview">${t.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>`;
    body.querySelector("[data-wa-copy]").addEventListener("click", (e) => {
      copyText(t);
      e.currentTarget.textContent = "Copiado";
    });
    body.querySelector("[data-wa-share]")?.addEventListener("click", () => navigator.share({ text: t }).catch(() => {}));
    openSheetShell();
  }

  return { text, open };
})();
