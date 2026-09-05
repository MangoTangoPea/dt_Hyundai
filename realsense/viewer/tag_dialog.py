"""
Cuadro de dialogo modal en Tkinter para clasificar la grabacion escribiendo la etiqueta.
Muestra claramente los ejemplos validos (C, IA, II, IR), un campo de texto (Entry)
con foco automatico para escribir directamente, y permite confirmar con ENTER o cancelar con ESC.
Aplica normalizacion .upper().strip() y crea dinamicamente la subcarpeta si no existe.
"""

import tkinter as tk


class TagDialog:
    def __init__(self, valid_tags=("C", "IA", "II", "IR")):
        self.valid_tags = [t.upper().strip() for t in valid_tags]
        self.selected_tag = None

    def show(self) -> str:
        """
        Abre la ventana modal bloqueante con campo de texto.
        Devuelve la etiqueta normalizada (.upper().strip()) o None si se cancela/descarta.
        """
        root = tk.Tk()
        root.title("Clasificación de Grabación - RealSense")
        root.geometry("460x320")
        root.resizable(False, False)
        root.configure(bg="#f8f9fa")

        # Centrar la ventana en pantalla
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Asegurar foco al frente
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        self.selected_tag = None

        # Encabezado principal
        lbl_title = tk.Label(
            root,
            text="Escribe la Clase de la Grabación",
            font=("Arial", 13, "bold"),
            bg="#f8f9fa",
            fg="#212529",
            pady=10,
        )
        lbl_title.pack()

        # Cuadro de ejemplos permitidos
        examples_frame = tk.LabelFrame(
            root,
            text=" Ejemplos / Clases Disponibles ",
            font=("Arial", 9, "bold"),
            bg="#ffffff",
            fg="#495057",
            padx=12,
            pady=8,
            relief="groove",
        )
        examples_frame.pack(padx=24, pady=(0, 12), fill="x")

        examples_text = (
            "• C   -> Centro / Normal\n"
            "• IA  -> Inclinación Adelante\n"
            "• II  -> Inclinación Izquierda\n"
            "• IR  -> Inclinación Derecha (Right)"
        )
        lbl_examples = tk.Label(
            examples_frame,
            text=examples_text,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#343a40",
            justify="left",
        )
        lbl_examples.pack(anchor="w")

        # Mensaje de instruccion
        lbl_inst = tk.Label(
            root,
            text="Ingresa la clase (ej. C, IA, II, IR) y presiona ENTER:",
            font=("Arial", 9),
            bg="#f8f9fa",
            fg="#495057",
        )
        lbl_inst.pack(pady=(2, 6))

        # Campo de entrada de texto
        entry_var = tk.StringVar()
        entry = tk.Entry(
            root,
            textvariable=entry_var,
            font=("Arial", 14, "bold"),
            justify="center",
            width=18,
            bd=2,
            relief="solid",
            highlightthickness=1,
            highlightcolor="#1971c2",
        )
        entry.pack(pady=4)
        entry.focus_set()

        # Etiqueta de advertencia de error
        lbl_error = tk.Label(
            root,
            text="",
            font=("Arial", 8, "italic"),
            bg="#f8f9fa",
            fg="#d6336c",
        )
        lbl_error.pack(pady=(2, 6))

        def confirm(event=None):
            val = entry_var.get().strip().upper()
            if not val:
                lbl_error.config(text="* Por favor escribe una etiqueta o presiona ESC para descartar.")
                return

            self.selected_tag = val
            root.destroy()

        def cancel(event=None):
            self.selected_tag = None
            root.destroy()

        # Eventos de teclado
        entry.bind("<Return>", confirm)
        root.bind("<Escape>", cancel)
        root.protocol("WM_DELETE_WINDOW", cancel)

        # Botones de accion
        btn_frame = tk.Frame(root, bg="#f8f9fa")
        btn_frame.pack(pady=(4, 10))

        btn_ok = tk.Button(
            btn_frame,
            text="Guardar [ENTER]",
            font=("Arial", 10, "bold"),
            bg="#2b8a3e",
            fg="white",
            activebackground="#237032",
            activeforeground="white",
            padx=14,
            pady=4,
            relief="raised",
            cursor="hand2",
            command=confirm,
        )
        btn_ok.pack(side="left", padx=8)

        btn_cancel = tk.Button(
            btn_frame,
            text="Descartar / Temporal [ESC]",
            font=("Arial", 9),
            bg="#e9ecef",
            fg="#495057",
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
            command=cancel,
        )
        btn_cancel.pack(side="left", padx=8)

        root.mainloop()
        return self.selected_tag


if __name__ == "__main__":
    dialog = TagDialog()
    tag = dialog.show()
    print(f"Etiqueta escrita: '{tag}'")
