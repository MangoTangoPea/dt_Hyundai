"""
Reproductor e Inspector Offline de grabaciones multicanal (.db3) para la PC Local.
Incorpora:
- Barra de avance temporal (Trackbar interactivo con OpenCV).
- Visualizacion en 4 cuadrantes o seleccion individual de canal.
- Medicion metrica de profundidad por mouse (D_(x,y) = matriz[y, x] * depth_scale).
- Controles: [Espacio] Play/Pausa, [A] / [D] o Flechas: Anterior/Siguiente frame.
"""

import sys
import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# Anadir la ruta raiz del proyecto para importaciones
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from inspector.db3_parser import DB3Parser


class OfflineInspector:
    def __init__(self, db_path: str):
        self.parser = DB3Parser(db_path)
        self.window_name = f"RealSense D435 Inspector - {os.path.basename(db_path)}"
        self.current_index = 0
        self.is_playing = False
        self.mouse_x = -1
        self.mouse_y = -1
        self.cached_frame = None
        self.cached_ts = 0.0

        # Dimensiones para el mosaico de inspeccion
        self.disp_w = 640
        self.disp_h = 360

        print(f"[*] Archivo cargado: {db_path}")
        print(f"[*] Total fotogramas: {self.parser.total_frames}")
        print(f"[*] Resolucion de canal: {self.parser.width}x{self.parser.height}")
        print(f"[*] Depth scale: {self.parser.depth_scale} m/unidad")

    def mouse_callback(self, event, x, y, flags, param):
        """Captura la posicion del cursor para calcular distancia exacta en el cuadrante de profundidad."""
        self.mouse_x = x
        self.mouse_y = y

    def run(self):
        if self.parser.total_frames == 0:
            print("[!] El archivo .db3 no contiene fotogramas.")
            return

        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        cv2.createTrackbar("Frame", self.window_name, 0, self.parser.total_frames - 1, self._on_trackbar)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        self._load_current_frame()

        while True:
            # Si esta en modo play, avanzar frame
            if self.is_playing:
                if self.current_index < self.parser.total_frames - 1:
                    self.current_index += 1
                    cv2.setTrackbarPos("Frame", self.window_name, self.current_index)
                    self._load_current_frame()
                else:
                    self.is_playing = False

            # Renderizar interfaz
            display_img = self._render_display()
            cv2.imshow(self.window_name, display_img)

            # Control de velocidad (si reproduce a 30 FPS, espera ~33ms, si esta en pausa espera tecla)
            wait_time = int(1000 / self.parser.fps) if self.is_playing else 30
            key = cv2.waitKey(wait_time) & 0xFF

            if key in (27, ord("q"), ord("Q")):
                break
            elif key == ord(" "):  # Barra espaciadora: Play / Pausa
                self.is_playing = not self.is_playing
            elif key in (ord("d"), ord("D"), 83):  # Siguiente frame
                if self.current_index < self.parser.total_frames - 1:
                    self.current_index += 1
                    cv2.setTrackbarPos("Frame", self.window_name, self.current_index)
                    self._load_current_frame()
            elif key in (ord("a"), ord("A"), 81):  # Frame anterior
                if self.current_index > 0:
                    self.current_index -= 1
                    cv2.setTrackbarPos("Frame", self.window_name, self.current_index)
                    self._load_current_frame()

        cv2.destroyAllWindows()

    def _on_trackbar(self, val):
        if val != self.current_index:
            self.current_index = val
            self._load_current_frame()

    def _load_current_frame(self):
        res = self.parser.get_frame(self.current_index)
        if res:
            self.cached_ts, self.cached_frame = res

    def _render_display(self):
        if self.cached_frame is None:
            blank = np.zeros((self.disp_h * 2, self.disp_w * 2, 3), dtype=np.uint8)
            cv2.putText(blank, "Sin datos de fotograma", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            return blank

        # 1. Cuadrante Color
        color_disp = cv2.resize(self.cached_frame["color"], (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA)

        # 2. Cuadrante Profundidad (Normalizado a colormap JET)
        depth_raw = self.cached_frame["depth"]
        # Normalizar para visualizacion dinamica
        depth_vis = cv2.normalize(depth_raw, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        depth_colored = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
        depth_disp = cv2.resize(depth_colored, (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA)

        # 3. Cuadrantes IR1 e IR2
        ir1_disp = cv2.cvtColor(cv2.resize(self.cached_frame["ir1"], (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
        ir2_disp = cv2.cvtColor(cv2.resize(self.cached_frame["ir2"], (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)

        # Calculo de distancia sobre el cuadrante de Profundidad (Top-Right: X in [disp_w, 2*disp_w], Y in [0, disp_h])
        depth_val_mm = None
        depth_val_m = None
        orig_x, orig_y = -1, -1

        if self.disp_w <= self.mouse_x < (self.disp_w * 2) and 0 <= self.mouse_y < self.disp_h:
            # Mapear coordenada de pantalla a resolucion original de profundidad (1280x720)
            local_x = self.mouse_x - self.disp_w
            local_y = self.mouse_y
            orig_x = int(local_x * (self.parser.width / self.disp_w))
            orig_y = int(local_y * (self.parser.height / self.disp_h))

            if 0 <= orig_x < self.parser.width and 0 <= orig_y < self.parser.height:
                raw_units = depth_raw[orig_y, orig_x]
                dist_meters = raw_units * self.parser.depth_scale
                depth_val_mm = int(dist_meters * 1000)
                depth_val_m = dist_meters

                # Dibujar mira sobre el display
                cv2.drawMarker(depth_disp, (local_x, local_y), (255, 255, 255), cv2.MARKER_CROSS, 14, 1)

        # Etiquetas de cuadrantes
        cv2.putText(color_disp, "1. RGB Color (1280x720)", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(depth_disp, "2. Profundidad Z16 (Cursor calcula distancia)", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(ir1_disp, "3. Infrarrojo 1 - Izquierdo", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(ir2_disp, "4. Infrarrojo 2 - Derecho", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Barra superior / inferior de datos
        top_row = np.hstack((color_disp, depth_disp))
        bottom_row = np.hstack((ir1_disp, ir2_disp))
        mosaico = np.vstack((top_row, bottom_row))

        # Superposicion de barra de telemetria
        info_bar = np.zeros((45, mosaico.shape[1], 3), dtype=np.uint8)
        status_play = "PLAYING" if self.is_playing else "PAUSED"
        ts_text = f"Frame: {self.current_index + 1}/{self.parser.total_frames} | Estado: {status_play} | [Espacio]: Play/Pausa | [A/D]: -/+1"
        cv2.putText(info_bar, ts_text, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

        if depth_val_m is not None:
            depth_text = f"Coord: ({orig_x}, {orig_y}) | Distancia: {depth_val_mm} mm ({depth_val_m:.3f} m)"
            cv2.putText(info_bar, depth_text, (mosaico.shape[1] - 480, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)

        final_view = np.vstack((mosaico, info_bar))
        return final_view


def select_file_via_dialog():
    """Abre un explorador de archivos si no se paso por argumento CLI."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Selecciona archivo de grabacion .db3",
        filetypes=[("Archivos de Grabacion RealSense", "*.db3"), ("Todos los archivos", "*.*")]
    )
    root.destroy()
    return file_path


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        print("[*] No se especifico archivo .db3 en linea de comandos. Abriendo selector...")
        db_path = select_file_via_dialog()

    if not db_path or not os.path.exists(db_path):
        print("[!] No se selecciono ningun archivo valido. Saliendo...")
        sys.exit(0)

    inspector = OfflineInspector(db_path)
    inspector.run()


if __name__ == "__main__":
    main()
