import csv
import os
import threading
from datetime import datetime

import config

CAMPOS = [
    "data_hora", "fase", "posicao", "mao", "mesa", "categoria", "descricao",
    "caminho", "acao", "acao_llm", "corrigida", "coerente", "formato_valido",
    "t_captura_s", "t_deteccao_s", "t_retrieval_s", "t_geracao_s", "t_decisao_s",
    "tokens_prompt", "tokens_gerados", "tokens_por_s",
    "trechos_usados", "cpu_pct", "ram_pct", "temp_c",
]

_lock = threading.Lock()

try:
    import psutil
    psutil.cpu_percent(interval=None)
except Exception:
    psutil = None


def temperatura_cpu():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def metricas_sistema():
    if psutil is None:
        return {"cpu_pct": None, "ram_pct": None, "ram_usada_mb": None, "temp_c": temperatura_cpu()}
    ram = psutil.virtual_memory()
    return {
        "cpu_pct": psutil.cpu_percent(interval=None),
        "ram_pct": ram.percent,
        "ram_usada_mb": round((ram.total - ram.available) / 2**20),
        "temp_c": temperatura_cpu(),
    }


def _arquivar_se_cabecalho_antigo():
    if not os.path.exists(config.BENCHMARK_CSV):
        return
    with open(config.BENCHMARK_CSV, encoding="utf-8") as f:
        cabecalho = f.readline().strip().split(";")
    if cabecalho != CAMPOS:
        raiz, ext = os.path.splitext(config.BENCHMARK_CSV)
        os.rename(config.BENCHMARK_CSV, f"{raiz}_antigo_{datetime.now():%Y%m%d-%H%M%S}{ext}")


def registrar(linha):
    os.makedirs(config.LOG_DIR, exist_ok=True)
    with _lock:
        _arquivar_se_cabecalho_antigo()
    novo = not os.path.exists(config.BENCHMARK_CSV)
    linha = {k: linha.get(k) for k in CAMPOS}
    linha["data_hora"] = linha["data_hora"] or datetime.now().isoformat(timespec="seconds")
    with _lock:
        with open(config.BENCHMARK_CSV, "a", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
            if novo:
                escritor.writeheader()
            escritor.writerow(linha)
