#!/usr/bin/env python3

import csv
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class TemperatureViewer:


    def __init__(self, root):
        self.root = root
        self.root.title("Jetson Temperature Viewer")
        self.root.geometry("1000x650")

        self.filename = None
        self.timestamps = []
        self.data = {}
        self.variables = {}

        # Botones superiores
        top = tk.Frame(root)
        top.pack(fill="x", padx=10, pady=10)

        tk.Button(
            top,
            text="Abrir archivo",
            command=self.open_file
        ).pack(side="left")

        tk.Button(
            top,
            text="Recargar",
            command=self.load_data
        ).pack(side="left", padx=5)

        self.label = tk.Label(
            top,
            text="Ningún archivo seleccionado"
        )
        self.label.pack(side="left", padx=15)

        # Panel de sensores
        self.sensor_frame = tk.Frame(root)
        self.sensor_frame.pack(side="left", fill="y", padx=10)

        # Gráfica
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

    def open_file(self):

        filename = filedialog.askopenfilename(
            filetypes=[
                ("Temperature files", "*.txt *.csv"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self.filename = filename
            self.load_data()

    def load_data(self):

        if not self.filename:
            return

        self.timestamps = []
        self.data = {}

        with open(self.filename, newline="") as file:

            reader = csv.DictReader(file)

            sensors = reader.fieldnames[2:]

            for sensor in sensors:
                self.data[sensor] = []

            for row in reader:

                timestamp = datetime.strptime(
                    row["date"] + " " + row["time"],
                    "%Y-%m-%d %H:%M:%S"
                )

                self.timestamps.append(timestamp)

                for sensor in sensors:

                    value = row[sensor]

                    if value == "NA":
                        self.data[sensor].append(None)
                    else:
                        self.data[sensor].append(float(value))

        self.label.config(
            text=self.filename.split("/")[-1]
        )

        self.create_checkboxes()
        self.plot()

    def create_checkboxes(self):

        # Borrar controles anteriores
        for widget in self.sensor_frame.winfo_children():
            widget.destroy()

        self.variables = {}

        for sensor in self.data:

            var = tk.BooleanVar(value=True)

            tk.Checkbutton(
                self.sensor_frame,
                text=sensor,
                variable=var,
                command=self.plot
            ).pack(anchor="w")

            self.variables[sensor] = var

    def plot(self):

        self.ax.clear()

        for sensor, var in self.variables.items():

            if var.get():

                values = self.data[sensor]

                # Solo mostrar sensores con datos
                if any(value is not None for value in values):

                    self.ax.plot(
                        self.timestamps,
                        values,
                        label=sensor
                    )

        self.ax.set_title("Temperaturas Jetson Nano")
        self.ax.set_xlabel("Hora")
        self.ax.set_ylabel("Temperatura (°C)")
        self.ax.grid(True)
        self.ax.legend()

        self.figure.autofmt_xdate()

        self.canvas.draw()

root = tk.Tk()
app = TemperatureViewer(root)
root.mainloop()
