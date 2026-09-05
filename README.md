# Sistema de Captura, Clasificación e Inspección Multicanal (RealSense D435 + Jetson Orin Nano)

Sistema desacoplado de adquisición de alto ancho de banda, almacenamiento optimizado en SSD NVMe (`.db3` SQLite) e inspección offline con telemetría métrica en tiempo real para una cámara **Intel RealSense D435** conectada a una **NVIDIA Jetson Orin Nano**. Todo el sistema se gestiona y ejecuta de forma 100% nativa en **Python**.

---

## Arquitectura del Proyecto

```
dt_Hyundai/
│
├── realsense/                      # SISTEMA REALSENSE MULTICANAL (100% PYTHON)
│   ├── config.json                 # Parámetros de hardware, almacenamiento, red e IPC
│   ├── run.py                      # Lanzador maestro "All-in-One" para la Jetson
│   ├── download_dataset.py         # Sincronizador de datasets Jetson -> PC
│   │
│   ├── recorder/                   # MÓDULO 1: Backend de Grabación a 30 FPS en NVMe
│   │   ├── camera_manager.py       # Pipeline 4 canales (1280x720) y timestamps por hardware
│   │   ├── db3_recorder.py         # Grabador asíncrono SQLite WAL (Queue FIFO RAM 150)
│   │   ├── mosaic_builder.py       # Monitor de previsualización RGB en vivo, FPS, TS, REC
│   │   └── main_recorder.py        # Orquestador del backend y servidor IPC
│   │
│   ├── viewer/                     # MÓDULO 2: Frontend X11 y Control Remoto
│   │   ├── stream_display.py       # Pantalla ligera en vivo del canal RGB (OpenCV)
│   │   ├── tag_dialog.py           # Modal Tkinter: escribe la clase (C, IA, II, IR) + ENTER
│   │   └── main_viewer.py          # Captura de teclado en vivo ('R' GRABAR, 'E' DETENER/CLASIFICAR, 'Q' SALIR)
│   │
│   ├── inspector/                  # MÓDULO 3: Reproducción e Inspección Offline en PC (Mosaico 2x2 Completo)
│   │   ├── db3_parser.py           # Deserializador indexado de matrices nativas Z16
│   │   └── main_inspector.py       # Reproductor Mosaico 2x2 con timeline y telemetría por cursor
│   │
│   ├── ipc/                        # MÓDULO 4: Comunicación Interproceso
│   │   └── ipc_manager.py          # Named Pipes (/tmp/pipe_frame y /tmp/pipe_cmd) + framing
│   │
│   └── grabaciones/                # Directorio de almacenamiento organizado por clases
│       ├── C/                      # Grabaciones clase C
│       ├── IA/                     # Grabaciones clase IA
│       ├── II/                     # Grabaciones clase II
│       └── IR/                     # Grabaciones clase IR
│
├── scripts/
│   └── temperature/                # Monitor y comparador de temperaturas de la Jetson
│       ├── gui.py                  # Interfaz gráfica Tkinter / Matplotlib
│       └── jetson_temperature.py   # Servicio de registro de temperaturas
│
├── temperature_logs/               # Registros históricos de temperatura (.txt)
├── requirements.txt                # Dependencias del proyecto
└── README.md
```

---

## Especificaciones de Flujos de Datos

| Parámetro | Previsualización Remota (Canal X11 / Captura) | Almacenamiento Local (Dataset `.db3` en NVMe) | Inspección Offline en PC (`main_inspector.py`) |
| :--- | :--- | :--- | :--- |
| **Vista** | **Solo Canal RGB** (Pantalla ligera en vivo) | **4 Canales RAW** (Archivados) | **Mosaico $2 \times 2$ Completo** (Color, Z16, IR1, IR2) |
| **Resolución** | $640 \times 480$ (Flujo liviano de video) | $1280 \times 720$ por cada canal | $1280 \times 720$ nativo por cuadrante |
| **Tasa de Refresco** | $15\text{ FPS}$ (Ultra fluido en red SSH) | $30\text{ FPS}$ continuos y garantizados | Velocidad real (30 FPS) o cuadro a cuadro |
| **Formato** | Buffer JPEG comprimido (Calidad 50%) | Raw original ($Z_{16}$ 16 bits, BGR8, Y8) | Matrices NumPy originales y mapa métrico |
| **Función** | Decidir cuándo grabar (`R`), parar y etiquetar (`E`) | Guardado íntegro para entrenamiento/análisis | Análisis de distancias y revisión detallada |

---

## Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/MangoTangoPea/dt_Hyundai.git
   cd dt_Hyundai
   ```

2. Crear y activar entorno virtual:
   ```bash
   python -m venv .venv
   # En Linux / Jetson:
   source .venv/bin/activate
   # En Windows:
   .venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

---

## Guía de Uso Operativo (100% Python)

### 1. En la NVIDIA Jetson Orin Nano (Captura y Control Remoto)

Conéctate por SSH habilitando el reenvío X11 (`ssh -X` o con clientes como MobaXterm):
```bash
ssh -X jetson@<IP_JETSON>
cd dt_Hyundai
python3 realsense/run.py
```

* **Inicialización automática**: Crea los directorios en el SSD NVMe (`/media/nvme/grabaciones`) y las tuberías interproceso sin scripts `.sh`.
* **Pantalla de captura**: Se abrirá en tu monitor una **pantalla limpia únicamente con el canal RGB** (`640x480`) para monitorear la escena sin saturar la red.
* **Controles activos en la ventana:**
  - **`R`**: Inicia la grabación a $30\text{ FPS}$ en el disco NVMe (`temp_rec_{timestamp}.db3`). En la pantalla RGB aparecerá el indicador parpadeante `● REC`.
  - **`E`**: Detiene la grabación y abre la ventana modal de clasificación:
    - Muestra los ejemplos en pantalla:
      - `C`  -> Centro / Normal
      - `IA` -> Inclinación Adelante
      - `II` -> Inclinación Izquierda
      - `IR` -> Inclinación Derecha (Right)
    - **Escribes la clase** en la casilla de texto (con foco automático) y presionas **`ENTER`**.
    - El archivo se traslada y clasifica automáticamente a `grabaciones/{CLASE}/{CLASE}_{timestamp}.db3`.
    - Si presionas **`ESC`** o cierras, se conserva seguro como temporal en `grabaciones/temp_rec_{timestamp}.db3`.
  - **`Q` o `ESC`**: Cierra el visualizador y finaliza ordenadamente la captura.

---

### 2. Sincronizar Datasets a la PC Local

Desde tu PC local (Windows o Linux), descarga los archivos `.db3`:
```bash
python realsense/download_dataset.py --ip 192.168.1.100 --user jetson
```
*(Utiliza `rsync` con fallback automático a `scp`, descargando de forma incremental todos los archivos `.db3` organizados por carpetas de clase).*

---

### 3. En la PC Local (Inspección y Reproducción Offline con Mosaico 2x2)

Abre el reproductor offline con selector gráfico de archivo:
```bash
python realsense/inspector/main_inspector.py
```
*(O pasando la ruta directa: `python realsense/inspector/main_inspector.py grabaciones/C/C_20260905_113000.db3`)*

* **Aquí se despliega el Mosaico $2 \times 2$ completo**:
  ```
  ┌─────────────────────────────────┬─────────────────────────────────┐
  │ 1. RGB Color (1280x720)         │ 2. Profundidad Z16 (Cursor mm/m)│
  ├─────────────────────────────────┼─────────────────────────────────┤
  │ 3. Infrarrojo 1 - Izquierdo     │ 4. Infrarrojo 2 - Derecho       │
  └─────────────────────────────────┴─────────────────────────────────┘
  ```
* **Telemetría Métrica por Mouse**: Pasa el ratón sobre el cuadrante 2 (Profundidad) para calcular en tiempo real la distancia exacta en milímetros y metros:
  $$D_{(x,y)} = \text{matriz}[y, x] \times \text{depth\_scale}$$
* **Timeline Trackbar**: Deslízate interactivamente a cualquier fotograma.
* **Atajos del reproductor**:
  - `Espacio`: Reproducir / Pausar.
  - `A` / `D` o Flechas Izquierda/Derecha: Retroceder / Avanzar un fotograma.
  - `Q` o `ESC`: Salir.

---

## Módulo Adicional: Monitor de Temperaturas

Para visualizar las curvas térmicas registradas en la Jetson:
```bash
python scripts/temperature/gui.py
```
