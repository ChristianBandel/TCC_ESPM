from __future__ import annotations

from pathlib import Path

import pandas as pd


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_table(df: pd.DataFrame, csv_path: Path, xlsx: bool = True) -> None:
    ensure_parent(csv_path)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    if xlsx:
        xlsx_path = csv_path.with_suffix(".xlsx")
        df.to_excel(xlsx_path, index=False)
