"""
Lanzador maestro en Python para el sistema RealSense D435 en Jetson Orin Nano.
Permite ejecutar todo el sistema con un solo comando:
    python realsense/run.py

Funcionalidades:
1. Valida y crea automaticamente los directorios de almacenamiento en NVMe (o fallback local).
2. Valida y crea las tuberias nombradas (FIFOs) en /tmp (o modo socket si es necesario).
3. Lanza el motor de grabacion (recorder/main_recorder.py) en un subproceso independiente.
4. Lanza la interfaz grafica remota (viewer/main_viewer.py) conectada al Canal X11.
5. Al presionar 'Q', 'ESC' o Ctrl+C, cierra ambos procesos ordenadamente sin dejar recursos colgados.
"""

import os
import sys
import time
import json
import signal
import subprocess
from pathlib import Path

# Directorio raiz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_environment(config):
    print("=" * 65)
    print("  INICIALIZANDO ENTORNO REALSENSE D435 (TODO EN PYTHON)")
    print("=" * 65)

    # 1. Configurar directorios de grabacion
    storage_cfg = config.get("storage", {})
    base_dir = storage_cfg.get("base_dir", "/media/nvme/grabaciones")
    valid_tags = storage_cfg.get("valid_tags", ["C", "IA", "II", "IR"])

    # Determinar si NVMe esta disponible y accesible, o usar fallback
    if os.path.exists(base_dir) and os.access(base_dir, os.W_OK):
        target_dir = Path(base_dir)
        print(f"[OK] Utilizando disco SSD NVMe: {target_dir}")
    else:
        fallback = PROJECT_ROOT / storage_cfg.get("fallback_local_dir", "./grabaciones")
        target_dir = fallback
        print(f"[AVISO] Punto NVMe '{base_dir}' no disponible/escribible.")
        print(f"        Usando almacenamiento local: {target_dir.resolve()}")

    target_dir.mkdir(parents=True, exist_ok=True)
    for tag in valid_tags:
        (target_dir / tag).mkdir(parents=True, exist_ok=True)

    # 2. Configurar Named Pipes (FIFOs) si estamos en Linux
    if hasattr(os, "mkfifo"):
        ipc_cfg = config.get("ipc", {})
        pipe_frame = ipc_cfg.get("pipe_frame", "/tmp/pipe_frame")
        pipe_cmd = ipc_cfg.get("pipe_cmd", "/tmp/pipe_cmd")

        for p in (pipe_frame, pipe_cmd):
            if not os.path.exists(p):
                try:
                    os.mkfifo(p)
                    os.chmod(p, 0o666)
                    print(f"[OK] Tuberia creada: {p}")
                except OSError as e:
                    print(f"[!] Aviso con tuberia {p}: {e}")
            else:
                print(f"[OK] Tuberia existente: {p}")

    print("=" * 65)


def main():
    config = load_config()
    prepare_environment(config)

    python_executable = sys.executable

    recorder_script = PROJECT_ROOT / "recorder" / "main_recorder.py"
    viewer_script = PROJECT_ROOT / "viewer" / "main_viewer.py"

    print("[*] Iniciando Engine de Grabacion (Backend)...")
    # Iniciar recorder en segundo plano
    proc_recorder = subprocess.Popen(
        [python_executable, str(recorder_script)],
        cwd=str(PROJECT_ROOT)
    )

    # Breve pausa para asegurar que el backend monte las tuberias / sockets
    time.sleep(1.2)

    print("[*] Iniciando Visualizador y Controlador X11 (Frontend)...")
    print("Controles activos en la ventana de video:")
    print("  [ R ] : Grabar a 30 FPS en SSD NVMe")
    print("  [ E ] : Detener y Clasificar (C, IA, II, IR)")
    print("  [ Q ] : Salir del sistema")
    print("-" * 65)

    try:
        # Iniciar viewer en primer plano interactivo
        proc_viewer = subprocess.Popen(
            [python_executable, str(viewer_script)],
            cwd=str(PROJECT_ROOT)
        )

        # Esperar a que el usuario termine el visor (tecla Q o ESC)
        proc_viewer.wait()

    except KeyboardInterrupt:
        print("\n[*] Interrupcion detectada (Ctrl+C). Cerrando componentes...")
    finally:
        print("[*] Deteniendo subprocesos de manera ordenada...")

        # Cerrar viewer si sigue activo
        if 'proc_viewer' in locals() and proc_viewer.poll() is None:
            proc_viewer.terminate()
            try:
                proc_viewer.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc_viewer.kill()

        # Cerrar recorder
        if proc_recorder.poll() is None:
            proc_recorder.terminate()
            try:
                proc_recorder.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc_recorder.kill()

        print("[OK] Sistema finalizado correctamente.")


if __name__ == "__main__":
    main()
