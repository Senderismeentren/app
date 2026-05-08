# ============================================================
# SENDERISME EN TREN — v19 (VERSIÓ ESTABLE I COMPLETA)
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
        font-weight: 850 !important;
        font-size: 22px !important;
        line-height: 1.2;
        margin-bottom: 5px;
    }
    .ruta-container {
        background-color: #f2f2f2;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 40px;
    }
    .caixa-blanca {
        background: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #ddd;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metrica-box {
        flex: 1;
        background: white;
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓ I DICCIONARIS ---
OPERADORS_INFO = {
    "rodalies": {"url": "https://rodalies.gencat.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-rodalies.svg"},
    "fgc": {"url": "https://www.fgc.cat", "logo": "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-fgc.svg"},
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

def trobar_col(df, noms_posibles):
    for nom in noms_posibles:
        for col in df.columns:
            if nom.lower() in col.lower().strip(): return col
    return None

def logos_linies_html(linies_str):
    if not linies_str or str(linies_str).lower() == "nan": return ""
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()]
    return "".join([f'<img src="{BASE_LOGO_LINIA.format(linia=l)}" width="20" style="margin-left:4px;">' for l in linies])

def bloc_estacio_html(op_str, linies_str):
    op = str(op_str).lower() if pd.notna(op_str) else "rodalies"
    info = OPERADORS_INFO.get(op, OPERADORS_INFO["rodalies"])
    logo = f'<img src="{info["logo"]}" width="20" style="margin-right:5px;">'
    horari = f'<a href="{info["url"]}" target="_blank" style="font-size:11px; color:#007bff; font-weight:bold; border:1px solid #007bff; padding:1px 4px; border-radius:3px; text-decoration:none; margin-left:5px;">HORARI</a>'
    return f"{logo}{logos_linies_html(linies_str)}{horari}"

# --- INICI APP ---
try:
    df_raw = carregar_dades()
    
    # Mapeig intel·ligent de columnes per evitar KeyError
    cols = {
        "id": trobar_col(df_raw, ["id"]),
        "ruta": trobar_col(df_raw, ["nom_de_la_ruta", "nom ruta"]),
        "desc": trobar_col(df_raw, ["descripció", "descripcio", "subtitol"]),
        "km": trobar_col(df_raw, ["km"]),
        "dif": trobar_col(df_raw, ["dificultat"]),
        "sortida": trobar_col(df_raw, ["estació_sortida", "sortida"]),
        "arribada": trobar_col(df_raw, ["estació_arribada", "arribada"]),
        "op_s": trobar_col(df_raw, ["operador_sortida"]),
        "op_a": trobar_col(df_raw, ["operador_arribada"]),
        "lin_s": trobar_col(df_raw, ["linies_sortida"]),
        "lin_a": trobar_col(df_raw, ["linies_arribada"]),
        "desn": trobar_col(df_raw, ["desnivell", "pujada"]),
        "wiki": trobar_col(df_raw, ["wikiloc"]),
        "comarca": trobar_col(df_raw, ["comarca"]),
        "coord_s": trobar_col(df_raw, ["coordenades_sortida"]),
        "cims": trobar_col(df_raw, ["100_cims", "100cims"])
    }

    # Sidebar
    st.sidebar.header("🔎 Filtres")
    cerca = st.sidebar.text_input("📝 Paraula clau")
    sel_dif = st.sidebar.multiselect("🧗 Dificultat", ["fàcil", "mitjana", "difícil", "molt difícil"])
    
    # Aplicar Filtres
    f = df_raw.copy()
    if cerca: f = f[f[cols["ruta"]].str.contains(cerca, case=False, na=False)]
    if sel_dif: f = f[f[cols["dif"]].str.lower().isin(sel_dif)]

    st.markdown('<h1>🚂 Senderisme en tren</h1>', unsafe_allow_html=True)
    st.write(f"S'han trobat **{len(f)}** rutes.")

    # Bucle de rutes
    for _, row in f.iterrows():
        rid = row[cols["id"]]
        nom = row[cols["ruta"]]
        desc = row[cols["desc"]] if pd.notna(row[cols["desc"]]) else ""
        dif = str(row[cols["dif"]]).lower()
        color = DIFICULTAT_COLOR.get(dif, "#888")
        
        st.markdown(f"""
        <div class="ruta-container">
            <div class="caixa-blanca" style="border-left: 10px solid {color}; display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
                <div style="width: 38px; height: 38px; border-radius: 50%; background: {color}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 18px;">{rid}</div>
                <div style="flex: 1;">
                    <div class="titol-ruta">{nom}</div>
                    <div style="font-size: 13px; color: #555;">{desc}</div>
                </div>
                <div style="background: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;">{dif}</div>
            </div>

            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <div class="metrica-box">
                    <div style="font-size: 10px; color: #777; font-weight: bold;">DISTÀNCIA</div>
                    <div style="font-size: 16px; font-weight: 800;">{row[cols["km"]]} km</div>
                </div>
                <div class="metrica-box">
                    <div style="font-size: 10px; color: #777; font-weight: bold;">DESNIVELL</div>
                    <div style="font-size: 16px; font-weight: 800;">+{row[cols["desn"]]} m</div>
                </div>
            </div>

            <div class="caixa-blanca">
                <div style="display: flex; align-items: center; padding-bottom: 10px; border-bottom: 1px solid #eee; margin-bottom: 10px;">
                    <span style="font-size: 18px; margin-right: 12px;">🟢</span>
                    <strong style="min-width: 80px; font-size: 13px; color: #444;">SORTIDA:</strong>
                    <span style="color: #007bff; font-weight: 800; font-size: 15px;">{row[cols["sortida"]]}</span>
                    <div style="margin-left: auto;">{bloc_estacio_html(row[cols["op_s"]], row[cols["lin_s"]])}</div>
                </div>
                <div style="display: flex; align-items: center;">
                    <span style="font-size: 18px; margin-right: 12px;">🔴</span>
                    <strong style="min-width: 80px; font-size: 13px; color: #444;">ARRIBADA:</strong>
                    <span style="color: #007bff; font-weight: 800; font-size: 15px;">{row[cols["arribada"]]}</span>
                    <div style="margin-left: auto;">{bloc_estacio_html(row[cols["op_a"]], row[cols["lin_a"]])}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mapes i Enllaços
        c1, c2 = st.columns(2)
        with c1:
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
                    else: st.info("Sense mapa GPX.")
                except: st.error("Error mapa.")
        with c2:
            if pd.notna(row[cols["wiki"]]):
                st.link_button("🔗 Veure a Wikiloc", str(row[cols["wiki"]]), use_container_width=True)

except Exception as e:
    st.error(f"Error de dades: {e}")
