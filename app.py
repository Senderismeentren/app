# ============================================================
# SENDERISME EN TREN — v18 (VERSIÓ CORREGIDA I COMPLETA)
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

# --- ESTILS CSS (MÀXIM CONTRAST I IDENTITAT) ---
st.markdown("""
    <style>
    .titol-ruta {
        color: #000000 !important;
        font-weight: 850 !important;
        font-size: 24px !important;
        line-height: 1.2;
    }
    .ruta-container {
        background-color: #f2f2f2;
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #d1d1d1;
        margin-bottom: 40px;
    }
    .caixa-blanca {
        background: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
    }
    .metrica-box {
        flex: 1;
        background: white;
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        min-width: 100px;
    }
    .metrica-valor {
        font-size: 18px;
        font-weight: 800;
        color: #000;
    }
    </style>
""", unsafe_allow_html=True)

# --- DICCIONARIS DE CONFIGURACIÓ ---
OPERADORS_INFO = {
    "rodalies": {"url": "https://rodalies.gencat.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg"},
    "fgc": {"url": "https://www.fgc.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg"},
    "cremallera de núria": {"url": "https://www.valldenuria.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-cremalleranuria.svg"},
    "tren dels llacs": {"url": "https://www.trendelsllacs.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-trendelsllacs.svg"},
}

CATEGORIES_ICONES = {
    "100 cims": "🏔️", "búnquer": "🪖", "castell": "🏰", "cova": "🕳️", "ermita": "⛪", "cascada": "💧", "cim": "⛰️", "gorgs": "🌊", "litoral": "🏖️", "pont": "🌉"
}

DIFICULTAT_COLOR = {"fàcil": "#1D9E75", "mitjana": "#EF9F27", "difícil": "#E24B4A", "molt difícil": "#9B1B1B"}
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

def trobar_col(df, possibles):
    for p in possibles:
        for c in df.columns:
            if p.lower() in str(c).lower().strip(): return c
    return None

def logos_linies_html(linies_str):
    if not linies_str or str(linies_str).lower() == "nan": return ""
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()]
    return "".join([f'<img src="{BASE_LOGO_LINIA.format(linia=l)}" width="22" style="margin-left:4px;">' for l in linies])

def bloc_estacio_html(op_str, linies_str):
    op = str(op_str).lower() if pd.notna(op_str) else "rodalies"
    info = OPERADORS_INFO.get(op, OPERADORS_INFO["rodalies"])
    logo = f'<img src="{info["logo"]}" width="22" style="vertical-align:middle;">'
    horari = f'<a href="{info["url"]}" target="_blank" style="font-size:11px; color:#007bff; font-weight:bold; border:1px solid #007bff; padding:2px 6px; border-radius:4px; text-decoration:none; margin-left:12px;">HORARI</a>'
    return f"{logo}{logos_linies_html(linies_str)}{horari}"

def punts_interes_html(elements_str, cats_str):
    if not elements_str or str(elements_str).lower() == "nan": return ""
    elems = [e.strip() for e in str(elements_str).split(";")]
    cats = [c.strip().lower() for c in str(cats_str).split(";")]
    html = '<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:10px; margin-top:10px;">'
    for i, el in enumerate(elems):
        icona = CATEGORIES_ICONES.get(cats[i] if i < len(cats) else "", "📍")
        html += f'<div style="background:#f8f9fa; padding:10px; border-radius:8px; font-size:13px; border:1px solid #eee; display:flex; align-items:center; gap:8px;"><span>{icona}</span> <span>{el}</span></div>'
    return html + "</div>"

# --- PROCESSAMENT ---
df_raw = carregar_dades()
c = {
    "id": trobar_col(df_raw, ["id"]),
    "ruta": trobar_col(df_raw, ["nom_de_la_ruta", "nom ruta"]),
    "desc": trobar_col(df_raw, ["descripció", "descripcio", "subtitol"]),
    "km": trobar_col(df_raw, ["km"]),
    "desn": trobar_col(df_raw, ["desnivell"]),
    "dif": trobar_col(df_raw, ["dificultat"]),
    "sortida": trobar_col(df_raw, ["estació_sortida", "sortida"]),
    "arribada": trobar_col(df_raw, ["estació_arribada", "arribada"]),
    "op_s": trobar_col(df_raw, ["operador_sortida"]),
    "op_a": trobar_col(df_raw, ["operador_arribada"]),
    "lin_s": trobar_col(df_raw, ["linies_sortida"]),
    "lin_a": trobar_col(df_raw, ["linies_arribada"]),
    "comarca": trobar_col(df_raw, ["comarca"]),
    "espai": trobar_col(df_raw, ["espai_natural"]),
    "cims": trobar_col(df_raw, ["100_cims"]),
    "wiki": trobar_col(df_raw, ["wikiloc"]),
    "coord_s": trobar_col(df_raw, ["coordenades_sortida"]),
    "elems": trobar_col(df_raw, ["elements_interès", "elements_interes"]),
    "cats": trobar_col(df_raw, ["categories_elements"])
}

# --- SIDEBAR (FILTRES COMPLETS) ---
st.sidebar.image("https://avatars.githubusercontent.com/u/279401247?v=4", width=80)
st.sidebar.header("🔎 Filtres")
sel_100cims = st.sidebar.checkbox("🏔️ Només rutes 100 Cims")
cerca = st.sidebar.text_input("📝 Cerca per nom o paraula")
sel_comarca = st.sidebar.multiselect("📍 Comarca", sorted(df_raw[c["comarca"]].dropna().unique()))
sel_espai = st.sidebar.multiselect("🌲 Espai natural", sorted(df_raw[c["espai"]].dropna().unique()))
sel_dif = st.sidebar.multiselect("🧗 Dificultat", ["fàcil", "mitjana", "difícil", "molt difícil"])
sel_km = st.sidebar.slider("📏 Distància (km)", 0.0, 50.0, (0.0, 50.0))

# Filtratge
f = df_raw.copy()
if sel_100cims: f = f[f[c["cims"]].astype(str).str.lower().str.contains("si", na=False)]
if cerca: f = f[f[c["ruta"]].str.contains(cerca, case=False, na=False)]
if sel_comarca: f = f[f[c["comarca"]].isin(sel_comarca)]
if sel_espai: f = f[f[c["espai"]].isin(sel_espai)]
if sel_dif: f = f[f[c["dif"]].str.lower().isin(sel_dif)]
f = f[(pd.to_numeric(f[c["km"]], errors='coerce') >= sel_km[0]) & (pd.to_numeric(f[c["km"]], errors='coerce') <= sel_km[1])]

# --- CONTINGUT PRINCIPAL ---
st.markdown('<h1 style="color:black; font-size:38px; font-weight:850; margin-bottom:10px;">🚂 Senderisme en tren</h1>', unsafe_allow_html=True)

with st.expander(f"🗺️ Veure mapa general ({len(f)} rutes disponibles)", expanded=False):
    m_gen = folium.Map(location=[41.7, 1.9], zoom_start=8)
    for _, r in f.iterrows():
        try:
            lat, lon = map(float, str(r[c["coord_s"]]).split(","))
            folium.Marker([lat, lon], tooltip=r[c["ruta"]], icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m_gen)
        except: pass
    st_folium(m_gen, width="100%", height=450, key="mapa_principal")

st.markdown(f"S'han trobat **{len(f)}** itineraris que coincideixen amb els teus filtres.")

# --- LLISTAT DE RUTES ---
for _, row in f.iterrows():
    rid = row[c["id"]]
    dif_nom = str(row[c["dif"]]).lower()
    color = DIFICULTAT_COLOR.get(dif_nom, "#888")
    
    st.markdown(f"""
    <div class="ruta-container">
        <div class="caixa-blanca" style="border-left: 12px solid {color}; display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
            <div style="width: 50px; height: 50px; border-radius: 50%; background: {color}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 22px;">{rid}</div>
            <div style="flex: 1;">
                <h2 class="titol-ruta">{row[c['ruta']]}</h2>
                <div style="color: #444; font-size: 16px; font-weight: 500;">{row[c['desc']]}</div>
            </div>
            <div style="background: {color}; color: white; padding: 6px 16px; border-radius: 25px; font-weight: 800; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">{dif_nom}</div>
        </div>

        <div style="display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap;">
            <div class="metrica-box">
                <div style="font-size: 11px; color: #666; font-weight: bold; text-transform: uppercase;">Distància</div>
                <div class="metrica-valor">{row[c['km']]} km</div>
            </div>
            <div class="metrica-box">
                <div style="font-size: 11px; color: #666; font-weight: bold; text-transform: uppercase;">Desnivell</div>
                <div class="metrica-valor">+{row[c['desn']]} m</div>
            </div>
            <div class="metrica-box" style="flex: 1.5;">
                <div style="font-size: 11px; color: #666; font-weight: bold; text-transform: uppercase;">Comarca</div>
                <div class="metrica-valor" style="font-size: 16px;">{row[c['comarca']]}</div>
            </div>
        </div>

        <div class="caixa-blanca" style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; padding-bottom: 12px; border-bottom: 1px solid #eee; margin-bottom: 12px;">
                <span style="font-size: 24px; margin-right: 15px;">🟢</span>
                <div style="flex: 1;">
                    <div style="font-size: 11px; color: #888; font-weight: bold;">ESTACIÓ DE SORTIDA</div>
                    <div style="font-weight: 850; font-size: 18px; color: #007bff;">{row[c['sortida']]}</div>
                </div>
                <div>{bloc_estacio_html(row[c['op_s']], row[c['lin_s']])}</div>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="font-size: 24px; margin-right: 15px;">🔴</span>
                <div style="flex: 1;">
                    <div style="font-size: 11px; color: #888; font-weight: bold;">ESTACIÓ D'ARRIBADA</div>
                    <div style="font-weight: 850; font-size: 18px; color: #007bff;">{row[c['arribada']]}</div>
                </div>
                <div>{bloc_estacio_html(row[c['op_a']], row[c['lin_a']])}</div>
            </div>
        </div>

        <div style="margin-top: 10px;">
            <div style="font-size: 12px; font-weight: 800; color: #555; margin-bottom: 5px;">PUNTS D'INTERÈS DURANT LA RUTA:</div>
            {punts_interes_html(row[c["elems"]], row[c["cats"]])}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # BOTONS I MAPA GPX
    col_map, col_wiki = st.columns([2, 1])
    with col_map:
        with st.expander("🗺️ Veure traçat de la ruta (GPX)"):
            try:
                gpx_res = requests.get(BASE_GPX_URL.format(id=int(rid)), timeout=5)
                if gpx_res.status_code == 200:
                    gpx_data = gpxpy.parse(gpx_res.text)
                    punts = [(p.latitude, p.longitude) for t in gpx_data.tracks for s in t.segments for p in s.points]
                    m_ruta = folium.Map(location=punts[0], zoom_start=13)
                    folium.PolyLine(punts, color="#007bff", weight=5, opacity=0.8).add_to(m_ruta)
                    st_folium(m_ruta, width="100%", height=350, key=f"map_{rid}")
                else: st.info("Traçat GPX no disponible per a aquesta ruta.")
            except: st.error("No s'ha pogut carregar el mapa GPX.")
    with col_wiki:
        if pd.notna(row[c["wiki"]]):
            st.link_button("🔗 Veure a Wikiloc", str(row[c["wiki"]]), use_container_width=True)
