"""
Coleta indicadores macro semanais (yfinance + FRED opcional).

Uso:
    python 1_Coleta_Dados/coletar_indicadores.py
    python 1_Coleta_Dados/coletar_indicadores.py --inicio 2015-01-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.check_deps import ensure_dependencies  # noqa: E402

ensure_dependencies(extra=[("yfinance", "yfinance")])

from tcc.config_loader import load_settings  # noqa: E402
from tcc.indicators import coletar_todos_indicadores  # noqa: E402
from tcc.io_utils import save_table  # noqa: E402
from tcc.paths import resolve  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta indicadores macro semanais")
    parser.add_argument("--inicio", default=None)
    parser.add_argument("--sem-fred", action="store_true")
    args = parser.parse_args()

    cfg = load_settings()
    start = args.inicio or cfg["env"]["data_inicio"]
    out_path = resolve(cfg["caminhos"]["raw_indicadores"])

    print(f"Coletando indicadores desde {start} ...")
    df = coletar_todos_indicadores(start, usar_fred=not args.sem_fred)
    save_table(df, out_path)
    print(f"OK: {len(df)} semanas -> {out_path}")
    print(f"     Colunas: {', '.join(c for c in df.columns if c != 'semana_inicio')}")


if __name__ == "__main__":
    main()
