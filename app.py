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

st.markdown("""
<style>
/* Pestanyes principals més grans */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-size: 15px !important;
    font-weight: 700 !important;
    padding: 10px 18px !important;
    letter-spacing: 0.2px !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] p {
    font-size: 15px !important;
    font-weight: 700 !important;
}
/* Mapa expander text més gran */
div[data-testid="stExpander"] > details > summary {
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 10px 12px !important;
}
/* Ocultar arrow per defecte de Streamlit */
div[data-testid="stExpander"] > details > summary svg {
    display: none !important;
}
div[data-testid="stExpander"] > details > summary > div > svg {
    display: none !important;
}
div[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] {
    display: none !important;
}
div[data-testid="stExpander"] > details > summary::before {
    content: '';
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-right: 8px;
    flex-shrink: 0;
    background-image: url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 12 12' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M2 4l4 4 4-4' stroke='%23888' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: center;
    transition: transform 0.2s;
}
div[data-testid="stExpander"] > details[open] > summary::before {
    transform: rotate(180deg);
}
</style>
""", unsafe_allow_html=True)

# --- CAPÇALERA AMB IMATGE DE PORTADA ---
portada_url = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/imatges/portada.png"
logo_url    = "https://avatars.githubusercontent.com/u/279401247?v=4"
st.markdown(f'''
    <div style="position:relative;width:100%;height:280px;border-radius:12px;overflow:hidden;margin-bottom:0;">
        <img src="{portada_url}" style="width:100%;height:100%;object-fit:cover;object-position:right center;">
        <div style="position:absolute;inset:0;background:linear-gradient(to right,rgba(0,0,0,0.55) 0%,rgba(0,0,0,0.1) 60%,transparent 100%);"></div>
        <div style="position:absolute;top:18px;left:50%;transform:translateX(-50%);">
            <img src="{logo_url}" style="width:48px;height:48px;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.4);">
        </div>
        <div style="position:absolute;bottom:28px;left:28px;">
            <h1 style="margin:0;font-size:32px;font-weight:800;color:white;text-shadow:0 2px 6px rgba(0,0,0,0.5);">Senderisme en tren</h1>
            <p style="margin:6px 0 0 0;font-size:15px;color:rgba(255,255,255,0.9);text-shadow:0 1px 4px rgba(0,0,0,0.4);">Rutes i excursions a peu amb accés en tren, metro, cremallera o funicular.</p>
        </div>
    </div>
''', unsafe_allow_html=True)

# --- COLOR DE FONS FIX ---
st.markdown(
    "<style>section[data-testid='stMain'] > div, .main .block-container { background-color: #f5f5f5 !important; }"
    "div[data-testid='stExpander'] { background: white !important; }"
    "div[data-testid='stExpander'] > details { background: white !important; }"
    "div[data-testid='stExpander'] > details > summary { background: white !important; }"
    "</style>",
    unsafe_allow_html=True
)

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

@st.cache_data(ttl=60)
def obtenir_horaris_rodalies(estacio, num_resultats=8):
    """Consulta horaris en temps real de Rodalies via API pública"""
    try:
        # API pública de Rodalies de Catalunya
        url = f"https://rodalies.gencat.cat/ca/inici/horaris-temps-real/?origen={estacio.replace(' ', '+')}"
        # Intentem l'API JSON si disponible
        api_url = f"https://api.rodalies.gencat.cat/v1/departures?station={estacio}&limit={num_resultats}"
        resp = requests.get(api_url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), "api"
    except:
        pass
    return None, "link"

def horaris_html_bloc(estacio, linia_str, op_str, dif_color, tipus_estacio="sortida"):
    """Genera HTML d'horaris per a una estació"""
    op_lower = str(op_str).lower() if op_str else ""
    linies = [l.strip() for l in str(linia_str).split(";") if l.strip() and l.strip().lower() != "nan"]

    if "rodalies" in op_lower or "renfe" in op_lower:
        url_horaris = f"https://rodalies.gencat.cat/ca/inici/horaris/?origen={estacio.replace(' ', '+')}"
        nom_op = "Rodalies"
    elif "fgc" in op_lower:
        url_horaris = f"https://www.fgc.cat/viatjar/horaris/?origen={estacio.replace(' ', '+')}"
        nom_op = "FGC"
    elif "metro" in op_lower or "tmb" in op_lower:
        url_horaris = "https://www.tmb.cat/ca/barcelona/horaris-metro"
        nom_op = "Metro TMB"
    else:
        url_horaris = f"https://rodalies.gencat.cat/ca/inici/horaris/?origen={estacio.replace(' ', '+')}"
        nom_op = "Rodalies"

    linies_html = "".join(
        f"<img src='https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{l}.svg' "
        f"style='height:16px;margin-right:3px;vertical-align:middle;' onerror=\"this.style.display='none'\">"
        for l in linies
    )

    titol = "Sortida" if tipus_estacio == "sortida" else "Arribada (tornada)"
    icon = "🟢" if tipus_estacio == "sortida" else "🔴"

    return (
        f"<div style='margin-bottom:14px;'>"
        f"<div style='font-size:12px;font-weight:700;color:#555;margin-bottom:4px;'>"
        f"{icon} {titol}: {estacio}</div>"
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px;'>"
        f"{linies_html}"
        f"<a href='{url_horaris}' target='_blank' "
        f"style='font-size:11px;font-weight:700;color:{dif_color};text-decoration:none;'>"
        f"HORARI {nom_op.upper()} →</a></div>"
        f"<div style='background:#f8f9fa;border-radius:6px;padding:8px 10px;font-size:12px;'>"
        f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr;gap:2px;margin-bottom:6px;'>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Destinació</span>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Línia</span>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Hora</span></div>"
        f"<div style='color:#888;font-size:11px;padding:4px 0;font-style:italic;'>Clica HORARI per veure els propers trens en temps real</div>"
        f"</div></div>"
    )

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
        # Ajustar zoom per mostrar tota la ruta
        lats_r = [p[0] for p in punts]
        lngs_r = [p[1] for p in punts]
        centre = (sum(lats_r) / len(lats_r), sum(lngs_r) / len(lngs_r))

        # Calcular zoom automàtic a partir de l'extensió de la ruta
        import math
        lat_range = max(lats_r) - min(lats_r)
        lng_range = max(lngs_r) - min(lngs_r)
        max_range = max(lat_range, lng_range)
        if max_range < 0.02:
            zoom = 14
        elif max_range < 0.05:
            zoom = 13
        elif max_range < 0.1:
            zoom = 12
        elif max_range < 0.2:
            zoom = 11
        elif max_range < 0.5:
            zoom = 10
        elif max_range < 1.0:
            zoom = 9
        else:
            zoom = 8

        m = folium.Map(location=centre, zoom_start=zoom, tiles="OpenStreetMap")
        folium.PolyLine(punts, color=COLOR_BLAU, weight=4, opacity=0.9).add_to(m)
        if lat_s and lng_s:
            folium.Marker([lat_s, lng_s], tooltip="Sortida",
                          icon=folium.Icon(color="blue", icon="train", prefix="fa")).add_to(m)
        if lat_a and lng_a and (lat_s != lat_a or lng_s != lng_a):
            folium.Marker([lat_a, lng_a], tooltip="Arribada",
                          icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
        st_folium(m, use_container_width=True, height=300, returned_objects=[], key=f"mapa_ruta_{ruta_id}")
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

        # Distàncies acumulades (km)
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

        # Diezmem a ~200 punts per rendiment
        pas = max(1, len(punts) // 200)
        dists_d = dists[::pas]
        elevs_d = elevs[::pas]
        if dists_d[-1] != dists[-1]:
            dists_d.append(dists[-1])
            elevs_d.append(elevs[-1])

        # SVG
        w, h = 600, 180
        ml, mr, mt, mb = 48, 14, 10, 30

        def to_svg(dist, elev):
            x = ml + (dist / km_total) * (w - ml - mr)
            y = mt + (1 - (elev - alt_min) / alt_rang) * (h - mt - mb)
            return x, y

        svg_pts = [to_svg(d, e) for d, e in zip(dists_d, elevs_d)]
        poly    = " ".join(f"{x:.1f},{y:.1f}" for x, y in svg_pts)
        area    = poly + f" {svg_pts[-1][0]:.1f},{mt+h-mt-mb:.1f} {svg_pts[0][0]:.1f},{mt+h-mt-mb:.1f}"

        # Eixos Y (altitud)
        eix_y = ""
        for frac in [0, 0.5, 1]:
            y_s = mt + (1 - frac) * (h - mt - mb)
            val = int(alt_min + frac * alt_rang)
            eix_y += (f'<line x1="{ml-3}" y1="{y_s:.1f}" x2="{ml}" y2="{y_s:.1f}" stroke="#bbb" stroke-width="1"/>'
                      f'<text x="{ml-5}" y="{y_s+3:.1f}" text-anchor="end" font-size="8" fill="#888">{val}</text>')

        # Eixos X (km)
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
    # Centre i zoom per mostrar tota Catalunya
    m = folium.Map(location=[41.7, 1.8], zoom_start=8, tiles="OpenStreetMap")

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
def render_caixa_ruta(row, cols):
    """Renderitza una caixa de ruta en format complet (igual que la pestanya Rutes)"""
    ruta_id  = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""
    nom_ruta = row[cols["ruta"]]
    dif_raw  = str(row[cols["dif"]]).strip() if pd.notna(row[cols["dif"]]) else ""
    dif_color = DIFICULTAT_COLOR.get(dif_raw.lower(), "#888888")
    km_val   = row[cols["km"]] if cols.get("km") and pd.notna(row[cols["km"]]) else "—"
    desn_p   = row[cols["desn"]] if cols.get("desn") and pd.notna(row[cols["desn"]]) else 0
    desn_n   = row[cols["baixada"]] if cols.get("baixada") and pd.notna(row[cols["baixada"]]) else 0
    tipus_r  = str(row[cols["tipus"]]).strip().lower() if cols.get("tipus") and pd.notna(row[cols["tipus"]]) else ""

    if "circular" in tipus_r:
        desn_txt = f"+/- {int(desn_p)} m"
    else:
        desn_txt = f"+{int(desn_p)} m / -{int(desn_n)} m"

    temps_fmt = "—"
    if cols.get("temps") and pd.notna(row[cols["temps"]]):
        try:
            hd = float(str(row[cols["temps"]]).replace(",", "."))
            h, mn = int(hd), round((hd - int(hd)) * 60)
            temps_fmt = f"{h}h{mn:02d}min" if h > 0 and mn > 0 else (f"{h}h" if h > 0 else f"{mn}min")
        except: pass

    comarca_val = str(row[cols["comarca"]]) if cols.get("comarca") and pd.notna(row[cols["comarca"]]) else ""
    espai_val   = str(row[cols["espai"]])   if cols.get("espai")   and pd.notna(row[cols["espai"]])   else ""
    cims_val    = str(row[cols["cims"]]).strip().lower() if cols.get("cims") and pd.notna(row[cols["cims"]]) else ""
    wiki_url    = str(row[cols["wiki"]])    if cols.get("wiki")    and pd.notna(row[cols["wiki"]])    else ""

    etiquetes = ""
    if comarca_val and comarca_val != "nan":
        etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{comarca_val}</span>'
    if espai_val and espai_val != "nan":
        etiquetes += f'<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#f0f2f6;color:#555;border:0.5px solid #ddd;margin-right:4px;">{espai_val}</span>'
    if cims_val == "si":
        etiquetes += '<span style="font-size:11px;padding:2px 7px;border-radius:20px;background:#E1F5EE;color:#0F6E56;border:0.5px solid #9FE1CB;margin-right:4px;">100 Cims</span>'
    if wiki_url and wiki_url != "nan":
        etiquetes += f'<a href="{wiki_url}" target="_blank" style="font-size:11px;padding:2px 7px;border-radius:20px;background:#EAF3DE;color:#3B6D11;border:0.5px solid #C0DD97;text-decoration:none;margin-right:4px;">Wikiloc</a>'

    etiquetes_html = f"<div style='padding:2px 12px 8px;'>{etiquetes}</div>" if etiquetes else ""

    st.markdown(
        f"<div style='margin-top:12px;border:1px solid {dif_color}44;border-left:5px solid {dif_color};"
        f"border-radius:8px;overflow:visible;background:white;'>"
        f"<div style='background:{dif_color}18;padding:10px 12px;display:flex;align-items:center;gap:10px;'>"
        f"<div style='width:26px;height:26px;border-radius:50%;background:{dif_color};color:white;"
        f"font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;'>{ruta_id}</div>"
        f"<div style='flex:1;font-size:14px;font-weight:700;color:#111;'>{nom_ruta}</div>"
        f"<span style='font-size:10px;font-weight:700;background:{dif_color};color:white;"
        f"padding:2px 9px;border-radius:20px;flex-shrink:0;text-transform:uppercase;letter-spacing:0.5px;'>{dif_raw}</span>"
        f"</div>"
        f"<div style='padding:6px 12px 4px;display:flex;gap:20px;flex-wrap:wrap;'>"
        f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Distància</div>"
        f"<div style='font-size:14px;font-weight:700;color:#111;'>{km_val} km</div></div>"
        f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Desnivell</div>"
        f"<div style='font-size:14px;font-weight:700;color:#111;'>{desn_txt}</div></div>"
        f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Temps</div>"
        f"<div style='font-size:14px;font-weight:700;color:#111;'>{temps_fmt}</div></div>"
        f"</div>"
        + etiquetes_html +
        f"</div>",
        unsafe_allow_html=True
    )


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
        "id":        buscar_col(["núm_ruta", "num_ruta", "id_ruta", "id"]),
        "ruta":      buscar_col(["nom_ruta", "nom_de_la_ruta"]),
        "desc":      buscar_col(["descripció", "descripcio", "subtitol", "comentaris"]),
        "km":        buscar_col(["km"]),
        "cims":      buscar_col(["100cims", "100_cims"]),
        "sortida":   buscar_col(["estació_sortida", "estacio_sortida", "sortida"]),
        "id_est_s":  buscar_col(["id_estació_sortida", "id_estacio_sortida"]),
        "op_s":      buscar_col(["operador_sortida"]),
        "arribada":  buscar_col(["estació_arribada", "estacio_arribada", "arribada"]),
        "id_est_a":  buscar_col(["id_estació_arribada", "id_estacio_arribada"]),
        "op_a":      buscar_col(["operador_arribada"]),
        "linia_s":   buscar_col(["linies_sortida"]),
        "linia_a":   buscar_col(["linies_arribada"]),
        "comarca":   buscar_col(["comarca_sortida", "comarca"]),
        "espai":     buscar_col(["espai_natural"]),
        "desn":      buscar_col(["desnivell_positiu"]),
        "baixada":   buscar_col(["desnivell_negatiu", "negatiu"]),
        "tipus":     buscar_col(["tipus_ruta", "tipus"]),
        "dif":       buscar_col(["dificultat"]),
        "wiki":      buscar_col(["enllaç_wikiloc", "wikiloc"]),
        "elements":  buscar_col(["elements_interès", "elements_interes"]),
        "cats":      buscar_col(["categories_elements_interès", "categories_elements_interes"]),
        "coord_s":   buscar_col(["coordenades_sortida"]),
        "coord_a":   buscar_col(["coordenades_arribada"]),
        "temps":     buscar_col(["durada_estimada", "durada", "temps"]),
        "cims_noms": buscar_col(["nom_100cims", "nom_100_cims"]),
        "punt_alt":  buscar_col(["punt_mes_alt", "punt_més_alt"]),
        "altitud_max": buscar_col(["alçada_punt_alt", "alcada_punt_alt"]),
        "terreny":   buscar_col(["senders", "terreny"]),
        "epoca":     buscar_col(["millor_època", "millor_epoca"]),
        "coord_cim": buscar_col(["coordenades_100cims"]),
        "comentaris": buscar_col(["comentaris", "comentari", "notes"]),
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
    sel_op      = st.sidebar.multiselect("🏢 Operador", get_unique(cols["op_s"]))
    sel_dif     = st.sidebar.multiselect("🧗 Dificultat", ["Molt fàcil","Fàcil","Moderada","Difícil","Molt difícil"])
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
    if sel_op and cols.get("op_s"):
        f = f[f[cols["op_s"]].astype(str).apply(lambda x: any(o in x for o in sel_op))]
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

    # --- PESTANYES ---
    tab_llista, tab_mapa, tab_cims = st.tabs(["🥾 Rutes", "🗺️ Mapa", "🏔️ 100 Cims"])

    with tab_mapa:
        mostrar_mapa_general(f, cols)
        if st.session_state.filtre_estacio:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.info(f"🚉 Estació: **{st.session_state.filtre_estacio}**")
            with col_btn:
                if st.button("✖ Treure filtre", key="btn_treure_mapa"):
                    st.session_state.filtre_estacio = None
                    st.session_state.map_reset_counter += 1
                    st.rerun()
            f_mapa = df[
                (df[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_estacio) |
                (df[cols["arribada"]].astype(str).str.strip() == st.session_state.filtre_estacio)
            ]
            st.write(f"**{len(f_mapa)} rutes amb {st.session_state.filtre_estacio}**")
            for _, row_m in f_mapa.iterrows():
                render_caixa_ruta(row_m, cols)

    with tab_cims:
        # Inicialitzar filtre de cim
        if "filtre_cim" not in st.session_state:
            st.session_state.filtre_cim = None

        if st.session_state.filtre_cim:
            # MODE FILTRE: mostrar rutes que visiten aquest cim
            st.markdown(f"### 🏔️ {st.session_state.filtre_cim}")
            if st.button("← Tornar a la llista de cims"):
                st.session_state.filtre_cim = None
                st.rerun()
            # Filtrar rutes que contenen el cim a la columna W
            if cols.get("cims_noms"):
                f_cim = df[df[cols["cims_noms"]].astype(str).str.contains(
                    st.session_state.filtre_cim, case=False, na=False, regex=False
                )]
            else:
                f_cim = df.iloc[0:0]
            st.write(f"**{len(f_cim)} rutes visiten aquest cim**")
            for _, row_c in f_cim.iterrows():
                render_caixa_ruta(row_c, cols)
        else:
            # MODE LLISTA: cims agrupats per comarca de l'estació de sortida
            if cols.get("cims_noms") and cols.get("comarca"):
                # Construir dict: cim -> set de comarques
                cim_comarques = {}
                for _, row_ci in df.iterrows():
                    val_cims = str(row_ci[cols["cims_noms"]]) if pd.notna(row_ci[cols["cims_noms"]]) else ""
                    comarca_ci = str(row_ci[cols["comarca"]]).strip() if pd.notna(row_ci[cols["comarca"]]) else ""
                    for c in val_cims.split(","):
                        c = c.strip()
                        if c and c.lower() not in ("nan", "no", ""):
                            if c not in cim_comarques:
                                cim_comarques[c] = set()
                            if comarca_ci and comarca_ci.lower() not in ("nan", ""):
                                cim_comarques[c].add(comarca_ci)

                # Agrupar cims per comarca
                comarca_cims = {}
                for cim, comarques in cim_comarques.items():
                    comarca_key = ", ".join(sorted(comarques)) if comarques else "Sense comarca"
                    if comarca_key not in comarca_cims:
                        comarca_cims[comarca_key] = []
                    comarca_cims[comarca_key].append(cim)

                total_cims = len(cim_comarques)
                n_rutes_cims = len(df[df[cols["cims"]].astype(str).str.strip().str.lower() == "si"]) if cols.get("cims") else 0
                st.markdown(
                    f"<div style='font-size:22px;font-weight:700;color:#111;margin-bottom:16px;'>"
                    f"{n_rutes_cims} rutes a 100 Cims</div>",
                    unsafe_allow_html=True
                )

                for comarca_key in sorted(comarca_cims.keys()):
                    cims_llista = sorted(comarca_cims[comarca_key])
                    st.markdown(
                        f"<div style='font-size:12px;font-weight:700;text-transform:uppercase;"
                        f"letter-spacing:0.5px;color:#aaa;margin:16px 0 6px;'>{comarca_key}</div>",
                        unsafe_allow_html=True
                    )
                    for nom_cim in cims_llista:
                        n_rutes_cim = df[cols["cims_noms"]].astype(str).str.contains(
                            nom_cim, case=False, na=False, regex=False
                        ).sum()
                        paraula = "ruta" if n_rutes_cim == 1 else "rutes"
                        if st.button(f"🏔️ {nom_cim}  ·  {n_rutes_cim} {paraula}", key=f"cim_{nom_cim}"):
                            st.session_state.filtre_cim = nom_cim
                            st.rerun()
            else:
                st.info("No hi ha dades de cims disponibles.")

    with tab_llista:
        # --- FILTRES EN FORMAT BOTÓ PILL ---
        if "filtre_btn_estacio" not in st.session_state:
            st.session_state.filtre_btn_estacio = None
        if "filtre_btn_linia" not in st.session_state:
            st.session_state.filtre_btn_linia = None

        estacions_list = sorted(f[cols["sortida"]].dropna().astype(str).unique().tolist()) if cols.get("sortida") else []
        linies_list = sorted(set(
            l.strip() for val in f[cols["linia_s"]].dropna().astype(str)
            for l in val.split(";") if l.strip() and l.strip().lower() != "nan"
        )) if cols.get("linia_s") else []

        # CSS per als selects amb aparença de botó pill
        st.markdown("""<style>
div[data-testid="stSelectbox"] > div > div {
    background: #f0f0f0 !important;
    border: 1px solid #ddd !important;
    border-radius: 20px !important;
    padding: 2px 12px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #333 !important;
    cursor: pointer !important;
}
div[data-testid="stSelectbox"] label {
    display: none !important;
}
</style>""", unsafe_allow_html=True)

        col_f1, col_f2, col_rest = st.columns([1, 1, 2])
        with col_f1:
            est_options = ["🚉 Estació"] + estacions_list
            sel_est_btn = st.selectbox("Estació", est_options,
                index=0 if not st.session_state.filtre_btn_estacio else
                      est_options.index(st.session_state.filtre_btn_estacio)
                      if st.session_state.filtre_btn_estacio in est_options else 0,
                key="sel_est_btn", label_visibility="collapsed")
            st.session_state.filtre_btn_estacio = sel_est_btn if sel_est_btn != "🚉 Estació" else None

        with col_f2:
            lin_options = ["🚆 Línia"] + linies_list
            sel_lin_btn = st.selectbox("Línia", lin_options,
                index=0 if not st.session_state.filtre_btn_linia else
                      lin_options.index(st.session_state.filtre_btn_linia)
                      if st.session_state.filtre_btn_linia in lin_options else 0,
                key="sel_lin_btn", label_visibility="collapsed")
            st.session_state.filtre_btn_linia = sel_lin_btn if sel_lin_btn != "🚆 Línia" else None

        # Aplicar filtres de botó
        if st.session_state.filtre_btn_estacio:
            f = f[
                (f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_btn_estacio) |
                (f[cols["arribada"]].astype(str).str.strip() == st.session_state.filtre_btn_estacio)
            ]
        if st.session_state.filtre_btn_linia:
            f = f[f[cols["linia_s"]].astype(str).apply(
                lambda x: st.session_state.filtre_btn_linia in [l.strip() for l in x.split(";")]
            )]

        st.write(f"**Resultats: {len(f)} rutes**")

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

            temps_fmt = "—"
            if cols.get("temps") and pd.notna(row[cols["temps"]]):
                try:
                    hores_dec = float(str(row[cols["temps"]]).replace(",", "."))
                    hores = int(hores_dec)
                    mins  = round((hores_dec - hores) * 60)
                    if hores > 0 and mins > 0:
                        temps_fmt = f"{hores}h{mins:02d}min"
                    elif hores > 0:
                        temps_fmt = f"{hores}h"
                    else:
                        temps_fmt = f"{mins}min"
                except:
                    temps_fmt = str(row[cols["temps"]])

            lat_s, lng_s = parse_coord(row[cols["coord_s"]]) if cols.get("coord_s") and pd.notna(row[cols["coord_s"]]) else (None, None)
            lat_a, lng_a = parse_coord(row[cols["coord_a"]]) if cols.get("coord_a") and pd.notna(row[cols["coord_a"]]) else (None, None)
            bloc_s = bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])
            bloc_a = bloc_estacio_html(row[cols["op_a"]], row[cols["linia_a"]])

            if "circular" in tipus:
                desn_txt = f"+/- {int(desn_pujada)} m"
            else:
                desn_txt = f"+{int(desn_pujada)} m / -{int(desn_baixada)} m"

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

            # Estacions HTML per al detall
            is_circular = s_est.lower() == a_est.lower()
            if is_circular:
                label_est = "Estació de sortida / arribada"
                estacions_html = (
                    f"<div style='display:flex;align-items:center;gap:10px;padding:10px 0 6px;'>"
                    f"<div>"
                    f"<div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;'>{label_est}</div>"
                    f"<div style='font-size:14px;font-weight:700;color:#111;display:flex;align-items:center;gap:6px;margin-top:2px;'>"
                    f"<span style='width:9px;height:9px;border-radius:50%;background:#1D9E75;display:inline-block;'></span>"
                    f"<a href='https://www.google.com/maps/search/{s_est}+estacio' target='_blank' style='text-decoration:none;color:#111;'>{s_est}</a>"
                    f"</div>"
                    f"</div>"
                    f"<div style='margin-left:auto;font-size:12px;'>{bloc_s}</div>"
                    f"</div>"
                )
            else:
                estacions_html = (
                    f"<div style='display:flex;align-items:center;gap:10px;padding:10px 0 2px;'>"
                    f"<div style='flex:1;'>"
                    f"<div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;'>Estació de sortida</div>"
                    f"<div style='font-size:14px;font-weight:700;color:#111;display:flex;align-items:center;gap:6px;margin-top:2px;'>"
                    f"<span style='width:9px;height:9px;border-radius:50%;background:#1D9E75;display:inline-block;'></span>"
                    f"<a href='https://www.google.com/maps/search/{s_est}+estacio' target='_blank' style='text-decoration:none;color:#111;'>{s_est}</a>"
                    f"</div></div>"
                    f"<div style='font-size:12px;'>{bloc_s}</div>"
                    f"</div>"
                    f"<div style='display:flex;align-items:center;gap:10px;padding:2px 0 8px;'>"
                    f"<div style='flex:1;'>"
                    f"<div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;'>Estació d'arribada</div>"
                    f"<div style='font-size:14px;font-weight:700;color:#111;display:flex;align-items:center;gap:6px;margin-top:2px;'>"
                    f"<span style='width:9px;height:9px;border-radius:50%;background:#E24B4A;display:inline-block;'></span>"
                    f"<a href='https://www.google.com/maps/search/{a_est}+estacio' target='_blank' style='text-decoration:none;color:#111;'>{a_est}</a>"
                    f"</div></div>"
                    f"<div style='font-size:12px;'>{bloc_a}</div>"
                    f"</div>"
                )

            # Graella de detalls addicionals
            def get_val(key):
                return str(row[cols[key]]).strip() if cols.get(key) and pd.notna(row[cols[key]]) and str(row[cols[key]]).strip() not in ("nan","") else None

            punt_alt_val = get_val("punt_alt")
            alt_max_val  = get_val("altitud_max")
            terreny_val  = get_val("terreny")
            epoca_val    = get_val("epoca")
            tipus_val    = tipus.capitalize() if tipus else None

            def cel_detall(icon, label, val1, val2=None):
                if not val1:
                    return ""
                v2 = f"<div style='font-size:12px;color:#666;margin-top:1px;'>{val2}</div>" if val2 else ""
                return (
                    f"<div style='display:flex;gap:8px;align-items:flex-start;padding:8px 0;'>"
                    f"<span style='font-size:16px;color:#aaa;flex-shrink:0;width:20px;margin-top:2px;'>{icon}</span>"
                    f"<div><div style='font-size:9px;text-transform:uppercase;letter-spacing:0.5px;color:#bbb;font-weight:600;'>{label}</div>"
                    f"<div style='font-size:13px;font-weight:600;color:#222;margin-top:1px;'>{val1}</div>{v2}</div>"
                    f"</div>"
                )

            c1 = cel_detall("⛰️", "Punt més alt", punt_alt_val, f"{alt_max_val} m" if alt_max_val else None)
            c2 = cel_detall("📅", "Època recomanada", epoca_val)
            c3 = cel_detall("🔄", "Tipus de ruta", tipus_val)
            c4 = cel_detall("🧗", "Dificultat", dif_raw)
            graella = (
                f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0 16px;"
                f"border-top:1px solid #eee;margin-top:8px;'>"
                f"{c1}{c2}{c3}{c4}</div>"
            )

            # Generar perfil SVG per a la pestanya
            svg_perfil_html = ""
            alt_info_html = ""
            if ruta_id:
                svg_p, alt_min_p, alt_max_p = perfil_elevacio_svg(ruta_id, dif_color)
                if svg_p:
                    svg_perfil_html = svg_p
                    alt_info_html = f"<div style='font-size:10px;color:#888;text-align:center;margin-top:4px;'>Altitud mín: <b>{int(alt_min_p)} m</b> · Altitud màx: <b>{int(alt_max_p)} m</b></div>"

            # Barra de dificultat HTML
            nivells_dif = [("Molt fàcil","#2196A6"),("Fàcil","#1D9E75"),("Moderada","#EF9F27"),("Difícil","#E24B4A"),("Molt difícil","#9B1B1B")]
            claus_norm_dif = ["molt facil","facil","moderada","dificil","molt dificil"]
            def normalitza_d(s):
                return s.lower().replace("í","i").replace("à","a").replace("è","e").replace("ó","o").replace("ú","u").strip()
            pos_dif = next((i for i,c in enumerate(claus_norm_dif) if c==normalitza_d(dif_raw)),-1)
            segs_dif = ""
            for i,(nom_niv,color_niv) in enumerate(nivells_dif):
                actiu=(i==pos_dif); opacity="1" if actiu else "0.22"
                radius="6px 0 0 6px" if i==0 else ("0 6px 6px 0" if i==4 else "0")
                dot=f'<div style="width:11px;height:11px;border-radius:50%;background:{color_niv};border:2px solid #111;position:absolute;top:-6px;left:50%;transform:translateX(-50%);box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>' if actiu else ""
                segs_dif+=f'<div style="flex:1;position:relative;">{dot}<div style="height:8px;background:{color_niv};opacity:{opacity};border-radius:{radius};"></div><div style="font-size:8px;color:#555;text-align:center;margin-top:3px;font-weight:{"700" if actiu else "400"};">{nom_niv}</div></div>'
            barra_dif = f'<div style="margin:10px 0 4px;"><div style="font-size:10px;color:#aaa;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.4px;">Dificultat</div><div style="display:flex;gap:2px;">{segs_dif}</div></div>'

            # Punts d'interès HTML
            elements_str = row[cols["elements"]] if cols["elements"] and pd.notna(row[cols["elements"]]) else ""
            cats_str     = row[cols["cats"]]     if cols["cats"]     and pd.notna(row[cols["cats"]])     else ""
            punts_html_content = punts_interes_html(elements_str, cats_str) if elements_str else "<div style='color:#888;font-size:13px;padding:8px 0;'>No hi ha punts d'interès registrats.</div>"

            # Comentaris columna AH
            comentaris_val = str(row[cols["comentaris"]]).strip() if cols.get("comentaris") and pd.notna(row[cols["comentaris"]]) and str(row[cols["comentaris"]]).strip() not in ("nan","") else ""

            # Horaris
            horaris_sortida  = horaris_html_bloc(s_est, row[cols["linia_s"]] if cols.get("linia_s") else "", row[cols["op_s"]] if cols.get("op_s") else "", dif_color, "sortida")
            horaris_arribada = horaris_html_bloc(a_est, row[cols["linia_a"]] if cols.get("linia_a") else "", row[cols["op_a"]] if cols.get("op_a") else "", dif_color, "arribada") if s_est.lower() != a_est.lower() else ""

            # Perfil bloc
            perfil_bloc = ""
            if svg_perfil_html:
                perfil_bloc = (
                    f"<div style='margin-top:12px;border-top:1px solid #eee;padding-top:10px;'>"
                    f"<div style='font-size:16px;font-weight:700;color:#222;margin-bottom:8px;'>Perfil de la ruta</div>"
                    + svg_perfil_html + alt_info_html + barra_dif +
                    f"</div>"
                )

            detalls_html = (
                # Comentaris
                (f"<div style='margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #eee;'>"
                 f"<div style='font-size:16px;font-weight:700;color:#222;margin-bottom:4px;'>Comentaris</div>"
                 f"<div style='font-size:16px;color:#444;line-height:1.5;'>{comentaris_val}</div>"
                 f"</div>" if comentaris_val else "") +

                # Dades
                f"<div style='font-size:16px;font-weight:700;color:#222;margin-bottom:8px;'>Dades</div>"
                + estacions_html
                + graella +

                # Punts d'interès
                (f"<div style='margin-top:12px;border-top:1px solid #eee;padding-top:10px;'>"
                 f"<div style='font-size:16px;font-weight:700;color:#222;margin-bottom:8px;'>Punts d'interès</div>"
                 f"{punts_html_content}</div>" if punts_html_content else "") +

                # Perfil
                perfil_bloc +

                # Horaris
                f"<div style='margin-top:12px;border-top:1px solid #eee;padding-top:10px;'>"
                f"<div style='font-size:16px;font-weight:700;color:#222;margin-bottom:8px;'>🕐 Horaris de tren</div>"
                + horaris_sortida + horaris_arribada +
                f"</div>"
            )

            etiquetes_html = f"<div style='padding:2px 12px 8px;'>{etiquetes}</div>" if etiquetes else ""

            # TARGETA UNIFICADA
            card_html = (
                f"<div style='margin-top:12px;border:1px solid {dif_color}44;border-left:5px solid {dif_color};"
                f"border-radius:8px;overflow:visible;background:white;'>"
                f"<div style='background:{dif_color}18;padding:10px 12px;display:flex;align-items:center;gap:10px;'>"
                f"<div style='width:26px;height:26px;border-radius:50%;background:{dif_color};color:white;"
                f"font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;'>{ruta_id}</div>"
                f"<div style='flex:1;font-size:14px;font-weight:700;color:#111;'>{nom_ruta}</div>"
                f"<span style='font-size:10px;font-weight:700;background:{dif_color};color:white;"
                f"padding:2px 9px;border-radius:20px;flex-shrink:0;text-transform:uppercase;letter-spacing:0.5px;'>{dif_raw}</span>"
                f"</div>"
                f"<div style='padding:6px 12px 4px;display:flex;gap:20px;flex-wrap:wrap;'>"
                f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Distància</div>"
                f"<div style='font-size:14px;font-weight:700;color:#111;'>{row[cols['km']]} km</div></div>"
                f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Desnivell</div>"
                f"<div style='font-size:14px;font-weight:700;color:#111;'>{desn_txt}</div></div>"
                f"<div><div style='font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Temps</div>"
                f"<div style='font-size:14px;font-weight:700;color:#111;'>{temps_fmt}</div></div>"
                f"</div>"
                + etiquetes_html +
                f"<details id='det_{ruta_id}' style='border-top:1px solid #eee;'>"
                f"<summary style='list-style:none;padding:0;cursor:pointer;display:block;' "
                f"onclick=\"this.parentElement.open ? "
                f"this.querySelector('.det-btn').textContent='Veure detalls' : "
                f"this.querySelector('.det-btn').textContent='Amagar detalls'\">"
                f"<div class='det-btn' style='margin:10px auto 12px;background:{dif_color};color:white;border-radius:8px;"
                f"padding:10px 24px;text-align:center;font-size:14px;font-weight:700;letter-spacing:0.3px;"
                f"box-shadow:0 2px 6px {dif_color}55;width:fit-content;min-width:160px;'>"
                f"Veure detalls</div></summary>"
                f"<div style='padding:8px 12px 12px;'>"
                + detalls_html +
                f"</div></details></div>"
            )
            st.markdown(card_html, unsafe_allow_html=True)

            # Mapa interactiu — arrow coherent amb Veure detalls via CSS global
            with st.expander("🗺️ Mapa del recorregut", key=f"mapa_{ruta_id}"):
                with st.spinner("Carregant mapa..."):
                    if ruta_id:
                        if not mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a):
                            st.info("Mapa no disponible per aquesta ruta.")

except Exception as e:
    st.error(f"S'ha produït un error: {e}")
