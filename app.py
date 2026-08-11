from flask import Flask, jsonify, request, render_template
import json, os, random
from datetime import date, timedelta

import sys

# Cartella base: quando frozen (exe) usa _MEIPASS, altrimenti la cartella dello script
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    # dati.json vicino all'exe, non dentro _MEIPASS (che e' read-only)
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
DATA_FILE = os.path.join(DATA_DIR, "dati.json")

# ─────────────────────────────────────────────
#  Data helpers
# ─────────────────────────────────────────────

def date_from_dict(d):
    """Accetta sia {"giorno":8,"mese":8,"anno":2025} che [8, 8, 2025]"""
    if isinstance(d, (list, tuple)):
        return date(d[2], d[1], d[0])  # [giorno, mese, anno]
    return date(d["anno"], d["mese"], d["giorno"])

def dict_from_date(d):
    return {"giorno": d.day, "mese": d.month, "anno": d.year}

def overlaps(a_in, a_out, b_in, b_out):
    """True se i due intervalli si sovrappongono.
    Se out di A == in di B è un cambio camera nello stesso giorno: consentito."""
    return not (a_out <= b_in or b_out <= a_in)

def days_free_gap(reservations, cal_start, cal_end):
    """Conta quanti gap >= 5 giorni liberi ci sono in una camera."""
    if not reservations:
        return 1 if (cal_end - cal_start).days + 1 >= 5 else 0

    sorted_res = sorted(reservations, key=lambda r: date_from_dict(r["in"]))
    count = 0

    first_in = date_from_dict(sorted_res[0]["in"])
    if (first_in - cal_start).days >= 5:
        count += 1

    for i in range(len(sorted_res) - 1):
        cur_out = date_from_dict(sorted_res[i]["out"])
        nxt_in  = date_from_dict(sorted_res[i+1]["in"])
        gap = (nxt_in - cur_out).days - 1
        if gap >= 5:
            count += 1

    last_out = date_from_dict(sorted_res[-1]["out"])
    if (cal_end - last_out).days >= 5:
        count += 1

    return count

_Y = date.today().year
CAL_START = date(_Y, 5, 1)
CAL_END   = date(_Y, 9, 30)

# ─────────────────────────────────────────────
#  Greedy solver
# ─────────────────────────────────────────────

def can_assign(pren, camera, use_piano4):
    cap_key = {"bassa": "capLow", "media": "capMid", "alta": "capHigh"}.get(pren["capienza"], "capMid")
    cap = camera[cap_key]

    if pren.get("roomReq", -1) != -1 and pren["roomReq"] != camera["num"]:
        return False
    if pren.get("noMans") and camera["piano"] == 3:
        return False
    if pren.get("noPiano4") and camera["piano"] == 4:
        return False
    if pren["quantity"] > cap:
        return False
    if not use_piano4 and camera["piano"] == 4 and pren.get("roomReq", -1) != camera["num"]:
        return False

    p_in  = date_from_dict(pren["in"])
    p_out = date_from_dict(pren["out"])
    for r in camera["res"]:
        if overlaps(p_in, p_out, date_from_dict(r["in"]), date_from_dict(r["out"])):
            return False
    return True

def capacity_available(pren, camera):
    cap_key = {"bassa": "capLow", "media": "capMid", "alta": "capHigh"}.get(pren["capienza"], "capMid")
    cap = camera[cap_key]
    if pren.get("roomReq", -1) != -1 and pren["roomReq"] != camera["num"]:
        return 0
    if pren.get("noMans") and camera["piano"] == 3:
        return 0
    if pren.get("noPiano4") and camera["piano"] == 4:
        return 0
    p_in  = date_from_dict(pren["in"])
    p_out = date_from_dict(pren["out"])
    for r in camera["res"]:
        if overlaps(p_in, p_out, date_from_dict(r["in"]), date_from_dict(r["out"])):
            return 0
    return cap

def total_gaps(camere):
    return sum(days_free_gap(c["res"], CAL_START, CAL_END) for c in camere)

def _gia_piazzata(p, camere):
    """True se questa prenotazione risulta già presente in una camera."""
    p_in, p_out = p.get("in"), p.get("out")
    p_room = p.get("roomReq", -1)
    for c in camere:
        for r in c.get("res", []):
            if (r.get("nome") == p.get("nome") and
                    r.get("in") == p_in and
                    r.get("out") == p_out and
                    r.get("roomReq", -1) == p_room):
                return True
    return False

def solve_core(prenotazioni, camere, use_piano4, iterations=500):
    today = date.today()

    # Prenotazioni da (ri)assegnare: quelle future, oppure quelle passate
    # che però non risultano ancora piazzate in nessuna camera (es. mai
    # assegnate a causa di un bug precedente, o inserite manualmente nel json).
    future = [
        p for p in prenotazioni
        if date_from_dict(p["in"]) > today or not _gia_piazzata(p, camere)
    ]

    best_sol = None
    best_score = -1

    for _ in range(iterations):
        random.shuffle(future)

        # Copia camere mantenendo SOLO le prenotazioni già iniziate o passate (non toccabili)
        copy_camere = []
        for c in camere:
            nc = {k: v for k, v in c.items() if k != "res"}
            nc["res"] = [r for r in c["res"] if date_from_dict(r["in"]) <= today]
            copy_camere.append(nc)

        failed = False
        for pren in future:
            assigned = False

            if not pren.get("div", False):
                # Non divisibile: scegli camera che massimizza i gap
                best_cam = None
                best_local = -1
                for cam in copy_camere:
                    if can_assign(pren, cam, use_piano4):
                        cam["res"].append(pren)
                        g = days_free_gap(cam["res"], CAL_START, CAL_END)
                        if g > best_local:
                            best_local = g
                            best_cam = cam
                        cam["res"].pop()
                if best_cam is not None:
                    best_cam["res"].append(pren)
                    assigned = True
            else:
                # Divisibile: occupa il minor numero di camere possibile
                # Cerca prima se una singola camera basta
                remaining = pren["quantity"]
                partial = []

                # Prova a soddisfare tutto con una camera sola
                single_found = False
                for cam in copy_camere:
                    avail = capacity_available(pren, cam)
                    if avail >= remaining:
                        part = dict(pren)
                        part["quantity"] = remaining
                        cam["res"].append(part)
                        partial.append((cam, part))
                        remaining = 0
                        single_found = True
                        break

                if not single_found:
                    # Ordina per capacità disponibile decrescente → meno camere usate
                    cams_sorted = sorted(
                        copy_camere,
                        key=lambda c: capacity_available(pren, c),
                        reverse=True
                    )
                    for cam in cams_sorted:
                        if remaining <= 0:
                            break
                        avail = capacity_available(pren, cam)
                        if avail > 0:
                            take = min(remaining, avail)
                            part = dict(pren)
                            part["quantity"] = take
                            cam["res"].append(part)
                            partial.append((cam, part))
                            remaining -= take

                if remaining == 0:
                    assigned = True
                else:
                    # rollback
                    for cam, part in partial:
                        cam["res"].remove(part)

            if not assigned:
                failed = True
                break

        if failed:
            continue

        score = total_gaps(copy_camere)
        if score > best_score:
            best_score = score
            best_sol = copy_camere

    return best_sol

def solve(prenotazioni, camere):
    sol = solve_core(prenotazioni, camere, use_piano4=False)
    if sol is None:
        sol = solve_core(prenotazioni, camere, use_piano4=True)
    return sol

# ─────────────────────────────────────────────
#  JSON persistence
# ─────────────────────────────────────────────

def normalize_pren(p):
    for key in ("in", "out"):
        v = p.get(key)
        if isinstance(v, (list, tuple)):
            p[key] = {"giorno": v[0], "mese": v[1], "anno": v[2]}
    return p

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"camere": [], "prenotazioni": [], "prezzi": [
            {"id": 1, "nome": "Notte",           "prezzo": 80.0,  "unita": "per notte"},
            {"id": 2, "nome": "Caffè",           "prezzo": 1.5,   "unita": "cadauno"},
            {"id": 3, "nome": "Vino",            "prezzo": 12.0,  "unita": "bottiglia"},
            {"id": 4, "nome": "Acqua",           "prezzo": 2.0,   "unita": "bottiglia"}
        ]}
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for p in data.get("prenotazioni", []):
        normalize_pren(p)
    for c in data.get("camere", []):
        for r in c.get("res", []):
            normalize_pren(r)
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def get_data():
    return jsonify(load_data())

@app.route("/api/camere", methods=["POST"])
def add_camera():
    data = load_data()
    cam = request.json
    cam["res"] = []
    data["camere"].append(cam)
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/camere/<int:num>", methods=["DELETE"])
def delete_camera(num):
    data = load_data()
    data["camere"] = [c for c in data["camere"] if c["num"] != num]
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/camere/<int:num>", methods=["PUT"])
def edit_camera(num):
    data = load_data()
    upd = request.json
    for c in data["camere"]:
        if c["num"] == num:
            c["piano"]  = upd["piano"]
            c["capLow"] = upd["capLow"]
            c["capMid"] = upd["capMid"]
            c["capHigh"]= upd["capHigh"]
            break
    else:
        return jsonify({"ok": False, "error": "Camera non trovata"})
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/prenotazioni", methods=["POST"])
def add_prenotazione():
    data = load_data()
    pren = request.json
    data["prenotazioni"].append(pren)

    sol = solve(data["prenotazioni"], data["camere"])
    if sol is None:
        data["prenotazioni"].pop()
        return jsonify({"ok": False, "error": "Impossibile assegnare la prenotazione."})

    data["camere"] = sol
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/prenotazioni/<int:idx>", methods=["DELETE"])
def delete_prenotazione(idx):
    data = load_data()
    if idx < 0 or idx >= len(data["prenotazioni"]):
        return jsonify({"ok": False})
    data["prenotazioni"].pop(idx)

    # Ricalcola
    for c in data["camere"]:
        c["res"] = []
    sol = solve(data["prenotazioni"], data["camere"])
    if sol:
        data["camere"] = sol
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/prenotazioni/<int:idx>", methods=["PUT"])
def edit_prenotazione(idx):
    data = load_data()
    if idx < 0 or idx >= len(data["prenotazioni"]):
        return jsonify({"ok": False})

    old = data["prenotazioni"][idx]
    data["prenotazioni"][idx] = request.json

    sol = solve(data["prenotazioni"], data["camere"])
    if sol is None:
        data["prenotazioni"][idx] = old
        return jsonify({"ok": False, "error": "Modifica non valida."})

    data["camere"] = sol
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/ricalcola", methods=["POST"])
def ricalcola():
    data = load_data()
    for c in data["camere"]:
        c["res"] = []
    sol = solve(data["prenotazioni"], data["camere"])
    if sol:
        data["camere"] = sol
        save_data(data)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Ricalcolo fallito."})

@app.route("/api/prezzi", methods=["PUT"])
def update_prezzi():
    """Salva l intero array prezzi."""
    data = load_data()
    data["prezzi"] = request.json
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/prezzi", methods=["POST"])
def add_voce():
    data = load_data()
    prezzi = data.get("prezzi", [])
    voce = request.json
    # Genera id univoco
    next_id = max((v["id"] for v in prezzi), default=0) + 1
    voce["id"] = next_id
    prezzi.append(voce)
    data["prezzi"] = prezzi
    save_data(data)
    return jsonify({"ok": True, "id": next_id})

@app.route("/api/prezzi/<int:vid>", methods=["PUT"])
def edit_voce(vid):
    data = load_data()
    for v in data.get("prezzi", []):
        if v["id"] == vid:
            v.update(request.json)
            v["id"] = vid  # non sovrascrivere id
            save_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Voce non trovata"})

@app.route("/api/prezzi/<int:vid>", methods=["DELETE"])
def delete_voce(vid):
    data = load_data()
    data["prezzi"] = [v for v in data.get("prezzi", []) if v["id"] != vid]
    save_data(data)
    return jsonify({"ok": True})

if __name__ == "__main__":
    import threading, webbrowser

    # Apri il browser dopo mezzo secondo (tempo che Flask si avvii)
    threading.Timer(0.8, lambda: webbrowser.open("http://localhost:8000")).start()

    # Avvia Flask senza debug (necessario per PyInstaller)
    app.run(debug=False, port=8000)