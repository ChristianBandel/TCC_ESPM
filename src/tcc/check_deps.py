"""Verifica dependencias antes de rodar os scripts."""

from __future__ import annotations

import sys

REQUIRED = [
    ("yaml", "pyyaml"),
    ("pandas", "pandas"),
    ("requests", "requests"),
    ("sklearn", "scikit-learn"),
    ("dotenv", "python-dotenv"),
]


def ensure_dependencies(extra: list[tuple[str, str]] | None = None) -> None:
    missing = []
    for mod, pip_name in REQUIRED + (extra or []):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    if missing:
        pkgs = " ".join(sorted(set(missing)))
        print(
            f"ERRO: pacotes ausentes no Python {sys.executable}\n"
            f"  Execute: python -m pip install -r requirements.txt\n"
            f"  Ou rode: .\\setup.ps1\n"
            f"  Faltando: {pkgs}"
        )
        sys.exit(1)
