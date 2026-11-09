import os
import shutil
import sys
from collections import defaultdict

import config
from langchain_chroma import Chroma
from poker.rag import _embeddings

vs = Chroma(persist_directory=config.CHROMA_DIR, embedding_function=_embeddings())
dados = vs._collection.get(include=["documents"])
grupos = defaultdict(list)
for i, texto in zip(dados["ids"], dados["documents"]):
    grupos[texto].append(i)
extras = [i for ids in grupos.values() for i in ids[1:]]
caracteres = sum(len(t) for t in grupos)
print(f"Trechos no índice: {len(dados['ids'])}")
print(f"Trechos únicos:    {len(grupos)}")
print(f"Cópias repetidas:  {len(extras)}")
print(f"Caracteres nos trechos únicos: {caracteres}")

if extras and "--remover" in sys.argv:
    backup = config.CHROMA_DIR + "_backup"
    if not os.path.exists(backup):
        shutil.copytree(config.CHROMA_DIR, backup)
    for k in range(0, len(extras), 5000):
        vs._collection.delete(ids=extras[k:k + 5000])
    print(f"Duplicatas removidas. Trechos restantes: {vs._collection.count()} (backup em {backup})")
