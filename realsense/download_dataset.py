"""
Script en Python para sincronizar y descargar datasets grabados en la Jetson
hacia la maquina local cliente sin necesidad de scripts de Bash (.sh).
Permite invocar rsync o scp nativamente desde Python con barra de progreso.

Uso:
    python realsense/download_dataset.py --ip 192.168.1.100 --user jetson
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Descargar datasets .db3 desde Jetson a PC Local.")
    parser.add_argument("--ip", default="192.168.1.100", help="Direccion IP de la Jetson")
    parser.add_argument("--user", default="jetson", help="Usuario SSH en la Jetson")
    parser.add_argument("--remote-dir", default="/media/nvme/grabaciones/", help="Ruta remota de las grabaciones")
    parser.add_argument("--dest", default="./dataset_local", help="Directorio destino local")
    args = parser.parse_args()

    dest_path = Path(args.dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(f" SINCRONIZANDO DATASETS DESDE JETSON ({args.user}@{args.ip})")
    print(f" Destino local: {dest_path.resolve()}")
    print("=" * 65)

    # Intentar con rsync si esta disponible
    rsync_cmd = [
        "rsync", "-avzP",
        "--include=*/", "--include=*.db3", "--exclude=*",
        f"{args.user}@{args.ip}:{args.remote_dir}",
        str(dest_path) + "/"
    ]

    try:
        res = subprocess.run(rsync_cmd)
        if res.returncode == 0:
            print("\n[OK] Sincronizacion completada con exito.")
            return
    except FileNotFoundError:
        print("[!] 'rsync' no esta en el PATH del sistema. Intentando con 'scp'...")

    # Fallback con SCP
    scp_cmd = [
        "scp", "-r",
        f"{args.user}@{args.ip}:{args.remote_dir}",
        str(dest_path)
    ]
    subprocess.run(scp_cmd)
    print("\n[OK] Transferencia finalizada.")

if __name__ == "__main__":
    main()
