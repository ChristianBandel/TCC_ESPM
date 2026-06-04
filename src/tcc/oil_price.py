"""Preco Brent atual via Oil Price API ou fallback no dataset."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests

from tcc.config_loader import load_settings
from tcc.paths import resolve


def fetch_latest_brent() -> dict:
    """Retorna preco spot mais recente da Oil Price API."""
    cfg = load_settings()
    token = cfg["env"]["oil_token"]
    commodity = cfg["env"]["commodity"]
    if not token:
        raise ValueError("OILPRICE_API_TOKEN nao configurado no .env")

    url = "https://api.oilpriceapi.com/v1/prices/latest"
    resp = requests.get(
        url,
        headers={"Authorization": f"Token {token}"},
        params={"by_code": commodity},
        timeout=30,
    )
    if resp.status_code == 401:
        raise ValueError("Token Oil Price API invalido")
    resp.raise_for_status()
    p = resp.json()["data"]
    return {
        "preco_usd": float(p["price"]),
        "commodity": p.get("code", commodity),
        "atualizado_em": p.get("updated_at") or p.get("created_at"),
        "fonte": "oil_price_api_latest",
    }


def fetch_from_dataset() -> dict:
    cfg = load_settings()
    path = resolve(cfg["caminhos"]["raw_petroleo"])
    if not path.exists():
        path = resolve(cfg["caminhos"]["dataset_ml_csv"])
    df = pd.read_csv(path)
    col_data = "data" if "data" in df.columns else "semana_inicio"
    df = df.sort_values(col_data)
    row = df.iloc[-1]
    preco = float(row["preco_usd"])
    data_ref = str(row[col_data])
    return {
        "preco_usd": preco,
        "commodity": row.get("commodity", "BRENT_CRUDE_USD"),
        "atualizado_em": data_ref,
        "fonte": "dataset_historico_semanal",
    }


def obter_preco_atual(forcar_api: bool = True) -> dict:
    """
    Prioridade: API ao vivo -> dataset.
    Retorna dict com preco_usd, fonte, atualizado_em, aviso (opcional).
    """
    if forcar_api and os.getenv("OILPRICE_API_TOKEN"):
        try:
            live = fetch_latest_brent()
            live["aviso"] = None
            return live
        except Exception as e:
            ds = fetch_from_dataset()
            ds["aviso"] = f"API indisponivel ({e}); usando ultima semana do dataset."
            return ds
    return fetch_from_dataset()


def atualizar_baseline_preco(baseline: pd.Series, preco_atual: float, df_hist: pd.DataFrame) -> pd.Series:
    """Ajusta features de preco no vetor de entrada com cotacao atual."""
    row = baseline.copy()
    row["preco_usd"] = preco_atual
    hist = df_hist.sort_values("semana_inicio").tail(5)
    if len(hist) >= 2:
        prev = float(hist.iloc[-2]["preco_usd"])
        if prev > 0:
            row["retorno_1s"] = (preco_atual - prev) / prev
        if len(hist) >= 5:
            row["retorno_4s"] = (preco_atual - float(hist.iloc[-5]["preco_usd"])) / float(
                hist.iloc[-5]["preco_usd"]
            )
        rets = hist["preco_usd"].pct_change().dropna()
        if len(rets) >= 2:
            row["volatilidade_realizada"] = float(rets.tail(4).std())
    return row
