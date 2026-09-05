"""
Frontend y Control Remoto para ejecucion bajo sesion SSH con X11 Forwarding.
Recibe el flujo JPEG comprimido desde pipe_frame, gestiona las teclas de operacion:
  'R' / 'r' -> START (Iniciar grabacion 30 FPS en NVMe)
  'E' / 'e' -> STOP  (Detener grabacion e invocar dialogo modal de clasificacion)
  'Q' / 'q' / ESC -> Cerrar aplicacion
"""

import sys
import json
import time
from pathlib import Path

# Anadir la ruta raiz del proyecto para importaciones
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from viewer.stream_display import StreamDisplay
from viewer.tag_dialog import TagDialog
from ipc.ipc_manager import FramePipeReader, CommandPipeWriter


def load_config():
    cfg_path = PROJECT_ROOT / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 65)
    print("  INTEL REALSENSE D435 - REMOTE VIEWER & CONTROLLER (X11)")
    print("=" * 65)
    print("Controles del operador:")
    print("  [ R ] : Iniciar grabacion a 30 FPS en disco NVMe")
    print("  [ E ] : Detener grabacion y clasificar (C, IA, II, IR)")
    print("  [ Q ] o [ ESC ] : Salir del visualizador")
    print("=" * 65)

    config = load_config()
    ipc_cfg = config["ipc"]

    # 1. Inicializar Canales IPC
    frame_reader = FramePipeReader(pipe_path=ipc_cfg["pipe_frame"], socket_port=ipc_cfg["socket_port_frame"])
    cmd_writer = CommandPipeWriter(pipe_path=ipc_cfg["pipe_cmd"], socket_port=ipc_cfg["socket_port_cmd"])

    frame_reader.open()
    cmd_writer.open()

    # 2. Inicializar Ventana de Despliegue
    display = StreamDisplay()
    dialog = TagDialog(valid_tags=config["storage"]["valid_tags"])

    is_recording_local = False

    try:
        while True:
            # Leer fotograma JPEG comprimido
            jpeg_bytes = frame_reader.read_frame()
            if not jpeg_bytes:
                time.sleep(0.01)
                continue

            # Mostrar en pantalla y capturar tecla
            key = display.show_jpeg(jpeg_bytes)

            if key in (ord("r"), ord("R")):
                if not is_recording_local:
                    print("\n[*] Solicitando INICIO de grabacion (START)...")
                    cmd_writer.send_command("START")
                    is_recording_local = True

            elif key in (ord("e"), ord("E")):
                if is_recording_local:
                    print("\n[*] Solicitando PARADA de grabacion (STOP)...")
                    cmd_writer.send_command("STOP")
                    is_recording_local = False

                    # Abrir cuadro de dialogo modal
                    print("[*] Abriendo ventana de clasificacion...")
                    chosen_tag = dialog.show()

                    if chosen_tag:
                        print(f"[*] Etiqueta asignada: '{chosen_tag}'. Enviando al recorder...")
                        cmd_writer.send_command(f"LABEL:{chosen_tag}")
                    else:
                        print("[*] Clasificacion cancelada o descartada. Conservando archivo temporal.")
                        cmd_writer.send_command("LABEL:DISCARD")

            elif key in (ord("q"), ord("Q"), 27):
                print("\n[*] Cerrando viewer...")
                cmd_writer.send_command("QUIT")
                break

    except KeyboardInterrupt:
        print("\n[*] Interrupcion por usuario.")
    finally:
        display.close()
        frame_reader.close()
        cmd_writer.close()
        print("[*] Viewer finalizado.")


if __name__ == "__main__":
    main()
