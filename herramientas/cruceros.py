"""Cruceros previstos en el puerto de Almería (335, lo pidió Isa el 2 nov 2026): la relación oficial de la Autoridad Portuaria de Almería
(apalmeria.com/pasajeros/cruceros/, «Cruceros AAAA (pdf)»: un PDF de Excel con fecha, horas, barco, naviera, muelle, pasajeros,
procedencia y destino). Se guardan en extras.json («cruceros») los de hoy en adelante; la tele enseña los próximos en Mar.
Los ferris (Melilla, Nador) no: su pantalla de llegadas y salidas (pantallas_em.apalmeria.com:4445) no se puede leer desde la nube.

  python3 -I herramientas/cruceros.py extras.json

Imprime una línea JSON: {"cruceros": N, "pdf": url, "actualizacion": "15/02/26"} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, json, os, re, subprocess, sys, tempfile
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
PAGINA = "https://apalmeria.com/pasajeros/cruceros/"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def pdf_del_anio(html, anio):
    """El enlace «Cruceros AAAA (pdf)» del año (el nombre del fichero cambia: CRUCEROS-2026.pdf, Cruceros-2025.pdf, 02_cruceros-2024.pdf)."""
    for u in re.findall(r'href="([^"]+\.pdf)"', html):
        if re.search(rf"cruceros-{anio}\.pdf$", u, re.I): return u if u.startswith("http") else "https://apalmeria.com" + u
    return None


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, check=True).stdout


def leer(texto):
    """Cada fila: número, fecha (o dos días: «11-12/04/2026»), día, entrada-salida, barco, naviera, muelle, pasajeros, … procedencia y
    destino. El día de la semana se calcula de la fecha (en la relación hay alguno mal). Lo que no se lee, no se apunta."""
    act = re.search(r"Actualizaci[oó]n\s*([\d/]+)", texto)
    filas = []
    for linea in texto.splitlines():
        m = re.match(r"\s*\d+\s+(\d{2})(?:-(\d{2}))?/(\d{2})/(\d{4})\s+\S+\s+(\d{1,2}[:.]\d{2})\s*-\s*(\d{1,2}[:.]\d{2})\s{2,}(.+)$", linea)
        if not m: continue
        d1, d2, mes, anio, ent, sal, resto = m.groups()
        try: fecha = dt.date(int(anio), int(mes), int(d1))
        except ValueError: continue
        c = [x.strip() for x in re.split(r"\s{2,}", resto.strip()) if x.strip()]
        if not c: continue
        pax = next((int(x.replace(".", "")) for x in c[1:] if re.fullmatch(r"\d{1,2}(\.\d{3})?|\d{2,4}", x)), None)
        f = {"fecha": fecha.isoformat(), "dia": DIAS[fecha.weekday()], "entrada": ent.replace(".", ":").zfill(5), "salida": sal.replace(".", ":").zfill(5),
             "barco": c[0].title().replace("´", "'"), "naviera": (lambda n: n.title() if n.isupper() else n)(re.sub(r"Ribera.*$", "", c[1]).strip()) if len(c) > 1 else ""}
        if d2: f["hasta"] = dt.date(int(anio), int(mes), int(d2)).isoformat()
        if pax: f["pasajeros"] = pax
        i = next((k for k, x in enumerate(c) if re.fullmatch(r"\d{1,2}(\.\d{3})?|\d{2,4}", x)), None)   # tras los pasajeros: consignatario,
        if i is not None and len(c) - i >= 4: f["desde"], f["hacia"] = c[-2].title(), c[-1].title()   # empresa (a veces juntos), procedencia y destino
        filas.append(f)
    return filas, (act.group(1) if act else None)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    try:
        html = comun.pedir(PAGINA).decode("utf-8", "replace")
        filas, act, urls = [], None, []
        for anio in sorted({hoy.year, (hoy + dt.timedelta(days=60)).year}):   # en noviembre y diciembre, también la del año siguiente si ya está
            u = pdf_del_anio(html, anio)
            if not u: continue
            f, a = leer(texto_pdf(comun.pedir(u)))
            filas += f; act = act or a; urls.append(u)
        if not urls: raise ValueError(f"sin la relación de cruceros de {hoy.year} en {PAGINA}")
        if not filas: raise ValueError("la relación no se ha podido leer")
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    prox = sorted((f for f in filas if (f.get("hasta") or f["fecha"]) >= hoy.isoformat()), key=lambda f: (f["fecha"], f["entrada"]))
    nuevo = {"lista": prox, "fuente": "Autoridad Portuaria de Almería", "pdf": urls[-1], "url": PAGINA, "actualizacion": act}
    if x.get("cruceros") != nuevo:
        x["cruceros"] = nuevo
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"cruceros": len(prox), "pdf": urls[-1], "actualizacion": act}, ensure_ascii=False))


if __name__ == "__main__":
    main()
