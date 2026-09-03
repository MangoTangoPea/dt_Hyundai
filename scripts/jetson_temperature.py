#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path

# ============================================================

# CONFIGURACIÓN

# ============================================================

# Directorio donde se guardarán los archivos diarios

LOG_DIR = Path("/home/gigseea/temperature_logs")

# Sensores que queremos registrar, en este orden

SENSORS = [
"cpu-thermal"
]

# ============================================================

# FUNCIONES

# ============================================================

def read_file(path):
    """
    Lee un archivo de texto de forma segura.

    Devuelve el contenido como string o None si no se puede leer.
    """

    try:
        with open(path, "r") as file:
            data = file.read()

        if data is None:
            return None

        return data.strip()

    except (OSError, IOError, ValueError, TypeError):
        return None


def read_temperature(zone):
    """
    Lee la temperatura de una zona térmica.

    ```
    Devuelve la temperatura en grados Celsius.
    Si el sensor no está disponible o no se puede leer,
    devuelve None.
    """

    temp_file = zone / "temp"

    raw_temperature = read_file(temp_file)

    if raw_temperature is None or raw_temperature == "":
        return None

    try:
        temperature = float(raw_temperature)

        # En Linux / sysfs normalmente la temperatura está
        # expresada en milésimas de grado Celsius.
        if temperature > 1000:
            temperature = temperature / 1000.0

        return temperature

    except (ValueError, TypeError):
        return None


def get_all_temperatures():
    """
    Busca todas las zonas térmicas disponibles y devuelve
    un diccionario con las temperaturas.
    """


    temperatures = {}

    thermal_path = Path("/sys/class/thermal")

    for zone in thermal_path.glob("thermal_zone*"):

        type_file = zone / "type"

        sensor_name = read_file(type_file)

        # Si no se pudo leer el nombre del sensor, continuar
        if sensor_name is None:
            continue

        # Solo registrar los sensores definidos en SENSORS
        if sensor_name in SENSORS:

            temperature = read_temperature(zone)

            temperatures[sensor_name] = temperature

    return temperatures


# ============================================================

# PROGRAMA PRINCIPAL

# ============================================================

def main():

    # Fecha y hora actual
    now = datetime.now()

    # Crear el directorio si no existe
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Crear un archivo nuevo cada día
    filename = LOG_DIR / f"temperatures_{now:%Y-%m-%d}.txt"

    # Obtener todas las temperaturas
    temperatures = get_all_temperatures()

    # Verificar si el archivo es nuevo
    new_file = not filename.exists()

    # Abrir archivo en modo append
    with filename.open("a", encoding="utf-8") as file:

        # Escribir cabecera solamente si es un archivo nuevo
        if new_file:

            header = [
                "date",
                "time",
                *SENSORS
            ]

            file.write(",".join(header) + "\n")

        # Crear la fila con fecha y hora
        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S")
        ]

        # Añadir cada temperatura
        for sensor in SENSORS:

            temperature = temperatures.get(sensor)

            if temperature is None:
                row.append("NA")
            else:
                row.append(f"{temperature:.3f}")

        # Guardar la fila
        file.write(",".join(row) + "\n")


if __name__ == "__main__":
    main()
