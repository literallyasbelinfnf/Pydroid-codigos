import json
import tkinter as tk
from tkinter import filedialog
import os


def convert_all_to_psych(input_folder, output_folder):
    # Primero, recorremos todo el árbol para recopilar rutas de archivos chart y metadata:
    chart_dict = {}
    metadata_dict = {}

    for root, dirs, files in os.walk(input_folder):
        for f in files:
            lower = f.lower()
            if lower.endswith('.json') and 'chart' in lower:
                # Ejemplo: "song-chart-nombre.json"
                chart_dict[lower] = os.path.join(root, f)
            elif lower.endswith('.json') and 'metadata' in lower:
                # Ejemplo: "song-metadata-nombre.json"
                metadata_dict[lower] = os.path.join(root, f)

    # Ahora, para cada chart, buscamos su metadata correspondiente (reemplazando "chart" → "metadata"):
    for chart_lower, chart_path in chart_dict.items():
        expected_meta_lower = chart_lower.replace('chart', 'metadata')
        if expected_meta_lower in metadata_dict:
            metadata_path = metadata_dict[expected_meta_lower]
            convert_to_psych(chart_path, metadata_path, output_folder)
        else:
            print(f"No se encontró metadata para {chart_path}")


def format_event_values(keys, valores):
    """
    Esta función original se usa en los eventos predefinidos.
    Retorna una cadena con los pares formateados (clave:valor) separados por comas.
    """
    return ",".join(f"{key}:{valores[key]}" for key in keys if key in valores)


def format_event_values_2(valores):
    """
    Formatea los key-value de un evento (diccionario) en dos cadenas:
      - value1: contendrá hasta 3 pares (separados por comas y sin coma final)
      - value2: contendrá hasta 3 pares adicionales (sin coma final) o vacío si no hay suficientes.
    Si hay más de 6 pares, se ignoran los extras.
    """
    flat_values = [f"{key}:{valores[key]}" for key in valores]
    if not flat_values:
        return ("", "")
    if len(flat_values) <= 3:
        return (",".join(flat_values), "")
    else:
        value1 = ",".join(flat_values[:3])
        value2 = ""
        if len(flat_values) > 3:
            value2 = ",".join(flat_values[3:6])
        return (value1, value2)


def convert_to_psych(input_chart, input_metadata, output_folder):
    with open(input_chart, 'r') as chart_file, open(input_metadata, 'r') as metadata_file:
        chart_data = json.load(chart_file)
        metadata_data = json.load(metadata_file)

    # Tomamos el BPM inicial del primer cambio de tiempo (si no hay, usamos 150)
    bpm = metadata_data.get("timeChanges", [{}])[0].get("bpm", 150)
    ms_per_beat = 60000 / bpm

    for difficulty, notes_data in chart_data.get("notes", {}).items():
        scroll_speed = chart_data.get("scrollSpeed", {}).get(difficulty, 1.0)

        psych_chart = {
            "song": {
                "player1": metadata_data["playData"]["characters"]["player"],
                "player2": metadata_data["playData"]["characters"]["opponent"],
                "gfVersion": metadata_data["playData"]["characters"]["girlfriend"],
                "credit": metadata_data["playData"].get("charter", "Unknown"),
                "splashSkin": metadata_data["playData"].get("noteStyle", ""),
                "song": metadata_data["songName"],
                "difficulty": difficulty.capitalize(),
                "needsVoices": True,
                "arrowSkin": "",
                "stage": metadata_data["playData"]["stage"],
                "validScore": True,
                "bpm": bpm,
                "speed": scroll_speed,
                "notes": [],
                "events": []
            }
        }

        # Agrupamos notas en secciones de 4 beats
        sections = {}
        for note in notes_data:
            time_in_ms = note["t"]
            lane = note["d"]
            duration_in_ms = note.get("l", 0)

            section_start = int(time_in_ms // (4 * ms_per_beat)) * (4 * ms_per_beat)
            if section_start not in sections:
                sections[section_start] = {
                    "sectionBeats": 4,
                    "sectionNotes": [],
                    "typeOfSection": 0,
                    "gfSection": False,
                    "altAnim": False,
                    "mustHitSection": True,
                    "changeBPM": False,
                    "bpm": bpm
                }

            formatted_note = [time_in_ms, lane, duration_in_ms]
            sections[section_start]["sectionNotes"].append(formatted_note)

        for section_start in sorted(sections.keys()):
            sections[section_start]["sectionNotes"].sort(key=lambda x: x[0])
            psych_chart["song"]["notes"].append(sections[section_start])

        # Transformación de eventos
        for event in chart_data.get("events", []):
            tiempo = event["t"]
            nombre = event["e"]
            # Usamos .get("v", {}) para evitar KeyError si no existe "v"
            valores = event.get("v", {})

            # Si el valor es numérico, lo convertimos a dict
            if isinstance(valores, (int, float)):
                valores = {"char": valores}

            if nombre == "ZoomCamera":
                nuevo_valor = [
                    "ZoomCamera",
                    format_event_values(["ease", "duration"], valores),
                    format_event_values(["zoom", "mode"], valores)
                ]
            elif nombre == "FocusCamera":
                # El mismo formato independientemente de si 'char' está vacío o no,
                # ya que .get("char") retornará "" si no existe.
                nuevo_valor = [
                    "FocusCamera",
                    format_event_values(["duration", "x", "y"], valores),
                    format_event_values(["char", "ease"], valores)
                ]
            elif nombre == "PlayAnimation":
                target = valores.get("target", "").lower()
                if target == "girlfriend":
                    target = "gf"
                elif target == "boyfriend":
                    target = "bf"
                elif target == "dad":
                    target = "dad"

                nuevo_valor = [
                    "Play Animation",
                    valores.get("anim", ""),
                    target
                ]
            elif nombre == "ScrollSpeed":
                nuevo_valor = [
                    "Change Scroll Speed",
                    str(valores.get("scroll", 1.0)),
                    str(valores.get("duration", 32))
                ]
            else:
                # Otros eventos: máximo 2 valores
                value1, value2 = format_event_values_2(valores)
                nuevo_valor = [nombre, value1, value2]

            # Filtrar valores vacíos y asegurar que estén como strings
            final_event = []
            for v in nuevo_valor:
                final_event.append(str(v) if not isinstance(v, str) else v)

            psych_chart["song"]["events"].append([tiempo, [final_event]])

        song_name = metadata_data["songName"]
        output_filename = f"{song_name}-{difficulty}.json"
        output_path = os.path.join(output_folder, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as output_file:
            json.dump(psych_chart, output_file, indent=4)

        print(f"Archivo convertido guardado: {output_path}")


def select_folders():
    input_folder = filedialog.askdirectory(title="Selecciona la carpeta de entrada")
    if not input_folder:
        print("No se seleccionó la carpeta de entrada.")
        return

    output_folder = filedialog.askdirectory(title="Selecciona la carpeta de salida")
    if not output_folder:
        print("No se seleccionó la carpeta de salida.")
        return

    convert_all_to_psych(input_folder, output_folder)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Conversor de Charts FNF Vanilla a Psych Engine")

    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack()

    label = tk.Label(frame, text="Conversor de Charts FNF Vanilla a Psych Engine", font=("Arial", 14))
    label.pack(pady=10)

    button = tk.Button(
        frame,
        text="Seleccionar carpetas y convertir",
        command=select_folders,
        font=("Arial", 12)
    )
    button.pack(pady=10)

    root.mainloop()