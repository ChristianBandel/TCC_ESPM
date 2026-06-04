"""Predicao de volatilidade e preco a partir de parametros de cenario."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from tcc.config_loader import load_settings
from tcc.oil_price import atualizar_baseline_preco, obter_preco_atual
from tcc.paths import resolve
from tcc.scenario_params import enrich_scenario_params

INTENSIDADE_MAP = {"baixo": 1, "medio": 2, "alto": 3, "nenhum": 0}


def build_scenario_row(
    features: list[str],
    baseline: pd.Series,
    eventos: int,
    mortes: int,
    paises: int,
    regioes: int,
    conflitos: int,
    intensidade: str,
    choque: int,
) -> pd.DataFrame:
    row = baseline.copy()
    overrides = {
        "num_eventos": eventos,
        "mortes_totais": mortes,
        "mortes_civis": int(mortes * 0.3),
        "paises_ativos": paises,
        "regioes_ativas": regioes,
        "conflitos_ativos": conflitos,
        "intensidade_media": INTENSIDADE_MAP.get(intensidade, 2) * 50,
        "choque_conflito": choque,
    }
    for k, v in overrides.items():
        if k in row.index:
            row[k] = v
        if f"{k}_lag1" in row.index:
            row[f"{k}_lag1"] = v
        if f"{k}_media4" in row.index:
            row[f"{k}_media4"] = v * 1.2
    return pd.DataFrame([{f: row.get(f, 0) for f in features}])


def _interpretar(vol: str, ret: float) -> str:
    direcao = "alta" if ret > 0.02 else "baixa" if ret < -0.02 else "estavel"
    return (
        f"Cenario sugere volatilidade {vol} com tendencia de preco {direcao} "
        f"({ret * 100:+.1f}% em ~4 semanas). Apoio analitico — nao previsao deterministica."
    )


def prever_cenario(params: dict[str, Any]) -> dict[str, Any]:
    """Executa modelos treinados com dict de cenario."""
    params = enrich_scenario_params(params)

    cfg = load_settings()
    meta_path = resolve(cfg["caminhos"]["metadados"])
    clf_path = resolve(cfg["caminhos"]["modelo_classificador"])
    reg_path = resolve(cfg["caminhos"]["modelo_regressor"])
    ds_path = resolve(cfg["caminhos"]["dataset_ml_csv"])

    for p in (meta_path, clf_path, reg_path):
        if not p.exists():
            raise FileNotFoundError(f"Modelo ausente: {p}. Treine com treinar_modelo.py.")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    features = meta["features"]
    clf = joblib.load(clf_path)
    reg = joblib.load(reg_path)
    df = pd.read_csv(ds_path)
    baseline = df.iloc[-1]

    if params.get("preco_atual"):
        preco_info = {
            "preco_usd": float(params["preco_atual"]),
            "fonte": "manual",
            "atualizado_em": None,
            "aviso": None,
        }
    else:
        preco_info = obter_preco_atual(forcar_api=not params.get("usar_dataset", False))

    preco = float(preco_info["preco_usd"])
    baseline = atualizar_baseline_preco(baseline, preco, df)

    intensidade = str(params.get("intensidade", "medio")).lower()
    if intensidade not in INTENSIDADE_MAP:
        intensidade = "medio"

    X = build_scenario_row(
        features,
        baseline,
        int(params["eventos"]),
        int(params["mortes"]),
        int(params["paises"]),
        int(params["regioes"]),
        int(params["conflitos"]),
        intensidade,
        int(params["choque"]),
    ).replace([np.inf, -np.inf], np.nan).fillna(0)

    pred_label = str(clf.predict(X)[0])
    vol_class = pred_label  # pode ser direcao (cai/sobe) ou volatilidade conforme treino
    retorno_4s = float(reg.predict(X)[0])
    preco_proj = preco * (1 + retorno_4s)

    probas: dict[str, float] = {}
    if hasattr(clf, "predict_proba"):
        classes = getattr(clf, "classes_", None)
        if classes is not None:
            for c, p in zip(classes, clf.predict_proba(X)[0]):
                probas[str(c)] = round(float(p), 3)

    return {
        "cenario": {
            "titulo": params.get("titulo", ""),
            "pais": params.get("pais", "Desconhecido"),
            "regiao": params.get("regiao", "Outras"),
            "intensidade": intensidade,
            "sentimento": params.get("sentimento", ""),
            "probabilidade_escalada_pct": params.get("probabilidade_escalada_pct"),
            "eventos_semana": int(params.get("eventos", 10)),
            "mortes_estimadas": int(params.get("mortes", 200)),
            "choque": bool(int(params.get("choque", 1))),
            "raciocinio": params.get("raciocinio", ""),
        },
        "petroleo": {
            "preco_atual_usd": round(float(preco), 2),
            "preco_referencia_fonte": preco_info.get("fonte"),
            "preco_referencia_data": preco_info.get("atualizado_em"),
            "dataset_ultimo_preco": round(float(df.iloc[-1]["preco_usd"]), 2),
            "dataset_ultima_semana": str(df.iloc[-1].get("semana_inicio", "")),
            "aviso_preco": preco_info.get("aviso"),
            "classe_volatilidade_prevista": vol_class,
            "direcao_prevista": pred_label,
            "probabilidades": probas,
            "retorno_esperado_4_semanas_pct": round(retorno_4s * 100, 2),
            "preco_projetado_4_semanas_usd": round(preco_proj, 2),
        },
        "parametros_ml": {
            "eventos": int(params["eventos"]),
            "mortes": int(params["mortes"]),
            "intensidade": intensidade,
            "choque": bool(int(params["choque"])),
        },
        "interpretacao": _interpretar(vol_class, retorno_4s),
    }
