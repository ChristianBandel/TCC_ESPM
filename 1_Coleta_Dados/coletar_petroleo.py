"""
Coleta preços históricos do Brent (Oil Price API) em frequência semanal desde 2015.

Uso (manual, na pasta do projeto):
    python 1_Coleta_Dados/coletar_petroleo.py
    python 1_Coleta_Dados/coletar_petroleo.py --inicio 2015-01-01 --intervalo 1w
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.check_deps import ensure_dependencies  # noqa: E402

ensure_dependencies()

from tcc.config_loader import load_settings  # noqa: E402
from tcc.io_utils import save_table  # noqa: E402
from tcc.paths import resolve  # noqa: E402


def fetch_historical_weekly(
    token: str,
    commodity: str,
    start_date: str,
    end_date: str,
    interval: str = "1w",
    per_page: int = 100,
) -> pd.DataFrame:
    base = "https://api.oilpriceapi.com/v1/prices/historical"
    headers = {"Authorization": f"Token {token}"}
    page = 1
    rows: list[dict] = []

    while True:
        params = {
            "by_code": commodity,
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval,
            "page": page,
            "per_page": per_page,
        }
        resp = requests.get(base, headers=headers, params=params, timeout=60)
        if resp.status_code == 401:
            raise RuntimeError("Token Oil Price API inválido. Configure OILPRICE_API_TOKEN no .env")
        resp.raise_for_status()
        payload = resp.json()
        prices = payload.get("data", {}).get("prices", [])
        for p in prices:
            rows.append(
                {
                    "data": pd.to_datetime(p["created_at"], utc=True).date().isoformat(),
                    "preco_usd": float(p["price"]),
                    "commodity": p.get("code", commodity),
                    "tipo_preco": p.get("type", ""),
                    "fonte": p.get("source", ""),
                }
            )
        total_pages = int(resp.headers.get("X-Total-Pages", 1))
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.3)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["data"]).sort_values("data").reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta Brent semanal via Oil Price API")
    parser.add_argument("--inicio", default=None, help="YYYY-MM-DD (padrão: config/env)")
    parser.add_argument("--fim", default=date.today().isoformat())
    parser.add_argument("--intervalo", default=None, help="1d, 1w, 1m")
    parser.add_argument("--commodity", default=None)
    args = parser.parse_args()

    cfg = load_settings()
    token = cfg["env"]["oil_token"]
    if not token:
        print("ERRO: defina OILPRICE_API_TOKEN no arquivo .env (copie de .env.example)")
        sys.exit(1)

    commodity = args.commodity or cfg["env"]["commodity"]
    start = args.inicio or cfg["env"]["data_inicio"]
    interval = args.intervalo or cfg["petroleo"]["intervalo"]
    out_path = resolve(cfg["caminhos"]["raw_petroleo"])

    print(f"Coletando {commodity} | {start} -> {args.fim} | intervalo={interval}")
    df = fetch_historical_weekly(token, commodity, start, args.fim, interval)
    if df.empty:
        print("Nenhum dado retornado.")
        sys.exit(1)

    save_table(df, out_path)
    print(f"OK: {len(df)} registros -> {out_path}")
    print(f"     XLSX -> {out_path.with_suffix('.xlsx')}")


if __name__ == "__main__":
    main()
