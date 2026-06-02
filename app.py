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
        "enllaç_wp":    v("Enllaç_WP"),
        "destacada":    (v("Destacades") or "").strip().lower() in ("sí", "si", "yes", "1", "x"),
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

    # Rutes destacades (columna "Destacada" = Sí)
    destacades = [r for r in rutes if r.get("destacada")][:6]
    if not destacades:
        destacades = rutes[:3]  # fallback

    # Millors rutes temàtiques (primeres 4 col·leccions)
    grups = {}
    for r in rutes:
        cat = r.get("millors", "")
        if not cat: continue
        grups.setdefault(cat, []).append(r)
    colleccions = []
    for k, v_list in sorted(grups.items()):
        primera = v_list[0] if v_list else None
        foto = f"https://raw.githubusercontent.com/Senderismeentren/imatges/main/ruta-{str(primera['id']).zfill(3)}/foto1.jpg" if primera else ""
        colleccions.append({"nom": k, "n": len(v_list), "foto": foto, "url": f"/rutes?millors={k}"})
    colleccions = colleccions[:4]

    # Articles recents del WP
    articles_recents = []
    try:
        resp = requests.get("https://senderismeentren.cat/wp-json/wp/v2/posts",
            params={"categories": CAT_ARTICLES, "per_page": 3,
                    "_fields": "id,title,excerpt,date"},
            timeout=5)
        for a in resp.json():
            articles_recents.append({
                "id": a.get("id"),
                "titol": a.get("title", {}).get("rendered", ""),
                "extracte": a.get("excerpt", {}).get("rendered", ""),
                "data": a.get("date", "")[:10],
            })
    except Exception:
        pass

    # Stats
    estacions_uniques = set()
    for r in rutes:
        if r["sortida"]: estacions_uniques.add(r["sortida"])
        if r["arribada"]: estacions_uniques.add(r["arribada"])
    linies_uniques = set()
    for r in rutes:
        for l in r["linies_sortida"]: linies_uniques.add(l)
        for l in r["linies_arribada"]: linies_uniques.add(l)
    linies_uniques = {l for l in linies_uniques if l}
    total_km = sum(float(r["km"] or 0) for r in rutes)
    total_desn = sum(int(r["desn_p"] or 0) for r in rutes)
    stats = {
        "n_rutes": len(rutes),
        "n_cims": sum(1 for r in rutes if r["cims"]),
        "n_estacions": len(estacions_uniques),
        "n_linies": len(linies_uniques),
        "total_km": round(total_km),
        "total_desn": total_desn,
    }
    return render_template("inici.html",
        destacades=destacades,
        colleccions=colleccions,
        articles_recents=articles_recents,
        stats=stats)


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
    millors_filtre = request.args.get("millors", "")
    if millors_filtre: rutes = [r for r in rutes if r.get("millors") == millors_filtre]

    filtres_actius = {k: v for k, v in {
        "dificultat": dif, "comarca": comarca,
        "operador": operador, "espai": espai,
        "cims": cims,
        "estacio": estacio,
        "millors": millors_filtre or millors,
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


# Caché de GPX de línies (en memòria, es carrega un cop)
_cache_gpx_linies = {}

# ── ARTICLES ─────────────────────────────────────────────────────
WP_BASE = "https://senderismeentren.cat/wp-json/wp/v2"
CAT_ARTICLES = 208

@app.route("/articles")
def articles_pagina():
    """Llista d'articles del WP."""
    try:
        resp = requests.get(f"{WP_BASE}/posts",
            params={"categories": CAT_ARTICLES, "per_page": 20,
                    "_fields": "id,title,excerpt,date,slug,link"},
            timeout=8)
        articles = resp.json()
        if not isinstance(articles, list):
            articles = []
        for a in articles:
            a["titol"] = a.get("title", {}).get("rendered", "")
            a["extracte"] = a.get("excerpt", {}).get("rendered", "")
            a["data"] = a.get("date", "")[:10]
    except Exception:
        articles = []
    return render_template("llista_articles.html", articles=articles)

@app.route("/article/<int:post_id>")
def article_pagina(post_id):
    """Mostra un article del WP."""
    import re
    try:
        resp = requests.get(f"{WP_BASE}/posts/{post_id}",
            params={"_fields": "id,title,content,excerpt,date"},
            timeout=8)
        data = resp.json()
        titol = data.get("title", {}).get("rendered", "")
        contingut_html = data.get("content", {}).get("rendered", "")
        data_pub = data.get("date", "")[:10]

        # Netejar HTML: treure social links, spacers, però mantenir imatges
        contingut = re.sub(r'<ul[^>]*wp-block-social-links[^>]*>.*?</ul>', '', contingut_html, flags=re.DOTALL)
        contingut = re.sub(r'<div[^>]*wp-block-spacer[^>]*>.*?</div>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r' style="[^"]*color[^"]*"', '', contingut)
        contingut = contingut.strip()
    except Exception as e:
        titol = "Article no trobat"
        contingut = ""
        data_pub = ""
    return render_template("fitxa_article.html", titol=titol, contingut=contingut,
                           data_pub=data_pub, post_id=post_id)


@app.route("/api/resseny")
def api_resseny():
    """Llegeix el contingut d'un post de WP via la seva URL."""
    import re
    url_wp = request.args.get("url", "")
    if not url_wp:
        return jsonify({"error": "cal url"}), 400
    try:
        # Extreure l'ID de la URL (pot ser numèric o slug)
        import re as _re
        segment = url_wp.rstrip('/').split('/')[-1]
        if segment.isdigit():
            api_url = f"https://senderismeentren.cat/wp-json/wp/v2/posts/{segment}?_fields=title,content,excerpt"
        else:
            api_url = f"https://senderismeentren.cat/wp-json/wp/v2/posts?slug={segment}&_fields=title,content,excerpt"

        resp = requests.get(api_url, timeout=8)
        data = resp.json()

        # Si és llista, agafar el primer
        if isinstance(data, list):
            if not data:
                return jsonify({"error": "no trobat"}), 404
            data = data[0]

        titol = data.get("title", {}).get("rendered", "")
        contingut_html = data.get("content", {}).get("rendered", "")
        extracte = data.get("excerpt", {}).get("rendered", "")

        # Intentar extreure solo la secció "LA RESSENYA" si existeix
        # Busca el heading amb id="la-ressenya" o similar
        m_resseny = re.search(
            r'<h[2-5][^>]*id="la-ressenya"[^>]*>.*?</h[2-5]>(.*?)(?=<h[2-5]|$)',
            contingut_html, flags=re.DOTALL | re.IGNORECASE
        )
        if not m_resseny:
            m_resseny = re.search(
                r"<h[2-5][^>]*id='la-ressenya'[^>]*>.*?</h[2-5]>(.*?)(?=<h[2-5]|$)",
                contingut_html, flags=re.DOTALL | re.IGNORECASE
            )
        if m_resseny:
            contingut_html = m_resseny.group(1)

        # Netejar HTML: treure galeries, imatges, spacers, social links
        contingut = re.sub(r'<ul[^>]*wp-block-social-links[^>]*>.*?</ul>', '', contingut_html, flags=re.DOTALL)
        contingut = re.sub(r'<ol[^>]*wp-block-table-of-contents[^>]*>.*?</ol>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r'<div[^>]*tiled-gallery[^>]*>.*?</div>\s*</div>\s*</div>\s*</div>\s*</div>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r'<div[^>]*wp-block-image[^>]*>.*?</div>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r'<div[^>]*wp-block-spacer[^>]*>.*?</div>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r'<figure[^>]*>.*?</figure>', '', contingut, flags=re.DOTALL)
        contingut = re.sub(r'<img[^>]*>', '', contingut)
        contingut = re.sub(r' style="[^"]*"', '', contingut)
        contingut = re.sub("\n{3,}", "\n\n", contingut)
        contingut = contingut.strip()

        return jsonify({
            "titol": titol,
            "contingut": contingut,
            "extracte": extracte,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gpx/linia/<nom_linia>")
def api_gpx_linia(nom_linia):
    """Serveix el GPX d'una línia de tren des de GitHub amb caché."""
    import re
    if not re.match(r'[a-zA-Z0-9._-]+', nom_linia):
        return jsonify({"error": "nom invàlid"}), 400

    # Retornar des de caché si ja existeix
    if nom_linia in _cache_gpx_linies:
        return jsonify(_cache_gpx_linies[nom_linia])

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
            for route in gpx.routes:
                for p in route.points:
                    punts.append({"lat": round(p.latitude,6), "lng": round(p.longitude,6)})
        # Simplificar punts per reduir mida (cada 3 punts)
        if len(punts) > 500:
            punts = punts[::3]
        _cache_gpx_linies[nom_linia] = punts
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


@app.route("/api/horaris/<path:id_estacio>")
def api_horaris(id_estacio):
    """Horaris en temps real FGC (per nom estació) i Rodalies (per ID numèric)."""
    from datetime import datetime
    ara = datetime.now()

    try:
        # ── FGC ──────────────────────────────────────────────────────
        if not id_estacio.isdigit():
            # Hora local catalana (UTC+2 estiu, UTC+1 hivern)
            import zoneinfo
            tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")
            ara_cat = datetime.now(tz_cat)
            hora_actual = ara_cat.strftime("%H:%M:%S")
            base = "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records"
            nom_estacio = id_estacio.replace("_", " ")
            # Normalitzar accents per compatibilitat amb l'API FGC
            _acc = {'à':'a','è':'e','é':'e','í':'i','ï':'i','ó':'o','ò':'o','ú':'u','ü':'u','ç':'c','À':'A','È':'E','É':'E','Í':'I','Ï':'I','Ó':'O','Ò':'O','Ú':'U','Ü':'U','·':''}
            nom_api = ''.join(_acc.get(c, c) for c in nom_estacio)
            # Carregar tots els trens d'avui i filtrar per hora en Python
            params = {
                "where": f"stop_name='{nom_api}'",
                "order_by": "departure_time ASC",
                "limit": "100",
                "select": "departure_time,route_short_name,trip_headsign",
            }
            resp = requests.get(base, params=params, timeout=8)
            data = resp.json()
            # Filtrar per hora actual en Python (evita problemes de format a l'API)
            results_filtrats = [
                r for r in data.get("results", [])
                if r.get("departure_time", "") >= hora_actual
            ]
            data["results"] = results_filtrats

            horaris = []
            vists = set()
            for rec in data.get("results", []):
                hora = rec.get("departure_time", "")[:5]
                linia = rec.get("route_short_name", "")
                dest = rec.get("trip_headsign", "")
                clau = f"{hora}_{linia}_{dest}"
                if hora and linia and clau not in vists:
                    vists.add(clau)
                    horaris.append({
                        "hora": hora,
                        "linia": linia,
                        "destinacio": dest,
                        "retard": 0,
                        "ara": False
                    })
            return jsonify({"horaris": horaris[:8], "operador": "FGC"})

        # ── RODALIES via eltrennofunca.cat ───────────────────────────
        rodalies_key = os.environ.get("RODALIES_API_KEY", "")
        url = f"https://eltrennofunca.cat/api/horaris/station/{id_estacio}"
        headers_etf = {"X-API-Key": rodalies_key} if rodalies_key else {}
        resp = requests.get(url, headers=headers_etf, timeout=6)
        data = resp.json()
        horaris = []
        vists = set()
        for entry in data.get("entries", []):
            hora = entry.get("theoreticalDeparture", "")[:5]
            hora_est = entry.get("estimatedDeparture", "")[:5]
            linia = entry.get("lineId", "")
            # headsign és la destinació concreta; si és null, usem la segona part del lineName
            headsign = entry.get("headsign")
            line_name = entry.get("lineName", "")
            if headsign:
                dest = headsign
            elif " - " in line_name:
                # Ex: "Sant Vicenç - Maçanet-Massanes" -> agafem la part correcta
                # segons la direcció del tren (no ho sabem, mostrem les dues parts)
                dest = line_name
            else:
                dest = line_name
            retard = int(entry.get("currentDelay", 0) or 0)
            clau = f"{hora}_{linia}_{dest}"
            if hora and linia and clau not in vists:
                vists.add(clau)
                horaris.append({
                    "hora": hora_est or hora,
                    "linia": linia,
                    "destinacio": dest,
                    "retard": retard,
                    "ara": False
                })
        return jsonify({"horaris": horaris[:8], "operador": "Rodalies"})

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
