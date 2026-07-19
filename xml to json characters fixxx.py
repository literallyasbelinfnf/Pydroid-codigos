import os
import xml.etree.ElementTree as ET
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

# ============================
# FUNCIONES AUXILIARES
# ============================

def hex_to_rgb(hex_color):
    hex_color = (hex_color or "#FFFFFF").lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])
    try:
        return [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    except:
        return [255, 255, 255]

def safe_float(value):
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# ============================
# CONVERSIÓN PRINCIPAL
# ============================

def convert(xml_path, output_folder):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        sprite = root.get('sprite')
        if not sprite or sprite.strip() == "":
            sprite = os.path.splitext(os.path.basename(xml_path))[0]

        antialias = root.get('antialiasing', 'true').lower() == 'true'
        flipX = root.get('flipX', 'false').lower() == 'true'
        isPlayer = root.get('isPlayer', 'false').lower() == 'true'
        icon = root.get('icon', 'face')
        color = hex_to_rgb(root.get('color', '#FFFFFF'))

        camx = int(safe_float(root.get('camx')))
        camy = int(safe_float(root.get('camy')))
        pos_x = int(safe_float(root.get('x')))
        pos_y = int(safe_float(root.get('y')))
        scale_value = safe_float(root.get('scale') or (1))

        animations = []
        for anim in root.findall('anim'):
            name = anim.get('name') or ""
            animname = anim.get('anim') or name or ""

            x = int(safe_float(anim.get('x')))
            y = int(safe_float(anim.get('y')))
            loop = anim.get('loop', 'false').lower() == 'true'
            fps = int(safe_float(anim.get('fps') or 24))

            indices_attr = anim.get('indices', '')
            indices = []
            if indices_attr:
                try:
                    indices = [int(i) for i in indices_attr.split(',')]
                except:
                    indices = []

            animations.append({
                "loop": loop,
                "offsets": [x, y],
                "anim": name,
                "fps": fps,
                "name": animname,
                "indices": indices
            })

        data = {
            "animations": animations,
            "vocals_file": "",
            "no_antialiasing": not antialias,
            "image": f"characters/{sprite}",
            "position": [pos_x, pos_y],
            "healthicon": icon,
            "flip_x": flipX,
            "healthbar_colors": color,
            "camera_position": [camx, camy],
            "sing_duration": 4,
            "scale": scale_value,
            "_editor_isPlayer": isPlayer
        }

        json_filename = os.path.splitext(os.path.basename(xml_path))[0] + ".json"
        json_path = os.path.join(output_folder, json_filename)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return True, json_filename
    except Exception as e:
        return False, f"{os.path.basename(xml_path)}: {e}"

# ============================
# INTERFAZ GRÁFICA
# ============================

class ConversorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Conversor XML a JSON (Psych Engine)")
        self.master.geometry("420x520")

        self.origen = tk.StringVar()
        self.destino = tk.StringVar()
        self.tema_actual = "oscuro"

        self.colores = {
            "oscuro": {
                "bg": "#1e1e2e",
                "text": "white",
                "sub": "#9ca3af",
                "button1": "#3b82f6",
                "button2": "#22c55e",
                "button3": "#a855f7",
                "area": "#0f172a",
                "progress": "#38bdf8"
            },
            "claro": {
                "bg": "#f8fafc",
                "text": "#111827",
                "sub": "#4b5563",
                "button1": "#2563eb",
                "button2": "#16a34a",
                "button3": "#9333ea",
                "area": "#e2e8f0",
                "progress": "#3b82f6"
            }
        }

        self.configurar_tema("oscuro")
        self.crear_interfaz()

    def configurar_tema(self, modo):
        c = self.colores[modo]
        self.master.configure(bg=c["bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=c["area"], background=c["progress"])
        self.tema_actual = modo

    def crear_interfaz(self):
        c = self.colores[self.tema_actual]

        tk.Label(self.master, text="Conversor XML a JSON", fg=c["text"], bg=c["bg"], font=("Arial", 15, "bold")).pack(pady=10)

        self.boton_tema = tk.Button(self.master, text="Cambiar a modo claro", command=self.cambiar_tema, bg=c["area"], fg=c["text"], font=("Arial", 10))
        self.boton_tema.pack(pady=5)

        frame = tk.Frame(self.master, bg=c["bg"])
        frame.pack(pady=10)

        tk.Button(frame, text="Seleccionar carpeta XML", command=self.seleccionar_origen, bg=c["button1"], fg="white", font=("Arial", 11), width=30).pack(pady=5)
        self.lbl_origen = tk.Label(frame, textvariable=self.origen, bg=c["bg"], fg=c["sub"], wraplength=350)
        self.lbl_origen.pack(pady=2)

        tk.Button(frame, text="Seleccionar carpeta destino", command=self.seleccionar_destino, bg=c["button2"], fg="white", font=("Arial", 11), width=30).pack(pady=5)
        self.lbl_destino = tk.Label(frame, textvariable=self.destino, bg=c["bg"], fg=c["sub"], wraplength=350)
        self.lbl_destino.pack(pady=2)

        tk.Button(self.master, text="Convertir todo", command=self.convertir_todo, bg=c["button3"], fg="white", font=("Arial", 13, "bold"), width=20, height=2).pack(pady=20)

        self.progress = ttk.Progressbar(self.master, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=5)

        self.texto_salida = tk.Text(self.master, height=10, width=45, bg=c["area"], fg=c["text"], font=("Consolas", 10))
        self.texto_salida.pack(pady=10)
        self.texto_salida.insert(tk.END, "Esperando acción...\n")

    def cambiar_tema(self):
        nuevo = "claro" if self.tema_actual == "oscuro" else "oscuro"
        self.configurar_tema(nuevo)
        self.reconstruir_interfaz()
        self.texto_salida.insert(tk.END, f"Tema cambiado a: {nuevo}\n")

    def reconstruir_interfaz(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        self.crear_interfaz()

    def seleccionar_origen(self):
        carpeta = filedialog.askdirectory(title="Selecciona carpeta con archivos XML")
        if carpeta:
            self.origen.set(carpeta)
            self.texto_salida.insert(tk.END, f"Carpeta XML: {carpeta}\n")

    def seleccionar_destino(self):
        carpeta = filedialog.askdirectory(title="Selecciona carpeta de salida JSON")
        if carpeta:
            self.destino.set(carpeta)
            self.texto_salida.insert(tk.END, f"Carpeta destino: {carpeta}\n")

    def convertir_todo(self):
        origen = self.origen.get()
        destino = self.destino.get()

        if not origen or not destino:
            messagebox.showwarning("Advertencia", "Debes seleccionar ambas carpetas primero.")
            return

        archivos = [f for f in os.listdir(origen) if f.lower().endswith(".xml")]
        if not archivos:
            messagebox.showinfo("Sin archivos", "No se encontraron archivos .xml en la carpeta seleccionada.")
            return

        total = len(archivos)
        self.progress["maximum"] = total
        ok, fail = 0, 0

        self.texto_salida.delete(1.0, tk.END)
        self.texto_salida.insert(tk.END, f"Iniciando conversión de {total} archivos...\n")

        for i, archivo in enumerate(archivos, 1):
            xml_path = os.path.join(origen, archivo)
            resultado, msg = convert(xml_path, destino)
            if resultado:
                ok += 1
                self.texto_salida.insert(tk.END, f"Convertido: {msg}\n")
            else:
                fail += 1
                self.texto_salida.insert(tk.END, f"Error: {msg}\n")

            self.progress["value"] = i
            self.master.update_idletasks()

        self.texto_salida.insert(tk.END, f"\nCompletado. Éxitos: {ok} - Errores: {fail}\n")
        messagebox.showinfo("Completado", f"Conversión finalizada.\nÉxitos: {ok}\nErrores: {fail}")

# ============================
# EJECUCIÓN
# ============================
if __name__ == "__main__":
    root = tk.Tk()
    app = ConversorApp(root)
    root.mainloop()