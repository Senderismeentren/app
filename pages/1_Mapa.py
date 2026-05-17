# ============================================================
# SENDERISME EN TREN — Pàgina: Mapa d'estacions
# Fitxer: pages/1_Mapa.py
# ============================================================

import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Mapa · Senderisme en tren",
    layout="wide",
    page_icon="🗺️"
)

# --- Ocultar sidebar i nav de Streamlit si vols iframe net ---
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
SHEET_ID   = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"
SHEET_NAME = "Rutes"

def color_folium_per_operador(op_str):
    """Retorna el color hex corporatiu per operador."""
    if not op_str or str(op_str).strip().lower() in ("nan", ""):
        return "#EE7F00"
    op = str(op_str).strip().lower().split(";")[0].strip()
    if "rodalies" in op:  return "#EE7F00"  # Pantone 152 / RAL 2000
    if "fgc" in op:       return "#97D700"  # Pantone 375C / RAL S 0580-G30Y
    if "metro" in op or "tmb" in op: return "#E30613"
    if "tram" in op:      return "#78BE20"
    if "adif" in op:      return "#8B008B"
    if "renfe" in op:     return "#003DA5"
    if "tren dels llacs" in op: return "#5F9EA0"
    if "alta velocitat" in op:  return "#8B0000"
    if "sncf" in op:      return "#C00000"
    if "cremallera" in op: return "#C8A96E"
    return "#EE7F00"

def parse_coord(coord_str):
    try:
        parts = str(coord_str).split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except:
        pass
    return None, None

@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full   = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return pd.DataFrame(full.get_all_records())

def buscar_col(df, llista):
    for c in df.columns:
        for p in llista:
            if p in str(c): return c
    return None

# --- CÀRREGA ---
try:
    df_raw = carregar_dades()
except Exception as e:
    st.error(f"Error connectant amb Google Sheets: {e}")
    st.stop()

df_raw.columns = df_raw.columns.str.strip().str.lower()

cols = {
    "id":       buscar_col(df_raw, ["núm_ruta", "num_ruta", "id_ruta", "id"]),
    "ruta":     buscar_col(df_raw, ["nom_ruta", "nom_de_la_ruta"]),
    "sortida":  buscar_col(df_raw, ["estació_sortida", "estacio_sortida", "sortida"]),
    "arribada": buscar_col(df_raw, ["estació_arribada", "estacio_arribada", "arribada"]),
    "op_s":     buscar_col(df_raw, ["operador_sortida"]),
    "op_a":     buscar_col(df_raw, ["operador_arribada"]),
    "coord_s":  buscar_col(df_raw, ["coordenades_sortida"]),
    "coord_a":  buscar_col(df_raw, ["coordenades_arribada"]),
}

df = df_raw.dropna(subset=[cols["ruta"]]).copy()

# --- MAPA ---
st.markdown("<h2 style='margin-top:0;'>🗺️ Mapa d'estacions</h2>", unsafe_allow_html=True)

if "filtre_estacio_mapa" not in st.session_state:
    st.session_state.filtre_estacio_mapa = None
if "map_reset_counter" not in st.session_state:
    st.session_state.map_reset_counter = 0

punts_mapa = {}

for _, row in df.iterrows():
    nom = str(row[cols["ruta"]])
    rid = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""
    op_s = str(row[cols["op_s"]]).strip() if cols.get("op_s") and pd.notna(row[cols["op_s"]]) else ""
    op_a = str(row[cols["op_a"]]).strip() if cols.get("op_a") and pd.notna(row[cols["op_a"]]) else ""

    if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]):
        lat_s, lng_s = parse_coord(row[cols["coord_s"]])
        s_est = str(row[cols["sortida"]]).strip()
        if lat_s and lng_s:
            key = (lat_s, lng_s, s_est)
            if key not in punts_mapa:
                punts_mapa[key] = {"rutes": [], "op": op_s}
            punts_mapa[key]["rutes"].append(f"Ruta {rid}: {nom}")

    if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]):
        lat_a, lng_a = parse_coord(row[cols["coord_a"]])
        a_est = str(row[cols["arribada"]]).strip()
        s_est = str(row[cols["sortida"]]).strip()
        if lat_a and lng_a and a_est.lower() != s_est.lower():
            key = (lat_a, lng_a, a_est)
            if key not in punts_mapa:
                punts_mapa[key] = {"rutes": [], "op": op_a}
            punts_mapa[key]["rutes"].append(f"Ruta {rid}: {nom}")

if not punts_mapa:
    st.info("No hi ha coordenades disponibles per mostrar al mapa.")
    st.stop()

m = folium.Map(location=[41.7, 1.8], zoom_start=8, tiles="OpenStreetMap")

for (lat, lng, estacio), info in punts_mapa.items():
    color = color_folium_per_operador(info["op"])
    n_rutes = len(info["rutes"])
    paraula = "ruta" if n_rutes == 1 else "rutes"
    icon_html = (
        f"<div style='background:{color};width:28px;height:28px;border-radius:50%;"
        f"border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.4);"
        f"display:flex;align-items:center;justify-content:center;font-size:13px;'>🚉</div>"
    )
    folium.Marker(
        location=[lat, lng],
        tooltip=estacio,
        popup=folium.Popup(f"<b>{estacio}</b><br>{n_rutes} {paraula}", max_width=200),
        icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    ).add_to(m)

map_key = f"mapa_pg_{st.session_state.get('map_reset_counter', 0)}"
resultat = st_folium(m, width=None, height=500, returned_objects=["last_object_clicked_tooltip"], key=map_key)

if resultat and resultat.get("last_object_clicked_tooltip"):
    estacio_clicada = str(resultat["last_object_clicked_tooltip"]).strip()
    if estacio_clicada != st.session_state.filtre_estacio_mapa:
        st.session_state.filtre_estacio_mapa = estacio_clicada
        st.rerun()

if st.session_state.filtre_estacio_mapa:
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.info(f"🚉 Estació seleccionada: **{st.session_state.filtre_estacio_mapa}**")
    with col_btn:
        if st.button("✖ Treure filtre"):
            st.session_state.filtre_estacio_mapa = None
            st.session_state.map_reset_counter += 1
            st.rerun()

    filtre = st.session_state.filtre_estacio_mapa
    f_mapa = df[
        (df[cols["sortida"]].astype(str).str.strip() == filtre) |
        (df[cols["arribada"]].astype(str).str.strip() == filtre)
    ]
    st.markdown(f"**{len(f_mapa)} rutes amb {filtre}**")
    for _, row in f_mapa.iterrows():
        nom = str(row[cols["ruta"]])
        rid = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""
        st.markdown(
            f"<div style='padding:8px 12px;margin:4px 0;background:white;border-radius:6px;"
            f"border-left:4px solid #EE7F00;font-size:14px;'>"
            f"<b>{rid}.</b> {nom}</div>",
            unsafe_allow_html=True
        )
