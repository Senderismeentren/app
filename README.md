# Senderisme en Tren — Flask

Portal de rutes de senderisme accessibles en tren per Catalunya.

## Estructura

```
app/
  app.py                  ← servidor Flask principal
  requirements.txt        ← dependències Python
  templates/
    base.html             ← plantilla mare (nav, footer)
    inici.html            ← pàgina d'inici
    rutes.html            ← llista de rutes amb filtres
    fitxa.html            ← fitxa individual de cada ruta
    mapa.html             ← mapa general amb estacions i tracks
    colleccions.html      ← col·leccions temàtiques
    404.html              ← pàgina d'error
```

## Variables d'entorn necessàries

| Variable        | Descripció |
|----------------|------------|
| `SHEET_ID`     | ID del Google Sheet amb les dades |
| `GOOGLE_CREDS` | JSON de credencials del compte de servei Google |

## Execució local

```bash
pip install -r requirements.txt
python app.py
```

L'app estarà disponible a `http://localhost:5000`

## Deployment a Render

1. Crea un nou **Web Service** a [render.com](https://render.com)
2. Connecta el repositori de GitHub
3. Configuració:
   - **Build Command**: `pip install -r app/requirements.txt`
   - **Start Command**: `gunicorn app.app:app`
   - **Root Directory**: `app`
4. Afegeix les variables d'entorn `SHEET_ID` i `GOOGLE_CREDS`
5. Despliega

## Seccions del portal

- `/` — Pàgina d'inici amb rutes destacades, col·leccions i articles
- `/rutes` — Llista filtrable de totes les rutes
- `/ruta/<id>` — Fitxa individual amb mapa GPX, perfil d'altitud i horaris
- `/mapa` — Mapa general amb estacions i tracks
- `/colleccions` — Rutes agrupades per temàtiques
- `/api/rutes` — API JSON amb totes les rutes
- `/api/gpx/<id>` — Track GPX d'una ruta en format JSON
- `/api/horaris/<id_estacio>` — Horaris en temps real (pendent d'IDs)
