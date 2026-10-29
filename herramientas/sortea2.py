"""Sorteos de la zona en sortea2.com, filtrados antes de que los mire Claude (tarea diaria): menos páginas que leer, menos tokens.

sortea2.com publica en su RSS (rss.xml; su robots.txt no lo cierra) las últimas 30 promociones con su texto entero, de todos los
países. El código se queda con las que nombran un pueblo de la zona (de Motril a Almería capital) y, si hay Jev (jev.py), Jev dice si
es un sorteo, si quien lo organiza está en la zona, si es para toda España y si dice cuándo acaba. Imprime una línea JSON con los
candidatos (texto y enlace); Claude los mira y apunta con sorteos.py solo los que tengan cuenta, premio, pueblo, fin y enlace a la
vista. Sin Jev, los candidatos son todos los que nombran la zona. Nunca se entra en Instagram.

  python3 -I herramientas/sortea2.py [--rss fichero]
"""
import argparse, html, json, os, re, sys, unicodedata, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

RSS = "https://www.sortea2.com/rss.xml"
UA = "TiempoYRadar/1.0 (sorteos locales para una tele)"
ZONA = ["Motril", "Torrenueva", "Calahonda", "Castell de Ferro", "La Mamola", "Albuñol", "La Rábita", "Adra", "Berja", "Dalías", "El Ejido",
        "Almerimar", "Balanegra", "Vícar", "La Mojonera", "Roquetas", "Aguadulce", "Almería"]


def plano(s): return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def items(xml):
    out = []
    for it in re.findall(r"(?s)<item>(.*?)</item>", xml):
        cdata = lambda tag: re.sub(r"(?s)^<!\[CDATA\[(.*)\]\]>$", r"\1", (re.search(rf"(?s)<{tag}>(.*?)</{tag}>", it) or [None, ""])[1].strip())
        texto = html.unescape(re.sub(r"<[^>]+>", " ", cdata("description")))
        texto = re.sub(r"Ver el sorteo publicado en Sortea2", "", re.sub(r"[ \t]+", " ", texto)).strip()
        texto = re.sub(r"^Hasta el: [\d/]+\s*", "", texto)      # la fecha hasta la que sortea2 tiene el anuncio, no la del sorteo
        out.append({"texto": texto, "enlace": cdata("link"), "publicado": cdata("pubDate")})
    return out


def en_zona(texto):
    t = plano(texto)
    return [z for z in ZONA if re.search(r"\b" + re.escape(plano(z)) + r"\b", t)]


def candidatos(xml, pedir=None):
    todos = items(xml); cand, juez = [], "Jev"; preguntado = False
    for p in todos:
        pueblos = en_zona(p["texto"])
        if not pueblos: continue
        c = {"pueblos": pueblos, "texto": p["texto"][:900], "enlace": p["enlace"], "publicado": p["publicado"]}
        if juez == "Jev":
            try:
                r, _ = jev.preguntar({"zona": ZONA, "promo": {"texto": p["texto"][:2500]}}, jev.preguntas_sorteo(), pedir=pedir)
                c["jev"] = {k: v["noul"] for k, v in r.items()}; preguntado = True
                if not jev.sorteo_candidato(r): continue
            except jev.SinRespuesta:
                c["jev"] = None                    # sin respuesta en la caché de Composio: va de candidato sin juzgar
            except jev.SinJev as e:
                juez = f"sin Jev ({e})"
        cand.append(c)
    return {"vistos": len(todos), "candidatos": cand, "juez": juez if preguntado or juez != "Jev" else "ninguno de la zona"}


def main():
    a = argparse.ArgumentParser(); a.add_argument("--rss"); o = a.parse_args()
    xml = (open(o.rss, "rb").read() if o.rss else urllib.request.urlopen(urllib.request.Request(RSS, headers={"User-Agent": UA}), timeout=40).read())
    print(json.dumps(candidatos(xml.decode("utf-8", "replace")), ensure_ascii=False))


if __name__ == "__main__":
    main()
