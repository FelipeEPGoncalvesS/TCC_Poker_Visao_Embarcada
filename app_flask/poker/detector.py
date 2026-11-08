import base64
import os
import time

import numpy as np

import config


class DetectorCartas:
    def __init__(self):
        self.disponivel = False
        self.erro = None
        self.model = None
        self.nomes = {}

        if not os.path.exists(config.YOLO_MODEL_PATH):
            self.erro = f"Modelo não encontrado em {config.YOLO_MODEL_PATH}."
            return
        try:
            from ultralytics import YOLO
        except Exception as exc:
            self.erro = f"Ultralytics não instalado ({exc})."
            return
        try:
            self.model = YOLO(config.YOLO_MODEL_PATH, task="detect")
            self.nomes = self.model.names
            vazio = np.zeros((config.YOLO_IMGSZ, config.YOLO_IMGSZ, 3), dtype=np.uint8)
            self.model.predict(source=vazio, imgsz=config.YOLO_IMGSZ, verbose=False)
            self.disponivel = True
        except Exception as exc:
            self.erro = f"Falha ao carregar o YOLO ({exc})."

    def detectar(self, imagem_bgr):
        if not self.disponivel:
            raise RuntimeError(self.erro or "Detector indisponível.")

        import cv2

        t0 = time.perf_counter()
        resultado = self.model.predict(
            source=imagem_bgr,
            imgsz=config.YOLO_IMGSZ,
            conf=config.YOLO_CONF,
            iou=config.YOLO_IOU,
            verbose=False,
        )[0]

        melhores = {}
        for box in resultado.boxes:
            rotulo = self.nomes[int(box.cls[0])]
            confianca = float(box.conf[0])
            if rotulo not in melhores or confianca > melhores[rotulo]["confianca"]:
                melhores[rotulo] = {"rotulo": rotulo, "confianca": round(confianca, 3)}
        cartas = sorted(melhores.values(), key=lambda c: c["confianca"], reverse=True)
        tempo_total = time.perf_counter() - t0

        anotada = resultado.plot()
        ok, buffer = cv2.imencode(".jpg", anotada, [cv2.IMWRITE_JPEG_QUALITY, 80])
        imagem_b64 = base64.b64encode(buffer).decode("ascii") if ok else None

        return {
            "cartas": cartas,
            "imagem_b64": imagem_b64,
            "tempos_ms": {k: round(v, 1) for k, v in resultado.speed.items()},
            "tempo_total_s": round(tempo_total, 3),
        }
