"""Las disposiciones del Servicio Andaluz de Salud de la pantalla SAS de la tele, etiquetadas con Jev (tarea diaria, con diario.py).

La tele lee sola el BOJA (sección 2.2) y el BOE de los últimos 7 días y enseña lo que nombra al SAS (Empleo.kt). Aquí se leen los
mismos boletines (igual que la tele) y Jev dice de cada disposición qué es (convocatoria, lista provisional o definitiva, nombramiento,
cese, bolsa, traslado u otra) y a qué provincia toca (Almería, toda Andalucía, otra o no consta). Va en extras.json «sas»:
{"fecha", "etiquetas": {url: {"tipo", "provincia"}}}; la tele pone la etiqueta y ordena primero lo de Almería y lo de toda Andalucía.
Sin Jev no toca nada (la tele sigue con su regla de palabras).

  python3 -I herramientas/sas.py extras.json [--dias 7]
"""
import argparse, datetime as dt, html, json, os, re, sys, urllib.error, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

TZ = ZoneInfo("Europe/Madrid")
JUNTA = "https://www.juntadeandalucia.es"
UA = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app (la Junta y el BOE lo aceptan así)


def pedir(url, aceptar=None, timeout=40):
    cab = {"User-Agent": UA} | ({"Accept": aceptar} if aceptar else {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


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


def todas(dias=7, hoy=None):
    hoy = hoy or dt.datetime.now(TZ).date(); out = []
    for ruta, fecha in boletines(pedir(f"{JUNTA}/ssdigitales/datasets/contentapi/boja/calendario?fechaDesde=now-{dias}d&fechaHasta=now")):
        base = f"{JUNTA}/eboja/{ruta}/"
        try: out += [d | {"boletin": "BOJA"} for d in disposiciones_boja(pedir(base + "s53.html"), base)]
        except urllib.error.HTTPError as e:
            if e.code != 404: raise                       # ese día no hubo sección 2.2
    for k in range(dias):
        d = hoy - dt.timedelta(days=k)
        try: out += [x | {"boletin": "BOE"} for x in sumario_boe(pedir(f"https://www.boe.es/datosabiertos/api/boe/sumario/{d:%Y%m%d}", "application/json"))]
        except urllib.error.HTTPError as e:
            if e.code != 404: raise                       # domingos y festivos no hay BOE
    return out


def etiquetar(disps, ya=None, pedir_jev=None):
    """{url: {"tipo", "provincia"}}; lo que ya estaba etiquetado no se vuelve a preguntar."""
    ya = ya or {}; et = {}
    for d in disps:
        if not d.get("url"): continue
        if d["url"] in ya: et[d["url"]] = ya[d["url"]]; continue
        try: r, _ = jev.preguntar({"disposicion": {"boletin": d["boletin"], "texto": d["texto"][:1500]}}, jev.preguntas_sas(), pedir=pedir_jev)
        except jev.SinRespuesta: continue          # sin respuesta en la caché de Composio: mañana se pregunta otra vez
        et[d["url"]] = {"tipo": r["tipo"]["choice"], "provincia": r["provincia"]["choice"]}
    return et


def main():
    a = argparse.ArgumentParser(); a.add_argument("extras"); a.add_argument("--dias", type=int, default=7); o = a.parse_args()
    x = json.load(open(o.extras, encoding="utf-8"))
    disps = todas(o.dias)
    try: et = etiquetar(disps, ((x.get("sas") or {}).get("etiquetas") or {}))
    except jev.SinJev as e:
        print(json.dumps({"disposiciones": len(disps), "juez": f"sin Jev ({e})"}, ensure_ascii=False)); return
    x["sas"] = {"fecha": dt.datetime.now(TZ).date().isoformat(), "etiquetas": et}
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"disposiciones": len(disps), "etiquetas": len(et), "juez": "Jev"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
