import json
import os
import shutil
import sqlite3
from datetime import datetime

import numpy as np


class DB3Recorder:
    """Stores synchronized RealSense channels in a SQLite .db3 file."""

    CATEGORIES = ("IA", "II", "C", "IR")
    FALLBACK_CATEGORY = "UNCLASSIFIED"

    def __init__(self, directory):
        self.directory = directory
        self.connection = None
        self.filename = None
        os.makedirs(directory, exist_ok=True)

    def start(self, camera):
        if self.connection is not None:
            print("Already recording.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(
            self.directory,
            f"video_{timestamp}.db3",
        )
        self.connection = sqlite3.connect(self.filename)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE recording_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms REAL NOT NULL,
                frame_number INTEGER,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE channels (
                frame_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                data BLOB NOT NULL,
                dtype TEXT NOT NULL,
                shape_json TEXT NOT NULL,
                FOREIGN KEY(frame_id) REFERENCES frames(id)
            );
            CREATE INDEX channels_frame_id ON channels(frame_id);
            """
        )
        self.connection.executemany(
            "INSERT INTO recording_metadata(key, value) VALUES (?, ?)",
            [
                ("format", "dt_hyundai_realsense_db3"),
                ("camera", "Intel RealSense D435"),
                ("color_size", json.dumps(camera.color_size)),
                ("depth_size", json.dumps(camera.depth_size)),
                ("fps", str(camera.fps)),
                ("depth_scale", str(camera.depth_scale)),
            ],
        )
        self.connection.commit()
        print(f"Recording started: {self.filename}")

    def write(self, capture):
        if self.connection is None:
            return

        cursor = self.connection.execute(
            """
            INSERT INTO frames(timestamp_ms, frame_number, metadata_json)
            VALUES (?, ?, ?)
            """,
            (
                capture.timestamp_ms,
                capture.metadata.get("frame_number"),
                json.dumps(capture.metadata),
            ),
        )
        frame_id = cursor.lastrowid
        channels = {
            "color": capture.color,
            "depth": capture.depth,
            "infrared_left": capture.infrared_left,
            "infrared_right": capture.infrared_right,
        }
        self.connection.executemany(
            """
            INSERT INTO channels(frame_id, name, data, dtype, shape_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    frame_id,
                    name,
                    sqlite3.Binary(np.ascontiguousarray(array).tobytes()),
                    str(array.dtype),
                    json.dumps(array.shape),
                )
                for name, array in channels.items()
            ],
        )
        self.connection.commit()

    def stop(self, category=None):
        if self.connection is None:
            return

        source_filename = self.filename
        self.connection.commit()
        self.connection.close()
        self.connection = None
        self.filename = None

        if category not in self.CATEGORIES:
            category = self.FALLBACK_CATEGORY

        category_directory = os.path.join(
            self.directory,
            category,
        )
        os.makedirs(category_directory, exist_ok=True)
        destination_filename = os.path.join(
            category_directory,
            os.path.basename(source_filename),
        )
        shutil.move(source_filename, destination_filename)

        print(f"Recording stopped: {destination_filename}")

    def is_recording(self):
        return self.connection is not None