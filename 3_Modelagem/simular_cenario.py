"""
Simula cenário hipotético de conflito e projeta volatilidade + retorno do petróleo.

Exemplo:
    python 3_Modelagem/simular_cenario.py ^
        --pais Ucrania --regiao "Europa Leste" --intensidade alto ^
        --eventos 25 --mortes 800 --semanas 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcc.predict import prever_cenario  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula cenário de conflito → petróleo")
    parser.add_argument("--pais", default="Desconhecido")
    parser.add_argument("--regiao", default="Outras")
    parser.add_argument("--intensidade", choices=["baixo", "medio", "alto"], default="medio")
    parser.add_argument("--eventos", type=int, default=10)
    parser.add_argument("--mortes", type=int, default=200)
    parser.add_argument("--paises", type=int, default=2)
    parser.add_argument("--regioes", type=int, default=1)
    parser.add_argument("--conflitos", type=int, default=1)
    parser.add_argument("--choque", type=int, default=1, help="1 = escalada súbita")
    parser.add_argument("--preco-atual", type=float, default=None)
    args = parser.parse_args()

    params = {
        "pais": args.pais,
        "regiao": args.regiao,
        "intensidade": args.intensidade,
        "eventos": args.eventos,
        "mortes": args.mortes,
        "paises": args.paises,
        "regioes": args.regioes,
        "conflitos": args.conflitos,
        "choque": args.choque,
        "preco_atual": args.preco_atual,
    }
    try:
        resultado = prever_cenario(params)
    except FileNotFoundError as e:
        print(f"ERRO: {e}")
        sys.exit(1)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
