"""Avisos urgentes al móvil, sin la tele (tarea programada cada 2 horas). Solo lo que importa y solo una vez:

  - Aviso naranja o rojo de AEMET en la zona del pueblo (tierra o su costa), de hoy a pasado mañana.
  - Terremoto que se puede notar en el pueblo (IGN, últimos 10 días): magnitud 3 a menos de 50 km, 3,5 a menos de
    100 km o 4 a menos de 200 km.
  - Corte de agua o de luz anunciado en el pueblo: los apuntados en extras.json (redes del Ayuntamiento, por el buzón)
    y los titulares de Noticias de Almería (su robots.txt lo permite; Google Noticias y Diario de Almería, no).

  python3 avisos_movil.py --estado avisos_enviados.json [--extras extras.json] [--lugar Adra --ine 04003 --lat 36.7489 --lon -3.0206]

Imprime una línea JSON: {"nuevos": [{"tipo", "texto", "enlace", "clave"}], "fallos": […]} y apunta en --estado lo enviado
(se olvida a los 30 días), para no repetirlo. Sale con 0 aunque falle alguna fuente; con 2 si fallan todas.
"""
import argparse, datetime as dt, gzip, io, json, math, re, sys, tarfile, unicodedata, urllib.request
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
UA = "TiempoYRadar/1.0 (avisos personales al movil)"
AEMET = "https://www.aemet.es"
IGN = "https://www.ign.es/web/ign/portal/ultimos-terremotos/-/ultimos-terremotos/get10dias"
NDA = ["https://www.noticiasdealmeria.com/rss/seccion/65/"]
FENOMENOS = {"PR": "lluvias", "TO": "tormentas", "VI": "viento", "CO": "fenómenos costeros", "NE": "nevadas", "AT": "temperaturas máximas",
             "TA": "temperaturas máximas", "BT": "temperaturas mínimas", "TI": "temperaturas mínimas", "NI": "nieblas", "PO": "polvo en suspensión",
             "RM": "rachas de viento", "GL": "galernas", "AL": "aludes"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def pedir(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read()


def sin_tildes(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


# ------------------------------------------------------------------ AEMET
def contiene(geom, x, y):
    if not geom: return False
    polis = [geom["coordinates"]] if geom.get("type") == "Polygon" else geom.get("coordinates", []) if geom.get("type") == "MultiPolygon" else []
    for poly in polis:
        anillo, dentro, j = poly[0], False, len(poly[0]) - 1
        for i in range(len(anillo)):
            (xi, yi), (xj, yj) = anillo[i][:2], anillo[j][:2]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: dentro = not dentro
            j = i
        if dentro: return True
    return False


def avisos_aemet(features, lon, lat, ahora):
    """Avisos naranja o rojo de la zona que contiene el punto o de su costa (como hace la tele)."""
    tierra = {f["properties"].get("Nombre_zona", "").lower() for f in features if contiene(f.get("geometry"), lon, lat)}
    res, vistos = [], set()
    for f in features:
        pr = f.get("properties") or {}
        z = pr.get("Nombre_zona", ""); zl = z.lower()
        mia = contiene(f.get("geometry"), lon, lat) or ("costa" in zl and any(t in zl or zl.replace(" - costa", "").replace("costa - ", "") in t for t in tierra if t))
        if not mia: continue
        for k, lista in pr.items():
            if not k.startswith("Avis_"): continue
            for a in lista or []:
                color = (a.get("severity") or "").lower()
                if color not in ("naranja", "rojo"): continue
                try: hasta = dt.datetime.fromisoformat(a.get("expires_local"))
                except Exception: hasta = None
                if hasta and hasta < ahora: continue
                codigo = a.get("code") or f"{k}{z}{a.get('onset_local')}"
                if codigo in vistos: continue
                vistos.add(codigo)
                res.append({"codigo": codigo, "color": color, "fenomeno": FENOMENOS.get(a.get("parametro")) or FENOMENOS.get(a.get("fenomeno")) or a.get("fenomeno", ""),
                            "descripcion": a.get("descripcion", ""), "zona": z, "desde": a.get("onset_local"), "hasta": a.get("expires_local")})
    return res


def leer_aemet(lon, lat, ahora):
    pag = pedir(AEMET + "/es/eltiempo/prediccion/avisos").decode("utf-8", "replace")
    m = re.search(r"/es/geojson/download/avisos/geojson_\d+\.tar\.gz", pag)
    if not m: raise IOError("AEMET: no encuentro el paquete de avisos")
    t = tarfile.open(fileobj=io.BytesIO(pedir(AEMET + m.group(0))), mode="r:gz")
    feats = []
    for mi in t.getmembers():
        n = mi.name.rsplit("/", 1)[-1]
        if re.match(r"r_D\+[012]_", n) and "_penbal_" in n:
            feats += json.load(t.extractfile(mi)).get("features", [])
    return avisos_aemet(feats, lon, lat, ahora)


def cuando(iso, ahora):
    d = dt.datetime.fromisoformat(iso).astimezone(TZ)
    dias = (d.date() - ahora.date()).days
    dia = "hoy" if dias == 0 else "mañana" if dias == 1 else f"el {DIAS[d.weekday()]} {d.day}"
    return f"{dia} a las {d.hour}:{d.minute:02d}"


# ------------------------------------------------------------------ IGN
FILA = re.compile(r'<td>(es\w+)</td>\s*<td>([\d/]+)</td>\s*<td>([\d:]+)</td>\s*<td>([\d:]+)</td>\s*<td class="tar">([-\d.]+)</td>\s*'
                  r'<td class="tar">([-\d.]+)</td>\s*<td class="tar">([-\d.]+)\s*</td>\s*<td class="tar">([-\d.]+)\s*</td>\s*'
                  r'<td class="tac">[^<]*</td>\s*<td class="tac">([^<]*)</td>\s*<td class="tal">([^<]*)</td>')


def km(lat0, lon0, lat, lon):
    return math.hypot((lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * 110.57)


def se_nota(mag, d):
    return (mag >= 3 and d <= 50) or (mag >= 3.5 and d <= 100) or (mag >= 4 and d <= 200)


def terremotos(html, lat, lon):
    res = []
    for g in FILA.findall(html):
        d, mag = km(lat, lon, float(g[4]), float(g[5])), float(g[7])
        if not se_nota(mag, d): continue
        utc = dt.datetime.strptime(g[1] + " " + g[2], "%d/%m/%Y %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        res.append({"evid": g[0], "mag": mag, "km": round(d), "lugar": g[9].strip(), "hora": utc.astimezone(TZ),
                    "url": f"https://www.ign.es/web/ign/portal/ultimos-terremotos/-/ultimos-terremotos/getDetails?evid={g[0]}"})
    return res


def lugar_ign(t):   # «SE GÓJAR.GR» → «Gójar (GR)»
    t = re.sub(r"^(N|S|E|W|O|NE|NW|SE|SW|NO|SO)\s+", "", t.strip())
    nom, _, prov = t.partition(".")
    return nom.title() + (f" ({prov})" if prov else "")


# ------------------------------------------------------------------ cortes de agua y luz
CORTES = [("agua", re.compile(r"\bcortes? (de|del|en el) (suministro (de|del) )?agua\b|\bcort(a|an|ara|aran|ar)\b[^.:;]{0,30}\b(suministro de agua|el agua)\b"
                              r"|\binterrupcion(es)? (de|del) (suministro (de|del) )?agua\b|\bsuministro de agua\b[^.:;]{0,30}\b(cortad|interrump|suspend)")),
          ("luz", re.compile(r"\bcortes? (de|del) (luz|suministro electrico|electricidad)\b|\bapagon(es)?\b|\binterrupcion(es)? del suministro electrico\b"))]
YA_NO = re.compile(r"\brestablec|\bfin (a|de) (los|las) (cortes|restricciones)|\bvuelve la normalidad|\bsin cortes\b")


def tipo_corte(titulo):
    t = sin_tildes(titulo)
    if YA_NO.search(t): return None
    return next((k for k, r in CORTES if r.search(t)), None)


def cortes_rss(xml, lugar, desde):
    res, raiz = [], ET.fromstring(xml)
    for it in raiz.iter("item"):
        tit = (it.findtext("title") or "").strip(); txt = tit + " " + re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        if not re.search(r"\b" + re.escape(sin_tildes(lugar)) + r"\b", sin_tildes(txt)): continue
        tipo = tipo_corte(tit)
        if not tipo: continue
        try: s = dt.datetime.strptime((it.findtext("pubDate") or "").strip(), "%a, %d %b %Y %H:%M:%S %z")
        except ValueError: s = None
        if s and s < desde: continue
        res.append({"tipo": tipo, "titulo": tit, "enlace": (it.findtext("link") or "").strip(), "fuente": "Noticias de Almería"})
    return res


# ------------------------------------------------------------------ todo junto
def nuevos(estado, aemet, sismos, cortes, ahora):
    out = []
    for a in aemet:
        k = "aemet:" + a["codigo"]
        if k in estado: continue
        out.append({"tipo": "aviso", "clave": k, "enlace": "https://www.aemet.es/es/eltiempo/prediccion/avisos",
                    "texto": f"⚠ Aviso {a['color']} de AEMET por {a['fenomeno']} en {a['zona']}, {cuando(a['desde'], ahora)} hasta {cuando(a['hasta'], ahora)}: {a['descripcion']}".strip()})
    for s in sismos:
        k = "ign:" + s["evid"]
        if k in estado or ahora - s["hora"] > dt.timedelta(hours=24): continue
        mag = f"{s['mag']:.1f}".replace(".", ",")
        out.append({"tipo": "terremoto", "clave": k, "enlace": s["url"],
                    "texto": f"Terremoto de magnitud {mag} a {s['km']} km, {lugar_ign(s['lugar'])}, {cuando(s['hora'].isoformat(), ahora)} (IGN)."})
    for c in cortes:
        k = "corte:" + (c.get("enlace") or c["titulo"])
        if k in estado: continue
        out.append({"tipo": "corte", "clave": k, "enlace": c.get("enlace", ""), "texto": f"Corte de {c['tipo']} anunciado: {c['titulo']} ({c['fuente']})."})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--estado", required=True); p.add_argument("--extras", default="extras.json")
    p.add_argument("--lugar", default="Adra"); p.add_argument("--ine", default="04003")
    p.add_argument("--lat", type=float, default=36.7489); p.add_argument("--lon", type=float, default=-3.0206)
    o = p.parse_args()
    ahora = dt.datetime.now(TZ)
    try:
        with open(o.estado, encoding="utf-8") as f: estado = json.load(f)
    except FileNotFoundError:
        estado = {}
    fallos, aemet, sismos, cortes, bien = [], [], [], [], 0
    try: aemet = leer_aemet(o.lon, o.lat, ahora); bien += 1
    except Exception as e: fallos.append(f"AEMET: {e}")
    try: sismos = terremotos(pedir(IGN).decode("utf-8", "replace"), o.lat, o.lon); bien += 1
    except Exception as e: fallos.append(f"IGN: {e}")
    try:
        with open(o.extras, encoding="utf-8") as f: x = json.load(f)
        hoy = ahora.date().isoformat()
        cortes += [{"tipo": c["tipo"], "titulo": c["titulo"], "enlace": c.get("enlace", ""), "fuente": c.get("fuente", "Ayuntamiento")}
                   for c in x.get("cortes", []) if c.get("tipo") in ("agua", "luz") and c.get("ine", o.ine) == o.ine and c.get("hasta", hoy) >= hoy]
        bien += 1
    except Exception as e: fallos.append(f"extras.json: {e}")
    for u in NDA:
        try: cortes += cortes_rss(pedir(u), o.lugar, ahora - dt.timedelta(days=2)); bien += 1
        except Exception as e: fallos.append(f"Noticias de Almería: {e}")
    n = nuevos(estado, aemet, sismos, cortes, ahora)
    for x in n: estado[x["clave"]] = ahora.isoformat(timespec="minutes")
    limite = (ahora - dt.timedelta(days=30)).isoformat()
    estado = {k: v for k, v in estado.items() if v >= limite}
    with open(o.estado, "w", encoding="utf-8") as f: json.dump(estado, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({"nuevos": n, "fallos": fallos}, ensure_ascii=False))
    sys.exit(0 if bien else 2)


if __name__ == "__main__":
    main()
