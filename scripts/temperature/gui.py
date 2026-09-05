#!/usr/bin/env python3
import os, glob, csv, tkinter as tk
from datetime import datetime, date
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "temperature_logs"
BASE_DATE = date(2000, 1, 1)

class TemperatureViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Jetson Temperature Viewer - Comparador de Días")
        self.root.geometry("1100x620")
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

        # Panel izquierdo con checkboxes para seleccionar múltiples días
        self.side_panel = tk.Frame(root, width=220)
        self.side_panel.pack(side="left", fill="y", padx=8, pady=8)
        tk.Label(self.side_panel, text="Días a comparar:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))

        self.checks_frame = tk.Frame(self.side_panel)
        self.checks_frame.pack(fill="both", expand=True)

        self.variables = {}  # {nombre_archivo: tk.BooleanVar}

        # Gráfica
        self.fig, self.ax = plt.subplots(figsize=(9, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

        self.refresh()

    def refresh(self):
        """Busca los 10 últimos logs, actualiza checkboxes y redibuja la gráfica cada 10s"""
        files = sorted(glob.glob(str(LOGS_DIR / "*.txt")), reverse=True)[:10]
        file_names = [os.path.basename(f) for f in files]

        # Si cambió la lista de archivos, reconstruir los checkboxes conservando selecciones
        if file_names != list(self.variables.keys()):
            for widget in self.checks_frame.winfo_children():
                widget.destroy()

            old_vars = self.variables
            self.variables = {}

            for idx, name in enumerate(file_names):
                default_val = old_vars[name].get() if name in old_vars else (idx == 0)
                var = tk.BooleanVar(value=default_val)
                self.variables[name] = var

                tk.Checkbutton(
                    self.checks_frame,
                    text=name.replace(".txt", ""),
                    variable=var,
                    font=("Consolas", 9),
                    command=self.plot
                ).pack(anchor="w", pady=2)

        self.plot()
        self.root.after(10000, self.refresh)

    def plot(self):
        """Grafica los días seleccionados superpuestos sobre las 24 horas del día"""
        self.ax.clear()

        has_data = False
        for file_name, var in self.variables.items():
            if not var.get():
                continue

            file_path = LOGS_DIR / file_name
            times, temps = [], []

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for row in csv.reader(f):
                    if len(row) >= 3 and row[0] != "date":
                        try:
                            # Normalizar la hora sobre una fecha base común para comparar los días
                            t = datetime.strptime(row[1], "%H:%M:%S").time()
                            times.append(datetime.combine(BASE_DATE, t))
                            temps.append(float(row[2]) if row[2] != "NA" else None)
                        except ValueError:
                            pass

            if times:
                label = file_name.replace("temperatures_", "").replace("temperature_", "").replace(".txt", "")
                self.ax.plot(times, temps, label=label, linewidth=1.5)
                has_data = True

        # Eje X fijo de 24 horas (00:00 a 23:59:59)
        start_time = datetime.combine(BASE_DATE, datetime.min.time())
        end_time = datetime.combine(BASE_DATE, datetime.max.time())
        self.ax.set_xlim(start_time, end_time)

        self.ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        self.ax.set_title("Comparativa de Temperatura de CPU (24 Horas)", fontsize=11, fontweight="bold")
        self.ax.set_xlabel("Hora del día", fontweight="bold")
        self.ax.set_ylabel("Temperatura (°C)", fontweight="bold")
        self.ax.grid(True, linestyle="--", alpha=0.6)

        if has_data:
            self.ax.legend(loc="upper right")

        self.fig.autofmt_xdate(rotation=45)
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = TemperatureViewer(root)
    root.mainloop()
