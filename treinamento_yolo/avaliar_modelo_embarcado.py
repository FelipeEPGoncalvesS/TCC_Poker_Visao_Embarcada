import argparse
import json
from pathlib import Path

import numpy as np
from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--pesos", required=True)
parser.add_argument("--dados", required=True)
parser.add_argument("--saida", default="modelo_embarcado")
args = parser.parse_args()

modelo = YOLO(args.pesos, task="detect")
lote = 1 if args.pesos.rstrip("/").endswith("ncnn_model") else 16
pasta = Path(args.saida)
resultados = {}
for split in ["train", "val", "test"]:
    m = modelo.val(data=args.dados, split=split, imgsz=640, batch=lote,
                   project=str(pasta), name=split, exist_ok=True, verbose=False)
    cm = m.confusion_matrix.matrix
    nc = cm.shape[0] - 1
    classes = cm[:nc, :nc]
    resultados[split] = {
        "P": round(float(m.box.mp), 3),
        "R": round(float(m.box.mr), 3),
        "mAP50": round(float(m.box.map50), 3),
        "mAP50-95": round(float(m.box.map), 3),
        "cartas_trocadas": int(classes.sum() - np.trace(classes)),
        "cartas_anotadas": int(cm[:, :nc].sum()),
    }
    print(split, resultados[split])
pasta.mkdir(parents=True, exist_ok=True)
with open(pasta / "metricas_modelo_embarcado.json", "w") as f:
    json.dump(resultados, f, indent=2)
print("Salvo em", pasta / "metricas_modelo_embarcado.json")
