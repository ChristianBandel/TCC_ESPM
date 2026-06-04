"""
Painel web TCC — pipeline + cenarios Groq + previsao ML.

Uso:
    python web/server.py
    http://127.0.0.1:5000
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
WEB_DIR = Path(__file__).resolve().parent

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    print("ERRO: Flask nao instalado. Execute: python -m pip install -r requirements.txt")
    sys.exit(1)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from tcc.config_loader import load_settings  # noqa: E402
from tcc.groq_scenarios import gerar_cenarios  # noqa: E402
from tcc.scenario_params import enrich_scenario_params  # noqa: E402
from tcc.paths import resolve  # noqa: E402
from tcc.oil_price import obter_preco_atual  # noqa: E402
from tcc.predict import prever_cenario  # noqa: E402

PYTHON = sys.executable
app = Flask(__name__, static_folder=str(WEB_DIR / "static"), static_url_path="/static")

ACTIONS = {
    "coleta_petroleo": ["1_Coleta_Dados/coletar_petroleo.py"],
    "coleta_conflitos": ["1_Coleta_Dados/coletar_conflitos.py"],
    "coleta_indicadores": ["1_Coleta_Dados/coletar_indicadores.py"],
    "preparacao": ["2_Preparacao_Dados/preparar_dataset.py"],
    "modelagem": ["3_Modelagem/treinar_modelo.py"],
    "pipeline": ["executar_pipeline.py"],
}


def run_cmd(args: list[str]) -> tuple[int, str]:
    cmd = [PYTHON]
    for a in args:
        script = ROOT / a
        cmd.append(str(script) if script.suffix == ".py" else a)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def modelos_prontos() -> bool:
    cfg = load_settings()
    return resolve(cfg["caminhos"]["metadados"]).exists()


@app.route("/")
def index():
    return send_from_directory(WEB_DIR / "templates", "index.html")


@app.route("/api/status")
def api_status():
    preco = None
    try:
        preco = obter_preco_atual()
    except Exception:
        pass
    return jsonify({
        "modelos": modelos_prontos(),
        "groq": bool(os.getenv("GROQ_API_KEY", "").strip()),
        "petroleo": resolve(load_settings()["caminhos"]["raw_petroleo"]).exists(),
        "conflitos": resolve(load_settings()["caminhos"]["raw_conflitos"]).exists(),
        "preco_atual": preco,
    })


@app.route("/api/modelo/metricas")
def api_modelo_metricas():
    cfg = load_settings()
    meta_path = resolve(cfg["caminhos"]["metadados"])
    charts_path = resolve(cfg["caminhos"].get("graficos_metricas", "dados/models/graficos_metricas.json"))
    if not meta_path.exists():
        return jsonify({"ok": False, "error": "Modelo nao treinado. Clique em Treinar ML."}), 404
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    avaliacao = meta.get("avaliacao")
    if not avaliacao and charts_path.exists():
        avaliacao = json.loads(charts_path.read_text(encoding="utf-8"))
    if not avaliacao:
        return jsonify({
            "ok": True,
            "meta": meta,
            "aviso": "Retreine o modelo para gerar graficos (python 3_Modelagem/treinar_modelo.py).",
        })
    return jsonify({"ok": True, "meta": meta, "avaliacao": avaliacao})


@app.route("/api/preco-atual")
def api_preco_atual():
    try:
        info = obter_preco_atual()
        return jsonify({"ok": True, **info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True) or {}
    action = data.get("action", "")
    try:
        if action not in ACTIONS:
            return jsonify({"ok": False, "error": f"Acao desconhecida: {action}"}), 400
        code, out = run_cmd(ACTIONS[action])
        return jsonify({"ok": code == 0, "code": code, "output": out[-12000:]})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Timeout (>10 min)"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cenarios/gerar", methods=["POST"])
def api_gerar_cenarios():
    data = request.get_json(force=True) or {}
    qtd = min(10, max(1, int(data.get("quantidade", 3))))
    modo = data.get("modo", "auto")
    tema = data.get("tema")
    try:
        cenarios, fonte = gerar_cenarios(quantidade=qtd, modo=modo, tema=tema)
        cenarios = [enrich_scenario_params(c, seed=i) for i, c in enumerate(cenarios)]
        return jsonify({"ok": True, "fonte": fonte, "cenarios": cenarios})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/cenarios/prever", methods=["POST"])
def api_prever():
    data = request.get_json(force=True) or {}
    cenario = data.get("cenario")
    if not cenario:
        return jsonify({"ok": False, "error": "Cenario ausente"}), 400
    if data.get("preco_atual"):
        cenario = {**cenario, "preco_atual": float(data["preco_atual"])}
    try:
        resultado = prever_cenario(cenario)
        return jsonify({"ok": True, "resultado": resultado})
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cenarios/prever-todos", methods=["POST"])
def api_prever_todos():
    data = request.get_json(force=True) or {}
    cenarios = data.get("cenarios") or []
    if not cenarios:
        return jsonify({"ok": False, "error": "Lista de cenarios vazia"}), 400
    preco_manual = data.get("preco_atual")
    try:
        resultados = []
        for c in cenarios:
            params = dict(c)
            if preco_manual:
                params["preco_atual"] = float(preco_manual)
            resultados.append(prever_cenario(params))
        return jsonify({"ok": True, "resultados": resultados})
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("Painel TCC: http://127.0.0.1:5000")
    if not os.getenv("GROQ_API_KEY"):
        print("  Dica: defina GROQ_API_KEY no .env para cenarios via Groq")
    app.run(host="127.0.0.1", port=5000, debug=False)
