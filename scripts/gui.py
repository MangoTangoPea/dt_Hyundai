#!/usr/bin/env python3

import csv
import os
import sys
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class TemperatureViewer:

    def __init__(self, root):
        self.root = root
        self.root.title("Jetson Temperature Viewer")
        self.root.geometry("1100x650")

        # Ruta predeterminada de logs (compatible con Linux/Ubuntu y Windows)
        script_dir = Path(__file__).resolve().parent
        project_dir = script_dir.parent
        self.logs_dir = project_dir / "temperature_logs"
        if not self.logs_dir.exists():
            # Alternativa por si se ejecuta en Jetson con la ruta directa del home
            home_logs = Path("/home/gigseea/temperature_logs")
            if home_logs.exists():
                self.logs_dir = home_logs

        self.filename = None
        self.timestamps = []
        self.temperatures = []
        self.files_map = []
        self.auto_refresh_interval = 10000  # Actualizar cada 10 segundos

        # Barra superior de controles
        top = tk.Frame(root)
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(
            top,
            text="Buscar otro archivo...",
            command=self.open_file_dialog
        ).pack(side="left")

        self.label = tk.Label(
            top,
            text="Cargando logs...",
            font=("Arial", 10, "bold")
        )
        self.label.pack(side="left", padx=15)

        self.status_label = tk.Label(
            top,
            text="● Actualización automática activa (10s)",
            fg="#008000",
            font=("Arial", 9, "italic")
        )
        self.status_label.pack(side="right", padx=10)

        # Panel lateral izquierdo: Lista de últimos 10 archivos de logs
        side_panel = tk.Frame(root, width=220)
        side_panel.pack(side="left", fill="y", padx=10, pady=5)

        tk.Label(
            side_panel,
            text="Últimos logs (temperatura):",
            font=("Arial", 9, "bold")
        ).pack(anchor="w", pady=(0, 5))

        list_container = tk.Frame(side_panel)
        list_container.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_container, orient="vertical")
        self.file_listbox = tk.Listbox(
            list_container,
            yscrollcommand=scrollbar.set,
            width=26,
            height=20,
            font=("Consolas", 9),
            selectmode="browse"
        )
        scrollbar.config(command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.pack(side="left", fill="both", expand=True)

        # Cargar archivo al hacer clic en un elemento de la lista
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        # Área de Gráfica
        self.figure, self.ax = plt.subplots(figsize=(9, 6))

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=root
        )

        self.canvas.get_tk_widget().pack(
            side="right",
            fill="both",
            expand=True
        )

        # Protocolo de cierre de ventana para matar todo el proceso de inmediato
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Cargar archivos y comenzar el bucle de actualización automática
        self.refresh_data(is_initial=True)
        self.schedule_auto_refresh()

    def on_close(self):
        """Cierra figuras de matplotlib, destruye la ventana y termina el proceso."""
        try:
            plt.close("all")
            self.root.destroy()
        except Exception:
            pass
        finally:
            os._exit(0)

    def schedule_auto_refresh(self):
        """Programa la actualización automática periódica."""
        self.refresh_data(is_initial=False)
        self.root.after(self.auto_refresh_interval, self.schedule_auto_refresh)

    def refresh_data(self, is_initial=False):
        """Verifica nuevos archivos y actualiza el gráfico con los nuevos datos."""
        if not self.logs_dir.exists():
            return

        all_files = [
            f for f in self.logs_dir.glob("*.txt")
        ] + [
            f for f in self.logs_dir.glob("*.csv")
        ]

        # Ordenar por fecha o nombre descendente
        all_files.sort(key=lambda f: f.name, reverse=True)
        latest_files = all_files[:10]

        current_selected_name = None
        sel = self.file_listbox.curselection()
        if sel and sel[0] < len(self.files_map):
            current_selected_name = self.files_map[sel[0]].name

        # Comprobar si la lista cambió
        new_names = [f.name for f in latest_files]
        current_names = [f.name for f in self.files_map]

        if new_names != current_names or is_initial:
            self.files_map = latest_files
            self.file_listbox.delete(0, tk.END)
            for f in self.files_map:
                self.file_listbox.insert(tk.END, f.name)

            # Mantener la selección o seleccionar el primero por defecto
            if current_selected_name in new_names:
                idx = new_names.index(current_selected_name)
                self.file_listbox.select_set(idx)
                target_file = self.files_map[idx]
            elif self.files_map:
                self.file_listbox.select_set(0)
                target_file = self.files_map[0]
            else:
                target_file = None

            if target_file:
                self.load_data(target_file)
        else:
            # Si la lista es igual, recargar el archivo actualmente seleccionado para ver nuevas lecturas
            if self.filename and self.filename.exists():
                self.load_data(self.filename)

    def on_file_selected(self, event):
        """Manejador del evento de selección en el listbox."""
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.files_map):
                self.load_data(self.files_map[index])

    def open_file_dialog(self):
        """Permite buscar manualmente cualquier otro archivo fuera de la lista."""
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Temperature files", "*.txt *.csv"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.load_data(Path(filename))

    def load_data(self, file_path):
        """Lee el archivo y extrae solo la temperatura de CPU."""
        if not file_path or not Path(file_path).exists():
            return

        self.filename = Path(file_path)
        self.timestamps = []
        self.temperatures = []

        with open(self.filename, mode="r", encoding="utf-8", errors="ignore") as file:
            reader = csv.DictReader(file)
            sensors = [s.strip() for s in (reader.fieldnames or [])[2:] if s]

            cpu_col = None
            for s in sensors:
                if "cpu" in s.lower():
                    cpu_col = s
                    break
            if not cpu_col and sensors:
                cpu_col = sensors[0]

            for row in reader:
                clean_row = {k.strip(): v.strip() for k, v in row.items() if k and v is not None}
                if "date" not in clean_row or "time" not in clean_row:
                    continue

                try:
                    timestamp = datetime.strptime(
                        clean_row["date"] + " " + clean_row["time"],
                        "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    continue

                self.timestamps.append(timestamp)

                val_str = clean_row.get(cpu_col, "NA") if cpu_col else "NA"
                if val_str in ("NA", "", "None", None):
                    self.temperatures.append(None)
                else:
                    try:
                        self.temperatures.append(float(val_str))
                    except ValueError:
                        self.temperatures.append(None)

        self.label.config(
            text=f"Archivo: {self.filename.name}"
        )

        self.plot()

    def plot(self):
        """Dibuja la gráfica con las 24 horas fijas y marcas cada 30 minutos."""
        self.ax.clear()

        if self.timestamps and any(v is not None for v in self.temperatures):
            self.ax.plot(
                self.timestamps,
                self.temperatures,
                label="CPU Thermal",
                color="#0066cc",
                linewidth=1.5
            )

        if self.timestamps:
            base_date = self.timestamps[0].date()
            start_time = datetime(base_date.year, base_date.month, base_date.day, 0, 0, 0)
            end_time = datetime(base_date.year, base_date.month, base_date.day, 23, 59, 59)
            self.ax.set_xlim(start_time, end_time)

        self.ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

        self.ax.set_title("Temperatura CPU Jetson Nano", fontsize=12, fontweight="bold")
        self.ax.set_xlabel("Hora", fontweight="bold")
        self.ax.set_ylabel("Temperatura (°C)", fontweight="bold")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self.ax.legend(loc="upper right")

        self.figure.autofmt_xdate(rotation=45)

        self.canvas.draw()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = TemperatureViewer(root)
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        os._exit(0)
