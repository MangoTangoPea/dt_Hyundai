"""
Modulo de gestion del hardware de la camara Intel RealSense D435.
Configura 4 canales sincronizados a 1280x720 @ 30 FPS mediante hardware timestamps.
"""

import sys
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    rs = None


class CameraManager:
    def __init__(self, width=1280, height=720, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.pipeline = None
        self.config = None
        self.profile = None
        self.depth_scale = 0.001  # Valor por defecto (1 mm por unidad)
        self.device_name = "Simulated / None"
        self.serial_number = "Unknown"
        self.colorizer = None

    def start(self):
        """Inicia el pipeline con los 4 flujos requeridos."""
        if rs is None:
            raise RuntimeError("pyrealsense2 no esta disponible en el entorno actual.")

        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # 1. Profundidad nativa Z16
        self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        # 2. Color RGB BGR8
        self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        # 3. Infrarrojo 1 (Izquierdo) Y8
        self.config.enable_stream(rs.stream.infrared, 1, self.width, self.height, rs.format.y8, self.fps)
        # 4. Infrarrojo 2 (Derecho) Y8
        self.config.enable_stream(rs.stream.infrared, 2, self.width, self.height, rs.format.y8, self.fps)

        print(f"[CameraManager] Iniciando streaming de 4 canales a {self.width}x{self.height} @ {self.fps} FPS...")
        self.profile = self.pipeline.start(self.config)
        device = self.profile.get_device()
        self.device_name = device.get_info(rs.camera_info.name)
        self.serial_number = device.get_info(rs.camera_info.serial_number)

        # Obtener la escala metrica del sensor de profundidad
        depth_sensor = device.first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()

        self.colorizer = rs.colorizer()

        print(f"[CameraManager] Conectado a: {self.device_name} (S/N: {self.serial_number})")
        print(f"[CameraManager] Escala de profundidad (depth_scale): {self.depth_scale} m/unidad")

    def wait_for_frames(self):
        """
        Espera por un conjunto de fotogramas sincronizados por hardware.
        Retorna: (dict_con_frames_numpy, dict_con_metadatos) o (None, None)
        """
        if self.pipeline is None:
            return None, None

        frames = self.pipeline.wait_for_frames()

        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        ir1_frame = frames.get_infrared_frame(1)
        ir2_frame = frames.get_infrared_frame(2)

        if not color_frame or not depth_frame or not ir1_frame or not ir2_frame:
            return None, None

        # Timestamp de hardware del sensor
        sensor_ts = depth_frame.get_timestamp()
        ts_domain = depth_frame.get_frame_timestamp_domain()

        # Matrices brutas en numpy
        color_data = np.asanyarray(color_frame.get_data())         # uint8 (720, 1280, 3)
        depth_data = np.asanyarray(depth_frame.get_data())         # uint16 (720, 1280)
        ir1_data = np.asanyarray(ir1_frame.get_data())             # uint8 (720, 1280)
        ir2_data = np.asanyarray(ir2_frame.get_data())             # uint8 (720, 1280)

        # Mapa de color para previsualizacion
        depth_colored = np.asanyarray(self.colorizer.colorize(depth_frame).get_data())

        frame_dict = {
            "color": color_data,
            "depth": depth_data,
            "depth_colored": depth_colored,
            "ir1": ir1_data,
            "ir2": ir2_data
        }

        meta = {
            "timestamp": sensor_ts,
            "timestamp_domain": str(ts_domain),
            "depth_scale": self.depth_scale
        }

        return frame_dict, meta

    def stop(self):
        if self.pipeline:
            print("[CameraManager] Deteniendo pipeline...")
            self.pipeline.stop()
            self.pipeline = None
