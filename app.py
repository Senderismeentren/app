# ============================================================
# SENDERISME EN TREN — v16
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
COLOR_VERD       = "#2d9e6b"

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
        horari  = f'<a href="{info["url"]}" target="_blank" style="font-size:12px;color:{COLOR_BLAU};text-decoration:none;font-weight:bold;margin-left:5px;">HORARI</a>'
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
            "<div style=\"display:flex;align-items:center;gap:8px;background:#f8f9fa;"
            "border-radius:8px;padding:7px 10px;font-size:13px;color:#333;\">"
            f"<span style=\"font-size:18px;\">{icona}</span><span>{element}</span></div>"
        )
    grid = "".join(targetes)
    return (
        "<div style=\"margin-top:10px;\">"
        "<div style=\"font-size:14px;font-weight:bold;color:#333;margin-bottom:8px;\">📌 Punts d'interès</div>"
        "<div style=\"display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;\">"
        f"{grid}</div></div>"
    )

def metric_box(label, value):
    return (
        "<div style=\"flex:1;background:white;border:0.5px solid #e0e0e0;border-radius:8px;"
        "padding:5px 8px;display:flex;align-items:center;gap:8px;\">"
        f"<div style=\"font-size:11px;color:#888;white-space:nowrap;\">{label}</div>"
        f"<div style=\"font-size:14px;font-weight:bold;color:#333;white-space:nowrap;\">{value}</div>"
        "</div>"
    )

def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
    gpx_url = BASE_GPX_URL.format(id=int(ruta_id))
    try:
        resp  = requests.get(gpx_url, timeout=10)
        if resp.status_code != 200:
            return False
        gpx   = gpxpy.parse(resp.text)
        punts = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
        if not punts:
            return False
        centre = (sum(p[0] for p in punts) / len(punts), sum(p[1] for p in punts) / len(punts))
        m = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(punts, color=COLOR_BLAU, weight=4, opacity=0.9).add_to(m)
        if lat_s and lng_s:
            folium.Marker([lat_s, lng_s], tooltip="Sortida",
                          icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a and lng_a and (lat_s != lat_a or lng_s != lng_a):
            folium.Marker([lat_a, lng_a], tooltip="Arribada",
                          icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        st_folium(m, width=None, height=300, returned_objects=[], key=f"mapa_ruta_{ruta_id}")
        return True
    except:
        return False

def mostrar_mapa_general(df_filtrat, cols):
    punts_mapa = {}

    def afegir_estacio(lat, lng, estacio, rid, nom, tipus):
        if not lat or not lng:
            return
        key = (lat, lng, estacio)
        if key not in punts_mapa:
            punts_mapa[key] = {"tipus": set(), "rutes": []}
        punts_mapa[key]["tipus"].add(tipus)
        punts_mapa[key]["rutes"].append(f"Ruta {rid}: {nom}")

    for _, row in df_filtrat.iterrows():
        nom = str(row[cols["ruta"]])
        rid = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""

        # Estació de sortida
        lat_s, lng_s = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
        s_est = str(row[cols["sortida"]]).strip()
        afegir_estacio(lat_s, lng_s, s_est, rid, nom, "sortida")

        # Estació d'arribada (si té coordenades i és diferent de la sortida)
        lat_a, lng_a = parse_coord(row[cols["coord_a"]]) if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]) else (None, None)
        a_est = str(row[cols["arribada"]]).strip()
        if a_est.lower() != s_est.lower():
            afegir_estacio(lat_a, lng_a, a_est, rid, nom, "arribada")

    if not punts_mapa:
        st.info("No hi ha coordenades disponibles per mostrar al mapa.")
        return

    lats   = [k[0] for k in punts_mapa]
    lngs   = [k[1] for k in punts_mapa]
    centre = (sum(lats) / len(lats), sum(lngs) / len(lngs))
    m = folium.Map(location=centre, zoom_start=9, tiles="OpenStreetMap")

    for (lat, lng, estacio), info in punts_mapa.items():
        tipus = info["tipus"]
        # Blau = només sortida | Vermell = només arribada | Verd = ambdues
        if "sortida" in tipus and "arribada" in tipus:
            color_marker = "green"
        elif "arribada" in tipus:
            color_marker = "red"
        else:
            color_marker = "blue"
        n_rutes = len(info["rutes"])
        paraula = "ruta" if n_rutes == 1 else "rutes"
        tooltip_text = f"Estació de {estacio} ({n_rutes} {paraula})"
        folium.Marker(
            location=[lat, lng],
            tooltip=tooltip_text,
            icon=folium.Icon(color=color_marker, icon="train", prefix="fa")
        ).add_to(m)

    # Key dinàmica per permetre el reset del mapa al treure el filtre
    map_key = f"mapa_general_{st.session_state.get('map_reset_counter', 0)}"
    resultat = st_folium(m, width=None, height=350, returned_objects=["last_object_clicked_tooltip"], key=map_key)

    if resultat and resultat.get("last_object_clicked_tooltip"):
        tooltip = resultat["last_object_clicked_tooltip"]
        estacio_clicada = re.sub(r"\s*\(\d+ rutes?\)$", "", tooltip.replace("Estació de ", "")).strip()
        if estacio_clicada != st.session_state.filtre_estacio:
            st.session_state.filtre_estacio = estacio_clicada
            st.rerun()

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
        "baixada":  buscar_col(["negatiu"]),
        "tipus":    buscar_col(["tipus"]),
        "dif":      buscar_col(["dificultat"]),
        "wiki":     buscar_col(["enllaç_wikiloc", "wikiloc"]),
        "elements": buscar_col(["elements_interès", "elements_interes"]),
        "cats":     buscar_col(["categories_elements_interès", "categories_elements_interes"]),
        "coord_s":  buscar_col(["coordenades_sortida"]),
        "coord_a":  buscar_col(["coordenades_arribada"]),
    }

    df = df_raw.dropna(subset=[cols["ruta"]]).copy()
    df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["desn"]:
        df[cols["desn"]] = pd.to_numeric(df[cols["desn"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["baixada"]:
        df[cols["baixada"]] = pd.to_numeric(df[cols["baixada"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    def get_unique(col_name):
        if col_name and col_name in df.columns:
            vals = df[col_name].dropna().astype(str)
            res  = set()
            for v in vals:
                for s in re.split(";|,", v):
                    if s.strip(): res.add(s.strip())
            return sorted(list(res))
        return []

    # --- FILTRES SIDEBAR ---
    st.sidebar.header("🔎 Filtres")
    st.sidebar.markdown(
        '<img src="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-100cims.svg" width="80" style="margin-bottom:5px;">',
        unsafe_allow_html=True
    )
    sel_100cims = st.sidebar.checkbox("Rutes amb 100 Cims")
    cerca       = st.sidebar.text_input("📝 Paraula clau")
    sel_sortida = st.sidebar.multiselect("🚉 Estació de sortida", get_unique(cols["sortida"]))
    sel_linia   = st.sidebar.multiselect("🚆 Línia de tren", get_unique(cols["linia_s"]))
    sel_dif     = st.sidebar.multiselect("🧗 Dificultat", get_unique(cols["dif"]))
    min_desn    = float(df[cols["desn"]].min()) if cols["desn"] else 0.0
    max_desn    = float(df[cols["desn"]].max()) if cols["desn"] else 9999.0
    sel_desn    = st.sidebar.slider("📈 Desnivell (m)", min_desn, max_desn, (min_desn, max_desn))
    sel_comarca = st.sidebar.multiselect("📍 Comarca", get_unique(cols["comarca"]))
    sel_espai   = st.sidebar.multiselect("🌲 Espai natural", get_unique(cols["espai"]))
    min_km, max_km = float(df[cols["km"]].min()), float(df[cols["km"]].max())
    sel_km      = st.sidebar.slider("📏 Distància (km)", min_km, max_km, (min_km, max_km))

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

    # --- ESTAT FILTRE ESTACIÓ ---
    if "filtre_estacio" not in st.session_state:
        st.session_state.filtre_estacio = None
    if "map_reset_counter" not in st.session_state:
        st.session_state.map_reset_counter = 0

    # --- MAPA GENERAL DESPLEGABLE ---
    with st.expander(f"🗺️ Veure mapa de rutes ({len(f)})", expanded=False):
        mostrar_mapa_general(f, cols)

    # --- FILTRE PER ESTACIÓ DES DEL MAPA ---
    if st.session_state.filtre_estacio:
        st.info(f"🚉 Filtrant per estació: **{st.session_state.filtre_estacio}**")
        if st.button("✖ Treure filtre d'estació"):
            st.session_state.filtre_estacio = None
            st.session_state.map_reset_counter += 1 # Reset del mapa
            st.rerun()
        f = f[
            (f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_estacio) |
            (f[cols["arribada"]].astype(str).str.strip() == st.session_state.filtre_estacio)
        ]

    st.write(f"**Resultats: {len(f)} rutes**")

    # --- BUCLE DE RUTES ---
    for _, row in f.iterrows():
        ruta_id      = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else None
        nom_ruta     = row[cols["ruta"]]
        desc         = str(row[cols["desc"]]).strip() if cols["desc"] and pd.notna(row[cols["desc"]]) else ""
        s_est        = str(row[cols["sortida"]]).strip()
        a_est        = str(row[cols["arribada"]]).strip()
        dif_raw      = str(row[cols["dif"]]).strip() if pd.notna(row[cols["dif"]]) else ""
        dif_color    = DIFICULTAT_COLOR.get(dif_raw.lower(), "#888888")
        tipus        = str(row[cols["tipus"]]).strip().lower() if cols["tipus"] and pd.notna(row[cols["tipus"]]) else ""
        desn_pujada  = row[cols["desn"]]    if cols["desn"]    and pd.notna(row[cols["desn"]])    else 0
        desn_baixada = row[cols["baixada"]] if cols["baixada"] and pd.notna(row[cols["baixada"]]) else 0

        lat_s, lng_s = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
        lat_a, lng_a = parse_coord(row[cols["coord_a"]]) if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]) else (None, None)

        bloc_s = bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])
        bloc_a = bloc_estacio_html(row[cols["op_a"]], row[cols["linia_a"]])

        # SEPARADOR LLEUGER
        st.markdown("<div style='border-top:1px solid #e0e0e0;margin:6px 0 4px 0;'></div>", unsafe_allow_html=True)

        # CAPÇALERA AMB DEGRADAT DE COLOR
        st.markdown(
            f"<div style=\"background:linear-gradient(90deg,{dif_color}cc 0%,{dif_color}33 60%,transparent 100%);"
            f"border-radius:6px;padding:8px 12px;display:flex;align-items:center;gap:10px;\">"
            f"<div style=\"width:26px;height:26px;border-radius:50%;background:{dif_color};color:white;"
            f"font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;"
            f"flex-shrink:0;\">{ruta_id}</div>"
            f"<div style=\"flex:1;\">"
            f"<div style=\"font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,0.3);\">{nom_ruta}</div>"
            f"<div style=\"font-size:11px;color:rgba(255,255,255,0.85);\">{desc}</div>"
            f"</div>"
            f"<span style=\"font-size:10px;font-weight:700;background:rgba(255,255,255,0.25);color:white;"
            f"padding:2px 8px;border-radius:20px;border:1px solid rgba(255,255,255,0.5);flex-shrink:0;"
            f"text-transform:uppercase;letter-spacing:0.5px;\">{dif_raw}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        # MÈTRIQUES COMPACTES
        if "circular" in tipus:
            desn_html = metric_box("Desnivell", f"+/- {desn_pujada} m")
        else:
            desn_html = metric_box("Desnivell pujada", f"+{desn_pujada} m") + metric_box("Desnivell baixada", f"-{desn_baixada} m")

        st.markdown(
            "<div style=\"display:flex;gap:6px;margin:6px 0;flex-wrap:wrap;\">"
            + metric_box("Distància", f"{row[cols['km']]} km")
            + desn_html
            + "</div>",
            unsafe_allow_html=True
        )

        # ESTACIONS
        if s_est.lower() == a_est.lower():
            st.markdown(
                f"<div style=\"font-size:13px;margin:4px 0 2px;display:flex;align-items:center;gap:6px;\">"
                f"<span style=\"width:9px;height:9px;border-radius:50%;background:#1D9E75;display:inline-block;flex-shrink:0;\"></span>"
                f"<strong><a href=\"https://www.google.com/maps/search/{s_est}+estacio\" target=\"_blank\" style=\"text-decoration:none;color:#111;\">{s_est}</a></strong>"
                f"<span style=\"margin-left:auto;\">{bloc_s}</span></div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style=\"font-size:13px;margin:4px 0 2px;display:flex;align-items:center;gap:6px;\">"
                f"<span style=\"width:9px;height:9px;border-radius:50%;background:#1D9E75;display:inline-block;flex-shrink:0;\"></span>"
                f"<strong><a href=\"https://www.google.com/maps/search/{s_est}+estacio\" target=\"_blank\" style=\"text-decoration:none;color:#111;\">{s_est}</a></strong>"
                f"<span style=\"margin-left:auto;\">{bloc_s}</span></div>"
                f"<div style=\"font-size:13px;margin:2px 0 6px;display:flex;align-items:center;gap:6px;\">"
                f"<span style=\"width:9px;height:9px;border-radius:50%;background:#E24B4A;display:inline-block;flex-shrink:0;\"></span>"
                f"<strong><a href=\"https://www.google.com/maps/search/{a_est}+estacio\" target=\"_blank\" style=\"text-decoration:none;color:#111;\">{a_est}</a></strong>"
                f"<span style=\"margin-left:auto;\">{bloc_a}</span></div>",
                unsafe_allow_html=True
            )

        # ETIQUETES
        comarca_val = str(row[cols["comarca"]]) if pd.notna(row[cols["comarca"]]) else ""
        espai_val   = str(row[cols["espai"]])   if pd.notna(row[cols["espai"]])   else ""
        cims_val    = str(row[cols["cims"]]).strip().lower() if cols["cims"] and pd.notna(row[cols["cims"]]) else ""
        wiki_url    = str(row[cols["wiki"]])    if pd.notna(row[cols["wiki"]])    else ""

        etiquetes = ""
        if comarca_val and comarca_val != "nan":
            etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{comarca_val}</span>'
        if espai_val and espai_val != "nan":
            etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{espai_val}</span>'
        if cims_val == "si":
            etiquetes += '<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#E1F5EE;color:#0F6E56;border:0.5px solid #9FE1CB;margin-right:4px;">100 Cims</span>'
        if wiki_url and wiki_url != "nan":
            etiquetes += f'<a href="{wiki_url}" target="_blank" style="font-size:11px;padding:2px 7px;border-radius:20px;background:#EAF3DE;color:#3B6D11;border:0.5px solid #C0DD97;text-decoration:none;margin-right:4px;">Wikiloc</a>'

        if etiquetes:
            st.markdown(f'<div style="margin:6px 0 4px;">{etiquetes}</div>', unsafe_allow_html=True)

        # DESPLEGABLES
        with st.expander("🗺️ Mapa del recorregut"):
            if ruta_id:
                if not mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
                    st.info("Mapa no disponible per aquesta ruta.")

        with st.expander("📌 Punts d'interès"):
            elements_str = row[cols["elements"]] if cols["elements"] and pd.notna(row[cols["elements"]]) else ""
            cats_str     = row[cols["cats"]]     if cols["cats"]     and pd.notna(row[cols["cats"]])     else ""
            if elements_str:
                st.markdown(punts_interes_html(elements_str, cats_str), unsafe_allow_html=True)
            else:
                st.info("No hi ha punts d'interès registrats.")

except Exception as e:
    st.error(f"S'ha produït un error: {e}")
