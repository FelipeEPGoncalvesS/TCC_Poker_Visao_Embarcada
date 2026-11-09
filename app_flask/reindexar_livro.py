import os
import shutil
import sys
import time
from collections import Counter

import config
from chromadb.api.client import SharedSystemClient
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from poker.rag import _embeddings

if len(sys.argv) < 2:
    sys.exit("Uso: python reindexar_livro.py caminho/do/livro.pdf")
pdf = os.path.expanduser(sys.argv[1])

original = config.CHROMA_DIR + "_backup"
alvo_diag = original if os.path.isdir(original) else config.CHROMA_DIR
if os.path.isdir(alvo_diag):
    vs = Chroma(persist_directory=alvo_diag, embedding_function=_embeddings())
    metas = vs._collection.get(include=["metadatas"])["metadatas"]
    fontes = Counter(os.path.basename(str((m or {}).get("source", "sem fonte"))) for m in metas)
    print(f"Índice original ({os.path.basename(alvo_diag)}): {len(metas)} trechos")
    for nome, n in fontes.most_common():
        print(f"  {n:>6}  {nome}")
    del vs
    SharedSystemClient.clear_system_cache()

from pypdf import PdfReader
paginas = [Document(page_content=p.extract_text() or "", metadata={"source": os.path.basename(pdf), "page": i})
           for i, p in enumerate(PdfReader(pdf).pages)]
divisor = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=60)
trechos = [t for t in divisor.split_documents(paginas) if t.page_content.strip()]
caracteres = sum(len(p.page_content) for p in paginas)
print(f"Livro: {len(paginas)} páginas, {caracteres} caracteres, {len(trechos)} trechos")

novo_dir = config.CHROMA_DIR + "_novo"
if os.path.exists(novo_dir):
    shutil.rmtree(novo_dir)
Chroma.from_documents(trechos, _embeddings(), persist_directory=novo_dir)
total = Chroma(persist_directory=novo_dir, embedding_function=_embeddings())._collection.count()
SharedSystemClient.clear_system_cache()

if os.path.exists(config.CHROMA_DIR):
    guardado = f"{config.CHROMA_DIR}_anterior_{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(config.CHROMA_DIR, guardado)
    print(f"Índice que estava em uso guardado em {guardado}")
shutil.move(novo_dir, config.CHROMA_DIR)
print(f"Novo índice: {total} trechos em {config.CHROMA_DIR}")
