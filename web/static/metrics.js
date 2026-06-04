/** Graficos de metricas do modelo (Chart.js) */

let charts = {};

function destroyCharts() {
  Object.values(charts).forEach((c) => c && c.destroy());
  charts = {};
}

function renderKpis(av) {
  const el = document.getElementById("metrics-kpis");
  if (!el || !av) return;
  const c = av.classificacao;
  const r = av.regressao;
  el.innerHTML = `
    <div class="kpi"><span class="kpi-label">Acuracia</span><span class="kpi-value">${(c.acuracia * 100).toFixed(1)}%</span></div>
    <div class="kpi"><span class="kpi-label">R² retorno</span><span class="kpi-value ${r.r2 < 0 ? "bad" : ""}">${r.r2.toFixed(3)}</span></div>
    <div class="kpi"><span class="kpi-label">MAE</span><span class="kpi-value">${(r.mae * 100).toFixed(2)}%</span></div>
    <div class="kpi"><span class="kpi-label">Prev. negativas</span><span class="kpi-value">${r.pct_previsto_negativo}%</span></div>
    <div class="kpi"><span class="kpi-label">Media prevista</span><span class="kpi-value">${r.media_retorno_previsto_pct >= 0 ? "+" : ""}${r.media_retorno_previsto_pct}%</span></div>
  `;
  const interp = document.getElementById("metricas-interpretacao");
  if (interp && av.interpretacao) interp.textContent = av.interpretacao;
}

function chartF1(av) {
  const data = av.graficos.acuracia_por_classe;
  const ctx = document.getElementById("chart-f1");
  if (!ctx) return;
  charts.f1 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((d) => d.classe),
      datasets: [
        { label: "F1", data: data.map((d) => d.f1), backgroundColor: "#d4a017" },
        { label: "Recall", data: data.map((d) => d.recall), backgroundColor: "#3b9eff88" },
      ],
    },
    options: { responsive: true, scales: { y: { max: 1, min: 0 } } },
  });
}

function chartConfusion(av) {
  const m = av.classificacao.matriz_confusao;
  const ctx = document.getElementById("chart-confusion");
  if (!ctx) return;
  const flat = [];
  const labels = [];
  m.valores.forEach((row, i) => {
    row.forEach((v, j) => {
      flat.push(v);
      labels.push(`${m.labels[i]} → ${m.labels[j]}`);
    });
  });
  charts.conf = new Chart(ctx, {
    type: "bar",
    data: {
      labels: m.labels,
      datasets: m.labels.map((label, j) => ({
        label: "Real: " + label,
        data: m.valores.map((row) => row[j]),
        backgroundColor: `hsl(${40 + j * 80}, 60%, 45%)`,
      })),
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: "Linha=real, cor=previsto" } },
      scales: { x: { stacked: true }, y: { stacked: true } },
    },
  });
}

function chartRetornos(av) {
  const pts = av.graficos.retorno_real_vs_previsto;
  const ctx = document.getElementById("chart-retornos");
  if (!ctx) return;
  charts.ret = new Chart(ctx, {
    type: "line",
    data: {
      labels: pts.map((_, i) => i + 1),
      datasets: [
        { label: "Real %", data: pts.map((p) => p.real_pct), borderColor: "#22c55e", tension: 0.2 },
        { label: "Previsto %", data: pts.map((p) => p.previsto_pct), borderColor: "#ef4444", tension: 0.2 },
      ],
    },
    options: { responsive: true },
  });
}

function chartDist(av) {
  const d = av.graficos.distribuicao_retorno_previsto;
  const ctx = document.getElementById("chart-dist");
  if (!ctx) return;
  charts.dist = new Chart(ctx, {
    type: "bar",
    data: {
      labels: d.map((x) => x.faixa),
      datasets: [{ label: "Frequencia", data: d.map((x) => x.contagem), backgroundColor: "#6366f1" }],
    },
    options: { responsive: true, indexAxis: "y" },
  });
}

async function loadMetricas() {
  const res = await fetch("/api/modelo/metricas");
  const data = await res.json();
  if (!data.ok || !data.avaliacao) {
    const interp = document.getElementById("metricas-interpretacao");
    if (interp) interp.textContent = data.aviso || data.error || "Treine o modelo primeiro.";
    return;
  }
  destroyCharts();
  const av = data.avaliacao;
  renderKpis(av);
  chartF1(av);
  chartConfusion(av);
  chartRetornos(av);
  chartDist(av);
}

document.getElementById("btn-recarregar-metricas")?.addEventListener("click", loadMetricas);
document.addEventListener("DOMContentLoaded", loadMetricas);

// Recarrega apos treino no pipeline
window.reloadMetricas = loadMetricas;
