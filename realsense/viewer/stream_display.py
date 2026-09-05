"""
Modulo de despliegue de flujo de video comprimido para la interfaz visual remota (Viewer).
Decodifica los buffers JPEG recibidos y los presenta en pantalla con OpenCV.
"""

import cv2
import numpy as np


class StreamDisplay:
    def __init__(self, window_name="Intel RealSense D435 - Monitor RGB en Vivo"):
        self.window_name = window_name
        self._window_created = False

    def show_jpeg(self, jpeg_bytes: bytes) -> int:
        """
        Decodifica y muestra el fotograma JPEG en la ventana OpenCV.
        Retorna la tecla presionada (cv2.waitKey(1) & 0xFF).
        """
        if not jpeg_bytes:
            return cv2.waitKey(1) & 0xFF

        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return cv2.waitKey(1) & 0xFF

        if not self._window_created:
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
            self._window_created = True

        cv2.imshow(self.window_name, frame)
        return cv2.waitKey(1) & 0xFF

    def close(self):
        if self._window_created:
            cv2.destroyWindow(self.window_name)
            self._window_created = False
