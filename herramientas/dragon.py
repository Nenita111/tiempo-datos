"""Próximos campeonatos internacionales de barco dragón (4.41, lo pidió Isa el 11 nov 2026: «indica próximos campeonatos de dragon
boat»): los mundiales de la Federación Internacional de Barco Dragón (IDBF, dragonboat.sport: «Upcoming Championships») y las pruebas de
barco dragón del calendario de Paddle Europe (la europea de piragüismo: paddle-europe.eu/calendar, categoría 6, de este año y del que
viene). Los de Andalucía y los de España los lee la tele de sus federaciones (su calendario). La federación internacional de piragüismo
(paddleworldwide.com, antes canoeicf.com) cierra el paso a los agentes como Claude en su robots.txt: no se usa.

  python3 -I herramientas/dragon.py extras.json [--siempre]

Solo mira los lunes y los jueves (o si aún no hay nada, o con --siempre): estos calendarios cambian muy de tarde en tarde. Guarda en
extras.json («dragon») los que no han pasado; si nada cambia, no toca el fichero. Lo que no se lee bien no se apunta. Imprime una línea
JSON: {"dragon": N, "idbf": N, "europa": N} o {"error": …} (sale con 1 y deja lo que había).
"""
import datetime as dt, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

IDBF = "https://www.dragonboat.sport/events/idbf-championships-ccwc-wdbrc/"
EUROPA = "https://paddle-europe.eu/calendar?year={}&category=6"
MESES_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
PAISES = {"Spain": "España", "Germany": "Alemania", "Italy": "Italia", "France": "Francia", "Hungary": "Hungría", "Poland": "Polonia",
          "Czech Republic": "República Checa", "Czechia": "Chequia", "Serbia": "Serbia", "Ukraine": "Ucrania", "Switzerland": "Suiza",
          "Sweden": "Suecia", "United Kingdom": "Reino Unido", "Great Britain": "Gran Bretaña", "Philippines": "Filipinas",
          "Thailand": "Tailandia", "Canada": "Canadá", "USA": "EE. UU.", "United States": "Estados Unidos", "Chinese Taipei": "China Taipéi",
          "Australia": "Australia", "Japan": "Japón", "Portugal": "Portugal", "Romania": "Rumanía", "Bulgaria": "Bulgaria", "Greece": "Grecia",
          "Turkey": "Turquía", "Russia": "Rusia", "Georgia": "Georgia", "Cyprus": "Chipre", "Netherlands": "Países Bajos", "Belgium": "Bélgica",
          "Austria": "Austria", "Slovakia": "Eslovaquia", "Slovenia": "Eslovenia", "Croatia": "Croacia", "Singapore": "Singapur"}


def fechas(t):
    """«17-24 October 2027», «29 August-6 September 2026», «14-20 July, 2025», «5 June 2027» → (desde, hasta) en ISO; si no es eso, None."""
    s = re.sub(r"\s+", " ", t.lower().replace(",", " ").replace("–", "-")).strip()
    mes = "(" + "|".join(MESES_EN) + ")"
    m = re.fullmatch(rf"(\d{{1,2}}) ?{mes} ?- ?(\d{{1,2}}) ?{mes} (\d{{4}})", s)
    if m: d1, m1, d2, m2, a = int(m[1]), MESES_EN.index(m[2]) + 1, int(m[3]), MESES_EN.index(m[4]) + 1, int(m[5])
    else:
        m = re.fullmatch(rf"(\d{{1,2}})(?: ?- ?(\d{{1,2}}))? ?{mes} (\d{{4}})", s)
        if not m: return None
        d1, d2, m1, a = int(m[1]), int(m[2] or m[1]), MESES_EN.index(m[3]) + 1, int(m[4]); m2 = m1
    try: return dt.date(a, m1, d1).isoformat(), dt.date(a, m2, d2).isoformat()
    except ValueError: return None


def lugar(t):
    """El sitio, con el país en español si se conoce: «Castelldefels, Barcelona, Spain» → «Castelldefels, Barcelona (España)»."""
    p = [x.strip() for x in re.sub(r"\s+", " ", t).split(",") if x.strip()]
    if len(p) > 1 and p[-1] in PAISES: return ", ".join(p[:-1]) + f" ({PAISES[p[-1]]})"
    return ", ".join(p)


def titulo_idbf(t):
    """El nombre en español de los dos campeonatos del mundo de la IDBF; cualquier otro, como viene."""
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th) IDBF World Dragon Boat Racing Championships", t)
    if m: return f"{m[1]}.º Mundial de Barco Dragón de selecciones"
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th) IDBF Club Crew World Championships", t)
    if m: return f"{m[1]}.º Mundial de Clubes de Barco Dragón"
    return t


def leer_idbf(pagina):
    """Los campeonatos de «Upcoming Championships» (hasta «Past World Championships»): el nombre (en negrita), quien lo organiza (en
    cursiva), el sitio, las fechas («Date TBC» si aún no las hay) y el año (el botón). Sin año o sin nombre, no se apunta."""
    j = pagina.find("Past World Championships"); i = pagina.rfind("Upcoming Championships", 0, max(j, 0))
    if i < 0 or j < 0: raise ValueError("la página de la IDBF ha cambiado: sin «Upcoming Championships»")
    out = []
    # cada campeonato acaba en el botón de su año
    for bloque in re.split(r'(?<=</a>)', pagina[i:j]):
        boton = re.search(r'<a class="et_pb_button[^"]*"[^>]*>\s*(20\d\d)\s*</a>\s*$', bloque)
        nombre = " ".join(comun.limpio(x) for x in re.findall(r"(?s)<strong>(.*?)</strong>", bloque)).strip()
        if not boton or not nombre: continue
        organiza = comun.limpio((re.search(r"(?s)<em>(.*?)</em>", bloque) or [0, ""])[1])
        parrafos = [comun.limpio(x) for x in re.findall(r'(?s)<div class="et_pb_blurb_description">(.*?)</div>', bloque)]
        parrafos = [p for p in parrafos if p and p != organiza]
        f = next((fechas(p) for p in parrafos if fechas(p)), None)
        sitio = lugar(" ".join(p for p in parrafos if not fechas(p) and not re.search(r"\bTBC\b", p, re.I)))
        c = {"titulo": titulo_idbf(nombre), "original": nombre, "lugar": sitio, "anio": int(boton[1]), "organiza": "IDBF", "enlace": IDBF}
        if f: c["desde"], c["hasta"] = f
        out.append(c)
    return out


def leer_europa(pagina, base="https://paddle-europe.eu"):
    """Las pruebas de una página del calendario de Paddle Europe: el nombre, el sitio (en negrita) y las fechas («1.5.2027 - 2.5.2027»)."""
    out = []
    for b in re.findall(r'(?s)<div class="description">(.*?)</div>\s*(?:<p>.*?</p>\s*)?<a class="button', pagina):
        t = re.search(r'(?s)<h2>\s*<a href="([^"]*)">(.*?)</a>', b)
        d = re.search(r'(?s)<div class="data"><strong>(.*?)</strong><br>\s*(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{4}))?', b)
        if not t or not d: continue
        try:
            desde = dt.date(int(d[4]), int(d[3]), int(d[2])); hasta = dt.date(int(d[7]), int(d[6]), int(d[5])) if d[5] else desde
        except ValueError: continue
        enlace = t[1] if t[1].startswith("http") else None
        out.append({"titulo": comun.limpio(t[2]), "original": comun.limpio(t[2]), "lugar": lugar(html.unescape(d[1]).replace(",", ", ")),
                    "anio": desde.year, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "organiza": "Paddle Europe",
                    "enlace": enlace or base + "/calendar"})
    return out


def proximos(lista, hoy):
    """Los que no han pasado (los que aún no tienen fecha, los de este año en adelante), por orden: primero los que tienen fecha."""
    vivos = [c for c in lista if (c.get("hasta") or f"{c['anio']}-12-31") >= hoy.isoformat()]
    return sorted(vivos, key=lambda c: (c.get("desde") or f"{c['anio']}-12-31", c["titulo"]))


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = comun.leer(ruta)
    hoy = dt.datetime.now(comun.TZ).date()
    if "--siempre" not in sys.argv and x.get("dragon") and hoy.weekday() not in (0, 3):
        # los demás días solo se quita lo que ya ha pasado
        antes = x["dragon"]; quedan = proximos(antes.get("campeonatos") or [], hoy)
        if quedan != (antes.get("campeonatos") or []):
            x["dragon"] = {**antes, "campeonatos": quedan}
            x["actualizado"] = dt.datetime.now(comun.TZ).isoformat(timespec="minutes"); comun.guardar(ruta, x)
        print(json.dumps({"dragon": len(quedan), "sin_mirar": "solo lunes y jueves"}, ensure_ascii=False)); return
    try:
        idbf = leer_idbf(comun.pedir(IDBF).decode("utf-8", "replace"))
        europa = []
        for anio in (hoy.year, hoy.year + 1):
            europa += leer_europa(comun.pedir(EUROPA.format(anio)).decode("utf-8", "replace"))
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    nuevo = {"campeonatos": proximos(idbf + europa, hoy),
             "fuentes": [{"nombre": "Federación Internacional de Barco Dragón (IDBF)", "enlace": IDBF},
                         {"nombre": "Paddle Europe", "enlace": "https://paddle-europe.eu/calendar"}]}
    if x.get("dragon") != nuevo:
        x["dragon"] = nuevo
        x["actualizado"] = dt.datetime.now(comun.TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"dragon": len(nuevo["campeonatos"]), "idbf": len(idbf), "europa": len(europa)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
