import os, json, re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f: return json.load(f)

def clean_bpm(val):
    try:
        f_val = float(val)
        return int(f_val) if f_val.is_integer() else f_val
    except (ValueError, TypeError):
        return val

def minify_json_output(obj):
    raw = json.dumps(obj, ensure_ascii=False, indent="\t")
    compacted = re.sub(r'\[\s+([\d\.\-]+),\s+([\d\.\-]+),\s+([\d\.\-]+)(?:\s*,\s*\"([^\"]*)\")?\s+\]', 
                       lambda m: f"[{m.group(1)}, {m.group(2)}, {m.group(3)}" + (f', "{m.group(4)}"' if m.group(4) else "") + "]", raw)
    return re.sub(r'\[\s+(\d+(?:\.\d+)?),\s+\[\s+\[\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"\s*\]\s*\]\s*\]',
                  lambda m: f'[{m.group(1)}, [["{m.group(2)}", "{m.group(3)}", "{m.group(4)}"]]]', compacted)

def execute_conversion(src, dest, c_path, m_path=None, c_stage=""):
    cd, md = load_json(c_path), load_json(m_path) if m_path else None
    sname, bpm, speed, p1, p2, gf, stage = "Untitled", 150, 1.0, "bf", "dad", "gf", "stage"
    n_src, e_src_raw, ext = [], [], {}
    
    cam_filters = ["focuscamera", "camera focus", "heycamera", "bpm change", "change bpm"]
    INVERTIR_MAPEO = True

    # Lista para capturar los cortes de cámara explícitos de Codename
    camera_timeline = []

    if src in ["Psych 1.0.4", "Psych 0.7.3", "Nightmare Vision"]:
        s = cd.get("song", cd) if isinstance(cd, dict) else {}
        sname = s.get("song", "Untitled")
        bpm, speed = clean_bpm(s.get("bpm", bpm)), s.get("speed", speed)
        p1, p2, gf, stage = s.get("player1", p1), s.get("player2", p2), s.get("gfVersion", gf), s.get("stage", stage)
        n_src, e_src_raw = s.get("notes", []), s.get("events", [])
        ext = {k: v for k, v in s.items() if k not in ["song", "bpm", "speed", "player1", "player2", "gfVersion", "stage", "notes", "events", "format"]}

    elif src == "V-Slice (v0.4.0+)":
        if not md: raise ValueError("Falta metadata.")
        sname = md.get("songName", "Untitled")
        if md.get("timeChanges"): bpm = clean_bpm(md["timeChanges"][0].get("bpm", 150))
        chars = md.get("playData", {}).get("characters", {})
        p1, p2, gf, stage = chars.get("player", "bf"), chars.get("opponent", "dad"), chars.get("girlfriend", "gf"), md.get("playData", {}).get("stage", "stage")
        
        if isinstance(cd, dict):
            sc = cd.get("scrollSpeed", 1.0)
            speed = list(sc.values())[0] if isinstance(sc, dict) and sc else float(sc)
            raw_notes = cd.get("notes", [])
            n_src = raw_notes.get(md.get("playData", {}).get("difficulties", ["hard"])[0], list(raw_notes.values())[0] if raw_notes else []) if isinstance(raw_notes, dict) else raw_notes

    elif src == "Codename Engine":
        if not md: raise ValueError("Falta meta.json.")
        sname, bpm = md.get("displayName", md.get("name", "Untitled")), clean_bpm(md.get("bpm", 150))
        stage = cd.get("stage", "stage") if isinstance(cd, dict) else "stage"
        
        codename_bpm_changes = [{"time": 0.0, "bpm": float(bpm)}]
        
        if isinstance(cd, dict):
            speed = cd.get("scrollSpeed", 1.0)
            strum_roles, strum_char_names = {}, {}
            
            for i, sl in enumerate(cd.get("strumLines", [])):
                chars = sl.get("characters", [])
                char_name = str(chars[0]).strip() if (isinstance(chars, list) and chars) else (str(chars).strip() if chars else "")
                pos, stype = str(sl.get("position", "")).lower(), sl.get("type")
                strum_char_names[i] = char_name if (char_name and not char_name.isdigit()) else ""
                
                if pos == "boyfriend" or stype == 1: 
                    strum_roles[i] = "player"
                    p1 = char_name or p1
                elif pos == "girlfriend" or stype == 2: 
                    strum_roles[i] = "gf"
                    gf = char_name or gf
                else: 
                    if "opponent" not in strum_roles.values():
                        strum_roles[i] = "opponent"
                        p2 = char_name or p2
                    else:
                        strum_roles[i] = "extra"

            for ev in cd.get("events", []):
                e_name = ev.get("name", "Event")
                ev_time = float(ev.get("time", ev.get("t", 0)))
                params = ev.get("params", [])
                p_str = [str(p).lower() if isinstance(p, bool) else str(p) for p in params]

                if e_name in ["BPM Change", "Change BPM"] and p_str:
                    try: codename_bpm_changes.append({"time": ev_time, "bpm": float(p_str[0])})
                    except ValueError: pass
                    continue

                if e_name.lower() in cam_filters: continue

                # MANEJO DEL EVENTO DE CÁMARA ORIGINAL DE CODENAME
                if e_name.lower() == "camera movement" and params:
                    cam_target = str(params[0]).strip()
                    # "0" significa enemigo/dad, "1" significa player/bf
                    is_bf_cam = cam_target.startswith("1")
                    camera_timeline.append({"time": ev_time, "mustHit": is_bf_cam})
                    continue # No lo inyectamos como un evento visual de Psych porque va directo a las secciones

                v1 = ({"0": "dad", "1": "bf", "2": "gf"}.get(str(params[0]).strip(), str(params[0]).strip()) if len(params) >= 1 else "") if (e_name in ["Change Character", "Character Change"]) else (",".join(p_str[:(len(p_str) + 1) // 2]))
                v2 = str(params[1]) if (e_name in ["Change Character", "Character Change"] and len(params) >= 2) else (",".join(p_str[(len(p_str) + 1) // 2:]))

                found = False
                for ex in e_src_raw:
                    if ex[0] == ev_time: ex[1].append([e_name, v1, v2]); found = True; break
                if not found: e_src_raw.append([ev_time, [[e_name, v1, v2]]])
            
            codename_bpm_changes.sort(key=lambda x: x["time"])
            camera_timeline.sort(key=lambda x: x["time"])
            n_src = cd.get("strumLines", [])

    e_src = []
    for ev in e_src_raw:
        ev_time = float(ev[0])
        valid_subs = [sub for sub in ev[1] if isinstance(sub, list) and len(sub) >= 1 and sub[0].lower() not in cam_filters] if len(ev) >= 2 and isinstance(ev[1], list) else []
        if valid_subs:
            found = False
            for ex in e_src:
                if abs(ex[0] - ev_time) < 0.01:
                    for s in valid_subs:
                        if s not in ex[1]: ex[1].append(s)
                    found = True; break
            if not found: e_src.append([ev_time, valid_subs])

    if c_stage and c_stage.strip(): stage = c_stage.strip()
    f_notes = []

    if src in ["Psych 1.0.4", "Psych 0.7.3", "Nightmare Vision"]:
        last_section_bpm = clean_bpm(bpm)
        for i, sec in enumerate(n_src):
            if not isinstance(sec, dict): continue
            h = sec.get("mustHitSection", True)
            ns = []
            sec_bpm = clean_bpm(sec.get("bpm", bpm))
            for n in sec.get("sectionNotes", []):
                if isinstance(n, list) and len(n) >= 3:
                    r_dir = int(n[1])
                    is_player = (r_dir >= 4) if h else (r_dir < 4)
                    if INVERTIR_MAPEO: is_player = not is_player
                    
                    nt_type = str(n[3]).strip() if (len(n) >= 4 and n[3] and str(n[3]).strip().lower() not in ["", "null", "none"]) else ""
                    nst = [float(n[0]), (r_dir % 4) + 4 if is_player else (r_dir % 4), float(n[2])]
                    if nt_type: nst.append(nt_type)
                    if nst not in ns: ns.append(nst)
            
            p_count = sum(1 for sn in ns if sn[1] >= 4)
            if ns: final_must_hit = p_count < (len(ns) - p_count) if INVERTIR_MAPEO else p_count > (len(ns) - p_count)
            else: final_must_hit = not h if INVERTIR_MAPEO else h
                
            has_changed = (i == 0) or (sec_bpm != last_section_bpm) or sec.get("changeBPM", False)
            f_notes.append({"sectionNotes": ns, "sectionBeats": 4, "lengthInSteps": 16, "mustHitSection": final_must_hit, "bpm": sec_bpm, "changeBPM": has_changed, "altAnim": sec.get("altAnim", False), "gfSection": sec.get("gfSection", False)})
            last_section_bpm = sec_bpm
            
    elif src in ["V-Slice (v0.4.0+)", "Codename Engine"]:
        temp_notes = []
        timeline = md.get("timeChanges", [{"t": 0, "bpm": bpm}]) if src == "V-Slice (v0.4.0+)" else [{"t": c["time"], "bpm": c["bpm"]} for c in codename_bpm_changes]
        timeline = [{"t": float(x.get("t", x.get("time", 0))), "bpm": float(x["bpm"])} for x in timeline]
        timeline.sort(key=lambda x: x["t"])

        if src == "V-Slice (v0.4.0+)":
            for n in n_src:
                if isinstance(n, dict):
                    is_bf = str(n.get("k", "")).lower().strip() in ["player", "1"]
                    n_type = str(n.get("type", "")).strip()
                    temp_notes.append([float(n.get("t", 0)), int(n.get("d", 0)) % 4, not is_bf if INVERTIR_MAPEO else is_bf, float(n.get("l", 0)), "" if n_type.lower() in ["null", "none"] else n_type])
        else:
            for s_idx, sl in enumerate(n_src):
                role, c_name = strum_roles.get(s_idx, "opponent"), strum_char_names.get(s_idx, "")
                for n in sl.get("notes", []):
                    f_type = str(n.get("type", "")).strip()
                    if f_type.isdigit() or f_type.lower() in ["", "null", "none"]: f_type = ""

                    # CORRECCIÓN DE NOTAS EXTRA / GF: Forzar siempre al carril del oponente
                    if role == "extra":
                        is_bf_n = False
                        if not f_type: f_type = c_name
                    elif role == "gf" or c_name.lower() in ["gf", "girlfriend"]:
                        is_bf_n = False
                        f_type = "GF Sing"
                    elif role == "player":
                        is_bf_n = True
                    else:
                        is_bf_n = False

                    final_is_bf = not is_bf_n if INVERTIR_MAPEO else is_bf_n

                    temp_notes.append([
                        float(n.get("time", n.get("t", 0))), 
                        int(n.get("id", n.get("d", 0))) % 4, 
                        final_is_bf, 
                        float(n.get("sLen", n.get("l", 0))), 
                        f_type
                    ])

        unique_notes = []
        for tn in temp_notes:
            if tn not in unique_notes: unique_notes.append(tn)
        unique_notes.sort(key=lambda x: x[0])

        current_time, note_ptr, last_bpm = 0.0, 0, None
        total_max_time = unique_notes[-1][0] + 500 if unique_notes else 5000.0
        last_camera = True
        
        while current_time < total_max_time:
            active_bpm = timeline[0]["bpm"]
            for ch in timeline:
                if current_time >= ch["t"] - 0.01: active_bpm = ch["bpm"]
                else: break
            
            next_sec_time = current_time + ((60000.0 / active_bpm) * 4.0)
            sec_ns = []
            
            while note_ptr < len(unique_notes) and unique_notes[note_ptr][0] < next_sec_time - 0.01:
                n = unique_notes[note_ptr]
                f_dir = n[1] + 4 if n[2] else n[1]
                
                # Forzar visualmente el carril izquierdo si es nota especial de GF
                if n[4] == "GF Sing": f_dir = n[1]
                
                nst = [n[0], f_dir, n[3]]
                if n[4]: nst.append(n[4])
                if nst not in sec_ns: sec_ns.append(nst)
                note_ptr += 1
            
            # CORRECCIÓN DE CÁMARA MAESTRA: Sincronizar con los eventos leídos en camera_timeline
            if src == "Codename Engine" and camera_timeline:
                # Buscar el estado de cámara más reciente para esta sección específica
                current_cam_state = last_camera
                for cam_ev in camera_timeline:
                    if current_time >= cam_ev["time"] - 10.0:
                        current_cam_state = cam_ev["mustHit"]
                    else:
                        break
                final_must_hit = current_cam_state
            else:
                p_count = sum(1 for sn in sec_ns if sn[1] >= 4)
                if sec_ns: final_must_hit = p_count < (len(sec_ns) - p_count) if INVERTIR_MAPEO else p_count > (len(sec_ns) - p_count)
                else: final_must_hit = last_camera
                
            c_bpm_clean = clean_bpm(active_bpm)
            trigger_change = (last_bpm is None) or (c_bpm_clean != last_bpm)

            f_notes.append({
                "sectionNotes": sec_ns, "sectionBeats": 4, "lengthInSteps": 16,
                "mustHitSection": final_must_hit,
                "bpm": c_bpm_clean, "changeBPM": trigger_change,
                "altAnim": False, "gfSection": False
            })
            last_bpm = c_bpm_clean
            last_camera = final_must_hit
            current_time = next_sec_time

    if not f_notes: f_notes.append({"sectionNotes": [], "sectionBeats": 4, "lengthInSteps": 16, "mustHitSection": True, "bpm": clean_bpm(bpm), "changeBPM": False, "altAnim": False, "gfSection": False})
    
    song_data = {"song": sname, "bpm": clean_bpm(bpm), "needsVoices": True, "speed": speed, "player1": p1, "player2": p2, "gfVersion": gf, "stage": stage, "notes": f_notes, "events": e_src}
    if dest == "Psych 1.0.4": song_data["format"] = "psych_v1"
    for k, v in ext.items(): song_data.setdefault(k, v)
    return song_data if dest == "Psych 0.7.3" else {"song": song_data}

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
        
        self.lbl_stage, self.ent_stage = tk.Label(card, text="STAGE LUA:", font=("Segoe UI", 9, "bold"), fg=c_cyan, bg=c_card), tk.Entry(card, bg="#1d1b2e", fg="#ffffff", bd=1)
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
            self.lbl_stage.grid(row=2, column=0, padx=15, sticky="w"); self.ent_stage.grid(row=2, column=1, pady=8, padx=10, sticky="ew")
        else:
            self.lbl_stage.grid_forget(); self.ent_stage.grid_forget(); self.m_file = ""

    def load_chart(self):
        self.c_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if self.c_file: self.btn_chart.config(text=f"CHART: {os.path.basename(self.c_file).upper()}", bg="#00ffcc", fg="#0b0a0f")

    def load_meta(self):
        self.m_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if self.m_file: self.btn_meta.config(text=f"META: {os.path.basename(self.m_file).upper()}", bg="#ff007f", fg="#ffffff")

    def start_conv(self):
        src, dest = self.src_combo.get(), self.dest_combo.get()
        if not self.c_file or (src in ["V-Slice (v0.4.0+)", "Codename Engine"] and not self.m_file):
            messagebox.showwarning("Error", "Faltan archivos."); return
        try:
            res = execute_conversion(src, dest, self.c_file, self.m_file or None, self.ent_stage.get())
            sfx = "-easy" if self.c_file.lower().endswith("-easy.json") else ("-hard" if self.c_file.lower().endswith("-hard.json") else "")
            t_dict = res["song"] if "song" in res and isinstance(res["song"], dict) else res
            out = f"{''.join(c for c in str(t_dict.get('song', 'Untitled')) if c.isalnum() or c in ' _-').strip()}{sfx}.json"
            
            with open(os.path.join(os.path.dirname(self.c_file), out), 'w', encoding='utf-8') as f: f.write(minify_json_output(res))
            self.status.config(text=f"[Guardado] {out}", fg="#00ffcc")
            messagebox.showinfo("Éxito", f"¡Convertido!\nCámaras corregidas vía mustHitSection. Notas de GF/Extras mapeadas al carril izquierdo.")
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    tk_r = tk.Tk()
    AdvancedConverterApp(tk_r)
    tk_r.mainloop()
