import os
import time

import config
from . import benchmark
from .camera import Camera
from .cartas import avaliar_mao, exibir
from .detector import DetectorCartas
from .estrategia import (
    RegrasPreFlop, avaliar_coerencia, fast_path_pos_flop, fast_path_pre_flop,
    prompt_pos_flop, prompt_pre_flop, situacao_estrategica,
)
from .llm import ModeloLinguagem, interpretar_resposta
from .rag import criar_bases


class Assistente:
    def __init__(self, usar_camera=None):
        if usar_camera is False:
            config.USAR_CAMERA = False
        print("[init] Carregando componentes...")
        self.camera = Camera()
        print(f"[init] Câmera: {'ok' if self.camera.disponivel else self.camera.erro}")
        self.detector = DetectorCartas()
        print(f"[init] YOLO:   {'ok' if self.detector.disponivel else self.detector.erro}")
        self.regras = RegrasPreFlop()
        print(f"[init] Regras: {'ok' if self.regras.disponivel else self.regras.erro}")
        self.bases = criar_bases()
        for nome in ("livro", "curada"):
            b = self.bases[nome]
            print(f"[init] RAG {nome:<6} {'ok (' + str(b.n_trechos) + ' trechos)' if b.disponivel else b.erro}")
        self.base = self.bases.get(config.RAG_FONTE, self.bases["livro"])
        if not self.base.disponivel and config.USAR_RAG:
            print(f"[init] RAG_FONTE='{config.RAG_FONTE}' indisponível; usando o livro.")
            self.base = self.bases["livro"]
        print(f"[init] RAG em uso: {self.base.nome}")
        self.llm = ModeloLinguagem()
        print(f"[init] LLM:    {'simulação' if self.llm.mock else ('ok' if self.llm.disponivel else self.llm.erro)}")
        if config.AQUECER_LLM:
            self.llm.aquecer()

    def status(self):
        def item(disponivel, erro, extra=None):
            d = {"ok": bool(disponivel), "erro": None if disponivel else erro}
            if extra:
                d.update(extra)
            return d

        return {
            "camera": item(self.camera.disponivel, self.camera.erro),
            "yolo": item(self.detector.disponivel, self.detector.erro,
                         {"modelo": os.path.basename(config.YOLO_MODEL_PATH)}),
            "regras": item(self.regras.disponivel, self.regras.erro),
            "rag": item(self.base.disponivel, self.base.erro, {"trechos": self.base.n_trechos, "fonte": self.base.nome}),
            "llm": item(self.llm.disponivel, self.llm.erro,
                        {"modelo": config.LLM_MODEL, "simulacao": self.llm.mock, "aquecido": self.llm.aquecido}),
            "config": {
                "fast_path": config.USAR_FAST_PATH,
                "corrigir_incoerencia": config.CORRIGIR_INCOERENCIA,
                "k_retrieval": config.K_RETRIEVAL,
                "score_threshold": config.SCORE_THRESHOLD,
                "num_predict": config.NUM_PREDICT,
                "temperature": config.TEMPERATURE,
                "yolo_conf": config.YOLO_CONF,
            },
            "sistema": benchmark.metricas_sistema(),
        }

    def detectar(self, imagem_bgr, nome_arquivo=None):
        resultado = self.detector.detectar(imagem_bgr)
        if config.SALVAR_CAPTURAS and nome_arquivo:
            try:
                import cv2
                os.makedirs(config.IMAGES_DIR, exist_ok=True)
                cv2.imwrite(os.path.join(config.IMAGES_DIR, nome_arquivo), imagem_bgr)
            except Exception:
                pass
        return resultado

    def decidir(self, posicao, mao, mesa, forcar_llm=False, tempos_visao=None):
        posicao_desc = config.POSICOES.get(posicao, posicao)
        tempos_visao = tempos_visao or {}
        fase = {0: "PRÉ-FLOP", 3: "FLOP", 4: "TURN", 5: "RIVER"}.get(len(mesa))
        if fase is None:
            raise ValueError(f"Quantidade de cartas na mesa inválida: {len(mesa)}")

        t0 = time.perf_counter()
        pre_flop = None
        if fase == "PRÉ-FLOP":
            pre_flop = self.regras.consultar(mao)
            avaliacao = avaliar_mao(mao, [])
            avaliacao["categoria_regra"] = pre_flop["categoria"]
            avaliacao["descricao"] = (
                f"Mão {pre_flop['chave']} — categoria '{pre_flop['categoria']}' no arquivo de regras."
            )
            acao_direta = None if forcar_llm else fast_path_pre_flop(pre_flop["categoria"], posicao)
            consulta = f"jogar a mão {pre_flop['chave']} na posição {posicao_desc}"
        else:
            avaliacao = avaliar_mao(mao, mesa)
            acao_direta = None if forcar_llm else fast_path_pos_flop(avaliacao)
            consulta = f"estratégia no {fase.lower()} com {avaliacao['texto_rag']} na posição {posicao_desc}"

        trechos, prompt, resposta_bruta = [], None, None
        t_retrieval = t_geracao = 0.0
        tokens = {"tokens_prompt": None, "tokens_gerados": None, "tokens_por_s": None}
        formato_valido = True
        acao_llm, corrigida = None, False
        situacao = situacao_estrategica(fase, avaliacao, pre_flop, posicao)

        if acao_direta:
            caminho = "fast-path"
            acao = acao_direta
            motivo = (
                f"Fast-path: {avaliacao['categoria']} já define a jogada, então o LLM não foi acionado."
                if fase != "PRÉ-FLOP"
                else f"Fast-path: a regra de pré-flop ('{pre_flop['categoria']}') já define a jogada, então o LLM não foi acionado."
            )
        else:
            if not self.llm.disponivel:
                raise RuntimeError(self.llm.erro or "LLM indisponível.")
            contexto, trechos, t_retrieval = self.base.buscar(
                consulta, fase=fase, avaliacao=avaliacao, pre_flop=pre_flop, posicao=posicao)
            rotulo = {"rotulo": self.base.rotulo} if self.base.disponivel and self.base.rotulo else {}
            if fase == "PRÉ-FLOP":
                prompt = prompt_pre_flop(pre_flop, posicao_desc, contexto, **rotulo)
            else:
                prompt = prompt_pos_flop(fase, mao, mesa, posicao_desc, avaliacao, contexto, **rotulo)
            gerado = self.llm.gerar(prompt)
            t_geracao = gerado["tempo_s"]
            resposta_bruta = gerado["texto"]
            tokens = {k: gerado[k] for k in tokens}
            acao, motivo, formato_valido = interpretar_resposta(resposta_bruta)
            if not self.base.disponivel:
                caminho = "llm (sem RAG)"
            else:
                caminho = "rag curado+llm" if self.base.nome == "curada" else "rag+llm"

        acao_llm = acao if not acao_direta else None
        coerente, alerta, acao_segura = avaliar_coerencia(
            fase, acao, avaliacao=avaliacao, pre_flop=pre_flop, posicao=posicao)
        if not coerente and acao_segura and config.CORRIGIR_INCOERENCIA and not acao_direta:
            acao, corrigida = acao_segura, True
            alerta = f"{alerta} Ação do LLM ({acao_llm}) substituída por {acao_segura}."
        t_decisao = time.perf_counter() - t0
        sistema = benchmark.metricas_sistema()

        decisao = {
            "fase": fase,
            "posicao": posicao,
            "posicao_descritiva": posicao_desc,
            "mao": mao,
            "mesa": mesa,
            "avaliacao": avaliacao,
            "regra_pre_flop": pre_flop,
            "caminho": caminho,
            "acao": acao,
            "acao_llm": acao_llm,
            "corrigida": corrigida,
            "situacao": situacao,
            "motivo": motivo,
            "coerente": coerente,
            "alerta": alerta,
            "formato_valido": formato_valido,
            "consulta_rag": None if acao_direta else consulta,
            "trechos": trechos,
            "prompt": prompt,
            "resposta_bruta": resposta_bruta,
            "tempos": {
                "captura_s": round(tempos_visao.get("captura_s", 0.0), 3),
                "deteccao_s": round(tempos_visao.get("deteccao_s", 0.0), 3),
                "retrieval_s": round(t_retrieval, 3),
                "geracao_s": round(t_geracao, 3),
                "decisao_s": round(t_decisao, 3),
            },
            **tokens,
            "sistema": sistema,
        }

        benchmark.registrar({
            "fase": fase,
            "posicao": posicao,
            "mao": " ".join(exibir(c) for c in mao),
            "mesa": " ".join(exibir(c) for c in mesa),
            "categoria": avaliacao.get("categoria_regra") or avaliacao["categoria"],
            "descricao": avaliacao["descricao"],
            "caminho": caminho,
            "acao": acao,
            "acao_llm": acao_llm,
            "corrigida": corrigida,
            "coerente": coerente,
            "formato_valido": formato_valido,
            "t_captura_s": decisao["tempos"]["captura_s"],
            "t_deteccao_s": decisao["tempos"]["deteccao_s"],
            "t_retrieval_s": decisao["tempos"]["retrieval_s"],
            "t_geracao_s": decisao["tempos"]["geracao_s"],
            "t_decisao_s": decisao["tempos"]["decisao_s"],
            "trechos_usados": sum(1 for t in trechos if t["usado"]),
            **tokens,
            "cpu_pct": sistema["cpu_pct"],
            "ram_pct": sistema["ram_pct"],
            "temp_c": sistema["temp_c"],
        })
        return decisao

    def encerrar(self):
        self.camera.fechar()
