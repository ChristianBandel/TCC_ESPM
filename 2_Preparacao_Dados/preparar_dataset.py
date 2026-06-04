"""
Une petróleo + conflitos em dataset semanal pronto para ML.

Saídas:
  - dados/processed/dataset_ml.parquet
  - dados/processed/dataset_ml.csv (+ xlsx)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.check_deps import ensure_dependencies  # noqa: E402

ensure_dependencies()

from tcc.config_loader import load_settings  # noqa: E402
from tcc.ged_regions import agregar_ged_semanal_regional  # noqa: E402
from tcc.indicators import YFINANCE_SERIES, add_macro_features  # noqa: E402
from tcc.io_utils import ensure_parent, save_table  # noqa: E402
from tcc.paths import ROOT, resolve  # noqa: E402


def load_petroleo(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["data"])
    df = df.rename(columns={"data": "semana_inicio"})
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"]).dt.to_period("W-MON").dt.start_time
    df = df.sort_values("semana_inicio").drop_duplicates("semana_inicio")
    return df


def load_conflitos(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["semana_inicio"])
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"]).dt.to_period("W-MON").dt.start_time
    return df.sort_values("semana_inicio").drop_duplicates("semana_inicio")


def load_indicadores(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["semana_inicio"])
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"]).dt.to_period("W-MON").dt.start_time
    return df.sort_values("semana_inicio").drop_duplicates("semana_inicio")


def build_features(
    df: pd.DataFrame, janela_vol: int, horizonte: int, limiar_direcao: float = 0.02
) -> pd.DataFrame:
    out = df.copy()
    out["retorno_1s"] = out["preco_usd"].pct_change()
    out["retorno_4s"] = out["preco_usd"].pct_change(4)
    out["volatilidade_realizada"] = out["retorno_1s"].rolling(janela_vol).std()

    # alvo: volatilidade nas próximas N semanas (desvio dos retornos futuros)
    rev = out["retorno_1s"].iloc[::-1]
    out["volatilidade_futura"] = rev.rolling(horizonte, min_periods=horizonte).std().iloc[::-1].values
    out["retorno_futuro_4s"] = out["preco_usd"].shift(-horizonte) / out["preco_usd"] - 1

    conflict_cols = [
        "num_eventos",
        "mortes_totais",
        "mortes_civis",
        "paises_ativos",
        "regioes_ativas",
        "conflitos_ativos",
        "intensidade_media",
    ]
    for c in conflict_cols:
        if c in out.columns:
            out[f"{c}_lag1"] = out[c].shift(1)
            out[f"{c}_media4"] = out[c].rolling(4).mean()

    out["choque_conflito"] = 0
    if "mortes_totais" in out.columns:
        med = out["mortes_totais"].rolling(12).median()
        out["choque_conflito"] = (out["mortes_totais"] > med * 1.5).astype(int)
        out["delta_mortes_4s"] = out["mortes_totais"] - out["mortes_totais"].shift(4)
        std = out["mortes_totais"].rolling(12).std().replace(0, np.nan)
        out["mortes_zscore_12s"] = (out["mortes_totais"] - med) / std
        out["log_mortes"] = np.log1p(out["mortes_totais"])

    for col in ("mortes_oriente_medio", "mortes_europa_leste", "mortes_africa_petroleo"):
        if col in out.columns:
            out[f"{col}_media4"] = out[col].rolling(4).mean()
            out[f"delta_{col}"] = out[col] - out[col].shift(1)

    macro_base = [m["col"] for m in YFINANCE_SERIES.values()] + [
        "dxy_fred",
        "inflacao_breakeven_5y",
        "wti_fred",
        "brent_fred",
    ]
    out = add_macro_features(out, macro_base)

    # Alvo interpretavel: petroleo sobe ou cai nas proximas 4 semanas
    out["direcao_futura"] = np.where(
        out["retorno_futuro_4s"] > limiar_direcao,
        "sobe",
        np.where(out["retorno_futuro_4s"] < -limiar_direcao, "cai", "estavel"),
    )

    out = out.dropna(subset=["preco_usd", "volatilidade_futura", "retorno_futuro_4s"])
    return out


def assign_volatility_class(series: pd.Series) -> pd.Series:
    q33, q66 = series.quantile([0.33, 0.66])
    return pd.cut(
        series,
        bins=[-np.inf, q33, q66, np.inf],
        labels=["baixa", "media", "alta"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--petroleo", default=None)
    parser.add_argument("--conflitos", default=None)
    args = parser.parse_args()

    cfg = load_settings()
    oil_path = resolve(args.petroleo or cfg["caminhos"]["raw_petroleo"])
    conf_path = resolve(args.conflitos or cfg["caminhos"]["raw_conflitos"])
    out_parquet = resolve(cfg["caminhos"]["dataset_ml"])
    out_csv = resolve(cfg["caminhos"]["dataset_ml_csv"])

    if not oil_path.exists():
        print(f"ERRO: petróleo não encontrado em {oil_path}. Rode coletar_petroleo.py primeiro.")
        sys.exit(1)

    oil = load_petroleo(oil_path)
    ged_path = resolve(cfg["conflitos"].get("ged_csv_padrao", "1_Coleta_Dados/GEDEvent_v25_1.csv"))
    if not ged_path.is_absolute():
        ged_path = ROOT / ged_path
    regional = None
    if ged_path.exists():
        print(f"Agregando regioes do GED: {ged_path.name} ...")
        regional = agregar_ged_semanal_regional(ged_path, year_min=cfg["conflitos"]["data_inicio"])

    if conf_path.exists():
        conf = load_conflitos(conf_path)
        merged = oil.merge(conf, on="semana_inicio", how="left")
        if regional is not None:
            merged = merged.merge(regional, on="semana_inicio", how="left")
        conflict_fill = {
            "num_eventos": 0,
            "mortes_totais": 0,
            "mortes_civis": 0,
            "paises_ativos": 0,
            "regioes_ativas": 0,
            "conflitos_ativos": 0,
            "intensidade_media": 0,
        }
        for k, v in conflict_fill.items():
            if k in merged.columns:
                merged[k] = merged[k].fillna(v)
        if regional is not None:
            reg_cols = [c for c in regional.columns if c != "semana_inicio"]
            for c in reg_cols:
                if c in merged.columns:
                    merged[c] = merged[c].fillna(0)
        print(f"Merge com conflitos: {len(conf)} semanas de conflito")
    else:
        merged = oil.copy()
        print(f"AVISO: {conf_path} ausente — dataset só com petróleo.")

    ind_path = resolve(cfg["caminhos"]["raw_indicadores"])
    if ind_path.exists():
        ind = load_indicadores(ind_path)
        merged = merged.merge(ind, on="semana_inicio", how="left")
        print(f"Merge com indicadores macro: {len(ind)} semanas")
    else:
        print(f"AVISO: {ind_path} ausente — rode coletar_indicadores.py")

    janela = cfg["preparacao"]["janela_volatilidade_semanas"]
    horizonte = cfg["preparacao"]["horizonte_previsao_semanas"]
    limiar = float(cfg["modelagem"].get("limiar_direcao_pct", 0.02))
    dataset = build_features(merged, janela, horizonte, limiar_direcao=limiar)
    dataset["classe_volatilidade"] = assign_volatility_class(dataset["volatilidade_futura"])

    ensure_parent(out_parquet)
    dataset.to_parquet(out_parquet, index=False)
    save_table(dataset, out_csv, xlsx=True)

    print(f"OK: {len(dataset)} linhas | {dataset['semana_inicio'].min()} -> {dataset['semana_inicio'].max()}")
    print(f"     Parquet: {out_parquet}")
    print(f"     CSV/XLSX: {out_csv}")


if __name__ == "__main__":
    main()
