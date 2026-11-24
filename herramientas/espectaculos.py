"""Conciertos y espectáculos (22 nov 2026, lo pidió Isa: «añade una pestaña con conciertos y espectáculos, de Motril a Almería capital»):
conciertos, flamenco, teatro, danza, musicales, humor y magia de los próximos 60 días, de pago o gratis, de las agendas oficiales de cada
sitio (ninguna de sus robots.txt las cierra):
  - Almería capital: Turismo de Almería (Ayuntamiento), la API de su agenda (todas las páginas: no van por fecha), solo lo de la franja.
  - Roquetas de Mar: el Faro Cultural del Ayuntamiento (farocultural.roquetasdemar.es), sus listas de música, teatro y danza.
  - El Ejido: Cultura del Ayuntamiento (cultura.elejido.es): los espectáculos de su portada; el día con su año, de la ficha de cada uno
    (su «og:title» acaba con «(AAAA-MM-DD)»; se recuerda en estado_diario.json y no se vuelve a pedir). Su robots.txt cierra /wp-: la API, no.
  - Motril: Motril Turismo (Ayuntamiento), su agenda de este mes y del siguiente, lo etiquetado como conciertos, teatro, danza…
    (su robots.txt pide 10 s entre páginas).
Lo de Adra ya va en la agenda del pueblo (agenda.py); la página lo junta.

  python3 -I herramientas/espectaculos.py extras.json

Se guarda en extras.json («espectaculos»: {lista: [{titulo, fecha, hora, lugar, municipio, tipo, infantil, gratis, precio, enlace,
fuente}], fuentes, dia}). Lo de una fuente que hoy falla se deja como estaba. Imprime una línea JSON: {"espectaculos": N, "fuentes": {…},
"fallos": […]} o {"error": …} (si fallan todas; sale con 1).
"""
import datetime as dt, html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun, actividades as A

DIAS = 60
TURALM = A.TURALM
ROQUETAS = "https://farocultural.roquetasdemar.es"
EJIDO = "https://cultura.elejido.es"
MOTRIL = A.MOTRIL
MESES_CORTOS = {m: i for i, m in enumerate(("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"), 1)}

# el tipo, por el título (y el sitio): lo más concreto primero
TIPOS = [("Flamenco", r"flamenc|cantaor|zambomba|tablao|bulería|saeta"),
         ("Musical", r"\b(?:el|un|en|del) musical\b|^musical\b"),
         ("Danza", r"\bdanza|\bballet|cascanueces|\bbaile\b"),
         ("Humor", r"\bhumor|mon[oó]log|c[oó]mic[oa]s?\b|stand.?up|\bimpro\b|impro-?sible|las risas|\brisas\b"),
         ("Magia", r"\bmagia\b|\bmago\b|mentalis"),
         ("Concierto", r"concierto|\bm[uú]sica|orquesta|\bbanda\b|recital|\bcoros?\b|\bjazz|\brock\b|tribut|sinf[oó]n|\bpiano|guitarr|"
                       r"\bgira\b|\btour\b|zarzuela|[oó]pera\b|cantata|villancico|\bdj\b|festival"),
         ("Teatro", r"teatro|\bobra\b|comedia|tragedia|drama|t[ií]teres|clown|circo")]
INFANTIL = re.compile(r"infantil|en familia|familiar|t[ií]teres|cuentacuentos|payas|cantajuego|bubble|burbuja|\bpeque", re.I)
FUERA = re.compile(r"^cine\b|\bcine:|ciclo de cine|exposici[oó]n|\btaller|\bcurso|club de lectura|visitas? guiada|conferencia|"
                   r"presentaci[oó]n del? libro|patrocinio|jornadas?\b|charla|concurso|convocatoria|inscripci[oó]n", re.I)
SALA = re.compile(r"teatro|auditori|tablao|\bsala\b|anfiteatro", re.I)


def tipo_de(titulo, base="", sala="", extra=""):
    """El tipo del espectáculo: por el título; si no dice nada, el de su lista (base: «Música», «Teatro»…) o, si es en un teatro o una
    sala o el principio de su texto (extra) lo parece, «Espectáculo». None si no lo parece."""
    for t, r in TIPOS:
        if re.search(r, titulo, re.I): return t
    b = {"musica": "Concierto", "conciertos": "Concierto", "teatro": "Teatro", "danza": "Danza", "flamenco": "Flamenco"}.get(comun.sin_tildes(base))
    if b: return b
    # lo que diga su texto solo dice que es un espectáculo, no de qué tipo (la sala de un teatro infantil habla de «canciones»…)
    return "Espectáculo" if SALA.search(sala or "") or any(re.search(r, extra or "", re.I) for _, r in TIPOS) else None if SALA.search(sala or "") else None


def fila(titulo, fecha, hoy, base="", **k):
    titulo = " ".join(titulo.split())
    if not titulo or FUERA.search(titulo) or not fecha or fecha < hoy or fecha > hoy + dt.timedelta(days=DIAS): return None
    t = tipo_de(titulo, base, k.get("lugar"), k.get("extra") or "")
    if not t: return None
    p = {"titulo": titulo, "fecha": fecha.isoformat(), "tipo": t}
    if k.get("completo"): p["completo"] = True
    for c in ("hora", "lugar", "municipio", "precio", "enlace", "fuente"):
        if k.get(c): p[c] = k[c]
    if INFANTIL.search(titulo): p["infantil"] = True
    if k.get("gratis"): p["gratis"] = True
    return p


# ---- Almería: Turismo de Almería
def turismo_almeria(eventos, lugares, hoy):
    zona = lambda l: 36.6 <= float(l["latitude"]) <= 37.15 and -3.65 <= float(l["longitude"]) <= -2.35
    locs = {l["id"]: l for l in lugares}
    res, vistos = [], set()
    for e in eventos:
        if e.get("id") in vistos: continue
        vistos.add(e.get("id"))
        tipos = {t.get("name") for t in e.get("event_type") or []}
        if tipos & {"Cine", "Congresos", "Gastronomía", "Turismo activo"}: continue
        m = e.get("meta") or {}
        try: a = dt.datetime.fromtimestamp(int(m["evcal_srow"]), dt.timezone.utc).replace(tzinfo=None)   # (la hora de aquí, como si fuera UTC)
        except (KeyError, ValueError, TypeError): continue
        L = (e.get("location") or [{}])[0]
        l = locs.get(L.get("id"), {})
        try:
            if l.get("latitude") and l.get("longitude") and not zona(l): continue
        except ValueError: continue
        cuerpo = A.texto(e.get("content"))
        gratis = bool(A.LIBRE.search(cuerpo))
        precio = "" if gratis else (A.PAGO.search(cuerpo).group(0) if A.PAGO.search(cuerpo) else "")
        mu = (l.get("city") or "").strip() or "Almería"
        p = fila(html.unescape(e.get("title") or ""), a.date(), hoy, lugar=A.titular(html.unescape(L.get("name") or "")),       # («CALLE TIRSO…»)
                 hora="" if m.get("evcal_allday") == "yes" else a.strftime("%H:%M"), municipio=mu.title() if mu.isupper() else mu,
                 enlace=e.get("permalink"), fuente="Turismo de Almería", gratis=gratis, precio=precio, extra=cuerpo[:300])
        if p: res.append(p)
    return res


def pedir_turismo_almeria(pedir, dormir, maximo=15):   # 24 nov 2026: la de comun (una vez al día, también para actividades.py)
    return comun.turismo_almeria(pedir, dormir, maximo)


# ---- Roquetas de Mar: Faro Cultural
def roquetas(pag, base, hoy):
    res = []
    for m in re.finditer(r'class="date m-0"><strong>(.*?)</strong>.*?class="lugar m-0"><strong>(.*?)</strong>.*?<h3 class="titulo[^"]*">\s*'
                         r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', pag, re.S):
        f = re.match(r"\s*(\d{1,2}) (\w{3})\w* (\d{4})(?:, (\d{1,2}:\d{2}) h)?", html.unescape(m[1]))
        if not f or f[2].lower() not in MESES_CORTOS: continue
        try: d = dt.date(int(f[3]), MESES_CORTOS[f[2].lower()], int(f[1]))
        except ValueError: continue
        t = " ".join(html.unescape(re.sub(r"<[^>]+>", "", m[4])).split())
        t = re.sub(r"^(?:Música|Teatro|Danza|Otras actividades)\s*:\s*", "", t)
        lugar = " ".join(html.unescape(m[2]).split())
        if lugar == "Teatro Auditorio": lugar = "Teatro Auditorio de Roquetas"
        p = fila(t, d, hoy, base, hora=f[4] or "", lugar=lugar, municipio="Roquetas de Mar", enlace=m[3], fuente="Ayuntamiento de Roquetas de Mar")
        if p: res.append(p)
    return res


# ---- El Ejido: Cultura
def ejido_portada(pag):
    """{enlace: título} de los eventos de la portada (el título dice el día sin el año, el sitio y la hora)."""
    res = {}
    for m in re.finditer(r'<a href="(https://cultura\.elejido\.es/\?ai1ec_event=[^"]+)" title="([^"]+)"', pag):
        res.setdefault(html.unescape(m[1]), " ".join(html.unescape(m[2]).split()))
    return res


def ejido_fecha(ficha):
    """El día de la ficha de un evento: su og:title acaba con «(AAAA-MM-DD)»."""
    m = re.search(r'<meta property="og:title" content="[^"]*\((\d{4}-\d{2}-\d{2})\)"', ficha)
    return m[1] if m else None


DIA_SEMANA = re.compile(r"^(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b|^auditorio\b", re.I)
# lo que va delante del título y no es el título: la lista o la productora («Música – …», «Pentación Espectáculos – …», «Gala especial – …»)
DELANTE = re.compile(r"^(?:m[uú]sica|teatro|danza|humor|flamenco|gala(?: especial)?|.*\bproducciones|.*\bespect[aá]culos|oto[ñn]o cultural.*)$", re.I)


def ejido(portada, fechas, hoy):
    res = []
    for enlace, t in portada.items():
        f = fechas.get(enlace)
        if not f or FUERA.search(t): continue
        completo = bool(re.match(r"COMPLETO\b", t))
        t = re.sub(r"^COMPLETO\s+", "", t)
        partes = [x.strip() for x in re.split(r"\s*[–]\s*|\s+-\s+|-\s+(?=(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b)", t, flags=re.I) if x.strip()]
        base = partes.pop(0) if len(partes) > 1 and DELANTE.match(partes[0]) else ""
        titulo = partes[0]
        resto = " ".join(partes[1:])
        h = re.search(r"(\d{1,2})(?::(\d{2}))?\s*h\b", resto)
        lugar = "Auditorio de El Ejido" if re.search(r"\bauditorio\b", resto, re.I) else ""
        p = fila(titulo, dt.date.fromisoformat(f), hoy, base, hora=f"{int(h[1]):02d}:{h[2] or '00'}" if h else "", lugar=lugar, municipio="El Ejido",
                 enlace=enlace, fuente="Ayuntamiento de El Ejido", extra=" ".join(x for x in partes[1:] if not DIA_SEMANA.match(x)), completo=completo)
        if p: res.append(p)
    return res


def candidato_ejido(t):
    return not FUERA.search(t.split(" – ")[0]) and not re.search(r"ciavieja|aula de ocio|talleres|visitas", t, re.I)


# ---- Motril: Motril Turismo
ETIQUETAS = re.compile(r"concierto|teatro|danza|flamenco|espect[aá]culo|m[uú]sica|humor|musical|zarzuela|magia", re.I)


def hora_motril(h):
    m = re.match(r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*(?:h\b|$)", h or "")
    return f"{int(m[1]):02d}:{m[2] or '00'}" if m else ""


def motril(pag, hoy):
    res = []
    for f in A.motril_filas(pag):
        if not ETIQUETAS.search(f["tipo"] or ""): continue
        for d in sorted(set(f["dias"])):
            p = fila(f["titulo"], d, hoy, base=f["tipo"].split(",")[0].strip(), hora=hora_motril(f["hora"]),
                     lugar=f["lugar"], municipio="Motril", gratis=f["gratis"], precio="" if f["gratis"] else f["precio"][:20], enlace=f["enlace"],
                     fuente="Motril Turismo")
            if p: res.append(p)
    return res


def juntar(lista):
    """Uno por título, día y sitio (Roquetas pone cada sesión aparte: «20:00 y 22:30»), del más cercano al más lejano."""
    vistos = {}
    for p in sorted(lista, key=lambda p: (p["fecha"], p.get("hora") or "", p["titulo"])):
        k = (comun.sin_tildes(p["titulo"]), p["fecha"], p.get("municipio"))
        if k in vistos:
            q = vistos[k]
            if p.get("hora") and p["hora"] not in (q.get("hora") or ""): q["hora"] = (q["hora"] + " y " if q.get("hora") else "") + p["hora"]
            continue
        vistos[k] = dict(p)
    return list(vistos.values())


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = comun.leer(ruta)
    hoy = comun.hoy()
    pedir = lambda u, **k: comun.pedir(u, **k)
    lista, fuentes, fallos = [], {}, []

    def fuente(nombre, f):
        try:
            l = f(); fuentes[nombre] = len(l); lista.extend(l)
        except Exception as e: fallos.append(f"{nombre}: {str(e)[:80]}")

    fuente("Turismo de Almería", lambda: turismo_almeria(*pedir_turismo_almeria(pedir, time.sleep), hoy))

    def de_roquetas():
        l = []
        for c in ("musica", "teatro", "danza"):
            l += roquetas(pedir(f"{ROQUETAS}/{c}", timeout=60).decode("utf-8", "replace"), c, hoy); time.sleep(1)
        return l
    fuente("Ayuntamiento de Roquetas de Mar", de_roquetas)

    fechas = comun.recuerdo(ruta, x, "fechasEjido") or {}

    def de_ejido():
        portada = ejido_portada(pedir(EJIDO + "/", timeout=60).decode("utf-8", "replace"))
        if not portada: raise ValueError("la portada de Cultura de El Ejido ha llegado sin eventos")
        for enlace, t in portada.items():
            if enlace in fechas or not candidato_ejido(t): continue
            f = ejido_fecha(pedir(enlace, timeout=60).decode("utf-8", "replace")); time.sleep(1)
            if f: fechas[enlace] = f
        return ejido(portada, fechas, hoy)
    fuente("Ayuntamiento de El Ejido", de_ejido)

    def de_motril():
        sig = (hoy.replace(day=1) + dt.timedelta(days=32)).strftime("%Y-%m")
        l = []
        for i, u in enumerate((f"{MOTRIL}/es/que-hacer/agenda", f"{MOTRIL}/es/agenda/{sig}")):
            if i: time.sleep(10)                   # Crawl-delay: 10
            l += motril(pedir(u, timeout=60).decode("utf-8", "replace"), hoy)
        return l
    fuente("Motril Turismo", de_motril)

    if not fuentes:
        comun.decir({"error": "fallan todas", "fallos": fallos}); sys.exit(1)
    viejo = (x.get("espectaculos") or {}).get("lista") or []
    for f in {p.get("fuente") for p in viejo} - set(fuentes):      # lo de una fuente que hoy falla, como estaba (lo que no ha pasado)
        lista += [p for p in viejo if p.get("fuente") == f and p["fecha"] >= hoy.isoformat()]
    lista = juntar(lista)
    # lo recordado de El Ejido: solo lo que no ha pasado
    fechas = {k: v for k, v in fechas.items() if v >= hoy.isoformat()}
    nuevo = {"lista": lista, "fuentes": sorted({p["fuente"] for p in lista} | set(fuentes))}
    antes = dict(x.get("espectaculos") or {}); antes.pop("dia", None)
    quitado = comun.recordar(ruta, x, "fechasEjido", fechas)
    if antes != nuevo or quitado:
        if antes != nuevo: x["espectaculos"] = dict(nuevo, dia=hoy.isoformat())
        comun.publicar(ruta, x)
    comun.decir({"espectaculos": len(lista), "fuentes": fuentes, "fallos": fallos})


if __name__ == "__main__":
    main()
