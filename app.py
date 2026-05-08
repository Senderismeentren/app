# ============================================================
# SENDERISME EN TREN — v17 (CORREGIDA)
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

# --- CAPÇALERA ---
st.markdown('''
    <div style="display:flex;align-items:center;gap:15px;margin-bottom:20px;background-color:#f0f2f6;padding:15px 20px;border-radius:10px;">
        <img src="https://avatars.githubusercontent.com/u/279401247?v=4" style="width:50px;height:50px;border-radius:50%;">
        <div>
            <h1 style="margin:0;font-size:28px;color:#000000;">Senderisme en tren</h1>
            <p style="margin:4px 0 0 0;font-size:15px;color:#555;">Rutes i excursions a peu amb accés en tren, metro, cremallera o funicular.</p>
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
    "metro": {"url": "https://www.tmb.cat/ca/barcelona/horaris-metro", "logo": None},
    "tram": {"url": "https://www.tram.cat/ca/linies-i-horaris", "logo": None},
    "renfe": {"url": "https://www.renfe.com/es/ca/viajar/informacion-util/horarios", "logo": None},
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
    },
}

CATEGORIES_ICONES = {
    "100 cims": "🏔️", "búnquer": "🪖", "castell": "🏰", "cova": "🕳️",
    "dolmen": "🪨", "ermita": "⛪", "ferrocarril": "🚂", "jaciment ibèric": "🏛️",
    "museu": "🖼️", "pintures rupestres": "🎨", "pont": "🌉", "època romana": "🏟️",
    "santuari": "🙏", "torre del telègraf": "📡", "torre": "🗼", "patrimoni unesco": "🌍",
    "bosc": "🌲", "camí equipat": "🧗", "cascada": "💧", "cim": "⛰️",
    "cingleres": "🪨", "gorgs": "🌊", "litoral": "🏖️", "platja": "🏝️",
    "riu": "🏞️", "pantà": "💦",
}

DIFICULTAT_COLOR = {
    "fàcil": "#1D9E75", "facil": "#1D9E75",
    "mitjana": "#EF9F27", "mitja": "#EF9F27",
    "difícil": "#E24B4A", "dificil": "#E24B4A",
    "molt difícil": "#9B1B1B", "molt dificil": "#9B1B1B",
}

BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
LOGO_SIZE        = 18
SHEET_ID         = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"
SHEET_NAME       = "Rutes"
COLOR_BLAU       = "#007bff"

@st.cache_data(ttl=300)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full   = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return pd.DataFrame(full.get_all_records())

def parse_coord(coord_str):
    try:
        parts = str(coord_str).split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except:
        pass
    return None, None

def logos_linies_html(linies_str):
    if not linies_str or str(linies_str).strip().lower() in ("nan", ""):
        return ""
    linies = [l.strip() for l in re.split(r"[;,]", str(linies_str)) if l.strip()]
    return "".join([
        f'<img src="{BASE_LOGO_LINIA.format(linia=l)}" width="{LOGO_SIZE}" style="vertical-align:middle;margin-left:3px;" title="{l}">'
        for l in linies
    ])

def bloc_estacio_html(op_str, linies_str):
    if not op_str or str(op_str).strip().lower() in ("nan", ""):
        op_str = "rodalies"
    operadors    = [o.strip().lower() for o in re.split(r";", str(op_str)) if o.strip()]
    logos_linies = logos_linies_html(linies_str)
    parts = []
    for op in operadors:
        info    = OPERADORS_INFO.get(op, OPERADORS_INFO["rodalies"])
        logo_op = f'<img src="{info["logo"]}" width="{LOGO_SIZE}" style="vertical-align:middle;margin-right:3px;">' if info.get("logo") else ""
        horari  = f'<a href="{info["url"]}" target="_blank" style="font-size:11px;color:{COLOR_BLAU};text-decoration:none;font-weight:bold;margin-left:5px;border:1px solid {COLOR_BLAU};padding:1px 4px;border-radius:3px;">HORARI</a>'
        parts.append(f'{logo_op}{logos_linies}{horari}')
    return " ".join(parts)

def punts_interes_html(elements_str, categories_str):
    if not elements_str or str(elements_str).strip().lower() in ("nan", ""):
        return ""
    elements   = [e.strip() for e in re.split(r";", str(elements_str)) if e.strip()]
    categories = [c.strip().lower() for c in re.split(r";", str(categories_str)) if c.strip()] if categories_str and str(categories_str).strip().lower() not in ("nan", "") else []
    targetes = []
    for i, element in enumerate(elements):
        categoria = categories[i] if i < len(categories) else ""
        icona     = CATEGORIES_ICONES.get(categoria, "📍")
        targetes.append(
            f"<div style='display:flex;align-items:center;gap:8px;background:white;border-radius:6px;padding:6px 10px;font-size:12px;color:#333;border:0.5px solid #ddd;'>"
            f"<span>{icona}</span><span>{element}</span></div>"
        )
    grid = "".join(targetes)
    return (
        f"<div style='margin-top:10px;'>"
        f"<div style='font-size:13px;font-weight:bold;color:#444;margin-bottom:8px;'>📌 Punts d'interès</div>"
        f"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px;'>"
        f"{grid}</div></div>"
    )

def metric_box(label, value):
    return (
        f"<div style='flex:1;background:white;border:1px solid #ddd;border-radius:8px;padding:8px;display:flex;flex-direction:column;min-width:100px;'>"
        f"<span style='font-size:10px;color:#777;text-transform:uppercase;font-weight:bold;'>{label}</span>"
        f"<span style='font-size:14px;font-weight:bold;color:#111;'>{value}</span></div>"
    )

def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
    gpx_url = BASE_GPX_URL.format(id=int(ruta_id))
    try:
        resp  = requests.get(gpx_url, timeout=10)
        if resp.status_code != 200: return False
        gpx   = gpxpy.parse(resp.text)
        punts = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
        if not punts: return False
        centre = (sum(p[0] for p in punts) / len(punts), sum(p[1] for p in punts) / len(punts))
        m = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(punts, color=COLOR_BLAU, weight=4, opacity=0.8).add_to(m)
        if lat_s and lng_s: folium.Marker([lat_s, lng_s], tooltip="Sortida", icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a and lng_a: folium.Marker([lat_a, lng_a], tooltip="Arribada", icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        st_folium(m, width=None, height=300, returned_objects=[], key=f"mapa_ruta_{ruta_id}")
        return True
    except: return False

def mostrar_mapa_general(df_filtrat, cols):
    punts_mapa = {}
    for _, row in df_filtrat.iterrows():
        lat, lng = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
        if lat and lng:
            estacio = str(row[cols["sortida"]]).strip()
            key = (lat, lng, estacio)
            if key not in punts_mapa: punts_mapa[key] = []
            punts_mapa[key].append(str(row[cols["ruta"]]))
            
    if not punts_mapa:
        st.info("No hi ha coordenades disponibles.")
        return

    lats = [k[0] for k in punts_mapa]
    lngs = [k[1] for k in punts_mapa]
    m = folium.Map(location=[sum(lats)/len(lats), sum(lngs)/len(lngs)], zoom_start=9)
    for (lat, lng, estacio), rutes in punts_mapa.items():
        folium.Marker(location=[lat, lng], tooltip=f"Estació de {estacio}", icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
    
    resultat = st_folium(m, width=None, height=350, key="mapa_general_v17")
    if resultat and resultat.get("last_object_clicked_tooltip"):
        estacio_clicada = resultat["last_object_clicked_tooltip"].replace("Estació de ", "").strip()
        if estacio_clicada != st.session_state.get('filtre_estacio'):
            st.session_state.filtre_estacio = estacio_clicada
            st.rerun()

# --- DADES ---
df_raw = carregar_dades()
df_raw.columns = df_raw.columns.str.strip().str.lower()
def buscar_col(llista):
    for c in df_raw.columns:
        for p in llista:
            if p in str(c): return c
    return None

cols = {
    "id": buscar_col(["id_ruta", "id"]),
    "ruta": buscar_col(["nom_de_la_ruta", "nom ruta"]),
    "desc": buscar_col(["descripció", "descripcio", "subtitol"]),
    "km": buscar_col(["km"]),
    "cims": buscar_col(["100_cims", "100cims"]),
    "sortida": buscar_col(["estació_sortida", "sortida"]),
    "op_s": buscar_col(["operador_sortida", "operador s"]),
    "arribada": buscar_col(["estació_arribada", "arribada"]),
    "op_a": buscar_col(["operador_arribada", "operador a"]),
    "linia_s": buscar_col(["linies_sortida"]),
    "linia_a": buscar_col(["linies_arribada"]),
    "comarca": buscar_col(["comarca"]),
    "espai": buscar_col(["espai_natural"]),
    "desn": buscar_col(["desnivell_positiu", "desnivell"]),
    "baixada": buscar_col(["negatiu"]),
    "tipus": buscar_col(["tipus"]),
    "dif": buscar_col(["dificultat"]),
    "wiki": buscar_col(["enllaç_wikiloc", "wikiloc"]),
    "elements": buscar_col(["elements_interès", "elements_interes"]),
    "cats": buscar_col(["categories_elements_interès", "categories_elements_interes"]),
    "coord_s": buscar_col(["coordenades_sortida"]),
    "coord_a": buscar_col(["coordenades_arribada"]),
}

df = df_raw.dropna(subset=[cols["ruta"]]).copy()
df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
if cols["desn"]: df[cols["desn"]] = pd.to_numeric(df[cols["desn"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
if cols["baixada"]: df[cols["baixada"]] = pd.to_numeric(df[cols["baixada"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- FILTRES ---
st.sidebar.header("🔎 Filtres")
cerca = st.sidebar.text_input("📝 Paraula clau")
sel_dif = st.sidebar.multiselect("🧗 Dificultat", sorted(df[cols["dif"]].dropna().unique()))
sel_km = st.sidebar.slider("📏 Distància (km)", float(df[cols["km"]].min()), float(df[cols["km"]].max()), (float(df[cols["km"]].min()), float(df[cols["km"]].max())))

f = df.copy()
if cerca: f = f[f[cols["ruta"]].str.contains(cerca, case=False, na=False)]
if sel_dif: f = f[f[cols["dif"]].isin(sel_dif)]
f = f[(f[cols["km"]] >= sel_km[0]) & (f[cols["km"]] <= sel_km[1])]

if "filtre_estacio" not in st.session_state: st.session_state.filtre_estacio = None
if st.session_state.filtre_estacio:
    st.info(f"🚉 Estació seleccionada: **{st.session_state.filtre_estacio}**")
    if st.button("✖ Esborrar filtre"): st.session_state.filtre_estacio = None; st.rerun()
    f = f[f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_estacio]

with st.expander("🗺️ Veure mapa general", expanded=False):
    mostrar_mapa_general(f, cols)

# --- RENDER RUTES ---
for _, row in f.iterrows():
    rid = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else "?"
    nom = row[cols["ruta"]]
    d_text = str(row[cols["desc"]]).strip() if pd.notna(row[cols["desc"]]) else ""
    dif = str(row[cols["dif"]]).strip()
    c_dif = DIFICULTAT_COLOR.get(dif.lower(), "#888")
    tipus = str(row[cols["tipus"]]).strip().lower()
    
    # HTML DE LA RUTA
    st.markdown(f"""
    <div style="background-color:#f4f4f4; padding:15px; border-radius:12px; border:1px solid #ddd; margin-bottom:25px;">
        <div style="border-left:8px solid {c_dif}; background:white; padding:12px 16px; border-radius:4px 8px 8px 4px; display:flex; align-items:center; gap:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
            <div style="width:35px; height:35px; border-radius:50%; background:{c_dif}; color:white; font-weight:bold; display:flex; align-items:center; justify-content:center;">{rid}</div>
            <div style="flex:1;">
                <div style="font-size:19px; font-weight:900; color:#000;">{nom}</div>
                <div style="font-size:12px; color:#666;">{d_text}</div>
            </div>
            <span style="font-size:11px; font-weight:bold; background:{c_dif}; color:white; padding:4px 10px; border-radius:20px;">{dif.upper()}</span>
        </div>
        
        <div style="display:flex; gap:8px; margin:12px 0; flex-wrap:wrap;">
            {metric_box("Distància", f"{row[cols['km']]} km")}
            {metric_box("Desnivell", f"+/- {row[cols['desn']]} m") if "circular" in tipus else metric_box("Pujada", f"+{row[cols['desn']]} m") + metric_box("Baixada", f"-{row[cols['baixada']]} m")}
        </div>

        <div style="background:white; padding:12px; border-radius:8px; border:1px solid #eee;">
            <div style="font-size:13px; margin-bottom:10px; display:flex; align-items:center; gap:8px;">
                <span style="width:12px; height:12px; border-radius:50%; background:#1D9E75;"></span>
                <strong style="color:#222; min-width:80px;">SORTIDA:</strong> 
                <span style="color:#007bff; font-weight:bold;">{row[cols['sortida']]}</span>
                <span style="margin-left:auto;">{bloc_estacio_html(row[cols['op_s']], row[cols['linia_s']])}</span>
            </div>
            <div style="font-size:13px; display:flex; align-items:center; gap:8px;">
                <span style="width:12px; height:12px; border-radius:50%; background:#E24B4A;"></span>
                <strong style="color:#222; min-width:80px;">ARRIBADA:</strong> 
                <span style="color:#007bff; font-weight:bold;">{row[cols['arribada']]}</span>
                <span style="margin-left:auto;">{bloc_estacio_html(row[cols['op_a']], row[cols['linia_a']])}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("🗺️ Mapa del recorregut"):
            lat_s, lng_s = parse_coord(row[cols["coord_s"]])
            lat_a, lng_a = parse_coord(row[cols["coord_a"]])
            mostrar_mapa_gpx(rid, lat_s, lng_s, lat_a, lng_a)
    with c2:
        with st.expander("📌 Punts d'interès i Wikiloc"):
            if pd.notna(row[cols["wiki"]]):
                st.markdown(f'<a href="{row[cols["wiki"]]}" target="_blank" style="display:inline-block; font-size:12px; padding:6px 12px; background:#EAF3DE; color:#3B6D11; border-radius:6px; text-decoration:none; font-weight:bold; border:1px solid #C0DD97;">VEURE A WIKILOC</a>', unsafe_allow_html=True)
            st.markdown(punts_interes_html(row[cols["elements"]], row[cols["cats"]]), unsafe_allow_html=True)
