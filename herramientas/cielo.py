"""Calendario del cielo para la tele (pantalla Espacio): lo saca de la Agenda astronómica oficial del Instituto Geográfico
Nacional (inicio de las estaciones, eclipses visibles en España, cambio de hora) y de la tabla de las principales lluvias de
meteoros del Observatorio Astronómico Nacional (su fecha de máximo es aproximada: puede variar un día de un año a otro).

  python3 cielo.py extras.json        (este año y el siguiente, si el IGN ya ha publicado su agenda)

Guarda en extras.json «cielo»: {"eventos": [{fecha, hora?, tipo, titulo, detalle, enlace}], "fuente": …}. Solo lo que está por
venir. Necesita pdftotext (poppler). Si no puede bajar una agenda, usa la copia del PDF oficial de herramientas/muestras;
si tampoco la hay, deja lo que había de ese año.
"""
import datetime as dt, json, os, re, subprocess, sys, tempfile, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # comun.py, al lado (con -I no se mira la carpeta del script)
import comun

TZ = ZoneInfo("Europe/Madrid")
AGENDA = "https://astronomia.ign.es/o/main-theme/images/webAstro/paginas/documentos/Agendas_Astronomicas/Agenda_astronomica_{}.pdf"
LLUVIAS_URL = "https://astronomia.ign.es/web/guest/lluvias-de-meteoros"
ECLIPSES_URL = "https://eclipses.ign.es/"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MES_RE = "(" + "|".join(MESES + ["setiembre"]) + ")"
# Tabla «Principales lluvias de meteoros» del Observatorio Astronómico Nacional (IGN), copiada de su web:
# nombre, día y mes del máximo, visibilidad (desde, hasta) y ritmo cenital habitual por hora.
LLUVIAS = [("Cuadrántidas", 3, 1, "28 dic", "12 ene", 80), ("Líridas", 22, 4, "14 abr", "30 abr", 18),
           ("Eta Acuáridas", 6, 5, "19 abr", "28 may", 50), ("Delta Acuáridas", 31, 7, "12 jul", "23 ago", 25),
           ("Perseidas", 13, 8, "17 jul", "24 ago", 100), ("Dracónidas", 9, 10, "6 oct", "10 oct", 5),
           ("Oriónidas", 21, 10, "2 oct", "7 nov", 20), ("Leónidas", 17, 11, "6 nov", "30 nov", 15),
           ("Gemínidas", 14, 12, "4 dic", "20 dic", 150), ("Úrsidas", 22, 12, "17 dic", "26 dic", 10)]


def mes(n):
    return 9 if n == "setiembre" else MESES.index(n) + 1


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", p, "-"], capture_output=True, text=True, check=True).stdout


def estaciones(t, año, url):
    res = []
    for nombre, dia, m, h, mi in re.findall(r"Inicio de(?:l| la) (primavera|verano|otoño|invierno):\s*(\d{1,2}) de " + MES_RE + r"\s+(\d{1,2})h\s*(\d{1,2})m", t):
        res.append({"fecha": dt.date(año, mes(m), int(dia)).isoformat(), "hora": f"{int(h):02d}:{int(mi):02d}", "tipo": "estacion",
                    "titulo": f"Empieza {'la' if nombre == 'primavera' else 'el'} {nombre}", "detalle": "", "enlace": url})
    return res


def eclipses(t, año, url):
    """Los eclipses de la agenda que el IGN dice visibles en España, con su frase."""
    t1 = re.sub(r"\s+", " ", t)
    notas = {}
    for m in re.finditer(r"(?:El eclipse [\w ]+? del|y el del) (\d{1,2}) de " + MES_RE + r" (?:será|se verá) visible (.*?)(?= y el del |\.)", t1):
        notas[(int(m.group(1)), mes(m.group(2)))] = m.group(3).strip()
    res = []
    for m in re.finditer(r"(\d{1,2}) de " + MES_RE + r" Eclipse (total|anular|parcial|penumbral|híbrido) de (Sol|Luna)", t1):
        dia, mm, clase, astro = int(m.group(1)), mes(m.group(2)), m.group(3), m.group(4)
        nota = notas.get((dia, mm))
        if not nota or "España" not in nota and "Península" not in nota and "península" not in nota: continue
        res.append({"fecha": dt.date(año, mm, dia).isoformat(), "tipo": "eclipse", "titulo": f"Eclipse {clase} de {astro}",
                    "detalle": "Visible " + nota, "enlace": ECLIPSES_URL if astro == "Sol" else url})
    return res


def cambio_hora(t, año, url):
    t1 = re.sub(r"\s+", " ", t)
    res = []
    a = re.search(r"horario adelantado se iniciará a las (\d)h .*? del domingo (\d{1,2}) de " + MES_RE, t1)
    b = re.search(r"durará hasta las (\d)h .*? del domingo (\d{1,2}) de " + MES_RE, t1)
    if a: res.append({"fecha": dt.date(año, mes(a.group(3)), int(a.group(2))).isoformat(), "tipo": "hora", "titulo": "Cambio de hora",
                      "detalle": f"A las {a.group(1)} de la madrugada serán las {int(a.group(1)) + 1}: una hora menos de sueño", "enlace": url})
    if b: res.append({"fecha": dt.date(año, mes(b.group(3)), int(b.group(2))).isoformat(), "tipo": "hora", "titulo": "Cambio de hora",
                      "detalle": f"A las {b.group(1)} de la madrugada serán las {int(b.group(1)) - 1}: una hora más", "enlace": url})
    return res


def lluvias(año):
    return [{"fecha": dt.date(año, m, d).isoformat(), "tipo": "meteoros", "titulo": f"Máximo de las {n}",
             "detalle": f"Hasta {r} meteoros por hora en condiciones ideales · visibles del {a} al {b} · fecha aproximada (OAN)", "enlace": LLUVIAS_URL}
            for n, d, m, a, b, r in LLUVIAS]


def agenda(año, bajar=None):
    url = AGENDA.format(año)
    t = texto_pdf((bajar or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "TiempoYRadar/1.0"}), timeout=60).read()))(url))
    if "Agenda Astron" not in t: raise IOError(f"No es la agenda astronómica de {año}")
    return estaciones(t, año, url) + eclipses(t, año, url) + cambio_hora(t, año, url)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    with open(ruta, encoding="utf-8") as f: x = json.load(f)
    hoy = dt.datetime.now(TZ).date()
    viejos = (x.get("cielo") or {}).get("eventos", [])
    eventos, fallos = [], []
    for año in (hoy.year, hoy.year + 1):
        copia = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras", f"agenda_{año}.pdf")
        try:
            eventos += agenda(año)
        except Exception as e:
            if os.path.exists(copia):   # la copia del PDF oficial que hay en el repositorio
                with open(copia, "rb") as f: datos = f.read()
                eventos += agenda(año, bajar=lambda u: datos)
            else:
                fallos.append(f"{año}: {e}")
                eventos += [v for v in viejos if v["fecha"].startswith(str(año)) and v["tipo"] != "meteoros"]
        eventos += lluvias(año)
    eventos = sorted({(e["fecha"], e["titulo"]): e for e in eventos if e["fecha"] >= hoy.isoformat()}.values(), key=lambda e: (e["fecha"], e.get("hora", "")))
    x["cielo"] = {"eventos": eventos, "fuente": "Instituto Geográfico Nacional · Observatorio Astronómico Nacional"}
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    comun.guardar(ruta, x)
    print(json.dumps({"eventos": len(eventos), "fallos": fallos}, ensure_ascii=False))


if __name__ == "__main__":
    main()
