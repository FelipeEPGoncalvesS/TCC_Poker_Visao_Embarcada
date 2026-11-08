import json
import os

import config
from .cartas import exibir, normalizar_para_chave

ACOES_AGRESSIVAS = {"Raise", "Bet"}


class RegrasPreFlop:

    def __init__(self):
        self.disponivel = False
        self.erro = None
        self.categorias = {}
        try:
            with open(config.REGRAS_JSON_PATH, "r", encoding="utf-8") as f:
                self.categorias = json.load(f)["manual_estrategia"]["categorias"]
            self.disponivel = True
        except FileNotFoundError:
            self.erro = f"Arquivo de regras não encontrado em {config.REGRAS_JSON_PATH}."
        except Exception as exc:
            self.erro = f"Falha ao ler o arquivo de regras ({exc})."

    def consultar(self, mao):
        chave = normalizar_para_chave(mao)
        for nome, dados in self.categorias.items():
            if chave in dados.get("tipos", []):
                return {"chave": chave, "categoria": nome, "estrategia": dados.get("estrategia", "")}
        if "lixo_marginal" in self.categorias:
            return {
                "chave": chave,
                "categoria": "lixo_marginal",
                "estrategia": self.categorias["lixo_marginal"].get("estrategia", ""),
            }
        return {"chave": chave, "categoria": "sem_regra", "estrategia": "Sem regra cadastrada para esta mão."}


def fast_path_pre_flop(categoria, posicao=None):
    if not config.USAR_FAST_PATH:
        return None
    acao = config.FAST_PATH_PRE_FLOP.get(categoria)
    if acao == "Fold" and posicao == "BB" and config.BB_CHECK_GRATIS:
        return "Check"
    return acao


def fast_path_pos_flop(avaliacao):
    if not config.USAR_FAST_PATH or avaliacao["so_mesa"]:
        return None
    acao = config.FAST_PATH_POS_FLOP.get(avaliacao["categoria"])
    if acao and avaliacao["categoria"] == "Carta Alta" and avaliacao["projetos"]:
        return None
    return acao


GRUPO_POSICAO = {"UTG": "inicial", "MP": "inicial", "CO": "final", "BTN": "final", "SB": "blinds", "BB": "blinds"}


def situacao_estrategica(fase, avaliacao=None, pre_flop=None, posicao=None):
    if fase == "PRÉ-FLOP":
        categoria = (pre_flop or {}).get("categoria", "sem_regra")
        return f"{categoria}_{GRUPO_POSICAO.get(posicao, 'inicial')}"
    a = avaliacao
    if a["so_mesa"]:
        return "so_mesa"
    if a["nivel"] >= 3:
        return "forte"
    if a["nivel"] == 2:
        return "dois_pares"
    if a["nivel"] == 1:
        d = a["detalhe"]
        if d.startswith("overpair"):
            return "overpair"
        if d.startswith("par alto"):
            return "top_pair"
        if d.startswith("par baixo"):
            return "par_baixo"
        if d.startswith("par apenas na mesa"):
            return "so_mesa"
        return "par_medio"
    projetos = " ".join(a["projetos"])
    if "flush" in projetos or "aberta" in projetos:
        return "projeto_forte"
    if "gutshot" in projetos:
        return "projeto_fraco"
    return "carta_alta"


def avaliar_coerencia(fase, acao, avaliacao=None, pre_flop=None, posicao=None):
    agressiva = acao in ACOES_AGRESSIVAS
    if fase == "PRÉ-FLOP" and pre_flop:
        if pre_flop["categoria"] == "lixo_marginal" and agressiva:
            segura = "Check" if posicao == "BB" else "Fold"
            return False, "Aposta agressiva com mão classificada como lixo/marginal pela regra.", segura
        return True, None, None
    if avaliacao:
        a = avaliacao
        if a["nivel"] >= 2 and not a["so_mesa"] and acao == "Fold":
            return False, f"Fold com {a['categoria']} — mão forte descartada.", "Call"
        if a["so_mesa"] and agressiva:
            return False, "Aposta agressiva com o jogo inteiro na mesa (as cartas do jogador só servem de kicker).", "Check/Fold"
        if a["nivel"] == 0 and not a["projetos"] and agressiva:
            return False, "Aposta agressiva com carta alta e sem projeto (blefe puro).", "Check/Fold"
        if (fase == "TURN" and a["nivel"] == 0 and agressiva
                and all("gutshot" in p for p in a["projetos"])):
            return False, "Aposta agressiva no turn com carta alta e só sequência interna (4 outs, cerca de 9%).", "Check/Fold"
    return True, None, None


def verificar_coerencia(fase, acao, avaliacao=None, pre_flop=None, posicao=None):
    coerente, alerta, _ = avaliar_coerencia(fase, acao, avaliacao, pre_flop, posicao)
    return coerente, alerta


FORMATO_RESPOSTA = """Responda em NO MÁXIMO duas linhas, estritamente neste formato:
- AÇÃO: [{opcoes}]
- MOTIVO: [uma frase curta, baseada na análise de força acima]"""


def prompt_pre_flop(pre_flop, posicao, contexto, rotulo="LIVRO"):
    return f"""[INSTRUÇÃO] Especialista em Poker. Escolha APENAS UMA ação definitiva (Fold, Call ou Raise).
1. REGRA: {pre_flop['estrategia']}
2. {rotulo}: {contexto or '(sem trecho relevante)'}
TAREFA: Mão {pre_flop['chave']} na posição {posicao}.
{FORMATO_RESPOSTA.format(opcoes='Fold, Call ou Raise')}"""


DIRETRIZES = {
    "FLOP": """- Se a força for TRINCA ou melhor: Ação deve ser Raise ou Bet (nunca Fold).
- Se a força for PAR: Check ou Call, dependendo da posição e do tipo de par.
- Se for CARTA ALTA: Check ou Fold se houver pressão, exceto com projeto forte.""",
    "TURN": """- Com mãos muito fortes: Raise ou Bet.
- Com pares médios/fracos ou sem jogo: Check ou Fold se houver pressão.
- Projetos perdem valor (resta só o river).""",
    "RIVER": """- Com mãos muito fortes: Value Bet ou Call contra apostas menores.
- Com mãos fracas ou carta alta: Check ou Fold frente a apostas do oponente.
- Não existem mais projetos: avalie só o valor de showdown.""",
}


def prompt_pos_flop(fase, mao, mesa, posicao, avaliacao, contexto, rotulo="CONTEXTO DO LIVRO"):
    return f"""[INSTRUÇÃO] Você é um especialista técnico em Poker analisando a fase {fase}.
- Mão do Jogador: {', '.join(exibir(c) for c in mao)}
- Cartas da Mesa: {', '.join(exibir(c) for c in mesa)}
- Posição: {posicao}
- ANÁLISE REAL DA FORÇA (calculada, confie nela): {avaliacao['descricao']}
- {rotulo}: {contexto or '(sem trecho relevante)'}

DIRETRIZES DE DECISÃO:
{DIRETRIZES[fase]}

{FORMATO_RESPOSTA.format(opcoes='Fold, Check, Call ou Raise')}"""
