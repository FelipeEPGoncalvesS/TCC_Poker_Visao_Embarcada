import argparse
from math import comb

import pandas as pd

from poker.cartas import avaliar_mao
from poker.estrategia import RegrasPreFlop, fast_path_pos_flop, fast_path_pre_flop, situacao_estrategica

NAIPES = {"♥": "Hearts", "♦": "Diamonds", "♠": "Spades", "♣": "Trefoils"}
FICHA_PRE = {
    "medios_inicial": "Fold",
    "medios_final": "Raise",
    "medios_blinds": "Call/Check",
    "conectores_naipes_inicial": "Fold",
    "conectores_naipes_final": "Call/Check",
    "conectores_naipes_blinds": "Call/Check",
}
SEM_RAG = {"sem RAG", "sem"}
regras = RegrasPreFlop()


def rotulos(texto):
    if not isinstance(texto, str) or not texto.strip():
        return []
    return [f"{c[:-1]} {NAIPES[c[-1]]}" for c in texto.split()]


def normalizar(acao):
    acao = str(acao or "").strip().lower()
    if acao in ("raise", "bet"):
        return "Raise"
    if acao in ("call", "check", "call/check"):
        return "Call/Check"
    return "Fold"


def ficha_pos_flop(situacao, rua):
    if situacao in ("forte", "dois_pares"):
        return "Raise"
    if situacao in ("overpair", "top_pair"):
        return "Call/Check" if rua == "RIVER" else "Raise"
    if situacao == "par_medio":
        return "Call/Check"
    if situacao == "projeto_forte":
        return "Call/Check" if rua == "FLOP" else "Fold"
    return "Fold"


def so_regras(rua, posicao, mao, mesa):
    mao, mesa = rotulos(mao), rotulos(mesa)
    if rua == "PRÉ-FLOP":
        pre = regras.consultar(mao)
        rapido = fast_path_pre_flop(pre["categoria"], posicao)
        if rapido:
            return normalizar(rapido)
        if pre["categoria"] in ("premium", "fortes"):
            return "Raise"
        return FICHA_PRE.get(situacao_estrategica(rua, None, pre, posicao), "Fold")
    avaliacao = avaliar_mao(mao, mesa)
    rapido = fast_path_pos_flop(avaliacao)
    if rapido:
        return normalizar(rapido)
    return ficha_pos_flop(situacao_estrategica(rua, avaliacao, None, posicao), rua)


def erro_grave(acao, ref):
    return {acao, ref} == {"Raise", "Fold"}


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def avaliar(arquivo):
    dados = pd.read_csv(arquivo, sep=";")
    col_llm = "acao_llm" if "acao_llm" in dados else "acao"
    sit = dados.drop_duplicates("id").set_index("id").copy()
    sit["regras"] = [so_regras(r.rua, r.posicao, r.mao, r.mesa) for r in sit.itertuples()]
    llm = dados[dados.config.isin(SEM_RAG)].set_index("id")[col_llm].map(normalizar).reindex(sit.index)
    ref = sit.ref_acao
    linhas = {"Sempre Fold": pd.Series("Fold", index=sit.index), "Só regras (sem LLM)": sit.regras}
    if llm.notna().all():
        linhas["LLM sem RAG"] = llm
    print(f"\n{arquivo} ({len(sit)} situações)")
    print(f"{'Política':<22}{'Concordância':>14}{'Erros graves':>14}")
    for nome, acoes in linhas.items():
        conc = (acoes == ref).mean() * 100
        grav = sum(erro_grave(a, r) for a, r in zip(acoes, ref)) / len(ref) * 100
        print(f"{nome:<22}{conc:>13.1f}%{grav:>13.1f}%")
    ok_regras, ok_llm = sit.regras == ref, llm == ref
    if "LLM sem RAG" in linhas:
        b, c = int((ok_regras & ~ok_llm).sum()), int((~ok_regras & ok_llm).sum())
        print(f"Só regras x LLM sem RAG: {b} x {c}, McNemar p = {mcnemar(b, c):.3f}")
    if "acao_sistema" in dados and "LLM sem RAG" in linhas:
        sis = dados[dados.config.isin(SEM_RAG)].set_index("id").acao_sistema.map(normalizar).reindex(sit.index)
        ok_sis = sis == ref
        b, c = int((ok_regras & ~ok_sis).sum()), int((~ok_regras & ok_sis).sum())
        print(f"Só regras x sistema híbrido: {b} x {c}, McNemar p = {mcnemar(b, c):.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="+")
    for arquivo in parser.parse_args().csv:
        avaliar(arquivo)
