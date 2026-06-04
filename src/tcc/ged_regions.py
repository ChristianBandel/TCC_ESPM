"""Agrega GED por semana e regiao (foco em areas ligadas ao petroleo)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Paises / regioes UCDP com maior ligacao historica ao mercado de petroleo
ORIENTE_MEDIO = {
    "Iraq", "Iran", "Yemen", "Syria", "Israel", "Palestine", "Saudi Arabia",
    "Kuwait", "Lebanon", "Jordan", "United Arab Emirates", "Bahrain", "Qatar",
}
EUROPA_ORIENTE = {"Ukraine", "Russia", "Georgia", "Moldova"}
AFRICA_PETROLEO = {"Libya", "Sudan", "South Sudan", "Nigeria", "Algeria", "Angola"}
ASIA = {"Afghanistan", "Pakistan", "Myanmar", "China", "India"}


def _regiao_petroleo(pais: str) -> str:
    p = str(pais).strip()
    if p in ORIENTE_MEDIO:
        return "oriente_medio"
    if p in EUROPA_ORIENTE:
        return "europa_leste"
    if p in AFRICA_PETROLEO:
        return "africa_petroleo"
    if p in ASIA:
        return "asia"
    return "outras"


def agregar_ged_semanal_regional(ged_path: Path, year_min: int = 2015) -> pd.DataFrame:
    usecols = ["date_start", "country", "best", "type_of_violence"]
    df = pd.read_csv(ged_path, usecols=usecols, low_memory=False)
    df["data_evento"] = pd.to_datetime(df["date_start"], errors="coerce")
    df = df[df["data_evento"].dt.year >= year_min]
    df["mortes"] = pd.to_numeric(df["best"], errors="coerce").fillna(0).clip(lower=0)
    df["regiao_petroleo"] = df["country"].map(_regiao_petroleo)
    df["semana_inicio"] = (
        df["data_evento"].dt.to_period("W-MON").dt.start_time.dt.normalize()
    )

    global_agg = (
        df.groupby("semana_inicio", as_index=False)
        .agg(
            ged_eventos=("data_evento", "count"),
            ged_mortes=("mortes", "sum"),
            ged_paises=("country", "nunique"),
        )
    )

    regional = (
        df.groupby(["semana_inicio", "regiao_petroleo"], as_index=False)
        .agg(mortes_reg=("mortes", "sum"), eventos_reg=("data_evento", "count"))
    )
    pivot_m = regional.pivot(index="semana_inicio", columns="regiao_petroleo", values="mortes_reg").fillna(0)
    pivot_e = regional.pivot(index="semana_inicio", columns="regiao_petroleo", values="eventos_reg").fillna(0)
    pivot_m.columns = [f"mortes_{c}" for c in pivot_m.columns]
    pivot_e.columns = [f"eventos_{c}" for c in pivot_e.columns]
    out = global_agg.set_index("semana_inicio").join(pivot_m).join(pivot_e).reset_index()
    return out.sort_values("semana_inicio")
