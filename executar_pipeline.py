"""
Executor do pipeline TCC (sem coleta — faça coleta manual antes).

Etapas:
  1. Preparação de dados
  2. Treinamento do modelo
  3. (opcional) Simulação de cenário

Uso:
    python executar_pipeline.py
    python executar_pipeline.py --somente preparacao
    python executar_pipeline.py --cenario
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def run_script(rel_path: str, extra_args: list[str] | None = None) -> int:
    script = ROOT / rel_path
    cmd = [PYTHON, str(script)] + (extra_args or [])
    print(f"\n{'='*60}\n>> {' '.join(cmd)}\n{'='*60}")
    return subprocess.call(cmd, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline TCC — preparação + modelagem")
    parser.add_argument(
        "--somente",
        choices=["preparacao", "modelagem", "cenario"],
        help="Executa apenas uma etapa",
    )
    parser.add_argument("--cenario", action="store_true", help="Roda simulação de exemplo ao final")
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = []
    if args.somente == "preparacao":
        steps = [("2_Preparacao_Dados/preparar_dataset.py", [])]
    elif args.somente == "modelagem":
        steps = [("3_Modelagem/treinar_modelo.py", [])]
    elif args.somente == "cenario":
        steps = [
            (
                "3_Modelagem/simular_cenario.py",
                ["--pais", "Ucrania", "--regiao", "Europa Leste", "--intensidade", "alto", "--mortes", "500"],
            )
        ]
    else:
        steps = [
            ("2_Preparacao_Dados/preparar_dataset.py", []),
            ("3_Modelagem/treinar_modelo.py", []),
        ]
        if args.cenario:
            steps.append(
                (
                    "3_Modelagem/simular_cenario.py",
                    ["--pais", "Ucrania", "--regiao", "Europa Leste", "--intensidade", "alto"],
                )
            )

    for script, extra in steps:
        code = run_script(script, extra)
        if code != 0:
            print(f"\nFalha em {script} (código {code})")
            sys.exit(code)

    print("\nPipeline concluído com sucesso.")


if __name__ == "__main__":
    main()
