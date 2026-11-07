"""Cursos gratis de formación para el empleo cerca de Adra (4.31, lo pidió Isa el 7 nov 2026: «cursos gratuitos de formación para el empleo
cerca de Adra»). Del buscador de cursos de la Consejería de Empleo, Empresa y Trabajo Autónomo de la Junta de Andalucía (formación
profesional para el empleo; su aviso legal deja reutilizarlo citando «Información obtenida del portal web Formación para el Empleo de la
Junta de Andalucía»; su robots.txt no cierra esa ruta). Dos búsquedas: los presenciales de la provincia de Almería y los de teleformación
(para toda Andalucía). Se quedan los gratuitos que aún se pueden pedir (la fecha de fin de solicitud no ha pasado; el «estado» del
buscador a veces está mal) o que se convocan para más adelante. El SEPE (sepe.es) cierra el paso a Claude en su robots.txt: no se usa.

  python3 -I herramientas/cursos.py extras.json

Imprime una línea JSON: {"cursos": N presenciales, "linea": M, ...} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, html, json, math, os, re, sys, time
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
WEB = "https://www.juntadeandalucia.es"
BUSCADOR = WEB + "/empleoformacionytrabajoautonomo/formacion/web/buscador-de-cursos"
BUSQUEDAS = {"presenciales": "provincias=63", "linea": "modalidad-de-imparticion=923"}
POR_PAGINA = 36
ADRA = (36.7480, -3.0213)
MAX_LINEA = 40
SIGLAS = {"RRSS", "IOT", "TIC", "TICS", "PRL", "SAP", "BIM", "CAD", "SEO", "SEM", "ERP", "CRM", "VSM", "IA", "UE", "PYMES", "ONG"}
MINUS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "a", "al", "por", "con", "o", "u", "sus", "su", "un", "una", "lo", "que"}


def municipios():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "municipios_almeria.json")
    return {comun.sin_tildes(m[0]): (m[2], m[3]) for m in comun.leer(p)["municipios"]}


def texto(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def tarjetas(pag):
    """Las tarjetas de una página del buscador: {campo: texto} con los «views-field-*» y las fechas, horas y lugar."""
    res = []
    for p in pag.split("views-view-grid__item-inner")[1:]:
        p = p.split('views-view-grid__item"')[0]
        d = {m.group(1): texto(m.group(2)) for m in re.finditer(r'views-field-([a-z0-9-]+)"[^>]*>(.*?)(?=<div class="views-field|$)', p, re.S)}
        a = re.search(r'href="(/empleoformacionytrabajoautonomo/formacion/web/buscador-de-cursos/(\d+))"', p)
        if a: d["url"], d["id"] = WEB + a.group(1), a.group(2)
        for cls in ("range-presentation", "date-range", "hours", "province"):
            m = re.search(r'class="%s"[^>]*>(.*?)</' % cls, p, re.S)
            if m: d[cls] = texto(m.group(1))
        res.append(d)
    return res


def fecha(s):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def nombre(t):
    """«IFCD85 - PROGRAMACIÓN PARA DISPOSITIVOS MÓVILES ANDROID» → («IFCD85», «Programación para dispositivos móviles Android»)."""
    if "¿" not in (t or ""): t = (t or "").replace("?", "")          # comillas que llegan como «?»
    cod, _, n = (t or "").partition(" - ")
    if not n: cod, n = "", cod
    if sum(c.isupper() for c in n) > 0.6 * max(1, sum(c.isalpha() for c in n)):
        pal = []
        for i, w in enumerate(n.split()):
            if re.search(r"\d", w) or w.strip(".,:;()") in SIGLAS or (2 <= len(w.strip(".,:;()")) <= 3 and w.isupper() and w.lower().strip(".,:;()") not in MINUS):
                pal.append(w)                                            # C1, 5G, VSM, RRSS, IA
            else:
                pal.append(w.lower())
        pal = [w.lower() if w in ("DEL", "LAS", "LOS", "CON", "POR", "UNA", "SUS", "QUE") else w for w in pal]
        n = " ".join(pal)
        n = re.sub(r"\b(android|excel|word|linux|windows|java|python|andalucía|almería|europa)\b", lambda m: m.group(1).capitalize(), n)
    return cod.strip(), (n[:1].upper() + n[1:]).strip()


def curso(d, hoy, munis):
    fin, ini = fecha(d.get("range-presentation")), fecha(d.get("date-range"))
    estado = d.get("field-state") or ""
    if "gratuit" not in comun.sin_tildes(d.get("field-finance")): return None
    convocado = "convocado" in comun.sin_tildes(estado)
    if not (fin and fin >= hoy) and not (convocado and ini and ini >= hoy): return None
    cod, nom = nombre(d.get("title-1"))
    c = {"id": d.get("id"), "codigo": cod, "nombre": nom, "enlace": d.get("url") or BUSCADOR}
    if fin: c["fin"] = fin.isoformat()
    if ini: c["inicio"] = ini.isoformat()
    h = re.search(r"(\d+)\s*Horas", d.get("hours") or "")
    if h: c["horas"] = int(h.group(1))
    para = comun.sin_tildes(d.get("field-directed"))
    c["para"] = "desempleadas" if "desemplead" in para else "ocupadas" if "ocupad" in para else (d.get("field-directed") or "")[:30]
    c["modalidad"] = "en línea" if "teleforma" in comun.sin_tildes(d.get("field-impartation-modality")) else (d.get("field-impartation-modality") or "").lower()
    if d.get("field-schedule"): c["horario"] = d["field-schedule"].lower()
    if convocado: c["convocado"] = True
    lugar = d.get("province") or ""
    if " - " in lugar:
        c["municipio"] = lugar.split(" - ", 1)[1].strip()
        p = munis.get(comun.sin_tildes(c["municipio"]))
        if p: c["km"] = round(math.hypot((p[1] - ADRA[1]) * 111.32 * math.cos(math.radians(ADRA[0])), (p[0] - ADRA[0]) * 110.57))
    return c


def buscar(filtro, pedir=comun.pedir, dormir=time.sleep):
    todas = []
    for n in range(1, 6):
        url = f"{BUSCADOR}?{filtro}&items_per_page={POR_PAGINA}&sort_bef_combine=fecha-inicio-prevista_ASC&pagina={n}"
        t = tarjetas(pedir(url, timeout=60).decode("utf-8", "replace"))
        nuevas = [d for d in t if d.get("id") not in {x.get("id") for x in todas}]
        todas += nuevas
        if len(t) < POR_PAGINA or not nuevas: break
        dormir(1)
    return todas


def leer(presenciales, linea, hoy, munis=None):
    munis = munis if munis is not None else municipios()
    pre = [c for c in (curso(d, hoy, munis) for d in presenciales) if c]
    lin = [c for c in (curso(d, hoy, munis) for d in linea) if c]
    clave = lambda c: (c.get("fin") or c.get("inicio") or "9999", c.get("km", 999), c["nombre"])
    return sorted(pre, key=clave), sorted(lin, key=clave)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    try:
        bruto = {k: buscar(f) for k, f in BUSQUEDAS.items()}
        if not bruto["presenciales"] and not bruto["linea"]: raise ValueError("el buscador no ha dado ningún curso")
        pre, lin = leer(bruto["presenciales"], bruto["linea"], hoy)
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    nuevo = {"presenciales": pre, "linea": lin[:MAX_LINEA], "lineaTotal": len(lin), "enlace": BUSCADOR,
             "fuente": "Información obtenida del portal web Formación para el Empleo de la Junta de Andalucía"}
    viejo = dict(x.get("cursos") or {}); viejo.pop("dia", None)
    if viejo != nuevo:
        x["cursos"] = dict(nuevo, dia=hoy.isoformat())
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"cursos": len(pre), "linea": len(lin), "vistos": sum(map(len, bruto.values()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
