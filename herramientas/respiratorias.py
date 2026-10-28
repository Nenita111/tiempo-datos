"""Gripe, COVID-19 y virus respiratorio sincitial (VRS) en Andalucía (pantalla Casa de la tele): lo saca del «Resumen» del último
informe semanal oficial de vigilancia de la infección respiratoria aguda en Andalucía (red centinela de la Consejería de Sanidad,
Presidencia y Emergencias de la Junta de Andalucía). Las cifras, tal cual las da el informe; nada calculado.

  python3 respiratorias.py extras.json

Guarda en extras.json «respiratorias»: {semana, desde, hasta, iras, gripal, covid, bronquiolitis, positividad, irag, enlace, pagina,
fuente}; cada tasa es {"tasa", "previa"} en casos por 100.000 habitantes. Si no hay informe nuevo, deja el que había.
Necesita pdftotext (poppler).
"""
import datetime as dt, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
BASE = "https://www.juntadeandalucia.es/organismos/presidenciasanidadyemergencias/areas/sanidad/salud-vida/vigilancia/paginas/"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
UA = {"User-Agent": "TiempoYRadar/1.0"}


def bajar(u):
    """El servidor de la Junta corta a veces la conexión: hasta 3 intentos, con una pausa."""
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read()
        except (ConnectionError, urllib.error.URLError) as e:
            if i == 2 or getattr(e, "code", None) in (403, 404): raise
            time.sleep(5 * (i + 1))


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", "-l", "4", p, "-"], capture_output=True, text=True, check=True).stdout


def temporada(hoy):
    """La temporada de vigilancia va de la semana 40 a la 39 del año siguiente: «2627» del otoño de 2026 al de 2027."""
    y = hoy.year if hoy.month >= 10 else hoy.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def informes(html, pagina):
    """Los informes de la página de la temporada: [(semana «42/2026», texto del enlace, url)], el más nuevo primero."""
    res = []
    for href, txt in re.findall(r'<a [^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"&nbsp;|\s+", " ", re.sub(r"<[^>]+>", "", txt)).strip()
        m = re.match(r"Semana (\d{1,2})/(\d{4})", t)
        if m: res.append((int(m.group(2)), int(m.group(1)), t, urllib.parse.urljoin(pagina, href)))
    return [(f"{s}/{y}", t, u) for y, s, t, u in sorted(res, reverse=True)]


def num(s):
    return float(s.replace(".", "").replace(",", "."))


def resumen(t):
    """Las cifras del «Resumen» del informe."""
    r = re.sub(r"\s+", " ", t)
    i = r.find("Resumen Vigilancia")
    if i < 0: i = r.find("Vigilancia de IRA en Atención Primaria")
    if i < 0: raise ValueError("informe sin resumen")
    r = r[i:i + 6000].replace("- ", "")   # palabras partidas al final de la línea («ca- sos»)
    o = {}
    sem = re.search(r"En la semana (\d{1,2}/\d{4})", r)
    if not sem: raise ValueError("resumen sin semana")
    o["semana"] = sem.group(1)
    N = r"(\d+(?:[.,]\d+)?)"

    def tasa(patron, clave):
        m = re.search(patron, r)
        if m: o[clave] = {"tasa": num(m.group(1)), "previa": num(m.group(2))}

    tasa(r"tasa de incidencia de IRAs en Andalucía ha sido de " + N + r" casos/100\.000 ?h \(" + N, "iras")
    tasa(r"tasa de síndrome gripal es de " + N + r" casos/100\.000 ?h \(" + N, "gripal")
    tasa(r"la de COVID-19 \(síndrome\) de " + N + r" casos/100\.000 ?h \(" + N, "covid")
    tasa(r"bronquitis y bronquiolitis en menores de 5 años de " + N + r" casos/100\.000 ?h \(" + N, "bronquiolitis")
    tasa(r"tasa de IRAG en Andalucía se sitúa en " + N + r" casos/100\.000 ?h \(" + N, "irag")
    m = re.search(r"porcentaje de positividad ha sido de " + N + r" ?% para gripe \(" + N + r" ?%[^)]*\), " + N + r" ?% para SARS-Co[Vv]-?2 \(" + N
                  + r" ?%[^)]*\),? (?:y )?" + N + r" ?% para VRS \(" + N, r)
    if m:
        v = [num(x) for x in m.groups()]
        o["positividad"] = {"gripe": v[0], "gripePrevia": v[1], "covid": v[2], "covidPrevia": v[3], "vrs": v[4], "vrsPrevia": v[5]}
    if "iras" not in o: raise ValueError("resumen sin la tasa de IRAs")
    return o


def fechas(texto_enlace):
    """«Semana 42/2026 (del 12 al 18 de octubre de 2026)» → («2026-10-12», «2026-10-18»)."""
    t = texto_enlace.replace("\xa0", " ")
    m = re.search(r"del (\d{1,2})(?: de (\w+)(?: de (\d{4}))?)? al (\d{1,2}) de (\w+) de (\d{4})", t)
    if not m: return None, None
    d1, m1, y1, d2, m2, y2 = m.groups()
    mes2 = MESES.index(m2.lower()) + 1
    mes1 = MESES.index(m1.lower()) + 1 if m1 else mes2
    a1 = int(y1) if y1 else (int(y2) - 1 if mes1 > mes2 else int(y2))
    return dt.date(a1, mes1, int(d1)).isoformat(), dt.date(int(y2), mes2, int(d2)).isoformat()


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    with open(ruta, encoding="utf-8") as f: x = json.load(f)
    viejo = x.get("respiratorias") or {}
    pagina = BASE + f"temporada{temporada(dt.datetime.now(TZ).date())}.html"
    try:
        lista = informes(bajar(pagina).decode("utf-8", "replace"), pagina)
        if not lista: raise ValueError("la página de la temporada no tiene informes")
        semana, txt, url = lista[0]
        if viejo.get("semana") == semana and viejo.get("enlace") == url:
            print(json.dumps({"semana": semana, "nuevo": False}, ensure_ascii=False)); return
        o = resumen(texto_pdf(bajar(url)))
        if o["semana"] != semana: raise ValueError(f"el informe dice la semana {o['semana']} y el enlace la {semana}")
        o["desde"], o["hasta"] = fechas(txt)
        o.update({"enlace": url, "pagina": pagina, "fuente": "Junta de Andalucía (vigilancia centinela de la infección respiratoria aguda)"})
    except Exception as e:
        print(json.dumps({"fallo": str(e)}, ensure_ascii=False)); sys.exit(2)
    x["respiratorias"] = o
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    with open(ruta, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    print(json.dumps({"semana": o["semana"], "nuevo": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
