# ============================================================
# SENDERISME EN TREN — v16.1
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
/* Pestanyes principals més grans */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
}
/* Compactar expanders globals */
div[data-testid="stExpander"] {
    margin-bottom: 0 !important;
    margin-top: 0 !important;
}
div[data-testid="stExpander"] > details {
    border-radius: 0 !important;
    border: none !important;
    border-top: 1px solid #e8e8e8 !important;
}
div[data-testid="stExpander"] > details > summary {
    padding: 6px 10px !important;
    font-size: 13px !important;
    background: transparent !important;
}
div[data-testid="stExpander"] > details[open] > summary {
    border-bottom: 1px solid #ebebeb;
}
</style>
""", unsafe_allow_html=True)

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
        "<div style=\"margin-top:4px;\">"
        "<div style=\"display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;\">"
        f"{grid}</div></div>"
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
        
        lats_r = [p[0] for p in punts]
        lngs_r = [p[1] for p in punts]
        centre = (sum(lats_r) / len(lats_r), sum(lngs_r) / len(lngs_r))
        
        m = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(punts, color=COLOR_BLAU, weight=4, opacity=0.9).add_to(m)
        
        if lat_s and lng_s:
            folium.Marker([lat_s, lng_s], tooltip="Sortida",
                          icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a and lng_a and (lat_s != lat_a or lng_s != lng_a):
            folium.Marker([lat_a, lng_a], tooltip="Arribada",
                          icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        
        m.fit_bounds([[min(lats_r), min(lngs_r)], [max(lats_r), max(lngs_r)]], padding=[20, 20])
        st_folium(m, width=None, height=300, returned_objects=[], key=f"mapa_ruta_{ruta_id}")
        return True
    except:
        return False

def perfil_elevacio_svg(ruta_id, dif_color):
    gpx_url = BASE_GPX_URL.format(id=int(ruta_id))
    try:
        resp = requests.get(gpx_url, timeout=10)
        if resp.status_code != 200:
            return None, None, None
        gpx   = gpxpy.parse(resp.text)
        punts = [(p.latitude, p.longitude, p.elevation)
                 for t in gpx.tracks for s in t.segments for p in s.points
                 if p.elevation is not None]
        if len(punts) < 2:
            return None, None, None

        import math
        def haversine(p1, p2):
            R = 6371
            lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
            lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            return R * 2 * math.asin(math.sqrt(a))

        dists = [0.0]
        for i in range(1, len(punts)):
            dists.append(dists[-1] + haversine(punts[i-1], punts[i]))

        elevs = [p[2] for p in punts]
        km_total = dists[-1]
        alt_min, alt_max = min(elevs), max(elevs)
        alt_rang = max(alt_max - alt_min, 1)

        pas = max(1, len(punts) // 200)
        dists_d = dists[::pas]
        elevs_d = elevs[::pas]
        if dists_d[-1] != dists[-1]:
            dists_d.append(dists[-1])
            elevs_d.append(elevs[-1])

        w, h = 600, 180
        ml, mr, mt, mb = 48, 14, 10, 30

        def to_svg(dist, elev):
            x = ml + (dist / km_total) * (w - ml - mr)
            y = mt + (1 - (elev - alt_min) / alt_rang) * (h - mt - mb)
            return x, y

        svg_pts = [to_svg(d, e) for d, e in zip(dists_d, elevs_d)]
        poly    = " ".join(f"{x:.1f},{y:.1f}" for x, y in svg_pts)
        area    = poly + f" {svg_pts[-1][0]:.1f},{mt+h-mt-mb:.1f} {svg_pts[0][0]:.1f},{mt+h-mt-mb:.1f}"

        eix_y = ""
        for frac in [0, 0.5, 1]:
            y_s = mt + (1 - frac) * (h - mt - mb)
            val = int(alt_min + frac * alt_rang)
            eix_y += (f'<line x1="{ml-3}" y1="{y_s:.1f}" x2="{ml}" y2="{y_s:.1f}" stroke="#bbb" stroke-width="1"/>'
                      f'<text x="{ml-5}" y="{y_s+3:.1f}" text-anchor="end" font-size="8" fill="#888">{val}</text>')

        eix_x = ""
        for frac in [0, 0.25, 0.5, 0.75, 1]:
            x_s = ml + frac * (w - ml - mr)
            val = f"{frac * km_total:.1f}"
            eix_x += (f'<line x1="{x_s:.1f}" y1="{mt+h-mt-mb}" x2="{x_s:.1f}" y2="{mt+h-mt-mb+3}" stroke="#bbb" stroke-width="1"/>'
                      f'<text x="{x_s:.1f}" y="{mt+h-mt-mb+13}" text-anchor="middle" font-size="8" fill="#888">{val}</text>')

        svg = f"""<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:680px;display:block;margin:0 auto 4px;">
  <polygon points="{area}" fill="{dif_color}28"/>
  <polyline points="{poly}" fill="none" stroke="{dif_color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  <line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+h-mt-mb}" stroke="#ccc" stroke-width="1"/>
  <line x1="{ml}" y1="{mt+h-mt-mb}" x2="{w-mr}" y2="{mt+h-mt-mb}" stroke="#ccc" stroke-width="1"/>
  {eix_y}{eix_x}
  <text x="{ml-28}" y="{mt+(h-mt-mb)//2+3}" text-anchor="middle" font-size="8" fill="#aaa" transform="rotate(-90,{ml-28},{mt+(h-mt-mb)//2})">m</text>
  <text x="{(ml+w-mr)//2}" y="{h}" text-anchor="middle" font-size="8" fill="#aaa">km</text>
</svg>"""
        return svg, alt_min, alt_max
    except:
        return None, None, None


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
        lat_s, lng_s = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
        s_est = str(row[cols["sortida"]]).strip()
        afegir_estacio(lat_s, lng_s, s_est, rid, nom, "sortida")
        lat_a, lng_a = parse_coord(row[cols["coord_a"]]) if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]) else (None, None)
        a_est = str(row[cols["arribada"]]).strip()
        if a_est.lower() != s_est.lower():
            afegir_estacio(lat_a, lng_a, a_est, rid, nom, "arribada")

    if not punts_mapa:
        st.info("No hi ha coordenades disponibles per mostrar al mapa.")
        return

    m = folium.Map(location=[41.7, 1.8], zoom_start=8, tiles="OpenStreetMap")
    for (lat, lng, estacio), info in punts_mapa.items():
        tipus = info["tipus"]
        color_marker = "green" if ("sortida" in tipus and "arribada" in tipus) else ("red" if "arribada" in tipus else "blue")
        n_rutes = len(info["rutes"])
        tooltip_text = f"Estació de {estacio} ({n_rutes} {'ruta' if n_rutes == 1 else 'rutes'})"
        folium.Marker(location=[lat, lng], tooltip=tooltip_text, icon=folium.Icon(color=color_marker, icon="train", prefix="fa")).add_to(m)

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
        "temps": df_raw.columns[20] if len(df_raw.columns) > 20 else None,
        "cims_noms": df_raw.columns[22] if len(df_raw.columns) > 22 else None,
        "inici": buscar_col(["inici", "punt_inici", "punt inici"]),
        "final": buscar_col(["final", "punt_final", "punt final"]),
        "punt_alt": buscar_col(["punt_mes_alt", "punt més alt", "cim", "altitud_max"]),
        "altitud_max": buscar_col(["altitud", "cota", "metres"]),
        "terreny": buscar_col(["terreny"]),
        "epoca": buscar_col(["època", "epoca", "millor_epoca", "recomanada"]),
    }
    df = df_raw.dropna(subset=[cols["ruta"]]).copy()
    df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["desn"]: df[cols["desn"]] = pd.to_numeric(df[cols["desn"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["baixada"]: df[cols["baixada"]] = pd.to_numeric(df[cols["baixada"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error processant dades: {e}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.header("🔎 Filtres")
st.sidebar.markdown('<img src="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-100cims.svg" width="80" style="margin-bottom:5px;">', unsafe_allow_html=True)
sel_100cims = st.sidebar.checkbox("Rutes amb 100 Cims")
cerca       = st.sidebar.text_input("📝 Paraula clau")

def get_unique(col_name):
    if col_name and col_name in df.columns:
        vals = df[col_name].dropna().astype(str)
        res = set()
        for v in vals:
            for s in re.split(";|,", v):
                if s.strip(): res.add(s.strip())
        return sorted(list(res))
    return []

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

# Aplicar filtres
f = df.copy()
if sel_100cims and cols["cims"]: f = f[f[cols["cims"]].astype(str).str.strip().str.lower() == "si"]
if cerca: f = f[f[cols["ruta"]].str.contains(cerca, case=False, na=False)]
if sel_sortida: f = f[f[cols["sortida"]].astype(str).apply(lambda x: any(s in x for s in sel_sortida))]
if sel_linia: f = f[f[cols["linia_s"]].astype(str).apply(lambda x: any(l in x for l in sel_linia))]
if sel_dif: f = f[f[cols["dif"]].astype(str).apply(lambda x: any(d in x for d in sel_dif))]
if sel_comarca: f = f[f[cols["comarca"]].astype(str).apply(lambda x: any(c in x for c in sel_comarca))]
if sel_espai: f = f[f[cols["espai"]].astype(str).apply(lambda x: any(e in x for e in sel_espai))]
f = f[(f[cols["km"]] >= sel_km[0]) & (f[cols["km"]] <= sel_km[1])]
if cols["desn"]: f = f[(f[cols["desn"]] >= sel_desn[0]) & (f[cols["desn"]] <= sel_desn[1])]

if "filtre_estacio" not in st.session_state: st.session_state.filtre_estacio = None
if "map_reset_counter" not in st.session_state: st.session_state.map_reset_counter = 0

tab_llista, tab_mapa, tab_cims = st.tabs(["🥾 Rutes", "🗺️ Mapa", "🏔️ 100 Cims"])

with tab_mapa:
    mostrar_mapa_general(f, cols)
    if st.session_state.filtre_estacio:
        st.info(f"🚉 Filtrant per estació: **{st.session_state.filtre_estacio}**")
        if st.button("✖ Treure filtre d'estació", key="btn_treure_mapa"):
            st.session_state.filtre_estacio = None
            st.session_state.map_reset_counter += 1
            st.rerun()

with tab_cims:
    if "filtre_cim" not in st.session_state: st.session_state.filtre_cim = None
    if st.session_state.filtre_cim:
        st.markdown(f"### 🏔️ {st.session_state.filtre_cim}")
        if st.button("← Tornar a la llista de cims"):
            st.session_state.filtre_cim = None
            st.rerun()
        if cols.get("cims_noms"):
            f_cim = df[df[cols["cims_noms"]].astype(str).str.contains(st.session_state.filtre_cim, case=False, na=False, regex=False)]
        else: f_cim = df.iloc[0:0]
        for _, row_c in f_cim.iterrows():
            rid_c = int(row_c[cols["id"]]) if pd.notna(row_c[cols["id"]]) else ""
            nom_c = row_c[cols["ruta"]]
            dif_c = str(row_c[cols["dif"]]).strip() if pd.notna(row_c[cols["dif"]]) else ""
            color_c = DIFICULTAT_COLOR.get(dif_c.lower(), "#888888")
            st.markdown(f"<div style='margin-top:8px;background:{color_c}1a;border-left:5px solid {color_c};border-radius:8px;padding:8px 12px;display:flex;align-items:center;gap:10px;'><div style='width:24px;height:24px;border-radius:50%;background:{color_c};color:white;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;'>{rid_c}</div><div style='flex:1;font-size:14px;font-weight:600;color:#111;'>{nom_c}</div><span style='font-size:10px;font-weight:700;background:{color_c};color:white;padding:2px 8px;border-radius:20px;flex-shrink:0;text-transform:uppercase;'>{dif_c}</span></div>", unsafe_allow_html=True)
    else:
        if cols.get("cims_noms"):
            tots_cims = set()
            for val in df[cols["cims_noms"]].dropna():
                for c in str(val).split(","):
                    c = c.strip()
                    if c and c.lower() not in ("nan", "no", ""): tots_cims.add(c)
            cims_ordenats = sorted(tots_cims)
        else: cims_ordenats = []
        for nom_cim in cims_ordenats:
            n_rutes_cim = df[cols["cims_noms"]].astype(str).str.contains(nom_cim, case=False, na=False, regex=False).sum() if cols.get("cims_noms") else 0
            if st.button(f"🏔️ {nom_cim}  ·  {n_rutes_cim} {'ruta' if n_rutes_cim == 1 else 'rutes'}", key=f"cim_{nom_cim}"):
                st.session_state.filtre_cim = nom_cim
                st.rerun()

with tab_llista:
    if st.session_state.filtre_estacio:
        st.info(f"🚉 Filtrant per estació: **{st.session_state.filtre_estacio}**")
        if st.button("✖ Treure filtre d'estació"):
            st.session_state.filtre_estacio = None
            st.session_state.map_reset_counter += 1
            st.rerun()
        f = f[(f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_estacio) | (f[cols["arribada"]].astype(str).str.strip() == st.session_state.filtre_estacio)]
    
    st.write(f"**Resultats: {len(f)} rutes**")

    # CSS de colors per expander principal
    css_rules = ""
    for idx_r, (_, row_c) in enumerate(f.iterrows()):
        dif_c = str(row_c[cols["dif"]]).strip().lower() if cols.get("dif") and pd.notna(row_c[cols["dif"]]) else ""
        color_c = DIFICULTAT_COLOR.get(dif_c, "#888888")
        n = idx_r + 2
        css_rules += f"div[data-testid='stVerticalBlock'] > div:nth-child({n}) div[data-testid='stExpander'] > details > summary {{ background:{color_c}1a !important; border-left:5px solid {color_c} !important; border-radius:4px !important; }}\n"
    if css_rules: st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)

    for _, row in f.iterrows():
        ruta_id = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else None
        nom_ruta = row[cols["ruta"]]
        dif_raw = str(row[cols["dif"]]).strip() if pd.notna(row[cols["dif"]]) else ""
        dif_color = DIFICULTAT_COLOR.get(dif_raw.lower(), "#888888")
        s_est = str(row[cols["sortida"]]).strip()
        a_est = str(row[cols["arribada"]]).strip()
        tipus = str(row[cols["tipus"]]).strip().lower() if cols["tipus"] and pd.notna(row[cols["tipus"]]) else ""
        desn_pujada = row[cols["desn"]] if cols["desn"] and pd.notna(row[cols["desn"]]) else 0
        desn_baixada = row[cols["baixada"]] if cols["baixada"] and pd.notna(row[cols["baixada"]]) else 0
        lat_s, lng_s = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
        lat_a, lng_a = parse_coord(row[cols["coord_a"]]) if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]) else (None, None)
        bloc_s = bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])
        bloc_a = bloc_estacio_html(row[cols["op_a"]], row[cols["linia_a"]])
        
        # Camps addicionals
        val_tipus = "Circular" if "circular" in tipus else "Lineal"
        val_epoca = str(row[cols["epoca"]]) if cols["epoca"] and pd.notna(row[cols["epoca"]]) and str(row[cols["epoca"]]).strip() != "" else "—"
        val_cim_alt = str(row[cols["punt_alt"]]) if cols["punt_alt"] and pd.notna(row[cols["punt_alt"]]) and str(row[cols["punt_alt"]]).strip() != "" else "—"

        temps_fmt = "—"
        if cols.get("temps") and pd.notna(row[cols["temps"]]):
            try:
                hores_dec = float(str(row[cols["temps"]]).replace(",", "."))
                hores = int(hores_dec); mins = round((hores_dec - hores) * 60)
                temps_fmt = f"{hores}h{mins:02d}min" if hores > 0 and mins > 0 else (f"{hores}h" if hores > 0 else f"{mins}min")
            except: temps_fmt = str(row[cols["temps"]])

        st.markdown("<div style='border-top:1px solid #e0e0e0;margin:6px 0 2px 0;'></div>", unsafe_allow_html=True)
        expander_label = f"**{ruta_id}** · {nom_ruta}  —  {dif_raw.upper()}"

        with st.expander(expander_label):
            # MÈTRIQUES (mida reduïda a 18px per a dades)
            desn_txt = f"+/- {int(desn_pujada)} m" if "circular" in tipus else f"+{int(desn_pujada)} m / -{int(desn_baixada)} m"
            st.markdown(f"<div style='display:flex;gap:32px;margin:8px 0 14px;flex-wrap:wrap;'><div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Distància</div><div style='font-size:18px;font-weight:700;color:#111;'>{row[cols['km']]} km</div></div><div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Desnivell</div><div style='font-size:18px;font-weight:700;color:#111;'>{desn_txt}</div></div><div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Temps</div><div style='font-size:18px;font-weight:700;color:#111;'>{temps_fmt}</div></div></div>", unsafe_allow_html=True)

            # ESTACIONS AMB ETIQUETA SUPERIOR
            if s_est.lower() == a_est.lower():
                st.markdown(f"""
                    <div style="margin-bottom:12px;">
                        <div style="font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Estació de sortida/arribada</div>
                        <div style="font-size:16px;font-weight:700;display:flex;align-items:center;gap:8px;">
                            <span style="width:10px;height:10px;border-radius:50%;background:#1D9E75;display:inline-block;flex-shrink:0;"></span>
                            <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none;color:#111;">{s_est}</a> 
                            <span style="margin-left:auto;font-size:12px;font-weight:400;">{bloc_s}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="margin-bottom:10px;">
                        <div style="font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Estació de sortida</div>
                        <div style="font-size:16px;font-weight:700;display:flex;align-items:center;gap:8px;">
                            <span style="width:10px;height:10px;border-radius:50%;background:#1D9E75;display:inline-block;flex-shrink:0;"></span>
                            <a href="https://www.google.com/maps/search/{s_est}+estacio" target="_blank" style="text-decoration:none;color:#111;">{s_est}</a>
                            <span style="margin-left:auto;font-size:12px;font-weight:400;">{bloc_s}</span>
                        </div>
                    </div>
                    <div style="margin-bottom:12px;">
                        <div style="font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Estació d'arribada</div>
                        <div style="font-size:16px;font-weight:700;display:flex;align-items:center;gap:8px;">
                            <span style="width:10px;height:10px;border-radius:50%;background:#E24B4A;display:inline-block;flex-shrink:0;"></span>
                            <a href="https://www.google.com/maps/search/{a_est}+estacio" target="_blank" style="text-decoration:none;color:#111;">{a_est}</a>
                            <span style="margin-left:auto;font-size:12px;font-weight:400;">{bloc_a}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            # NOVA FILA: Tipus, Època, Cim més alt
            st.markdown(f"""
                <div style='display:flex;gap:32px;margin:12px 0 16px;flex-wrap:wrap;'>
                    <div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Tipus de ruta</div><div style='font-size:14px;font-weight:600;color:#333;'>{val_tipus}</div></div>
                    <div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Època</div><div style='font-size:14px;font-weight:600;color:#333;'>{val_epoca}</div></div>
                    <div><div style='font-size:10px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Cim més alt</div><div style='font-size:14px;font-weight:600;color:#333;'>{val_cim_alt}</div></div>
                </div>
            """, unsafe_allow_html=True)

            comarca_val = str(row[cols["comarca"]]) if pd.notna(row[cols["comarca"]]) else ""
            espai_val   = str(row[cols["espai"]])   if pd.notna(row[cols["espai"]])   else ""
            cims_val    = str(row[cols["cims"]]).strip().lower() if cols["cims"] and pd.notna(row[cols["cims"]]) else ""
            wiki_url    = str(row[cols["wiki"]])    if pd.notna(row[cols["wiki"]])    else ""
            etiquetes = ""
            if comarca_val and comarca_val != "nan": etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{comarca_val}</span>'
            if espai_val and espai_val != "nan": etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{espai_val}</span>'
            if cims_val == "si": etiquetes += '<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#E1F5EE;color:#0F6E56;border:0.5px solid #9FE1CB;margin-right:4px;">100 Cims</span>'
            if wiki_url and wiki_url != "nan": etiquetes += f'<a href="{wiki_url}" target="_blank" style="font-size:11px;padding:2px 7px;border-radius:20px;background:#EAF3DE;color:#3B6D11;border:0.5px solid #C0DD97;text-decoration:none;margin-right:4px;">Wikiloc</a>'
            if etiquetes: st.markdown(f'<div style="margin:4px 0 8px;">{etiquetes}</div>', unsafe_allow_html=True)

            # SUB-EXPANDERS (DINS LA CAIXA)
            with st.expander("🗺️ Mapa del recorregut"):
                if ruta_id:
                    if not mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
                        st.info("Mapa no disponible per aquesta ruta.")

            with st.expander("⛰️ Terreny i dificultat"):
                if ruta_id:
                    svg_perfil, alt_min, alt_max = perfil_elevacio_svg(ruta_id, dif_color)
                    if svg_perfil:
                        st.markdown(svg_perfil, unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:10px;'>Altitud mín: <b>{int(alt_min)} m</b> · Altitud màx: <b>{int(alt_max)} m</b></div>", unsafe_allow_html=True)
                    else: st.info("Perfil d'elevació no disponible per aquesta ruta.")
                nivells = [("Molt fàcil", "#2196A6"), ("Fàcil", "#1D9E75"), ("Moderada", "#EF9F27"), ("Difícil", "#E24B4A"), ("Molt difícil", "#9B1B1B")]
                claus_norm = ["molt facil", "facil", "moderada", "dificil", "molt dificil"]
                def normalitza(s): return s.lower().replace("í","i").replace("à","a").replace("è","e").replace("ó","o").replace("ú","u").strip()
                pos_actual = next((i for i, c in enumerate(claus_norm) if c == normalitza(dif_raw)), -1)
                segments = ""
                for i, (nom_niv, color_niv) in enumerate(nivells):
                    actiu = (i == pos_actual); opacity = "1" if actiu else "0.22"; radius = ("6px 0 0 6px" if i == 0 else ("0 6px 6px 0" if i == 4 else "0"))
                    dot = f'<div style="width:13px;height:13px;border-radius:50%;background:{color_niv};border:2.5px solid #111;position:absolute;top:-8px;left:50%;transform:translateX(-50%);box-shadow:0 1px 4px rgba(0,0,0,0.35);z-index:2;"></div>' if actiu else ""
                    segments += f'<div style="flex:1;position:relative;">{dot}<div style="height:10px;background:{color_niv};opacity:{opacity};border-radius:{radius};"></div><div style="font-size:9px;color:#555;text-align:center;margin-top:4px;font-weight:{"700" if actiu else "400"};">{nom_niv}</div></div>'
                st.markdown(f'<div style="margin-top:6px;"><div style="font-size:11px;color:#888;margin-bottom:12px;">Dificultat</div><div style="display:flex;gap:2px;">{segments}</div></div>', unsafe_allow_html=True)

            with st.expander("📌 Punts d'interès"):
                elements_str = row[cols["elements"]] if cols["elements"] and pd.notna(row[cols["elements"]]) else ""
                cats_str     = row[cols["cats"]]     if cols["cats"]     and pd.notna(row[cols["cats"]])     else ""
                if elements_str: st.markdown(punts_interes_html(elements_str, cats_str), unsafe_allow_html=True)
                else: st.info("No hi ha punts d'interès registrats.")
