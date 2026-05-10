# ============================================================
# SENDERISME EN TREN — v16.4
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

st.markdown("""
<style>
/* Estils de les pestanyes */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-size: 16px !important;
    font-weight: 600 !important;
}
/* Treure el marc per defecte dels expanders per personalitzar-los */
div[data-testid="stExpander"] {
    margin-bottom: 0 !important;
    margin-top: 0 !important;
}
div[data-testid="stExpander"] > details {
    border-radius: 8px !important;
    border: none !important;
    margin-bottom: 8px !important;
}
div[data-testid="stExpander"] > details > summary {
    padding: 12px 16px !important;
}
/* Petites etiquetes de títol de camp */
.field-label {
    font-size: 10px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
}
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓ I CONSTANTS ---
OPERADORS_INFO = {
    "rodalies": {"url": "https://rodalies.gencat.cat/ca/inici/index.html", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg"},
    "fgc": {"url": "https://www.fgc.cat/cercador/", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg"},
    "cremallera de núria": {"url": "https://www.valldenuria.cat/ca/cremallera", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-cremalleranuria.svg"},
    "tren dels llacs": {"url": "https://www.renfe.com/es/ca/viajar/informacion-util/horarios", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-trendelsllacs.svg"},
}

CATEGORIES_ICONES = {"100 cims": "🏔️", "cim": "⛰️", "bosc": "🌲", "ermita": "⛪", "castell": "🏰", "riu": "🏞️", "cascada": "💧"}
DIFICULTAT_COLOR = {"fàcil": "#1D9E75", "mitjana": "#EF9F27", "difícil": "#E24B4A", "molt difícil": "#9B1B1B"}

BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
SHEET_ID = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"

# --- FUNCIONS AUXILIARS ---
@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full = client.open_by_key(SHEET_ID).worksheet("Rutes")
    df = pd.DataFrame(full.get_all_records())
    df.columns = df.columns.str.strip().str.lower()
    return df

def parse_coord(coord_str):
    try:
        parts = str(coord_str).split(",")
        return float(parts[0].strip()), float(parts[1].strip())
    except: return None, None

def bloc_estacio_html(op_str, linies_str):
    op_str = str(op_str).lower() if pd.notna(op_str) else "rodalies"
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()] if pd.notna(linies_str) else []
    logos = "".join([f'<img src="{BASE_LOGO_LINIA.format(linia=l)}" width="18" style="margin-left:3px; vertical-align:middle;">' for l in linies])
    info = OPERADORS_INFO.get(op_str, OPERADORS_INFO["rodalies"])
    logo_op = f'<img src="{info["logo"]}" width="18" style="margin-right:3px; vertical-align:middle;">' if info.get("logo") else ""
    return f'{logo_op}{logos} <a href="{info["url"]}" target="_blank" style="font-size:11px; color:#007bff; font-weight:bold; text-decoration:none; margin-left:5px;">HORARI</a>'

def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
    try:
        resp = requests.get(BASE_GPX_URL.format(id=int(ruta_id)), timeout=5)
        gpx = gpxpy.parse(resp.text)
        punts = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
        m = folium.Map(location=punts[0], zoom_start=13)
        folium.PolyLine(punts, color="#007bff", weight=4).add_to(m)
        folium.Marker([lat_s, lng_s], icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a and (lat_s != lat_a or lng_s != lng_a):
            folium.Marker([lat_a, lng_a], icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        st_folium(m, width=None, height=350, key=f"map_{ruta_id}")
    except: st.info("Mapa no disponible.")

def perfil_elevacio_svg(ruta_id, color):
    try:
        resp = requests.get(BASE_GPX_URL.format(id=int(ruta_id)), timeout=5)
        gpx = gpxpy.parse(resp.text)
        elevs = [p.elevation for t in gpx.tracks for s in t.segments for p in s.points if p.elevation is not None]
        if not elevs: return None, 0, 0
        alt_min, alt_max = min(elevs), max(elevs)
        punts_svg = " ".join([f"{i*600/len(elevs)},{100-(e-alt_min)*80/(max(alt_max-alt_min,1))}" for i,e in enumerate(elevs)])
        svg = f'<svg viewBox="0 0 600 100" style="width:100%; height:80px;"><polyline points="{punts_svg}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
        return svg, alt_min, alt_max
    except: return None, 0, 0

# --- PREPARACIÓ DE DADES ---
df = carregar_dades()
cols = {
    "id": "id_ruta", "ruta": "nom_de_la_ruta", "km": "km", "desn": "desnivell_positiu",
    "dif": "dificultat", "sortida": "estació_sortida", "arribada": "estació_arribada",
    "op_s": "operador_sortida", "op_a": "operador_arribada", "linia_s": "linies_sortida",
    "linia_a": "linies_arribada", "tipus": "tipus", "coord_s": "coordenades_sortida",
    "coord_a": "coordenades_arribada", "temps": df.columns[20], "epoca": "època",
    "punt_alt": "punt_mes_alt", "elements": "elements_interès", "cats": "categories_elements_interès"
}

# --- INTERFÍCIE ---
st.markdown('<div style="display:flex;align-items:center;gap:15px;margin-bottom:20px;background-color:#f0f2f6;padding:15px 20px;border-radius:10px;"><img src="https://avatars.githubusercontent.com/u/279401247?v=4" style="width:50px;border-radius:50%;"><div><h1 style="margin:0;font-size:24px;">Senderisme en tren</h1></div></div>', unsafe_allow_html=True)

tab_rutes, tab_mapa_gen = st.tabs(["🥾 Llista de Rutes", "🗺️ Mapa General"])

with tab_rutes:
    cerca = st.text_input("Buscar per nom de ruta o estació...", "")
    f = df[df[cols["ruta"]].str.contains(cerca, case=False, na=False) | df[cols["sortida"]].str.contains(cerca, case=False, na=False)]
    
    st.write(f"S'han trobat **{len(f)}** rutes.")

    for _, row in f.iterrows():
        rid = int(row[cols["id"]])
        nom = row[cols["ruta"]]
        dif = str(row[cols["dif"]]).strip()
        color = DIFICULTAT_COLOR.get(dif.lower(), "#888")
        km = row[cols["km"]]
        desn = int(row[cols["desn"]]) if pd.notna(row[cols["desn"]]) else 0
        temps = str(row[cols["temps"]])
        
        # Etiqueta de la capçalera de l'expander (DADES PRINCIPALS)
        header_label = f"**{rid}** · {nom} | **{dif.upper()}** | {km}km · {desn}m · {temps}"
        
        # CSS per pintar l'expander segons dificultat
        st.markdown(f"<style>div[key='exp_{rid}'] > details > summary {{ background: {color}15 !important; border-left: 6px solid {color} !important; }}</style>", unsafe_allow_html=True)

        with st.expander(header_label):
            st.container(key=f"exp_{rid}")
            
            # SUB-EXPANDER VEURE MÉS (DADES DETALLADES)
            with st.expander("➕ Veure detalls del recorregut"):
                st.markdown(f"<div style='border-left: 2px solid {color}; padding-left: 20px; margin-top:10px;'>", unsafe_allow_html=True)
                
                # BLOC ESTACIONS
                s_est, a_est = str(row[cols["sortida"]]), str(row[cols["arribada"]])
                if s_est.lower() == a_est.lower():
                    st.markdown(f'<div class="field-label">Estació de sortida/arribada</div><div style="font-size:16px; font-weight:700; margin-bottom:15px;">{s_est} {bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="field-label">Estació de sortida</div><div style="font-size:16px; font-weight:700; margin-bottom:10px;">{s_est} {bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="field-label">Estació d\'arribada</div><div style="font-size:16px; font-weight:700; margin-bottom:15px;">{a_est} {bloc_estacio_html(row[cols["op_a"]], row[cols["linia_a"]])}</div>', unsafe_allow_html=True)

                # FILA DADES TÈCNIQUES
                c1, c2, c3 = st.columns(3)
                tipus_val = "Circular" if "circular" in str(row[cols["tipus"]]).lower() else "Lineal"
                c1.markdown(f'<div class="field-label">Tipus de ruta</div><div style="font-weight:600;">{tipus_val}</div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="field-label">Època</div><div style="font-weight:600;">{row[cols["epoca"]] if pd.notna(row[cols["epoca"]]) else "—"}</div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="field-label">Cim més alt</div><div style="font-weight:600;">{row[cols["punt_alt"]] if pd.notna(row[cols["punt_alt"]]) else "—"}</div>', unsafe_allow_html=True)
                
                st.write("---")

                # APARTATS INTERNS
                with st.expander("🗺️ Mapa i Track"):
                    l_s, ln_s = parse_coord(row[cols["coord_s"]])
                    l_a, ln_a = parse_coord(row[cols["coord_a"]])
                    mostrar_mapa_gpx(rid, l_s, ln_s, l_a, ln_a)
                
                with st.expander("⛰️ Perfil d'elevació"):
                    svg, a_min, a_max = perfil_elevacio_svg(rid, color)
                    if svg:
                        st.markdown(svg, unsafe_allow_html=True)
                        st.caption(f"Cota mínima: {int(a_min)}m | Cota màxima: {int(a_max)}m")
                
                with st.expander("📌 Punts d'interès"):
                    txt_elem = row[cols["elements"]]
                    if pd.notna(txt_elem): st.write(txt_elem)
                    else: st.info("No s'han informat punts d'interès.")

                st.markdown("</div>", unsafe_allow_html=True)

with tab_mapa_gen:
    st.info("Aquí apareixerà el mapa general de totes les estacions amb rutes.")
    m_gen = folium.Map(location=[41.7, 1.8], zoom_start=8)
    for _, r in f.iterrows():
        lat, lon = parse_coord(r[cols["coord_s"]])
        if lat: folium.Marker([lat, lon], tooltip=f"Sortida: {r[cols['ruta']]}").add_to(m_gen)
    st_folium(m_gen, width=1200, height=500)
