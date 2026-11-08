import atexit
import os
import socket

import numpy as np
from flask import Flask, jsonify, render_template, request, send_file

import config
from poker.cartas import interpretar_texto
from poker.partida import NOME, QTD, Partida
from poker.pipeline import Assistente

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024

assistente = Assistente()
partida = Partida()
atexit.register(assistente.encerrar)


def erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


@app.get("/")
def index():
    return render_template("index.html", posicoes=config.POSICOES)


@app.get("/api/status")
def api_status():
    return jsonify(assistente.status())


@app.get("/api/estado")
def api_estado():
    return jsonify(partida.para_dict())


@app.post("/api/nova-mao")
def api_nova_mao():
    dados = request.get_json(silent=True) or {}
    posicao = (dados.get("posicao") or "").upper().strip()
    if posicao not in config.POSICOES:
        return erro(f"Posição inválida. Use uma de: {', '.join(config.POSICOES)}.")
    partida.nova_mao(posicao)
    return jsonify(partida.para_dict())


@app.post("/api/cartas")
def api_cartas():
    etapa = request.form.get("etapa") or partida.proxima_etapa()
    fonte = request.form.get("fonte", "camera")
    if etapa not in QTD:
        return erro("Todas as etapas já foram registradas. Inicie uma nova mão.")

    resposta = {"etapa": etapa, "fonte": fonte, "imagem_b64": None, "detectadas": [], "tempos": {}}
    try:
        if fonte == "manual":
            candidatas = interpretar_texto(request.form.get("texto", ""))
            resposta["detectadas"] = [{"rotulo": c, "confianca": None} for c in candidatas]
        else:
            if not assistente.detector.disponivel:
                return erro(assistente.detector.erro or "YOLO indisponível.", 503)
            if fonte == "camera":
                imagem, t_captura = assistente.camera.capturar()
            elif fonte == "upload":
                import cv2
                arquivo = request.files.get("imagem")
                if not arquivo:
                    return erro("Nenhuma imagem enviada.")
                imagem = cv2.imdecode(np.frombuffer(arquivo.read(), np.uint8), cv2.IMREAD_COLOR)
                if imagem is None:
                    return erro("Não foi possível ler a imagem enviada.")
                t_captura = 0.0
            else:
                return erro(f"Fonte desconhecida: {fonte}")

            det = assistente.detectar(imagem, nome_arquivo=f"captura_{etapa}.jpg")
            candidatas = [c["rotulo"] for c in det["cartas"]]
            resposta.update({
                "detectadas": det["cartas"],
                "imagem_b64": det["imagem_b64"],
                "tempos": {"captura_s": round(t_captura, 3), "deteccao_s": det["tempo_total_s"],
                           "yolo_ms": det["tempos_ms"]},
            })

        aceitas, avisos = partida.registrar(
            etapa, candidatas,
            tempos={"captura_s": resposta["tempos"].get("captura_s", 0.0),
                    "deteccao_s": resposta["tempos"].get("deteccao_s", 0.0)},
        )
    except (ValueError, RuntimeError) as exc:
        return erro(str(exc))

    resposta.update({"aceitas": aceitas, "avisos": avisos, "estado": partida.para_dict()})
    return jsonify(resposta)


@app.post("/api/decidir")
def api_decidir():
    dados = request.get_json(silent=True) or {}
    estado = partida.para_dict()
    if not estado["posicao"]:
        return erro("Escolha a posição e inicie uma nova mão.")
    etapa = estado["ultima_etapa_completa"]
    if etapa is None:
        return erro("Registre as 2 cartas da mão antes de pedir uma decisão.")

    mao = estado["cartas"]["mao"]
    mesa = estado["cartas"]["flop"] + estado["cartas"]["turn"] + estado["cartas"]["river"]
    try:
        decisao = assistente.decidir(
            estado["posicao"], mao, mesa,
            forcar_llm=bool(dados.get("forcar_llm")),
            tempos_visao=partida.tempos.get(etapa, {}),
        )
    except RuntimeError as exc:
        return erro(str(exc), 503)
    except Exception as exc:
        return erro(f"Falha ao gerar a decisão: {exc}", 500)

    decisao["etapa"] = etapa
    decisao["etapa_nome"] = NOME[etapa]
    partida.adicionar_decisao({
        k: decisao[k] for k in ("fase", "acao", "caminho", "coerente", "tempos", "etapa_nome")
    })
    return jsonify(decisao)


@app.get("/api/benchmark.csv")
def api_benchmark():
    if not os.path.exists(config.BENCHMARK_CSV):
        return erro("Ainda não há decisões registradas.", 404)
    return send_file(config.BENCHMARK_CSV, as_attachment=True, download_name="benchmark.csv")


def _ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    print(f"\nServidor no ar: http://{_ip_local()}:{config.FLASK_PORT}  (Ctrl+C para encerrar)\n")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, threaded=True, debug=False, use_reloader=False)
