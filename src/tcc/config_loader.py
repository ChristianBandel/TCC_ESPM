from __future__ import annotations

import os
from typing import Any

import yaml
from dotenv import load_dotenv

from tcc.paths import CONFIG_PATH, ROOT

load_dotenv(ROOT / ".env")


def load_settings() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["env"] = {
        "oil_token": os.getenv("OILPRICE_API_TOKEN", ""),
        "ucdp_token": os.getenv("UCDP_ACCESS_TOKEN", ""),
        "groq_key": os.getenv("GROQ_API_KEY", ""),
        "groq_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "fred_key": os.getenv("FRED_API_KEY", ""),
        "data_inicio": os.getenv("DATA_INICIO", cfg["petroleo"]["data_inicio"]),
        "commodity": os.getenv("COMMODITY_CODE", cfg["petroleo"]["commodity"]),
    }
    return cfg
