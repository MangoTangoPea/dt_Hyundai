"""
Orquestador principal del motor de grabacion (Backend) para la Jetson Orin Nano.
Coordina la adquisicion a 30 FPS, la cola de escritura SQLite/NVMe y el servidor IPC.
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path

# Anadir la ruta raiz del proyecto para importaciones relativas
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from recorder.camera_manager import CameraManager
from recorder.db3_recorder import DB3VideoRecorder
from recorder.mosaic_builder import MosaicBuilder
from ipc.ipc_manager import FramePipeWriter, CommandPipeReader


def load_config():
    cfg_path = PROJECT_ROOT / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_storage_dir(config):
    nvme_dir = config["storage"]["base_dir"]
    if os.path.exists(nvme_dir) and os.access(nvme_dir, os.W_OK):
        return Path(nvme_dir)

    fallback_dir = PROJECT_ROOT / config["storage"]["fallback_local_dir"]
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir


def main():
    print("=" * 65)
    print("  JETSON ORIN NANO - MULTI-CHANNEL RECORDER ENGINE (BACKEND)")
    print("=" * 65)

    config = load_config()
    storage_dir = resolve_storage_dir(config)
    print(f"[*] Directorio de almacenamiento activo: {storage_dir}")

    # Asegurar subcarpetas de clases
    for tag in config["storage"]["valid_tags"]:
        (storage_dir / tag).mkdir(parents=True, exist_ok=True)

    # 1. Inicializar Hardware de la Camara
    cam_cfg = config["camera"]
    camera = CameraManager(width=cam_cfg["width"], height=cam_cfg["height"], fps=cam_cfg["fps"])
    try:
        camera.start()
    except Exception as e:
        print(f"[ERROR] No se pudo inicializar la camara RealSense: {e}")
        print("[!] Verifica la conexion USB 3.0. Saliendo...")
        sys.exit(1)

    # 2. Inicializar DB3 Recorder
    db_recorder = DB3VideoRecorder(maxsize=config["storage"]["queue_maxsize"])

    # 3. Inicializar Previsualizador del Canal RGB
    prev_cfg = config["preview"]
    mosaic_builder = MosaicBuilder(
        width=prev_cfg.get("total_width", 640),
        height=prev_cfg.get("total_height", 480),
        jpeg_quality=prev_cfg.get("jpeg_quality", 50)
    )

    # 4. Inicializar Canales IPC
    ipc_cfg = config["ipc"]
    frame_writer = FramePipeWriter(pipe_path=ipc_cfg["pipe_frame"], socket_port=ipc_cfg["socket_port_frame"])
    cmd_reader = CommandPipeReader(pipe_path=ipc_cfg["pipe_cmd"], socket_port=ipc_cfg["socket_port_cmd"])

    frame_writer.open()
    cmd_reader.open()

    # Variables de estado
    is_recording = False
    current_temp_file = None
    current_timestamp_str = ""

    # Control de tasa de refresco para previsualizacion (10-15 FPS)
    target_preview_fps = prev_cfg.get("target_fps", 15)
    preview_interval = 1.0 / target_preview_fps
    last_preview_time = 0.0

    print("\n[OK] Engine de grabacion listo y a la espera de comandos (START / STOP / LABEL)...")

    try:
        while True:
            # A. Leer comandos IPC entrantes
            cmd = cmd_reader.read_command()
            if cmd:
                cmd_clean = cmd.strip()
                print(f"[IPC-CMD] Recibido: '{cmd_clean}'")

                if cmd_clean == "START" and not is_recording:
                    current_timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                    temp_name = f"{config['storage']['temp_prefix']}{current_timestamp_str}.db3"
                    current_temp_file = storage_dir / temp_name

                    metadata = {
                        "camera_name": camera.device_name,
                        "serial_number": camera.serial_number,
                        "width": camera.width,
                        "height": camera.height,
                        "fps": camera.fps,
                        "depth_scale": camera.depth_scale,
                        "start_time": current_timestamp_str
                    }

                    db_recorder.start(str(current_temp_file), metadata)
                    is_recording = True
                    print(f"[RECORDER] Grabando en: {current_temp_file.name}")

                elif cmd_clean == "STOP" and is_recording:
                    print("[RECORDER] Comando STOP recibido. Finalizando archivo...")
                    rec_count, drop_count = db_recorder.stop()
                    is_recording = False
                    print(f"[RECORDER] Grabacion finalizada. ({rec_count} frames guardados)")

                elif cmd_clean.startswith("LABEL:") and current_temp_file and current_temp_file.exists():
                    raw_tag = cmd_clean.split(":", 1)[1]
                    normalized_tag = raw_tag.upper().strip()

                    if normalized_tag and normalized_tag != "DISCARD":
                        target_dir = storage_dir / normalized_tag
                        target_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = target_dir / f"{normalized_tag}_{current_timestamp_str}.db3"
                        shutil.move(str(current_temp_file), str(dest_file))
                        print(f"[RECORDER] Archivo clasificado con exito: {dest_file}")
                    else:
                        print(f"[RECORDER] Etiqueta descartada o vacia ('{normalized_tag}').")
                        print(f"[RECORDER] Conservando archivo temporal seguro en: {current_temp_file}")

                    current_temp_file = None

                elif cmd_clean == "QUIT":
                    print("[RECORDER] Comando QUIT recibido. Cerrando...")
                    break

            # B. Adquisicion de fotogramas sincronizados a 30 FPS
            frames_dict, meta = camera.wait_for_frames()
            if frames_dict is None:
                continue

            # C. Si esta grabando, encolar en memoria RAM para escritura continua en disco
            if is_recording:
                # Convertir matrices numpy a bytes crudos contiguos
                color_raw = frames_dict["color"].tobytes()
                depth_raw = frames_dict["depth"].tobytes()
                ir1_raw = frames_dict["ir1"].tobytes()
                ir2_raw = frames_dict["ir2"].tobytes()

                db_recorder.enqueue_frame(
                    timestamp=meta["timestamp"],
                    color_bytes=color_raw,
                    depth_bytes=depth_raw,
                    ir1_bytes=ir1_raw,
                    ir2_bytes=ir2_raw
                )

            # D. Generacion y envio del Mosaico liviano JPEG (10-15 FPS para red)
            now = time.time()
            if now - last_preview_time >= preview_interval:
                jpeg_bytes = mosaic_builder.build_mosaic(
                    frame_dict=frames_dict,
                    is_recording=is_recording,
                    sensor_ts=meta["timestamp"]
                )
                if jpeg_bytes:
                    frame_writer.write_frame(jpeg_bytes)
                last_preview_time = now

    except KeyboardInterrupt:
        print("\n[*] Interrupcion por usuario.")
    finally:
        print("[*] Limpiando y cerrando recursos...")
        if is_recording:
            db_recorder.stop()
        camera.stop()
        frame_writer.close()
        cmd_reader.close()
        print("[*] Recorder backend finalizado.")


if __name__ == "__main__":
    main()
