"""Saca la imagen de una captura bajada de Google Drive para poder mirarla (buzón de capturas de sorteos y cortes).

El conector de Drive (download_file_content) devuelve la imagen en base64. Si es pequeña llega dentro de la conversación
y queda en el registro de la sesión (~/.claude/projects/**/*.jsonl); si es grande, Claude Code la guarda en un fichero
(…/tool-results/…) y solo dice dónde. Este script busca el resultado de ese fileId en los dos sitios (o en el fichero que
se le diga), lo decodifica y deja la imagen y, si es alta como una captura de móvil, recortes que se leen mejor.

  python3 captura.py FILEID carpeta_salida [--desde fichero]
"""
import argparse, base64, glob, json, os, re, sys

B64 = re.compile(r'\\?"content\\?"\s*:\s*\\?"([A-Za-z0-9+/=]{16,})')
TIPOS = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"GIF8": "gif", b"RIFF": "webp"}


def textos(o):
    """Todas las cadenas de un JSON, también las que son a su vez JSON (resultados dentro de resultados)."""
    if isinstance(o, str):
        yield o
        if o[:1] in "{[":
            try: yield from textos(json.loads(o))
            except ValueError: pass
    elif isinstance(o, dict):
        for v in o.values(): yield from textos(v)
    elif isinstance(o, list):
        for v in o: yield from textos(v)


def base64_de(texto, fid):
    """El base64 del campo «content» de la respuesta de ese fichero, o None."""
    for t in textos(texto):
        if fid not in t: continue
        try:
            d = json.loads(t)
            if isinstance(d, dict) and d.get("id") == fid and d.get("content"): return d["content"]
        except ValueError:
            pass
        m = B64.search(t)
        if m: return m.group(1)
    return None


RAIZ = os.path.join(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")), "projects")


def buscar(fid, desde=None, raiz=RAIZ):
    """Primero el fichero indicado; si no, el más nuevo de tool-results y registros que tenga el fileId."""
    if desde: candidatos = [desde]
    else:
        candidatos = glob.glob(os.path.join(raiz, "**", "tool-results", "*"), recursive=True)
        candidatos += glob.glob(os.path.join(raiz, "**", "*.jsonl"), recursive=True)
        candidatos.sort(key=os.path.getmtime, reverse=True)
    for f in candidatos:
        try:
            with open(f, encoding="utf-8", errors="replace") as h: crudo = h.read()
        except OSError: continue
        if fid not in crudo: continue
        lineas = crudo.splitlines() if f.endswith(".jsonl") else [crudo]
        for l in reversed(lineas):            # el resultado más reciente de ese fichero
            if fid not in l: continue
            try: o = json.loads(l)
            except ValueError: o = l
            b = base64_de(o, fid) or (base64_de(l, fid) if o is not l else None)
            if b: return b
    return None


def tipo(datos):
    for firma, ext in TIPOS.items():
        if datos.startswith(firma): return ext
    return "bin"


def recortes(ruta, salida, base, ancho_max=1000):
    """Captura alta → trozos de alto ≈ 1,1 × ancho con solape del 12 %, para leer la letra pequeña."""
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        im = Image.open(ruta)
        im.load()
    except Exception:                          # no es una imagen que PIL sepa abrir (HEIC, PDF…): se mira tal cual
        return []
    with im:
        im = im.convert("RGB")
        w, h = im.size
        if h <= 1.3 * w: return []
        alto, paso, hechos, y = int(w * 1.1), int(w * 1.1 * 0.88), [], 0
        while True:
            y2 = min(y + alto, h)
            t = im.crop((0, max(0, y2 - alto), w, y2))
            if w > ancho_max: t = t.resize((ancho_max, int(t.height * ancho_max / w)))
            p = os.path.join(salida, f"{base}_parte{len(hechos) + 1}.png")
            t.save(p)
            hechos.append(p)
            if y2 >= h: return hechos
            y += paso


def main():
    a = argparse.ArgumentParser()
    a.add_argument("fileid"); a.add_argument("salida"); a.add_argument("--desde")
    o = a.parse_args()
    b = buscar(o.fileid, o.desde)
    if not b: sys.exit(f"No encuentro la descarga de {o.fileid}: llama antes a download_file_content con ese fileId.")
    datos = base64.b64decode(b)
    os.makedirs(o.salida, exist_ok=True)
    ruta = os.path.join(o.salida, f"{o.fileid}.{tipo(datos)}")
    with open(ruta, "wb") as h: h.write(datos)
    print(ruta)
    for p in recortes(ruta, o.salida, o.fileid): print(p)


if __name__ == "__main__":
    main()
