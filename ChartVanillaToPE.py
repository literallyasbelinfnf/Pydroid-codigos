import json
import tkinter as tk
from tkinter import filedialog
import os


def convert_all_to_psych(input_folder, output_folder):
    for root, dirs, files in os.walk(input_folder):
        charts = [f for f in files if f.endswith("chart.json")]
        metadatas = [f for f in files if f.endswith("metadata.json")]

        for chart in charts:
            chart_path = os.path.join(root, chart)
            metadata_name = chart.replace("chart.json", "metadata.json")
            if metadata_name in metadatas:
                metadata_path = os.path.join(root, metadata_name)
                convert_to_psych(chart_path, metadata_path, output_folder)
            else:
                print(f"No se encontró metadata para {chart}")


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

    bpm = metadata_data["timeChanges"][0]["bpm"] if metadata_data["timeChanges"] else 150
    ms_per_beat = 60000 / bpm

    for difficulty, notes_data in chart_data["notes"].items():
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
            valores = event["v"]

            # Si el valor es numérico, lo convertimos a dict
            if isinstance(valores, int) or isinstance(valores, float):
                valores = {"char": valores}

            if nombre == "ZoomCamera":
                nuevo_valor = [
                    "ZoomCamera",
                    format_event_values(["ease", "duration"], valores),
                    format_event_values(["zoom", "mode"], valores)
                ]
            elif nombre == "FocusCamera":
                # Para FocusCamera: evitamos agregar una línea vacía adicional
                if valores.get("char") == "":
                    nuevo_valor = [
                        "FocusCamera",
                        format_event_values(["duration", "x", "y"], valores),
                        format_event_values(["char", "ease"], valores)
                    ]
                else:
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
                # Solo usamos duración y scroll; se traduce a "Change Scroll Speed"
                nuevo_valor = [
                    "Change Scroll Speed",
                    str(valores.get("scroll", 1.0)),
                    str(valores.get("duration", 32))
                ]
            else:
                # Otros eventos: se usan máximo 2 values.
                value1, value2 = format_event_values_2(valores)
                nuevo_valor = [nombre, value1, value2]

            # Filtrar valores vacíos (pero mantener las comas necesarias)
            final_event = []
            for v in nuevo_valor:
                if isinstance(v, str):
                    # Mantenemos cadenas vacías solo si son necesarias
                    final_event.append(v)
                else:
                    # Si no es string (por ejemplo, un dict), lo convertimos a string
                    final_event.append(str(v))
            psych_chart["song"]["events"].append([tiempo, [final_event]])

        song_name = metadata_data["songName"]
        output_path = os.path.join(output_folder, f"{song_name}-{difficulty}.json")
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


root = tk.Tk()
root.title("Conversor de Charts a Psych Engine")

frame = tk.Frame(root, padx=20, pady=20)
frame.pack()

label = tk.Label(frame, text="Conversor de Charts FNF Vanilla a Psych Engine", font=("Arial", 14))
label.pack(pady=10)

button = tk.Button(frame, text="Seleccionar carpetas y convertir", command=select_folders, font=("Arial", 12))
button.pack(pady=10)

root.mainloop()