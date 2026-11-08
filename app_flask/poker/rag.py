import os
import time
import warnings

import config
from .estrategia import situacao_estrategica

PREFIXO_CONSULTA = "search_query: "
PREFIXO_DOCUMENTO = "search_document: "


def _embeddings():
    from langchain_ollama import OllamaEmbeddings
    kwargs = {"model": config.EMBEDDING_MODEL}
    if config.OLLAMA_HOST:
        kwargs["base_url"] = config.OLLAMA_HOST
    return OllamaEmbeddings(**kwargs)


class SemRAG:
    nome = "sem"
    rotulo = "CONTEXTO DO LIVRO"

    def __init__(self):
        self.disponivel = False
        self.erro = "RAG desativado."
        self.n_trechos = 0

    def buscar(self, consulta, **_):
        return "", [], 0.0


class BaseConhecimento:
    nome = "livro"
    rotulo = None

    def __init__(self):
        self.disponivel = False
        self.erro = None
        self.n_trechos = 0
        self._vs = None

        if not config.USAR_RAG:
            self.erro = "RAG desativado (USAR_RAG=0)."
            return
        if not os.path.isdir(config.CHROMA_DIR):
            self.erro = f"Índice Chroma não encontrado em {config.CHROMA_DIR}."
            return
        try:
            from langchain_chroma import Chroma
            from langchain_ollama import OllamaEmbeddings
        except Exception as exc:
            self.erro = f"langchain-chroma / langchain-ollama não instalados ({exc})."
            return
        try:
            kwargs = {"model": config.EMBEDDING_MODEL}
            if config.OLLAMA_HOST:
                kwargs["base_url"] = config.OLLAMA_HOST
            self._vs = Chroma(
                persist_directory=config.CHROMA_DIR,
                embedding_function=OllamaEmbeddings(**kwargs),
            )
            self.n_trechos = self._vs._collection.count()
            if self.n_trechos == 0:
                self.erro = "Índice Chroma aberto, mas sem trechos (coleção vazia)."
                return
            self.disponivel = True
        except Exception as exc:
            self.erro = f"Falha ao abrir o índice Chroma ({exc})."

    def buscar(self, consulta, **_):
        if not self.disponivel:
            return "", [], 0.0

        t0 = time.perf_counter()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resultados = self._vs.similarity_search_with_relevance_scores(
                consulta, k=config.K_RETRIEVAL
            )
        tempo = time.perf_counter() - t0

        limiar = config.SCORE_THRESHOLD
        trechos = []
        for doc, score in resultados:
            score = float(score)
            trechos.append({
                "texto": doc.page_content,
                "score": round(score, 3),
                "pagina": doc.metadata.get("page"),
                "usado": limiar < 0 or score >= limiar,
            })
        contexto = "\n".join(t["texto"] for t in trechos if t["usado"])
        return contexto, trechos, tempo


class BaseCurada:
    nome = "curada"
    rotulo = "ORIENTAÇÃO DA BASE DE ESTRATÉGIA"

    def __init__(self):
        self.disponivel = False
        self.erro = None
        self.n_trechos = 0
        self._vs = None
        if not os.path.isdir(config.CHROMA_CURADA_DIR):
            self.erro = (f"Base curada não encontrada em {config.CHROMA_CURADA_DIR}. "
                         "Rode: python criar_base_curada.py")
            return
        try:
            from langchain_chroma import Chroma
            self._vs = Chroma(
                collection_name=config.COLECAO_CURADA,
                persist_directory=config.CHROMA_CURADA_DIR,
                embedding_function=_embeddings(),
            )
            self.n_trechos = self._vs._collection.count()
            if self.n_trechos == 0:
                self.erro = "Base curada vazia. Rode: python criar_base_curada.py"
                return
            self.disponivel = True
        except Exception as exc:
            self.erro = f"Falha ao abrir a base curada ({exc})."

    def buscar(self, consulta, fase=None, avaliacao=None, pre_flop=None, posicao=None, **_):
        if not self.disponivel:
            return "", [], 0.0
        situacao = situacao_estrategica(fase, avaliacao, pre_flop, posicao)
        t0 = time.perf_counter()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            filtro = {"$and": [{"rua": fase}, {"situacao": situacao}]}
            resultados = self._vs.similarity_search_with_relevance_scores(
                PREFIXO_CONSULTA + consulta, k=1, filter=filtro)
            if not resultados:
                resultados = self._vs.similarity_search_with_relevance_scores(
                    PREFIXO_CONSULTA + consulta, k=1, filter={"rua": fase})
        tempo = time.perf_counter() - t0
        trechos = []
        for doc, score in resultados:
            texto = doc.page_content
            if texto.startswith(PREFIXO_DOCUMENTO):
                texto = texto[len(PREFIXO_DOCUMENTO):]
            trechos.append({
                "texto": texto,
                "score": round(float(score), 3),
                "pagina": doc.metadata.get("pagina"),
                "ficha": doc.metadata.get("id"),
                "situacao": situacao,
                "usado": True,
            })
        contexto = "\n".join(t["texto"] for t in trechos)
        return contexto, trechos, tempo


def criar_bases():
    return {"sem": SemRAG(), "livro": BaseConhecimento(), "curada": BaseCurada()}
