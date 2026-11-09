"""Ofertas recientes de provisión temporal del Servicio Andaluz de Salud en la zona (lo pidió Isa el 9 nov 2026: «añade las ofertas
recientes del sur de Granada, poniente almeriense y Almería capital»): la página oficial del SAS «Provisión temporal de puestos base,
cargos intermedios y puestos directivos» (…/ofertas-de-empleo/provision-temporal-…/ooe). Su buscador se lee con direcciones normales
(?ooe_type=…&centro=…, las mismas a las que lleva su botón CONSULTAR); su robots.txt da 403 (sin restricciones, RFC 9309).

De cada tipo (puestos base, cargos intermedios y puestos directivos) se piden los centros de la zona, por su nombre en el filtro «Centro»
de la propia página: el Área de gestión sanitaria Sur de Granada; el Distrito Poniente de Almería y el Hospital de Poniente; y, de
Almería capital, el Hospital Universitario Torrecárdenas, el Distrito Almería, el Centro de transfusión y el 061. Se guardan en
extras.json («sasOfertas») las publicadas en los últimos 30 días: tipo, código, fecha (la de la web o la del BOJA), centro, título, puesto,
enlace a la convocatoria (PDF oficial), en qué va (por los documentos que el SAS añade después: listas, resolución, desierta…; nunca su
texto, solo una de las etiquetas de ESTADOS) y el plazo de solicitudes.

El plazo sale del PDF de la convocatoria (pdftotext), que solo se baja una vez por oferta: la frase «plazo de presentación … será de N días
hábiles (o naturales)…»; si no hay exactamente una, no se pone. El último día se calcula como en sas.py (Ley 39/2015, art. 30, con el
calendario oficial de días inhábiles de la Junta para el pueblo), desde el día siguiente a la publicación: en la web (puestos base) o en el
BOJA (cargos intermedios y directivos, que es la fecha que da la página). Sin Jev: la frase es de fórmula y el PDF no llega a su sandbox.

  python3 -I herramientas/sas_ofertas.py extras.json [--dias 30]

Imprime una línea JSON: {"ofertas": N, "nuevas": N, "con_plazo": N, "peticiones": N, "fallos": [...]} o {"error": …} (sale con 1; deja
lo que había). Si falla un centro, se quedan sus ofertas de la vez anterior que sigan dentro de los días.
"""
import argparse, datetime as dt, html, json, os, re, subprocess, sys, tempfile, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun
import sas

BASE = "https://www.sspa.juntadeandalucia.es"
PAGINA = (BASE + "/servicioandaluzdesalud/profesionales/ofertas-de-empleo/"
          "provision-temporal-de-puestos-base-cargos-intermedios-y-puestos-directivos/ooe")
TIPOS = [("base", "ooe_puesto_base", "pb"), ("intermedio", "ooe_cargo_intermedio", "ci"), ("directivo", "ooe_puesto_directivo", "pd")]
# los centros de la zona, por su nombre (sin tildes y en minúsculas) en el filtro «Centro» de la página; el primero que cuadre
AREAS = [("sur_granada", re.compile(r"sur de granada")),
         ("poniente", re.compile(r"poniente")),
         ("almeria", re.compile(r"torrecardenas|^distrito almeria$|^centro de transfusion.* de almeria$|^061 almeria\b"))]
FUERA = re.compile(r"norte de almeria|levante|almanzora|inmaculada")       # el Levante de Almería no es de la zona
# en qué va la oferta, por el título de los documentos que el SAS añade después de la convocatoria (el último que cuadre)
ESTADOS = [("desierta", re.compile(r"desiert")),
           ("resuelta", re.compile(r"adjudicaci|resoluci[oó]n definitiva|se resuelve")),
           ("resolución provisional", re.compile(r"resoluci[oó]n provisional")),
           ("lista definitiva de admitidos", re.compile(r"(?:listado?|relaci[oó]n) definitiv")),
           ("lista provisional de admitidos", re.compile(r"(?:listado?|relaci[oó]n) provisional")),
           ("actualizada", re.compile(r"actualizaci"))]
PESO = re.compile(r"\s*\(\s*\d[\d.,]*\s*[KM]B\s*\)\s*$", re.I)


def area_de(centro):
    c = comun.sin_tildes(centro).strip()
    if FUERA.search(c): return None
    return next((a for a, r in AREAS if r.search(c)), None)


def formulario(h):
    """El trozo de la página con el buscador y sus resultados."""
    i = h.find('id="sas-ooe-search-form"')
    return h[i:h.find("</form>", i)] if i >= 0 else ""


def centros(h, abrev):
    """[(id, nombre, elegido)] del filtro «Centro» de un tipo de oferta."""
    m = re.search(rf'(?s)<select[^>]*name="field_oferta_{abrev}_centro_target_id"[^>]*>(.*?)</select>', formulario(h))
    if not m: return []
    return [(v, comun.limpio(t), bool(s)) for v, s, t in re.findall(r'<option value="(\d+)"(\s+selected(?:="selected")?)?[^>]*>([^<]*)</option>', m.group(1))]


def filas(h):
    """Las ofertas de una página de resultados: [{id, cod, fecha, boja, docs: [(etiqueta, url, título)]}], en el orden de la página."""
    out = []
    for m in re.finditer(r'(?s)<article[^>]*data-history-node-id="(\d+)"[^>]*class="node node--type-ooe-[^"]*"[^>]*>(.*?)(?=<div class="views-row|<nav class="pager|$)', formulario(h)):
        nid, c = m.groups()
        f = re.search(r'(?s)field--name-field-oferta-\w+-fecha-(\w+)[^>]*>(.*?)</div>', c)
        d = re.search(r"(\d{2})/(\d{2})/(\d{4})", comun.limpio(f.group(2))) if f else None
        cod = re.search(r"Cod\.\s*</span>\s*(\d+)", c)
        docs = [(comun.limpio(pre).rstrip(". "), u if u.startswith("http") else BASE + u, PESO.sub("", comun.limpio(t)).strip())
                for pre, u, t in re.findall(r'(?s)<span class="file[^"]*">(.*?)<a href="([^"]+)"[^>]*>(.*?)</a>', c)]
        if not d or not docs: continue
        out.append({"id": nid, "cod": cod.group(1) if cod else "", "fecha": f"{d.group(3)}-{d.group(2)}-{d.group(1)}",
                    "boja": f.group(1) == "boja", "docs": docs})
    return out


def paginas(h):
    return max([int(n) for n in re.findall(r"[?&;]page=(\d+)", formulario(h))] or [0]) + 1


def puesto(tipo, titulo):
    """El puesto que se ofrece, sacado del título; «» si el título no es de los de siempre (se enseña entero)."""
    t = titulo.strip().rstrip(".").strip()
    if tipo == "base":
        m = re.search(r"(?i)provisi[oó]n temporal de\s+(.+?)(?:,?\s+para\s+(?:el|la|los|las)\s+|\s+(?:en|del)\s+(?:el\s+|la\s+)?(?=hospital|distrito|[aá]rea|ags\b|centro)|$)", t)
        if not m: return ""
        p = re.sub(r"(?i)^(?:un|una|uno|1)\s+puesto\s+de\s+", "", m.group(1).strip())
        n = re.match(r"(?i)^(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+puestos\s+de\s+(.+)$", p)
        if n: p = f"{n.group(2)} ({n.group(1).lower()} puestos)"
        p = p.strip(" ,.")
        return p[:1].upper() + p[1:] if len(p) > 3 else ""
    if tipo == "intermedio":
        m = re.search(r"(?i)\bcobertura\s+(.+)$", t)
        if not m: return ""
        p, cuantos = m.group(1), ""
        while True:       # «de un puesto de», «del puesto de cargo intermedio, próximo a quedar vacante, de», «de cuatro puestos de cargo intermedio de»…
            q = re.sub(r"(?i)^(?:del?|un|una|el|la)\s+", "", p)
            n = re.match(r"(?i)^(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+puestos\s+", q)
            if n: cuantos, q = n.group(1).lower(), q[n.end():]
            q = re.sub(r"(?i)^puestos?\s+", "", q)
            q = re.sub(r"(?i)^cargos?\s+intermedios?\s*", "", q)
            q = re.sub(r"(?i)^,?\s*pr[oó]ximos?\s+a\s+quedar\s+vacantes?\s*,?\s*", "", q)
            if q == p: break
            p = q
    else:
        m = re.search(r"(?i)car[aá]cter\s+directivo\s*,?\s*(?:pr[oó]ximo\s+a\s+quedar\s+vacante\s*,?\s*)?de\s+(.+)$", t)
        if not m: return ""
        p, cuantos = m.group(1), ""
    # el centro va aparte: fuera el final «… en el Distrito Sanitario…», «… en el Hospital…»
    p = re.sub(r"(?i)\s*,?\s+en\s+(?:el|la)\s+(?:distrito|hospital|[aá]rea\s+de\s+gesti[oó]n|centro)\b.*$", "", p).strip(" ,.")
    if len(p) <= 3: return ""
    return p[:1].upper() + p[1:] + (f" ({cuantos} puestos)" if cuantos else "")


def estado(docs):
    """En qué va, por los documentos de después de la convocatoria: una etiqueta de ESTADOS, «con novedades» si no cuadra ninguna o None."""
    e = None
    for pre, _, t in docs[1:]:
        x = (pre + " " + t).lower()
        if re.search(r"correcci[oó]n de errores", x): e = e or "corrección de errores"; continue
        e = next((n for n, r in ESTADOS if r.search(x)), None) or e or "con novedades"
    return e


N_U = r"(\d{1,3}|" + "|".join(sorted(sas.NUMEROS, key=len, reverse=True)) + r")\s+(?:\(\d{1,3}\)\s+)?(d[ií]as?\s+h[aá]biles|d[ií]as?\s+naturales|d[ií]as?)\b"
PLAZO = re.compile(r"(?is)plazo\s+de\s+presentaci[oó]n\b[^.;]{0,140}?\bser[aá]\s+de\s+" + N_U + r"([^.;]{0,260})")


def plazo_de(texto):
    """(n, unidad, desde_la_publicación) de la frase del plazo de presentación; None si no hay exactamente una (o dicen cosas distintas)."""
    t = re.sub(r"\s+", " ", texto or "")
    v = {}
    for m in PLAZO.finditer(t):
        n = int(m.group(1)) if m.group(1).isdigit() else sas.NUMEROS[m.group(1).lower()]
        u = "naturales" if "natural" in m.group(2).lower() else "habiles"
        v[(n, u)] = v.get((n, u), False) or "publicaci" in m.group(3).lower()
    if len(v) != 1: return None
    (n, u), pub = next(iter(v.items()))
    return n, u, pub


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", p, "-"], capture_output=True, text=True, timeout=120).stdout


def recoger(pedir, hoy, dias=30, antes=None, pausa=time.sleep, pdf=texto_pdf, inhabiles=None):
    """Las ofertas de la zona de los últimos «dias» días. «antes»: las de la vez anterior (su plazo no se vuelve a buscar y, si un centro
    falla, se quedan las suyas). Devuelve (lista, resumen)."""
    antes = {o["id"]: o for o in (antes or [])}
    desde = (hoy - dt.timedelta(days=dias)).isoformat()
    lista, fallos, n, inh, fallidos = {}, [], 0, None, set()
    texto = lambda u: pedir(u).decode("utf-8", "replace")
    for tipo, clave, ab in TIPOS:
        try: n += 1; cs = [(i, c, area_de(c)) for i, c, _ in centros(texto(f"{PAGINA}?ooe_type={clave}"), ab)]
        except Exception as e: fallos.append(f"{tipo}: {e}"[:120]); fallidos.add(tipo); continue
        for cid, centro, area in cs:
            if not area: continue
            pausa(1.5)
            try:
                for pag in range(3):
                    n += 1; h = texto(f"{PAGINA}?ooe_type={clave}&centro={cid}" + (f"&page={pag}" if pag else ""))
                    if not any(i == cid and s for i, _, s in centros(h, ab)): raise ValueError("el filtro del centro no se ha aplicado")
                    fs = filas(h)
                    for f in fs:
                        if f["fecha"] < desde: continue
                        d0 = f["docs"][0]
                        lista[f["id"]] = {"id": f["id"], "cod": f["cod"], "tipo": tipo, "fecha": f["fecha"], "boja": f["boja"], "centro": centro,
                                          "area": area, "titulo": d0[2], "puesto": puesto(tipo, d0[2]), "enlace": d0[1],
                                          "docs": len(f["docs"]), "estado": estado(f["docs"])}
                    if not fs or fs[-1]["fecha"] < desde or pag + 1 >= paginas(h): break       # lo demás es más antiguo
                    pausa(1.5)
            except Exception as e:
                fallos.append(f"{tipo}, {centro}: {e}"[:120]); fallidos.add((tipo, centro))
    for o in antes.values():       # lo de un centro (o un tipo) que hoy no se ha podido leer, si sigue dentro de los días
        if o["id"] not in lista and o.get("fecha", "") >= desde and (o.get("tipo") in fallidos or (o.get("tipo"), o.get("centro")) in fallidos):
            lista[o["id"]] = o
    nuevas = 0
    for o in lista.values():
        a = antes.get(o["id"])
        if a is not None and "plazo" in a: o["plazo"] = a["plazo"]; continue
        nuevas += 1
        try: n += 1; pausa(1.5); p = plazo_de(pdf(pedir(o["enlace"])))
        except Exception as e: fallos.append(f"PDF {o['cod']}: {e}"[:120]); continue       # mañana otra vez
        if not p: o["plazo"] = None; continue
        num, u, pub = p
        hasta = None
        if pub:
            f = dt.date.fromisoformat(o["fecha"])
            if inh is None: inh = (inhabiles or (lambda a: sas.inhabiles(a, lambda url: pedir(url).decode("utf-8", "replace"))))({f.year, f.year + 1})
            hasta = sas.fin_plazo(f, num, u, inh).isoformat()
        o["plazo"] = {"n": num, "unidad": u, "hasta": hasta}
    orden = sorted(lista.values(), key=lambda o: (o["fecha"], o["cod"].zfill(8)), reverse=True)
    return orden, {"ofertas": len(orden), "nuevas": nuevas, "con_plazo": sum(1 for o in orden if o.get("plazo")), "peticiones": n, "fallos": fallos}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("extras"); ap.add_argument("--dias", type=int, default=30)
    a = ap.parse_args()
    x = comun.leer(a.extras)
    hoy = dt.datetime.now(comun.TZ).date()
    viejo = x.get("sasOfertas") or {}
    try:
        lista, res = recoger(lambda u: comun.pedir(u, timeout=90), hoy, a.dias, viejo.get("lista"))
        if len(res["fallos"]) >= 3 and not lista: raise ValueError("; ".join(res["fallos"])[:200])
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    nuevo = {"lista": lista, "dias": a.dias, "fuente": "Servicio Andaluz de Salud", "url": PAGINA}
    if viejo != nuevo:
        x["sasOfertas"] = nuevo
        x["actualizado"] = dt.datetime.now(comun.TZ).isoformat(timespec="minutes")
        comun.guardar(a.extras, x)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
