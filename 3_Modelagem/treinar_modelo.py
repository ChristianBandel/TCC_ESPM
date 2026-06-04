"""
Treina modelos com validacao temporal e foco em conflito -> petroleo.

Alvos:
  - Classificacao: direcao_futura (cai / estavel / sobe) ou volatilidade
  - Regressao: retorno_futuro_4s

Uso:
    python 3_Modelagem/treinar_modelo.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import classification_report, mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.check_deps import ensure_dependencies  # noqa: E402

ensure_dependencies()

from tcc.config_loader import load_settings  # noqa: E402
from tcc.model_metrics import avaliar_modelos  # noqa: E402
from tcc.paths import resolve  # noqa: E402

FEATURES_OIL = ["retorno_1s", "retorno_4s", "volatilidade_realizada"]
FEATURES_OIL_NIVEL = ["preco_usd"]
FEATURES_CONFLICT = [
    "num_eventos",
    "mortes_totais",
    "mortes_civis",
    "paises_ativos",
    "regioes_ativas",
    "conflitos_ativos",
    "intensidade_media",
    "choque_conflito",
    "delta_mortes_4s",
    "mortes_zscore_12s",
    "log_mortes",
    "ged_eventos",
    "ged_mortes",
    "mortes_oriente_medio",
    "mortes_europa_leste",
    "mortes_africa_petroleo",
    "mortes_asia",
    "mortes_outras",
    "interacao_oriente_medio_x_vix",
    "spread_brent_wti",
]
FEATURES_MACRO = [
    "vix",
    "dxy",
    "wti_usd",
    "sp500",
    "ouro_usd",
    "dxy_fred",
    "inflacao_breakeven_5y",
    "wti_fred",
]


def select_features(df: pd.DataFrame, usar_preco_nivel: bool = False) -> list[str]:
    bases = FEATURES_OIL + FEATURES_CONFLICT + FEATURES_MACRO
    if usar_preco_nivel:
        bases = FEATURES_OIL_NIVEL + bases

    cols: list[str] = []
    for base in bases:
        if base in df.columns:
            cols.append(base)
        for suf in ("_lag1", "_media4"):
            c = f"{base}{suf}"
            if c in df.columns:
                cols.append(c)
        if base.startswith("mortes_") and f"delta_{base}" in df.columns:
            cols.append(f"delta_{base}")

    for c in df.columns:
        if c.startswith(("ret_", "z_")) and c not in cols:
            cols.append(c)

    exclude = {
        "semana_inicio",
        "commodity",
        "tipo_preco",
        "fonte",
        "classe_volatilidade",
        "direcao_futura",
        "volatilidade_futura",
        "retorno_futuro_4s",
        "nivel_conflito_semana",
        "ano",
    }
    return [c for c in dict.fromkeys(cols) if c not in exclude]


def time_series_split_index(n: int, test_size: float) -> int:
    return int(n * (1 - test_size))


def cross_val_direcao(X: pd.DataFrame, y: pd.Series, n_splits: int = 4) -> float:
    tscv = TimeSeriesSplit(n_splits=n_splits)
    accs = []
    for train_idx, test_idx in tscv.split(X):
        m = HistGradientBoostingClassifier(
            max_depth=4,
            learning_rate=0.08,
            max_iter=120,
            class_weight="balanced",
            random_state=42,
        )
        m.fit(X.iloc[train_idx], y.iloc[train_idx])
        accs.append((m.predict(X.iloc[test_idx]) == y.iloc[test_idx]).mean())
    return float(np.mean(accs))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None)
    args = parser.parse_args()

    cfg = load_settings()
    ds_path = resolve(args.dataset or cfg["caminhos"]["dataset_ml"])
    if not ds_path.exists():
        ds_path = resolve(cfg["caminhos"]["dataset_ml_csv"])
    if not ds_path.exists():
        print("ERRO: dataset ML nao encontrado. Rode preparar_dataset.py.")
        sys.exit(1)

    df = pd.read_parquet(ds_path) if ds_path.suffix == ".parquet" else pd.read_csv(ds_path)
    usar_nivel = cfg["preparacao"].get("usar_preco_nivel", False)
    features = select_features(df, usar_preco_nivel=usar_nivel)
    if len(features) < 5:
        print("ERRO: poucas features. Rode preparar_dataset.py apos atualizar o codigo.")
        sys.exit(1)

    alvo = cfg["modelagem"].get("alvo_classificacao", "direcao_futura")
    if alvo not in df.columns:
        alvo = "classe_volatilidade"
    classes = cfg["modelagem"].get(
        "classes_direcao" if alvo == "direcao_futura" else "classes_volatilidade",
        ["cai", "estavel", "sobe"],
    )

    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_class = df[alvo].astype(str)
    y_reg = df["retorno_futuro_4s"].astype(float)

    split = time_series_split_index(len(df), cfg["modelagem"]["test_size"])
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    yc_train, yc_test = y_class.iloc[:split], y_class.iloc[split:]
    yr_train, yr_test = y_reg.iloc[:split], y_reg.iloc[split:]

    print(f"Features: {len(features)} | Treino: {len(X_train)} | Teste: {len(X_test)}")
    print(f"Alvo classificacao: {alvo}")
    print(f"Distribuicao treino:\n{yc_train.value_counts()}")

    cv_acc = cross_val_direcao(X_train, yc_train)
    print(f"CV temporal (acuracia media {cv_acc*100:.1f}%)")

    clf = HistGradientBoostingClassifier(
        max_depth=5,
        learning_rate=0.06,
        max_iter=200,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=cfg["modelagem"]["random_state"],
    )
    reg = HistGradientBoostingRegressor(
        max_depth=4,
        learning_rate=0.05,
        max_iter=200,
        min_samples_leaf=10,
        random_state=cfg["modelagem"]["random_state"],
    )

    clf.fit(X_train, yc_train)
    reg.fit(X_train, yr_train)

    pred_c = clf.predict(X_test)
    pred_r = reg.predict(X_test)

    print("=== Classificacao ===")
    print(classification_report(yc_test, pred_c, zero_division=0))
    print("=== Regressao (retorno 4 semanas) ===")
    print(f"MAE: {mean_absolute_error(yr_test, pred_r):.4f}")
    print(f"R2:  {r2_score(yr_test, pred_r):.4f}")

    # Baseline: sempre prever classe mais frequente / media do retorno
    base_class = yc_train.mode().iloc[0]
    base_acc = (yc_test == base_class).mean()
    base_r2 = r2_score(yr_test, np.full(len(yr_test), yr_train.mean()))
    print(f"Baseline classe majoritaria ({base_class}): acuracia {base_acc*100:.1f}%")
    print(f"Baseline retorno = media treino: R2 {base_r2:.4f}")

    corr_imp = []
    for f in features:
        if f in df.columns:
            c = df[f].corr(df[alvo].astype("category").cat.codes if df[alvo].dtype == object else df[alvo])
            if not np.isnan(c):
                corr_imp.append((f, abs(float(c))))
    top_imp = sorted(corr_imp, key=lambda x: -x[1])[:12]

    metricas_full = avaliar_modelos(
        yc_test, pred_c, yr_test, pred_r, classes_ordem=classes
    )
    metricas_full["treino"] = {
        "cv_acuracia_temporal": round(cv_acc, 4),
        "baseline_acuracia": round(float(base_acc), 4),
        "alvo": alvo,
        "top_features": [{"nome": k, "importancia": round(v, 4)} for k, v in top_imp],
    }

    meta = {
        "features": features,
        "alvo_classificacao": alvo,
        "classes": classes,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "metricas": {
            "mae_retorno": metricas_full["regressao"]["mae"],
            "r2_retorno": metricas_full["regressao"]["r2"],
            "acuracia": metricas_full["classificacao"]["acuracia"],
            "cv_acuracia": round(cv_acc, 4),
        },
        "avaliacao": metricas_full,
    }

    clf_path = resolve(cfg["caminhos"]["modelo_classificador"])
    reg_path = resolve(cfg["caminhos"]["modelo_regressor"])
    meta_path = resolve(cfg["caminhos"]["metadados"])

    clf_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, clf_path)
    joblib.dump(reg, reg_path)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    charts_path = resolve(cfg["caminhos"].get("graficos_metricas", "dados/models/graficos_metricas.json"))
    charts_path.write_text(
        json.dumps(metricas_full, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("Top features:", top_imp[:6])
    print(f"Modelos salvos em {clf_path.parent}")


if __name__ == "__main__":
    main()
