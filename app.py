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

# CSS: pestanyes natives estilitzades com a píndoles flotants sobre la imatge
st.markdown("""
<style>
/* Elimina el marge entre la capçalera i les pestanyes */
div[data-testid="stTabs"] { margin-top: -2px !important; }

/* Barra de pestanyes: fons transparent, centrada */
div[data-baseweb="tab-list"] {
    background: transparent !important;
    justify-content: center !important;
    gap: 8px !important;
    padding: 10px 0 6px 0 !important;
    border-bottom: none !important;
}

/* Cada pestanya: estil píndola */
button[data-baseweb="tab"] {
    background: rgba(255,255,255,0.18) !important;
    border: 1.5px solid rgba(255,255,255,0.5) !important;
    border-radius: 30px !important;
    color: #333 !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 8px 22px !important;
    backdrop-filter: blur(4px) !important;
}

/* Pestanya activa: fons blanc sòlid */
button[data-baseweb="tab"][aria-selected="true"] {
    background: white !important;
    color: #222 !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
    border: none !important;
}

/* Treu la línia taronja de sota */
div[data-baseweb="tab-highlight"] { display: none !important; }
div[data-baseweb="tab-border"]    { display: none !important; }
</style>
""", unsafe_allow_html=True)

st.markdown(f'''
    <div style="position:relative;width:100%;height:260px;border-radius:12px 12px 0 0;overflow:hidden;margin-bottom:0;">
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

@st.cache_data(ttl=30)
def obtenir_horaris_rodalies(id_estacio, num=8):
    """API Rodalies/Renfe en temps real (nucli 60 = Catalunya)"""
    try:
        url = (
            f"https://horarios.renfe.com/cer/HorariosServlet"
            f"?nucleo=60&origen={id_estacio}&destino=&fchaViaje="
            f"&validaReglaNegocio=true&tiempoReal=true&servicioHorarios=VTI"
            f"&horaViajeOrigen=00&horaViajeLlegada=26&accesibilidadTrenes=false"
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://horarios.renfe.com/",
            "Origin": "https://horarios.renfe.com",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                horari = data.get("horario", [])
                if horari:
                    return horari[:num]
            except Exception as e:
                st.session_state["debug_rodalies"] = f"JSON error: {e} | body: {resp.text[:200]}"
        else:
            st.session_state["debug_rodalies"] = f"HTTP {resp.status_code} per estació {id_estacio}"
    except Exception as e:
        st.session_state["debug_rodalies"] = f"Excepció: {e}"
    return None

@st.cache_data(ttl=30)
def obtenir_horaris_fgc(id_estacio, num=8):
    """API FGC en temps real"""
    try:
        url = f"https://www.fgc.cat/api/v1/departure-board/{id_estacio}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.fgc.cat/",
            "Origin": "https://www.fgc.cat",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, list):
                    return data[:num]
                return data.get("departures", data.get("data", []))[:num]
            except Exception as e:
                st.session_state["debug_fgc"] = f"JSON error: {e} | body: {resp.text[:200]}"
        else:
            st.session_state["debug_fgc"] = f"HTTP {resp.status_code} per estació {id_estacio}"
    except Exception as e:
        st.session_state["debug_fgc"] = f"Excepció: {e}"
    return None

def _taula_horaris_html(files_data, dif_color, url_horaris, nom_op):
    """Genera HTML de taula d'horaris normalitzada"""
    if not files_data:
        return (
            f"<div style='background:#f8f9fa;border-radius:6px;padding:8px 10px;margin-top:6px;'>"
            f"<a href='{url_horaris}' target='_blank' style='font-size:12px;color:{dif_color};"
            f"font-weight:600;text-decoration:none;'>Veure horaris {nom_op} →</a></div>"
        )
    files_html = ""
    for t in files_data:
        retard = t.get("retard", 0) or 0
        try: retard = int(retard)
        except: retard = 0
        if retard > 0:
            estat = f"<span style='color:#E24B4A;font-weight:700;font-size:10px;'>+{retard} min</span>"
        else:
            estat = "<span style='color:#1D9E75;font-size:10px;'>✓ En temps</span>"
        files_html += (
            f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:4px;"
            f"padding:5px 0;border-bottom:1px solid #eee;align-items:center;'>"
            f"<span style='font-size:12px;color:#222;'>{t.get('desti','—')}</span>"
            f"<span style='font-size:11px;color:#555;'>{t.get('linia','')}</span>"
            f"<span style='font-size:12px;font-weight:600;color:#111;'>{t.get('hora','—')}</span>"
            f"{estat}</div>"
        )
    header = (
        f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:4px;"
        f"padding:4px 0;margin-bottom:2px;'>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Destinació</span>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Línia</span>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Hora</span>"
        f"<span style='font-size:10px;font-weight:700;color:#aaa;text-transform:uppercase;'>Estat</span>"
        f"</div>"
    )
    return f"<div style='background:#f8f9fa;border-radius:6px;padding:8px 10px;margin-top:6px;'>{header}{files_html}</div>"

def horaris_html_bloc(estacio, linia_str, op_str, dif_color, id_estacio_str, tipus_estacio="sortida"):
    """Genera HTML d'horaris per a una estació amb temps real si disponible"""
    op_lower = str(op_str).lower() if op_str else ""
    linies   = [l.strip() for l in str(linia_str).split(";") if l.strip() and l.strip().lower() != "nan"]
    id_est   = str(id_estacio_str).strip() if id_estacio_str and str(id_estacio_str).strip() not in ("nan","") else ""

    # URL i nom de l'operador
    if "fgc" in op_lower:
        url_horaris = f"https://www.fgc.cat/viatjar/horaris/?origen={estacio.replace(' ', '+')}"
        nom_op = "FGC"
    elif "metro" in op_lower or "tmb" in op_lower:
        url_horaris = "https://www.tmb.cat/ca/barcelona/horaris-metro"
        nom_op = "Metro TMB"
    elif "tram" in op_lower:
        url_horaris = "https://www.tram.cat/ca/linies-i-horaris"
        nom_op = "Tram"
    elif "sncf" in op_lower:
        url_horaris = "https://www.sncf-connect.com"
        nom_op = "SNCF"
    elif "cremallera" in op_lower:
        url_horaris = "https://www.valldenuria.cat/ca/cremallera"
        nom_op = "Cremallera de Núria"
    elif "alta velocitat" in op_lower:
        url_horaris = "https://www.renfe.com/es/ca/viajar/informacion-util/horarios"
        nom_op = "Alta Velocitat"
    else:
        url_horaris = f"https://rodalies.gencat.cat/ca/inici/horaris/?origen={estacio.replace(' ', '+')}"
        nom_op = "Rodalies"

    linies_html = "".join(
        f"<img src='https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{l}.svg' "
        f"style='height:16px;margin-right:3px;vertical-align:middle;' onerror=\"this.style.display='none'\">"
        for l in linies
    )

    titol = "Sortida" if tipus_estacio == "sortida" else "Arribada (tornada)"
    icon  = "🟢" if tipus_estacio == "sortida" else "🔴"

    # --- Obtenir horaris en temps real segons operador ---
    files_data = None

    if id_est:
        if "fgc" in op_lower:
            raw = obtenir_horaris_fgc(id_est)
            if raw:
                files_data = []
                for t in raw:
                    files_data.append({
                        "desti": t.get("destination", t.get("destinació", t.get("headsign", "—"))),
                        "linia": t.get("line", t.get("linia", t.get("route", ""))),
                        "hora":  t.get("scheduledTime", t.get("time", t.get("hora", "—"))),
                        "retard": t.get("delay", t.get("retard", 0)),
                    })
        elif any(k in op_lower for k in ("rodalies", "renfe", "tren dels llacs", "adif")) or op_lower == "":
            raw = obtenir_horaris_rodalies(id_est)
            if raw:
                files_data = []
                for t in raw:
                    retard = t.get("retraso", 0)
                    try: retard = int(retard)
                    except: retard = 0
                    files_data.append({
                        "desti": t.get("destino", t.get("destinoNombre", "—")),
                        "linia": t.get("cdgoTren", t.get("linia", "")),
                        "hora":  t.get("horaSalidaReal", t.get("horaSalida", "—")),
                        "retard": retard,
                    })

    taula_html = _taula_horaris_html(files_data, dif_color, url_horaris, nom_op)

    return (
        f"<div style='margin-bottom:14px;'>"
        f"<div style='font-size:13px;font-weight:700;color:#333;margin-bottom:4px;'>{icon} {titol}: {estacio}</div>"
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:4px;'>{linies_html}</div>"
        f"{taula_html}"
        f"</div>"
    )


RECORREGUTS_LINIA = {
    # Rodalies
    "R1":      "Molins de Rei - Maçanet-Massanes",
    "R2":      "Castelldefels - Granollers Centre",
    "R2 Nord": "Aeroport - Maçanet-Massanes",
    "R2 Sud":  "Estació de França - Sant Vicenç de Calders",
    "R3":      "L'Hospitalet de Llobregat - Puigcerdà",
    "R4":      "Manresa - Sant Vicenç de Calders",
    "R7":      "Barcelona Fabra i Puig - Martorell",
    "R8":      "Martorell Central - Granollers Centre",
    "R11":     "Barcelona Sants - Portbou",
    "R13":     "Barcelona França - Lleida (per Valls)",
    "R14":     "Barcelona França - Lleida (per Tarragona i Reus)",
    "R15":     "Barcelona França - Reus - Riba-roja d'Ebre",
    "R16":     "Barcelona França - Tarragona - Tortosa / Ulldecona",
    "R17":     "Barcelona França - Salou-Port Aventura",
    "RG1":     "L'Hospitalet de Llobregat - Figueres / Portbou",
    "RG2":     "Girona - Figueres",
    "RL1":     "Lleida Pirineus - Balaguer",
    "RL3":     "Lleida Pirineus - Cervera",
    "RL4":     "Lleida Pirineus - Terrassa estació del Nord",
    "RT1":     "Tarragona - La Plana Picamoixons",
    "RT2":     "L'Arboç - Salou Port Aventura",
    # FGC Metropolità
    "L6":      "Plaça Catalunya - Sarrià",
    "L7":      "Plaça Catalunya - Av. Tibidabo",
    "L8":      "Plaça Espanya - Molí Nou-Ciutat Cooperativa",
    "S1":      "Plaça Espanya - Terrassa",
    "S2":      "Plaça Espanya - Sabadell",
    "S3":      "Plaça Espanya - Can Ros",
    "S4":      "Plaça Espanya - Olesa de Montserrat",
    "S8":      "Plaça Espanya - Martorell Enllaç",
    "S9":      "Plaça Espanya - Quatre Camins",
    "R5":      "Plaça Espanya - Manresa",
    "R50":     "Plaça Espanya - Manresa (via Montserrat)",
    "R6":      "Plaça Espanya - Igualada",
    "R60":     "Plaça Espanya - Igualada (directe)",
    # FGC Girona / Lleida
    "L1":      "Plaça Catalunya - Vallvidrera Superior",
    "RL2":     "Lleida - La Pobla de Segur",
    # Cremallera i funicular
    "CR":      "Ribes de Freser - Núria",
    "FM":      "Montserrat Aeri - Monistrol de Montserrat",
    # Metro TMB
    "L1":      "Hospital Bellvitge - Fondo",
    "L2":      "Badalona Pompeu Fabra - Pep Ventura",
    "L3":      "Zona Universitària - Trinitat Nova",
    "L4":      "La Pau - Trinitat Nova",
    "L5":      "Cornellà Centre - Horta",
    "L9N":     "La Sagrera - Can Zam / Gorg",
    "L9S":     "Aeroport T1 - Zona Universitària",
    "L10N":    "La Sagrera - Gorg",
    "L10S":    "Zona Universitària - Foc",
    "L11":     "Trinitat Nova - Can Cuiàs",
    # Tram
    "T1":      "Francesc Macià - Sant Feliu",
    "T2":      "Francesc Macià - Quatre Camins",
    "T3":      "Francesc Macià - Baix Llobregat",
    "T4":      "Ciutadella - La Pau",
    "T5":      "Glòries - Badalona Pompeu Fabra",
    "T6":      "Glòries - Besòs",
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
    "molt fàcil":   "#2ECC71", "molt facil":   "#2ECC71",
    "fàcil":        "#3498DB", "facil":        "#3498DB",
    "moderada":     "#E67E22",
    "exigent":      "#E74C3C",
    "molt exigent": "#2C3E50",
}

BASE_LOGO_LINIA = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/Logo-{linia}.svg"
BASE_GPX_URL    = "https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/gpx/ruta-{id:03d}.gpx"
BASE_FOTO_URL   = "https://raw.githubusercontent.com/Senderismeentren/imatges/main/ruta-{id:03d}/foto{n}.jpg"
MAX_FOTOS_RUTA  = 9
LOGO_SIZE        = 18
SHEET_ID         = "12SrgpFkVTowVdfjSMTprs-XBYR5zUKTr-uU3tyYeVEE"
SHEET_NAME       = "Rutes"
COLOR_BLAU       = "#007bff"
COLOR_VERD       = "#2d9e6b"

@st.cache_data(ttl=600)
def carregar_dades():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    full   = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return pd.DataFrame(full.get_all_records())

def parse_coord(coord_str):
    """Mante compatibilitat amb format antic lat,lon en una sola columna."""
    try:
        parts = str(coord_str).split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except:
        pass
    return None, None

def get_coord(row, col_lat, col_lon):
    """Llegeix lat i lon de dues columnes separades (nou format)."""
    try:
        lat = float(str(row[col_lat]).replace(",", ".")) if col_lat and pd.notna(row[col_lat]) and str(row[col_lat]).strip() not in ("", "nan") else None
        lon = float(str(row[col_lon]).replace(",", ".")) if col_lon and pd.notna(row[col_lon]) and str(row[col_lon]).strip() not in ("", "nan") else None
        return lat, lon
    except:
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
        # Cerca exacta primer, després cerca parcial per si la categoria conté la clau
        icona = CATEGORIES_ICONES.get(categoria)
        if not icona:
            for clau, ico in CATEGORIES_ICONES.items():
                if clau in categoria or categoria in clau:
                    icona = ico
                    break
        if not icona:
            icona = "📍"
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

def mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a, context="llista"):
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
        lats_r = [p[0] for p in punts]
        lngs_r = [p[1] for p in punts]
        centre = (sum(lats_r) / len(lats_r), sum(lngs_r) / len(lngs_r))

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
        st_folium(m, use_container_width=True, height=300, returned_objects=[], key=f"mapa_ruta_{context}_{ruta_id}")
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


@st.cache_data(ttl=300)
def obtenir_fotos_ruta(ruta_id):
    """Comprova fotos .jpg i .png. Para quan troba 2 numeros consecutius buits."""
    urls = []
    buides = 0
    for n in range(1, MAX_FOTOS_RUTA + 1):
        trobada = False
        for ext in ("jpg", "png"):
            url = BASE_FOTO_URL.format(id=int(ruta_id), n=n).replace(".jpg", f".{ext}")
            try:
                resp = requests.head(url, timeout=5)
                if resp.status_code == 200:
                    urls.append(url)
                    trobada = True
                    break
            except Exception:
                pass
        if trobada:
            buides = 0
        else:
            buides += 1
            if buides >= 2:
                break
    return urls

def fotos_contingut_html(ruta_id):
    """Retorna el contingut intern de les fotos (sense embolcall de seccio), o cadena buida."""
    if not ruta_id:
        return ""
    urls = obtenir_fotos_ruta(ruta_id)
    if not urls:
        return ""
    fotos_html = ""
    for url in urls:
        fotos_html += (
            f"<a href='{url}' target='_blank' style='display:block;aspect-ratio:1;overflow:hidden;"
            f"border-radius:6px;border:0.5px solid #e0e0e0;'>"
            f"<img src='{url}' style='width:100%;height:100%;object-fit:cover;display:block;' "
            f"loading='lazy' onerror=\"this.parentElement.style.display='none'\">"
            f"</a>"
        )
    return (
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px;'>"
        f"{fotos_html}"
        f"</div>"
        f"<p style='font-size:11px;color:#aaa;margin:6px 0 0;text-align:right;'>Clica per veure a mida completa</p>"
    )


def barra_mini_dif(dif_raw, dif_color):
    """Barra de 5 segments mini que substitueix el badge de text a la capçalera de targeta."""
    nivells = [
        ("Molt fàcil", "#2ECC71"),
        ("Fàcil",      "#3498DB"),
        ("Moderada",   "#E67E22"),
        ("Difícil",    "#E74C3C"),
        ("Molt difícil","#2C3E50"),
    ]
    claus = ["molt facil","facil","moderada","dificil","molt dificil"]

    def norm(s):
        return (s.lower()
                 .replace("à","a").replace("á","a")
                 .replace("è","e").replace("é","e")
                 .replace("í","i").replace("ï","i")
                 .replace("ò","o").replace("ó","o")
                 .replace("ú","u").replace("ü","u")
                 .replace("ç","c"))

    pos = next((i for i, c in enumerate(claus) if c == norm(dif_raw)), -1)
    segs = ""
    for i, (nom, color) in enumerate(nivells):
        actiu = (i == pos)
        opacity = "1" if actiu else "0.2"
        radius = "4px 0 0 4px" if i == 0 else ("0 4px 4px 0" if i == 4 else "0")
        label_w = "font-weight:700;" if actiu else ""
        segs += (
            f"<div style='flex:1;'>"
            f"<div style='height:6px;background:{color};opacity:{opacity};"
            f"border-radius:{radius};'></div>"
            f"<div style='font-size:11px;color:#555;text-align:center;"
            f"margin-top:2px;{label_w}'>{nom if actiu else ''}</div>"
            f"</div>"
        )
    return (
        f"<div style='display:flex;gap:2px;margin-top:6px;align-items:flex-end;'>"
        f"{segs}"
        f"</div>"
    )


def color_folium_per_operador(op_str):
    """Retorna el color hex segons l'operador principal de l'estació."""
    if not op_str or str(op_str).strip().lower() in ("nan", ""):
        return "#EE7F00"  # Rodalies taronja Pantone 152
    op = str(op_str).strip().lower().split(";")[0].strip()
    if "rodalies" in op:
        return "#EE7F00"  # Taronja Pantone 152 / RAL 2000
    if "fgc" in op:
        return "#97D700"  # Verd Pantone 375C / RAL S 0580-G30Y
    if "metro" in op or "tmb" in op:
        return "#E30613"
    if "tram" in op:
        return "#78BE20"
    if "adif" in op:
        return "#8B008B"
    if "renfe" in op:
        return "#003DA5"
    if "tren dels llacs" in op:
        return "#5F9EA0"
    if "alta velocitat" in op:
        return "#8B0000"
    if "sncf" in op:
        return "#C00000"
    if "cremallera" in op:
        return "#C8A96E"
    return "#EE7F00"

def mostrar_mapa_general(df_filtrat, cols):
    punts_mapa = {}

    def afegir_estacio(lat, lng, estacio, rid, nom, op_str):
        if not lat or not lng:
            return
        key = (lat, lng, estacio)
        if key not in punts_mapa:
            punts_mapa[key] = {"rutes": [], "op": op_str}
        punts_mapa[key]["rutes"].append(f"Ruta {rid}: {nom}")

    for _, row in df_filtrat.iterrows():
        nom = str(row[cols["ruta"]])
        rid = int(row[cols["id"]]) if pd.notna(row[cols["id"]]) else ""
        op_s = str(row[cols["op_s"]]).strip() if cols.get("op_s") and pd.notna(row[cols["op_s"]]) else ""
        op_a = str(row[cols["op_a"]]).strip() if cols.get("op_a") and pd.notna(row[cols["op_a"]]) else ""

        lat_s, lng_s = get_coord(row, cols.get("coord_s"), cols.get("lon_s"))
        s_est = str(row[cols["sortida"]]).strip()
        afegir_estacio(lat_s, lng_s, s_est, rid, nom, op_s)

        lat_a, lng_a = get_coord(row, cols.get("coord_a"), cols.get("lon_a"))
        a_est = str(row[cols["arribada"]]).strip()
        if a_est.lower() != s_est.lower():
            afegir_estacio(lat_a, lng_a, a_est, rid, nom, op_a)

    if not punts_mapa:
        st.info("No hi ha coordenades disponibles per mostrar al mapa.")
        return

    # Mapa de nom d'estació -> key, per fer la cerca al clic
    estacio_a_key = {}
    for key in punts_mapa:
        _, _, nom_est = key
        estacio_a_key[nom_est] = key

    m = folium.Map(location=[41.7, 1.8], zoom_start=8, tiles="OpenStreetMap")

    for (lat, lng, estacio), info in punts_mapa.items():
        color_marker = color_folium_per_operador(info["op"])
        n_rutes = len(info["rutes"])
        paraula = "ruta" if n_rutes == 1 else "rutes"
        # Tooltip: NOMÉS el nom de l'estació, sense prefix, per recuperar-lo fiablement
        tooltip_text = f"{estacio}||{n_rutes} {paraula}"
        icon_html = (
            f"<div style='background:{color_marker};width:28px;height:28px;border-radius:50%;"
            f"border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.4);"
            f"display:flex;align-items:center;justify-content:center;font-size:13px;'>🚉</div>"
        )
        folium.Marker(
            location=[lat, lng],
            tooltip=estacio,
            popup=folium.Popup(f"<b>{estacio}</b><br>{n_rutes} {paraula}", max_width=200),
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
        ).add_to(m)

    map_key = f"mapa_general_{st.session_state.get('map_reset_counter', 0)}"
    resultat = st_folium(m, width=None, height=350, returned_objects=["last_object_clicked_tooltip"], key=map_key)

    if resultat and resultat.get("last_object_clicked_tooltip"):
        tooltip = resultat["last_object_clicked_tooltip"]
        # El tooltip és directament el nom de l'estació
        estacio_clicada = str(tooltip).strip()
        if estacio_clicada != st.session_state.filtre_estacio:
            st.session_state.filtre_estacio = estacio_clicada
            st.session_state.pestanya_activa = "mapa"
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
        f"<div style='background:{dif_color}18;padding:10px 12px 8px;'>"
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<div style='width:26px;height:26px;border-radius:50%;background:{dif_color};color:white;"
        f"font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;'>{ruta_id}</div>"
        f"<div style='flex:1;font-size:15px;font-weight:700;color:#111;line-height:1.3;'>{nom_ruta}{'  <span style=\"font-size:17px;\">📷</span>' if te_fotos else ''}</div>"
        f"</div>"
        f"{barra_mini_dif(dif_raw, dif_color)}"
        f"</div>"
        f"<div style='padding:6px 12px 4px;display:flex;gap:20px;flex-wrap:wrap;'>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Distància</div>"
        f"<div style='font-size:14px;font-weight:700;color:#111;'>{km_val} km</div></div>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Desnivell</div>"
        f"<div style='font-size:15px;font-weight:700;color:#111;'>{desn_txt}</div></div>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Temps</div>"
        f"<div style='font-size:15px;font-weight:700;color:#111;'>{temps_fmt}</div></div>"
        f"</div>"
        + etiquetes_html +
        f"</div>",
        unsafe_allow_html=True
    )



def render_ruta_completa(row, cols, context="llista", te_fotos=False):
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

    lat_s, lng_s = get_coord(row, cols.get("coord_s"), cols.get("lon_s"))
    lat_a, lng_a = get_coord(row, cols.get("coord_a"), cols.get("lon_a"))
    bloc_s = bloc_estacio_html(row[cols["op_s"]], row[cols["linia_s"]])
    bloc_a = bloc_estacio_html(row[cols["op_a"]], row[cols["linia_a"]])

    if "circular" in tipus:
        desn_txt = f"+/- {int(desn_pujada)} m"
    else:
        desn_txt = f"+{int(desn_pujada)} m / -{int(desn_baixada)} m"

    comarca_val = str(row[cols["comarca"]]) if pd.notna(row[cols["comarca"]]) else ""
    espai_val   = str(row[cols["espai"]]) if cols.get("espai") and pd.notna(row[cols["espai"]]) else ""
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
            f"<div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;'>Estació de sortida</div>"
            f"<div style='font-size:14px;font-weight:700;color:#111;display:flex;align-items:center;gap:6px;margin-top:2px;'>"
            f"<span style='width:9px;height:9px;border-radius:50%;background:#1D9E75;display:inline-block;'></span>"
            f"<a href='https://www.google.com/maps/search/{s_est}+estacio' target='_blank' style='text-decoration:none;color:#111;'>{s_est}</a>"
            f"</div></div>"
            f"<div style='font-size:12px;'>{bloc_s}</div>"
            f"</div>"
            f"<div style='display:flex;align-items:center;gap:10px;padding:2px 0 8px;'>"
            f"<div style='flex:1;'>"
            f"<div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;'>Estació d'arribada</div>"
            f"<div style='font-size:14px;font-weight:700;color:#111;display:flex;align-items:center;gap:6px;margin-top:2px;'>"
            f"<span style='width:9px;height:9px;border-radius:50%;background:#E24B4A;display:inline-block;'></span>"
            f"<a href='https://www.google.com/maps/search/{a_est}+estacio' target='_blank' style='text-decoration:none;color:#111;'>{a_est}</a>"
            f"</div></div>"
            f"<div style='font-size:12px;'>{bloc_a}</div>"
            f"</div>"
        )

    def get_val(key):
        return str(row[cols[key]]).strip() if cols.get(key) and pd.notna(row[cols[key]]) and str(row[cols[key]]).strip() not in ("nan","") else None

    punt_alt_val = get_val("punt_alt")
    alt_max_val  = get_val("altitud_max")
    terreny_val  = get_val("terreny")
    epoca_val    = get_val("epoca")
    tipus_val    = tipus.capitalize() if tipus else None
    advertiments_val = get_val("advertiments")

    def cel_detall(icon, label, val1, val2=None):
        if not val1:
            return ""
        v2 = f"<div style='font-size:11px;color:#666;margin-top:1px;'>{val2}</div>" if val2 else ""
        return (
            f"<div style='display:flex;gap:8px;align-items:flex-start;padding:8px 0;'>"
            f"<span style='font-size:16px;color:#aaa;flex-shrink:0;width:20px;margin-top:2px;'>{icon}</span>"
            f"<div><div style='font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#bbb;font-weight:600;'>{label}</div>"
            f"<div style='font-size:13px;font-weight:600;color:#222;margin-top:1px;'>{val1}</div>{v2}</div>"
            f"</div>"
        )

    c1 = cel_detall("⛰️", "Punt més alt", punt_alt_val, f"{alt_max_val} m" if alt_max_val else None)
    c2 = cel_detall("📅", "Època recomanada", epoca_val)
    c3 = cel_detall("🔄", "Tipus de ruta", tipus_val)
    c4 = cel_detall("🧗", "Dificultat", dif_raw)

    seguretat_html = ""
    if advertiments_val:
        seguretat_html = (
            f"<div style='display:flex;gap:8px;align-items:flex-start;padding:8px 0;"
            f"border-top:1px solid #eee;margin-top:4px;'>"
            f"<span style='font-size:16px;color:#aaa;flex-shrink:0;width:20px;margin-top:2px;'>⚠️</span>"
            f"<div><div style='font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#bbb;font-weight:600;'>Seguretat</div>"
            f"<div style='font-size:13px;font-weight:600;color:#222;margin-top:1px;'>{advertiments_val}</div></div>"
            f"</div>"
        )

    graella = (
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0 16px;"
        f"border-top:1px solid #eee;margin-top:8px;'>"
        f"{c1}{c2}{c3}{c4}</div>"
        + (
            f"<div>{seguretat_html}</div>"
            if seguretat_html else ""
        )
    )

    svg_perfil_html = ""
    alt_info_html = ""
    if ruta_id:
        svg_p, alt_min_p, alt_max_p = perfil_elevacio_svg(ruta_id, dif_color)
        if svg_p:
            svg_perfil_html = svg_p
            alt_info_html = f"<div style='font-size:11px;color:#888;text-align:center;margin-top:4px;'>Altitud mín: <b>{int(alt_min_p)} m</b> · Altitud màx: <b>{int(alt_max_p)} m</b></div>"

    nivells_dif = [("Molt fàcil","#2ECC71"),("Fàcil","#3498DB"),("Moderada","#E67E22"),("Difícil","#E74C3C"),("Molt difícil","#2C3E50")]
    claus_norm_dif = ["molt facil","facil","moderada","dificil","molt dificil"]
    def normalitza_d(s):
        return s.lower().replace("í","i").replace("à","a").replace("è","e").replace("ó","o").replace("ú","u").strip()
    pos_dif = next((i for i,c in enumerate(claus_norm_dif) if c==normalitza_d(dif_raw)),-1)
    segs_dif = ""
    for i,(nom_niv,color_niv) in enumerate(nivells_dif):
        actiu=(i==pos_dif); opacity="1" if actiu else "0.22"
        radius="6px 0 0 6px" if i==0 else ("0 6px 6px 0" if i==4 else "0")
        dot=f'<div style="width:11px;height:11px;border-radius:50%;background:{color_niv};border:2px solid #111;position:absolute;top:-6px;left:50%;transform:translateX(-50%);box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>' if actiu else ""
        segs_dif+=f'<div style="flex:1;position:relative;">{dot}<div style="height:8px;background:{color_niv};opacity:{opacity};border-radius:{radius};"></div><div style="font-size:11px;color:#555;text-align:center;margin-top:3px;font-weight:{"700" if actiu else "400"};">{nom_niv}</div></div>'
    barra_dif = f'<div style="margin:10px 0 4px;"><div style="font-size:11px;color:#aaa;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.4px;">Dificultat</div><div style="display:flex;gap:2px;">{segs_dif}</div></div>'

    elements_str = row[cols["elements"]] if cols["elements"] and pd.notna(row[cols["elements"]]) else ""
    cats_str     = row[cols["cats"]]     if cols["cats"]     and pd.notna(row[cols["cats"]])     else ""
    punts_html_content = punts_interes_html(elements_str, cats_str) if elements_str else "<div style='color:#888;font-size:13px;padding:8px 0;'>No hi ha punts d'interès registrats.</div>"

    # Comentaris columna AH
    comentaris_val = str(row[cols["comentaris"]]).strip() if cols.get("comentaris") and pd.notna(row[cols["comentaris"]]) and str(row[cols["comentaris"]]).strip() not in ("nan","") else ""

    # Descripció de la ruta (columna Descripció_ruta)
    desc_ruta_val = str(row[cols["desc_ruta"]]).strip() if cols.get("desc_ruta") and pd.notna(row[cols["desc_ruta"]]) and str(row[cols["desc_ruta"]]).strip() not in ("nan","") else ""

    perfil_bloc = ""

    TITOL_SECCIO = "font-size:13px;font-weight:700;color:#444;text-transform:uppercase;letter-spacing:0.5px;cursor:pointer;"
    CAP_SECCIO   = "background:#f5f5f5;padding:8px 12px;list-style:none;border-bottom:1px solid #e0e0e0;display:flex;align-items:center;justify-content:space-between;"
    COS_SECCIO   = "padding:10px 12px;"
    BOX_SECCIO   = "margin-top:10px;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;"

    def seccio_plegable(titol, contingut, obert=True):
        open_attr = "open" if obert else ""
        return (
            f"<details {open_attr} style='{BOX_SECCIO}'>"
            f"<summary style='{CAP_SECCIO}'>"
            f"<span style='{TITOL_SECCIO}'>{titol}</span>"
            f"<span style='font-size:11px;color:#aaa;'>▲▼</span>"
            f"</summary>"
            f"<div style='{COS_SECCIO}'>{contingut}</div>"
            f"</details>"
        )

    if svg_perfil_html:
        perfil_bloc = seccio_plegable(
            "⛰️ Perfil de la ruta",
            svg_perfil_html + alt_info_html + barra_dif,
            obert=False
        )

    # Descripció de la ruta (columna Descripció_ruta) — just a sobre de les estacions
    desc_ruta_html = ""
    if desc_ruta_val:
        desc_ruta_html = seccio_plegable(
            "📋 Descripció de la ruta",
            f"<div style='font-size:14px;color:#444;line-height:1.6;'>{desc_ruta_val}</div>",
            obert=True
        )

    detalls_html = (
        # 1. Descripció de la ruta
        desc_ruta_html +

        # 2. Dades
        seccio_plegable("📊 Dades", estacions_html + graella, obert=True) +

        # 3. Punts d'interès
        (seccio_plegable("📍 Punts d'interès", punts_html_content, obert=False)
         if punts_html_content else "") +

        # 4. Perfil
        perfil_bloc +

        # 5. Fotos
        (seccio_plegable("📷 Fotos de la ruta", fotos_contingut_html(ruta_id), obert=False)
         if fotos_contingut_html(ruta_id) else "")
    )

    etiquetes_html = f"<div style='padding:2px 12px 8px;'>{etiquetes}</div>" if etiquetes else ""

    # Foto de portada (primera foto disponible) per a la targeta
    foto_portada_html = ""
    if ruta_id and te_fotos:
        urls_fotos = obtenir_fotos_ruta(ruta_id)
        if urls_fotos:
            foto_portada_html = (
                f"<a href='{urls_fotos[0]}' target='_blank' style='"
                f"display:block;width:90px;flex-shrink:0;"
                f"overflow:hidden;border-radius:0 0 8px 0;'>"
                f"<img src='{urls_fotos[0]}' style='width:90px;height:90px;"
                f"object-fit:cover;display:block;' loading='lazy' "
                f"onerror=\"this.parentElement.style.display='none'\">"
                f"</a>"
            )

    # Botó Wikiloc (si hi ha URL)
    wikiloc_btn = ""
    if wiki_url and wiki_url != "nan":
        wikiloc_btn = (
            f"<a href='{wiki_url}' target='_blank' style='"
            f"display:block;background:#2d9e6b;color:white;border-radius:8px;"
            f"padding:7px 18px;text-align:center;font-size:12px;font-weight:700;letter-spacing:0.3px;"
            f"box-shadow:0 2px 6px #2d9e6b55;min-width:130px;text-decoration:none;'>"
            f"Wikiloc</a>"
        )

    card_html = (
        f"<div style='margin-top:12px;border:1px solid {dif_color}44;border-left:5px solid {dif_color};"
        f"border-radius:8px;overflow:visible;background:white;'>"
        f"<div style='background:{dif_color}18;padding:10px 12px 8px;'>"
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<div style='width:26px;height:26px;border-radius:50%;background:{dif_color};color:white;"
        f"font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;'>{ruta_id}</div>"
        f"<div style='flex:1;font-size:15px;font-weight:700;color:#111;line-height:1.3;'>{nom_ruta}{'  <span style=\"font-size:17px;\">📷</span>' if te_fotos else ''}</div>"
        f"</div>"
        f"{barra_mini_dif(dif_raw, dif_color)}"
        f"</div>"
        f"<div style='display:flex;gap:0;'>"
        f"<div style='flex:1;padding:6px 12px 4px;display:flex;gap:20px;flex-wrap:wrap;align-items:center;'>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Distància</div>"
        f"<div style='font-size:15px;font-weight:700;color:#111;'>{row[cols['km']]} km</div></div>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Desnivell</div>"
        f"<div style='font-size:15px;font-weight:700;color:#111;'>{desn_txt}</div></div>"
        f"<div><div style='font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.4px;'>Temps</div>"
        f"<div style='font-size:15px;font-weight:700;color:#111;'>{temps_fmt}</div></div>"
        f"</div>"
        f"{foto_portada_html}"
        f"</div>"
        + etiquetes_html +
        f"<details id='det_{ruta_id}' style='border-top:1px solid #eee;'>"
        f"<summary style='list-style:none;padding:0;cursor:pointer;display:block;' "
        f"onclick=\"this.parentElement.open ? "
        f"this.querySelector('.det-btn').textContent='Tancar ruta' : "
        f"this.querySelector('.det-btn').textContent='Veure detalls'\">"
        f"<div style='display:flex;justify-content:center;gap:10px;margin:10px 0 12px;flex-wrap:wrap;'>"
        f"<div class='det-btn' style='background:#7D8B99;color:white;border-radius:8px;"
        f"padding:7px 18px;text-align:center;font-size:12px;font-weight:700;letter-spacing:0.3px;"
        f"box-shadow:0 2px 6px #7D8B9955;min-width:130px;cursor:pointer;'>"
        f"Veure detalls</div>"
        + wikiloc_btn +
        f"</div></summary>"
        f"<div style='padding:4px 12px 16px;'>"
        + detalls_html +
        f"</div></details></div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)

    with st.expander("🗺️ Mapa del recorregut", key=f"mapa_{context}_{ruta_id}"):
        with st.spinner("Carregant mapa..."):
            if ruta_id:
                if not mostrar_mapa_gpx(ruta_id, lat_s, lng_s, lat_a, lng_a, context=context):
                    st.info("Mapa no disponible per aquesta ruta.")



try:
    df_raw = carregar_dades()
except Exception as e:
    st.error(f"Error connectant amb Google Sheets: {e}")
    st.stop()

try:
    df_raw.columns = df_raw.columns.str.strip().str.lower()

    def norm(s):
        """Normalitza string: minúscules i sense accents, per comparació robusta."""
        return (s.lower()
                 .replace("à","a").replace("á","a")
                 .replace("è","e").replace("é","e")
                 .replace("í","i").replace("ï","i")
                 .replace("ò","o").replace("ó","o")
                 .replace("ú","u").replace("ü","u")
                 .replace("ç","c"))

    def buscar_col(llista):
        for c in df_raw.columns:
            c_norm = norm(str(c))
            for p in llista:
                if norm(p) in c_norm:
                    return c
        return None

    cols = {
        "id":          buscar_col(["num_ruta", "id_ruta", "id"]),
        "ruta":        buscar_col(["nom_ruta"]),
        "wiki":        buscar_col(["enllac_wikiloc", "wikiloc"]),
        "sortida":     buscar_col(["estacio_sortida"]),
        "op_s":        buscar_col(["operador_sortida"]),
        "id_est_s":    buscar_col(["id_estacio_sortida"]),
        "coord_s":     buscar_col(["lat_sortida"]),
        "lon_s":       buscar_col(["lon_sortida"]),
        "linia_s":     buscar_col(["linies_sortida"]),
        "comarca":     buscar_col(["comarca_sortida"]),
        "arribada":    buscar_col(["estacio_arribada"]),
        "op_a":        buscar_col(["operador_arribada"]),
        "id_est_a":    buscar_col(["id_estacio_arribada"]),
        "coord_a":     buscar_col(["lat_arribada"]),
        "lon_a":       buscar_col(["lon_arribada"]),
        "linia_a":     buscar_col(["linies_arribada"]),
        "km":          buscar_col(["km"]),
        "desn":        buscar_col(["desnivell_positiu"]),
        "baixada":     buscar_col(["desnivell_negatiu"]),
        "tipus":       buscar_col(["tipus_ruta"]),
        "dif":         buscar_col(["dificultat"]),
        "temps":       buscar_col(["durada_estimada"]),
        "epoca":       buscar_col(["millor_epoca"]),
        "punt_alt":    buscar_col(["punt_mes_alt"]),
        "altitud_max": buscar_col(["alcada_punt_alt"]),
        "cims":        buscar_col(["100cims"]),
        "cims_noms":   buscar_col(["nom_100cims"]),
        "coord_cim":   buscar_col(["lat_100cims"]),
        "lon_cim":     buscar_col(["lon_100cims"]),
        "terreny":     buscar_col(["senders"]),
        "elements":    buscar_col(["elements_interes"]),
        "cats":        buscar_col(["categories_elements_interes"]),
        "desc_ruta":   buscar_col(["descripcio_ruta"]),
        "espai":       buscar_col(["espai_natural"]),
        "comarca_a":   buscar_col(["comarca_arribada"]),
        "espai_a":     buscar_col(["espai_natural_arribada"]),
        "comentaris":  None,
        "desc":        buscar_col(["descripcio_ruta"]),
        "millors":     buscar_col(["millors_rutes"]),
        "advertiments": buscar_col(["advertiments"]),
    }

    df = df_raw.dropna(subset=[cols["ruta"]]).copy()
    df[cols["km"]] = pd.to_numeric(df[cols["km"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["desn"]:
        df[cols["desn"]] = pd.to_numeric(df[cols["desn"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    if cols["baixada"]:
        df[cols["baixada"]] = pd.to_numeric(df[cols["baixada"]].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    def get_unique(col_name, col_name2=None):
        res = set()
        for cn in [col_name, col_name2]:
            if cn and cn in df.columns:
                vals = df[cn].dropna().astype(str)
                for v in vals:
                    for s in re.split(";|,", v):
                        if s.strip() and s.strip().lower() not in ("nan", ""):
                            res.add(s.strip())
        return sorted(list(res))

    # --- FILTRES SIDEBAR ---
    st.sidebar.header("🔎 Filtres")
    st.sidebar.markdown(
        '<img src="https://raw.githubusercontent.com/Senderismeentren/senderisme-recursos/refs/heads/main/logo-100cims.svg" width="80" style="margin-bottom:5px;">',
        unsafe_allow_html=True
    )

    # ── Botó Netejar filtres — ABANS dels widgets per poder modificar session_state ──
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Netejar filtres", key="btn_netejar_filtres", use_container_width=True):
        st.session_state.filtre_btn_estacio = None
        st.session_state.filtre_btn_linia   = None
        st.session_state.filtre_btn_ruta    = None
        st.session_state.filtre_btn_millors = None
        st.session_state.filtre_reset_counter = st.session_state.get("filtre_reset_counter", 0) + 1
        for key in ["sb_op", "sb_dif", "sb_comarca", "sb_espai", "sb_sortida", "sb_linia"]:
            if key in st.session_state:
                st.session_state[key] = []
        for key in ["sb_desn", "sb_km"]:
            if key in st.session_state:
                del st.session_state[key]
        if "sb_100cims" in st.session_state:
            st.session_state["sb_100cims"] = False
        if "sb_cerca" in st.session_state:
            st.session_state["sb_cerca"] = ""
        st.rerun()
    st.sidebar.markdown("---")

    sel_100cims = st.sidebar.checkbox("Rutes amb 100 Cims", key="sb_100cims")
    cerca       = st.sidebar.text_input("📝 Paraula clau", key="sb_cerca")

    # Construir estacions agrupades per operador
    def estacions_per_operador():
        grups = {}
        for _, r in df.iterrows():
            for col_est, col_op in [(cols["sortida"], cols["op_s"]), (cols["arribada"], cols["op_a"])]:
                if not col_est or not col_op: continue
                est = str(r[col_est]).strip() if pd.notna(r[col_est]) else ""
                if not est or est.lower() in ("nan",""):  continue
                ops_raw = str(r[col_op]).strip() if pd.notna(r[col_op]) else ""
                ops = [o.strip().title() for o in ops_raw.split(";") if o.strip() and o.strip().lower() not in ("nan","","none")]
                if not ops:
                    ops = ["Altres"]
                for op in ops:
                    grups.setdefault(op, set()).add(est)
        return {op: sorted(ests) for op, ests in sorted(grups.items())}

    def linies_per_operador():
        grups = {}
        for _, r in df.iterrows():
            for col_lin, col_op in [(cols["linia_s"], cols["op_s"]), (cols["linia_a"], cols["op_a"])]:
                if not col_lin or not col_op: continue
                lins = [l.strip() for l in str(r[col_lin]).split(";") if l.strip() and l.strip().lower() not in ("nan","")]
                ops_raw = str(r[col_op]).strip() if pd.notna(r[col_op]) else ""
                # Suport per a múltiples operadors separats per ;
                ops = [o.strip().title() for o in ops_raw.split(";") if o.strip() and o.strip().lower() not in ("nan","","none")]
                if not ops:
                    ops = ["Altres"]
                for op in ops:
                    for l in lins:
                        grups.setdefault(op, set()).add(l)
        return {op: sorted(lins) for op, lins in sorted(grups.items())}

    grups_estacions = estacions_per_operador()
    grups_linies    = linies_per_operador()

    # Multiselect estacions amb grups visuals
    opcions_estacions = []
    for op, ests in grups_estacions.items():
        opcions_estacions.append(f"── {op} ──")
        opcions_estacions.extend(ests)

    sel_sortida_raw = st.sidebar.multiselect(
        "🚉 Estació de sortida",
        opcions_estacions,
        format_func=lambda x: x,
        key="sb_sortida"
    )
    sel_sortida = [e for e in sel_sortida_raw if not e.startswith("──")]

    # Multiselect línies amb grups visuals
    opcions_linies = []
    for op, lins in grups_linies.items():
        opcions_linies.append(f"── {op} ──")
        for l in lins:
            dest = RECORREGUTS_LINIA.get(l, "")
            opcions_linies.append(f"{l}  {dest}" if dest else l)

    sel_linia_raw = st.sidebar.multiselect(
        "🚆 Línia de tren",
        opcions_linies,
        format_func=lambda x: x,
        key="sb_linia"
    )
    sel_linia = [l.split("  ")[0].strip() for l in sel_linia_raw if not l.startswith("──")]

    sel_op  = st.sidebar.multiselect("🏢 Operador", get_unique(cols["op_s"], cols.get("op_a")), key="sb_op")
    sel_dif = st.sidebar.multiselect("🧗 Dificultat", ["Molt Fàcil", "Fàcil", "Moderada", "Exigent", "Molt exigent"], key="sb_dif")

    # ── Comarca ordenada per provincies ──
    COMARQUES_PROVINCIA = {
        "Barcelona": [
            "Alt Penedès","Anoia","Bages","Baix Llobregat","Barcelonès","Berguedà",
            "Garraf","Maresme","Moianès","Osona","Vallès Occidental","Vallès Oriental",
        ],
        "Girona": [
            "Alt Empordà","Baix Empordà","Cerdanya","Garrotxa","Gironès","Pla de l'Estany",
            "Ripollès","Selva","Osona",
        ],
        "Lleida": [
            "Alta Ribagorça","Alt Urgell","Cerdanya","Garrigues","Noguera","Pallars Jussà",
            "Pallars Sobirà","Pla d'Urgell","Segarra","Segrià","Solsonès","Urgell",
            "Val d'Aran",
        ],
        "Tarragona": [
            "Alt Camp","Baix Camp","Baix Ebre","Baix Penedès","Conca de Barberà",
            "Montsià","Priorat","Ribera d'Ebre","Tarragonès","Terra Alta",
        ],
        "Catalunya Nord": [
            "Alt Conflent","Capcir","Cerdanya","Conflent","Fenolledès","Rosselló",
            "Vallespir",
        ],
        "Aragó": [],
        "País Valencià": [],
        "Occitània": [],
        "Madrid": [],
    }

    def comarques_agrupades():
        totes = set(get_unique(cols["comarca"], cols.get("comarca_a")))
        opcions = []
        assignades = set()
        for provincia, llista in COMARQUES_PROVINCIA.items():
            comarques_prov = [c for c in llista if c in totes]
            # Afegir també comarques de l'Excel que no estan a la llista predefinida
            # però que podrien pertànyer a aquesta provincia si coincideix el nom
            if comarques_prov:
                opcions.append(f"── {provincia} ──")
                for c in sorted(comarques_prov):
                    opcions.append(c)
                    assignades.add(c)
        # Comarques que no hem assignat a cap provincia
        sense_assignar = [c for c in sorted(totes) if c not in assignades]
        if sense_assignar:
            opcions.append("── Altres ──")
            opcions.extend(sense_assignar)
        return opcions

    opcions_comarques = comarques_agrupades()
    sel_comarca_raw = st.sidebar.multiselect("📍 Comarca", opcions_comarques, format_func=lambda x: x, key="sb_comarca")
    sel_comarca = [c for c in sel_comarca_raw if not c.startswith("──")]

    sel_espai = st.sidebar.multiselect("🌲 Espai natural", get_unique(cols.get("espai"), cols.get("espai_a")), key="sb_espai")

    min_km, max_km = float(df[cols["km"]].min()), float(df[cols["km"]].max())
    sel_km   = st.sidebar.slider("📏 Distància (km)", min_km, max_km, (min_km, max_km), key="sb_km")

    min_desn = float(df[cols["desn"]].min()) if cols["desn"] else 0.0
    max_desn = float(df[cols["desn"]].max()) if cols["desn"] else 9999.0
    sel_desn = st.sidebar.slider("📈 Desnivell (m)", min_desn, max_desn, (min_desn, max_desn), key="sb_desn")

    # --- APLICAR FILTRES SIDEBAR ---
    f = df.copy()
    if sel_100cims and cols["cims"]:
        f = f[f[cols["cims"]].astype(str).str.strip().str.lower() == "si"]
    if cerca:
        _camps_cerca = [cols["ruta"]]
        if cols.get("desc_ruta"): _camps_cerca.append(cols["desc_ruta"])
        if cols.get("elements"):  _camps_cerca.append(cols["elements"])
        _mask_cerca = pd.Series(False, index=f.index)
        for _c in _camps_cerca:
            if _c and _c in f.columns:
                _mask_cerca |= f[_c].astype(str).str.contains(cerca, case=False, na=False)
        f = f[_mask_cerca]
    if sel_sortida:
        f = f[f[cols["sortida"]].astype(str).apply(lambda x: any(s in x for s in sel_sortida))]
    if sel_linia:
        mask_s = f[cols["linia_s"]].astype(str).apply(lambda x: any(l in x for l in sel_linia))
        mask_a = f[cols["linia_a"]].astype(str).apply(lambda x: any(l in x for l in sel_linia)) if cols.get("linia_a") else pd.Series(False, index=f.index)
        f = f[mask_s | mask_a]
    if sel_op and cols.get("op_s"):
        mask_s = f[cols["op_s"]].astype(str).apply(lambda x: any(o in x for o in sel_op))
        mask_a = f[cols["op_a"]].astype(str).apply(lambda x: any(o in x for o in sel_op)) if cols.get("op_a") else pd.Series(False, index=f.index)
        f = f[mask_s | mask_a]
    if sel_dif:
        f = f[f[cols["dif"]].astype(str).apply(lambda x: any(d in x for d in sel_dif))]
    if sel_comarca:
        mask_s = f[cols["comarca"]].astype(str).apply(lambda x: any(c in x for c in sel_comarca))
        mask_a = f[cols["comarca_a"]].astype(str).apply(lambda x: any(c in x for c in sel_comarca)) if cols.get("comarca_a") else pd.Series(False, index=f.index)
        f = f[mask_s | mask_a]
    if sel_espai:
        mask_s = f[cols["espai"]].astype(str).apply(lambda x: any(e in x for e in sel_espai))
        mask_a = f[cols["espai_a"]].astype(str).apply(lambda x: any(e in x for e in sel_espai)) if cols.get("espai_a") else pd.Series(False, index=f.index)
        f = f[mask_s | mask_a]
    f = f[(f[cols["km"]] >= sel_km[0]) & (f[cols["km"]] <= sel_km[1])]
    if cols["desn"]:
        f = f[(f[cols["desn"]] >= sel_desn[0]) & (f[cols["desn"]] <= sel_desn[1])]

    # --- ESTAT FILTRE ESTACIÓ ---
    if "filtre_estacio" not in st.session_state:
        st.session_state.filtre_estacio = None
    if "map_reset_counter" not in st.session_state:
        st.session_state.map_reset_counter = 0
    if "pestanya_activa" not in st.session_state:
        st.session_state.pestanya_activa = "rutes"

    # --- MODE MAPA SOL (per a WordPress iframe: ?page=mapa) ---
    if st.query_params.get("page") == "mapa":
        mostrar_mapa_general(f, cols)
        st.stop()

    # --- PESTANYES (les natives queden amagades pel CSS, però cal declarar-les) ---
    tab_llista, tab_mapa, tab_cims, tab_millors = st.tabs(["🥾 Rutes", "🗺️ Mapa", "🏔️ 100 Cims", "⭐ Millors"])

    with tab_mapa:
        mostrar_mapa_general(f, cols)
        if st.session_state.get("filtre_estacio"):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.info(f"🚉 Estació: **{st.session_state.filtre_estacio}**")
            with col_btn:
                if st.button("✖ Treure filtre", key="btn_treure_mapa"):
                    st.session_state.filtre_estacio = None
                    st.session_state.map_reset_counter += 1
                    st.rerun()
            f_mapa = f[
                (f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_estacio) |
                (f[cols["arribada"]].astype(str).str.strip() == st.session_state.filtre_estacio)
            ]
            st.write(f"**{len(f_mapa)} rutes amb {st.session_state.filtre_estacio}**")
            for _, row_m in f_mapa.iterrows():
                render_ruta_completa(row_m, cols, context="mapa")

    with tab_cims:
        if "filtre_cim" not in st.session_state:
            st.session_state.filtre_cim = None

        if st.session_state.filtre_cim:
            st.markdown(f"### 🏔️ {st.session_state.filtre_cim}")
            if st.button("← Tornar a la llista de cims"):
                st.session_state.filtre_cim = None
                st.rerun()
            # FIX 1: usar f (ja filtrat pel sidebar) en lloc de df
            if cols.get("cims_noms"):
                f_cim = f[f[cols["cims_noms"]].astype(str).str.contains(
                    st.session_state.filtre_cim, case=False, na=False, regex=False
                )]
            else:
                f_cim = f.iloc[0:0]
            st.write(f"**{len(f_cim)} rutes visiten aquest cim**")
            for _, row_c in f_cim.iterrows():
                render_ruta_completa(row_c, cols, context="cims")
        else:
            if cols.get("cims_noms") and cols.get("comarca"):
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

    with tab_millors:
        if not cols.get("millors") or not cols.get("ruta") or not cols.get("id"):
            st.info("No hi ha dades de millors rutes disponibles.")
        else:
            per_cat_m = {}
            for _, r_m in df.iterrows():
                cat_m = str(r_m[cols["millors"]]).strip() if pd.notna(r_m[cols["millors"]]) else ""
                if not cat_m or cat_m.lower() in ("nan", ""): continue
                nom_m = str(r_m[cols["ruta"]]).strip() if pd.notna(r_m[cols["ruta"]]) else ""
                if not nom_m or nom_m.lower() in ("nan", ""): continue
                num_m = str(r_m[cols["id"]]).strip() if pd.notna(r_m[cols["id"]]) else ""
                try:
                    codi_m = f"ST{int(float(num_m)):03d}"
                except Exception:
                    codi_m = f"ST{num_m}"
                entrada = (codi_m, nom_m, r_m)
                per_cat_m.setdefault(cat_m, [])
                if not any(e[0] == codi_m for e in per_cat_m[cat_m]):
                    per_cat_m[cat_m].append(entrada)

            n_total_millors = sum(len(v) for v in per_cat_m.values())
            st.markdown(
                f"<div style='font-size:22px;font-weight:700;color:#111;margin-bottom:16px;'>"
                f"{n_total_millors} rutes destacades</div>",
                unsafe_allow_html=True
            )

            if "filtre_millors_ruta" not in st.session_state:
                st.session_state.filtre_millors_ruta = None

            if st.session_state.filtre_millors_ruta:
                codi_sel_m, nom_sel_m = st.session_state.filtre_millors_ruta
                st.markdown(f"### ⭐ {codi_sel_m} · {nom_sel_m}")
                if st.button("← Tornar a la llista de millors rutes", key="btn_tornar_millors"):
                    st.session_state.filtre_millors_ruta = None
                    st.rerun()
                f_millors = df[
                    df[cols["ruta"]].astype(str).str.strip() == nom_sel_m
                ]
                for _, row_mm in f_millors.iterrows():
                    render_ruta_completa(row_mm, cols, context="millors")
            else:
                for cat_m in sorted(per_cat_m.keys()):
                    rutes_cat_m = sorted(per_cat_m[cat_m], key=lambda x: x[0])
                    st.markdown(
                        f"<div style='font-size:12px;font-weight:700;text-transform:uppercase;"
                        f"letter-spacing:0.5px;color:#aaa;margin:16px 0 6px;'>{cat_m}</div>",
                        unsafe_allow_html=True
                    )
                    for codi_m, nom_m, _ in rutes_cat_m:
                        if st.button(f"⭐ {codi_m} · {nom_m}", key=f"millors_{codi_m}"):
                            st.session_state.filtre_millors_ruta = (codi_m, nom_m)
                            st.rerun()

    with tab_llista:
        if "filtre_btn_estacio" not in st.session_state:
            st.session_state.filtre_btn_estacio = None
        if "filtre_btn_linia" not in st.session_state:
            st.session_state.filtre_btn_linia = None
        if "filtre_btn_ruta" not in st.session_state:
            st.session_state.filtre_btn_ruta = None

        # ── Estacions ordenades per operador ──
        def build_estacions_agrupades():
            grups = {}
            for _, r in df.iterrows():
                for col_est, col_op in [(cols.get("sortida"), cols.get("op_s")),
                                        (cols.get("arribada"), cols.get("op_a"))]:
                    if not col_est or not col_op: continue
                    est = str(r[col_est]).strip() if pd.notna(r[col_est]) else ""
                    if not est or est.lower() in ("nan","","none"): continue
                    ops_raw = str(r[col_op]).strip() if pd.notna(r[col_op]) else ""
                    ops = [o.strip().title() for o in ops_raw.split(";") if o.strip() and o.strip().lower() not in ("nan","","none")]
                    if not ops:
                        ops = ["Altres"]
                    for op in ops:
                        grups.setdefault(op, set()).add(est)
            opcions = ["🚉 Estació"]
            for op in sorted(grups.keys()):
                opcions.append(f"── {op} ──")
                opcions.extend(sorted(grups[op]))
            return opcions

        # ── Línies ordenades per operador ──
        def build_linies_agrupades():
            grups = {}
            for _, r in df.iterrows():
                for col_lin, col_op in [(cols.get("linia_s"), cols.get("op_s")),
                                        (cols.get("linia_a"), cols.get("op_a"))]:
                    if not col_lin or not col_op: continue
                    lins = [l.strip() for l in str(r[col_lin]).split(";")
                            if l.strip() and l.strip().lower() not in ("nan","")]
                    ops_raw = str(r[col_op]).strip() if pd.notna(r[col_op]) else ""
                    ops = [o.strip().title() for o in ops_raw.split(";") if o.strip() and o.strip().lower() not in ("nan","","none")]
                    if not ops:
                        ops = ["Altres"]
                    for op in ops:
                        for l in lins:
                            grups.setdefault(op, set()).add(l)
            opcions = ["🚆 Línia"]
            for op in sorted(grups.keys()):
                opcions.append(f"── {op} ──")
                for l in sorted(grups[op]):
                    recorregut = RECORREGUTS_LINIA.get(l, "")
                    opcions.append(f"{l}  {recorregut}" if recorregut else l)
            return opcions

        # ── Llistat de rutes ordenat per Núm_Ruta ──
        def build_rutes_llista():
            opcions = ["📋 Llistat de rutes"]
            if not cols.get("id") or not cols.get("ruta"): return opcions
            rutes_df = df[[cols["id"], cols["ruta"]]].dropna(subset=[cols["id"]])
            rutes_df = rutes_df.sort_values(by=cols["id"])
            for _, r in rutes_df.iterrows():
                num  = str(r[cols["id"]]).strip()
                nom  = str(r[cols["ruta"]]).strip() if pd.notna(r[cols["ruta"]]) else ""
                codi = f"ST{int(float(num)):03d}" if num.replace(".","").isdigit() else f"ST{num}"
                opcions.append(f"{codi} · {nom}")
            return opcions

        # ── Millors rutes: categories destacades, ordenades per categoria i nom ──
        def build_millors_rutes():
            """Llegeix la columna Millors_rutes de Sheets i agrupa per categoria."""
            opcions = ["⭐ Millors rutes"]
            if not cols.get("millors") or not cols.get("ruta") or not cols.get("id"):
                return opcions
            per_cat = {}
            for _, r in df.iterrows():
                cat = str(r[cols["millors"]]).strip() if pd.notna(r[cols["millors"]]) else ""
                if not cat or cat.lower() in ("nan", ""): continue
                nom = str(r[cols["ruta"]]).strip() if pd.notna(r[cols["ruta"]]) else ""
                if not nom or nom.lower() in ("nan", ""): continue
                num_raw = str(r[cols["id"]]).strip() if pd.notna(r[cols["id"]]) else ""
                try:
                    codi = f"ST{int(float(num_raw)):03d}"
                except Exception:
                    codi = f"ST{num_raw}"
                etiqueta = f"Ruta {codi}. {nom}"
                per_cat.setdefault(cat, [])
                if etiqueta not in per_cat[cat]:
                    per_cat[cat].append(etiqueta)
            for cat in sorted(per_cat.keys()):
                rutes_cat = sorted(per_cat[cat])
                if rutes_cat:
                    opcions.append(f"── {cat} ──")
                    opcions.extend(rutes_cat)
            return opcions

        est_options    = build_estacions_agrupades()
        lin_options    = build_linies_agrupades()
        ruta_options   = build_rutes_llista()
        millors_options = build_millors_rutes()

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

        if "filtre_reset_counter" not in st.session_state:
            st.session_state.filtre_reset_counter = 0
        if "filtre_btn_millors" not in st.session_state:
            st.session_state.filtre_btn_millors = None

        _reset_sfx = st.session_state.filtre_reset_counter

        # ── Selector de mode: Estació o Línia ──────────────────────────
        if "mode_filtre_tren" not in st.session_state:
            st.session_state.mode_filtre_tren = "🚉 Estació"

        col_radio, col_sel, col_ruta = st.columns([1, 2, 2])
        with col_radio:
            mode_tren = st.radio(
                "Mode", ["🚉 Estació", "🚆 Línia"],
                index=0 if st.session_state.mode_filtre_tren == "🚉 Estació" else 1,
                key=f"radio_mode_tren_{_reset_sfx}",
                label_visibility="collapsed",
                horizontal=True
            )
            st.session_state.mode_filtre_tren = mode_tren

        with col_sel:
            if st.session_state.mode_filtre_tren == "🚉 Estació":
                sel_est_btn = st.selectbox("Estació", est_options,
                    index=0 if not st.session_state.filtre_btn_estacio else
                          est_options.index(st.session_state.filtre_btn_estacio)
                          if st.session_state.filtre_btn_estacio in est_options else 0,
                    key=f"sel_est_btn_{_reset_sfx}", label_visibility="collapsed")
                st.session_state.filtre_btn_estacio = sel_est_btn if sel_est_btn != "🚉 Estació" and not sel_est_btn.startswith("──") else None
                st.session_state.filtre_btn_linia = None
            else:
                sel_lin_btn = st.selectbox("Línia", lin_options,
                    index=0,
                    key=f"sel_lin_btn_{_reset_sfx}", label_visibility="collapsed")
                if sel_lin_btn and sel_lin_btn != "🚆 Línia" and not sel_lin_btn.startswith("──"):
                    st.session_state.filtre_btn_linia = sel_lin_btn.split("  ")[0].strip()
                else:
                    st.session_state.filtre_btn_linia = None
                st.session_state.filtre_btn_estacio = None

        with col_ruta:
            sel_ruta_btn = st.selectbox("Llistat de rutes", ruta_options,
                index=0 if not st.session_state.filtre_btn_ruta else
                      ruta_options.index(st.session_state.filtre_btn_ruta)
                      if st.session_state.filtre_btn_ruta in ruta_options else 0,
                key=f"sel_ruta_btn_{_reset_sfx}", label_visibility="collapsed")
            st.session_state.filtre_btn_ruta = sel_ruta_btn if sel_ruta_btn != "📋 Llistat de rutes" else None

        if st.session_state.filtre_btn_estacio:
            # Estació de sortida: només cerca a la columna sortida
            f = f[
                f[cols["sortida"]].astype(str).str.strip() == st.session_state.filtre_btn_estacio
            ]
        if st.session_state.filtre_btn_linia:
            _lin = st.session_state.filtre_btn_linia
            # Cerca la línia tant a sortida com a arribada
            mask_s = f[cols["linia_s"]].astype(str).apply(
                lambda x: _lin in [l.strip() for l in x.split(";")]
            )
            mask_a = f[cols["linia_a"]].astype(str).apply(
                lambda x: _lin in [l.strip() for l in x.split(";")]
            ) if cols.get("linia_a") else pd.Series([False] * len(f), index=f.index)
            f = f[mask_s | mask_a]
        if st.session_state.filtre_btn_ruta and cols.get("id") and cols.get("ruta"):
            # Extraiem el número de la selecció "ST001 · Nom ruta"
            _codi_sel = st.session_state.filtre_btn_ruta.split(" · ")[0].replace("ST","").lstrip("0") or "0"
            f = f[f[cols["id"]].astype(str).str.replace(".0","",regex=False).str.lstrip("0").apply(
                lambda x: (x or "0") == _codi_sel
            )]

        # ── Ordenació ──────────────────────────────────────────────────
        _opcions_ordre = {
            "Núm. ruta (defecte)": (cols["id"],    True,  False),
            "Nom (A → Z)":         (cols["ruta"],  True,  False),
            "Distància ↑":         (cols["km"],    True,  True),
            "Distància ↓":         (cols["km"],    False, True),
            "Desnivell ↑":         (cols["desn"],  True,  True),
            "Desnivell ↓":         (cols["desn"],  False, True),
        }
        _ordre_sel = st.selectbox("Ordenar per", list(_opcions_ordre.keys()),
            key="sb_ordre", label_visibility="collapsed")
        _col_ord, _asc, _numeric = _opcions_ordre[_ordre_sel]
        if _col_ord and _col_ord in f.columns:
            if _numeric:
                f = f.copy()
                f[_col_ord] = pd.to_numeric(f[_col_ord].astype(str).str.replace(",","."), errors="coerce").fillna(0)
            f = f.sort_values(by=_col_ord, ascending=_asc)

        # ── URL directa per ruta (?ruta=005) ──────────────────────────
        _ruta_param = st.query_params.get("ruta", "")
        if _ruta_param:
            _ruta_num = _ruta_param.lstrip("0") or "0"
            f_param = f[f[cols["id"]].astype(str).str.replace(".0","",regex=False).str.lstrip("0").apply(
                lambda x: (x or "0") == _ruta_num
            )]
            if not f_param.empty:
                f = f_param

        n_fotos_per_ruta = {}
        _spinner_placeholder = st.empty()
        with _spinner_placeholder:
            for _rid in f[cols["id"]].dropna().unique():
                try:
                    _rid_int = int(float(_rid))
                    n_fotos_per_ruta[_rid_int] = len(obtenir_fotos_ruta(_rid_int))
                except Exception:
                    pass
        _spinner_placeholder.empty()

        col_res, col_ord = st.columns([3, 2])
        with col_res:
            st.markdown(f"**{len(f)} rutes**", unsafe_allow_html=True)

        for _, row in f.iterrows():
            try:
                _rid_int = int(float(str(row[cols["id"]])))
            except Exception:
                _rid_int = None
            _te_fotos = _rid_int and n_fotos_per_ruta.get(_rid_int, 0) > 0
            render_ruta_completa(row, cols, te_fotos=_te_fotos)
except Exception as e:
    st.error(f"S'ha produït un error: {e}")
