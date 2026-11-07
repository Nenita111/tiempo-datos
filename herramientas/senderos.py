"""Los senderos señalizados entre Almería y Motril (4.31, lo pidió Isa el 7 nov 2026: «senderos oficiales entre Almería y Motril, con su
distancia, dificultad, duración y mapa, y el tiempo de hoy en cada uno»). De la Junta de Andalucía: la capa «senderos» de los equipamientos de
uso público de la REDIAM (WFS REDIAM_WFS_Patrimonio_Natural, ms:senderos, con su trazado; CC BY 4.0), su punto de inicio (la capa
ms:equipamientos_uso_publico, por su código) y la ficha de cada uno en la Ventana del Visitante (municipios, trazado, distancia, duración y
si está cerrado). Solo los senderos a pie (los carriles cicloturistas, no) de menos de 30 km (la Sulayr, de 279, no). El municipio del
inicio da el código INE con el que la tele pide a AEMET el tiempo de hoy de cada uno (Senderos.kt) — de la relación de municipios del INE a
1 de enero de 2026 (municipios_ine_almeria_granada.json). Se pide una vez a la semana (el lunes, o si no hay); los robots.txt de la Junta no
cierran esas rutas.

  python3 -I herramientas/senderos.py extras.json [--ya]

Imprime una línea JSON: {"senderos": N, ...} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, html, json, math, os, re, sys, time
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun
from agenda_junta import utm30_a_latlon

TZ = ZoneInfo("Europe/Madrid")
WFS = "https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_WFS_Patrimonio_Natural"
CAJA = "36.60,-3.60,37.10,-2.40"            # lat, lon (EPSG:4326, orden de ejes de la norma)
ADRA = (36.7480, -3.0213)
MAX_M = 30000
TOLERANCIA = 0.0004                          # unos 40 m: el trazado simplificado para el mapa de la tele
FUENTE = "Junta de Andalucía (REDIAM y Ventana del Visitante)"


def wfs(capa, pedir=comun.pedir):
    u = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature&typenames={capa}&outputFormat=application/json;%20subtype=geojson"
         f"&srsName=EPSG:4326&bbox={CAJA},urn:ogc:def:crs:EPSG::4326")
    return json.loads(pedir(u, timeout=120))


def km(a, b):
    return math.hypot((a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110.57)


def simplificar(p, tol=TOLERANCIA):
    """Douglas-Peucker sobre lon/lat (con la longitud acortada por el coseno de la latitud)."""
    if len(p) < 3: return p
    c = math.cos(math.radians(p[0][1]))
    def dist(q, a, b):
        ax, ay, bx, by, qx, qy = a[0] * c, a[1], b[0] * c, b[1], q[0] * c, q[1]
        dx, dy = bx - ax, by - ay
        if dx == dy == 0: return math.hypot(qx - ax, qy - ay)
        t = max(0, min(1, ((qx - ax) * dx + (qy - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(qx - ax - t * dx, qy - ay - t * dy)
    keep, pila = {0, len(p) - 1}, [(0, len(p) - 1)]
    while pila:
        i, j = pila.pop()
        k, d = max(((k, dist(p[k], p[i], p[j])) for k in range(i + 1, j)), key=lambda x: x[1], default=(None, 0))
        if k is not None and d > tol: keep.add(k); pila += [(i, k), (k, j)]
    return [p[i] for i in sorted(keep)]


def partes(g):
    if not g: return []
    return [g["coordinates"]] if g["type"] == "LineString" else list(g["coordinates"]) if g["type"] == "MultiLineString" else []


def ficha(pag):
    """Lo de la ficha de la Ventana del Visitante: nombre, municipios, trazado, distancia (m), duración y si está cerrado."""
    s = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", " ", pag, flags=re.S)
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", "\n", s)).split())
    f = {}
    m = re.search(r'og:title" content="([^"]+?) - Ventana del Visitante', pag)
    if m and not m.group(1).lower().startswith("detalle buscador"): f["nombre"] = html.unescape(m.group(1)).strip()   # (si no la encuentra, la genérica)
    m = re.search(r"Municipios (.+?) (?:Trazado|Distancia|Duración|Dificultad)\b", t)
    if m: f["municipios"] = [x.strip() for x in re.split(r",\s*|\s+y\s+", m.group(1)) if x.strip()]
    m = re.search(r"Trazado (\w+)", t)
    if m: f["trazado"] = m.group(1).lower()
    m = re.search(r"Distancia ida \(metros\) ([\d.]+)", t)
    if m: f["metros"] = int(m.group(1).replace(".", ""))
    m = re.search(r"Duración (.+?) (?:Dificultad|MAPA|CÓMO)", t)
    if m: f["duracion"] = m.group(1).strip()
    f["cerrado"] = "CERRADO TEMPORALMENTE" in t
    return f


def plano(s):
    """«Ejido (el)» y «Ejido, El» → «el ejido»; sin tildes."""
    t = comun.sin_tildes(s).strip()
    m = re.match(r"^(.*?)\s*(?:\((el|la|los|las)\)|,\s*(el|la|los|las))$", t)
    return f"{m.group(2) or m.group(3)} {m.group(1)}".strip() if m else t


def codigos():
    """{nombre plano: (código INE, nombre oficial con el artículo delante)}."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "municipios_ine_almeria_granada.json")
    oficial = lambda n: (lambda m: f"{m.group(2)} {m.group(1)}" if m else n)(re.match(r"^(.*), (El|La|Los|Las)$", n))
    return {plano(n): (c, oficial(n)) for n, c in comun.leer(p)["municipios"]}


def con_tildes(t, ine):
    """Las tildes que no trae la capa, en los nombres de municipio y en «Río»."""
    nom = {comun.sin_tildes(n).lower(): n for _, n in ine.values() if " " not in n}
    return " ".join(nom.get(w.lower(), "Río" if w.lower() == "rio" else w) for w in t.split())


def titulo(n):
    """«TREVELEZ - SIETE LAGUNAS» (la capa no lleva tildes) → «Trevelez - Siete Lagunas»; la ficha, si la hay, manda."""
    pal = n.lower().split()
    return " ".join(w if (i and w in ("de", "del", "la", "las", "el", "los", "y")) else w[:1].upper() + w[1:] for i, w in enumerate(pal))


def senderos(capa, inicios, fichas, ine):
    ini = {}
    for f in inicios.get("features") or []:
        p = f.get("properties") or {}
        if "SENDERO" in (p.get("TIPOEQUIPA") or "").upper():
            try: ini[str(p.get("CODIGOEQUI"))] = utm30_a_latlon(float(p["coor_X"]), float(p["coor_Y"]))
            except (KeyError, TypeError, ValueError): pass
    res = []
    for f in capa.get("features") or []:
        p = f.get("properties") or {}
        if "sendero" not in (p.get("modalidad") or "").lower(): continue
        try: largo = float(p.get("longitud") or 0)
        except ValueError: largo = 0
        if not largo or largo > MAX_M: continue
        cod = str(p.get("codigoequi"))
        tr = [simplificar([[round(x, 5), round(y, 5)] for x, y, *_ in q]) for q in partes(f.get("geometry")) if len(q) > 1]
        if not tr: continue
        a = ini.get(cod) or (tr[0][0][1], tr[0][0][0])
        fi = fichas.get(cod) or {}
        s = {"id": cod, "nombre": fi.get("nombre") and titulo(fi["nombre"]) or titulo(p.get("nombre") or ""), "dificultad": (p.get("t_dificult") or "").lower(),
             "km": round((fi.get("metros") or largo) / 1000, 1), "inicio": [round(a[0], 5), round(a[1], 5)], "traza": tr,
             "adraKm": round(km(ADRA, a)), "ficha": p.get("FICHA_VV")}
        for k in ("duracion", "trazado", "municipios"):
            if fi.get(k): s[k] = fi[k]
        if fi.get("cerrado"): s["cerrado"] = True
        mu = (fi.get("municipios") or [None])[0]
        if mu and ine.get(plano(mu)): s["ine"], s["tiempoDe"] = ine[plano(mu)]
        if not fi.get("nombre"): s["nombre"] = con_tildes(s["nombre"], ine)
        res.append(s)
    # sin municipio en la ficha: el que se nombre en el sendero («Trevélez - Siete Lagunas») o el del sendero más cercano (a 8 km o menos)
    for s in res:
        if "ine" in s: continue
        en = [v for k, v in ine.items() if " " not in k and re.search(r"\b" + re.escape(k) + r"\b", comun.sin_tildes(s["nombre"]).lower())]
        if en: s["ine"], s["tiempoDe"] = en[0]; continue
        cerca = min((t for t in res if t.get("ine") and t is not s), key=lambda t: km(t["inicio"], s["inicio"]), default=None)
        if cerca and km(cerca["inicio"], s["inicio"]) <= 8: s["ine"], s["tiempoDe"] = cerca["ine"], cerca["tiempoDe"]
    return sorted(res, key=lambda s: (s["adraKm"], s["nombre"]))


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    viejo = x.get("senderos") or {}
    if "--ya" not in sys.argv and viejo.get("lista") and hoy.weekday() != 0 and viejo.get("dia", "") > (hoy - dt.timedelta(days=8)).isoformat():
        print(json.dumps({"senderos": len(viejo["lista"]), "dia": viejo.get("dia")}, ensure_ascii=False)); return
    fallos = []
    try:
        capa = wfs("ms:senderos"); time.sleep(1)
        try: inicios = wfs("ms:equipamientos_uso_publico")
        except Exception as e: inicios = {}; fallos.append(f"inicios: {str(e)[:60]}")
        fichas = {}
        for f in capa.get("features") or []:
            p = f.get("properties") or {}
            if "sendero" not in (p.get("modalidad") or "").lower() or not p.get("FICHA_VV"): continue
            try:
                if float(p.get("longitud") or 0) > MAX_M: continue
                time.sleep(1); fichas[str(p.get("codigoequi"))] = ficha(comun.pedir(p["FICHA_VV"], timeout=60).decode("utf-8", "replace"))
            except Exception as e: fallos.append(f"{p.get('codigoequi')}: {str(e)[:50]}")
        lista = senderos(capa, inicios, fichas, codigos())
        if not lista: raise ValueError("ningún sendero")
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    nuevo = {"lista": lista, "fuente": FUENTE, "enlace": "https://www.juntadeandalucia.es/medioambiente/portal/web/ventanadelvisitante"}
    v = dict(viejo); v.pop("dia", None)
    x["senderos"] = dict(nuevo, dia=hoy.isoformat())
    if v != nuevo: x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    comun.guardar(ruta, x)
    print(json.dumps({"senderos": len(lista), "sinIne": [s["id"] for s in lista if "ine" not in s], "cerrados": sum(1 for s in lista if s.get("cerrado")),
                      "fallos": fallos[:3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
