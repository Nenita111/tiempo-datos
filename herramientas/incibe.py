"""Estafas y engaños en circulación (15 nov 2026, lo pidió Isa: «estafas en circulación (avisos del INCIBE) en Alertas y productos»): los
avisos de seguridad para la ciudadanía del Instituto Nacional de Ciberseguridad (INCIBE), de su RSS oficial
(www.incibe.es/ciudadania/avisos/feed, el que enlaza su propia página de avisos; su robots.txt no lo cierra). Publica uno o dos al mes.
De cada aviso: el título, el día, a quién afecta («Recursos afectados») y de qué va (el primer párrafo de su descripción), tal cual, y su
enlace. Se guardan en extras.json («estafas») los de los últimos DIAS días, como mucho MAX.

  python3 -I herramientas/incibe.py extras.json

Un aviso recién publicado (de hace 3 días como mucho) se deja además para el móvil (comun.apuntar_aviso: lo manda la tarea diaria), una
sola vez: los ya vistos se recuerdan en estado_diario.json («estafasVistas»).
Imprime una línea JSON: {"estafas": N, "ultimo": "AAAA-MM-DD", "al_movil": N} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, email.utils, html, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

PAGINA = "https://www.incibe.es/ciudadania/avisos"
RSS = PAGINA + "/feed"
DIAS, MAX, RECIENTE = 60, 6, 3


def campo(desc, nombre):
    """El texto de un campo de la ficha del aviso (los «field--name-…» de su descripción): el primer párrafo, limpio."""
    m = re.search(rf'(?s)field--name-{nombre}\b.*?<div class="field__item">(.*?)</div>', desc)
    if not m: return ""
    p = re.search(r"(?s)<p[^>]*>(.*?)</p>", m.group(1))
    return comun.limpio(p.group(1) if p else m.group(1))


def recorta(s, n):
    """El texto entero si cabe; si no, hasta la última palabra que cabe, con puntos suspensivos."""
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def avisos(xml):
    """Los avisos del RSS, del más nuevo al más viejo: {titulo, fecha, afecta, resumen, enlace}. El que no trae título, día o enlace, no."""
    res = []
    for it in re.findall(r"(?s)<item>(.*?)</item>", xml):
        g = lambda e: html.unescape((re.search(rf"(?s)<{e}[^>]*>(.*?)</{e}>", it) or [None, ""])[1]).strip()
        desc, enlace, titulo = g("description"), g("link"), comun.limpio(g("title"))
        m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', desc)
        try: fecha = m.group(1) if m else email.utils.parsedate_to_datetime(g("pubDate")).astimezone(comun.TZ).date().isoformat()
        except (TypeError, ValueError): continue
        if not titulo or not enlace.startswith("https://www.incibe.es/"): continue
        a = {"titulo": titulo, "fecha": fecha, "enlace": enlace}
        afecta, resumen = campo(desc, "field-recursos-afectados"), campo(desc, "body")
        if afecta: a["afecta"] = recorta(afecta, 260)
        if resumen: a["resumen"] = recorta(resumen, 420)
        res.append(a)
    return sorted(res, key=lambda a: a["fecha"], reverse=True)


def vigentes(lista, hoy):
    desde = (hoy - dt.timedelta(days=DIAS)).isoformat()
    return [a for a in lista if desde <= a["fecha"] <= hoy.isoformat()][:MAX]


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = comun.leer(ruta)
    hoy = comun.hoy()
    try:
        todos = avisos(comun.pedir(RSS).decode("utf-8", "replace"))
        if not todos: raise ValueError("el RSS de avisos del INCIBE viene vacío")
    except Exception as e:
        comun.fallar(e)
    lista = vigentes(todos, hoy)
    comun.poner(ruta, x, "estafas", {"lista": lista, "fuente": "INCIBE (Instituto Nacional de Ciberseguridad)", "url": PAGINA})
    # al móvil, una vez, lo recién publicado (la primera vez no avisa de lo viejo: solo lo de los últimos días)
    vistas = comun.recuerdo(ruta, x, "estafasVistas")
    nuevos = [a for a in todos if a["enlace"] not in (vistas or []) and a["fecha"] >= (hoy - dt.timedelta(days=RECIENTE)).isoformat()]
    for a in nuevos: comun.apuntar_aviso(ruta, f"🛡️ Aviso del INCIBE: {a['titulo']}: {a['enlace']}")
    comun.recordar(ruta, x, "estafasVistas", [a["enlace"] for a in todos][:30])
    comun.decir({"estafas": len(lista), "ultimo": todos[0]["fecha"], "al_movil": len(nuevos)})


if __name__ == "__main__":
    main()
