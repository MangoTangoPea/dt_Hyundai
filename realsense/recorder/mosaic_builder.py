"""
Generador de previsualizacion en vivo para el canal RGB y codificador JPEG para X11/SSH.
Muestra una vista limpia y fluida de la camara RGB (con indicador de estado STANDBY / ● REC,
FPS y marca de tiempo) para que el operador decida cuando iniciar y detener la grabacion.
"""

import time
import cv2
import numpy as np


class MosaicBuilder:
    """
    Builder de previsualizacion en tiempo real.
    Optimizada para desplegar unicamente el canal RGB de forma liviana hacia el cliente X11.
    """

    def __init__(self, width=640, height=480, jpeg_quality=50):
        self.width = width
        self.height = height
        self.jpeg_quality = jpeg_quality
        self.last_time = time.time()
        self.fps = 0.0
        self.frame_count = 0

    def build_mosaic(self, frame_dict: dict, is_recording: bool, sensor_ts: float) -> bytes:
        """
        Toma el fotograma RGB original, lo escala a la resolucion de previsualizacion,
        anade los overlays informativos (Timestamp, FPS, estado STANDBY o REC) y lo codifica en JPEG.
        """
        # Calculo de FPS de previsualizacion
        self.frame_count += 1
        now = time.time()
        dt = now - self.last_time
        if dt >= 1.0:
            self.fps = self.frame_count / dt
            self.frame_count = 0
            self.last_time = now

        # Extraer fotograma de color (RGB/BGR) y redimensionar a la ventana de previsualizacion
        color_img = frame_dict.get("color")
        if color_img is None:
            return b""

        preview = cv2.resize(color_img, (self.width, self.height), interpolation=cv2.INTER_AREA)

        # Barra inferior translucida / oscura para telemetria
        overlay = preview.copy()
        cv2.rectangle(overlay, (0, self.height - 35), (self.width, self.height), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.6, preview, 0.4, 0, preview)

        # Informacion en barra inferior: Hora del sistema y FPS
        sys_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            preview,
            f"VISTA RGB | {sys_time_str} | FPS: {self.fps:.1f}",
            (12, self.height - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )

        # Indicador superior de estado: [STANDBY] o [● REC] parpadeante
        if is_recording:
            blink = int(now * 2.5) % 2 == 0
            if blink:
                cv2.circle(preview, (self.width - 80, 25), 8, (0, 0, 255), -1)
                cv2.putText(
                    preview,
                    "REC",
                    (self.width - 64, 31),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )
        else:
            cv2.putText(
                preview,
                "STANDBY",
                (self.width - 95, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

        # Codificacion a JPEG liviano (calidad 50%) para envio por tuberias/X11
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        success, enc_buf = cv2.imencode(".jpg", preview, encode_params)

        if not success:
            return b""
        return enc_buf.tobytes()
