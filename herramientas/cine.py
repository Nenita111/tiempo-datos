"""Cine (21 nov 2026, lo pidió Isa: «añade Ocine»): las sesiones de hoy del Ocine Copo de El Ejido, el cine más cercano a Adra (Adra no
tiene cine). La web del propio cine (ocinecopo.es) es una aplicación que no da la cartelera en la página; se leen de su ficha en Sensacine
(www.sensacine.com/cines/cine/E2899/: su robots.txt no cierra /cines/ ni nombra a Claude), que es de donde se compran las entradas del
cine (tickets.ocinecopo.es). Cada película: su título, sus horas de hoy y su versión, tal cual.

  python3 -I herramientas/cine.py extras.json

Se guarda en extras.json («cine»). Imprime una línea JSON: {"peliculas": N, "sesiones": N} o {"error": …} (sale con 1; deja lo que había).
"""
import html, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

PAGINA = "https://www.sensacine.com/cines/cine/E2899/"
CINE, SITIO = "Ocine Copo", "El Ejido"


def peliculas(h, hoy):
    """[{titulo, horas: ["16:00", …], version}] de las sesiones de hoy ([hoy], «AAAA-MM-DD»), en el orden de la página."""
    h = re.sub(r"(?s)<(style|script)\b.*?</\1>", "", h)
    trozos = re.split(r'class="card entity-card', h)[1:]
    res = []
    for t in trozos:
        m = re.search(r'class="meta-title-link"[^>]*>([^<]+)<', t)
        if not m: continue
        horas = sorted({x[11:16] for x in re.findall(r'data-showtime-time="([^"]+)"', t) if x.startswith(hoy)})
        if not horas: continue
        v = re.search(r'(?s)<div class="text">\s*[^<]*?-\s*En\s+([^<]+?)\s*</div>', t)
        res.append({"titulo": comun.limpio(html.unescape(m.group(1))), "horas": horas, "version": comun.limpio(v.group(1)) if v else ""})
    return res


def main():
    ruta = sys.argv[1]
    x = comun.leer(ruta)
    hoy = comun.hoy().isoformat()
    try:
        P = peliculas(comun.pedir(PAGINA, intentos=1).decode("utf-8", "replace"), hoy)
        if not P: raise ValueError("Sensacine no trae sesiones de hoy del Ocine Copo")
    except Exception as e:
        comun.fallar(e)
    comun.poner(ruta, x, "cine", {"cine": CINE, "sitio": SITIO, "fecha": hoy, "peliculas": P, "fuente": "Sensacine", "enlace": PAGINA})
    comun.decir({"peliculas": len(P), "sesiones": sum(len(p["horas"]) for p in P)})


if __name__ == "__main__":
    main()
