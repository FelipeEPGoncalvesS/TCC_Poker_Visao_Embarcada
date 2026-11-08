import re
from collections import Counter
from itertools import combinations

VALORES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
PESO = {v: i + 2 for i, v in enumerate(VALORES)}
NOME_VALOR = {p: v for v, p in PESO.items()}
NAIPES = ["Hearts", "Diamonds", "Spades", "Trefoils"]
SIMBOLO = {"Hearts": "♥", "Diamonds": "♦", "Spades": "♠", "Trefoils": "♣"}
ROTULOS_VALIDOS = {f"{v} {n}" for v in VALORES for n in NAIPES}

CATEGORIAS = [
    "Carta Alta", "Par", "Dois Pares", "Trinca", "Sequência",
    "Flush", "Full House", "Quadra", "Straight Flush",
]

_NAIPE_ALIAS = {
    "hearts": "Hearts", "copas": "Hearts", "h": "Hearts", "♥": "Hearts",
    "diamonds": "Diamonds", "ouros": "Diamonds", "d": "Diamonds", "♦": "Diamonds",
    "spades": "Spades", "espadas": "Spades", "s": "Spades", "♠": "Spades",
    "trefoils": "Trefoils", "clubs": "Trefoils", "paus": "Trefoils", "c": "Trefoils", "♣": "Trefoils",
}
_VALOR_ALIAS = {"t": "10", "j": "J", "q": "Q", "k": "K", "a": "A"}

_PADRAO_CARTA = re.compile(
    r"(10|[2-9]|[tjqka])\s*"
    r"(hearts|diamonds|spades|trefoils|clubs|copas|ouros|espadas|paus|[hdsc♥♦♠♣])"
    r"(?![a-z])",
    re.IGNORECASE,
)


def interpretar_texto(texto):
    rotulos = []
    for valor, naipe in _PADRAO_CARTA.findall(texto or ""):
        v = _VALOR_ALIAS.get(valor.lower(), valor.upper())
        n = _NAIPE_ALIAS[naipe.lower()]
        rotulo = f"{v} {n}"
        if rotulo not in rotulos:
            rotulos.append(rotulo)
    if not rotulos:
        raise ValueError(
            "Nenhuma carta reconhecida. Use, por exemplo: '8 Hearts, 8 Trefoils' ou '8h 8c'."
        )
    return rotulos


def ler(rotulo):
    valor, naipe = rotulo.split()
    return PESO[valor], naipe


def exibir(rotulo):
    valor, naipe = rotulo.split()
    return f"{valor}{SIMBOLO.get(naipe, '?')}"


def normalizar_para_chave(cartas):
    v_map = {"10": "T"}
    pares = sorted((ler(c) for c in cartas), key=lambda x: x[0], reverse=True)
    v_str = "".join(v_map.get(NOME_VALOR[p], NOME_VALOR[p]) for p, _ in pares)
    if pares[0][0] == pares[1][0]:
        return v_str
    return v_str + ("s" if pares[0][1] == pares[1][1] else "o")


def _maior_sequencia(pesos):
    s = set(pesos)
    if 14 in s:
        s.add(1)
    for topo in range(14, 4, -1):
        if all(p in s for p in range(topo - 4, topo + 1)):
            return topo
    return None


def _pontuar_5(cartas):
    pesos = sorted((p for p, _ in cartas), reverse=True)
    cont = Counter(pesos)
    grupos = sorted(cont.items(), key=lambda x: (x[1], x[0]), reverse=True)
    flush = len({n for _, n in cartas}) == 1
    seq = _maior_sequencia(pesos) if len(cont) == 5 else None

    if flush and seq:
        return (8, seq)
    if grupos[0][1] == 4:
        return (7, grupos[0][0], grupos[1][0])
    if grupos[0][1] == 3 and grupos[1][1] == 2:
        return (6, grupos[0][0], grupos[1][0])
    if flush:
        return (5, *pesos)
    if seq:
        return (4, seq)
    if grupos[0][1] == 3:
        return (3, grupos[0][0], *[p for p, _ in grupos[1:]])
    if grupos[0][1] == 2 and grupos[1][1] == 2:
        return (2, grupos[0][0], grupos[1][0], grupos[2][0])
    if grupos[0][1] == 2:
        return (1, grupos[0][0], *[p for p, _ in grupos[1:]])
    return (0, *pesos)


def _pontuar_parcial(cartas):
    cont = Counter(p for p, _ in cartas)
    qtds = sorted(cont.values(), reverse=True)
    if not qtds:
        return (0,)
    if qtds[0] >= 4:
        return (7,)
    if qtds[0] == 3:
        return (3,)
    if qtds[0] == 2 and len(qtds) > 1 and qtds[1] == 2:
        return (2,)
    if qtds[0] == 2:
        return (1,)
    return (0,)


def melhor_pontuacao(cartas):
    if len(cartas) >= 5:
        return max(_pontuar_5(c) for c in combinations(cartas, 5))
    return _pontuar_parcial(cartas)


def _valores_que_completam_sequencia(pesos_todos, pesos_mesa):
    faltantes = set()
    for r in range(2, 15):
        if r in pesos_todos:
            continue
        if _maior_sequencia(list(pesos_todos) + [r]) and not _maior_sequencia(list(pesos_mesa) + [r]):
            faltantes.add(r)
    return faltantes


def _projetos(mao_c, mesa_c, nivel):
    if not 3 <= len(mesa_c) <= 4:
        return []
    projetos = []
    todas = mao_c + mesa_c
    if nivel < 5:
        for naipe, qtd in Counter(n for _, n in todas).items():
            if qtd == 4 and any(n == naipe for _, n in mao_c):
                projetos.append(f"projeto de flush de {SIMBOLO[naipe]} (9 outs)")
    if nivel < 4:
        faltam = _valores_que_completam_sequencia({p for p, _ in todas}, {p for p, _ in mesa_c})
        if len(faltam) >= 2:
            projetos.append("projeto de sequência aberta (8 outs)")
        elif len(faltam) == 1:
            projetos.append("projeto de sequência interna/gutshot (4 outs)")
    return projetos


def _detalhe(nivel, mao_c, mesa_c):
    pm = [p for p, _ in mao_c]
    pmesa = [p for p, _ in mesa_c]
    par_na_mao = pm[0] == pm[1]
    if nivel == 1:
        if par_na_mao:
            if pm[0] > max(pmesa):
                return "overpair — par na mão acima de todas as cartas da mesa"
            return "underpair — par na mão abaixo da carta mais alta da mesa"
        par = next((p for p in pm if p in pmesa), None)
        if par is None:
            return "par apenas na mesa"
        if par == max(pmesa):
            return f"par alto/top pair de {NOME_VALOR[par]}"
        if par == min(pmesa):
            return f"par baixo/bottom pair de {NOME_VALOR[par]}"
        return f"par médio/middle pair de {NOME_VALOR[par]}"
    if nivel == 3:
        if par_na_mao and pm[0] in pmesa:
            return f"set de {NOME_VALOR[pm[0]]} — par na mão + carta igual na mesa"
        return "trips — uma carta da mão + par da mesa"
    if nivel == 2:
        usados = [p for p in pm if p in pmesa]
        if len(set(usados)) == 2:
            return "dois pares usando as duas cartas da mão"
        if usados or par_na_mao:
            return "dois pares usando uma carta da mão e um par da mesa"
    return ""


_ADJETIVO = {
    0: "Mão fraca, sem pareamento.",
    1: "Mão de força média.",
    2: "Mão de força média-alta.",
}


def avaliar_mao(mao, mesa):
    mao_c = [ler(c) for c in mao]
    mesa_c = [ler(c) for c in mesa]

    if not mesa_c:
        par = mao_c[0][0] == mao_c[1][0]
        return {
            "categoria": "Par" if par else "Carta Alta",
            "nivel": 1 if par else 0,
            "detalhe": "par na mão" if par else "",
            "projetos": [],
            "so_mesa": False,
            "descricao": "Pré-flop: par na mão." if par else "Pré-flop: sem par na mão.",
            "texto_rag": "par na mão" if par else "cartas não pareadas",
        }

    pont_total = melhor_pontuacao(mao_c + mesa_c)
    pont_mesa = melhor_pontuacao(mesa_c)
    nivel = pont_total[0]
    categoria = CATEGORIAS[nivel]

    so_mesa = (
        nivel >= 1
        and nivel == pont_mesa[0]
        and not (nivel >= 4 and len(mesa_c) == 5 and pont_total > pont_mesa)
    )
    detalhe = "" if so_mesa else _detalhe(nivel, mao_c, mesa_c)
    projetos = _projetos(mao_c, mesa_c, nivel)

    partes = [categoria + (f" ({detalhe})" if detalhe else "") + "."]
    if so_mesa:
        partes.append(f"Atenção: a {categoria.lower()} está inteira na mesa — as cartas do jogador não melhoram o jogo, só servem de kicker.")
    else:
        partes.append(_ADJETIVO.get(nivel, "Mão muito forte."))
    if projetos:
        partes.append("Projetos: " + ", ".join(projetos) + ".")

    texto_rag = categoria.lower()
    if detalhe:
        texto_rag += " " + detalhe.split(" — ")[0]
    if projetos:
        texto_rag += " com " + " e ".join(p.split(" (")[0] for p in projetos)
    if so_mesa:
        texto_rag = f"jogo apenas na mesa ({categoria.lower()})"

    return {
        "categoria": categoria,
        "nivel": nivel,
        "detalhe": detalhe,
        "projetos": projetos,
        "so_mesa": so_mesa,
        "descricao": " ".join(partes),
        "texto_rag": texto_rag,
    }
