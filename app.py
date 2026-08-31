"""
Senderisme en Tren — Flask app
"""
import os
import random
import threading
import json
import math
import requests
import gpxpy
import pandas as pd
import gspread
from flask import Flask, render_template, jsonify, request, abort, Response
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import time
import html as h
import re
import zipfile
import io

app = Flask(__name__)

# ── CONFIGURACIÓ ────────────────────────────────────────────────────
SHEET_ID        = os.environ.get("SHEET_ID", "")
GOOGLE_CREDS    = os.environ.get("GOOGLE_CREDS", "")   # JSON de credencials
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "")   # per pujar el límit de l'API de 60/h a 5.000/h
TMB_APP_ID      = os.environ.get("TMB_APP_ID", "")
TMB_APP_KEY     = os.environ.get("TMB_APP_KEY", "")
BASE_FOTO_URL   = "https://raw.githubusercontent.com/Senderismeentren/imatges/main/ruta-{id:03d}/foto{n}.jpg"
BASE_GPX_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx-rutes/ruta-{id:03d}.gpx"
BASE_LOGO_OPERADOR_URL = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logos-operadors/logo-{operador}.svg"
BASE_LOGO_LINIA_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logos-linies/logo-{operador}-{linia}.svg"
MAX_FOTOS       = 40
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


def _sense_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ── TIPUS DE PUNT D'INTERÈS (detecció automàtica per paraula clau) ──
# Cada categoria és una llista de paraules (sense accents, minúscules) que,
# si apareixen en qualsevol posició del títol d'un Punt_interès o Element_ferroviari,
# el classifiquen dins d'aquell tipus. És una detecció aproximada, no exacta.
TIPUS_PUNT_INTERES = {
    "Santuari":            ["santuari"],
    "Monestir":            ["monestir", "cenobi"],
    "Ermita":              ["ermita", "capella"],
    "Convent":             ["convent"],
    "Castell":             ["castell"],
    "Torre":               ["torre", "talaia"],
    "Jaciment ibèric":     ["iberic", "poblat iber"],
    "Jaciment arqueològic":["jaciment"],
    "Patrimoni megalític": ["dolmen", "menhir", "cromlec", "necropolis megalitica"],
    "Túnel ferroviari":    ["tunel"],
    "Pont":                ["pont", "viaducte", "aqueducte"],
    "Patrimoni militar":   ["bunquer", "casamata", "niu de metralladora", "linia p", "fortificacio"],
    "Coves i mines":       ["cova", "coves", "mina", "avenc"],
    "Molí":                ["moli"],
    "Masia":               ["masia", "mas "],
    "Refugi":              ["refugi"],
    "Estany":              ["estany", "llac", "gorg"],
    "Cascada":             ["cascada", "salt d'aigua", "salt de"],
    "Far":                 ["far "],
    "Vil·la romana":       ["vil.la romana", "villa romana", "roma"],
}

# ── COLORS OPERADOR ─────────────────────────────────────────────────
COLORS_OP = {
    "rodalies":      "#EE7F00",
    "fgc":           "#97D700",
    "fgv":           "#F58220",
    "bsm":           "#8E44AD",
    "metro":         "#E30613",
    "tram":          "#78BE20",
    "alta velocitat":"#8B0000",
    "tav":           "#8B0000",
    "cercanias":     "#C1121F",
    "media distancia":"#6A4C93",
    "md":            "#6A4C93",
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
_avisats_fallback = set()

def _obtenir_sheet():
    """Retorna l'spreadsheet obert (gspread), o None si falla. Reutilitzat
    per operacions puntuals (com incrementar un comptador) fora del cicle
    normal de carregar_dades()."""
    try:
        if not (GOOGLE_CREDS and SHEET_ID):
            return None
        raw = GOOGLE_CREDS.strip()
        if raw.startswith("{"):
            creds_dict = json.loads(raw)
        else:
            import re
            creds_dict = {}
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("["):
                    continue
                m = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
                if m:
                    key, val = m.group(1), m.group(2)
                    creds_dict[key] = val.replace("\\n", "\n")
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive"]
        )
        gc_local = gspread.authorize(creds)
        return gc_local.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"[sheet] Error obrint spreadsheet: {repr(e)}")
        return None


def _incrementar_descarrega(format_nom):
    """Suma 1 al comptador d'aquest format a la pestanya Descàrregues.
    S'executa en un fil a part perquè mai retardi ni trenqui la descàrrega
    en si, encara que Sheets falli o vagi lent."""
    def _fer():
        try:
            sh = _obtenir_sheet()
            if not sh:
                return
            ws = sh.worksheet("Descàrregues")
            valors = ws.get_all_values()
            for i, fila in enumerate(valors[1:], start=2):
                if fila and fila[0].strip().lower() == format_nom.lower():
                    actual = int(fila[1]) if len(fila) > 1 and str(fila[1]).strip().isdigit() else 0
                    ws.update_cell(i, 2, actual + 1)
                    break
        except Exception as e:
            print(f"[descarregues] Error incrementant {format_nom}: {repr(e)}")
    threading.Thread(target=_fer, daemon=True).start()


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
            # Carregar pestanya Senders
            try:
                ws_senders = sh.worksheet("Senders")
                _cache_dades["senders_url"] = {
                    row["Senders"]: row["Enllaç_senders"]
                    for row in ws_senders.get_all_records()
                    if row.get("Senders") and row.get("Enllaç_senders")
                }
            except Exception as e:
                print(f"Error carregant Senders: {e}")
                _cache_dades["senders_url"] = {}
            # Carregar pestanya Estacions (dades úniques per estació)
            try:
                ws_est = sh.worksheet("Estacions")
                estacions_info = {}
                for erow in ws_est.get_all_records():
                    nom = str(erow.get("Nom_estació", "")).strip()
                    if not nom:
                        continue
                    def parse_llista(val):
                        return [x.strip() for x in str(val or "").split(";") if x.strip()]
                    def parse_float(val):
                        try: return float(str(val).strip())
                        except: return 0.0
                    estacions_info[nom] = {
                        "op": str(erow.get("Operador_sortida", "")).strip(),
                        "op2": str(erow.get("Operador2_sortida", "")).strip(),
                        "linies": parse_llista(erow.get("Linies_sortida", "")),
                        "linies2": parse_llista(erow.get("Linies2_sortida", "")),
                        "id": str(erow.get("ID_estació_sortida", "")).strip(),
                        "lat": parse_float(erow.get("Lat_sortida", "")),
                        "lng": parse_float(erow.get("Lon_sortida", "")),
                        "municipi": str(erow.get("Municipi_sortida", "")).strip(),
                        "comarca": str(erow.get("Comarca_sortida", "")).strip(),
                        "meteocat": str(erow.get("Enllaç_Meteocat", "")).strip(),
                        "meteofrance": str(erow.get("Enllaç_Meteofrance", "")).strip(),
                        "avamet": str(erow.get("Enllaç_Avamet", "")).strip(),
                        "aemet": str(erow.get("Enllaç_Aemet", "")).strip(),
                    }
                _cache_dades["estacions_info"] = estacions_info
            except Exception as e:
                print(f"Error carregant Estacions: {e}")
                _cache_dades["estacions_info"] = {}
            # Carregar pestanya Articles (URL triades manualment, evita la consulta massiva per categoria)
            try:
                ws_articles = sh.worksheet("Articles")
                import unicodedata
                def _sense_accents(s):
                    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
                urls_articles = []
                for arow in ws_articles.get_all_records():
                    url_art = str(arow.get("Enllaç_article", "")).strip()
                    publicat = _sense_accents(str(arow.get("Publicat", "")).strip().lower())
                    if url_art and publicat == "si":
                        urls_articles.append(url_art)
                _cache_dades["articles_urls"] = urls_articles
            except Exception as e:
                print(f"Error carregant Articles: {e}")
                _cache_dades["articles_urls"] = []
            # Carregar pestanya 100cims (dades úniques per cim)
            try:
                ws_cims = sh.worksheet("100cims")
                cims_info = {}
                for crow in ws_cims.get_all_records():
                    nom = str(crow.get("Nom_100cims", "")).strip()
                    if not nom:
                        continue
                    def parse_float_c(val):
                        try: return float(str(val).strip())
                        except: return 0.0
                    cims_info[nom] = {
                        "categoria": str(crow.get("Categoria", "")).strip(),
                        "alcada": str(crow.get("Alçada", "")).strip(),
                        "comarca": str(crow.get("Comarca", "")).strip(),
                        "lat": parse_float_c(crow.get("Lat_100cims", "")),
                        "lng": parse_float_c(crow.get("Lon_100cims", "")),
                    }
                _cache_dades["cims_info"] = cims_info
            except Exception as e:
                print(f"Error carregant 100cims: {e}")
                _cache_dades["cims_info"] = {}
            # Carregar pestanya 522cims (llistat complet del repte "100 Cims" de la FEEC)
            try:
                ws_cims522 = sh.worksheet("522cims")
                valors = ws_cims522.get_all_values()
                capcalera = valors[0] if valors else []
                def _idx_col(nom):
                    try: return capcalera.index(nom)
                    except ValueError: return None
                i_nom = _idx_col("Nom_100cims")
                i_alcada = _idx_col("Alçada")
                i_comarca = _idx_col("Comarca")
                i_categoria = _idx_col("Categoria")
                i_lat = _idx_col("Lat_100cims")
                i_lon = _idx_col("Lon_100cims")
                def _cel(fila, i):
                    return fila[i] if (i is not None and i < len(fila)) else ""
                def parse_float_522(val):
                    try: return float(str(val).strip())
                    except Exception: return None
                cims522 = []
                for fila in valors[1:]:
                    nom = _cel(fila, i_nom).strip()
                    if not nom:
                        continue
                    cims522.append({
                        "nom": nom,
                        "alcada": parse_float_522(_cel(fila, i_alcada)),
                        "comarca": _cel(fila, i_comarca).strip(),
                        "essencial": _cel(fila, i_categoria).strip().lower() == "essencial",
                        "lat": parse_float_522(_cel(fila, i_lat)),
                        "lng": parse_float_522(_cel(fila, i_lon)),
                    })
                _cache_dades["cims522"] = cims522
            except Exception as e:
                print(f"Error carregant 522cims: {e}")
                _cache_dades["cims522"] = []
            # Carregar pestanya Descàrregues (comptadors GPX/KML/Excel dels 522 cims)
            try:
                ws_desc = sh.worksheet("Descàrregues")
                descarregues = {}
                for fila in ws_desc.get_all_values()[1:]:
                    if fila and fila[0].strip():
                        try:
                            descarregues[fila[0].strip()] = int(fila[1]) if len(fila) > 1 and str(fila[1]).strip().isdigit() else 0
                        except Exception:
                            descarregues[fila[0].strip()] = 0
                _cache_dades["descarregues"] = descarregues
            except Exception as e:
                print(f"Error carregant Descàrregues: {e}")
                _cache_dades["descarregues"] = {}
        else:
            # Fallback local per a desenvolupament
            df = pd.read_excel("SET_excel_app.xlsx")
            _cache_dades["senders_url"] = {}
            _cache_dades["estacions_info"] = {}
            _cache_dades["cims_info"] = {}
            _cache_dades["articles_urls"] = []
            _cache_dades["cims522"] = []
            _cache_dades["descarregues"] = {}
    except Exception as e:
        print(f"Error carregant dades: {e}")
        df = pd.DataFrame()
        _cache_dades["senders_url"] = {}
        _cache_dades["estacions_info"] = {}
        _cache_dades["cims_info"] = {}
        _cache_dades["articles_urls"] = []
        _cache_dades["cims522"] = []
        _cache_dades["descarregues"] = {}

    _cache_dades["dades"] = df
    _avisats_fallback.clear()
    _cache_dades["ts"] = ara
    return df


def _resol_cims_camp(noms_cim_str, camp, vf_fallback=""):
    """Per a un o més cims (separats per ';'), retorna el valor demanat
    (lat/lng/categoria/alcada) de la pestanya 100cims, o el fallback si no es troba."""
    if not noms_cim_str:
        return ""
    cims_info = _cache_dades.get("cims_info") or {}
    noms = [n.strip() for n in str(noms_cim_str).split(";") if n.strip()]
    fallbacks = [f.strip() for f in str(vf_fallback).split(";")] if vf_fallback else []
    resultats = []
    for i, nom in enumerate(noms):
        info = cims_info.get(nom)
        if info is not None and info.get(camp) not in (None, ""):
            resultats.append(str(info[camp]))
        elif i < len(fallbacks) and fallbacks[i]:
            resultats.append(fallbacks[i])
            if nom not in _avisats_fallback:
                print(f"[100cims] FALLBACK a Rutes per al cim: '{nom}' (no trobat a la pestanya 100cims)")
                _avisats_fallback.add(nom)
        else:
            resultats.append("")
    return ";".join(resultats)


def _detall_cims(noms_cim_str):
    """Retorna una llista de dicts {nom, alcada, categoria} per a cada cim d'una ruta,
    llegint de la pestanya 100cims. Facilita mostrar-ho a les plantilles."""
    if not noms_cim_str:
        return []
    cims_info = _cache_dades.get("cims_info") or {}
    noms = [n.strip() for n in str(noms_cim_str).split(";") if n.strip()]
    detall = []
    for nom in noms:
        info = cims_info.get(nom, {})
        detall.append({
            "nom": nom,
            "alcada": info.get("alcada", ""),
            "categoria": info.get("categoria", ""),
        })
    return detall


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

    # Dades d'estació: prioritat a la pestanya "Estacions"; si no hi és, fallback a les columnes de Rutes
    estacions_info = _cache_dades.get("estacions_info") or {}
    nom_sortida_v = v("Estació_sortida")
    nom_arribada_v = v("Estació_arribada")
    info_s = estacions_info.get(nom_sortida_v, {})
    info_a = estacions_info.get(nom_arribada_v, {})
    if nom_sortida_v and not info_s and nom_sortida_v not in _avisats_fallback:
        print(f"[Estacions] FALLBACK a Rutes per a l'estació de sortida: '{nom_sortida_v}' (no trobada a la pestanya Estacions)")
        _avisats_fallback.add(nom_sortida_v)
    if nom_arribada_v and not info_a and nom_arribada_v not in _avisats_fallback:
        print(f"[Estacions] FALLBACK a Rutes per a l'estació d'arribada: '{nom_arribada_v}' (no trobada a la pestanya Estacions)")
        _avisats_fallback.add(nom_arribada_v)

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
        "op_sortida":   info_s.get("op") or v("Operador_sortida"),
        "op2_sortida":  info_s.get("op2") or v("Operador2_sortida"),
        "id_sortida":   info_s.get("id") or v("ID_estació_sortida"),
        "enllaç_wp":    v("Enllaç_WP"),
        "destacada":    (v("Destacades") or "").strip().lower() in ("sí", "si", "yes", "1", "x"),
        "punt_interes":  v("Punt_interès") or v("Punt_interes") or "",
        "element_ferroviari": v("Element_ferroviari") or "",
        "lat_sortida":  info_s.get("lat") or vf("Lat_sortida"),
        "lng_sortida":  info_s.get("lng") or vf("Lon_sortida"),
        "linies_sortida": info_s.get("linies") or [l.strip() for l in v("Linies_sortida").split(";") if l.strip()],
        "linies2_sortida": info_s.get("linies2") or [l.strip() for l in v("Linies2_sortida").split(";") if l.strip()],
        "muni_sortida": info_s.get("municipi") or v("Municipi_sortida"),
        "comarca_sortida": info_s.get("comarca") or v("Comarca_sortida"),
        "arribada":     v("Estació_arribada"),
        "op_arribada":  info_a.get("op") or v("Operador_arribada"),
        "op2_arribada": info_a.get("op2") or v("Operador2_arribada"),
        "id_arribada":  info_a.get("id") or v("ID_estació_arribada"),
        "lat_arribada": info_a.get("lat") or vf("Lat_arribada"),
        "lng_arribada": info_a.get("lng") or vf("Lon_arribada"),
        "linies_arribada": info_a.get("linies") or [l.strip() for l in v("Linies_Arribada").split(";") if l.strip()],
        "linies2_arribada": info_a.get("linies2") or [l.strip() for l in v("Linies2_Arribada").split(";") if l.strip()],
        "muni_arribada":info_a.get("municipi") or v("Municipi_arribada"),
        "comarca_arribada": info_a.get("comarca") or v("Comarca_arribada"),
        "km":           v("km"),
        "desn_txt":     desn_txt,
        "desn_p":       int(desn_p),
        "desn_n":       int(desn_n),
        "tipus":        v("Tipus_ruta"),
        "dificultat":   dif,
        "color_dif":    color_dif(dif),
        "color_op_s":   color_op(info_s.get("op") or v("Operador_sortida")),
        "color_op_a":   color_op(info_a.get("op") or v("Operador_arribada")),
        "temps":        temps_fmt,
        "epoca":        v("Millor_època"),
        "punt_alt":     v("Punt_mes_alt"),
        "alcada_alt":   int(vf("Alçada_punt_alt")),
        "cims":         v("100cims").lower() in ("si", "sí", "yes", "1", "true"),
        "nom_cim":      v("Nom_100cims"),
        "lat_cim":      _resol_cims_camp(v("Nom_100cims"), "lat", vf_fallback=v("Lat_100cims")),
        "lng_cim":      _resol_cims_camp(v("Nom_100cims"), "lng", vf_fallback=v("Lon_100cims")),
        "categoria_cim": _resol_cims_camp(v("Nom_100cims"), "categoria", vf_fallback=""),
        "alcada_cim":   _resol_cims_camp(v("Nom_100cims"), "alcada", vf_fallback=""),
        "cims_detall":  _detall_cims(v("Nom_100cims")),
        "senders":      senders,
        "espai":        [e.strip() for e in v("Espai_natural").split(";") if e.strip()],
        "punts_interes": punts_interes,
        "millors":      v("Millors_rutes"),
        "descripcio":   v("Descripció_ruta"),
        "advertiments": v("Advertiments"),
        "enllaç_meteocat": str(info_s.get("meteocat") or v("Enllaç_Meteocat")).zfill(6) if (info_s.get("meteocat") or v("Enllaç_Meteocat")) else "",
        "enllaç_meteofrance": (
            str(int(float(info_s.get("meteofrance")))).zfill(6) if info_s.get("meteofrance")
            else (str(int(float(v("Enllaç_Meteofrance")))).zfill(6) if v("Enllaç_Meteofrance") else "")
        ),
        "enllaç_aemet": info_s.get("aemet") or v("Enllaç_Aemet"),
        "enllaç_avamet": info_s.get("avamet") or v("Enllaç_Avamet"),
    }


def get_avis():
    """Llegeix l'avís de la cel·la AP2 del Sheets."""
    try:
        dades = _cache_dades.get("dades")
        if dades is None or dades.empty:
            return ""
        # AP és la columna 42 (0-indexed), fila 0 (primera fila de dades = AP2 al Sheets)
        if "Avís" in dades.columns:
            val = dades["Avís"].iloc[0] if len(dades) > 0 else ""
            return str(val).strip() if val and str(val) != "nan" else ""
        # Provar sense accent
        if "Avis" in dades.columns:
            val = dades["Avis"].iloc[0] if len(dades) > 0 else ""
            return str(val).strip() if val and str(val) != "nan" else ""
    except Exception:
        pass
    return ""


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
    return sorted(rutes, key=lambda x: x["id"], reverse=True)


# ── FOTOS ────────────────────────────────────────────────────────────
_cache_fotos = {}

def obtenir_fotos(ruta_id):
    """Llista les fotos reals d'una ruta amb una sola crida a l'API de GitHub
    (en lloc de provar foto1.jpg, foto1.JPG, foto2.jpg... una a una)."""
    if ruta_id in _cache_fotos:
        return _cache_fotos[ruta_id]
    fotos = []
    try:
        api_url = f"https://api.github.com/repos/Senderismeentren/imatges/contents/ruta-{ruta_id:03d}"
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        r = requests.get(api_url, timeout=6, headers=headers)
        if r.status_code == 200:
            arxius = r.json()
            candidats = []
            for a in arxius:
                nom = a.get("name", "")
                m = re.match(r'foto(\d+)\.(jpg|jpeg|png)$', nom, re.IGNORECASE)
                if m:
                    candidats.append((int(m.group(1)), a.get("download_url") or ""))
            candidats.sort(key=lambda x: x[0])
            fotos = [url for _, url in candidats if url][:MAX_FOTOS]
        elif r.status_code == 404:
            fotos = []  # la ruta no té carpeta de fotos
        else:
            print(f"[fotos] Resposta inesperada de GitHub per ruta-{ruta_id:03d}: status {r.status_code}")
            return []  # error temporal (p. ex. 403 per rate limit): no cachejar, es reintentarà
    except Exception as e:
        print(f"[fotos] Error llistant fotos de ruta-{ruta_id:03d}: {repr(e)}")
        return []  # error temporal: no cachejar, es reintentarà
    _cache_fotos[ruta_id] = fotos
    return fotos


# ── GPX ─────────────────────────────────────────────────────────────
_cache_gpx = {}

def obtenir_gpx(ruta_id):
    ara = time.time()
    if ruta_id in _cache_gpx:
        punts, ts = _cache_gpx[ruta_id]
        if ara - ts < CACHE_TTL:
            return punts
    url = BASE_GPX_URL.format(id=ruta_id)
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            _cache_gpx[ruta_id] = (None, ara)
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
        _cache_gpx[ruta_id] = (punts, ara)
        return punts
    except Exception as e:
        print(f"Error GPX {ruta_id}: {e}")
        # Si ja teníem una versió vàlida en cache, la mantenim (millor mostrar
        # dades una mica antigues que res); si no, no cachegem l'error.
        if ruta_id in _cache_gpx and _cache_gpx[ruta_id][0] is not None:
            return _cache_gpx[ruta_id][0]
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
        for camp in [("sortida","op_sortida","op2_sortida","lat_sortida","lng_sortida","linies_sortida","linies2_sortida","color_op_s"),
                     ("arribada","op_arribada","op2_arribada","lat_arribada","lng_arribada","linies_arribada","linies2_arribada","color_op_a")]:
            nom = r[camp[0]]
            if not nom: continue
            if nom not in estacions:
                estacions[nom] = {
                    "nom": nom,
                    "op": r[camp[1]],
                    "op2": r[camp[2]],
                    "lat": r[camp[3]],
                    "lng": r[camp[4]],
                    "linies": list(r[camp[5]]),
                    "linies2": list(r[camp[6]]),
                    "color": r[camp[7]],
                    "te_cims": False,
                    "rutes": []
                }
            else:
                # Acumular linies i linies2 de totes les rutes
                est = estacions[nom]
                for l in r[camp[5]]:
                    if l and l not in est["linies"]:
                        est["linies"].append(l)
                for l in r[camp[6]]:
                    if l and l not in est["linies2"]:
                        est["linies2"].append(l)
                # Actualitzar op2 si no en tenia
                if not est["op2"] and r[camp[2]]:
                    est["op2"] = r[camp[2]]
            if r["id"] not in [x["id"] for x in estacions[nom]["rutes"]]:
                estacions[nom]["rutes"].append({"id": r["id"], "nom": r["nom"]})
            if r.get("cims"):
                estacions[nom]["te_cims"] = True
    return estacions


# ── FILTRES DISPONIBLES ─────────────────────────────────────────────

# Assignació de comarques a província, agrupades per comunitat
COMUNITATS_PROV_COMARCA = {
    "Catalunya": {
        "Barcelona": [
            "Alt Penedès", "Anoia", "Bages", "Baix Llobregat", "Barcelonès",
            "Berguedà", "Garraf", "Maresme", "Moianès", "Osona",
            "Vallès Occidental", "Vallès Oriental",
        ],
        "Girona": [
            "Alt Empordà", "Baix Empordà", "Cerdanya", "Garrotxa", "Gironès",
            "La Selva", "Pla de l'Estany", "Ripollès",
        ],
        "Lleida": [
            "Alta Ribagorça", "Alt Urgell", "Les Garrigues", "La Noguera",
            "Pallars Jussà", "Pallars Sobirà", "Pla d'Urgell",
            "La Segarra", "Segrià", "Solsonès", "Urgell", "Val d'Aran",
        ],
        "Tarragona": [
            "Alt Camp", "Baix Camp", "Baix Ebre", "Baix Penedès",
            "Conca de Barberà", "Montsià", "Priorat", "Ribera d'Ebre",
            "Tarragonès", "Terra Alta",
        ],
        "Catalunya Nord": [
            "Alta Cerdanya", "Capcir", "Conflent", "Rosselló", "Vallespir",
        ],
    },
    "País Valencià": {
        "Alacant": [
            "Baix Vinalopó (Alacant)", "Marina Alta (Alacant)", "Marina Baixa (Alacant)",
        ],
        "Castelló": [
            "Baix Maestrat (Castelló)", "Plana Alta (Castelló)",
        ],
    },
    "Aragó": {
        "Osca": [
            "Alt Gàllego (Osca)", "Foia d'Osca (Osca)",
        ],
    },
    "Madrid": {
        "Madrid": [
            "Cuenca Alta del Manzanares (Madrid)", "Cuenca del Guadarrama (Madrid)",
            "Alfoz de Segovia (Segovia)",
        ],
    },
    "Occitània": {
        "Arieja": [
            "Arieja (Occitània)",
        ],
    },
}

ORDRE_COMUNITATS = ["Catalunya", "País Valencià", "Aragó", "Madrid", "Occitània"]

# Ordre dels grups (comunitat, província) tal com apareixeran als menús
ORDRE_GRUPS = [
    (com, prov)
    for com in ORDRE_COMUNITATS
    for prov in COMUNITATS_PROV_COMARCA[com]
]

# Índexs invers: comarca → província / comarca → comunitat / província → comunitat
_COMARCA_A_PROV = {
    c: prov
    for provs in COMUNITATS_PROV_COMARCA.values()
    for prov, comarques in provs.items()
    for c in comarques
}
_PROV_A_COMUNITAT = {
    prov: com
    for com, provs in COMUNITATS_PROV_COMARCA.items()
    for prov in provs
}

# Assignació d'espais naturals a província (per la comarca principal)
# → deduït automàticament a get_filtres() a partir de les rutes


def _agrupar_per_comunitat_prov(items, index_a_prov):
    """Agrupa una llista d'ítems per 'Comunitat · Província' seguint ORDRE_GRUPS.
    Els ítems no reconeguts van a 'Altres'."""
    grups = {f"{com} · {prov}": [] for com, prov in ORDRE_GRUPS}
    altres = []
    for item in sorted(items):
        prov = index_a_prov.get(item)
        comunitat = _PROV_A_COMUNITAT.get(prov)
        clau = f"{comunitat} · {prov}" if comunitat else None
        if clau and clau in grups:
            grups[clau].append(item)
        else:
            altres.append(item)
    resultat = {clau: vals for clau, vals in grups.items() if vals}
    if altres:
        resultat["Altres"] = altres
    return resultat


def get_filtres(rutes):
    ORDRE_DIF = ['Molt fàcil', 'Fàcil', 'Moderada', 'Exigent', 'Molt exigent']
    difs_set = set(r["dificultat"] for r in rutes if r["dificultat"])
    dificultats = [d for d in ORDRE_DIF if d in difs_set]
    comarques = sorted(set(
        c for r in rutes
        for c in [r["comarca_sortida"], r["comarca_arribada"]] if c
    ))
    operadors = sorted(set(
        op.strip()
        for r in rutes
        for camp in [r["op_sortida"], r["op_arribada"]] if camp
        for op in camp.split(";") if op.strip()
    ))
    espais = sorted(set(e for r in rutes for e in r["espai"] if e))
    millors = sorted(set(
        cat.strip()
        for r in rutes if r["millors"]
        for cat in r["millors"].split(";") if cat.strip()
    ))

    # Mapeig explícit per espais que no es poden deduir automàticament
    ESPAI_PROV_EXPLICIT = {
        "Parc Natural de les Muntanyes de Prades": "Tarragona",
        "PN Regional dels Pirineus Catalans": "Catalunya Nord",
        "Tour du Carlit": "Arieja",
    }

    # Deduir província de cada espai natural a partir de les comarques de les rutes
    espai_a_prov = dict(ESPAI_PROV_EXPLICIT)
    for r in rutes:
        for espai in r.get("espai", []):
            if not espai or espai in espai_a_prov:
                continue
            for comarca in [r.get("comarca_sortida"), r.get("comarca_arribada")]:
                prov = _COMARCA_A_PROV.get(comarca)
                if prov:
                    espai_a_prov[espai] = prov
                    break

    return {
        "dificultats": dificultats,
        "comarques": comarques,
        "comarques_per_prov": _agrupar_per_comunitat_prov(comarques, _COMARCA_A_PROV),
        "operadors": operadors,
        "espais": espais,
        "espais_per_prov": _agrupar_per_comunitat_prov(espais, espai_a_prov),
        "millors": millors,
    }


# ══════════════════════════════════════════════════════════════════════
# RUTES FLASK (URLs)
# ══════════════════════════════════════════════════════════════════════

@app.context_processor
def injectar_avis():
    return {"avis": get_avis()}


@app.route("/")
def inici():
    rutes = get_rutes()

    # Rutes destacades (columna "Destacada" = Sí), en ordre aleatori cada vegada
    destacades_totes = [r for r in rutes if r.get("destacada")]
    random.shuffle(destacades_totes)
    destacades = destacades_totes[:6]
    if not destacades:
        destacades = rutes[:3]  # fallback

    # Millors rutes temàtiques (primeres 4 col·leccions)
    grups = {}
    for r in rutes:
        cat = r.get("millors", "")
        if not cat: continue
        for c in cat.split(";"):
            c = c.strip()
            if c:
                grups.setdefault(c, []).append(r)
    colleccions = []
    for k, v_list in sorted(grups.items()):
        primera = v_list[0] if v_list else None
        foto = f"https://raw.githubusercontent.com/Senderismeentren/imatges/main/ruta-{str(primera['id']).zfill(3)}/foto1.jpg" if primera else ""
        colleccions.append({"nom": k, "n": len(v_list), "foto": foto, "url": f"/rutes?millors={k}"})
    # Totes les col·leccions (inici.html en mostra 4 i la resta amb botó)

    # Articles recents del WP (reutilitza la caché de get_articles)
    articles_recents = get_articles()[:3]

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
        "n_cims": len({n.strip() for r in rutes if r["cims"] and r["nom_cim"] for n in r["nom_cim"].split(";") if n.strip()}),
        "n_estacions": len(estacions_uniques),
        "n_linies": len(linies_uniques),
        "total_km": f"{round(total_km):,}".replace(",", "."),
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
    dist    = request.args.get("dist", "")

    rutes_all_list = get_rutes()
    if dif:     rutes = [r for r in rutes if r["dificultat"] == dif]
    if comarca: rutes = [r for r in rutes if comarca in [r["comarca_sortida"], r["comarca_arribada"]]]
    if operador:rutes = [r for r in rutes if any(operador == op.strip() for camp in [r["op_sortida"] or "", r["op_arribada"] or ""] for op in camp.split(";"))]
    if espai:   rutes = [r for r in rutes if espai in r["espai"]]
    if cims:    rutes = [r for r in rutes if r["cims"]]
    if millors: rutes = [r for r in rutes if r["millors"] and millors in [c.strip() for c in r["millors"].split(";")]]
    if estacio: rutes = [r for r in rutes if estacio in [r["sortida"], r["arribada"]]]
    if dist:
        def dins_dist(r):
            km = float(r["km"] or 0)
            if dist == "0-10": return km < 10
            if dist == "10-20": return 10 <= km <= 20
            if dist == "20+": return km > 20
            return True
        rutes = [r for r in rutes if dins_dist(r)]
    millors_filtre = request.args.get("millors", "")
    if millors_filtre: rutes = [r for r in rutes if r.get("millors") and millors_filtre in [c.strip() for c in r["millors"].split(";")]]

    filtres_actius = {k: v for k, v in {
        "dificultat": dif, "comarca": comarca,
        "operador": operador, "espai": espai,
        "cims": cims, "estacio": estacio,
        "dist": dist,
        "millors": millors_filtre or millors,
    }.items() if v}

    # Afegir estacions al diccionari de filtres
    filtres["estacions"] = sorted(set(
        est for r in rutes_all_list
        for est in [r["sortida"], r["arribada"]] if est
    ))
    # Estacions agrupades per operador
    estacions_op = {}
    for r in rutes_all_list:
        for est, ops_str in [(r["sortida"], r["op_sortida"]), (r["arribada"], r["op_arribada"])]:
            if est and ops_str:
                for op in ops_str.split(";"):
                    op = op.strip()
                    if op:
                        estacions_op.setdefault(op, set()).add(est)
    filtres["estacions_per_op"] = {op: sorted(ests) for op, ests in sorted(estacions_op.items())}

    return render_template("rutes.html",
        rutes=rutes,
        rutes_all=rutes_all_list,
        filtres=filtres,
        filtres_actius=filtres_actius,
        n_total=len(rutes_all_list)
    )


@app.route("/api/gpx-descarrega/<int:ruta_id>")
def gpx_descarrega(ruta_id):
    """Serveix el GPX original de la ruta forçant la descàrrega (el fitxer
    viu a GitHub, i un enllaç directe entre dominis no força la descàrrega
    a la majoria de navegadors)."""
    url = BASE_GPX_URL.format(id=ruta_id)
    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            abort(404)
        resp = Response(r.content, mimetype="application/gpx+xml")
        resp.headers["Content-Disposition"] = f"attachment; filename=ruta-{ruta_id:03d}.gpx"
        return resp
    except Exception as e:
        print(f"[gpx-descarrega] Error ruta {ruta_id}: {repr(e)}")
        abort(404)


@app.route("/ruta/<int:ruta_id>")
def fitxa_ruta(ruta_id):
    rutes = get_rutes()
    ruta = next((r for r in rutes if r["id"] == ruta_id), None)
    if not ruta: abort(404)

    fotos = obtenir_fotos(ruta_id)
    gpx_punts = obtenir_gpx(ruta_id)
    dists, eles = gpx_a_perfil(gpx_punts) if gpx_punts else ([], [])

    # Rutes des de les mateixes estacions, separades per estació
    def rutes_per_estacio(est):
        if not est: return []
        ids_vistos = set()
        resultat = []
        for r in rutes:
            if r["id"] == ruta_id: continue
            if r["id"] in ids_vistos: continue
            if est in (r["sortida"], r["arribada"]):
                ids_vistos.add(r["id"])
                resultat.append({
                    "id": r["id"],
                    "nom": r["nom"],
                    "dificultat": r["dificultat"],
                })
        return resultat

    estacions_vistes = set()
    rutes_relacionades = []
    for est in [ruta["sortida"], ruta["arribada"]]:
        if not est or est in estacions_vistes: continue
        estacions_vistes.add(est)
        rutes_est = rutes_per_estacio(est)
        if rutes_est:
            rutes_relacionades.append({"estacio": est, "rutes": rutes_est})

    mateixa_estacio = len(rutes_relacionades) <= 1

    def _titol(camp):
        return camp.split(";", 1)[0].strip() if camp else ""

    def _detecta_tipus(titol):
        """Detecta automàticament de quin tipus de lloc es tracta buscant
        paraules clau en qualsevol posició del títol (no cal que hi comenci).
        Imprecís per naturalesa: només reconeix els tipus previstos aquí."""
        if not titol:
            return None
        t = _sense_accents(titol.lower())
        for tipus, paraules in TIPUS_PUNT_INTERES.items():
            for paraula in paraules:
                if paraula in t:
                    return tipus
        return None

    def _rutes_amb_mateix_tipus(tipus_actual, camp_nom):
        if not tipus_actual:
            return []
        resultat = []
        for r in rutes:
            if r["id"] == ruta_id:
                continue
            if _detecta_tipus(_titol(r.get(camp_nom, ""))) == tipus_actual:
                resultat.append({"id": r["id"], "nom": r["nom"], "dificultat": r["dificultat"]})
        return resultat

    titol_punt_interes = _titol(ruta.get("punt_interes", ""))
    titol_element_ferroviari = _titol(ruta.get("element_ferroviari", ""))
    tipus_punt_interes = _detecta_tipus(titol_punt_interes)
    tipus_element_ferroviari = _detecta_tipus(titol_element_ferroviari)
    rutes_mateix_punt_interes = _rutes_amb_mateix_tipus(tipus_punt_interes, "punt_interes")
    rutes_mateix_element_ferroviari = _rutes_amb_mateix_tipus(tipus_element_ferroviari, "element_ferroviari")

    return render_template("fitxa.html",
        ruta=ruta,
        fotos=fotos,
        gpx_punts=json.dumps(gpx_punts or []),
        perfil_dists=json.dumps(dists),
        perfil_eles=json.dumps(eles),
        BASE_LOGOS_OP="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logos-operadors/",
        BASE_LOGOS_LI="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logos-linies/",
        senders_url=_cache_dades.get("senders_url", {}),
        rutes_relacionades=rutes_relacionades,
        mateixa_estacio=mateixa_estacio,
        rutes_mateix_punt_interes=rutes_mateix_punt_interes,
        rutes_mateix_element_ferroviari=rutes_mateix_element_ferroviari,
        tipus_punt_interes=tipus_punt_interes,
        tipus_element_ferroviari=tipus_element_ferroviari,
    )


@app.route("/mapa")
def mapa_pagina():
    rutes = get_rutes()
    estacions = get_estacions()
    # Només rutes amb coordenades
    rutes_mapa = [r for r in rutes if r["lat_sortida"] not in ("", None, 0) and r["lng_sortida"] not in ("", None, 0)]
    # Agrupar estacions per operador per al sidebar
    estacions_list = list(estacions.values())
    estacions_per_op = {}
    for est in sorted(estacions_list, key=lambda x: x["nom"]):
        ops_str = est["op"] or "Altres"
        for op in ops_str.split(";"):
            op = op.strip() or "Altres"
            if op not in estacions_per_op:
                estacions_per_op[op] = []
            if est["nom"] not in [e["nom"] for e in estacions_per_op[op]]:
                estacions_per_op[op].append(est)
    ORDRE_OPERADORS_FILTRE = ["FGC", "Rodalies", "TMB", "Tram", "BSM", "FGV", "Renfe", "Cercanias", "TAV", "SNCF"]
    ORDRE_OPERADORS_LOWER = [o.lower() for o in ORDRE_OPERADORS_FILTRE]
    def _clau_ordre_op(item):
        op = item[0]
        try:
            return (ORDRE_OPERADORS_LOWER.index(op.lower()), "")
        except ValueError:
            return (len(ORDRE_OPERADORS_FILTRE), op.lower())
    estacions_per_op = dict(sorted(estacions_per_op.items(), key=_clau_ordre_op))

    # Espais naturals únics per als filtres
    espais_mapa = sorted(set(e for r in rutes_mapa for e in r["espai"] if e))

    # Cims (100 Cims): deduplicats per nom, amb les rutes que hi passen
    cims_info = _cache_dades.get("cims_info") or {}
    cims_dict = {}
    for r in rutes_mapa:
        if not r["cims"] or not r["nom_cim"]:
            continue
        noms = [n.strip() for n in r["nom_cim"].split(";") if n.strip()]
        for nom in noms:
            info = cims_info.get(nom)
            if info and info.get("lat") and info.get("lng"):
                lat, lng = info["lat"], info["lng"]
            else:
                # Fallback si el cim encara no és a la pestanya 100cims
                idx = noms.index(nom)
                lats_fb = str(r["lat_cim"]).split(";")
                lngs_fb = str(r["lng_cim"]).split(";")
                try:
                    lat = float(lats_fb[idx] if idx < len(lats_fb) else lats_fb[0])
                    lng = float(lngs_fb[idx] if idx < len(lngs_fb) else lngs_fb[0])
                except (ValueError, IndexError):
                    continue
            if not lat or not lng:
                continue
            if nom not in cims_dict:
                cims_dict[nom] = {
                    "nom": nom,
                    "lat": lat, "lng": lng,
                    "categoria": (info or {}).get("categoria", ""),
                    "alcada": (info or {}).get("alcada", ""),
                    "rutes": [],
                }
            if r["id"] not in [x["id"] for x in cims_dict[nom]["rutes"]]:
                cims_dict[nom]["rutes"].append({"id": r["id"], "nom": r["nom"]})
    cims_llista = sorted(cims_dict.values(), key=lambda x: x["nom"])

    # Línies per operador (només les que apareixen al portal)
    OP_ORDER = ["Rodalies", "FGC", "FGV", "BSM", "TMB", "Tram", "SNCF", "TAV", "Cercanias", "MD"]
    # Ordre fix per FGC
    FGC_ORDER = ["L6","L7","L8","L12","S1","S2","S3","S4","S8","S9",
                 "R5","R50","R6","R60","Funicular de Vallvidrera",
                 "Cremallera de Núria","Cremallera de Montserrat"]
    # Ordre fix per Rodalies (RG1 després R1, RT al final)
    RODALIES_ORDER_PREFIX = ["R1","R2","R2 Nord","R2 Sud","R3","R4",
                              "R7","R8","R11","R13","R14","R15","R16","R17",
                              "RG1","RL3","RL4","RT1","RT2"]

    linies_per_op = {}
    for r in rutes_mapa:
        # Operador principal
        for camp_op, camp_lin in [("op_sortida","linies_sortida"),("op_arribada","linies_arribada")]:
            op = r.get(camp_op, "").strip()
            if not op: continue
            for linia in r.get(camp_lin, []):
                if not linia: continue
                if op not in linies_per_op:
                    linies_per_op[op] = set()
                linies_per_op[op].add(linia)
        # Segon operador
        for camp_op2, camp_lin2 in [("op2_sortida","linies2_sortida"),("op2_arribada","linies2_arribada")]:
            op2 = r.get(camp_op2, "").strip()
            if not op2: continue
            for linia in r.get(camp_lin2, []):
                if not linia: continue
                if op2 not in linies_per_op:
                    linies_per_op[op2] = set()
                linies_per_op[op2].add(linia)

    def _ordre_linia(op, nom):
        if op == "FGC":
            try: return (FGC_ORDER.index(nom), nom)
            except ValueError: return (999, nom)
        if op == "Rodalies":
            try: return (RODALIES_ORDER_PREFIX.index(nom), nom)
            except ValueError:
                import re
                m = re.search(r'(\d+)', nom)
                return (500 + (int(m.group(1)) if m else 999), nom)
        import re
        m = re.search(r'(\d+)', nom)
        return (int(m.group(1)) if m else 999, nom)

    linies_per_op = {op: sorted(lins, key=lambda n: _ordre_linia(op, n))
                     for op, lins in linies_per_op.items()}

    # Ordenar operadors per ordre preferit
    linies_per_op_ord = {}
    for op in OP_ORDER:
        if op in linies_per_op:
            linies_per_op_ord[op] = linies_per_op[op]
    for op in linies_per_op:
        if op not in linies_per_op_ord:
            linies_per_op_ord[op] = linies_per_op[op]

    return render_template("mapa.html",
        rutes=rutes_mapa,
        estacions=estacions_list,
        estacions_per_op=estacions_per_op,
        espais_mapa=espais_mapa,
        linies_per_op=linies_per_op_ord,
        cims_llista=cims_llista,
    )


@app.route("/millors_rutes")
def millors_rutes_pagina():
    rutes = get_rutes()
    # Agrupar per categoria Millors_rutes (una ruta pot pertànyer a diverses, separades per ";")
    grups = {}
    for r in rutes:
        cat = r["millors"]
        if not cat: continue
        for c in cat.split(";"):
            c = c.strip()
            if c:
                grups.setdefault(c, []).append(r)
    def _clau_ordre_cat(item):
        m = re.match(r'^\s*(\d+)', item[0])
        return (int(m.group(1)) if m else float('inf'), item[0])
    grups = dict(sorted(grups.items(), key=_clau_ordre_cat))
    for llista in grups.values():
        random.shuffle(llista)
    return render_template("millors_rutes.html", grups=grups)


@app.route("/100-cims")
def cims_522_pagina():
    rutes = get_rutes()
    cims = list(_cache_dades.get("cims522") or [])

    # Creuar amb les rutes existents: TOTES les rutes que fan cada cim, no només la primera
    # (mateix criteri que el comptador d'Inici: cal que la columna 100cims digui "Sí")
    rutes_per_cim = {}
    for r in rutes:
        if not r.get("cims"):
            continue
        nom_camp = r.get("nom_cim") or ""
        for part in str(nom_camp).split(";"):
            nom = part.strip()
            if nom:
                rutes_per_cim.setdefault(nom, []).append(r)

    cims.sort(key=lambda c: (c["nom"] or "").lower())

    for i, c in enumerate(cims, start=1):
        c["num"] = i
        rutes_fetes = rutes_per_cim.get(c["nom"], [])
        c["fet"] = len(rutes_fetes) > 0
        c["rutes_ids"] = [r["id"] for r in rutes_fetes]

    n_fets = len({n.strip() for r in rutes if r["cims"] and r["nom_cim"] for n in r["nom_cim"].split(";") if n.strip()})

    n_essencials_total = sum(1 for c in cims if c["essencial"])
    n_essencials_fets = sum(1 for c in cims if c["essencial"] and c["fet"])

    descarregues = _cache_dades.get("descarregues") or {}
    return render_template("100cims.html", cims=cims, n_fets=n_fets, n_total=len(cims),
                            n_essencials_fets=n_essencials_fets, n_essencials_total=n_essencials_total,
                            descarregues=descarregues)


@app.route("/100-cims/descarrega.gpx")
def cims_522_gpx():
    cims = _cache_dades.get("cims522") or []
    linies = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gpx version="1.1" creator="Senderisme en Tren" xmlns="http://www.topografix.com/GPX/1/1">']
    for c in cims:
        if not c.get("lat") or not c.get("lng"):
            continue
        nom = h.escape(c["nom"])
        ele = f'<ele>{c["alcada"]}</ele>' if c.get("alcada") else ''
        linies.append(f'<wpt lat="{c["lat"]}" lon="{c["lng"]}">{ele}<name>{nom}</name></wpt>')
    linies.append('</gpx>')
    _incrementar_descarrega("GPX")
    resp = Response("\n".join(linies), mimetype="application/gpx+xml")
    resp.headers["Content-Disposition"] = "attachment; filename=522-cims-feec.gpx"
    return resp


@app.route("/100-cims/descarrega.kml")
def cims_522_kml():
    cims = _cache_dades.get("cims522") or []
    linies = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
              '<name>522 Cims de la FEEC</name>']
    for c in cims:
        if not c.get("lat") or not c.get("lng"):
            continue
        nom = h.escape(c["nom"])
        comarca_txt = c["comarca"] or ""
        descripcio = h.escape(comarca_txt + (' · Essencial' if c.get('essencial') else ''))
        linies.append(
            f'<Placemark><name>{nom}</name><description>{descripcio}</description>'
            f'<Point><coordinates>{c["lng"]},{c["lat"]},{c["alcada"] or 0}</coordinates></Point></Placemark>'
        )
    linies.append('</Document></kml>')
    _incrementar_descarrega("KML")
    resp = Response("\n".join(linies), mimetype="application/vnd.google-earth.kml+xml")
    resp.headers["Content-Disposition"] = "attachment; filename=522-cims-feec.kml"
    return resp


@app.route("/100-cims/descarrega.xlsx")
def cims_522_xlsx():
    cims = list(_cache_dades.get("cims522") or [])
    cims.sort(key=lambda c: (c["nom"] or "").lower())
    df = pd.DataFrame([{
        "Nom": c["nom"],
        "Alçada (m)": c["alcada"],
        "Comarca": c["comarca"],
        "Essencial": "Sí" if c.get("essencial") else "",
        "Latitud": c["lat"],
        "Longitud": c["lng"],
    } for c in cims])
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    _incrementar_descarrega("Excel")
    resp = Response(buf.read(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp.headers["Content-Disposition"] = "attachment; filename=522-cims-feec.xlsx"
    return resp


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
ARTICLES_CACHE_TTL = 3600  # 1 hora
ARTICLES_RETRY_BACKOFF = 300  # 5 min: si falla, no tornar a provar-ho abans d'aquest temps
WP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_cache_articles = {"articles": None, "ts": 0, "darrer_intent": 0}

def _id_o_slug_de_url(url_wp):
    """Extreu l'identificador (numèric o slug) del darrer tros d'una URL de WP."""
    return url_wp.rstrip('/').split('/')[-1]

def _fetch_un_article_wp(url_wp):
    """Consulta un sol article de WP per la seva URL (numèrica o slug), amb imatge inclosa.
    Retorna None si no es troba o falla, sense llençar excepció (un article solt que falli
    no ha de tombar tota la llista)."""
    segment = _id_o_slug_de_url(url_wp)
    try:
        if segment.isdigit():
            api_url = f"{WP_BASE}/posts/{segment}"
            params = {"_embed": "wp:featuredmedia"}
        else:
            api_url = f"{WP_BASE}/posts"
            params = {"slug": segment, "_embed": "wp:featuredmedia"}
        resp = requests.get(api_url, params=params, headers=WP_HEADERS, timeout=6)
        a = resp.json()
        if isinstance(a, list):
            if not a:
                return None
            a = a[0]
        try:
            imatge = a["_embedded"]["wp:featuredmedia"][0]["source_url"]
        except (KeyError, IndexError, TypeError):
            imatge = ""
        return {
            "id": a.get("id"),
            "titol": h.unescape(a.get("title", {}).get("rendered", "")),
            "extracte": a.get("excerpt", {}).get("rendered", ""),
            "data": a.get("date", "")[:10],
            "imatge": imatge,
        }
    except Exception as e:
        print(f"[articles] Article {url_wp} descartat per error: {repr(e)}")
        return None

def _fetch_articles_wp():
    """Consulta un per un els articles triats manualment a la pestanya Articles de Sheets
    (en lloc d'una consulta massiva per categoria, que ha demostrat provocar bloquejos 429
    a WP). Una petita pausa entre articles evita fer una ràfega de peticions seguides."""
    urls = _cache_dades.get("articles_urls") or []
    articles = []
    for i, url_wp in enumerate(urls):
        article = _fetch_un_article_wp(url_wp)
        if article:
            articles.append(article)
        if i < len(urls) - 1:
            time.sleep(0.3)
    articles.sort(key=lambda a: a["data"], reverse=True)
    return articles

_articles_fetching = False
_articles_lock = threading.Lock()

def _refrescar_articles_en_segon_pla():
    global _articles_fetching
    try:
        articles = _fetch_articles_wp()
        _cache_articles["articles"] = articles
        _cache_articles["ts"] = time.time()
        print(f"[articles] Caché actualitzada ({len(articles)} articles)")
    except Exception as e:
        print(f"[articles] Error consultant WP: {repr(e)}")
    finally:
        _articles_fetching = False

def get_articles():
    """Retorna articles des de caché (TTL 1h). Si la caché és buida o caducada, llança
    l'actualització en un fil a part (mai bloqueja la pàgina que l'ha demanat) i retorna
    el que ja hi hagi (encara que sigui buit o antic). Com a molt es refresca cada
    ARTICLES_RETRY_BACKOFF segons si l'últim intent va fallar."""
    global _articles_fetching
    ara = time.time()
    if _cache_articles["articles"] is not None and ara - _cache_articles["ts"] < ARTICLES_CACHE_TTL:
        return _cache_articles["articles"]
    if ara - _cache_articles["darrer_intent"] < ARTICLES_RETRY_BACKOFF:
        return _cache_articles["articles"] or []
    with _articles_lock:
        if _articles_fetching:
            return _cache_articles["articles"] or []
        _articles_fetching = True
        _cache_articles["darrer_intent"] = ara
    threading.Thread(target=_refrescar_articles_en_segon_pla, daemon=True).start()
    return _cache_articles["articles"] or []

@app.route("/articles")
def articles_pagina():
    """Llista d'articles del WP."""
    articles = get_articles()
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
        titol = __import__("html").unescape(data.get("title", {}).get("rendered", ""))
        contingut_html = data.get("content", {}).get("rendered", "")
        data_pub = data.get("date", "")[:10]

        # Netejar HTML: treure social links, spacers, però mantenir imatges
        contingut = re.sub(r'<ul[^>]*wp-block-social-links[^>]*>.*?</ul>\s*', '', contingut_html, flags=re.DOTALL, count=1)
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

        titol = __import__("html").unescape(data.get("title", {}).get("rendered", ""))
        contingut = data.get("content", {}).get("rendered", "")
        extracte = data.get("excerpt", {}).get("rendered", "")

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
        # ── TRAM ─────────────────────────────────────────────────────
        if ";" in id_estacio and all(p.strip().isdigit() for p in id_estacio.split(";")):
            tram_id = os.environ.get("TRAM_CLIENT_ID", "")
            tram_secret = os.environ.get("TRAM_CLIENT_SECRET", "")
            codis = [int(p.strip()) for p in id_estacio.split(";")]
            r_token = requests.post("https://opendata.tram.cat/connect/token", data={
                "grant_type": "client_credentials",
                "client_id": tram_id,
                "client_secret": tram_secret
            }, timeout=8)
            token = r_token.json()["access_token"]
            horaris = []
            vists = set()
            for code in codis:
                r2 = requests.get(f"https://opendata.tram.cat/api/v1/stopTimes/{code}",
                    headers={"Authorization": f"Bearer {token}"}, timeout=8)
                for st in r2.json():
                    hora = st.get("arrivalTime", "")[:16].split(" ")[-1][:5]
                    linia = st.get("lineName", "")
                    dest = st.get("destination", "")
                    clau = f"{hora}_{linia}_{dest}"
                    if hora and clau not in vists:
                        vists.add(clau)
                        horaris.append({
                            "hora": hora,
                            "linia": linia,
                            "destinacio": dest,
                            "retard": 0,
                            "ara": False
                        })
            horaris.sort(key=lambda h: h["hora"])
            return jsonify({"horaris": horaris[:8], "operador": "Tram"})

        # ── FGC ──────────────────────────────────────────────────────
        if not id_estacio.isdigit():
            # Hora local catalana (UTC+2 estiu, UTC+1 hivern)
            import zoneinfo
            tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")
            ara_cat = datetime.now(tz_cat)
            hora_actual = ara_cat.strftime("%H:%M:%S")
            base = "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records"
            nom_estacio = id_estacio.replace("_", " ")
            nom_api = nom_estacio
            # Paginació per trobar l'hora actual: demanem de 100 en 100 fins trobar trens futurs
            params_base = {
                "where": f"stop_name='{nom_api}'",
                "order_by": "departure_time ASC",
                "limit": "100",
                "select": "departure_time,route_short_name,trip_headsign",
            }
            results_filtrats = []
            for offset in range(0, 600, 100):
                params_base["offset"] = str(offset)
                resp = requests.get(base, params=params_base, timeout=8)
                bloc = resp.json().get("results", [])
                if not bloc:
                    break
                # Si l'últim element del bloc és anterior a l'hora actual, saltem al següent
                ultim = bloc[-1].get("departure_time", "00:00:00")
                if ultim < hora_actual:
                    continue
                # Tenim trens futurs en aquest bloc
                results_filtrats = sorted(
                    [r for r in bloc if r.get("departure_time", "00:00:00") >= hora_actual],
                    key=lambda r: r.get("departure_time", "")
                )
                break
            data = {"results": results_filtrats}

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


@app.route("/api/horaris-renfe/<path:id_estacio>")
def api_horaris_renfe(id_estacio):
    """Horaris en temps real per a Cercanías/Media Distancia (fora de Catalunya),
    via el feed GTFS-Realtime oficial de Renfe (gtfsrt.renfe.com/trip_updates.json).
    Nota: aquest feed només dona hora i retard, no destinació; la línia es dedueix
    del sufix del tripId (p. ex. "...C8b" -> "C-8b") quan és possible."""
    from datetime import datetime
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    try:
        resp = requests.get("https://gtfsrt.renfe.com/trip_updates.json", timeout=8)
        data = resp.json()
        horaris = []
        vists = set()
        for entity in data.get("entity", []):
            tu = entity.get("tripUpdate", {})
            trip_id = tu.get("trip", {}).get("tripId", "")
            m_linia = re.search(r'C(\d+)[a-z]?$', trip_id, re.IGNORECASE)
            linia = f"C-{m_linia.group(1)}" if m_linia else "Cercanías"
            for stu in tu.get("stopTimeUpdate", []):
                if str(stu.get("stopId", "")) != str(id_estacio):
                    continue
                arribada = stu.get("arrival", {})
                ts = arribada.get("time")
                if not ts:
                    continue
                hora = datetime.fromtimestamp(int(ts), tz_cat).strftime("%H:%M")
                retard_seg = int(arribada.get("delay", 0) or 0)
                retard_min = max(0, round(retard_seg / 60))
                clau = f"{hora}_{linia}"
                if clau not in vists:
                    vists.add(clau)
                    horaris.append({
                        "hora": hora,
                        "linia": linia,
                        "destinacio": "",
                        "retard": retard_min,
                        "ara": False
                    })
        horaris.sort(key=lambda h: h["hora"])
        return jsonify({"horaris": horaris[:8], "operador": "Cercanías"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


_cache_gtfs_renfe = {"dades": None, "carregat_a": 0}
GTFS_RENFE_TTL = 24 * 3600

def _carregar_gtfs_renfe():
    """Descarrega i parseja el mirall a GitHub del GTFS estàtic de Renfe Cercanías
    (l'original de ssl.renfe.com falla sovint des de servidors de hosting, per
    això es manté un mirall actualitzat setmanalment via GitHub Action)."""
    ara = time.time()
    if _cache_gtfs_renfe["dades"] and (ara - _cache_gtfs_renfe["carregat_a"] < GTFS_RENFE_TTL):
        return _cache_gtfs_renfe["dades"]

    url = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gtfs-renfe/fomento_transit.zip"
    r = requests.get(url, timeout=15)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    stops = pd.read_csv(z.open("stops.txt"), dtype=str)
    routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
    calendar = pd.read_csv(z.open("calendar.txt"), dtype=str) if "calendar.txt" in z.namelist() else None
    calendar = _netejar_calendar(calendar)
    calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype=str) if "calendar_dates.txt" in z.namelist() else None

    dades = {
        "stops": stops, "routes": routes, "trips": trips,
        "stop_times": stop_times, "calendar": calendar, "calendar_dates": calendar_dates
    }
    _cache_gtfs_renfe["dades"] = dades
    _cache_gtfs_renfe["carregat_a"] = ara
    return dades


@app.route("/api/horaris-renfe-gtfs/<path:id_estacio>")
def api_horaris_renfe_gtfs(id_estacio):
    """Horaris programats (GTFS estàtic oficial de Renfe, via mirall a GitHub)
    per a Cercanías/Media Distancia, en substitució del feed en directe
    (gtfsrt.renfe.com), que sovint no dona cap resultat per a línies poc
    freqüentades com Cercedilla."""
    from datetime import datetime, timedelta
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    try:
        dades = _carregar_gtfs_renfe()
        stops, routes, trips = dades["stops"], dades["routes"], dades["trips"]
        stop_times = dades["stop_times"]

        coincidents = stops[(stops["stop_id"] == str(id_estacio)) | (stops.get("stop_code") == str(id_estacio))]
        if coincidents.empty:
            return jsonify({"horaris": [], "error": f"Estació {id_estacio} no trobada al GTFS de Renfe"})
        stop_ids = set(coincidents["stop_id"])

        trip_id_a_linia = dict(zip(trips["trip_id"], trips["route_id"]))
        trip_id_a_desti = dict(zip(trips["trip_id"], trips.get("trip_headsign", pd.Series(dtype=str)).fillna("")))
        trip_id_a_servei = dict(zip(trips["trip_id"], trips["service_id"]))
        route_id_a_nom = dict(zip(routes["route_id"], routes["route_short_name"]))

        serveis_avui = _serveis_actius_avui(dades["calendar"], dades["calendar_dates"])

        pas = stop_times[stop_times["stop_id"].isin(stop_ids) & stop_times["trip_id"].isin(trip_id_a_linia.keys())]

        ara = datetime.now(tz_cat)
        avui_str = ara.strftime("%Y%m%d")
        avui_iso = ara.strftime("%Y-%m-%d")
        horaris = []
        vist_claus = set()
        for _, row in pas.iterrows():
            trip_id = row["trip_id"]
            data_incrustada = _data_incrustada_trip_id(trip_id)
            if data_incrustada is not None:
                if data_incrustada != avui_iso:
                    continue
            elif serveis_avui is not None and trip_id_a_servei.get(trip_id) not in serveis_avui:
                continue
            hora_txt = row.get("departure_time") or row.get("arrival_time")
            if not hora_txt:
                continue
            hh, mm, ss = [int(x) for x in hora_txt.split(":")]
            moment = datetime.strptime(avui_str, "%Y%m%d").replace(
                hour=0, minute=0, second=0, tzinfo=tz_cat
            ) + timedelta(hours=hh, minutes=mm, seconds=ss)
            if moment < ara:
                continue
            linia = str(route_id_a_nom.get(trip_id_a_linia.get(trip_id), "")).strip()
            desti = str(trip_id_a_desti.get(trip_id, "")).strip()
            clau = (moment.strftime("%H:%M"), linia, desti)
            if clau in vist_claus:
                continue
            vist_claus.add(clau)
            horaris.append({
                "hora": moment.strftime("%H:%M"),
                "linia": linia,
                "destinacio": desti,
                "retard": 0,
                "ara": False,
                "_ordre": moment
            })
        horaris.sort(key=lambda x: x["_ordre"])
        for hh in horaris:
            del hh["_ordre"]
        return jsonify({"horaris": horaris[:8], "operador": "Cercanías"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


_cache_gtfs_renfe_avld = {"dades": None, "carregat_a": 0}
GTFS_RENFE_AVLD_TTL = 24 * 3600

def _carregar_gtfs_renfe_avld():
    """Descarrega i parseja el mirall a GitHub del GTFS estàtic de Renfe
    Alta Velocitat / Llarga Distància / Media Distancia (Regional Exprés
    inclòs), diferent del de Cercanías."""
    ara = time.time()
    if _cache_gtfs_renfe_avld["dades"] and (ara - _cache_gtfs_renfe_avld["carregat_a"] < GTFS_RENFE_AVLD_TTL):
        return _cache_gtfs_renfe_avld["dades"]

    url = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gtfs-renfe-avld/google_transit.zip"
    r = requests.get(url, timeout=15)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    stops = pd.read_csv(z.open("stops.txt"), dtype=str)
    routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
    calendar = pd.read_csv(z.open("calendar.txt"), dtype=str) if "calendar.txt" in z.namelist() else None
    calendar = _netejar_calendar(calendar)
    calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype=str) if "calendar_dates.txt" in z.namelist() else None

    dades = {
        "stops": stops, "routes": routes, "trips": trips,
        "stop_times": stop_times, "calendar": calendar, "calendar_dates": calendar_dates
    }
    _cache_gtfs_renfe_avld["dades"] = dades
    _cache_gtfs_renfe_avld["carregat_a"] = ara
    return dades


@app.route("/api/horaris-renfe-avld-gtfs/<path:id_estacio>")
def api_horaris_renfe_avld_gtfs(id_estacio):
    """Horaris programats (GTFS estàtic oficial) per a Media Distancia,
    Regional Exprés, Llarga Distància i Alta Velocitat de Renfe."""
    from datetime import datetime, timedelta
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    try:
        dades = _carregar_gtfs_renfe_avld()
        stops, routes, trips = dades["stops"], dades["routes"], dades["trips"]
        stop_times = dades["stop_times"]

        coincidents = stops[(stops["stop_id"] == str(id_estacio)) | (stops.get("stop_code") == str(id_estacio))]
        if coincidents.empty:
            return jsonify({"horaris": [], "error": f"Estació {id_estacio} no trobada al GTFS d'AV/LD/MD"})
        stop_ids = set(coincidents["stop_id"])

        trip_id_a_linia = dict(zip(trips["trip_id"], trips["route_id"]))
        trip_id_a_desti = dict(zip(trips["trip_id"], trips.get("trip_headsign", pd.Series(dtype=str)).fillna("")))
        trip_id_a_servei = dict(zip(trips["trip_id"], trips["service_id"]))
        route_id_a_nom = dict(zip(routes["route_id"], routes["route_short_name"]))

        serveis_avui = _serveis_actius_avui(dades["calendar"], dades["calendar_dates"])

        pas = stop_times[stop_times["stop_id"].isin(stop_ids) & stop_times["trip_id"].isin(trip_id_a_linia.keys())]

        if request.args.get("debug"):
            dates_trobades = sorted(set(
                _data_incrustada_trip_id(t) for t in pas["trip_id"] if _data_incrustada_trip_id(t)
            ))
            return jsonify({
                "total_files_estacio": len(pas),
                "dates_incrustades_trobades": dates_trobades[:30],
                "data_avui": datetime.now(tz_cat).strftime("%Y-%m-%d")
            })

        ara = datetime.now(tz_cat)
        avui_str = ara.strftime("%Y%m%d")
        avui_iso = ara.strftime("%Y-%m-%d")
        horaris = []
        vist_claus = set()
        for _, row in pas.iterrows():
            trip_id = row["trip_id"]
            data_incrustada = _data_incrustada_trip_id(trip_id)
            if data_incrustada is not None:
                if data_incrustada != avui_iso:
                    continue
            elif serveis_avui is not None and trip_id_a_servei.get(trip_id) not in serveis_avui:
                continue
            hora_txt = row.get("departure_time") or row.get("arrival_time")
            if not hora_txt:
                continue
            hh, mm, ss = [int(x) for x in hora_txt.split(":")]
            moment = datetime.strptime(avui_str, "%Y%m%d").replace(
                hour=0, minute=0, second=0, tzinfo=tz_cat
            ) + timedelta(hours=hh, minutes=mm, seconds=ss)
            if moment < ara:
                continue
            linia = str(route_id_a_nom.get(trip_id_a_linia.get(trip_id), "")).strip()
            desti = str(trip_id_a_desti.get(trip_id, "")).strip()
            clau = (moment.strftime("%H:%M"), linia, desti)
            if clau in vist_claus:
                continue
            vist_claus.add(clau)
            horaris.append({
                "hora": moment.strftime("%H:%M"),
                "linia": linia,
                "destinacio": desti,
                "retard": 0,
                "ara": False,
                "_ordre": moment
            })
        horaris.sort(key=lambda x: x["_ordre"])
        for hh in horaris:
            del hh["_ordre"]
        return jsonify({"horaris": horaris[:8], "operador": "Renfe"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})




    """Horaris en temps real del Metro de Barcelona via l'API i-Metro de TMB."""
    from datetime import datetime
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    if not TMB_APP_ID or not TMB_APP_KEY:
        return jsonify({"horaris": [], "error": "Falten les credencials TMB_APP_ID/TMB_APP_KEY"})

    try:
        url = "https://api.tmb.cat/v1/itransit/metro/estacions"
        params = {"estacions": id_estacio, "app_id": TMB_APP_ID, "app_key": TMB_APP_KEY}
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        horaris = []
        for linia in data.get("linies", []):
            nom_linia = linia.get("nom_linia", "")
            for estacio in linia.get("estacions", []):
                for trajecte in estacio.get("linies_trajectes", []):
                    desti = trajecte.get("desti_trajecte", "")
                    for tren in trajecte.get("propers_trens", []):
                        ts_ms = tren.get("temps_arribada")
                        if not ts_ms:
                            continue
                        hora = datetime.fromtimestamp(int(ts_ms) / 1000, tz_cat).strftime("%H:%M")
                        horaris.append({
                            "hora": hora,
                            "linia": nom_linia,
                            "destinacio": desti,
                            "retard": 0,
                            "ara": False
                        })
        horaris.sort(key=lambda h: h["hora"])
        return jsonify({"horaris": horaris[:8], "operador": "TMB"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


_cache_gtfs_tmb = {"dades": None, "carregat_a": 0}
GTFS_TMB_TTL = 24 * 3600  # el GTFS de TMB s'actualitza setmanalment; refresquem cada dia

def _carregar_gtfs_tmb():
    """Descarrega i parseja el GTFS estàtic de TMB (només un cop al dia, es queda en memòria)."""
    ara = time.time()
    if _cache_gtfs_tmb["dades"] and (ara - _cache_gtfs_tmb["carregat_a"] < GTFS_TMB_TTL):
        return _cache_gtfs_tmb["dades"]

    url = "https://api.tmb.cat/v1/static/datasets/gtfs.zip"
    r = requests.get(url, params={"app_id": TMB_APP_ID, "app_key": TMB_APP_KEY}, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    stops = pd.read_csv(z.open("stops.txt"), dtype=str)
    routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
    calendar = pd.read_csv(z.open("calendar.txt"), dtype=str) if "calendar.txt" in z.namelist() else None
    calendar = _netejar_calendar(calendar)
    calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype=str) if "calendar_dates.txt" in z.namelist() else None

    dades = {
        "stops": stops, "routes": routes, "trips": trips,
        "stop_times": stop_times, "calendar": calendar, "calendar_dates": calendar_dates
    }
    _cache_gtfs_tmb["dades"] = dades
    _cache_gtfs_tmb["carregat_a"] = ara
    return dades


_PATRO_DATA_TRIP_ID = re.compile(r'(\d{4}-\d{2}-\d{2})$')

def _data_incrustada_trip_id(trip_id):
    """Alguns trip_id de Renfe porten la data exacta de validesa enganxada
    al final (p. ex. '0146312026-08-17' -> vàlid només el 2026-08-17).
    Retorna aquesta data en format 'YYYY-MM-DD', o None si el trip_id no
    en porta cap."""
    m = _PATRO_DATA_TRIP_ID.search(str(trip_id))
    return m.group(1) if m else None


_PATRO_PREFIX_CORRUPTE = re.compile(r'^\d{4}-\d{2}-\d{2}\d{4}-\d{2}-\d{2}(.+)$')

def _netejar_calendar(calendar):
    """Alguns GTFS de Renfe (p. ex. AV/LD/MD) porten el service_id de calendar.txt
    amb un prefix de dates enganxat sense coma (p. ex. '2026-07-302026-08-04001901'
    en lloc de '001901'). Ho netegem perquè coincideixi amb el service_id real
    que fan servir trips.txt."""
    if calendar is not None and "service_id" in calendar.columns:
        calendar = calendar.copy()
        calendar["service_id"] = calendar["service_id"].astype(str).apply(
            lambda v: (_PATRO_PREFIX_CORRUPTE.match(v).group(1) if _PATRO_PREFIX_CORRUPTE.match(v) else v)
        )
    return calendar


def _serveis_actius_avui(calendar, calendar_dates):
    """Retorna el conjunt de service_id vàlids per avui, segons calendar.txt + excepcions."""
    from datetime import date
    avui = date.today()
    avui_str = avui.strftime("%Y%m%d")
    dies = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    dia_setmana = dies[avui.weekday()]

    actius = set()
    te_columnes = (
        calendar is not None
        and {"start_date", "end_date", "service_id"}.issubset(set(calendar.columns))
    )
    if not te_columnes and (calendar_dates is None or not {"date", "service_id", "exception_type"}.issubset(set(calendar_dates.columns))):
        return None  # no es pot determinar el calendari: no filtrem per servei

    if te_columnes:
        for _, row in calendar.iterrows():
            if row.get(dia_setmana) == "1" and row["start_date"] <= avui_str <= row["end_date"]:
                actius.add(row["service_id"])
    if calendar_dates is not None and {"date", "service_id", "exception_type"}.issubset(set(calendar_dates.columns)):
        avui_exc = calendar_dates[calendar_dates["date"] == avui_str]
        for _, row in avui_exc.iterrows():
            if row["exception_type"] == "1":
                actius.add(row["service_id"])
            elif row["exception_type"] == "2" and row["service_id"] in actius:
                actius.discard(row["service_id"])
    return actius


@app.route("/api/horaris-tmb/<path:id_estacio>")
def api_horaris_tmb(id_estacio):
    """Horaris en temps real del Metro de Barcelona via l'API i-Metro de TMB."""
    from datetime import datetime
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    if not TMB_APP_ID or not TMB_APP_KEY:
        return jsonify({"horaris": [], "error": "Falten les credencials TMB_APP_ID/TMB_APP_KEY"})

    try:
        url = "https://api.tmb.cat/v1/itransit/metro/estacions"
        params = {"estacions": id_estacio, "app_id": TMB_APP_ID, "app_key": TMB_APP_KEY}
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        horaris = []
        for linia in data.get("linies", []):
            nom_linia = linia.get("nom_linia", "")
            for estacio in linia.get("estacions", []):
                for trajecte in estacio.get("linies_trajectes", []):
                    desti = trajecte.get("desti_trajecte", "")
                    for tren in trajecte.get("propers_trens", []):
                        ts_ms = tren.get("temps_arribada")
                        if not ts_ms:
                            continue
                        hora = datetime.fromtimestamp(int(ts_ms) / 1000, tz_cat).strftime("%H:%M")
                        horaris.append({
                            "hora": hora,
                            "linia": nom_linia,
                            "destinacio": desti,
                            "retard": 0,
                            "ara": False
                        })
        horaris.sort(key=lambda h: h["hora"])
        return jsonify({"horaris": horaris[:8], "operador": "TMB"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


@app.route("/api/horaris-tmb-gtfs/<path:id_estacio>")
def api_horaris_tmb_gtfs(id_estacio):
    """Horaris programats (GTFS estàtic oficial) per a L9 i L10 (Nord i Sud),
    on l'i-Metro en temps real no dona cobertura. Com que són línies automàtiques
    sense conductor, l'horari programat és pràcticament exacte."""
    from datetime import datetime, timedelta
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    if not TMB_APP_ID or not TMB_APP_KEY:
        return jsonify({"horaris": [], "error": "Falten les credencials TMB_APP_ID/TMB_APP_KEY"})

    try:
        dades = _carregar_gtfs_tmb()
        stops, routes, trips = dades["stops"], dades["routes"], dades["trips"]
        stop_times = dades["stop_times"]

        # Trobar el/s stop_id que coincideixin amb el codi d'estació (stop_id o stop_code)
        coincidents = stops[(stops["stop_id"] == str(id_estacio)) | (stops.get("stop_code") == str(id_estacio))]
        if coincidents.empty:
            return jsonify({"horaris": [], "error": f"Estació {id_estacio} no trobada al GTFS"})
        stop_ids = set(coincidents["stop_id"])

        # Només L9/L10 (Nord i Sud)
        rutes_l9l10 = routes[routes["route_short_name"].isin(["L9N", "L9S", "L10N", "L10S"])]
        route_ids = set(rutes_l9l10["route_id"])
        if not route_ids:
            return jsonify({"horaris": [], "error": "No s'han trobat les línies L9/L10 al GTFS"})

        trips_l9l10 = trips[trips["route_id"].isin(route_ids)]
        trip_id_a_linia = dict(zip(trips_l9l10["trip_id"], trips_l9l10["route_id"]))
        trip_id_a_desti = dict(zip(trips_l9l10["trip_id"], trips_l9l10.get("trip_headsign", pd.Series(dtype=str)).fillna("")))
        trip_id_a_servei = dict(zip(trips_l9l10["trip_id"], trips_l9l10["service_id"]))
        route_id_a_nom = dict(zip(routes["route_id"], routes["route_short_name"]))

        serveis_avui = _serveis_actius_avui(dades["calendar"], dades["calendar_dates"])

        pas = stop_times[stop_times["stop_id"].isin(stop_ids) & stop_times["trip_id"].isin(trip_id_a_linia.keys())]

        ara = datetime.now(tz_cat)
        avui_str = ara.strftime("%Y%m%d")
        avui_iso = ara.strftime("%Y-%m-%d")
        horaris = []
        vist_claus = set()
        for _, row in pas.iterrows():
            trip_id = row["trip_id"]
            data_incrustada = _data_incrustada_trip_id(trip_id)
            if data_incrustada is not None:
                if data_incrustada != avui_iso:
                    continue
            elif serveis_avui is not None and trip_id_a_servei.get(trip_id) not in serveis_avui:
                continue
            hora_txt = row.get("departure_time") or row.get("arrival_time")
            if not hora_txt:
                continue
            hh, mm, ss = [int(x) for x in hora_txt.split(":")]
            moment = datetime.strptime(avui_str, "%Y%m%d").replace(
                hour=0, minute=0, second=0, tzinfo=tz_cat
            ) + timedelta(hours=hh, minutes=mm, seconds=ss)  # gestiona hores >=24 (servei nocturn)
            if moment < ara:
                continue
            linia = str(route_id_a_nom.get(trip_id_a_linia.get(trip_id), "")).strip()
            desti = str(trip_id_a_desti.get(trip_id, "")).strip()
            clau = (moment.strftime("%H:%M"), linia, desti)
            if clau in vist_claus:
                continue
            vist_claus.add(clau)
            horaris.append({
                "hora": moment.strftime("%H:%M"),
                "linia": linia,
                "destinacio": desti,
                "retard": 0,
                "ara": False,
                "_ordre": moment
            })
        horaris.sort(key=lambda x: x["_ordre"])
        for hh in horaris:
            del hh["_ordre"]
        return jsonify({"horaris": horaris[:8], "operador": "TMB"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


_cache_gtfs_fgv = {"dades": None, "carregat_a": 0}
GTFS_FGV_TTL = 24 * 3600  # setmanal segons FGV; refresquem cada dia per si de cas

def _carregar_gtfs_fgv():
    """Descarrega i parseja el GTFS estàtic oficial del TRAM d'Alacant (FGV)."""
    ara = time.time()
    if _cache_gtfs_fgv["dades"] and (ara - _cache_gtfs_fgv["carregat_a"] < GTFS_FGV_TTL):
        return _cache_gtfs_fgv["dades"]

    url = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gtfs-fgv/google_transit.zip"
    r = requests.get(url, timeout=15)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    stops = pd.read_csv(z.open("stops.txt"), dtype=str)
    routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
    calendar = pd.read_csv(z.open("calendar.txt"), dtype=str) if "calendar.txt" in z.namelist() else None
    calendar = _netejar_calendar(calendar)
    calendar_dates = pd.read_csv(z.open("calendar_dates.txt"), dtype=str) if "calendar_dates.txt" in z.namelist() else None

    dades = {
        "stops": stops, "routes": routes, "trips": trips,
        "stop_times": stop_times, "calendar": calendar, "calendar_dates": calendar_dates
    }
    _cache_gtfs_fgv["dades"] = dades
    _cache_gtfs_fgv["carregat_a"] = ara
    return dades


@app.route("/api/horaris-fgv-gtfs/<path:id_estacio>")
def api_horaris_fgv_gtfs(id_estacio):
    """Horaris programats (GTFS estàtic oficial) del TRAM d'Alacant (FGV),
    ja que FGV no publica cap API pública d'horaris en temps real."""
    from datetime import datetime, timedelta
    import zoneinfo
    tz_cat = zoneinfo.ZoneInfo("Europe/Madrid")

    try:
        dades = _carregar_gtfs_fgv()
        stops, routes, trips = dades["stops"], dades["routes"], dades["trips"]
        stop_times = dades["stop_times"]

        coincidents = stops[(stops["stop_id"] == str(id_estacio)) | (stops.get("stop_code") == str(id_estacio))]
        if coincidents.empty:
            return jsonify({"horaris": [], "error": f"Estació {id_estacio} no trobada al GTFS de FGV"})
        stop_ids = set(coincidents["stop_id"])

        trip_id_a_linia = dict(zip(trips["trip_id"], trips["route_id"]))
        trip_id_a_desti = dict(zip(trips["trip_id"], trips.get("trip_headsign", pd.Series(dtype=str)).fillna("")))
        trip_id_a_servei = dict(zip(trips["trip_id"], trips["service_id"]))
        route_id_a_nom = dict(zip(routes["route_id"], routes["route_short_name"]))

        serveis_avui = _serveis_actius_avui(dades["calendar"], dades["calendar_dates"])

        pas = stop_times[stop_times["stop_id"].isin(stop_ids) & stop_times["trip_id"].isin(trip_id_a_linia.keys())]

        ara = datetime.now(tz_cat)
        avui_str = ara.strftime("%Y%m%d")
        avui_iso = ara.strftime("%Y-%m-%d")
        horaris = []
        vist_claus = set()
        for _, row in pas.iterrows():
            trip_id = row["trip_id"]
            data_incrustada = _data_incrustada_trip_id(trip_id)
            if data_incrustada is not None:
                if data_incrustada != avui_iso:
                    continue
            elif serveis_avui is not None and trip_id_a_servei.get(trip_id) not in serveis_avui:
                continue
            hora_txt = row.get("departure_time") or row.get("arrival_time")
            if not hora_txt:
                continue
            hh, mm, ss = [int(x) for x in hora_txt.split(":")]
            moment = datetime.strptime(avui_str, "%Y%m%d").replace(
                hour=0, minute=0, second=0, tzinfo=tz_cat
            ) + timedelta(hours=hh, minutes=mm, seconds=ss)
            if moment < ara:
                continue
            linia = str(route_id_a_nom.get(trip_id_a_linia.get(trip_id), "")).strip()
            desti = str(trip_id_a_desti.get(trip_id, "")).strip()
            clau = (moment.strftime("%H:%M"), linia, desti)
            if clau in vist_claus:
                continue
            vist_claus.add(clau)
            horaris.append({
                "hora": moment.strftime("%H:%M"),
                "linia": linia,
                "destinacio": desti,
                "retard": 0,
                "ara": False,
                "_ordre": moment
            })
        horaris.sort(key=lambda x: x["_ordre"])
        for hh in horaris:
            del hh["_ordre"]
        return jsonify({"horaris": horaris[:8], "operador": "FGV"})
    except Exception as e:
        return jsonify({"horaris": [], "error": str(e)})


@app.route("/api/cerca-estacio-fgv")
def cerca_estacio_fgv():
    """Utilitat: cerca el stop_id del GTFS de FGV pel nom (p. ex. ?q=calp),
    per trobar el codi a posar a Sheets sense haver de baixar el GTFS a mà."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"error": "Passa un nom a cercar, p. ex. /api/cerca-estacio-fgv?q=calp"})
    try:
        dades = _carregar_gtfs_fgv()
        stops = dades["stops"]
        trobades = stops[stops["stop_name"].str.lower().str.contains(q, na=False)]
        resultat = trobades[["stop_id", "stop_name"] + (["stop_code"] if "stop_code" in trobades.columns else [])].to_dict(orient="records")
        return jsonify({"resultats": resultat})
    except Exception as e:
        return jsonify({"error": str(e)})



@app.route("/api/horaris-sncf/<path:id_estacio>")
def api_horaris_sncf(id_estacio):
    """Horaris en temps real SNCF via API Navitia. Accepta un o dos IDs separats per ;"""
    from datetime import datetime
    import zoneinfo
    sncf_key = os.environ.get("SNCF_API_KEY", "")
    if not sncf_key:
        return jsonify({"horaris": [], "error": "SNCF_API_KEY no configurada"})
    try:
        tz_paris = zoneinfo.ZoneInfo("Europe/Paris")
        ara = datetime.now(tz_paris)
        # Suporta múltiples IDs separats per ; (ex: "87611483;87611905")
        ids = [i.strip() for i in id_estacio.split(";") if i.strip()]
        totes_departures = []
        for id_est in ids:
            if not id_est.startswith("stop_area:"):
                id_est = f"stop_area:SNCF:{id_est}"
            url = f"https://api.sncf.com/v1/coverage/sncf/stop_areas/{id_est}/departures"
            params = {"count": 15}
            resp = requests.get(url, params=params, auth=(sncf_key, ""), timeout=8)
            data = resp.json()
            totes_departures.extend(data.get("departures", []))
        horaris = []
        vists = set()
        for dep in totes_departures:
            dt_str = dep.get("stop_date_time", {}).get("departure_date_time", "")
            if not dt_str:
                continue
            dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S").replace(tzinfo=tz_paris)
            if dt < ara:
                continue
            hora = dt.strftime("%H:%M")
            info = dep.get("display_informations", {})
            linia_codi = info.get("code") or info.get("label", "")
            NOMS_SNCF = {"P14": "Tren Groc"}
            linia = NOMS_SNCF.get(linia_codi, linia_codi)
            dest = info.get("direction", "").split(" (")[0]
            mode = info.get("physical_mode", "")
            # Afegir icona per distingir tren/autocar
            if "coach" in mode.lower() or "autocar" in mode.lower():
                mode_icon = "🚌"
            else:
                mode_icon = "🚆"
            clau = f"{hora}_{linia}_{dest}"
            if clau not in vists:
                vists.add(clau)
                horaris.append({
                    "hora": hora,
                    "linia": f"{mode_icon} {linia or mode}".strip(),
                    "destinacio": dest,
                    "retard": 0,
                    "ara": False
                })
        # Ordenar per hora i limitar
        horaris.sort(key=lambda h: h["hora"])
        return jsonify({"horaris": horaris[:10], "operador": "SNCF"})
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
            {"id": "cims",       "nom": "100 Cims",     "icon": "🏔️", "url": "/100-cims"},
            {"id": "colleccions","nom": "Millors rutes",  "icon": "⭐", "url": "/millors_rutes"},
            {"id": "articles",   "nom": "Articles",     "icon": "📖", "url": "/articles"},
        ]
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)

@app.route("/api/tram-debug")
def tram_debug():
    """Diagnòstic temporal de l'API de Tram."""
    tram_id = os.environ.get("TRAM_CLIENT_ID", "NO_ID")
    tram_secret = os.environ.get("TRAM_CLIENT_SECRET", "NO_SECRET")
    try:
        r_token = requests.post("https://opendata.tram.cat/connect/token", data={
            "grant_type": "client_credentials",
            "client_id": tram_id,
            "client_secret": tram_secret
        }, timeout=8)
        token_resp = r_token.json()
        token = token_resp.get("access_token", "")
        if not token:
            return jsonify({"error": "no_token", "resp": token_resp})
        r2 = requests.get("https://opendata.tram.cat/api/v1/stopTimes/1001",
            headers={"Authorization": f"Bearer {token}"}, timeout=8)
        return jsonify({
            "token_ok": True,
            "client_id": tram_id,
            "stopTimes_status": r2.status_code,
            "stopTimes_resp": r2.text[:500]
        })
    except Exception as e:
        return jsonify({"error": str(e)})
