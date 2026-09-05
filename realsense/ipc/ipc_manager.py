"""
Gestor de comunicacion interproceso (IPC) para Linux FIFOs (Named Pipes)
con fallback transparente a sockets TCP en plataformas de desarrollo / Windows.
Incorpora protocolo de longitud de tramas (4 bytes big-endian) para streams binarios.
"""

import os
import sys
import struct
import socket
import select
import time
from pathlib import Path


class FramePipeWriter:
    """Escritor de fotogramas JPEG comprimidos hacia el pipe/socket."""

    def __init__(self, pipe_path="/tmp/pipe_frame", socket_port=5555):
        self.pipe_path = pipe_path
        self.socket_port = socket_port
        self.is_posix = hasattr(os, "mkfifo")
        self.fifo_fd = None
        self.server_sock = None
        self.client_sock = None

    def open(self):
        if self.is_posix:
            if not os.path.exists(self.pipe_path):
                try:
                    os.mkfifo(self.pipe_path)
                except OSError:
                    pass
            # Abrir en modo no bloqueante o bloqueante segun conexion
            print(f"[IPC-Writer] Esperando conexion de lectura en FIFO: {self.pipe_path}...")
            self.fifo_fd = os.open(self.pipe_path, os.O_WRONLY)
            print("[IPC-Writer] Lector conectado a FIFO de frames.")
        else:
            # Fallback Socket TCP para desarrollo local (ej. Windows)
            print(f"[IPC-Writer] Modo Socket en puerto {self.socket_port}...")
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(("127.0.0.1", self.socket_port))
            self.server_sock.listen(1)
            self.server_sock.settimeout(1.0)

    def write_frame(self, jpeg_bytes: bytes) -> bool:
        if not jpeg_bytes:
            return False

        payload = struct.pack(">I", len(jpeg_bytes)) + jpeg_bytes

        if self.is_posix and self.fifo_fd is not None:
            try:
                os.write(self.fifo_fd, payload)
                return True
            except (BrokenPipeError, OSError):
                return False
        else:
            if self.client_sock is None and self.server_sock is not None:
                try:
                    self.client_sock, _ = self.server_sock.accept()
                except socket.timeout:
                    return False
                except Exception:
                    return False

            if self.client_sock is not None:
                try:
                    self.client_sock.sendall(payload)
                    return True
                except (BrokenPipeError, ConnectionResetError, OSError):
                    self.client_sock.close()
                    self.client_sock = None
                    return False
        return False

    def close(self):
        if self.fifo_fd is not None:
            try:
                os.close(self.fifo_fd)
            except OSError:
                pass
            self.fifo_fd = None

        if self.client_sock:
            self.client_sock.close()
            self.client_sock = None
        if self.server_sock:
            self.server_sock.close()
            self.server_sock = None


class FramePipeReader:
    """Lector de fotogramas JPEG comprimidos desde el pipe/socket."""

    def __init__(self, pipe_path="/tmp/pipe_frame", socket_port=5555):
        self.pipe_path = pipe_path
        self.socket_port = socket_port
        self.is_posix = hasattr(os, "mkfifo")
        self.fifo_fd = None
        self.sock = None

    def open(self):
        if self.is_posix:
            if not os.path.exists(self.pipe_path):
                try:
                    os.mkfifo(self.pipe_path)
                except OSError:
                    pass
            print(f"[IPC-Reader] Conectando a FIFO de frames: {self.pipe_path}...")
            self.fifo_fd = os.open(self.pipe_path, os.O_RDONLY)
            print("[IPC-Reader] Conectado a FIFO de frames.")
        else:
            print(f"[IPC-Reader] Conectando a socket 127.0.0.1:{self.socket_port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            while True:
                try:
                    self.sock.connect(("127.0.0.1", self.socket_port))
                    print("[IPC-Reader] Conectado a servidor de frames.")
                    break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.5)

    def _read_exact(self, n_bytes: int) -> bytes:
        data = bytearray()
        while len(data) < n_bytes:
            if self.is_posix and self.fifo_fd is not None:
                packet = os.read(self.fifo_fd, n_bytes - len(data))
            elif self.sock is not None:
                packet = self.sock.recv(n_bytes - len(data))
            else:
                return b""

            if not packet:
                return b""
            data.extend(packet)
        return bytes(data)

    def read_frame(self) -> bytes:
        header = self._read_exact(4)
        if len(header) < 4:
            return b""
        frame_len = struct.unpack(">I", header)[0]
        return self._read_exact(frame_len)

    def close(self):
        if self.fifo_fd is not None:
            try:
                os.close(self.fifo_fd)
            except OSError:
                pass
            self.fifo_fd = None
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class CommandPipeWriter:
    """Escritor de comandos de texto (START, STOP, LABEL:...) hacia el backend."""

    def __init__(self, pipe_path="/tmp/pipe_cmd", socket_port=5556):
        self.pipe_path = pipe_path
        self.socket_port = socket_port
        self.is_posix = hasattr(os, "mkfifo")
        self.fifo_fd = None
        self.sock = None

    def open(self):
        if self.is_posix:
            if not os.path.exists(self.pipe_path):
                try:
                    os.mkfifo(self.pipe_path)
                except OSError:
                    pass
            self.fifo_fd = os.open(self.pipe_path, os.O_WRONLY)
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            while True:
                try:
                    self.sock.connect(("127.0.0.1", self.socket_port))
                    break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.5)

    def send_command(self, cmd: str) -> bool:
        data = (cmd.strip() + "\n").encode("utf-8")
        try:
            if self.is_posix and self.fifo_fd is not None:
                os.write(self.fifo_fd, data)
                return True
            elif self.sock is not None:
                self.sock.sendall(data)
                return True
        except (BrokenPipeError, OSError):
            return False
        return False

    def close(self):
        if self.fifo_fd is not None:
            try:
                os.close(self.fifo_fd)
            except OSError:
                pass
            self.fifo_fd = None
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class CommandPipeReader:
    """Lector no bloqueante de comandos de texto provenientes del viewer."""

    def __init__(self, pipe_path="/tmp/pipe_cmd", socket_port=5556):
        self.pipe_path = pipe_path
        self.socket_port = socket_port
        self.is_posix = hasattr(os, "mkfifo")
        self.fifo_fd = None
        self.server_sock = None
        self.client_sock = None
        self._buffer = ""

    def open(self):
        if self.is_posix:
            if not os.path.exists(self.pipe_path):
                try:
                    os.mkfifo(self.pipe_path)
                except OSError:
                    pass
            self.fifo_fd = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        else:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(("127.0.0.1", self.socket_port))
            self.server_sock.listen(1)
            self.server_sock.setblocking(False)

    def read_command(self) -> str:
        """Devuelve el proximo comando pendiente o None si no hay ninguno."""
        if self.is_posix and self.fifo_fd is not None:
            try:
                chunk = os.read(self.fifo_fd, 1024).decode("utf-8")
                if chunk:
                    self._buffer += chunk
            except (BlockingIOError, OSError):
                pass
        elif not self.is_posix:
            if self.client_sock is None and self.server_sock is not None:
                try:
                    self.client_sock, _ = self.server_sock.accept()
                    self.client_sock.setblocking(False)
                except (BlockingIOError, socket.error):
                    pass

            if self.client_sock is not None:
                try:
                    chunk = self.client_sock.recv(1024).decode("utf-8")
                    if chunk:
                        self._buffer += chunk
                except (BlockingIOError, socket.error):
                    pass

        if "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            return line.strip()

        return None

    def close(self):
        if self.fifo_fd is not None:
            try:
                os.close(self.fifo_fd)
            except OSError:
                pass
            self.fifo_fd = None
        if self.client_sock:
            self.client_sock.close()
            self.client_sock = None
        if self.server_sock:
            self.server_sock.close()
            self.server_sock = None
