"""Novedades de barco dragón de la Federación Andaluza de Piragüismo (3.8, lo pidió Isa el 29 oct 2026: «añade las nuevas propuestas»): las
circulares y las noticias de la FAP (fapira.com; su robots.txt solo cierra las carpetas internas de Joomla) que hablan de una competición de
barco dragón, para saber de una nueva, o de un cambio de fecha o de sede, una suspensión o un aplazamiento, antes de que salga en el calendario
de competiciones (Cielo.regatas de la app).

  - Qué anuncia una competición de barco dragón que aún no se ha celebrado y qué anuncia un cambio: las circulares que lo dicen en el título
    («dragón», «suspensión», «aplazamiento»…), y Jev (jev.preguntas_fap, con el título y la entradilla) para lo demás; Jev dice también si
    el título nombra a alguien: esas no se guardan. Cada aviso se juzga una vez («juzgados», por un resumen del enlace).
  - De las circulares de barco dragón, el PDF (pdftotext): el día, el lugar y el último día de inscripción de su tabla («Fecha … Lugar …»,
    «Inscripción Del 13/10 al 27/10»), si los trae.

extras.json «fap»: {"fecha", "novedades": [{tipo, titulo, enlace, fecha, cambio, dia?, lugar?, inscripcion?}] (las de los últimos 60 días,
la más nueva primero), "juzgados": {clave: {anuncia, cambio, persona, …}}}. Sin Jev, solo las circulares que dicen «dragón». La tele las enseña en la tarjeta del
barco dragón y avisos_movil.py las manda al móvil, una vez.

  python3 -I herramientas/fap.py extras.json
"""
import datetime as dt, hashlib, html, json, os, re, subprocess, sys, tempfile, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

TZ = ZoneInfo("Europe/Madrid")
UA = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app
FAP = "https://fapira.com"
CIRCULARES = FAP + "/index.php/circulares-2/circulares-{y}"
NOTICIAS = FAP + "/index.php/noticias-2/noticias-{y}"
DIAS = 60
DRAGON = re.compile(r"(?i)\bdrag[oó]n\b|dragon\s*boat")
CAMBIO = re.compile(r"(?i)suspensi[oó]n|suspend|aplaza|cancela|anula|nueva fecha|cambio de (fecha|sede|lugar)|modificaci[oó]n")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MENUDAS = {"de", "del", "la", "las", "el", "los", "y", "en", "a", "al", "por", "para", "con", "e", "o"}


def pedir(url, timeout=60, intentos=3):
    for n in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r: return r.read()
        except Exception:
            if n == intentos - 1: raise


def limpio(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def absoluto(u): return u if u.startswith("http") else FAP + u


def bloques(h):
    """Cada elemento de la lista (circular o noticia): el título de su h3 con su enlace y lo demás del bloque."""
    for b in h.split('class="el-item')[1:]:
        t = re.search(r'(?s)<h3 class="el-title[^"]*">(.*?)</h3>', b)
        a = t and re.search(r'href="([^"]+)"', t.group(1))
        if a: yield b, absoluto(html.unescape(a.group(1))), limpio(t.group(1))


def circulares(h):
    out = []
    for b, enlace, titulo in bloques(h):
        d = re.search(r'<time datetime="(\d{4}-\d\d-\d\d)', b)
        if d and enlace.lower().endswith(".pdf"): out.append({"tipo": "circular", "titulo": titulo, "enlace": enlace, "fecha": d.group(1), "resumen": ""})
    return out


def noticias(h):
    out = []
    for b, enlace, titulo in bloques(h):
        m = re.search(r'(?s)class="el-meta[^"]*">\s*(\d{1,2})\s+([A-Za-zé]+)\s+(\d{4})\s*<', b)
        if not m or m.group(2).lower() not in MESES or "/noticias-" not in enlace: continue
        r = re.search(r'(?s)class="el-content[^"]*">(.*?)</div>', b)
        out.append({"tipo": "noticia", "titulo": titulo, "enlace": enlace, "resumen": limpio(r.group(1))[:500] if r else "",
                    "fecha": dt.date(int(m.group(3)), MESES.index(m.group(2).lower()) + 1, int(m.group(1))).isoformat()})
    return out


def titulo_limpio(t):
    """«CIRCULAR Nº 26/2026 - NORMATIVA CAMPEONATO DE ANDALUCÍA DE BARCO DRAGÓN 500m» → «Normativa Campeonato de Andalucía de Barco Dragón 500 m»."""
    t = re.sub(r"(?i)^circular\s+n[º°o]\.?\s*\d+\s*/\s*\d+\s*[-–:]\s*", "", t).strip()
    if not re.search(r"[a-záéíóúñ]{3}", t):                 # todo en mayúsculas
        p = t.lower().split()
        t = " ".join(w if (i and w in MENUDAS) or re.match(r"^\d", w) else w[:1].upper() + w[1:] for i, w in enumerate(p))
    return re.sub(r"(\d)\s*(m|metros)\b", r"\1 m", t)


def datos_pdf(datos):
    """El día, el lugar y el último día de inscripción de la tabla de la normativa (pdftotext). {} si no los trae o no se puede leer."""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "c.pdf"); open(f, "wb").write(datos)
        try: t = subprocess.run(["pdftotext", "-layout", f, "-"], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired): return {}
    return datos_texto(t)


def datos_texto(t):
    out = {}
    m = re.search(r"(?m)^\s*Fecha\s+(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+Lugar\s+(.+?))?\s*$", t)
    if m:
        try: out["dia"] = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError: pass
        if m.group(4): out["lugar"] = re.sub(r"\s+", " ", m.group(4)).strip()
    i = re.search(r"(?m)^\s*Inscripci[oó]n\s+Del?\s+\d{1,2}/\d{1,2}\s+al\s+(\d{1,2})/(\d{1,2})", t)
    if i and out.get("dia"):
        y = int(out["dia"][:4]); d = dt.date(y, int(i.group(2)), int(i.group(1)))
        if d.isoformat() > out["dia"]: d = d.replace(year=y - 1)     # en enero, la inscripción de diciembre
        out["inscripcion"] = d.isoformat()
    return out


def clave(enlace):
    """Lo juzgado se guarda por un resumen del enlace: los enlaces de las noticias llevan el título y a veces nombres de personas."""
    return hashlib.sha1(enlace.encode("utf-8")).hexdigest()[:12]


def juzgar(avisos, ya, pedir_jev=None, red=pedir, leer_pdf=datos_pdf):
    """{clave: {anuncia, cambio, persona, …}} de los avisos; lo ya juzgado no se vuelve a preguntar. Devuelve (juzgados, juez).
    Las circulares que dicen «dragón» anuncian una competición (son la normativa, la suspensión…); las noticias, según Jev, que dice también si
    el título nombra a alguien (esas no se guardan: ni nombres de palistas ni de nadie). Sin Jev, solo las circulares que dicen «dragón»."""
    out, juez = {}, "Jev"
    for a in avisos:
        k = clave(a["enlace"])
        if k in ya: out[k] = ya[k]; continue
        circ = a["tipo"] == "circular"
        anuncia, cambio = (1.0 if circ and DRAGON.search(a["titulo"]) else 0.0), (1.0 if CAMBIO.search(a["titulo"]) else 0.0)
        persona = 0.0 if circ else None
        if juez == "Jev":
            try:
                r, _ = jev.preguntar({"aviso": {"titulo": a["titulo"], "resumen": a.get("resumen", "")}}, jev.preguntas_fap(), pedir=pedir_jev)
                anuncia, cambio = max(anuncia, r["anuncia"]["noul"]), max(cambio, r["cambio"]["noul"])
                if not circ: persona = r["persona"]["noul"]
            except jev.SinRespuesta: continue                  # no estaba en la caché de Composio: mañana
            except (jev.SinJev, ValueError) as e: juez = f"sin Jev ({e})"
        if persona is None or (juez != "Jev" and not anuncia): continue    # sin Jev, solo se da por juzgado lo seguro
        e = {"anuncia": round(anuncia, 2), "cambio": round(cambio, 2), "persona": round(persona, 2)}
        if anuncia >= jev.SI and circ:
            try: e |= leer_pdf(red(a["enlace"]))
            except Exception: pass
        out[k] = e
    return out, juez


def novedades(avisos, juzgados):
    out = []
    for a in avisos:
        j = juzgados.get(clave(a["enlace"]))
        if not j or j["anuncia"] < jev.SI or j.get("persona", 1) >= 0.3: continue
        out.append({"tipo": a["tipo"], "titulo": titulo_limpio(a["titulo"]), "enlace": a["enlace"], "fecha": a["fecha"],
                    "cambio": j["cambio"] >= jev.SI} | {k: j[k] for k in ("dia", "lugar", "inscripcion") if j.get(k)})
    return sorted(out, key=lambda n: n["fecha"], reverse=True)


def leer(hoy, red=pedir):
    """Los avisos de los últimos DIAS días (circulares y noticias de este año y, en enero y febrero, del pasado)."""
    desde = (hoy - dt.timedelta(days=DIAS)).isoformat(); avisos, fallos = [], []
    for y in sorted({hoy.year, (hoy - dt.timedelta(days=DIAS)).year}):
        for url, f in ((CIRCULARES, circulares), (NOTICIAS, noticias)):
            try: avisos += f(red(url.format(y=y)).decode("utf-8", "replace"))
            except Exception as e: fallos.append(f"{url.format(y=y)}: {e}"[:160])
    vistos, res = set(), []
    for a in avisos:
        if a["fecha"] >= desde and a["enlace"] not in vistos: vistos.add(a["enlace"]); res.append(a)
    return res, fallos


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    x = json.load(open(sys.argv[1], encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    avisos, fallos = leer(hoy)
    if not avisos and fallos:
        print(json.dumps({"fallos": fallos}, ensure_ascii=False)); sys.exit(1)
    ya = (x.get("fap") or {}).get("juzgados") or {}
    juzgados, juez = juzgar(avisos, ya)
    x["fap"] = {"fecha": hoy.isoformat(), "novedades": novedades(avisos, juzgados), "juzgados": juzgados}
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    json.dump(x, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"avisos": len(avisos), "novedades": len(x["fap"]["novedades"]), "juez": juez, "fallos": fallos}, ensure_ascii=False))


if __name__ == "__main__":
    main()
