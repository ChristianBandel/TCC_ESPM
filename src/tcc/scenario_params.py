"""Converte cenario Groq/UI em parametros numericos para o modelo."""

from __future__ import annotations

import random
from typing import Any

INTENSIDADE_MULT = {"baixo": 0.5, "medio": 1.0, "alto": 2.0, "nenhum": 0.3}
SENTIMENTO_CHOQUE = {"critico": 1, "tenso": 1, "calmo": 0, "moderado": 0}


def enrich_scenario_params(raw: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """
    Deriva eventos, mortes e choque a partir de intensidade + escalada% quando ausentes.
    Evita que todos os cenarios Groq caiam nos defaults (10 eventos, 200 mortes).
    """
    rng = random.Random(seed)
    p = dict(raw)
    intensidade = str(p.get("intensidade", "medio")).lower()
    if intensidade not in INTENSIDADE_MULT:
        intensidade = "medio"
    mult = INTENSIDADE_MULT[intensidade]

    escalada = p.get("probabilidade_escalada_pct")
    if escalada is None:
        escalada = {"baixo": 25, "medio": 50, "alto": 75}.get(intensidade, 50)
    escalada = max(5, min(95, int(escalada)))

    sentimento = str(p.get("sentimento", p.get("sentimento_geopolitico", "tenso"))).lower()

    if "eventos" not in p or p.get("eventos") in (None, 0, 10):
        base_ev = 8 + escalada / 8
        p["eventos"] = max(3, int(base_ev * mult * rng.uniform(0.85, 1.15)))

    if "mortes" not in p or p.get("mortes") in (None, 0, 100, 200):
        base_m = 40 + escalada * 4
        p["mortes"] = max(10, int(base_m * mult * rng.uniform(0.9, 1.2)))

    if "paises" not in p or not p.get("paises"):
        p["paises"] = max(1, min(15, 2 + int(escalada / 25) + (1 if mult > 1 else 0)))

    if "regioes" not in p or not p.get("regioes"):
        p["regioes"] = max(1, min(5, 1 + int(escalada / 40)))

    if "conflitos" not in p or not p.get("conflitos"):
        p["conflitos"] = max(1, int(2 + escalada / 20 * mult))

    if "choque" not in p:
        p["choque"] = 1 if sentimento in SENTIMENTO_CHOQUE and SENTIMENTO_CHOQUE[sentimento] else (
            1 if escalada >= 65 else 0
        )

    p["intensidade"] = intensidade
    p["probabilidade_escalada_pct"] = escalada
    return p
