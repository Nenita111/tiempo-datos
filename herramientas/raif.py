"""Plagas destacadas en los cultivos de invernadero de Almería esta semana (pantalla Precios de la tele): lo saca de los informes
semanales oficiales de la Red de Alerta e Información Fitosanitaria de Andalucía (RAIF, Junta de Andalucía), provincia de Almería,
«Informe Especial Interés» de cada cultivo: las fechas del boletín y sus «Agentes más destacados», tal cual.

  python3 raif.py extras.json

Guarda en extras.json «raif»: {"provincia", "cultivos": [{cultivo, desde, hasta, destacados, enlace}], "pagina", "fuente"}.
Si no puede leer un cultivo, deja el que había. Necesita pdftotext (poppler).
"""
import datetime as dt, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
PAGINA = "https://www.juntadeandalucia.es/agriculturapescaaguaydesarrollorural/raif/boletin-provincial/informe-semanal/informe-semanal-almeria/"
# los cultivos de invernadero de la comarca, en este orden
CULTIVOS = ["Tomate", "Pimiento", "Pepino", "Calabacín", "Berenjena", "Sandía"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
UA = {"User-Agent": "TiempoYRadar/1.0"}


def bajar(u):
    """El servidor de la Junta corta a veces la conexión: hasta 3 intentos, con una pausa."""
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()
        except (ConnectionError, urllib.error.URLError) as e:
            if i == 2 or getattr(e, "code", None) in (403, 404): raise
            time.sleep(5 * (i + 1))


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, check=True).stdout


def enlaces(html):
    """Enlace al informe de cada cultivo de la página de la provincia («Informe Especial Interés Tomate» → su PDF)."""
    res = {}
    # cada informe es un bloque con el título en <h5> y un enlace «full-link» vacío detrás
    for txt, href in re.findall(r"<h5>(.*?)</h5>\s*</div>\s*<a [^>]*href=\"([^\"]+\.pdf)\"", html, re.S):
        t = re.sub(r"<[^>]+>|\s+", " ", txt).strip()
        m = re.match(r"Informe Especial Inter[eé]s\s+(.+)$", t)
        if m: res[m.group(1).strip()] = urllib.parse.urljoin(PAGINA, href)
    return res


def boletin(t):
    """Fechas y agentes destacados de un boletín de cultivo: («2026-10-19», «2026-10-23», «Mosca blanca y trips»)."""
    t1 = re.sub(r"[ \t]+", " ", t)
    m = re.search(r"Del (\d{1,2})(?: de (\w+))? al (\d{1,2}) de (\w+)\s*(?:de\s*)?/?\s*(\d{4})", t1)
    if not m: raise ValueError("boletín sin fechas")
    d1, m1, d2, m2, y = m.groups()
    mes2 = MESES.index(m2.lower()) + 1
    mes1 = MESES.index(m1.lower()) + 1 if m1 else mes2
    y1 = int(y) - 1 if mes1 > mes2 else int(y)
    desde, hasta = dt.date(y1, mes1, int(d1)), dt.date(int(y), mes2, int(d2))
    lineas = [l.strip() for l in t.splitlines()]
    i = next((k for k, l in enumerate(lineas) if re.match(r"Agentes m[aá]s destacados:", l)), None)
    if i is None: raise ValueError("boletín sin agentes destacados")
    destacados = re.sub(r"^Agentes m[aá]s destacados:\s*", "", lineas[i])
    # en la maqueta, a veces el texto de la derecha cae en la misma línea («… Boletín Fitosanitario»): fuera
    destacados = re.split(r"\s{2,}|Bolet[ií]n Fitosanitario", destacados)[0].strip().rstrip(".")
    if not destacados:   # a veces la lista queda en la línea de encima o de debajo
        cabecera = re.compile(r"^(ASPECTOS GENERALES|Bolet[ií]n|Del \d|/?\d{4}$|PROVINCIA|RAIF|Red de Alerta|Fitosanitaria)", re.I)
        for k in (i - 1, i + 1, i - 2, i + 2):
            if 0 <= k < len(lineas) and lineas[k] and not cabecera.match(lineas[k]):
                destacados = re.split(r"\s{2,}", lineas[k])[-1].strip().rstrip("."); break
    if not destacados: raise ValueError("agentes destacados vacíos")
    return desde.isoformat(), hasta.isoformat(), destacados[0].upper() + destacados[1:].lower() if destacados.isupper() else destacados


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    with open(ruta, encoding="utf-8") as f: x = json.load(f)
    viejos = {c["cultivo"]: c for c in (x.get("raif") or {}).get("cultivos", [])}
    fallos = []
    try:
        ligas = enlaces(bajar(PAGINA).decode("utf-8", "replace"))
    except Exception as e:
        ligas, fallos = {}, [f"página: {e}"]
    cultivos = []
    for c in CULTIVOS:
        u = ligas.get(c)
        try:
            if not u: raise ValueError("sin enlace en la página")
            desde, hasta, dest = boletin(texto_pdf(bajar(u)))
            cultivos.append({"cultivo": c, "desde": desde, "hasta": hasta, "destacados": dest, "enlace": u})
        except Exception as e:
            fallos.append(f"{c}: {e}")
            if c in viejos: cultivos.append(viejos[c])
    if cultivos:
        x["raif"] = {"provincia": "Almería", "cultivos": cultivos, "pagina": PAGINA,
                     "fuente": "Red de Alerta e Información Fitosanitaria de Andalucía (RAIF, Junta de Andalucía)"}
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        with open(ruta, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    print(json.dumps({"cultivos": len(cultivos), "fallos": fallos}, ensure_ascii=False))
    if not cultivos: sys.exit(2)


if __name__ == "__main__":
    main()
