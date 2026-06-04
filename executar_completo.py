"""
Executa coleta + preparacao + modelagem em sequencia.

Uso:
    python executar_completo.py
    python executar_completo.py --sem-petroleo   # so GED + pipeline (petroleo ja coletado)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
GED_PADRAO = ROOT / "1_Coleta_Dados" / "GEDEvent_v25_1.csv"


def run(args: list[str]) -> int:
    cmd = [PYTHON, *args]
    print(f"\n>> {' '.join(str(x) for x in cmd)}\n")
    return subprocess.call(cmd, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-petroleo", action="store_true")
    parser.add_argument("--ged", default=str(GED_PADRAO))
    args = parser.parse_args()

    if not Path(args.ged).exists():
        print(f"ERRO: GED nao encontrado em {args.ged}")
        sys.exit(1)

    steps = [
        ["1_Coleta_Dados/coletar_conflitos.py", "--csv", args.ged],
        ["1_Coleta_Dados/coletar_indicadores.py"],
    ]
    if not args.sem_petroleo:
        steps.append(["1_Coleta_Dados/coletar_petroleo.py"])
    steps.append(["executar_pipeline.py", "--cenario"])

    for s in steps:
        if run(s) != 0:
            sys.exit(1)
    print("\nFluxo completo OK.")


if __name__ == "__main__":
    main()
