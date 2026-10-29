"""Las disposiciones del Servicio Andaluz de Salud de la pantalla SAS de la tele, etiquetadas con Jev (tarea diaria, con diario.py).

La tele lee sola el BOJA (sección 2.2) y el BOE de los últimos 7 días y enseña lo que nombra al SAS (Empleo.kt). Aquí se leen los
mismos boletines (igual que la tele) y Jev dice de cada disposición qué es (convocatoria, lista provisional o definitiva, nombramiento,
cese, bolsa, traslado u otra) y a qué provincia toca (Almería, toda Andalucía, otra o no consta). Va en extras.json «sas»:
{"fecha", "etiquetas": {url: {"tipo", "provincia", "zona"}}, "avisar": [...]}; la tele pone la etiqueta y ordena primero lo de Almería y lo
de toda Andalucía. 3.7: «zona» (jev.ZONA_SAS: Almería sin lo que es solo del Levante, solo el Levante, la costa de Granada hasta Motril, toda
Andalucía, otra o no consta), que la tele usa antes que su regla de palabras para enseñar solo lo de la zona, y «avisar»: las convocatorias de
la zona ({url, fecha, boletin, resumen, hasta}), para los avisos al móvil (avisos_movil.py). 3.8: el plazo de presentar solicitudes de
cada convocatoria de la zona («plazo»: {n, unidad, hasta}): el código saca del texto de la disposición las frases con un plazo, Jev dice cuál
es el de las solicitudes y el código calcula el último día (Ley 39/2015, art. 30: los días, hábiles salvo que digan naturales; sin sábados,
domingos ni los festivos del calendario oficial de días inhábiles de la Junta para el pueblo; los meses, de fecha a fecha). Sin Jev no toca
nada (la tele sigue con su regla).

  python3 -I herramientas/sas.py extras.json [--dias 7]
"""
import argparse, datetime as dt, html, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun
import jev

TZ = ZoneInfo("Europe/Madrid")
JUNTA = "https://www.juntadeandalucia.es"
UA = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app (la Junta y el BOE lo aceptan así)


def pedir(url, aceptar=None, timeout=40):
    """Con 3 intentos (comun.pedir): el servidor de la Junta corta conexiones de vez en cuando."""
    return comun.pedir(url, UA, aceptar=aceptar, timeout=timeout).decode("utf-8", "replace")


def limpio(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


# ------------------------------------------------------------------ como Empleo.kt de la app
def disposiciones_boja(h, base):
    res = []
    for m in re.finditer(r'(?s)<div class="item punteado_izquierda">\s*<p>(.*?)</p>(.*?)(?=<div class="item punteado_izquierda">|<p class="h5|</main>|$)', h):
        texto = limpio(m.group(1))
        if "Servicio Andaluz de Salud" not in texto: continue
        pdf = re.search(r'href="([^"]+\.pdf)"', m.group(2)); ver = re.search(r'href="(/boja/\d{4}/\d+/\d+)"', m.group(2))
        pdf = (pdf.group(1) if pdf.group(1).startswith("http") else base + pdf.group(1)) if pdf else None
        res.append({"texto": texto, "url": JUNTA + ver.group(1) if ver else pdf})
    return res


def boletines(js):
    res = []
    for d in json.loads(js).get("resultado") or []:
        try: fecha = dt.datetime.strptime(d["bojaDate"], "%d/%m/%Y").date()
        except (KeyError, ValueError): continue
        for x in d.get("boja") or []:
            if x.get("extraordinario"): continue
            m = re.search(r"/eboja/(\d{4}/\d+)/", x.get("enlace", ""))
            if m: res.append((m.group(1), fecha))
    return res


def _lista(x): return x if isinstance(x, list) else [x] if isinstance(x, dict) else []


def sumario_boe(js):
    res = []
    s = (json.loads(js).get("data") or {}).get("sumario") or {}
    for diario in _lista(s.get("diario")):
        for sec in _lista(diario.get("seccion")):
            for dep in _lista(sec.get("departamento")):
                for it in _lista(dep.get("item")) + [i for e in _lista(dep.get("epigrafe")) for i in _lista(e.get("item"))]:
                    t = it.get("titulo", "")
                    if "Andaluz de Salud" in t: res.append({"texto": t, "url": it.get("url_html")})
    return res


def todas(dias=7, hoy=None, red=None):
    """Las disposiciones de los últimos días del BOJA (sección 2.2) y del BOE. Un día que no llega no tira los demás (3.9); si no llega
    ninguno, el error."""
    red = red or pedir
    hoy = hoy or dt.datetime.now(TZ).date(); out, error, bien = [], None, 0
    try: dias_boja = boletines(red(f"{JUNTA}/ssdigitales/datasets/contentapi/boja/calendario?fechaDesde=now-{dias}d&fechaHasta=now"))
    except Exception as e: dias_boja, error = [], e
    for ruta, fecha in dias_boja:
        base = f"{JUNTA}/eboja/{ruta}/"
        try: out += [d | {"boletin": "BOJA", "fecha": fecha.isoformat()} for d in disposiciones_boja(red(base + "s53.html"), base)]; bien += 1
        except urllib.error.HTTPError as e:
            if e.code == 404: bien += 1                    # ese día no hubo sección 2.2
            else: error = e
        except Exception as e: error = e
    for k in range(dias):
        d = hoy - dt.timedelta(days=k)
        try: out += [x | {"boletin": "BOE", "fecha": d.isoformat()} for x in sumario_boe(red(f"https://www.boe.es/datosabiertos/api/boe/sumario/{d:%Y%m%d}", "application/json"))]; bien += 1
        except urllib.error.HTTPError as e:
            if e.code == 404: bien += 1                    # domingos y festivos no hay BOE
            else: error = e
        except Exception as e: error = e
    if not bien and error: raise error
    return out


ZONA_TELE = ("almeria", "costa_granada", "andalucia")      # lo que enseña la tele (3.7)


# ------------------------------------------------------------------ 3.8: el plazo de las convocatorias de la zona
CALENDARIO = ("https://www.juntadeandalucia.es/ssdigitales/datasets/work-calendar/work-calendar/get/search_calendar_weekends"
              "?municipality={m}&province=-&year={y}")
MUNICIPIO = "ADRA"           # el de la tele, como lo escribe el calendario de la Junta
NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
           "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciséis": 16, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
           "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintiún": 21, "veintidós": 22, "veintidos": 22, "veintitrés": 23, "veintitres": 23,
           "veinticuatro": 24, "veinticinco": 25, "veintiséis": 26, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
           "treinta": 30, "cuarenta y cinco": 45, "sesenta": 60}
CANDIDATO = re.compile(r"(?i)\b(\d{1,3}|" + "|".join(sorted(NUMEROS, key=len, reverse=True)) + r")\s+(?:\(\d{1,3}\)\s+)?"
                       r"(d[ií]as?\s+h[aá]biles|d[ií]as?\s+naturales|d[ií]as?|mes(?:es)?)\b")


def frases_plazo(texto):
    """Las frases que hablan de un plazo con su número de días o meses: [(frase, n, unidad)] (unidad: habiles, naturales o meses)."""
    out = []
    for f in re.split(r"(?<=[.;])\s+", texto or ""):
        m = CANDIDATO.search(f) if re.search(r"(?i)\bplazo", f) else None
        if not m: continue
        n = int(m.group(1)) if m.group(1).isdigit() else NUMEROS[m.group(1).lower()]
        u = m.group(2).lower()
        out.append((f.strip()[:400], n, "meses" if u.startswith("mes") else "naturales" if "natural" in u else "habiles"))
    out.sort(key=lambda t: "solicitud" not in t[0].lower())     # primero las que hablan de solicitudes (en las bases largas hay muchos plazos)
    return out[:12]


DESDE_BOE = re.compile(r"(?i)Bolet[ií]n Oficial del Estado|\bBOE\b")


def desde_publicacion(frase, boletin):
    """¿Se cuenta desde el día siguiente a esta publicación? Si se cuenta desde la del BOE (y esto es del BOJA) o desde otra cosa, no se pone
    fecha: solo el número de días o meses."""
    f = frase.lower()
    if "publicaci" not in f: return False
    return not (boletin == "BOJA" and DESDE_BOE.search(frase))


def inhabiles(anios, red=pedir, municipio=MUNICIPIO):
    """Los días inhábiles (festivos de Andalucía y del pueblo) del calendario oficial de la Junta; los fines de semana, en fin_plazo."""
    out = set()
    for y in anios:
        try: r = json.loads(red(CALENDARIO.format(m=urllib.parse.quote(municipio), y=y))).get("results") or []
        except Exception: continue               # el año siguiente aún sin publicar: solo los fines de semana
        for x in r:
            if x.get("type") in ("LABORAL", "LOCAL"):
                d = str(x.get("date"))
                if len(d) == 8: out.add(dt.date(int(d[:4]), int(d[4:6]), int(d[6:])))
    return out


def fin_plazo(pub, n, unidad, inh):
    """El último día del plazo, contado desde el día siguiente a la publicación (Ley 39/2015, art. 30)."""
    habil = lambda d: d.weekday() < 5 and d not in inh
    if unidad == "habiles":
        d, k = pub, 0
        while k < n:
            d += dt.timedelta(days=1)
            if habil(d): k += 1
        return d
    if unidad == "meses":
        m = pub.month - 1 + n; y, m = pub.year + m // 12, m % 12 + 1
        ultimo = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
        d = dt.date(y, m, min(pub.day, ultimo))
    else:
        d = pub + dt.timedelta(days=n)
    while not habil(d): d += dt.timedelta(days=1)       # si acaba en inhábil, al primer hábil siguiente
    return d


def texto_disposicion(url, red=pedir):
    h = red(url)
    return limpio(re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", h))


def plazos(disps, et, red=pedir, pedir_jev=None):
    """Pone «plazo» en las convocatorias de la zona que aún no lo tienen (None si el texto no da ninguno). Devuelve cuántas."""
    hechas, inh = 0, None
    for d in disps:
        e = et.get(d.get("url"))
        if not e or e.get("tipo") != "convocatoria" or e.get("zona") not in ZONA_TELE or "plazo" in e or not d.get("fecha"): continue
        try: frases = frases_plazo(texto_disposicion(d["url"], red))
        except Exception: continue                   # la página no llega: mañana otra vez
        if not frases: e["plazo"] = None; continue
        ids = {f"p{i}": f for i, (f, _, _) in enumerate(frases)}
        try: r, _ = jev.preguntar({"convocatoria": d["texto"][:300], "frases": ids}, jev.preguntas_plazo(ids), pedir=pedir_jev)
        except (jev.SinRespuesta, ValueError): continue
        p = sorted(((r[i]["noul"], i) for i in ids if i in r), reverse=True)
        if not p or p[0][0] < jev.SI or (len(p) > 1 and p[1][0] >= 0.5): e["plazo"] = None; continue     # ninguna segura, o dos
        f, n, u = frases[int(p[0][1][1:])]
        hasta = None
        if desde_publicacion(f, d.get("boletin")):
            pub = dt.date.fromisoformat(d["fecha"])
            if inh is None: inh = set() if jev.COMPOSIO else inhabiles({pub.year, pub.year + 1}, red)   # en el sandbox no hace falta
            hasta = fin_plazo(pub, n, u, inh).isoformat()
        e["plazo"] = {"n": n, "unidad": u, "hasta": hasta}; hechas += 1
    return hechas


def resumen(t):
    """«Resolución de …, de la Dirección General …, por la que se convocan …» → «Convocan …» (como Empleo.resumen de la app)."""
    m = re.search(r"(?i),?\s+por (?:la|el) que(?:,? a propuesta de [^,]+,)? se\s+", t)
    r = t[m.end():] if m else t
    return (r[:1].upper() + r[1:]).rstrip(".")


def avisar(disps, et, hoy=None):
    """Las convocatorias de la zona, con su plazo si se sabe, para los avisos al móvil (las de plazo ya acabado, no)."""
    hoy = (hoy or dt.datetime.now(TZ).date()).isoformat()
    return [{"url": d["url"], "fecha": d.get("fecha"), "boletin": d.get("boletin"), "resumen": resumen(d["texto"])[:400],
             "hasta": (et[d["url"]].get("plazo") or {}).get("hasta")}
            for d in disps if d.get("url") in et and et[d["url"]].get("tipo") == "convocatoria" and et[d["url"]].get("zona") in ZONA_TELE
            and ((et[d["url"]].get("plazo") or {}).get("hasta") or hoy) >= hoy
            and not re.search(r"\b(?:don|doña|D\.|Dña\.)\s", d["texto"])]          # el repositorio es público: nada con nombres de personas


def etiquetar(disps, ya=None, pedir_jev=None):
    """{url: {"tipo", "provincia", "zona"}}; lo que ya estaba etiquetado (con zona) no se vuelve a preguntar."""
    ya = ya or {}; et = {}
    for d in disps:
        if not d.get("url"): continue
        if d["url"] in ya and "zona" in ya[d["url"]]: et[d["url"]] = dict(ya[d["url"]]); continue
        try: r, _ = jev.preguntar({"disposicion": {"boletin": d["boletin"], "texto": d["texto"][:1500]}}, jev.preguntas_sas(), pedir=pedir_jev)
        except (jev.SinRespuesta, ValueError): continue    # sin respuesta en la caché de Composio (o rara): mañana otra vez
        et[d["url"]] = {"tipo": r["tipo"]["choice"], "provincia": r["provincia"]["choice"], "zona": r["zona"]["choice"]}
    return et


def main():
    a = argparse.ArgumentParser(); a.add_argument("extras"); a.add_argument("--dias", type=int, default=7); o = a.parse_args()
    x = json.load(open(o.extras, encoding="utf-8"))
    disps = todas(o.dias)
    try: et = etiquetar(disps, ((x.get("sas") or {}).get("etiquetas") or {}))
    except jev.SinJev as e:
        print(json.dumps({"disposiciones": len(disps), "juez": f"sin Jev ({e})"}, ensure_ascii=False)); return
    try: n = plazos(disps, et)
    except jev.SinJev: n = 0
    x["sas"] = {"fecha": dt.datetime.now(TZ).date().isoformat(), "etiquetas": et, "avisar": avisar(disps, et)}
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    comun.guardar(o.extras, x)
    print(json.dumps({"disposiciones": len(disps), "etiquetas": len(et), "plazos": n, "juez": "Jev"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
