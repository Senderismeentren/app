# ============================================================
# SENDERISME EN TREN — v16.5
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
div[data-testid="stTabs"] button[data-baseweb="tab"] { font-size: 16px !important; font-weight: 600 !important; }
div[data-testid="stExpander"] { margin-bottom: 0 !important; margin-top: 0 !important; }
div[data-testid="stExpander"] > details { border-radius: 8px !important; border: none !important; margin-bottom: 8px !important; }
div[data-testid="stExpander"] > details > summary { padding: 12px 16px !important; }
.field-label { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
DIFICULTAT_COLOR = {"fàcil": "#1D9E75", "mitjana": "#EF9F27", "difícil": "#E24B4A", "molt difícil": "#9B1B1B"}
OPERADORS_INFO = {
    "rodalies": {"url": "https://rodalies.gencat.cat/ca/inici/index.html", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg"},
    "fgc": {"url": "https://www.fgc.cat/cercador/", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg"},
}
BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
SHEET_ID = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"

# --- FUNCIONS ---
@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full = client.open_by_key(SHEET_ID).worksheet("Rutes")
    df = pd.DataFrame(full.get_all_records())
    df.columns = df.columns.str.strip().str.lower()
    return df

def buscar_columna(df, noms_possibles):
    for nom in noms_possibles:
        nom_norm = nom.lower()
        for col in df.columns:
            if nom_norm in col: return col
    return None

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
    return f'<img src="{info["logo"]}" width="18" style="vertical-align:middle;">{logos} <a href="{info["url"]}" target="_blank" style="font-size:11px; color:#007bff; font-weight:bold; text-decoration:none; margin-left:5px;">HORARI</a>'

def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
    try:
        resp = requests.get(BASE_GPX_URL.format(id=int(ruta_id)), timeout=5)
        gpx = gpxpy.parse(resp.text)
        punts = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
        m = folium.Map(location=punts[0], zoom_start=12)
        folium.PolyLine(punts, color="#007bff", weight=4).add_to(m)
        folium.Marker([lat_s, lng_s], icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a: folium.Marker([lat_a, lng_a], icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        st_folium(m, width=None, height=350, key=f"map_{ruta_id}")
    except: st.info("Mapa no disponible.")

# --- PREPARACIÓ DADES ---
df = carregar_dades()
c = {
    "id": buscar_columna(df, ["id_ruta", "id"]),
    "ruta": buscar_columna(df, ["nom_de_la_ruta", "nom"]),
    "km": buscar_columna(df, ["km", "distancia"]),
    "desn": buscar_columna(df, ["desnivell_positiu", "pujada"]),
    "dif": buscar_columna(df, ["dificultat"]),
    "sortida": buscar_columna(df, ["estació_sortida", "sortida"]),
    "arribada": buscar_columna(df, ["estació_arribada", "arribada"]),
    "op_s": buscar_columna(df, ["operador_sortida", "op s"]),
    "op_a": buscar_columna(df, ["operador_arribada", "op a"]),
    "linia_s": buscar_columna(df, ["linies_sortida", "linia s"]),
    "linia_a": buscar_columna(df, ["linies_arribada", "linia a"]),
    "tipus": buscar_columna(df, ["tipus"]),
    "coord_s": buscar_columna(df, ["coordenades_sortida"]),
    "coord_a": buscar_columna(df, ["coordenades_arribada"]),
    "temps": df.columns[20] if len(df.columns) > 20 else None,
    "epoca": buscar_columna(df, ["època", "epoca", "millor"]),
    "punt_alt": buscar_columna(df, ["punt_mes_alt", "cim", "cota"]),
}

# --- INTERFÍCIE ---
st.title("🥾 Senderisme en tren")

tab_rutes, tab_mapa = st.tabs(["Llista de Rutes", "Mapa General"])

with tab_rutes:
    cerca = st.text_input("Filtrar rutes...", "")
    f = df[df[c["ruta"]].str.contains(cerca, case=False, na=False)] if c["ruta"] else df
    
    for _, row in f.iterrows():
        rid = row[c["id"]] if c["id"] else "?"
        nom = row[c["ruta"]] if c["ruta"] else "Sense nom"
        dif = str(row[c["dif"]]).strip().lower() if c["dif"] else "mitjana"
        color = DIFICULTAT_COLOR.get(dif, "#888")
        km = row[c["km"]] if c["km"] else 0
        desn = row[c["desn"]] if c["desn"] else 0
        
        # Temps formatat
        t_raw = row[c["temps"]] if c["temps"] else "—"
        try:
            t_val = float(str(t_raw).replace(",", "."))
            h = int(t_val); m = round((t_val - h) * 60)
            temps_fmt = f"{h}h {m}min"
        except: temps_fmt = str(t_raw)

        # CAPÇALERA SEMPRE VISIBLE
        label = f"**{rid}** · {nom} | **{dif.upper()}** | {km}km · {desn}m · {temps_fmt}"
        
        st.markdown(f"<style>div[key='box_{rid}'] > details > summary {{ background:{color}15 !important; border-left:6px solid {color} !important; }}</style>", unsafe_allow_html=True)

        with st.expander(label):
            st.container(key=f"box_{rid}")
            
            with st.expander("➕ Veure més"):
                st.markdown(f"<div style='border-left: 2px solid {color}; padding-left: 20px;'>", unsafe_allow_html=True)
                
                # Estacions
                s_est, a_est = str(row[c["sortida"]]), str(row[c["arribada"]])
                tipus_r = str(row[c["tipus"]]).lower() if c["tipus"] else ""
                
                if "circular" in tipus_r or s_est.lower() == a_est.lower():
                    st.markdown(f'<div class="field-label">Estació de sortida/arribada</div><div style="font-size:16px; font-weight:700; margin-bottom:15px;">{s_est} {bloc_estacio_html(row[c["op_s"]], row[c["linia_s"]])}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="field-label">Estació de sortida</div><div style="font-size:16px; font-weight:700;">{s_est} {bloc_estacio_html(row[c["op_s"]], row[c["linia_s"]])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="field-label">Estació d\'arribada</div><div style="font-size:16px; font-weight:700; margin-bottom:15px;">{a_est} {bloc_estacio_html(row[c["op_a"]], row[c["linia_a"]])}</div>', unsafe_allow_html=True)

                # Fila de dades
                col1, col2, col3 = st.columns(3)
                tipus_text = "Circular" if "circular" in tipus_r else "Lineal"
                
                # Aquí la seguretat: comprovem si la clau existeix abans d'usar-la
                epoca_val = row[c["epoca"]] if c["epoca"] and pd.notna(row[c["epoca"]]) else "—"
                cim_val = row[c["punt_alt"]] if c["punt_alt"] and pd.notna(row[c["punt_alt"]]) else "—"

                col1.markdown(f'<div class="field-label">Tipus de ruta</div><div style="font-weight:600;">{tipus_text}</div>', unsafe_allow_html=True)
                col2.markdown(f'<div class="field-label">Època</div><div style="font-weight:600;">{epoca_val}</div>', unsafe_allow_html=True)
                col3.markdown(f'<div class="field-label">Cim més alt</div><div style="font-weight:600;">{cim_val}</div>', unsafe_allow_html=True)
                
                # Mapa i Track
                if c["coord_s"]:
                    st.write("---")
                    ls, lns = parse_coord(row[c["coord_s"]])
                    la, lna = parse_coord(row[c["coord_a"]]) if c["coord_a"] else (None, None)
                    mostrar_mapa_gpx(rid, ls, lns, la, lna)
                
                st.markdown("</div>", unsafe_allow_html=True)
