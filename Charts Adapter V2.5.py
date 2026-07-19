import os, json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f: return json.load(f)

def save_json(p, d):
    with open(p, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False, indent=4)

def execute_conversion(src, dest, c_path, m_path=None, c_stage=""):
    cd = load_json(c_path)
    md = load_json(m_path) if m_path else None
    
    sname, bpm, speed, p1, p2, gf, stage = "Untitled", 150, 1.0, "bf", "dad", "gf", "stage"
    n_src, e_src, ext, p1_sk, p2_sk = [], [], {}, "", ""

    # --- DETECCIÓN AUTOMÁTICA PARA PSYCH ENGINE ---
    if src in ["Psych 1.0.4", "Psych 0.7.3", "Nightmare Vision"]:
        if isinstance(cd, dict) and "song" in cd and isinstance(cd["song"], str):
            s = cd
            sname = cd["song"]
        else:
            s = cd.get("song", cd) if isinstance(cd, dict) else {}
            sname = s.get("song", "Untitled")

        bpm = s.get("bpm", bpm)
        speed = s.get("speed", speed)
        p1 = s.get("player1", p1)
        p2 = s.get("player2", p2)
        gf = s.get("gfVersion", gf)
        stage = s.get("stage", stage)
        n_src, e_src = s.get("notes", []), s.get("events", [])
        ext = {k: v for k, v in s.items() if k not in ["song", "bpm", "speed", "player1", "player2", "gfVersion", "stage", "notes", "events", "format"]}

    # --- DETECCIÓN AUTOMÁTICA PARA V-SLICE ---
    elif src == "V-Slice (v0.4.0+)":
        if not md: raise ValueError("Falta metadata.")
        sname = md.get("songName", "Untitled")
        ch = md.get("timeChanges", [])
        if ch: bpm = ch[0].get("bpm", 150)
        chars = md.get("playData", {}).get("characters", {})
        p1, p2, gf, stage = chars.get("player", "bf"), chars.get("opponent", "dad"), chars.get("girlfriend", "gf"), md.get("playData", {}).get("stage", "stage")
        
        if isinstance(cd, dict):
            sc = cd.get("scrollSpeed", 1.0)
            if isinstance(sc, dict): speed = list(sc.values())[0] if sc else 1.0
            else: speed = float(sc)
                
            raw_notes = cd.get("notes", [])
            if isinstance(raw_notes, dict):
                diffs_available = list(raw_notes.keys())
                if diffs_available:
                    meta_diffs = md.get("playData", {}).get("difficulties", [])
                    target_diff = meta_diffs[0] if meta_diffs and meta_diffs[0] in raw_notes else diffs_available[0]
                    n_src = raw_notes[target_diff]
            else:
                n_src = raw_notes
            
            camera_timeline = []
            for ev in cd.get("events", []):
                v = ev.get("v", {})
                e_name = ev.get("e", "Event")
                if e_name == "FocusCamera" and isinstance(v, dict):
                    c_val = int(v.get("char", 0))
                    camera_timeline.append({"time": float(ev.get("t", 0)), "char": c_val})
                    c_focus = "0" if c_val == 1 else "1"
                    e_src.append([ev.get("t", 0), [["Change Character Focus", c_focus, ""]]])
                elif isinstance(v, dict):
                    e_src.append([ev.get("t", 0), [[e_name, str(v.get("char", v.get("text", v))), str(v.get("y", ""))]]])
            camera_timeline.sort(key=lambda x: x["time"])

    # --- DETECCIÓN AUTOMÁTICA PARA CODENAME ENGINE ---
    elif src == "Codename Engine":
        if not md: raise ValueError("Falta meta.json.")
        sname, bpm, stage = md.get("displayName", md.get("name", "Untitled")), md.get("bpm", 150), md.get("stage", "stage")
        p1 = md.get("playables", ["bf"])[0] if md.get("playables") else "bf"
        p2 = md.get("opponents", ["dad"])[0] if md.get("opponents") else "dad"
        gf = md.get("gf", "gf")
        
        if isinstance(cd, dict):
            speed, n_src = cd.get("scrollSpeed", 1.0), cd.get("strumLines", [])
            for sl in n_src:
                if not isinstance(sl, dict): continue
                is_p = str(sl.get("type", "")).lower() == "player" or sl.get("type") == 1
                c = sl.get("characters", sl.get("character", sl.get("name", "")))
                c = c[0] if isinstance(c, list) and c else c
                if c and str(c).lower() != "null":
                    if is_p: p1 = str(c).strip()
                    elif str(sl.get("type", "")).lower() == "girlfriend" or sl.get("type") == 2: gf = str(c).strip()
                    else: p2 = str(c).strip()
                sk = sl.get("arrowSkin", "")
                if sk and str(sk).lower() not in ["default", "normal", "0", "null", "none"]:
                    if is_p: p1_sk = str(sk).strip()
                    else: p2_sk = str(sk).strip()
            for ev in cd.get("events", []):
                p_str = [str(p) for p in ev.get("params", [])] + ["", ""]
                e_src.append([ev.get("time", 0), [[ev.get("name", "Event"), p_str[0], p_str[1]]]])

    if c_stage and c_stage.strip(): stage = c_stage.strip()
    f_notes = []

    if src in ["Psych 1.0.4", "Psych 0.7.3", "Nightmare Vision"]:
        for sec in n_src:
            if not isinstance(sec, dict): continue
            h, ns = sec.get("mustHitSection", True), []
            for n in sec.get("sectionNotes", []):
                if isinstance(n, list) and len(n) >= 3:
                    d = int(n[1])
                    if src != dest and not h and 0 <= d < 8: d ^= 4
                    ns.append([float(n[0]), d, float(n[2])] + ([str(n[3])] if len(n) >= 4 and n[3] else []))
            f_notes.append({**sec, "mustHitSection": h, "sectionNotes": ns, "bpm": sec.get("bpm", bpm)})
            
    elif src == "V-Slice (v0.4.0+)":
        s_map = {}
        max_sec_idx = 0
        
        time_changes = md.get("timeChanges", [{"t": 0, "bpm": bpm}]) if md else [{"t": 0, "bpm": bpm}]
        time_changes.sort(key=lambda x: x["t"])
        
        def get_section_index_and_bpm(note_time):
            current_ms = 0.0
            current_beat = 0.0
            current_bpm = time_changes[0]["bpm"]
            
            for i in range(len(time_changes)):
                change = time_changes[i]
                next_change = time_changes[i+1] if i + 1 < len(time_changes) else None
                change_t = float(change["t"])
                change_bpm = float(change["bpm"])
                
                if note_time < change_t:
                    break
                    
                if next_change and note_time >= float(next_change["t"]):
                    duration = float(next_change["t"]) - change_t
                    beats_in_segment = duration / (60000.0 / change_bpm)
                    current_ms = float(next_change["t"])
                    current_beat += beats_in_segment
                    current_bpm = float(next_change["t"])
                else:
                    rem_ms = note_time - change_t
                    beats_in_rem = rem_ms / (60000.0 / change_bpm)
                    total_beats = current_beat + beats_in_rem
                    return int(total_beats // 4), change_bpm
            
            ms_per_section = (60000.0 / current_bpm) * 4
            return int(note_time // ms_per_section), current_bpm

        for n in n_src:
            if isinstance(n, dict):
                t = float(n.get("t", 0))
                raw_d = int(n.get("d", 0))
                k_type = str(n.get("k", "")).lower().strip()
                
                # LOGICA DE ENTRADA ESTILO CODENAME:
                # Determinamos de quién es la nota de manera binaria e independiente antes de mapear secciones
                if raw_d >= 4:
                    is_player = True
                    final_dir = raw_d
                elif k_type in ["player", "1"]:
                    is_player = True
                    final_dir = (raw_d % 4) + 4
                elif k_type in ["opponent", "0"]:
                    is_player = False
                    final_dir = raw_d % 4
                else:
                    # Si 'k' está vacío, usamos la cámara en ese milisegundo exacto para clasificar el carril original
                    current_focus = 1
                    for cam in camera_timeline:
                        if t >= cam["time"]: current_focus = cam["char"]
                        else: break
                    is_player = (current_focus == 1)
                    final_dir = (raw_d % 4) + 4 if is_player else (raw_d % 4)
                
                sec_idx, active_bpm = get_section_index_and_bpm(t)
                if sec_idx > max_sec_idx: max_sec_idx = sec_idx
                
                s_map.setdefault(sec_idx, {"notes": [], "bpm": active_bpm})
                s_map[sec_idx]["notes"].append([t, final_dir, float(n.get("l", 0))])
        
        # LOGICA DE SALIDA REESTRUCTURADA CODENAME -> PSYCH:
        # Generamos la lista de secciones rellenando vacíos secuenciales completos
        for idx in range(max_sec_idx + 1):
            sec_data = s_map.get(idx, {"notes": [], "bpm": bpm})
            ns = sec_data["notes"]
            sec_bpm = sec_data["bpm"]
            
            # Obtener el foco de la cámara estimado para esta sección basado en el tiempo medio
            section_ms_start = (idx * 4) * (60000.0 / sec_bpm) # Tiempo estimado de inicio de sección
            must_hit = True
            for cam in camera_timeline:
                if section_ms_start >= cam["time"]:
                    must_hit = (cam["char"] == 1)
                else:
                    break
            
            # Re-indexación de notas según la estructura requerida por mustHitSection de Psych Engine
            # Si mustHitSection es True, las notas de BF van de 4-7. Si es False, van de 0-3.
            formatted_notes = []
            for note in ns:
                nt_time = note[0]
                nt_dir = note[1]
                nt_len = note[2]
                
                # Conservamos el tipo de nota intacto basándonos en si originalmente era de jugador o no
                formatted_notes.append([nt_time, nt_dir, nt_len])
                
            f_notes.append({
                "sectionNotes": formatted_notes, 
                "typeOfSection": 0, 
                "sectionBeats": 4, 
                "altAnim": False, 
                "gfSection": False, 
                "mustHitSection": must_hit, 
                "changeBPM": True if idx == 0 or (idx > 0 and sec_bpm != f_notes[idx-1]["bpm"]) else False, 
                "bpm": sec_bpm
            })
            
    elif src == "Codename Engine":
        s_map = {}
        max_sec_idx = 0
        ms_sec = (60000 / bpm) * 4
        for sl in n_src:
            if isinstance(sl, dict):
                is_p = str(sl.get("type", "")).lower() == "player" or sl.get("type") == 1
                sk = "" if str(sl.get("arrowSkin", "")).lower() in ["", "default", "normal", "0", "null", "none"] else sl.get("arrowSkin", "")
                for n in sl.get("notes", []):
                    if isinstance(n, dict):
                        t, nt = float(n.get("time", n.get("t", 0))), n.get("type", "")
                        nt = sk if (not nt or str(nt).lower() in ["normal", "0", "false", "none", "0.0"]) and dest == "Psych 0.7.3" else ("" if str(nt).lower() in ["normal", "0", "false", "none", "0.0"] else nt)
                        s_idx = int(t // ms_sec)
                        if s_idx > max_sec_idx: max_sec_idx = s_idx
                        s_map.setdefault(s_idx, []).append({"t": t, "d": int(n.get("id", n.get("d", 0))) % 4, "l": float(n.get("sLen", n.get("l", 0))), "nt": nt, "is_p": is_p})
                        
        for idx in range(max_sec_idx + 1):
            r_notes = s_map.get(idx, [])
            ns = []
            for n in r_notes:
                if n["is_p"]: rd = n["d"] + 4
                else: rd = n["d"]
                ns.append([n["t"], rd, n["l"]] + ([str(n["nt"]).strip()] if str(n["nt"]).strip() else []))
            f_notes.append({"sectionNotes": ns, "typeOfSection": 0, "sectionBeats": 4, "altAnim": False, "gfSection": False, "mustHitSection": True, "changeBPM": False, "bpm": bpm})

    if not f_notes: f_notes.append({"sectionNotes": [], "typeOfSection": 0, "sectionBeats": 4, "altAnim": False, "gfSection": False, "mustHitSection": True, "changeBPM": False, "bpm": bpm})
    sd = {"song": sname, "bpm": bpm, "needsVoices": True, "speed": speed, "player1": p1, "player2": p2, "gfVersion": gf, "stage": stage, "notes": f_notes, "events": e_src, **ext}
    if dest == "Psych 1.0.4":
        sd["format"] = "psych_v1"
        if p1_sk: sd["playerSkin"] = p1_sk
        if p2_sk: sd["opponentSkin"] = p2_sk
    return {"song": sd}

class AdvancedConverterApp:
    def __init__(self, r):
        self.r = r
        r.title("FNF Universal Chart Adapter")
        r.geometry("540x510")
        r.configure(bg="#0b0a0f")
        c_cyan, c_pink, c_card = "#00ffcc", "#ff007f", "#14121f"
        
        tk.Label(r, text="CORE CHART ADAPTER", font=("Impact", 20), fg=c_cyan, bg="#0b0a0f").pack(pady=10)
        card = tk.Frame(r, bg=c_card, bd=1, relief="solid", highlightbackground=c_cyan, highlightthickness=1)
        card.pack(padx=20, pady=5, fill="both", expand=True)
        card.columnconfigure((0,1), weight=1)
        
        self.src_combo = ttk.Combobox(card, values=["Psych 1.0.4", "Psych 0.7.3", "Nightmare Vision", "V-Slice (v0.4.0+)", "Codename Engine"], state="readonly")
        self.src_combo.grid(row=0, column=1, pady=8, padx=10, sticky="ew")
        self.src_combo.current(0)
        self.src_combo.bind("<<ComboboxSelected>>", self.toggle_meta)
        
        self.dest_combo = ttk.Combobox(card, values=["Psych 0.7.3", "Psych 1.0.4"], state="readonly")
        self.dest_combo.grid(row=1, column=1, pady=8, padx=10, sticky="ew")
        self.dest_combo.current(0)
        
        tk.Label(card, text="ENGINE:", font=("Segoe UI", 9, "bold"), fg="#6c697e", bg=c_card).grid(row=0, column=0, padx=15, sticky="w")
        tk.Label(card, text="VERSION:", font=("Segoe UI", 9, "bold"), fg=c_pink, bg=c_card).grid(row=1, column=0, padx=15, sticky="w")
        
        self.lbl_stage = tk.Label(card, text="STAGE LUA:", font=("Segoe UI", 9, "bold"), fg=c_cyan, bg=c_card)
        self.ent_stage = tk.Entry(card, bg="#1d1b2e", fg="#ffffff", bd=1)
        self.c_file = self.m_file = ""
        
        self.btn_chart = tk.Button(card, text="CARGAR CHART (.JSON)", bg="#1d1b2e", fg=c_cyan, bd=0, height=2, command=self.load_chart)
        self.btn_chart.grid(row=3, column=0, columnspan=2, padx=15, pady=6, sticky="ew")
        
        self.btn_meta = tk.Button(card, text="REQUERIDO: METADATA", bg="#151421", fg="#6c697e", bd=0, height=2, state="disabled", command=self.load_meta)
        self.btn_meta.grid(row=4, column=0, columnspan=2, padx=15, pady=6, sticky="ew")
        
        tk.Button(r, text="ADAPTAR Y PROCESAR CHART", font=("Impact", 12), bg=c_pink, fg="#ffffff", bd=0, height=2, command=self.start_conv).pack(pady=10, padx=20, fill="x")
        self.status = tk.Label(r, text="[Sistema listo]", font=("Consolas", 9), fg="#6c697e", bg="#0b0a0f")
        self.status.pack()

    def toggle_meta(self, e=None):
        req = self.src_combo.get() in ["V-Slice (v0.4.0+)", "Codename Engine"]
        self.btn_meta.config(state="normal" if req else "disabled", bg="#1d1b2e" if req else "#151421", fg="#ff007f" if req else "#6c697e", text="CARGAR METADATA / META.JSON" if req else "REQUERIDO: METADATA")
        if req:
            self.lbl_stage.grid(row=2, column=0, padx=15, sticky="w")
            self.ent_stage.grid(row=2, column=1, pady=8, padx=10, sticky="ew")
        else:
            self.lbl_stage.grid_forget()
            self.ent_stage.grid_forget()
            self.m_file = ""

    def load_chart(self):
        self.c_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if self.c_file: self.btn_chart.config(text=f"CHART: {os.path.basename(self.c_file).upper()}", bg="#00ffcc", fg="#0b0a0f")

    def load_meta(self):
        self.m_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if self.m_file: self.btn_meta.config(text=f"META: {os.path.basename(self.m_file).upper()}", bg="#ff007f", fg="#ffffff")

    def start_conv(self):
        src, dest = self.src_combo.get(), self.dest_combo.get()
        if not self.c_file or (src in ["V-Slice (v0.4.0+)", "Codename Engine"] and not self.m_file):
            messagebox.showwarning("Error", "Faltan archivos.")
            return
        try:
            res = execute_conversion(src, dest, self.c_file, self.m_file or None, self.ent_stage.get())
            sfx = "-easy" if self.c_file.lower().endswith("-easy.json") else ("-hard" if self.c_file.lower().endswith("-hard.json") else "")
            title = "".join(c for c in str(res["song"]["song"]) if c.isalnum() or c in ' _-').strip()
            out = f"{title}{sfx}.json"
            save_json(os.path.join(os.path.dirname(self.c_file), out), res)
            self.status.config(text=f"[Guardado] {out}", fg="#00ffcc")
            messagebox.showinfo("Éxito", f"¡Convertido!\nArchivo: {out}")
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    tk_r = tk.Tk()
    AdvancedConverterApp(tk_r)
    tk_r.mainloop()
