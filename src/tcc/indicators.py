"""Coleta e agregacao semanal de indicadores macro (yfinance + FRED opcional)."""

from __future__ import annotations

import os
from datetime import date
import numpy as np
import pandas as pd
import requests

# Tickers yfinance -> colunas no dataset
YFINANCE_SERIES: dict[str, dict[str, str]] = {
    "vix": {"ticker": "^VIX", "col": "vix"},
    "dxy": {"ticker": "DX-Y.NYB", "col": "dxy"},
    "wti_yf": {"ticker": "CL=F", "col": "wti_usd"},
    "sp500": {"ticker": "^GSPC", "col": "sp500"},
    "ouro": {"ticker": "GC=F", "col": "ouro_usd"},
}

# FRED (opcional) series_id -> coluna
FRED_SERIES: dict[str, str] = {
    "DTWEXBGS": "dxy_fred",
    "T5YIE": "inflacao_breakeven_5y",
    "DCOILWTICO": "wti_fred",
    "DCOILBRENTEU": "brent_fred",
}


def to_weekly_monday(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Ultimo valor disponivel de cada semana (segunda-feira como rotulo)."""
    s = df[value_col].dropna().sort_index()
    if s.empty:
        return pd.DataFrame(columns=["semana_inicio", value_col])
    weekly = s.resample("W-MON").last().dropna()
    out = weekly.reset_index()
    out.columns = ["semana_inicio", value_col]
    out["semana_inicio"] = pd.to_datetime(out["semana_inicio"]).dt.normalize()
    return out


def fetch_yfinance_series(ticker: str, start: str, col: str) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(ticker, start=start, end=date.today().isoformat(), progress=False, auto_adjust=True)
    if data.empty:
        return pd.DataFrame(columns=["semana_inicio", col])
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
    price = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
    raw = price.reset_index()
    raw.columns = ["data", col]
    raw["data"] = pd.to_datetime(raw["data"]).dt.tz_localize(None)
    return to_weekly_monday(raw.set_index("data"), col)


def fetch_fred_series(series_id: str, api_key: str, start: str, col: str) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    rows = []
    for o in obs:
        v = o.get("value", ".")
        if v in (".", "", None):
            continue
        rows.append({"data": o["date"], col: float(v)})
    if not rows:
        return pd.DataFrame(columns=["semana_inicio", col])
    raw = pd.DataFrame(rows)
    raw["data"] = pd.to_datetime(raw["data"])
    return to_weekly_monday(raw.set_index("data"), col)


def coletar_todos_indicadores(start: str, usar_fred: bool = True) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for meta in YFINANCE_SERIES.values():
        try:
            w = fetch_yfinance_series(meta["ticker"], start, meta["col"])
            if not w.empty:
                frames.append(w)
                print(f"  OK yfinance {meta['ticker']} -> {meta['col']} ({len(w)} semanas)")
        except Exception as e:
            print(f"  AVISO yfinance {meta['ticker']}: {e}")

    fred_key = os.getenv("FRED_API_KEY", "").strip()
    if usar_fred and fred_key:
        for sid, col in FRED_SERIES.items():
            try:
                w = fetch_fred_series(sid, fred_key, start, col)
                if not w.empty:
                    frames.append(w)
                    print(f"  OK FRED {sid} -> {col} ({len(w)} semanas)")
            except Exception as e:
                print(f"  AVISO FRED {sid}: {e}")
    elif usar_fred:
        print("  AVISO: FRED_API_KEY ausente — apenas yfinance.")

    if not frames:
        raise RuntimeError("Nenhum indicador coletado.")

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="semana_inicio", how="outer")
    merged = merged.sort_values("semana_inicio").reset_index(drop=True)
    return merged


def add_macro_features(df: pd.DataFrame, macro_cols: list[str]) -> pd.DataFrame:
    """Retornos, z-score 12s, lags e spread Brent-WTI."""
    out = df.copy()
    if "wti_usd" in out.columns and "preco_usd" in out.columns:
        out["spread_brent_wti"] = out["preco_usd"] - out["wti_usd"]
    elif "wti_fred" in out.columns and "preco_usd" in out.columns:
        out["spread_brent_wti"] = out["preco_usd"] - out["wti_fred"]

    extra = list(macro_cols)
    if "spread_brent_wti" in out.columns:
        extra.append("spread_brent_wti")

    for col in extra:
        if col not in out.columns:
            continue
        out[f"ret_{col}_1s"] = out[col].pct_change()
        med = out[col].rolling(12).median()
        std = out[col].rolling(12).std().replace(0, np.nan)
        out[f"z_{col}_12s"] = (out[col] - med) / std
        out[f"{col}_lag1"] = out[col].shift(1)

    # Interacao conflito x risco (se existir)
    if "mortes_oriente_medio" in out.columns and "vix" in out.columns:
        out["interacao_oriente_medio_x_vix"] = (
            out["mortes_oriente_medio"].fillna(0) * out["vix"].fillna(0) / 1000
        )

    return out
