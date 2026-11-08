import threading
import time

import config


class Camera:
    def __init__(self):
        self.disponivel = False
        self.erro = None
        self._cam = None
        self._lock = threading.Lock()

        if not config.USAR_CAMERA:
            self.erro = "Câmera desativada (USAR_CAMERA=0)."
            return
        try:
            from picamera2 import Picamera2
        except Exception as exc:
            self.erro = f"Picamera2 não disponível neste ambiente ({exc})."
            return
        try:
            self._cam = Picamera2()
            cfg = self._cam.create_still_configuration(
                main={"size": config.CAMERA_SIZE, "format": "RGB888"}
            )
            self._cam.configure(cfg)
            self._cam.start()
            time.sleep(config.CAMERA_WARMUP_S)
            self.disponivel = True
        except Exception as exc:
            self.erro = (
                f"Falha ao abrir a câmera ({exc}). Se o Jupyter estiver com a câmera "
                "aberta, reinicie o kernel do notebook antes de iniciar o Flask."
            )
            self.fechar()

    def capturar(self):
        if not self.disponivel:
            raise RuntimeError(self.erro or "Câmera indisponível.")
        with self._lock:
            t0 = time.perf_counter()
            frame = self._cam.capture_array("main")
            return frame, time.perf_counter() - t0

    def fechar(self):
        if self._cam is not None:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
            self._cam = None
        self.disponivel = False
