"""Gera cenarios de conflito via Groq (JSON) ou amostragem aleatoria local."""

from __future__ import annotations

import json
import os
import random
import re
from typing import Any

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

REGIOES = [
    "Europa Leste",
    "Oriente Medio",
    "Norte da Africa",
    "Sahel",
    "Asia Central",
    "Sudeste Asiatico",
    "America Latina",
    "Outras",
]

PAISES_POR_REGIAO: dict[str, list[str]] = {
    "Europa Leste": ["Ukraine", "Russia", "Moldova"],
    "Oriente Medio": ["Syria", "Iraq", "Yemen", "Israel", "Palestine", "Iran"],
    "Norte da Africa": ["Libya", "Sudan", "Egypt"],
    "Sahel": ["Mali", "Niger", "Burkina Faso"],
    "Asia Central": ["Afghanistan", "Pakistan"],
    "Sudeste Asiatico": ["Myanmar", "Philippines"],
    "America Latina": ["Colombia", "Mexico"],
    "Outras": ["Ethiopia", "Somalia", "India"],
}

SYSTEM_PROMPT = """Voce e analista geopolitico para um TCC sobre petroleo e conflitos.
Responda APENAS com JSON valido (sem markdown), no formato:
{
  "cenarios": [
    {
      "titulo": "string curta",
      "pais": "string",
      "regiao": "string",
      "intensidade": "baixo|medio|alto",
      "sentimento_geopolitico": "calmo|tenso|critico",
      "probabilidade_escalada_pct": 0-100,
      "eventos_semana_estimados": inteiro >= 1,
      "mortes_semana_estimadas": inteiro >= 0,
      "paises_envolvidos": inteiro >= 1,
      "regioes_envolvidas": inteiro >= 1,
      "conflitos_paralelos": inteiro >= 1,
      "choque": true ou false,
      "raciocinio_curto": "1-2 frases em portugues"
    }
  ]
}
Baseie-se em tensoes geopoliticas plausiveis para os proximos meses (nao e previsao certa).
Varie regioes e intensidades entre os cenarios."""


def _parse_json_content(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def gerar_cenarios_groq(
    quantidade: int = 3,
    tema: str | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    key = api_key or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY nao configurada no .env")

    user_msg = f"Gere exatamente {quantidade} cenarios hipoteticos de escalada de conflitos."
    if tema:
        user_msg += f" Foco tematico: {tema}."
    user_msg += " Inclua impacto potencial em mercado de petroleo."

    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.9,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        },
        timeout=60,
    )
    if resp.status_code == 401:
        raise ValueError("Groq API key invalida. Crie em https://console.groq.com/keys")
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = _parse_json_content(content)
    cenarios = data.get("cenarios", data if isinstance(data, list) else [])
    return [_normalizar_cenario(c) for c in cenarios[:quantidade]]


def gerar_cenarios_aleatorios(quantidade: int = 3, seed: int | None = None) -> list[dict[str, Any]]:
    """Cenarios estocasticos baseados em faixas plausiveis (sem API)."""
    rng = random.Random(seed)
    intensidades = ["baixo", "medio", "alto"]
    sentimentos = ["calmo", "tenso", "critico"]
    out = []
    for i in range(quantidade):
        regiao = rng.choice(REGIOES)
        pais = rng.choice(PAISES_POR_REGIAO.get(regiao, ["Desconhecido"]))
        intensidade = rng.choices(intensidades, weights=[0.25, 0.45, 0.30])[0]
        mult = {"baixo": 1, "medio": 2.5, "alto": 5}[intensidade]
        mortes = int(rng.randint(20, 120) * mult)
        eventos = int(rng.randint(3, 25) * mult / 2)
        out.append(
            _normalizar_cenario(
                {
                    "titulo": f"Escalada simulada #{i + 1} — {pais}",
                    "pais": pais,
                    "regiao": regiao,
                    "intensidade": intensidade,
                    "sentimento_geopolitico": rng.choice(sentimentos),
                    "probabilidade_escalada_pct": rng.randint(15, 95),
                    "eventos_semana_estimados": eventos,
                    "mortes_semana_estimadas": mortes,
                    "paises_envolvidos": rng.randint(1, 6),
                    "regioes_envolvidas": rng.randint(1, 3),
                    "conflitos_paralelos": rng.randint(1, 8),
                    "choque": rng.random() < 0.35,
                    "raciocinio_curto": "Cenario gerado por amostragem estocastica para teste do modelo.",
                }
            )
        )
    return out


def _normalizar_cenario(raw: dict[str, Any]) -> dict[str, Any]:
    intensidade = str(raw.get("intensidade", "medio")).lower()
    if intensidade not in ("baixo", "medio", "alto"):
        intensidade = "medio"
    return {
        "titulo": str(raw.get("titulo", "Cenario sem titulo")),
        "pais": str(raw.get("pais", "Desconhecido")),
        "regiao": str(raw.get("regiao", "Outras")),
        "intensidade": intensidade,
        "sentimento": str(raw.get("sentimento_geopolitico", raw.get("sentimento", "tenso"))),
        "probabilidade_escalada_pct": int(raw.get("probabilidade_escalada_pct", 50)),
        "eventos": max(1, int(raw.get("eventos_semana_estimados", raw.get("eventos", 10)))),
        "mortes": max(0, int(raw.get("mortes_semana_estimadas", raw.get("mortes", 100)))),
        "paises": max(1, int(raw.get("paises_envolvidos", raw.get("paises", 2)))),
        "regioes": max(1, int(raw.get("regioes_envolvidas", raw.get("regioes", 1)))),
        "conflitos": max(1, int(raw.get("conflitos_paralelos", raw.get("conflitos", 1)))),
        "choque": 1 if raw.get("choque") in (True, 1, "true", "1") else 0,
        "raciocinio": str(raw.get("raciocinio_curto", raw.get("raciocinio", ""))),
    }


def gerar_cenarios(
    quantidade: int = 3,
    modo: str = "auto",
    tema: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    modo: auto | groq | aleatorio
    Retorna (cenarios, fonte).
    """
    if modo == "aleatorio":
        return gerar_cenarios_aleatorios(quantidade), "aleatorio"

    if modo == "groq" or (modo == "auto" and os.getenv("GROQ_API_KEY")):
        try:
            return gerar_cenarios_groq(quantidade, tema=tema), "groq"
        except Exception as e:
            if modo == "groq":
                raise
            fallback = gerar_cenarios_aleatorios(quantidade)
            for c in fallback:
                c["raciocinio"] = f"(Groq indisponivel: {e}) " + c.get("raciocinio", "")
            return fallback, "aleatorio_fallback"

    return gerar_cenarios_aleatorios(quantidade), "aleatorio"
