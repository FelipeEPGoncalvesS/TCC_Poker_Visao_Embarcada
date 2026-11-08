import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_bool(nome, padrao):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes", "on")


def _env_float(nome, padrao):
    valor = os.getenv(nome)
    return float(valor) if valor not in (None, "") else padrao


def _env_int(nome, padrao):
    valor = os.getenv(nome)
    return int(valor) if valor not in (None, "") else padrao


YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", os.path.join(BASE_DIR, "Models", "bestNew_ncnn_model"))
REGRAS_JSON_PATH = os.getenv("REGRAS_JSON_PATH", os.path.join(BASE_DIR, "Regras mãos poker.json"))
CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(BASE_DIR, "chroma_db_poker"))
IMAGES_DIR = os.path.join(BASE_DIR, "Images")
LOG_DIR = os.path.join(BASE_DIR, "logs")
BENCHMARK_CSV = os.path.join(LOG_DIR, "benchmark.csv")
SESSAO_JSON = os.path.join(BASE_DIR, "sessao_poker.json")

USAR_CAMERA = _env_bool("USAR_CAMERA", True)
CAMERA_SIZE = (_env_int("CAMERA_LARGURA", 640), _env_int("CAMERA_ALTURA", 480))
CAMERA_WARMUP_S = _env_float("CAMERA_WARMUP_S", 2.0)
SALVAR_CAPTURAS = _env_bool("SALVAR_CAPTURAS", True)

YOLO_IMGSZ = _env_int("YOLO_IMGSZ", 640)
YOLO_CONF = _env_float("YOLO_CONF", 0.5)
YOLO_IOU = _env_float("YOLO_IOU", 0.3)

USAR_RAG = _env_bool("USAR_RAG", True)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
K_RETRIEVAL = _env_int("K_RETRIEVAL", 2)
SCORE_THRESHOLD = _env_float("SCORE_THRESHOLD", 0.35)

RAG_FONTE = os.getenv("RAG_FONTE", "livro")
BASE_CURADA_JSON = os.getenv("BASE_CURADA_JSON", os.path.join(BASE_DIR, "base_estrategia.json"))
CHROMA_CURADA_DIR = os.getenv("CHROMA_CURADA_DIR", os.path.join(BASE_DIR, "chroma_db_curada"))
COLECAO_CURADA = "estrategia_curada"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
NUM_PREDICT = _env_int("NUM_PREDICT", 60)
TEMPERATURE = _env_float("TEMPERATURE", 0.2)
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "30m")
AQUECER_LLM = _env_bool("AQUECER_LLM", True)

LLM_MOCK = _env_bool("LLM_MOCK", False)
LLM_MOCK_ATRASO_S = _env_float("LLM_MOCK_ATRASO_S", 1.5)

USAR_FAST_PATH = _env_bool("USAR_FAST_PATH", True)

FAST_PATH_POS_FLOP = {
    "Straight Flush": "Raise",
    "Quadra": "Raise",
    "Full House": "Raise",
    "Flush": "Raise",
    "Sequência": "Raise",
    "Trinca": "Raise",
    "Carta Alta": "Check/Fold",
}

FAST_PATH_PRE_FLOP = {
    "lixo_marginal": "Fold",
}
BB_CHECK_GRATIS = _env_bool("BB_CHECK_GRATIS", True)

CORRIGIR_INCOERENCIA = _env_bool("CORRIGIR_INCOERENCIA", True)

POSICOES = {
    "UTG": "Early Position (Under The Gun)",
    "MP": "Middle Position",
    "CO": "Cut-Off",
    "BTN": "Button",
    "SB": "Small Blind",
    "BB": "Big Blind",
}

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = _env_int("FLASK_PORT", 5000)
MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 10)
