"""
Modulo de grabacion en base de datos SQLite (.db3) optimizado para almacenamiento NVMe.
Implementa una cola FIFO en memoria RAM (queue.Queue) en un hilo asincrono secundario
para absorber latencias de I/O y asegurar 30 FPS continuos sin perdida de fotogramas.
"""

import os
import time
import queue
import sqlite3
import threading
from typing import Dict, Any


class DB3VideoRecorder:
    def __init__(self, maxsize=150):
        self.maxsize = maxsize
        self.frame_queue = queue.Queue(maxsize=maxsize)
        self.writer_thread = None
        self.is_recording = False
        self.stop_event = threading.Event()
        self.db_path = None
        self.total_recorded = 0
        self.total_dropped = 0

    def start(self, db_path: str, metadata: Dict[str, Any]):
        """Inicializa la base de datos SQLite (.db3) y arranca el hilo de escritura."""
        self.db_path = db_path
        self.stop_event.clear()
        self.total_recorded = 0
        self.total_dropped = 0
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        # Asegurar directorio
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # Iniciar esquema en el archivo .db3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = OFF;")
        cursor.execute("PRAGMA cache_size = -64000;")  # 64MB de cache

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS frames (
                frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ns REAL,
                color_blob BLOB,
                depth_blob BLOB,
                ir1_blob BLOB,
                ir2_blob BLOB
            );
        """)

        for k, v in metadata.items():
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", (str(k), str(v)))

        conn.commit()
        conn.close()

        self.is_recording = True
        self.writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
        self.writer_thread.start()
        print(f"[DB3Recorder] Grabacion iniciada en: {self.db_path}")

    def enqueue_frame(self, timestamp: float, color_bytes: bytes, depth_bytes: bytes, ir1_bytes: bytes, ir2_bytes: bytes):
        """Inserta un paquete de fotogramas en la cola FIFO. Si la cola esta llena, incrementa dropped_frames."""
        if not self.is_recording:
            return

        item = (timestamp, color_bytes, depth_bytes, ir1_bytes, ir2_bytes)
        try:
            self.frame_queue.put_nowait(item)
        except queue.Full:
            self.total_dropped += 1
            if self.total_dropped % 30 == 0:
                print(f"[DB3Recorder-WARNING] Cola RAM llena! Total fotogramas descartados: {self.total_dropped}")

    def _writer_worker(self):
        """Worker en hilo independiente con inserciones por transaccion para maximo rendimiento."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = OFF;")
        cursor.execute("PRAGMA cache_size = -64000;")

        batch = []
        BATCH_SIZE = 15  # Commit cada ~0.5 segundos

        while not self.stop_event.is_set() or not self.frame_queue.empty():
            try:
                item = self.frame_queue.get(timeout=0.05)
                batch.append(item)
                self.frame_queue.task_done()
            except queue.Empty:
                pass

            if len(batch) >= BATCH_SIZE or (self.stop_event.is_set() and batch):
                cursor.executemany("""
                    INSERT INTO frames (timestamp_ns, color_blob, depth_blob, ir1_blob, ir2_blob)
                    VALUES (?, ?, ?, ?, ?);
                """, batch)
                conn.commit()
                self.total_recorded += len(batch)
                batch.clear()

        # Insertar cualquier remanente final
        if batch:
            cursor.executemany("""
                INSERT INTO frames (timestamp_ns, color_blob, depth_blob, ir1_blob, ir2_blob)
                VALUES (?, ?, ?, ?, ?);
            """, batch)
            conn.commit()
            self.total_recorded += len(batch)
            batch.clear()

        # Guardar resumen final en metadata
        cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('total_frames', ?);", (str(self.total_recorded),))
        cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('dropped_frames', ?);", (str(self.total_dropped),))
        conn.commit()
        conn.close()
        print(f"[DB3Recorder] Escritura completada: {self.total_recorded} frames guardados | {self.total_dropped} descartados.")

    def stop(self):
        """Detiene la grabacion y espera a que se vacie la cola en disco."""
        if not self.is_recording:
            return
        print("[DB3Recorder] Deteniendo grabacion y vaciando buffer a disco...")
        self.is_recording = False
        self.stop_event.set()
        if self.writer_thread:
            self.writer_thread.join(timeout=10.0)
            self.writer_thread = None
        return self.total_recorded, self.total_dropped
