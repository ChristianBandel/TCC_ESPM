"""Metricas e artefatos para avaliacao / graficos do modelo."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    r2_score,
)


def avaliar_modelos(
    yc_test: pd.Series,
    pred_c: np.ndarray,
    yr_test: pd.Series,
    pred_r: np.ndarray,
    classes_ordem: list[str] | None = None,
) -> dict[str, Any]:
    classes = list(classes_ordem or sorted(set(yc_test.astype(str)) | set(pred_c.astype(str))))
    cm = confusion_matrix(yc_test.astype(str), pred_c.astype(str), labels=classes)
    report = classification_report(yc_test, pred_c, labels=classes, zero_division=0, output_dict=True)

    acc = float(accuracy_score(yc_test, pred_c))
    mae = float(mean_absolute_error(yr_test, pred_r))
    r2 = float(r2_score(yr_test, pred_r))

    media_retorno_teste = float(yr_test.mean())
    pred_media = float(np.mean(pred_r))
    pred_negativos_pct = float((pred_r < 0).mean() * 100)
    real_negativos_pct = float((yr_test < 0).mean() * 100)

    baseline_mae = float(mean_absolute_error(yr_test, np.full_like(yr_test, media_retorno_teste)))
    baseline_r2 = 0.0

    return {
        "classificacao": {
            "acuracia": round(acc, 4),
            "matriz_confusao": {
                "labels": classes,
                "valores": cm.tolist(),
            },
            "por_classe": {
                k: {
                    "precision": round(v.get("precision", 0), 4),
                    "recall": round(v.get("recall", 0), 4),
                    "f1": round(v.get("f1-score", 0), 4),
                    "support": int(v.get("support", 0)),
                }
                for k, v in report.items()
                if k in classes
            },
            "macro_avg": {
                "precision": round(report["macro avg"]["precision"], 4),
                "recall": round(report["macro avg"]["recall"], 4),
                "f1": round(report["macro avg"]["f1-score"], 4),
            },
        },
        "regressao": {
            "mae": round(mae, 4),
            "r2": round(r2, 4),
            "mae_baseline_media": round(baseline_mae, 4),
            "r2_baseline_media": baseline_r2,
            "media_retorno_real_teste_pct": round(media_retorno_teste * 100, 2),
            "media_retorno_previsto_pct": round(pred_media * 100, 2),
            "pct_previsto_negativo": round(pred_negativos_pct, 1),
            "pct_real_negativo": round(real_negativos_pct, 1),
        },
        "graficos": {
            "retorno_real_vs_previsto": [
                {"real_pct": round(float(a) * 100, 2), "previsto_pct": round(float(b) * 100, 2)}
                for a, b in zip(yr_test.values[-30:], pred_r[-30:])
            ],
            "distribuicao_retorno_previsto": _histogram(pred_r),
            "acuracia_por_classe": [
                {
                    "classe": c,
                    "f1": round(report[c]["f1-score"], 4),
                    "recall": round(report[c]["recall"], 4),
                }
                for c in classes
                if c in report
            ],
        },
        "interpretacao": _texto_interpretacao(acc, r2, pred_negativos_pct, pred_media),
    }


def _histogram(values: np.ndarray, bins: int = 8) -> list[dict]:
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return []
    counts, edges = np.histogram(arr, bins=bins)
    out = []
    for i, c in enumerate(counts):
        out.append(
            {
                "faixa": f"{edges[i]*100:.1f}% a {edges[i+1]*100:.1f}%",
                "contagem": int(c),
            }
        )
    return out


def _texto_interpretacao(acc: float, r2: float, pct_neg: float, pred_media: float) -> str:
    parts = []
    if r2 < 0:
        parts.append(
            "R2 negativo: o modelo de retorno erra mais do que usar a media historica — "
            "use as projecoes como ordem de grandeza, nao previsao pontual."
        )
    if pct_neg > 70:
        parts.append(
            f"O regressor prevê queda em ~{pct_neg:.0f}% dos casos de teste "
            f"(media prevista {pred_media*100:+.1f}% em 4 semanas) — por isso muitos cenarios Groq caem juntos."
        )
    if acc < 0.5:
        parts.append(f"Acuracia de volatilidade moderada ({acc*100:.0f}%) — classe 'alta' pode estar super-representada.")
    return " ".join(parts) if parts else "Metricas dentro do esperado para dataset pequeno."
