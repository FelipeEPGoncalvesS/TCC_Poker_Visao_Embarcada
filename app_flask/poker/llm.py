import re
import threading
import time

import config

ACOES_VALIDAS = ["Fold", "Check", "Call", "Raise", "Bet"]


def _campo(resposta, nome):
    valor = getattr(resposta, nome, None)
    if valor is None:
        try:
            valor = resposta[nome]
        except Exception:
            valor = None
    return valor


def interpretar_resposta(texto):
    acao = None
    linha_acao = re.search(r"A[ÇC][ÃA]O\s*[:\-]\s*\**\s*\[?([^\n\]]+)", texto, re.IGNORECASE)
    alvo = linha_acao.group(1) if linha_acao else texto
    for candidata in ACOES_VALIDAS:
        if re.search(rf"\b{candidata}\b", alvo, re.IGNORECASE):
            acao = candidata
            break
    linha_motivo = re.search(r"MOTIVO\s*[:\-]\s*\**\s*\[?(.+)", texto, re.IGNORECASE | re.DOTALL)
    motivo = linha_motivo.group(1).strip().rstrip("]").strip() if linha_motivo else texto.strip()
    formato_valido = bool(linha_acao) and acao is not None and bool(linha_motivo)
    return acao or "Indefinida", motivo, formato_valido


class ModeloLinguagem:
    def __init__(self):
        self.disponivel = False
        self.erro = None
        self.mock = config.LLM_MOCK
        self.aquecido = False
        self._client = None

        if self.mock:
            self.disponivel = True
            self.aquecido = True
            return
        try:
            import ollama
        except Exception as exc:
            self.erro = f"Biblioteca 'ollama' não instalada ({exc})."
            return
        try:
            self._client = ollama.Client(host=config.OLLAMA_HOST) if config.OLLAMA_HOST else ollama.Client()
            self._client.show(config.LLM_MODEL)
            self.disponivel = True
        except Exception as exc:
            self.erro = (
                f"Não foi possível usar '{config.LLM_MODEL}' no Ollama ({exc}). "
                f"Verifique se o serviço está ativo e rode: ollama pull {config.LLM_MODEL}"
            )

    def aquecer(self):
        if self.mock or not self.disponivel:
            return

        def _tarefa():
            try:
                self._client.generate(
                    model=config.LLM_MODEL,
                    prompt="ok",
                    options={"num_predict": 1},
                    keep_alive=config.KEEP_ALIVE,
                )
                self.aquecido = True
            except Exception as exc:
                self.erro = f"Falha ao aquecer o modelo ({exc})."

        threading.Thread(target=_tarefa, daemon=True).start()

    def gerar(self, prompt):
        if not self.disponivel:
            raise RuntimeError(self.erro or "LLM indisponível.")

        t0 = time.perf_counter()
        if self.mock:
            time.sleep(config.LLM_MOCK_ATRASO_S)
            return {
                "texto": "- AÇÃO: Call\n- MOTIVO: (modo simulação) resposta fixa, o Ollama não foi chamado.",
                "tempo_s": time.perf_counter() - t0,
                "tokens_gerados": None,
                "tokens_por_s": None,
                "tokens_prompt": None,
            }

        resposta = self._client.chat(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": config.NUM_PREDICT, "temperature": config.TEMPERATURE},
            keep_alive=config.KEEP_ALIVE,
        )
        tempo = time.perf_counter() - t0
        mensagem = _campo(resposta, "message")
        texto = _campo(mensagem, "content") or ""

        eval_count = _campo(resposta, "eval_count")
        eval_duration = _campo(resposta, "eval_duration")
        tokens_por_s = None
        if eval_count and eval_duration:
            tokens_por_s = round(eval_count / (eval_duration / 1e9), 2)

        self.aquecido = True
        return {
            "texto": texto,
            "tempo_s": tempo,
            "tokens_gerados": eval_count,
            "tokens_por_s": tokens_por_s,
            "tokens_prompt": _campo(resposta, "prompt_eval_count"),
        }
