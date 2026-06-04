"""
Coleta e agrega dados de conflitos/guerras para frequência semanal.

Fontes suportadas (em ordem):
  1. UCDP GED API — eventos diários → agregação semanal (requer UCDP_ACCESS_TOKEN)
  2. CSV manual — baixado em https://ucdp.uu.se/downloads/ (GED ou PRIO)
  3. UCDP PRIO Armed Conflict (CSV anual expandido para semanas)

Uso:
    python 1_Coleta_Dados/coletar_conflitos.py
    python 1_Coleta_Dados/coletar_conflitos.py --csv dados/raw/ucdp_ged251.csv
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.check_deps import ensure_dependencies  # noqa: E402

ensure_dependencies()

from tcc.config_loader import load_settings  # noqa: E402
from tcc.io_utils import save_table  # noqa: E402
from tcc.paths import resolve  # noqa: E402

# Mapeamento simplificado de regiões (GW → região para features de ML)
REGIAO_POR_PAIS = {
    "Ukraine": "Europa Leste",
    "Russia": "Europa Leste",
    "Syria": "Oriente Médio",
    "Iraq": "Oriente Médio",
    "Yemen": "Oriente Médio",
    "Israel": "Oriente Médio",
    "Palestine": "Oriente Médio",
    "Libya": "Norte da África",
    "Sudan": "Norte da África",
    "Ethiopia": "África Oriental",
    "Somalia": "África Oriental",
    "Mali": "Sahel",
    "Niger": "Sahel",
    "Burkina Faso": "Sahel",
    "Afghanistan": "Ásia Central",
    "Myanmar": "Sudeste Asiático",
}


def week_start(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
    return dt.dt.to_period("W-MON").dt.start_time.dt.strftime("%Y-%m-%d")


def aggregate_ged_events(df: pd.DataFrame, year_min: int) -> pd.DataFrame:
    """Agrega eventos GED (nível dia) para painel semanal."""
    col_map = {
        "date_start": "data_evento",
        "country": "pais",
        "region": "regiao",
        "where_description": "local",
        "type_of_violence": "tipo_violencia",
        "conflict_name": "nome_conflito",
        "side_a": "envolvido_a",
        "side_b": "envolvido_b",
        "deaths_a": "mortes_a",
        "deaths_b": "mortes_b",
        "deaths_civilians": "mortes_civis",
        "deaths_unknown": "mortes_desconhecidas",
        "best": "mortes_estimadas",
        "high": "mortes_max",
        "low": "mortes_min",
        "latitude": "latitude",
        "longitude": "longitude",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if "data_evento" not in df.columns:
        raise ValueError("CSV GED precisa da coluna date_start (ou data_evento).")

    df["data_evento"] = pd.to_datetime(df["data_evento"], errors="coerce")
    df = df[df["data_evento"].dt.year >= year_min].copy()
    df["semana_inicio"] = week_start(df["data_evento"])

    for c in ("mortes_estimadas", "mortes_civis", "mortes_a", "mortes_b"):
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "pais" not in df.columns:
        df["pais"] = "Desconhecido"
    if "regiao" not in df.columns:
        df["regiao"] = df["pais"].map(REGIAO_POR_PAIS).fillna("Outras")

    df["nivel_intensidade"] = pd.cut(
        df["mortes_estimadas"].clip(lower=0),
        bins=[-1, 0, 10, 100, 10_000],
        labels=["nenhum", "baixo", "medio", "alto"],
    ).astype(str)

    agg_spec: dict = {
        "num_eventos": ("data_evento", "count"),
        "mortes_totais": ("mortes_estimadas", "sum"),
        "mortes_civis": ("mortes_civis", "sum"),
        "paises_ativos": ("pais", "nunique"),
        "regioes_ativas": ("regiao", "nunique"),
        "intensidade_media": ("mortes_estimadas", "mean"),
    }
    if "nome_conflito" in df.columns:
        agg_spec["conflitos_ativos"] = ("nome_conflito", "nunique")
    agg = df.groupby("semana_inicio", as_index=False).agg(**agg_spec)
    agg["nivel_conflito_semana"] = pd.cut(
        agg["mortes_totais"],
        bins=[-1, 50, 500, 10_000_000],
        labels=["baixo", "medio", "alto"],
    ).astype(str)
    agg["ano"] = pd.to_datetime(agg["semana_inicio"]).dt.year
    return agg.sort_values("semana_inicio").reset_index(drop=True)


def expand_prio_yearly(df: pd.DataFrame, year_min: int) -> pd.DataFrame:
    """Expande UCDP/PRIO conflict-year para semanas (proxy quando não há GED)."""
    rename = {
        "year": "ano",
        "location": "pais",
        "region": "regiao",
        "type_of_conflict": "tipo_conflito",
        "intensity_level": "nivel_intensidade",
        "side_a": "envolvido_a",
        "side_b": "envolvido_b",
        "conflict_id": "id_conflito",
        "conflict_name": "nome_conflito",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "ano" not in df.columns:
        raise ValueError("CSV PRIO precisa da coluna 'year'.")

    df = df[df["ano"] >= year_min].copy()
    if "pais" not in df.columns and "country" in df.columns:
        df["pais"] = df["country"]
    if "regiao" not in df.columns:
        df["regiao"] = df.get("pais", pd.Series(dtype=str)).map(REGIAO_POR_PAIS).fillna("Outras")

    semanas = []
    for ano in sorted(df["ano"].unique()):
        inicio = pd.Timestamp(f"{ano}-01-01")
        fim = pd.Timestamp(f"{ano}-12-31")
        weeks = pd.date_range(inicio, fim, freq="W-MON")
        for w in weeks:
            semanas.append(w.date().isoformat())

    base = pd.DataFrame({"semana_inicio": semanas})
    ano_df = (
        df.groupby("ano", as_index=False)
        .agg(
            conflitos_ativos=("id_conflito", "nunique") if "id_conflito" in df.columns else ("ano", "count"),
            paises_ativos=("pais", "nunique"),
            regioes_ativas=("regiao", "nunique"),
            nivel_intensidade=("nivel_intensidade", "max") if "nivel_intensidade" in df.columns else ("ano", "count"),
        )
    )
    base["ano"] = pd.to_datetime(base["semana_inicio"]).dt.year
    merged = base.merge(ano_df, on="ano", how="left")
    merged["num_eventos"] = merged["conflitos_ativos"].fillna(0)
    merged["mortes_totais"] = 0
    merged["nivel_conflito_semana"] = merged.get("nivel_intensidade", "medio").astype(str)
    return merged.drop(columns=["ano"], errors="ignore")


def fetch_ucdp_ged_api(token: str, version: str, year_min: int, page_size: int = 500) -> pd.DataFrame:
    """Baixa eventos GED via API paginada (pode demorar; use CSV para volume total)."""
    url = f"https://ucdpapi.pcr.uu.se/api/gedevents/{version}"
    headers = {"x-ucdp-access-token": token}
    page = 1
    rows: list[dict] = []
    max_pages_demo = 20  # limite de segurança; remova ou aumente para coleta completa

    while page <= max_pages_demo:
        params = {"pagesize": page_size, "page": page, "Year": f"{year_min}"}
        resp = requests.get(url, headers=headers, params=params, timeout=120)
        if resp.status_code == 401:
            raise RuntimeError(
                "UCDP API requer token. Cadastre-se em https://ucdp.uu.se/apidocs/ "
                "e defina UCDP_ACCESS_TOKEN no .env, ou use --csv com download manual."
            )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", [])
        if not result:
            break
        rows.extend(result)
        total_pages = data.get("TotalPages", 1)
        print(f"  página {page}/{total_pages} — {len(rows)} eventos")
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)

    return pd.DataFrame(rows)


def detect_format(df: pd.DataFrame) -> str:
    if "date_start" in df.columns or "data_evento" in df.columns:
        return "ged"
    if "year" in df.columns:
        return "prio"
    return "unknown"


def gerar_exemplo_semanal(oil_csv: Path, year_min: int) -> pd.DataFrame:
    """Gera painel semanal ilustrativo alinhado às datas do petróleo (somente demonstração)."""
    oil = pd.read_csv(oil_csv, parse_dates=["data"])
    oil["semana_inicio"] = pd.to_datetime(oil["data"]).dt.to_period("W-MON").dt.start_time
    semanas = oil["semana_inicio"].drop_duplicates().sort_values()
    semanas = semanas[semanas.dt.year >= year_min]
    rng = np.random.default_rng(42)
    n = len(semanas)
    base_events = 5 + (oil.set_index("semana_inicio").reindex(semanas)["preco_usd"].pct_change().abs().fillna(0) * 80).values
    return pd.DataFrame(
        {
            "semana_inicio": semanas.dt.date.astype(str),
            "num_eventos": np.maximum(1, (base_events + rng.normal(0, 2, n)).astype(int)),
            "mortes_totais": np.maximum(0, (base_events * 12 + rng.integers(0, 80, n))).astype(int),
            "mortes_civis": np.maximum(0, (base_events * 3 + rng.integers(0, 30, n))).astype(int),
            "paises_ativos": rng.integers(2, 12, n),
            "regioes_ativas": rng.integers(1, 6, n),
            "conflitos_ativos": rng.integers(3, 25, n),
            "intensidade_media": np.round(base_events * 2, 2),
            "nivel_conflito_semana": np.where(base_events > 8, "alto", np.where(base_events > 4, "medio", "baixo")),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta conflitos UCDP → semanal")
    parser.add_argument("--csv", help="Caminho para CSV GED ou PRIO baixado manualmente")
    parser.add_argument("--ano-inicio", type=int, default=None)
    parser.add_argument("--api-completa", action="store_true", help="Sem limite de páginas na API")
    parser.add_argument(
        "--exemplo",
        action="store_true",
        help="Gera dados semanais ilustrativos (use só se UCDP não estiver disponível)",
    )
    args = parser.parse_args()

    cfg = load_settings()
    year_min = args.ano_inicio or cfg["conflitos"]["data_inicio"]
    out_path = resolve(cfg["caminhos"]["raw_conflitos"])

    df_raw: pd.DataFrame | None = None

    if args.exemplo:
        oil_path = resolve(cfg["caminhos"]["raw_petroleo"])
        if not oil_path.exists():
            print("ERRO: rode coletar_petroleo.py antes de --exemplo")
            sys.exit(1)
        weekly = gerar_exemplo_semanal(oil_path, year_min)
        save_table(weekly, out_path)
        print(f"OK (exemplo ilustrativo): {len(weekly)} semanas -> {out_path}")
        print("Substitua por dados UCDP reais para o TCC final.")
        return

    if args.csv:
        csv_path = resolve(args.csv) if not Path(args.csv).is_absolute() else Path(args.csv)
        print(f"Lendo CSV manual: {csv_path}")
        df_raw = pd.read_csv(csv_path, low_memory=False)
    elif cfg["env"]["ucdp_token"]:
        print("Coletando via UCDP GED API (amostra paginada)...")
        df_raw = fetch_ucdp_ged_api(
            cfg["env"]["ucdp_token"],
            cfg["conflitos"]["api_version"],
            year_min,
        )
    else:
        ged_padrao = resolve(cfg["conflitos"].get("ged_csv_padrao", "1_Coleta_Dados/GEDEvent_v25_1.csv"))
        manual = resolve(cfg["caminhos"]["raw_conflitos_manual"])
        if ged_padrao.exists():
            print(f"Usando GED padrao: {ged_padrao}")
            df_raw = pd.read_csv(ged_padrao, low_memory=False)
        elif manual.exists():
            print(f"Usando CSV manual: {manual}")
            df_raw = pd.read_csv(manual, low_memory=False)
        else:
            print(
                "Nenhuma fonte disponível.\n"
                "  Coloque GEDEvent_v25_1.csv em 1_Coleta_Dados/\n"
                "  ou: python coletar_conflitos.py --csv caminho/arquivo.csv"
            )
            sys.exit(1)

    fmt = detect_format(df_raw)
    if fmt == "ged":
        weekly = aggregate_ged_events(df_raw, year_min)
    elif fmt == "prio":
        weekly = expand_prio_yearly(df_raw, year_min)
    else:
        print("Formato CSV não reconhecido. Use export GED (date_start) ou PRIO (year).")
        sys.exit(1)

    save_table(weekly, out_path)
    print(f"OK: {len(weekly)} semanas -> {out_path}")


if __name__ == "__main__":
    main()
