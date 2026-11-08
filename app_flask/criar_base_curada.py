import json
import os
import shutil
import sys

import config
from poker.rag import PREFIXO_DOCUMENTO, _embeddings

RUAS_POS_FLOP = ("FLOP", "TURN", "RIVER")
SITUACOES_POS_FLOP = ["forte", "dois_pares", "overpair", "top_pair", "par_medio",
                      "par_baixo", "so_mesa", "projeto_forte", "projeto_fraco", "carta_alta"]
SEM_PROJETO_NO_RIVER = {"projeto_forte", "projeto_fraco"}


def esperadas(categorias_pre_flop):
    sits = {("PRÉ-FLOP", f"{c}_{g}") for c in categorias_pre_flop for g in ("inicial", "final", "blinds")}
    for rua in RUAS_POS_FLOP:
        for s in SITUACOES_POS_FLOP:
            if not (rua == "RIVER" and s in SEM_PROJETO_NO_RIVER):
                sits.add((rua, s))
    return sits


def main():
    with open(config.BASE_CURADA_JSON, encoding="utf-8") as f:
        fichas = json.load(f)["fichas"]

    ids = [x["id"] for x in fichas]
    if len(ids) != len(set(ids)):
        sys.exit("Há fichas com 'id' repetido no JSON.")

    try:
        with open(config.REGRAS_JSON_PATH, encoding="utf-8") as f:
            categorias = list(json.load(f)["manual_estrategia"]["categorias"])
    except Exception:
        categorias = ["premium", "fortes", "medios", "lixo_marginal"]
    existentes = {(x["rua"], x["situacao"]) for x in fichas}
    faltando = sorted(esperadas(categorias) - existentes)
    if faltando:
        print("Aviso: situações sem ficha (a busca usará a ficha mais próxima da mesma rua):")
        for rua, s in faltando:
            print(f"  {rua:<9} {s}")

    if os.path.isdir(config.CHROMA_CURADA_DIR):
        shutil.rmtree(config.CHROMA_CURADA_DIR)

    from langchain_chroma import Chroma
    textos = [PREFIXO_DOCUMENTO + x["texto"] for x in fichas]
    metadados = [{"id": x["id"], "rua": x["rua"], "situacao": x["situacao"],
                  "fonte": x.get("fonte") or "", "pagina": str(x.get("pagina") or "")} for x in fichas]
    vs = Chroma.from_texts(
        texts=textos, embedding=_embeddings(), metadatas=metadados, ids=ids,
        collection_name=config.COLECAO_CURADA, persist_directory=config.CHROMA_CURADA_DIR,
    )
    n = vs._collection.count()
    print(f"Base curada criada em {config.CHROMA_CURADA_DIR}: {n} fichas.")
    print("Para usar no Flask: RAG_FONTE=curada python app.py")


if __name__ == "__main__":
    main()
