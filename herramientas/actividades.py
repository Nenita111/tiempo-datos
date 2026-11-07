"""Planes gratis o al aire libre entre Almería y Motril (4.31, lo pidió Isa el 7 nov 2026: «agenda cultural de actividades gratuitas o al
aire libre, como senderos, entre Almería y Motril» y «añade senderos aunque no sean gratuitos»). Lo que se hace en los próximos 45 días y
es gratis (lo dice su ficha: «gratuito», «entrada libre», precio 0) o al aire libre (rutas, senderismo, marchas, excursiones, naturaleza);
las rutas de senderismo, aunque se paguen. De:
  - Turismo de Almería (Ayuntamiento de Almería; la API de su agenda, wp-json/eventon-api, y la de sus lugares, con coordenadas). Sus horas
    («evcal_srow») son la hora de aquí escrita como si fuera UTC: se leen así (comprobado con el texto de tres eventos).
  - Motril Turismo (Ayuntamiento de Motril; la agenda del mes y la del mes siguiente, con su precio).
  - Diputación de Almería, Deportes (los títulos de su portada: «Rutas y Senderos 2026. Sendero de la Uva Canjáyar 15-11-26»; sus fichas
    daban error el 7 nov 2026: solo el título y el día).
Los robots.txt de las tres dejan esas páginas. La agenda de la Junta ya está en «agendaJunta» (agenda_junta.py); la página junta las dos.

  python3 -I herramientas/actividades.py extras.json

Imprime una línea JSON: {"actividades": N, "fuentes": {…}, "fallos": […]} o {"error": …} (sale con 1 si fallan todas; deja lo que había).
"""
import datetime as dt, html, json, os, re, sys, time
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
DIAS = 45
TURALM = "https://www.turismodealmeria.org/wp-json"
MOTRIL = "https://motrilturismo.com"
DIPALME = "https://www.dipalme.org"
DIPALME_DEPORTES = DIPALME + "/Servicios/cmsdipro/index.nsf/index.xsp?p=deportes"
LIBRE = re.compile(r"gratuit|entrada libre|acceso libre|\bgratis\b|sin coste|entrada gratuita", re.I)
PAGO = re.compile(r"\d+(?:[.,]\d+)?\s?(?:€|euros)", re.I)
SENDERISMO = re.compile(r"\bsender|\bsenda\b|\brutas?\b|\bmarcha\b|caminata|\bsenderismo", re.I)
AIRE = re.compile(r"\bsender|\bsenda\b|\brutas?\b|\bmarcha\b|excursi|\bpaseo|\bplaya|naturaleza|aire libre|avistamiento|observaci[oó]n de (?:aves|estrellas)|"
                  r"\bbicicl|\bkayak|\bsnorkel|\bestrellas\b|astron|\bjard[ií]n bot|al aire", re.I)
MESES = {m: i for i, m in enumerate(comun.MESES, 1)}


def texto(h):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h or "")).split())


def ventana(ini, fin, hoy):
    """Lo que no ha acabado y empieza en los próximos 45 días; lo largo (más de tres semanas) que ya había empezado hace más de una, no;
    ni lo que dura más de dos meses (cursos, exposiciones permanentes)."""
    if not ini or not fin or fin < hoy or ini > hoy + dt.timedelta(days=DIAS): return False
    return (fin - ini).days <= 60 and not ((fin - ini).days > 21 and ini < hoy - dt.timedelta(days=7))


def plan(titulo, ini, fin, hoy, **k):
    t = " ".join(str(k.get(c) or "") for c in ("tipo", "programa"))          # el texto entero, no («Historia Natural», «el mar»…)
    gratis = k.pop("gratis", None)
    senderismo = bool(SENDERISMO.search(titulo + " " + str(k.get("programa") or "")))
    aire = senderismo or bool(AIRE.search(titulo + " " + t))
    if not (gratis or aire) or not ventana(ini, fin, hoy): return None
    p = {"titulo": titulo, "inicio": ini.isoformat()}
    if fin != ini: p["fin"] = fin.isoformat()
    for c in ("hora", "lugar", "municipio", "precio", "enlace", "fuente"):
        if k.get(c): p[c] = k[c]
    if gratis: p["gratis"] = True
    if aire: p["aireLibre"] = True
    if senderismo: p["senderismo"] = True
    return p


def titular(t):
    t = " ".join(t.split())
    return t[:1] + t[1:].lower() if sum(c.isupper() for c in t) > 0.6 * max(1, sum(c.isalpha() for c in t)) else t


# ---- Turismo de Almería
def turismo_almeria(eventos, lugares, hoy):
    zona = lambda l: l.get("latitude") and 36.6 <= float(l["latitude"]) <= 37.15 and -3.65 <= float(l["longitude"]) <= -2.35
    locs = {l["id"]: l for l in lugares}
    res, vistos = [], set()
    for e in eventos:
        if e.get("id") in vistos: continue
        vistos.add(e.get("id"))
        m = e.get("meta") or {}
        try:
            a = dt.datetime.fromtimestamp(int(m["evcal_srow"]), dt.timezone.utc).replace(tzinfo=None)
            b = dt.datetime.fromtimestamp(int(m.get("evcal_erow") or m["evcal_srow"]), dt.timezone.utc).replace(tzinfo=None)
        except (KeyError, ValueError, TypeError): continue
        L = (e.get("location") or [{}])[0]
        l = locs.get(L.get("id"), {})
        if l and l.get("latitude") and not zona(l): continue
        cuerpo = texto(e.get("content"))
        gratis = True if LIBRE.search(cuerpo) else None
        p = plan(html.unescape(e.get("title") or "").strip(), a.date(), b.date(), hoy, gratis=gratis, texto=cuerpo,
                 tipo=", ".join(t.get("name", "") for t in e.get("event_type") or []),
                 hora="" if m.get("evcal_allday") == "yes" else a.strftime("%H:%M"), lugar=html.unescape(L.get("name") or ""),
                 municipio="Almería", enlace=e.get("permalink"), fuente="Turismo de Almería",
                 precio="" if gratis else (PAGO.search(cuerpo).group(0) if PAGO.search(cuerpo) else ""))
        if p: res.append(p)
    return res


def pedir_turismo_almeria(pedir, dormir):
    ev, lu = [], []
    for n in (1, 2):
        ev += json.loads(pedir(f"{TURALM}/eventon-api/v1/events?per_page=100&page={n}", timeout=60)).get("data") or []; dormir(1)
    for n in range(1, 6):
        d = json.loads(pedir(f"{TURALM}/evenlocation/v1/locations?per_page=100&page={n}", timeout=60)).get("data") or []
        lu += d; dormir(1)
        if len(d) < 100: break
    return ev, lu


# ---- Motril Turismo
def motril(pag, hoy):
    def campo(b, nombre):
        m = re.search(r"field-name-" + nombre + r'[^"]*">(.*?)</div></div></div>', b, re.S)
        return texto(re.sub(r'<div class="field-label">.*?</div>', "", m.group(1), flags=re.S)) if m else ""
    res = []
    for b in re.split(r'<div class="views-row ', pag)[1:]:
        if "node-evento" not in b[:300]: continue
        a = re.search(r'field-name-title-field.*?<a href="([^"]+)">(.*?)</a>', b, re.S)
        if not a: continue
        ds = [dt.date(int(y), MESES[m.lower()], int(d)) for d, m, y in re.findall(r"(\d{1,2}) de ([A-Za-zé]+), (\d{4})", campo(b, "field-horario-fecha"))
              if m.lower() in MESES]
        if not ds: continue
        precio = campo(b, "field-precio-normal")
        gratis = True if LIBRE.search(precio) or re.fullmatch(r"0(?:[.,]00?)?\s*€?", precio or "x") else None
        p = plan(titular(texto(a.group(2))), ds[0], ds[-1], hoy, gratis=gratis, tipo=campo(b, "field-evento-etiquetas"),
                 hora=campo(b, "field-horario-horario")[:40], lugar=campo(b, "field-referencia-a-sitio"), municipio="Motril",
                 precio="" if gratis else precio[:20], enlace=MOTRIL + a.group(1), fuente="Motril Turismo")
        if p: res.append(p)
    return res


# ---- Diputación de Almería, Deportes
def municipios():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "municipios_almeria.json")
    return {comun.sin_tildes(m[0]): (m[0], m[2], m[3]) for m in comun.leer(p)["municipios"]}


def dipalme(pag, hoy, munis=None):
    munis = munis if munis is not None else municipios()
    res, vistos = [], set()
    for m in re.finditer(r'href="(/Servicios/cmsdipro/index\.nsf/fiestas\.xsp\?p=deportes&(?:amp;)?documentId=([0-9A-F]+))"[^>]*>(.*?)</a>', pag, re.S):
        t = texto(m.group(3))
        f = re.search(r"(?:(\d{1,2}) al )?(\d{1,2})-(\d{1,2})-(\d{2,4})$", t)
        if not f or m.group(2) in vistos: continue
        vistos.add(m.group(2))
        try:
            fin = dt.date(int(f[4]) + (2000 if len(f[4]) == 2 else 0), int(f[3]), int(f[2]))
            ini = fin.replace(day=int(f[1])) if f[1] else fin
        except ValueError: continue
        prog, _, resto = t[:f.start()].strip().partition(". ")
        if not resto: continue
        if not re.search(r"ruta|sender|descubre|naturaleza|activa", prog, re.I): continue      # los talleres y torneos, no
        # solo lo de un pueblo de la franja de Almería a Motril (los títulos acaban con el pueblo: «… Canjáyar»; Calar Alto o Tabernas, no)
        mu = next((n for k, (n, la, lo) in munis.items() if re.search(r"\b" + re.escape(k) + r"\b", comun.sin_tildes(resto))), None)
        if not mu or not (munis[comun.sin_tildes(mu)][1] <= 37.15 and -3.65 <= munis[comun.sin_tildes(mu)][2] <= -2.40): continue
        p = plan(resto.strip(), ini, fin, hoy, programa=prog, municipio=mu, enlace=DIPALME + html.unescape(m.group(1)), fuente="Diputación de Almería")
        if p: p["programa"] = prog; res.append(p)
    return res


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    lista, fuentes, fallos = [], {}, []
    pedir = lambda u, **k: comun.pedir(u, **k)
    try:
        ev, lu = pedir_turismo_almeria(pedir, time.sleep)
        l = turismo_almeria(ev, lu, hoy); fuentes["Turismo de Almería"] = len(l); lista += l
    except Exception as e: fallos.append(f"Turismo de Almería: {str(e)[:80]}")
    try:
        sig = (hoy.replace(day=1) + dt.timedelta(days=32)).strftime("%Y-%m")
        l = []
        for u in (f"{MOTRIL}/es/que-hacer/agenda", f"{MOTRIL}/es/agenda/{sig}"):
            l += motril(pedir(u, timeout=60).decode("utf-8", "replace"), hoy); time.sleep(1)
        u, l = set(), [p for p in l if not (p["enlace"] + p["inicio"] in u or u.add(p["enlace"] + p["inicio"]))]
        fuentes["Motril Turismo"] = len(l); lista += l
    except Exception as e: fallos.append(f"Motril Turismo: {str(e)[:80]}")
    try:
        l = dipalme(pedir(DIPALME_DEPORTES, timeout=60).decode("utf-8", "replace"), hoy); fuentes["Diputación de Almería"] = len(l); lista += l
    except Exception as e: fallos.append(f"Diputación de Almería: {str(e)[:80]}")
    if not fuentes:
        print(json.dumps({"error": "fallan todas", "fallos": fallos}, ensure_ascii=False)); sys.exit(1)
    viejo = {p.get("fuente") for p in (x.get("actividades") or {}).get("lista") or []}
    # lo de una fuente que hoy ha fallado se deja como estaba (lo que no ha pasado)
    for f in viejo - set(fuentes):
        lista += [p for p in x["actividades"]["lista"] if p.get("fuente") == f and (p.get("fin") or p["inicio"]) >= hoy.isoformat()]
    lista.sort(key=lambda p: (p["inicio"], p.get("hora") or "", p["titulo"]))
    nuevo = {"lista": lista, "fuentes": sorted(fuentes)}
    viejo_x = dict(x.get("actividades") or {}); viejo_x.pop("dia", None)
    if viejo_x != nuevo:
        x["actividades"] = dict(nuevo, dia=hoy.isoformat())
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"actividades": len(lista), "fuentes": fuentes, "fallos": fallos}, ensure_ascii=False))


if __name__ == "__main__":
    main()
