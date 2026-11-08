import json
import threading
import uuid

import config
from .cartas import exibir

ETAPAS = [
    ("mao", 2, "Mão", "PRÉ-FLOP"),
    ("flop", 3, "Flop", "FLOP"),
    ("turn", 1, "Turn", "TURN"),
    ("river", 1, "River", "RIVER"),
]
ORDEM = [e[0] for e in ETAPAS]
QTD = {e[0]: e[1] for e in ETAPAS}
NOME = {e[0]: e[2] for e in ETAPAS}
FASE = {e[0]: e[3] for e in ETAPAS}


class Partida:
    def __init__(self):
        self._lock = threading.RLock()
        self.nova_mao(None)

    def nova_mao(self, posicao):
        with self._lock:
            self.id = uuid.uuid4().hex[:8]
            self.posicao = posicao
            self.cartas = {k: [] for k in ORDEM}
            self.tempos = {k: {} for k in ORDEM}
            self.decisoes = []
            self._salvar_json()

    def etapa_completa(self, etapa):
        return len(self.cartas[etapa]) == QTD[etapa]

    def proxima_etapa(self):
        for etapa in ORDEM:
            if not self.etapa_completa(etapa):
                return etapa
        return None

    def ultima_etapa_completa(self):
        ultima = None
        for etapa in ORDEM:
            if not self.etapa_completa(etapa):
                break
            ultima = etapa
        return ultima

    def mesa(self):
        return self.cartas["flop"] + self.cartas["turn"] + self.cartas["river"]

    def registrar(self, etapa, candidatas, tempos=None):
        with self._lock:
            if etapa not in QTD:
                raise ValueError(f"Etapa inválida: {etapa}")
            if self.posicao is None:
                raise ValueError("Escolha a posição e inicie uma nova mão primeiro.")
            indice = ORDEM.index(etapa)
            for anterior in ORDEM[:indice]:
                if not self.etapa_completa(anterior):
                    raise ValueError(f"Complete a etapa '{NOME[anterior]}' antes de registrar '{NOME[etapa]}'.")

            for posterior in ORDEM[indice + 1:]:
                self.cartas[posterior] = []
                self.tempos[posterior] = {}

            usadas = {c for e in ORDEM[:indice] for c in self.cartas[e]}
            avisos = []
            ignoradas = [c for c in candidatas if c in usadas]
            novas = [c for c in candidatas if c not in usadas]
            if ignoradas:
                avisos.append("Ignoradas por já estarem em outra etapa: " + ", ".join(exibir(c) for c in ignoradas))

            necessario = QTD[etapa]
            aceitas = novas[:necessario]
            if len(novas) > necessario:
                avisos.append(
                    f"Foram encontradas {len(novas)} cartas novas; mantidas as {necessario} de maior confiança: "
                    + ", ".join(exibir(c) for c in aceitas)
                )
            if len(aceitas) < necessario:
                avisos.append(
                    f"{NOME[etapa]} precisa de {necessario} carta(s), mas só {len(aceitas)} foi(ram) encontrada(s). "
                    "Capture de novo ou digite as cartas manualmente."
                )

            self.cartas[etapa] = aceitas
            self.tempos[etapa] = tempos or {}
            self._salvar_json()
            return aceitas, avisos

    def adicionar_decisao(self, decisao):
        with self._lock:
            self.decisoes.append(decisao)

    def para_dict(self):
        with self._lock:
            return {
                "id": self.id,
                "posicao": self.posicao,
                "posicao_descritiva": config.POSICOES.get(self.posicao, self.posicao),
                "cartas": {k: list(v) for k, v in self.cartas.items()},
                "etapas": [
                    {"chave": k, "nome": NOME[k], "qtd": QTD[k], "registradas": len(self.cartas[k]),
                     "completa": self.etapa_completa(k)}
                    for k in ORDEM
                ],
                "proxima_etapa": self.proxima_etapa(),
                "ultima_etapa_completa": self.ultima_etapa_completa(),
                "decisoes": list(self.decisoes),
            }

    def _salvar_json(self):
        dados = {"posicao": config.POSICOES.get(self.posicao, self.posicao), "mao": self.cartas["mao"]}
        if self.cartas["flop"]:
            dados["flop"] = self.cartas["flop"]
        if self.cartas["turn"]:
            dados["turn"] = self.cartas["flop"] + self.cartas["turn"]
        if self.cartas["river"]:
            dados["river"] = self.mesa()
        try:
            with open(config.SESSAO_JSON, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=4)
        except OSError:
            pass
