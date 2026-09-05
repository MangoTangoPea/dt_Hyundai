"""
Modulo deserializador para bases de datos SQLite (.db3).
Extrae matrices completas a 1280x720 sin perdida de precision:
- Color: (720, 1280, 3) uint8 BGR
- Depth: (720, 1280) uint16 Z16 nativo
- Infrarrojo 1: (720, 1280) uint8 Y8
- Infrarrojo 2: (720, 1280) uint8 Y8
Permite acceso indexado O(1) a cualquier fotograma para el slider de tiempo.
"""

import os
import sqlite3
import numpy as np
from typing import Dict, Any, Tuple, Optional


class DB3Parser:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Archivo .db3 no encontrado: {self.db_path}")

        self.metadata = {}
        self.total_frames = 0
        self.width = 1280
        self.height = 720
        self.fps = 30
        self.depth_scale = 0.001
        self._frame_ids = []

        self._load_metadata_and_indices()

    def _load_metadata_and_indices(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Cargar tabla metadata
        try:
            cursor.execute("SELECT key, value FROM metadata;")
            for k, v in cursor.fetchall():
                self.metadata[k] = v
        except sqlite3.OperationalError:
            pass

        self.width = int(self.metadata.get("width", 1280))
        self.height = int(self.metadata.get("height", 720))
        self.fps = int(self.metadata.get("fps", 30))
        self.depth_scale = float(self.metadata.get("depth_scale", 0.001))

        # Obtener lista de frame_ids ordenados para acceso rapido
        cursor.execute("SELECT frame_id FROM frames ORDER BY frame_id ASC;")
        rows = cursor.fetchall()
        self._frame_ids = [r[0] for r in rows]
        self.total_frames = len(self._frame_ids)

        conn.close()

    def get_frame(self, index: int) -> Optional[Tuple[float, Dict[str, np.ndarray]]]:
        """
        Retorna: (timestamp, dict_de_matrices_numpy) para el indice solicitado (0 <= index < total_frames).
        """
        if index < 0 or index >= self.total_frames:
            return None

        target_id = self._frame_ids[index]
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp_ns, color_blob, depth_blob, ir1_blob, ir2_blob
            FROM frames WHERE frame_id = ?;
        """, (target_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        timestamp, color_blob, depth_blob, ir1_blob, ir2_blob = row

        # Deserializacion exacta a arrays de numpy
        color_arr = np.frombuffer(color_blob, dtype=np.uint8).reshape((self.height, self.width, 3))
        depth_arr = np.frombuffer(depth_blob, dtype=np.uint16).reshape((self.height, self.width))
        ir1_arr = np.frombuffer(ir1_blob, dtype=np.uint8).reshape((self.height, self.width))
        ir2_arr = np.frombuffer(ir2_blob, dtype=np.uint8).reshape((self.height, self.width))

        frames = {
            "color": color_arr,
            "depth": depth_arr,
            "ir1": ir1_arr,
            "ir2": ir2_arr
        }

        return timestamp, frames
