"""
Senderisme en Tren — Flask app
"""
import os
import json
import math
import requests
import gpxpy
import pandas as pd
import gspread
from flask import Flask, render_template, jsonify, request, abort
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import time

app = Flask(__name__)

# ── CONFIGURACIÓ ────────────────────────────────────────────────────
SHEET_ID        = os.environ.get("SHEET_ID", "")
GOOGLE_CREDS    = os.environ.get("GOOGLE_CREDS", "")   # JSON de credencials
BASE_FOTO_URL   = "https://raw.githubusercontent.com/Senderismeentren/imatges/main/ruta-{id:03d}/foto{n}.jpg"
BASE_GPX_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
BASE_LOGO_URL   = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
MAX_FOTOS       = 9
CACHE_TTL       = 1800   # 30 min

# ── COLORS DIFICULTAT ───────────────────────────────────────────────
COLORS_DIF = {
    "molt fàcil":  "#2ECC71", "molt facil":  "#2ECC71",
    "fàcil":       "#3498DB", "facil":       "#3498DB",
    "moderada":    "#E67E22",
    "exigent":     "#E74C3C",
    "molt exigent":"#111111",
}

def color_dif(dif):
    if not dif: return "#888888"
    return COLORS_DIF.get(str(dif).strip().lower(), "#888888")

# ── COLORS OPERADOR ─────────────────────────────────────────────────
COLORS_OP = {
    "rodalies":      "#EE7F00",
    "fgc":           "#97D700",
    "metro":         "#E30613",
    "tram":          "#78BE20",
    "alta velocitat":"#8B0000",
    "cremallera":    "#C8A96E",
    "sncf":          "#C00000",
}

def color_op(op):
    if not op: return "#EE7F00"
    op_l = str(op).strip().lower()
    for k, v in COLORS_OP.items():
        if k in op_l: return v
    return "#EE7F00"

# ── CÀRREGA DE DADES ────────────────────────────────────────────────
_cache_dades = {"dades": None, "ts": 0}

def carregar_dades():
    """Carrega les dades del Google Sheet amb cache de 30 min."""
    ara = time.time()
    if _cache_dades["dades"] is not None and ara - _cache_dades["ts"] < CACHE_TTL:
        return _cache_dades["dades"]

    try:
        if GOOGLE_CREDS and SHEET_ID:
            # Suporta tant JSON pur com format TOML de Streamlit
            raw = GOOGLE_CREDS.strip()
            if raw.startswith("{"):
                # Format JSON directe
                creds_dict = json.loads(raw)
            else:
                # Format TOML de Streamlit: extreure clau=valor
                import re
                creds_dict = {}
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith("["):
                        continue
                    m = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
                    if m:
                        key, val = m.group(1), m.group(2)
                        # Restaurar salts de línia de la private_key
                        creds_dict[key] = val.replace("\\n", "\n")
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://spreadsheets.google.com/feeds",
                        "https://www.googleapis.com/auth/drive"]
            )
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.get_worksheet(0)
            df = pd.DataFrame(ws.get_all_records())
        else:
            # Fallback local per a desenvolupament
            df = pd.read_excel("SET_excel_app.xlsx")
    except Exception as e:
        print(f"Error carregant dades: {e}")
        df = pd.DataFrame()

    _cache_dades["dades"] = df
    _cache_dades["ts"] = ara
    return df


def ruta_a_dict(row):
    """Converteix una fila del DataFrame a diccionari net per a les plantilles."""
    def v(camp):
        val = row.get(camp, "")
        if pd.isna(val) if hasattr(pd, 'isna') else val != val:
            return ""
        return str(val).strip() if val is not None else ""

    def vf(camp):
        try: return float(row.get(camp, 0) or 0)
        except: return 0.0

    num = v("Núm_Ruta")
    try: ruta_id = int(float(num))
    except: ruta_id = 0

    tipus = v("Tipus_ruta").lower()
    desn_p = vf("desnivell_positiu")
    desn_n = vf("desnivell_negatiu")
    if "circular" in tipus:
        desn_txt = f"+/- {int(desn_p)} m"
    else:
        desn_txt = f"+{int(desn_p)} m / -{int(desn_n)} m"

    temps_fmt = ""
    try:
        hd = float(str(v("Durada_estimada")).replace(",", "."))
        h, mn = int(hd), round((hd - int(hd)) * 60)
        if h > 0 and mn > 0: temps_fmt = f"{h}h{mn:02d}min"
        elif h > 0: temps_fmt = f"{h}h"
        else: temps_fmt = f"{mn}min"
    except: pass

    dif = v("Dificultat")
    senders = [s.strip() for s in v("Senders").split(";") if s.strip()]

    # Ordenar senders: GR → PR → SL → altres
    def ordre_sender(s):
        su = s.upper()
        if su.startswith("GR"): return (0, su)
        if su.startswith("PR"): return (1, su)
        if su.startswith("SL"): return (2, su)
        return (3, su)
    senders = sorted(senders, key=ordre_sender)

    elements = [e.strip() for e in v("Elements_interès").split(";") if e.strip()]
    cats_el  = [c.strip() for c in v("Categories_elements_interès").split(";") if c.strip()]
    punts_interes = list(zip(elements, cats_el + [""]*(len(elements)-len(cats_el))))

    return {
        "id":           ruta_id,
        "codi":         f"ST{ruta_id:03d}",
        "nom":          v("Nom_ruta"),
        "wiki":         v("Enllaç_Wikiloc"),
        "sortida":      v("Estació_sortida"),
        "op_sortida":   v("Operador_sortida"),
        "id_sortida":   v("ID_estació_sortida"),
        "lat_sortida":  vf("Lat_sortida"),
        "lng_sortida":  vf("Lon_sortida"),
        "linies_sortida": [l.strip() for l in v("Linies_sortida").split(";") if l.strip()],
        "muni_sortida": v("Municipi_sortida"),
        "comarca_sortida": v("Comarca_sortida"),
        "arribada":     v("Estació_arribada"),
        "op_arribada":  v("Operador_arribada"),
        "id_arribada":  v("ID_estació_arribada"),
        "lat_arribada": vf("Lat_arribada"),
        "lng_arribada": vf("Lon_arribada"),
        "linies_arribada": [l.strip() for l in v("Linies_Arribada").split(";") if l.strip()],
        "muni_arribada":v("Municipi_arribada"),
        "comarca_arribada": v("Comarca_arribada"),
        "km":           v("km"),
        "desn_txt":     desn_txt,
        "desn_p":       int(desn_p),
        "desn_n":       int(desn_n),
        "tipus":        v("Tipus_ruta"),
        "dificultat":   dif,
        "color_dif":    color_dif(dif),
        "color_op_s":   color_op(v("Operador_sortida")),
        "color_op_a":   color_op(v("Operador_arribada")),
        "temps":        temps_fmt,
        "epoca":        v("Millor_època"),
        "punt_alt":     v("Punt_mes_alt"),
        "alcada_alt":   int(vf("Alçada_punt_alt")),
        "cims":         v("100cims").lower() in ("si", "sí", "yes", "1", "true"),
        "nom_cim":      v("Nom_100cims"),
        "lat_cim":      vf("Lat_100cims"),
        "lng_cim":      vf("Lon_100cims"),
        "senders":      senders,
        "espai":        v("Espai_natural"),
        "punts_interes": punts_interes,
        "millors":      v("Millors_rutes"),
        "descripcio":   v("Descripció_ruta"),
        "advertiments": v("Advertiments"),
    }


def get_rutes():
    """Retorna totes les rutes com a llista de dicts."""
    df = carregar_dades()
    if df.empty: return []
    rutes = []
    for _, row in df.iterrows():
        try:
            r = ruta_a_dict(row.to_dict())
            if r["id"] > 0:
                rutes.append(r)
        except Exception as e:
            print(f"Error processant ruta: {e}")
    return sorted(rutes, key=lambda x: x["id"])


# ── FOTOS ────────────────────────────────────────────────────────────
_cache_fotos = {}

def obtenir_fotos(ruta_id):
    if ruta_id in _cache_fotos:
        return _cache_fotos[ruta_id]
    fotos = []
    for n in range(1, MAX_FOTOS + 1):
        url = BASE_FOTO_URL.format(id=ruta_id, n=n)
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                fotos.append(url)
            else:
                break
        except:
            break
    _cache_fotos[ruta_id] = fotos
    return fotos


# ── GPX ─────────────────────────────────────────────────────────────
_cache_gpx = {}

def obtenir_gpx(ruta_id):
    if ruta_id in _cache_gpx:
        return _cache_gpx[ruta_id]
    url = BASE_GPX_URL.format(id=ruta_id)
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            _cache_gpx[ruta_id] = None
            return None
        gpx = gpxpy.parse(r.text)
        punts = []
        for track in gpx.tracks:
            for segment in track.segments:
                for p in segment.points:
                    punts.append({
                        "lat": round(p.latitude, 6),
                        "lng": round(p.longitude, 6),
                        "ele": round(p.elevation or 0, 1)
                    })
        _cache_gpx[ruta_id] = punts
        return punts
    except Exception as e:
        print(f"Error GPX {ruta_id}: {e}")
        _cache_gpx[ruta_id] = None
        return None


def gpx_a_perfil(punts):
    """Calcula distància acumulada i elevació per al perfil d'altitud."""
    if not punts: return [], []
    dists, eles = [0], [punts[0]["ele"]]
    for i in range(1, len(punts)):
        p1, p2 = punts[i-1], punts[i]
        # Distància aproximada en km (Haversine simplificat)
        dlat = math.radians(p2["lat"] - p1["lat"])
        dlng = math.radians(p2["lng"] - p1["lng"])
        a = math.sin(dlat/2)**2 + math.cos(math.radians(p1["lat"])) * math.cos(math.radians(p2["lat"])) * math.sin(dlng/2)**2
        d = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        dists.append(round(dists[-1] + d, 3))
        eles.append(punts[i]["ele"])
    # Simplificar a màxim 200 punts
    if len(dists) > 200:
        step = len(dists) // 200
        dists = dists[::step]
        eles = eles[::step]
    return dists, eles


# ── ESTACIONS (agregades de les rutes) ──────────────────────────────
def get_estacions():
    rutes = get_rutes()
    estacions = {}
    for r in rutes:
        for camp in [("sortida","op_sortida","lat_sortida","lng_sortida","linies_sortida","color_op_s"),
                     ("arribada","op_arribada","lat_arribada","lng_arribada","linies_arribada","color_op_a")]:
            nom = r[camp[0]]
            if not nom: continue
            if nom not in estacions:
                estacions[nom] = {
                    "nom": nom,
                    "op": r[camp[1]],
                    "lat": r[camp[2]],
                    "lng": r[camp[3]],
                    "linies": r[camp[4]],
                    "color": r[camp[5]],
                    "rutes": []
                }
            if r["id"] not in [x["id"] for x in estacions[nom]["rutes"]]:
                estacions[nom]["rutes"].append({"id": r["id"], "nom": r["nom"]})
    return estacions


# ── FILTRES DISPONIBLES ─────────────────────────────────────────────
def get_filtres(rutes):
    dificultats = sorted(set(r["dificultat"] for r in rutes if r["dificultat"]))
    comarques = sorted(set(
        c for r in rutes
        for c in [r["comarca_sortida"], r["comarca_arribada"]] if c
    ))
    operadors = sorted(set(
        op for r in rutes
        for op in [r["op_sortida"], r["op_arribada"]] if op
    ))
    espais = sorted(set(r["espai"] for r in rutes if r["espai"]))
    millors = sorted(set(r["millors"] for r in rutes if r["millors"]))
    return {
        "dificultats": dificultats,
        "comarques": comarques,
        "operadors": operadors,
        "espais": espais,
        "millors": millors,
    }


# ══════════════════════════════════════════════════════════════════════
# RUTES FLASK (URLs)
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def inici():
    rutes = get_rutes()
    # Rutes destacades: les primeres 3 amb fotos
    destacades = rutes[:3]
    stats = {
        "n_rutes": len(rutes),
        "n_cims": sum(1 for r in rutes if r["cims"]),
    }
    return render_template("inici.html", destacades=destacades, stats=stats)


@app.route("/rutes")
def rutes_pagina():
    rutes = get_rutes()
    filtres = get_filtres(rutes)

    # Aplicar filtres de la URL
    dif     = request.args.get("dificultat", "")
    comarca = request.args.get("comarca", "")
    operador= request.args.get("operador", "")
    espai   = request.args.get("espai", "")
    cims    = request.args.get("cims", "")
    millors = request.args.get("millors", "")

    estacio = request.args.get("estacio", "")

    rutes_all_list = get_rutes()
    if dif:     rutes = [r for r in rutes if r["dificultat"] == dif]
    if comarca: rutes = [r for r in rutes if comarca in [r["comarca_sortida"], r["comarca_arribada"]]]
    if operador:rutes = [r for r in rutes if operador in [r["op_sortida"], r["op_arribada"]]]
    if espai:   rutes = [r for r in rutes if r["espai"] == espai]
    if cims:    rutes = [r for r in rutes if r["cims"]]
    if millors: rutes = [r for r in rutes if r["millors"] == millors]
    if estacio: rutes = [r for r in rutes if estacio in [r["sortida"], r["arribada"]]]

    filtres_actius = {k: v for k, v in {
        "dificultat": dif, "comarca": comarca,
        "operador": operador, "espai": espai,
        "cims": cims, "millors": millors,
        "estacio": estacio,
    }.items() if v}

    # Afegir estacions al diccionari de filtres
    filtres["estacions"] = sorted(set(
        est for r in rutes_all_list
        for est in [r["sortida"], r["arribada"]] if est
    ))

    return render_template("rutes.html",
        rutes=rutes,
        rutes_all=rutes_all_list,
        filtres=filtres,
        filtres_actius=filtres_actius,
        n_total=len(rutes_all_list)
    )


@app.route("/ruta/<int:ruta_id>")
def fitxa_ruta(ruta_id):
    rutes = get_rutes()
    ruta = next((r for r in rutes if r["id"] == ruta_id), None)
    if not ruta: abort(404)

    fotos = obtenir_fotos(ruta_id)
    gpx_punts = obtenir_gpx(ruta_id)
    dists, eles = gpx_a_perfil(gpx_punts) if gpx_punts else ([], [])

    return render_template("fitxa.html",
        ruta=ruta,
        fotos=fotos,
        gpx_punts=json.dumps(gpx_punts or []),
        perfil_dists=json.dumps(dists),
        perfil_eles=json.dumps(eles),
    )


@app.route("/mapa")
def mapa_pagina():
    rutes = get_rutes()
    estacions = get_estacions()
    # Només rutes amb coordenades
    rutes_mapa = [r for r in rutes if r["lat_sortida"] and r["lng_sortida"]]
    # Agrupar estacions per operador per al sidebar
    estacions_list = list(estacions.values())
    estacions_per_op = {}
    for est in sorted(estacions_list, key=lambda x: (x["op"] or "", x["nom"])):
        op = est["op"] or "Altres"
        estacions_per_op.setdefault(op, []).append(est)

    return render_template("mapa.html",
        rutes=rutes_mapa,
        estacions=estacions_list,
        estacions_per_op=estacions_per_op,
    )


@app.route("/millors_rutes")
def millors_rutes_pagina():
    rutes = get_rutes()
    # Agrupar per categoria Millors_rutes
    grups = {}
    for r in rutes:
        cat = r["millors"]
        if not cat: continue
        grups.setdefault(cat, []).append(r)
    grups = dict(sorted(grups.items()))
    return render_template("millors_rutes.html", grups=grups)


# ── APIs JSON ────────────────────────────────────────────────────────

@app.route("/api/rutes")
def api_rutes():
    """API JSON per al mapa i filtres dinàmics."""
    rutes = get_rutes()
    # Camps mínims per al mapa
    return jsonify([{
        "id": r["id"],
        "nom": r["nom"],
        "dificultat": r["dificultat"],
        "color_dif": r["color_dif"],
        "km": r["km"],
        "desn_txt": r["desn_txt"],
        "temps": r["temps"],
        "cims": r["cims"],
        "lat_s": r["lat_sortida"],
        "lng_s": r["lng_sortida"],
        "lat_a": r["lat_arribada"],
        "lng_a": r["lng_arribada"],
        "comarca": r["comarca_sortida"],
        "espai": r["espai"],
    } for r in rutes])


@app.route("/api/gpx/linia/<nom_linia>")
def api_gpx_linia(nom_linia):
    """Serveix el GPX d'una línia de tren des de GitHub (evita CORS)."""
    import re
    if not re.match(r'[a-zA-Z0-9._-]+', nom_linia):
        return jsonify({"error": "nom invàlid"}), 400
    url = f"https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx-linies/{nom_linia}.gpx"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return jsonify({"error": "no trobat"}), 404
        gpx = gpxpy.parse(resp.text)
        punts = []
        for track in gpx.tracks:
            for segment in track.segments:
                for p in segment.points:
                    punts.append({"lat": round(p.latitude,6), "lng": round(p.longitude,6)})
        if not punts:
            # Intentar amb routes
            for route in gpx.routes:
                for p in route.points:
                    punts.append({"lat": round(p.latitude,6), "lng": round(p.longitude,6)})
        return jsonify(punts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gpx/<int:ruta_id>")
def api_gpx(ruta_id):
    """Retorna el track GPX com a JSON per al mapa."""
    punts = obtenir_gpx(ruta_id)
    if punts is None:
        return jsonify({"error": "GPX no disponible"}), 404
    return jsonify(punts)


@app.route("/api/estacio/<nom_estacio>")
def api_estacio(nom_estacio):
    """Rutes d'una estació concreta."""
    rutes = get_rutes()
    rutes_est = [r for r in rutes if nom_estacio in [r["sortida"], r["arribada"]]]
    return jsonify([{
        "id": r["id"], "nom": r["nom"],
        "dificultat": r["dificultat"], "color_dif": r["color_dif"],
        "km": r["km"], "temps": r["temps"],
    } for r in rutes_est])


@app.route("/api/horaris/<id_estacio>")
def api_horaris(id_estacio):
    """Horaris en temps real. Detecta operador pel prefix de l'ID."""
    from datetime import datetime
    ara = datetime.now()

    try:
        # ── FGC ──────────────────────────────────────────────────────
        # IDs FGC comencen per lletra (ex: "BC", "SB", "VL"...)
        if not id_estacio.isdigit():
            from datetime import datetime
            hora_actual = datetime.now().strftime("%H:%M:%S")
            url = (
                f"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/"
                f"viajes-de-hoy/records?"
                f"where=stop_id like '{id_estacio}%25'"
                f" and departure_time >= '{hora_actual}'"
                f"&order_by=departure_time ASC"
                f"&limit=6"
                f"&select=departure_time,route_short_name,trip_headsign"
            )
            resp = requests.get(url, timeout=5)
            data = resp.json()
            horaris = []
            for rec in data.get("results", []):
                hora = rec.get("departure_time", "")[:5]
                linia = rec.get("route_short_name", "")
                dest = rec.get("trip_headsign", "")
                if hora and linia:
                    horaris.append({
                        "hora": hora,
                        "linia": linia,
                        "destinacio": dest,
                        "retard": 0,
                        "ara": False
                    })
            return jsonify({"horaris": horaris, "operador": "FGC"})

        # ── RODALIES ─────────────────────────────────────────────────
        # IDs Rodalies són numèrics
        url = (
            f"https://rodalies.gencat.cat/es/horaris/salida.json"
            f"?estacioOrigen={id_estacio}"
            f"&hora={ara.strftime('%H')}"
            f"&minuts={ara.strftime('%M')}"
        )
        resp = requests.get(url, timeout=5)
        data = resp.json()
        horaris = []
        for t in data.get("trens", [])[:6]:
            hora = t.get("hora", "")
            linia = t.get("linia", "")
            dest = t.get("destinacio", "")
            retard = int(t.get("retard", 0))
            horaris.append({
                "hora": hora,
                "linia": linia,
                "destinacio": dest,
                "retard": retard,
                "ara": False
            })
        return jsonify({"horaris": horaris, "operador": "Rodalies"})

    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


# ── ERROR HANDLERS ───────────────────────────────────────────────────
@app.errorhandler(404)
def pagina_no_trobada(e):
    return render_template("404.html"), 404


# ── CONTEXT PROCESSORS (variables globals a totes les plantilles) ────
@app.context_processor
def globals_plantilles():
    return {
        "nom_app": "Senderisme en tren",
        "seccions": [
            {"id": "rutes",      "nom": "Rutes",        "icon": "🥾", "url": "/rutes"},
            {"id": "mapa",       "nom": "Mapa",         "icon": "🗺️", "url": "/mapa"},
            {"id": "colleccions","nom": "Millors rutes",  "icon": "⭐", "url": "/millors_rutes"},
            {"id": "articles",   "nom": "Articles",     "icon": "📖", "url": "/articles"},
        ]
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)
