"""Agenda cultural de la Junta de Andalucía cerca de Adra (4.27, lo pidió Isa el 5 nov 2026: «agenda cultural de Andalucía: conciertos,
exposiciones, teatro, actividades culturales, conferencias y eventos públicos; filtrar por Adra, Almería y municipios cercanos»). Del
conjunto de datos abiertos «Agenda de eventos organizados por la Junta de Andalucía» (CC BY 4.0, se pone al día cada día; JSON en
datos.juntadeandalucia.es/api/v0/schedule/all?format=json, que lleva al fichero dataset-agenda.json). Se quedan los que no han acabado
y están a 60 km o menos de Adra (sus coordenadas vienen en UTM 30N, ETRS89; si no las traen, las de la capital de su municipio, de
municipios_almeria.json: INE e IGN, Nomenclátor Geográfico Básico; los de fuera de la provincia sin coordenadas, no). Se guarda en extras.json («agendaJunta»).

  python3 -I herramientas/agenda_junta.py extras.json

Imprime una línea JSON: {"agendaJunta": N, "total": M} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, html, json, math, os, re, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
URL = "https://datos.juntadeandalucia.es/api/v0/schedule/all?format=json"
FICHA = "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/agenda-de-eventos-organizados-por-la-junta-de-andalucia"
ADRA = (36.7480, -3.0213)
RADIO_KM = 60


def utm30_a_latlon(x, y):
    """UTM huso 30 norte (ETRS89/GRS80) → latitud y longitud en grados (fórmulas de la USGS, Snyder 1987)."""
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f); ep2 = e2 / (1 - e2); k0 = 0.9996
    x -= 500000.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) \
        + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)
    c1 = ep2 * math.cos(p1) ** 2; t1 = math.tan(p1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2); r1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = p1 - (n1 * math.tan(p1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                           + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(p1)
    return math.degrees(lat), -3.0 + math.degrees(lon)


def sin_tildes(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def municipios():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "municipios_almeria.json")
    return {sin_tildes(m[0]): (m[2], m[3]) for m in json.load(open(p, encoding="utf-8"))["municipios"]}


def km(a, b):
    return math.hypot((a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110.57)


def texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def leer(eventos, hoy, munis=None):
    munis = munis if munis is not None else municipios()
    res = []
    for e in eventos:
        fechas = [(r.get("start_date_registration"), r.get("end_date_registration")) for r in (e.get("date_registration") or []) if r]
        fechas = [(a, b or a) for a, b in fechas if a]
        if not fechas: continue
        desde, hasta = min(a for a, _ in fechas), max(b for _, b in fechas)
        if hasta < hoy.isoformat(): continue
        c = next((p for p in (e.get("coordinates") or []) if p and p.get("longitude") and p.get("latitude")), None)
        try: la, lo = utm30_a_latlon(float(c["longitude"]), float(c["latitude"])) if c else munis[sin_tildes(e.get("location"))]
        except (TypeError, ValueError, KeyError): continue
        d = km(ADRA, (la, lo))
        if d > RADIO_KM: continue
        hor = e.get("schedule")
        ev = {"titulo": texto(e.get("title")), "fecha": desde, "lugar": texto(e.get("location")), "km": round(d), "fuente": "Junta de Andalucía",
              "enlace": FICHA}
        if hasta != desde: ev["hasta"] = hasta
        if isinstance(hor, str) and texto(hor): ev["horario"] = texto(hor)[:80]
        if e.get("cost"): ev["precio"] = texto(e.get("cost"))[:40]
        temas = [t.get("themes") for t in (e.get("themes") or []) if t and t.get("themes")]
        if temas: ev["tema"] = temas[0]
        if ev["titulo"]: res.append(ev)
    return sorted(res, key=lambda v: (v["fecha"], v["titulo"]))


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    try:
        L = json.loads(comun.pedir(URL, timeout=120).decode("utf-8"))
        if not isinstance(L, list) or not L: raise ValueError("la agenda de la Junta ha llegado vacía")
        cerca = leer(L, hoy)
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    if x.get("agendaJunta") != cerca:
        x["agendaJunta"] = cerca
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"agendaJunta": len(cerca), "total": len(L)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
