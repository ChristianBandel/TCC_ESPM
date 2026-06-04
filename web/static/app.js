const logEl = () => document.getElementById("log");
const cenariosEl = () => document.getElementById("cenarios-list");
const resultEl = () => document.getElementById("result-panel");

let cenariosCache = [];
let selectedIdx = -1;
let precoAtual = null;

function getPrecoParaPrevisao() {
  const manual = document.getElementById("preco-manual").value;
  if (manual !== "" && !isNaN(parseFloat(manual))) return parseFloat(manual);
  return precoAtual;
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

function setLog(text, isError) {
  const el = logEl();
  el.textContent = text || "";
  el.style.color = isError ? "#f87171" : "";
}

async function loadStatus() {
  const res = await fetch("/api/status");
  const s = await res.json();
  document.getElementById("badge-models").textContent = s.modelos
    ? "Modelos treinados"
    : "Modelos pendentes";
  document.getElementById("badge-models").className = "badge " + (s.modelos ? "ok" : "warn");
  document.getElementById("badge-groq").textContent = s.groq
    ? "Groq conectado"
    : "Groq: modo aleatorio";
  document.getElementById("badge-groq").className = "badge " + (s.groq ? "ok" : "");
  if (s.preco_atual) aplicarPreco(s.preco_atual);
}

async function atualizarPreco() {
  const res = await fetch("/api/preco-atual");
  const data = await res.json();
  if (data.ok) aplicarPreco(data);
  else setLog(data.error, true);
}

function aplicarPreco(info) {
  precoAtual = info.preco_usd;
  const inp = document.getElementById("preco-manual");
  if (!inp.value) inp.value = info.preco_usd.toFixed(2);
  const fonte = info.fonte === "oil_price_api_latest" ? "API ao vivo" : "Dataset semanal";
  document.getElementById("badge-preco").textContent = "Brent: $" + info.preco_usd.toFixed(2);
  document.getElementById("preco-fonte").textContent =
    fonte +
    (info.atualizado_em ? " · " + String(info.atualizado_em).slice(0, 19) : "") +
    (info.aviso ? " · " + info.aviso : "");
}

async function runPipeline(action) {
  setLog("Executando " + action + "...");
  const data = await api("/api/run", { action });
  setLog(data.output || data.error || JSON.stringify(data, null, 2), !data.ok);
  if (data.ok) {
    loadStatus();
    if (action === "modelagem" || action === "pipeline") {
      window.reloadMetricas?.();
    }
  }
}

async function gerarCenarios() {
  const qtd = parseInt(document.getElementById("qtd-cenarios").value, 10) || 3;
  const modo = document.getElementById("modo-geracao").value;
  const tema = document.getElementById("tema-groq").value.trim();
  const list = cenariosEl();
  list.innerHTML = '<div class="empty-cenarios"><span class="loading"></span>Gerando cenarios...</div>';
  setLog("Gerando cenarios (" + modo + ")...");

  const data = await api("/api/cenarios/gerar", {
    quantidade: qtd,
    modo,
    tema: tema || null,
  });

  if (!data.ok) {
    list.innerHTML = '<div class="empty-cenarios">' + (data.error || "Erro") + "</div>";
    setLog(data.error, true);
    return;
  }

  cenariosCache = data.cenarios || [];
  setLog("Fonte: " + data.fonte + " | " + cenariosCache.length + " cenarios");
  renderCenarios();
}

function renderCenarios() {
  const list = cenariosEl();
  if (!cenariosCache.length) {
    list.innerHTML =
      '<div class="empty-cenarios">Clique em <strong>Gerar com IA</strong> ou <strong>Aleatorio</strong></div>';
    return;
  }
  list.innerHTML = cenariosCache
    .map(
      (c, i) => `
    <div class="cenario-card ${i === selectedIdx ? "selected" : ""}" data-idx="${i}">
      <h3>${escapeHtml(c.titulo || c.pais)}</h3>
      <div class="cenario-meta">
        <span class="tag">${escapeHtml(c.pais)}</span>
        <span class="tag">${escapeHtml(c.regiao)}</span>
        <span class="tag ${c.intensidade}">${c.intensidade}</span>
        <span class="tag">${escapeHtml(c.sentimento || "")}</span>
        ${c.probabilidade_escalada_pct != null ? `<span class="tag">escalada ${c.probabilidade_escalada_pct}%</span>` : ""}
        <span class="tag">~${c.eventos || "?"} ev / ${c.mortes || "?"} mortes</span>
      </div>
      <p style="margin-top:0.5rem;font-size:0.8rem;color:var(--muted)">${escapeHtml(c.raciocinio || "")}</p>
    </div>`
    )
    .join("");

  list.querySelectorAll(".cenario-card").forEach((el) => {
    el.addEventListener("click", () => {
      selectedIdx = parseInt(el.dataset.idx, 10);
      renderCenarios();
      preverUm(selectedIdx);
    });
  });
}

async function preverUm(idx) {
  if (idx < 0 || !cenariosCache[idx]) return;
  const panel = resultEl();
  panel.classList.add("visible");
  panel.innerHTML = '<span class="loading"></span> Rodando modelo ML...';
  const body = { cenario: cenariosCache[idx] };
  const p = getPrecoParaPrevisao();
  if (p != null) body.preco_atual = p;
  const data = await api("/api/cenarios/prever", body);
  if (!data.ok) {
    panel.innerHTML = "<p style='color:#f87171'>" + escapeHtml(data.error) + "</p>";
    return;
  }
  renderResultado(data.resultado);
}

async function preverTodos() {
  if (!cenariosCache.length) {
    setLog("Gere cenarios primeiro.", true);
    return;
  }
  setLog("Prevendo todos os cenarios...");
  const body = { cenarios: cenariosCache };
  const p = getPrecoParaPrevisao();
  if (p != null) body.preco_atual = p;
  const data = await api("/api/cenarios/prever-todos", body);
  if (!data.ok) {
    setLog(data.error, true);
    return;
  }
  const panel = resultEl();
  panel.classList.add("visible");
  panel.innerHTML = data.resultados
    .map((r) => {
      const p = r.petroleo;
      const c = r.cenario;
      const pm = r.parametros_ml || {};
      return `<div style="margin-bottom:1rem;padding-bottom:1rem;border-bottom:1px solid var(--border)">
        <strong>${escapeHtml(c.titulo || c.pais)}</strong>
        <span class="vol-badge ${p.classe_volatilidade_prevista}">${p.classe_volatilidade_prevista}</span>
        <span style="color:var(--muted);font-size:0.85rem"> $${p.preco_atual_usd} → $${p.preco_projetado_4_semanas_usd} (${p.retorno_esperado_4_semanas_pct}%)</span>
        <span style="display:block;font-size:0.75rem;color:var(--muted)">${pm.eventos || "?"} ev, ${pm.mortes || "?"} mortes, ${pm.intensidade || ""}</span>
      </div>`;
    })
    .join("");
  setLog("Previsoes concluidas para " + data.resultados.length + " cenarios.");
}

function renderResultado(r) {
  const p = r.petroleo;
  const c = r.cenario;
  const vol = p.classe_volatilidade_prevista;
  let probHtml = "";
  if (p.probabilidades && Object.keys(p.probabilidades).length) {
    probHtml =
      '<div class="prob-bars">' +
      Object.entries(p.probabilidades)
        .map(
          ([k, v]) => `
        <div class="prob-row"><span>${k}</span>
          <div class="prob-bar"><div class="prob-fill" style="width:${Math.round(v * 100)}%"></div></div>
          <span>${Math.round(v * 100)}%</span></div>`
        )
        .join("") +
      "</div>";
  }
  const aviso =
    p.dataset_ultimo_preco && Math.abs(p.preco_atual_usd - p.dataset_ultimo_preco) > 1
      ? `<p class="preco-aviso">Dataset tinha $${p.dataset_ultimo_preco} (${p.dataset_ultima_semana || "semanal"}). Usando ${p.preco_referencia_fonte || "referencia atual"}.</p>`
      : "";
  const pm = r.parametros_ml || {};
  const paramsHtml = pm.eventos
    ? `<p style="font-size:0.8rem;color:var(--muted)">ML: ${pm.eventos} eventos/sem, ${pm.mortes} mortes, intensidade ${pm.intensidade}</p>`
    : "";
  resultEl().innerHTML = `
    <h3 style="margin-bottom:0.5rem">${escapeHtml(c.titulo || c.pais)}</h3>
    <span class="vol-badge ${vol}">Volatilidade ${vol}</span>
    ${aviso}${paramsHtml}
    <div class="price-row">
      <div class="price-box"><div class="label">Brent atual</div><div class="value">$${p.preco_atual_usd}</div></div>
      <div class="price-box"><div class="label">Projecao ~4 sem.</div><div class="value">$${p.preco_projetado_4_semanas_usd}</div></div>
      <div class="price-box"><div class="label">Retorno esperado</div><div class="value" style="color:${p.retorno_esperado_4_semanas_pct >= 0 ? "var(--ok)" : "var(--danger)"}">${p.retorno_esperado_4_semanas_pct}%</div></div>
    </div>
    ${probHtml}
    <p style="margin-top:0.75rem;font-size:0.85rem;color:var(--muted)">${escapeHtml(r.interpretacao)}</p>
    ${c.raciocinio ? `<p style="margin-top:0.5rem;font-size:0.8rem">${escapeHtml(c.raciocinio)}</p>` : ""}
  `;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

document.getElementById("btn-petroleo").addEventListener("click", () => runPipeline("coleta_petroleo"));
document.getElementById("btn-conflitos").addEventListener("click", () => runPipeline("coleta_conflitos"));
document.getElementById("btn-indicadores").addEventListener("click", () => runPipeline("coleta_indicadores"));
document.getElementById("btn-preparar").addEventListener("click", () => runPipeline("preparacao"));
document.getElementById("btn-treinar").addEventListener("click", () => runPipeline("modelagem"));
document.getElementById("btn-pipeline").addEventListener("click", () => runPipeline("pipeline"));
document.getElementById("btn-gerar-groq").addEventListener("click", () => {
  document.getElementById("modo-geracao").value = "groq";
  gerarCenarios();
});
document.getElementById("btn-gerar-auto").addEventListener("click", () => {
  document.getElementById("modo-geracao").value = "auto";
  gerarCenarios();
});
document.getElementById("btn-gerar-rand").addEventListener("click", () => {
  document.getElementById("modo-geracao").value = "aleatorio";
  gerarCenarios();
});
document.getElementById("btn-prever-todos").addEventListener("click", preverTodos);
document.getElementById("btn-atualizar-preco").addEventListener("click", atualizarPreco);

loadStatus();
atualizarPreco();
