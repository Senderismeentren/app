# ============================================================
# SENDERISME EN TREN — v7
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
        <h1 style="margin: 0; font-size: 28px; color: #000000;">Senderisme en tren</h1>
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

BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
LOGO_SIZE = 22
SHEET_ID  = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"
SHEET_NAME = "SET_excel_app"

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

# --- FUNCIÓ: genera llista de punts d'interès ---
def punts_interes_html(punts_str):
    if not punts_str or str(punts_str).strip().lower() in ("nan", ""):
        return ""
    punts = [p.strip() for p in re.split(r"[;,]", str(punts_str)) if p.strip()]
    items = "".join([f'<li style="font-size: 15px; color: #333;">{p}</li>' for p in punts])
    return f'''
        <div style="margin-top: 8px;">
            <span style="font-size: 15px; font-weight: bold; color: #444;">📌 Punts d'interès:</span>
            <ul style="margin: 4px 0 0 20px; padding: 0;">{items}</ul>
        </div>
    '''

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
        m = folium.Map(location=centre, zoom_start=12, tiles="OpenStreetMap")
        folium.PolyLine(punts, color="#E63946", weight=3, opacity=0.9).add_to(m)

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

        st_folium(m, width=700, height=400, returned_objects=[])
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
        "id":      buscar_col(["id_ruta", "id"]),
        "ruta":    buscar_col(["nom_de_la_ruta", "nom ruta"]),
        "km":      buscar_col(["km"]),
        "cims":    buscar_col(["100", "cim", "s/n"]),
        "sortida": buscar_col(["estació_sortida", "sortida"]),
        "op_s":    buscar_col(["operador_sortida", "operador s"]),
        "arribada":buscar_col(["estació_arribada", "arribada"]),
        "op_a":    buscar_col(["operador_arribada", "operador a"]),
        "linia_s": buscar_col(["linies_sortida"]),
        "linia_a": buscar_col(["linies_arribada"]),
        "comarca": buscar_col(["comarca"]),
        "espai":   buscar_col(["espai_natural"]),
        "desn":    buscar_col(["desnivell_positiu", "desnivell"]),
        "dif":     buscar_col(["dificultat"]),
        "wiki":    buscar_col(["enllaç_wikiloc", "wikiloc"]),
        "punts":   buscar_col(["punts_interès_tipus", "punts_interes_tipus"]),
        "lat_s":   buscar_col(["lat_sortida", "lat_s"]),
        "lng_s":   buscar_col(["lng_sortida", "lng_s"]),
        "lat_a":   buscar_col(["lat_arribada", "lat_a"]),
        "lng_a":   buscar_col(["lng_arribada", "lng_a"]),
    }

    df = df_raw.dropna(subset=[cols["ruta"]]).copy()
    df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    # --- FILTRES SIDEBAR ---
    st.sidebar.header("🔎 Filtres")
    cerca = st.sidebar.text_input("📝 Paraula clau")
    
    def get_unique(col_name):
        if col_name and col_name in df.columns:
            vals = df[col_name].dropna().astype(str)
            res = set()
            for v in vals:
                for s in re.split(";|,", v):
                    if s.strip(): res.add(s.strip())
            return sorted(list(res))
        return []

    sel_comarca = st.sidebar.multiselect("📍 Comarca", get_unique(cols["comarca"]))
    sel_espai   = st.sidebar.multiselect("🌲 Espai natural", get_unique(cols["espai"]))
    min_km, max_km = float(df[cols["km"]].min()), float(df[cols["km"]].max())
    sel_km = st.sidebar.slider("📏 Distància (km)", min_km, max_km, (min_km, max_km))

    f = df.copy()
    if cerca:       f = f[f[cols["ruta"]].str.contains(cerca, case=False, na=False)]
    if sel_comarca: f = f[f[cols["comarca"]].astype(str).apply(lambda x: any(c in x for c in sel_comarca))]
    if sel_espai:   f = f[f[cols["espai"]].astype(str).apply(lambda x: any(e in x for e in sel_espai))]
    f = f[(f[cols["km"]] >= sel_km[0]) & (f[cols["km"]] <= sel_km[1])]

    st.write(f"**Resultats: {len(f)} rutes**")

    # --- BUCLE DE RUTES ---
    for _, row in f.iterrows():
        st.markdown(f'<h2 style="color: #000000; margin-top: 25px; font-size: 30px; font-weight: bold;">Ruta {int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""}: {row[cols["ruta"]]}</h2>', unsafe_allow_html=True)
        
        s_est = str(row[cols["sortida"]]).strip()
        a_est = str(row[cols["arribada"]]).strip()
        op_s_raw = str(row[cols["op_s"]]) if pd.notna(row[cols["op_s"]]) else "rodalies"
        op_a_raw = str(row[cols["op_a"]]) if pd.notna(row[cols["op_a"]]) else "rodalies"

        bloc_s  = bloc_operadors_html(op_s_raw)
        bloc_a  = bloc_operadors_html(op_a_raw)
        logos_s = logos_linies_html(row[cols["linia_s"]])
        logos_a = logos_linies_html(row[cols["linia_a"]])

        # BLOC ESTACIONS
        if s_est.lower() == a_est.lower():
            st.markdown(f'''
                <div style="font-size: 18px; margin-bottom: 4px;">
                    <b>🚉 Sortida/Arribada:</b> {s_est}
                    <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none;">📍</a>
                </div>
                <div style="margin-left: 24px; margin-bottom: 12px;">
                    {bloc_s} {logos_s}
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
                <div style="font-size: 18px; margin-bottom: 4px;">
                    <b>🚉 Sortida:</b> {s_est}
                    <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none;">📍</a>
                </div>
                <div style="margin-left: 24px; margin-bottom: 12px;">
                    {bloc_s} {logos_s}
                </div>
                <div style="font-size: 18px; margin-bottom: 4px;">
                    <b>🏁 Arribada:</b> {a_est}
                    <a href="https://www.google.com/maps/search/{a_est}+estacio" target="_blank" style="text-decoration:none;">📍</a>
                </div>
                <div style="margin-left: 24px; margin-bottom: 12px;">
                    {bloc_a} {logos_a}
                </div>
            ''', unsafe_allow_html=True)

        # MÈTRIQUES
        st.markdown(f"""
            <div style="display: flex; gap: 30px; margin: 15px 0; font-size: 20px;">
                <span>📏 <b>{row[cols['km']]} km</b></span>
                <span>📈 <b>{row[cols['desn']]} m</b></span>
                <span>🧗 <b>{row[cols['dif']]}</b></span>
            </div>
        """, unsafe_allow_html=True)

        # PUNTS D'INTERÈS
        if cols["punts"] and pd.notna(row[cols["punts"]]):
            st.markdown(punts_interes_html(row[cols["punts"]]), unsafe_allow_html=True)

        # MAPA GPX
        if pd.notna(row[cols["id"]]):
            lat_s = row[cols["lat_s"]] if cols["lat_s"] and pd.notna(row[cols["lat_s"]]) else None
            lng_s = row[cols["lng_s"]] if cols["lng_s"] and pd.notna(row[cols["lng_s"]]) else None
            lat_a = row[cols["lat_a"]] if cols["lat_a"] and pd.notna(row[cols["lat_a"]]) else None
            lng_a = row[cols["lng_a"]] if cols["lng_a"] and pd.notna(row[cols["lng_a"]]) else None
            mostrar_mapa_gpx(row[cols["id"]], lat_s, lng_s, lat_a, lng_a)

        # WIKILOC
        if pd.notna(row[cols["wiki"]]):
            st.markdown(f'<a href="{row[cols["wiki"]]}" target="_blank" style="background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 18px; font-weight: bold; display: inline-block; margin: 10px 0;">🔗 Veure a Wikiloc</a>', unsafe_allow_html=True)

        st.markdown(f'<div style="font-size: 16px; color: #444;">📍 <b>Comarca:</b> {row[cols["comarca"]]} | 🌲 <b>Espai:</b> {row[cols["espai"]]}</div>', unsafe_allow_html=True)
        st.markdown("<hr style='margin: 25px 0; opacity: 0.2;'>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"S'ha produït un error: {e}")
