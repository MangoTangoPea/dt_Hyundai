#!/usr/bin/env python3
import os, glob, csv, tkinter as tk
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LOGS_DIR = Path(__file__).resolve().parent.parent / "temperature_logs"

class TemperatureViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Jetson Temperature Viewer")
        self.root.geometry("1000x600")
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

        # Panel izquierdo: lista de los 10 últimos logs
        self.listbox = tk.Listbox(root, width=28)
        self.listbox.pack(side="left", fill="y", padx=5, pady=5)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.load_and_plot())

        # Gráfica
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

        self.refresh()

    def refresh(self):
        """Actualiza lista y recarga gráfica automáticamente cada 10s"""
        files = sorted(glob.glob(str(LOGS_DIR / "*.txt")), reverse=True)[:10]
        current = [self.listbox.get(i) for i in range(self.listbox.size())]
        file_names = [os.path.basename(f) for f in files]

        if current != file_names:
            self.listbox.delete(0, tk.END)
            for name in file_names:
                self.listbox.insert(tk.END, name)
            if file_names:
                self.listbox.select_set(0)

        self.load_and_plot()
        self.root.after(10000, self.refresh)

    def load_and_plot(self):
        sel = self.listbox.curselection()
        if not sel: return
        file_path = LOGS_DIR / self.listbox.get(sel[0])

        times, temps = [], []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3 and row[0] != "date":
                    try:
                        times.append(datetime.strptime(f"{row[0]} {row[1]}", "%Y-%m-%d %H:%M:%S"))
                        temps.append(float(row[2]) if row[2] != "NA" else None)
                    except ValueError: pass

        self.ax.clear()
        if times:
            self.ax.plot(times, temps, label="CPU Thermal", color="blue")
            d = times[0].date()
            self.ax.set_xlim(datetime(d.year, d.month, d.day, 0, 0), datetime(d.year, d.month, d.day, 23, 59, 59))

        self.ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        self.ax.set_title(f"Temperatura CPU - {file_path.name}")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self.fig.autofmt_xdate(rotation=45)
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = TemperatureViewer(root)
    root.mainloop()
