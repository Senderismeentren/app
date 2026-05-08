# ============================================================
# SENDERISME EN TREN — v18 (VERSIÓ COMPLETA I ESTABLE)
# ============================================================

import streamlit as st
import pandas as pd
import re
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

# --- ESTILS CSS ---
st.markdown("""
    <style>
    .titol-ruta {
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 20px !important;
        line-height: 1.2;
    }
    .ruta-container {
        background-color: #f2f2f2;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
    }
    .metrica-box {
        flex: 1;
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 8px;
        display: flex;
        flex-direction: column;
        min-width: 100px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- DICCIONARIS ---
OPERADORS_INFO = {
    "rodalies": {"url": "https://rodalies.gencat.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg"},
    "fgc": {"url": "https://www.fgc.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg"},
    "tren dels llacs": {"url": "https://www.trendelsllacs.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-trendelsllacs.svg"},
    "cremallera de núria": {"url": "https://www.valldenuria.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-cremalleranuria.svg"},
}

CATEGORIES_ICONES = {
    "100 cims": "🏔️", "búnquer": "🪖", "castell": "🏰", "cim": "⛰️", "cascada": "💧", "riu": "🏞️", "ermita": "⛪"
}

DIFICULTAT_COLOR = {
    "fàcil": "#1D9E75", "facil": "#1D9E75",
    "mitjana": "#EF9F27", "mitja": "#EF9F27",
    "difícil": "#E24B4A", "dificil": "#E24B4A",
    "molt difícil": "#9B1B1B"
}

BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"

# --- FUNCIONS ---
@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full = client.open_by_key("12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE").worksheet("Rutes")
    return pd.DataFrame(full.get_all_records())

def get_col(df, posibles_noms):
    for nom in posibles_noms:
        for col in df.columns:
            if nom.lower() in col.lower().strip(): return col
    return None

def parse_coord(coord_str):
    try:
        parts = str(coord_str).split(",")
        return float(parts[0].strip()), float(parts[1].strip())
    except: return None, None

def logos_linies_html(linies_str):
    if not linies_str or str(linies_str).lower() == "nan": return ""
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()]
    return "".join([f'<img src="{BASE_LOGO_LINIA.format(linia=l)}" width="18" style="margin-left:3px;" title="{l}">' for l in linies])

def bloc_estacio_html(op_str, linies_str):
    op_str = str(op_str).lower() if pd.notna(op_str) else "rodalies"
    operadors = [o.strip() for o in op_str.split(";")]
    parts = []
    for op in operadors:
        info = OPERADORS_INFO.get(op, OPERADORS_INFO["rodalies"])
        logo = f'<img src="{info["logo"]}" width="18" style="margin-right:3px;">' if info.get("logo") else ""
        horari = f'<a href="{info["url"]}" target="_blank" style="font-size:11px; color:#007bff; text-decoration:none; font-weight:bold; border:1px solid #007bff; padding:1px 4px; border-radius:3px; margin-left:5px;">HORARI</a>'
        parts.append(f"{logo}{logos_linies_html(linies_str)}{horari}")
    return " ".join(parts)

# --- LÒGICA DE DADES ---
df_raw = carregar_dades()
c = {
    "id": get_col(df_raw, ["id"]),
    "ruta": get_col(df_raw, ["nom_de_la_ruta", "nom ruta"]),
    "desc": get_col(df_raw, ["descripció", "descripcio"]),
    "km": get_col(df_raw, ["km"]),
    "dif": get_col(df_raw, ["dificultat"]),
    "sortida": get_col(df_raw, ["estació_sortida", "sortida"]),
    "arribada": get_col(df_raw, ["estació_arribada", "arribada"]),
    "op_s": get_col(df_raw, ["operador_sortida"]),
    "op_a": get_col(df_raw, ["operador_arribada"]),
    "lin_s": get_col(df_raw, ["linies_sortida"]),
    "lin_a": get_col(df_raw, ["linies_arribada"]),
    "desn": get_col(df_raw, ["desnivell_positiu", "desnivell"]),
    "comarca": get_col(df_raw, ["comarca"]),
    "espai": get_col(df_raw, ["espai_natural"]),
    "cims": get_col(df_raw, ["100_cims"]),
    "wiki": get_col(df_raw, ["wikiloc"]),
    "coord_s": get_col(df_raw, ["coordenades_sortida"]),
    "elements": get_col(df_raw, ["elements_interès"]),
    "cats": get_col(df_raw, ["categories_elements"])
}

# --- SIDEBAR ---
st.sidebar.image("https://avatars.githubusercontent.com/u/279401247?v=4", width=80)
st.sidebar.header("🔎 Filtres")
sel_100cims = st.sidebar.checkbox("Rutes amb 100 Cims")
cerca = st.sidebar.text_input("📝 Paraula clau")
sel_comarca = st.sidebar.multiselect("📍 Comarca", sorted(df_raw[c["comarca"]].unique()) if c["comarca"] else [])
sel_dif = st.sidebar.multiselect("🧗 Dificultat", ["fàcil", "mitjana", "difícil", "molt difícil"])

# --- FILTRATGE ---
f = df_raw.copy()
if sel_100cims: f = f[f[c["cims"]].astype(str).str.lower().str.contains("si", na=False)]
if cerca: f = f[f[c["ruta"]].str.contains(cerca, case=False, na=False)]
if sel_comarca: f = f[f[c["comarca"]].isin(sel_comarca)]
if sel_dif: f = f[f[c["dif"]].str.lower().isin(sel_dif)]

# --- RENDER PÀGINA ---
st.markdown('<h1>🚂 Senderisme en tren</h1>', unsafe_allow_html=True)
st.write(f"S'han trobat **{len(f)}** rutes que encaixen amb els teus filtres.")

for _, row in f.iterrows():
    rid = row[c["id"]]
    nom = row[c["ruta"]]
    desc = row[c["desc"]] if pd.notna(row[c["desc"]]) else ""
    dif = str(row[c["dif"]]).lower()
    color = DIFICULTAT_COLOR.get(dif, "#888")
    
    st.markdown(f"""
    <div class="ruta-container">
        <div style="border-left: 8px solid {color}; background: white; padding: 15px; border-radius: 4px 10px 10px 4px; display: flex; align-items: center; gap: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px;">
            <div style="width: 35px; height: 35px; border-radius: 50%; background: {color}; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold;">{rid}</div>
            <div style="flex: 1;">
                <div class="titol-ruta">{nom}</div>
                <div style="font-size: 13px; color: #666;">{desc}</div>
            </div>
            <div style="background: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;">{dif}</div>
        </div>

        <div style="display: flex; gap: 10px; margin-bottom: 15px;">
            <div class="metrica-box">
                <span style="font-size: 10px; color: #888; font-weight: bold;">DISTÀNCIA</span>
                <span style="font-size: 15px; font-weight: bold;">{row[c["km"]]} km</span>
            </div>
            <div class="metrica-box">
                <span style="font-size: 10px; color: #888; font-weight: bold;">PUJADA</span>
                <span style="font-size: 15px; font-weight: bold;">+{row[c["desn"]]} m</span>
            </div>
        </div>

        <div style="background: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 18px; margin-right: 10px;">🟢</span>
                <strong style="min-width: 80px; font-size: 13px;">SORTIDA:</strong>
                <span style="color: #007bff; font-weight: bold; font-size: 14px;">{row[c["sortida"]]}</span>
                <div style="margin-left: auto;">{bloc_estacio_html(row[c["op_s"]], row[c["lin_s"]])}</div>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="font-size: 18px; margin-right: 10px;">🔴</span>
                <strong style="min-width: 80px; font-size: 13px;">ARRIBADA:</strong>
                <span style="color: #007bff; font-weight: bold; font-size: 14px;">{row[c["arribada"]]}</span>
                <div style="margin-left: auto;">{bloc_estacio_html(row[c["op_a"]], row[c["lin_a"]])}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ACCIONS (MAPA I WIKILOC)
    col_map, col_wiki = st.columns(2)
    with col_map:
        with st.expander("🗺️ Mapa del recorregut"):
            gpx_url = BASE_GPX_URL.format(id=int(rid))
            try:
                resp = requests.get(gpx_url, timeout=5)
                if resp.status_code == 200:
                    gpx = gpxpy.parse(resp.text)
                    punts = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
                    m = folium.Map(location=punts[0], zoom_start=13)
                    folium.PolyLine(punts, color="#007bff", weight=5).add_to(m)
                    st_folium(m, width="100%", height=300, key=f"map_{rid}")
                else: st.warning("GPX no trobat.")
            except: st.error("Error carregant el mapa.")
    
    with col_wiki:
        if pd.notna(row[c["wiki"]]):
            st.link_button("🔗 Veure a Wikiloc", str(row[c["wiki"]]), use_container_width=True)
        else:
            st.info("No hi ha enllaç a Wikiloc.")
