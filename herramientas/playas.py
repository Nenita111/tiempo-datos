"""Calidad sanitaria de las playas de Adra (4.26, lo pidió Isa el 5 nov 2026): los informes de la Junta de Andalucía (Consejería de Sanidad,
«Zonas de baño»: un PDF por provincia cada quince días del 1 de junio al 30 de septiembre, maritimas_almeria_AAAAMMDD.pdf). De cada zona de
baño de Adra: su calificación anual, y de cada inspección de la temporada, la fecha, la valoración para el baño, el comunicado y las
observaciones (las incidencias). Se guarda en extras.json («playas»); fuera de temporada queda la última.

  python3 -I herramientas/playas.py extras.json

Imprime una línea JSON: {"playas": N, "informes": N, "ultimo": "2026-09-30"} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, json, os, re, subprocess, sys, tempfile
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
PAGINA = "https://www.juntadeandalucia.es/organismos/saludyconsumo/areas/entornos-saludables/salud-ambiental/paginas/zonas-bano.html"
PROVINCIA, MUNICIPIO = "almeria", "ADRA"


def informes(html, anio):
    """Los PDF de la provincia del año, por fecha (si hay dos del mismo día, el último enlace)."""
    res = {}
    for u in re.findall(r'href="([^"]*maritimas_' + PROVINCIA + r'_(\d{8})[^"]*\.pdf)"', html, re.I):
        url, f = u
        if f.startswith(str(anio)):
            res[f] = url if url.startswith("http") else "https://www.juntadeandalucia.es" + url.strip()
    return [(dt.date(int(f[:4]), int(f[4:6]), int(f[6:])), res[f]) for f in sorted(res)]


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, check=True).stdout


def leer(texto, municipio=MUNICIPIO):
    """Cada fila del municipio: provincia, municipio, zona de baño, punto de muestreo, calificación anual, fecha de inspección (dd/mm/aaaa),
    valoración para el baño, comunicado y observaciones, en columnas separadas por dos o más espacios. Lo que no se lee, no se apunta."""
    filas = []
    for linea in texto.splitlines():
        c = []
        for x in (x.strip() for x in re.split(r"\s{2,}", linea.strip()) if x.strip()):
            m = re.fullmatch(r"(\d{2}/\d{2}/\d{4})\s+(.+)", x)          # la fecha pegada a la valoración (algunos informes)
            c += [m.group(1), m.group(2)] if m else [x]
        c = [x for x in c if not re.fullmatch(r"(?i)zonas de ba\S+ mar\S+", x)]   # la columna del tipo de zona (algún informe)
        if len(c) < 7 or comun.sin_tildes(c[1]).upper() != comun.sin_tildes(municipio).upper(): continue
        i = next((k for k, x in enumerate(c) if re.fullmatch(r"\d{2}/\d{2}/\d{4}", x)), None)
        if i is None or i < 4: continue
        d, m, a = c[i].split("/")
        f = {"zona": c[2], "punto": c[3] if i >= 5 else "", "calificacion": c[i - 1], "fecha": f"{a}-{m}-{d}",
             "valoracion": c[i + 1] if len(c) > i + 1 else "", "comunicado": c[i + 2] if len(c) > i + 2 else ""}
        if len(c) > i + 3: f["observaciones"] = " ".join(c[i + 3:])
        filas.append(f)
    return filas


def nombre(z):
    z = re.sub(r"^PLAYA\s+(DE\s+)?", "", z.strip(), flags=re.I)
    w = z.lower().split()
    return " ".join(x if i and x in ("de", "del", "la", "las", "el", "los") else x.capitalize() for i, x in enumerate(w))


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    try:
        html = comun.pedir(PAGINA).decode("utf-8", "replace")
        lista = informes(html, hoy.year) or informes(html, hoy.year - 1)
        if not lista: raise ValueError(f"sin informes de {PROVINCIA} en {PAGINA}")
        zonas = {}
        for fecha, url in lista:
            for f in leer(texto_pdf(comun.pedir(url))):
                z = zonas.setdefault(f["zona"], {"nombre": nombre(f["zona"]), "calificacion": f["calificacion"], "inspecciones": {}})
                z["calificacion"] = f["calificacion"] or z["calificacion"]
                ins = {k: f[k] for k in ("valoracion", "comunicado", "observaciones") if f.get(k)}
                # un punto de muestreo con incidencia manda sobre otro de la misma zona y día
                prev = z["inspecciones"].get(f["fecha"])
                if not prev or "no apta" in ins.get("valoracion", "").lower() or ins.get("observaciones"):
                    z["inspecciones"][f["fecha"]] = dict(ins, fecha=f["fecha"])
        if not zonas: raise ValueError(f"ningún informe trae las zonas de baño de {MUNICIPIO}")
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    playas = [{"nombre": z["nombre"], "calificacion": z["calificacion"], "inspecciones": [z["inspecciones"][k] for k in sorted(z["inspecciones"])]}
              for z in sorted(zonas.values(), key=lambda z: z["nombre"])]
    nuevo = {"temporada": lista[-1][0].year, "playas": playas, "informes": [f.isoformat() for f, _ in lista], "pdf": lista[-1][1],
             "url": PAGINA, "fuente": "Junta de Andalucía (Consejería de Sanidad)"}
    if x.get("playas") != nuevo:
        x["playas"] = nuevo
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"playas": len(playas), "informes": len(lista), "ultimo": lista[-1][0].isoformat()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
