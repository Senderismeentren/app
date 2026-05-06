# ============================================================
# SENDERISME EN TREN — v9.1
# ============================================================

import streamlit as st
import pandas as pd
import re
import os
import requests
import folium
from streamlit_folium import st_folium
import gpxpy
import gspread
from google.oauth2.service_account import Credentials

# 1. CONFIGURACIÓ DE LA PÀGINA
st.set_page_config(
    page_title="Senderisme en tren", 
    layout="wide", 
    page_icon="https://avatars.githubusercontent.com/u/279401247?v=4"
)

# --- CAPÇALERA ---
st.markdown(f'''
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px; background-color: #f0f2f6; padding: 15px 20px; border-radius: 10px;">
        <img src="https://avatars.githubusercontent.com/u/279401247?v=4" style="width: 50px; height: 50px; border-radius: 50%;">
        <div>
            <h1 style="margin: 0; font-size: 28px; color: #000000;">Senderisme en tren</h1>
            <p style="margin: 4px 0 0 0; font-size: 15px; color: #555;">Rutes i excursions a peu amb accés en tren, metro, cremallera o funicular.</p>
        </div>
    </div>
''', unsafe_allow_html=True)

# --- DICCIONARI D'OPERADORS ---
OPERADORS_INFO = {
    "rodalies": {
        "url": "https://rodalies.gencat.cat/ca/inici/index.html", 
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg",
    },
    "fgc": {
        "url": "https://www.fgc.cat/cercador/", 
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg",
    },
    "metro": {
        "url": "https://www.tmb.cat/ca/barcelona/horaris-metro",
        "logo": None,
    },
    "tram": {
        "url": "https://www.tram.cat/ca/linies-i-horaris",
        "logo": None,
    },
    "renfe": {
        "url": "https://www.renfe.com/es/ca/viajar/informacion-util/horarios",
        "logo": None,
    },
    "tren dels llacs": {
        "url": "https://www.renfe.com/es/ca/viajar/informacion-util/horarios",
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-trendelsllacs.svg",
    },
    "alta velocitat": {
        "url": "https://www.renfe.com/es/ca/viajar/informacion-util/horarios",
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-altavelocitat.svg",
    },
    "adif": {
        "url": "https://www.adif.es",
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-ADIF.svg",
    },
    "sncf": {
        "url": "https://www.sncf-connect.com",
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-SNCF.svg",
    },
    "cremallera de núria": {
        "url": "https://www.valldenuria.cat/ca/cremallera",
        "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-cremalleranuria.svg",
    }
}

# --- DICCIONARI DE CATEGORIES AMB ICONES ---
CATEGORIES_ICONES = {
    "100 cims": "🏔️",
    "búnquer": "🪖",
    "castell": "🏰",
    "cova": "🕳️",
    "dolmen": "🪨",
    "ermita": "⛪",
    "ferrocarril": "🚂",
    "jaciment ibèric": "🏛️",
    "museu": "🖼️",
    "pintures rupestres": "🎨",
    "pont": "🌉",
    "època romana": "🏟️",
    "santuari": "🙏",
    "torre del telègraf": "📡",
    "torre": "🗼",
    "patrimoni unesco": "🌍",
    "bosc": "🌲",
    "camí equipat": "🧗",
    "cascada": "💧",
    "cim": "⛰️",
    "cingleres": "🪨",
    "gorgs": "🌊",
    "litoral": "🏖️",
    "platja": "🏝️",
    "riu": "🏞️",
    "pantà": "💦",
}

BASE_LOGO_LINIA  = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL     = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
BASE_IMATGE_URL  = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/main/imatges/ruta-{id:03d}.jpg"
LOGO_SIZE = 22
SHEET_ID  = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"
SHEET_NAME = "Rutes"

# --- FUNCIÓ: carrega dades de Google Sheets ---
@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", 
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full   = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    dades  = full.get_all_records()
    return pd.DataFrame(dades)

# --- FUNCIÓ: comprova si una imatge existeix ---
def imatge_existeix(url):
    try:
        r = requests.head(url, timeout=3)
        return r.status_code == 200
    except:
        return False

# --- FUNCIÓ: genera els logos de línies ---
def logos_linies_html(linies_str):
    if not linies_str or str(linies_str).strip().lower() in ("nan", ""):
        return ""
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()]
    imgs = []
    for linia in linies:
        url = BASE_LOGO_LINIA.format(linia=linia)
        imgs.append(f'<img src="{url}" width="{LOGO_SIZE}" style="vertical-align: middle; margin-left: 4px;" title="{linia}">')
    return "".join(imgs)

# --- FUNCIÓ: genera logos + link HORARI per un o més operadors ---
def bloc_operadors_html(op_str):
    if not op_str or str(op_str).strip().lower() in ("nan", ""):
        op_str = "rodalies"
    operadors = [o.strip().lower() for o in re.split(r";", str(op_str)) if o.strip()]
    parts = []
    for op in operadors:
        info = OPERADORS_INFO.get(op, OPERADORS_INFO["rodalies"])
        logo = f'<img src="{info["logo"]}" width="{LOGO_SIZE}" style="vertical-align: middle; margin-right: 4px;">' if info.get("logo") else ""
        link = f'<a href="{info["url"]}" target="_blank" style="font-size: 13px; margin-left: 4px; color: #007bff; text-decoration: none; font-weight: bold;">HORARI</a>'
        parts.append(f'{logo}{link}')
    return "&nbsp;&nbsp;".join(parts)

# --- FUNCIÓ: genera targetes de punts d'interès ---
def punts_interes_html(elements_str, categories_str):
    if not elements_str or str(elements_str).strip().lower() in ("nan", ""):
        return ""
    elements = [e.strip() for e in re.split(r";", str(elements_str)) if e.strip()]
    categories = [c.strip().lower() for c in re.split(r";", str(categories_str)) if c.strip()] if categories_str and str(categories_str).strip().lower() not in ("nan", "") else []

    targetes = []
    for i, element in enumerate(elements):
        categoria = categories[i] if i < len(categories) else ""
        icona = CATEGORIES_ICONES.get(categoria, "📍")
        targetes.append(
            "<div style=\"display:flex;align-items:center;gap:10px;background:#f8f9fa;"
            "border-radius:10px;padding:10px 14px;font-size:14px;color:#333;\">"
            f"<span style=\"font-size:22px;\">{icona}</span>"
            f"<span>{element}</span>"
            "</div>"
        )

    grid = "".join(targetes)
    return (
        "<div style=\"margin-top:16px;\">"
        "<div style=\"font-size:16px;font-weight:bold;color:#333;margin-bottom:10px;\">📌 Punts d'interès</div>"
        "<div style=\"display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;\">"
        f"{grid}"
        "</div></div>"
    )

# --- FUNCIÓ: carrega i mostra el mapa GPX ---
def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
    gpx_url = BASE_GPX_URL.format(id=int(ruta_id))
    try:
        resp = requests.get(gpx_url, timeout=5)
        if resp.status_code != 200:
            return False
        gpx = gpxpy.parse(resp.text)
        punts = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    punts.append((point.latitude, point.longitude))
        if not punts:
            return False
        centre = (sum(p[0] for p in punts) / len(punts),
                  sum(p[1] for p in punts) / len(punts))
        m = folium.Map(location=centre, tiles="OpenStreetMap")
        m.fit_bounds([[min(p[0] for p in punts), min(p[1] for p in punts)],
                      [max(p[0] for p in punts), max(p[1] for p in punts)]])
        folium.PolyLine(punts, color="#2d9e6b", weight=4, opacity=0.9).add_to(m)
        if lat_s and lng_s:
            folium.Marker(
                location=[lat_s, lng_s],
                tooltip="Sortida",
                icon=folium.Icon(color="green", icon="train", prefix="fa")
            ).add_to(m)
        if lat_a and lng_a and (lat_s != lat_a or lng_s != lng_a):
            folium.Marker(
                location=[lat_a, lng_a],
                tooltip="Arribada",
                icon=folium.Icon(color="red", icon="flag", prefix="fa")
            ).add_to(m)
        st_folium(m, width=None, height=350, returned_objects=[])
        return True
    except Exception:
        return False

# --- CÀRREGA DE DADES ---
try:
    df_raw = carregar_dades()
except Exception as e:
    st.error(f"Error connectant amb Google Sheets: {e}")
    st.stop()

try:
    df_raw.columns = df_raw.columns.str.strip().str.lower()

    def buscar_col(llista):
        for c in df_raw.columns:
            for p in llista:
                if p in str(c): return c
        return None

    cols = {
        "id":       buscar_col(["id_ruta", "id"]),
        "ruta":     buscar_col(["nom_de_la_ruta", "nom ruta"]),
        "desc":     buscar_col(["descripció", "descripcio", "subtitol"]),
        "km":       buscar_col(["km"]),
        "cims":     buscar_col(["100_cims", "100cims"]),
        "sortida":  buscar_col(["estació_sortida", "sortida"]),
        "op_s":     buscar_col(["operador_sortida", "operador s"]),
        "arribada": buscar_col(["estació_arribada", "arribada"]),
        "op_a":     buscar_col(["operador_arribada", "operador a"]),
        "linia_s":  buscar_col(["linies_sortida"]),
        "linia_a":  buscar_col(["linies_arribada"]),
        "comarca":  buscar_col(["comarca"]),
        "espai":    buscar_col(["espai_natural"]),
        "desn":     buscar_col(["desnivell_positiu", "desnivell"]),
        "dif":      buscar_col(["dificultat"]),
        "wiki":     buscar_col(["enllaç_wikiloc", "wikiloc"]),
        "elements": buscar_col(["elements_interès", "elements_interes"]),
        "cats":     buscar_col(["categories_elements_interès", "categories_elements_interes"]),
        "lat_s":    buscar_col(["lat_sortida", "lat_s"]),
        "lng_s":    buscar_col(["lng_sortida", "lng_s"]),
        "lat_a":    buscar_col(["lat_arribada", "lat_a"]),
        "lng_a":    buscar_col(["lng_arribada", "lng_a"]),
    }

    df = df_raw.dropna(subset=[cols["ruta"]]).copy()
    df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["desn"]:
        df[cols["desn"]] = pd.to_numeric(df[cols["desn"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    def get_unique(col_name):
        if col_name and col_name in df.columns:
            vals = df[col_name].dropna().astype(str)
            res = set()
            for v in vals:
                for s in re.split(";|,", v):
                    if s.strip(): res.add(s.strip())
            return sorted(list(res))
        return []

    # --- FILTRES SIDEBAR ---
    st.sidebar.header("🔎 Filtres")
    st.sidebar.markdown('<img src="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-100cims.svg" width="80" style="margin-bottom: 5px;">', unsafe_allow_html=True)
    sel_100cims = st.sidebar.checkbox("Rutes amb 100 Cims")
    cerca = st.sidebar.text_input("📝 Paraula clau")
    sel_sortida = st.sidebar.multiselect("🚉 Estació de sortida", get_unique(cols["sortida"]))
    sel_linia = st.sidebar.multiselect("🚆 Línia de tren", get_unique(cols["linia_s"]))
    sel_dif = st.sidebar.multiselect("🧗 Dificultat", get_unique(cols["dif"]))
    min_desn = float(df[cols["desn"]].min()) if cols["desn"] else 0.0
    max_desn = float(df[cols["desn"]].max()) if cols["desn"] else 9999.0
    sel_desn = st.sidebar.slider("📈 Desnivell (m)", min_desn, max_desn, (min_desn, max_desn))
    sel_comarca = st.sidebar.multiselect("📍 Comarca", get_unique(cols["comarca"]))
    sel_espai = st.sidebar.multiselect("🌲 Espai natural", get_unique(cols["espai"]))
    min_km, max_km = float(df[cols["km"]].min()), float(df[cols["km"]].max())
    sel_km = st.sidebar.slider("📏 Distància (km)", min_km, max_km, (min_km, max_km))

    # --- APLICAR FILTRES ---
    f = df.copy()
    if sel_100cims and cols["cims"]:
        f = f[f[cols["cims"]].astype(str).str.strip().str.lower() == "si"]
    if cerca:
        f = f[f[cols["ruta"]].str.contains(cerca, case=False, na=False)]
    if sel_sortida:
        f = f[f[cols["sortida"]].astype(str).apply(lambda x: any(s in x for s in sel_sortida))]
    if sel_linia:
        f = f[f[cols["linia_s"]].astype(str).apply(lambda x: any(l in x for l in sel_linia))]
    if sel_dif:
        f = f[f[cols["dif"]].astype(str).apply(lambda x: any(d in x for d in sel_dif))]
    if sel_comarca:
        f = f[f[cols["comarca"]].astype(str).apply(lambda x: any(c in x for c in sel_comarca))]
    if sel_espai:
        f = f[f[cols["espai"]].astype(str).apply(lambda x: any(e in x for e in sel_espai))]
    f = f[(f[cols["km"]] >= sel_km[0]) & (f[cols["km"]] <= sel_km[1])]
    if cols["desn"]:
        f = f[(f[cols["desn"]] >= sel_desn[0]) & (f[cols["desn"]] <= sel_desn[1])]

    st.write(f"**Resultats: {len(f)} rutes**")

    # --- BUCLE DE RUTES ---
    for _, row in f.iterrows():
        ruta_id = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else None
        nom_ruta = row[cols["ruta"]]
        desc = str(row[cols["desc"]]).strip() if cols["desc"] and pd.notna(row[cols["desc"]]) else ""

        # Variables estacions (cal abans de la capçalera)
        s_est = str(row[cols["sortida"]]).strip()
        a_est = str(row[cols["arribada"]]).strip()

        # CAPÇALERA DE LA RUTA
        imatge_url = BASE_IMATGE_URL.format(id=ruta_id) if ruta_id else None
        te_imatge = imatge_existeix(imatge_url) if imatge_url else False

        if te_imatge:
            st.markdown(f'''
                <div style="position: relative; border-radius: 12px; overflow: hidden; margin-top: 30px; margin-bottom: 0;">
                    <img src="{imatge_url}" style="width: 100%; height: 200px; object-fit: cover; display: block;">
                    <div style="position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, rgba(0,0,0,0.75)); padding: 20px;">
                        <span style="background: #2d9e6b; color: white; font-size: 16px; font-weight: bold; padding: 5px 14px; border-radius: 20px;">RUTA {ruta_id}</span>
                        <div style="margin-top: 8px; font-size: 38px; font-weight: bold; color: white;">
                            {s_est} &nbsp;→&nbsp; {a_est}
                        </div>
                    </div>
                </div>
                <div style="background: white; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 12px 12px; padding: 16px 20px; margin-bottom: 10px;">
                    <h2 style="margin: 0 0 4px 0; font-size: 24px; color: #111;">{nom_ruta}</h2>
                    <p style="margin: 0; font-size: 14px; color: #666;">{desc}</p>
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
                <div style="background: #f0f2f6; border-radius: 12px; padding: 16px 20px; margin-top: 30px; margin-bottom: 10px;">
                    <span style="background: #2d9e6b; color: white; font-size: 16px; font-weight: bold; padding: 5px 14px; border-radius: 20px;">RUTA {ruta_id}</span>
                    <div style="margin-top: 8px; font-size: 22px; font-weight: bold; color: #111;">
                        🚉 {s_est} &nbsp;→&nbsp; 🏁 {a_est}
                    </div>
                    <h2 style="margin: 8px 0 4px 0; font-size: 24px; color: #111;">{nom_ruta}</h2>
                    <p style="margin: 0; font-size: 14px; color: #666;">{desc}</p>
                </div>
            ''', unsafe_allow_html=True)

        # MÈTRIQUES
        st.markdown(f'''
            <div style="display: flex; gap: 12px; margin: 12px 0;">
                <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 18px; color: #888;">Distància</div>
                    <div style="font-size: 22px; font-weight: bold; color: #111;"> {row[cols["km"]]} km</div>
                </div>
                <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 18px; color: #888;">Desnivell</div>
                    <div style="font-size: 22px; font-weight: bold; color: #111;"> +{row[cols["desn"]]} m</div>
                </div>
                <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px; text-align: center;">
                    <div style="font-size: 18px; color: #888;">Dificultat</div>
                    <div style="font-size: 22px; font-weight: bold; color: #111;"> {row[cols["dif"]]}</div>
                </div>
            </div>
        ''', unsafe_allow_html=True)

        # ESTACIONS
        op_s_raw = str(row[cols["op_s"]]) if pd.notna(row[cols["op_s"]]) else "rodalies"
        op_a_raw = str(row[cols["op_a"]]) if pd.notna(row[cols["op_a"]]) else "rodalies"
        bloc_s  = bloc_operadors_html(op_s_raw)
        bloc_a  = bloc_operadors_html(op_a_raw)
        logos_s = logos_linies_html(row[cols["linia_s"]])
        logos_a = logos_linies_html(row[cols["linia_a"]])

        if s_est.lower() == a_est.lower():
            st.markdown(f'''
                <div style="display: flex; gap: 12px; margin: 12px 0;">
                    <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px;">
                        <div style="font-size: 12px; color: #2d9e6b; font-weight: bold;">Sortida/Arribada</div>
                        <div style="font-size: 20px; font-weight: bold; margin: 4px 0;">🚉 <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none; color:#111;">{s_est}</a></div>
                        <div style="margin-top: 6px;">{bloc_s} {logos_s}</div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
                <div style="display: flex; gap: 12px; margin: 12px 0;">
                    <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px;">
                        <div style="font-size: 18px; color: #2d9e6b; font-weight: bold;">Sortida</div>
                        <div style="font-size: 22px; font-weight: bold; margin: 4px 0;">🚉 {s_est} <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none; font-size:16px;">📍</a></div>
                        <div style="margin-top: 6px;">{bloc_s} {logos_s}</div>
                    </div>
                    <div style="flex: 1; background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px;">
                        <div style="font-size: 18px; color: #2d9e6b; font-weight: bold;">Arribada</div>
                        <div style="font-size: 22px; font-weight: bold; margin: 4px 0;">🏁 {a_est} <a href="https://www.google.com/maps/search/{a_est}+estacio" target="_blank" style="text-decoration:none; font-size:16px;">📍</a></div>
                        <div style="margin-top: 6px;">{bloc_a} {logos_a}</div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)

        # MAPA GPX
        if ruta_id:
            lat_s = row[cols["lat_s"]] if cols["lat_s"] and pd.notna(row[cols["lat_s"]]) else None
            lng_s = row[cols["lng_s"]] if cols["lng_s"] and pd.notna(row[cols["lng_s"]]) else None
            lat_a = row[cols["lat_a"]] if cols["lat_a"] and pd.notna(row[cols["lat_a"]]) else None
            lng_a = row[cols["lng_a"]] if cols["lng_a"] and pd.notna(row[cols["lng_a"]]) else None
            mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a)

        # PUNTS D'INTERÈS
        elements_str = row[cols["elements"]] if cols["elements"] and pd.notna(row[cols["elements"]]) else ""
        cats_str = row[cols["cats"]] if cols["cats"] and pd.notna(row[cols["cats"]]) else ""
        if elements_str:
            st.markdown(punts_interes_html(elements_str, cats_str), unsafe_allow_html=True)

        # WIKILOC
        if pd.notna(row[cols["wiki"]]):
            st.markdown(f'<a href="{row[cols["wiki"]]}" target="_blank" style="background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: bold; display: inline-block; margin: 12px 0;">🔗 Veure a Wikiloc</a>', unsafe_allow_html=True)

        st.markdown(f'<div style="font-size: 14px; color: #888; margin-top: 8px;">📍 <b>Comarca:</b> {row[cols["comarca"]]} &nbsp;|&nbsp; 🌲 <b>Espai:</b> {row[cols["espai"]]}</div>', unsafe_allow_html=True)
        st.markdown("<hr style='margin: 30px 0; opacity: 0.15;'>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"S'ha produït un error: {e}")
