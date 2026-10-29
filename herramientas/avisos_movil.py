"""Avisos urgentes al móvil, sin la tele (tarea programada cada 2 horas). Solo lo que importa y solo una vez:

  - Aviso naranja o rojo de AEMET en la zona del pueblo (tierra o su costa), de hoy a pasado mañana.
  - Terremoto que se puede notar en el pueblo (IGN, últimos 10 días): magnitud 3 a menos de 50 km, 3,5 a menos de
    100 km o 4 a menos de 200 km.
  - Corte de agua o de luz anunciado en el pueblo: los apuntados en extras.json (redes del Ayuntamiento, por el buzón)
    y los titulares de Noticias de Almería (su robots.txt lo permite; Google Noticias y Diario de Almería, no). Si hay Jev
    (jev.py), Jev dice si el titular anuncia un corte en el pueblo; cuando duda, o sin Jev, la regla de texto de antes.
  - Corte de agua de Hidralia (su «Mapa de obras y afectaciones», la capa pública de cierres de Agbar): planificado o en curso,
    cuando empieza en las próximas 36 horas o ya ha empezado y no ha pasado su previsión de restablecimiento.
  - (3.7, lo pidió Isa el 29 oct 2026) Ofertas de empleo nuevas de la zona (zona.py: provincia de Almería sin el Levante, la costa de Granada
    hasta Motril, toda Andalucía): las de empleo público del SAE (su lista, en cada pasada), las de los entes de la Junta de la zona y las
    convocatorias del SAS de la zona (las dos, de extras.json «etiquetas.ofertas» y «sas.avisar», que pone la tarea diaria con Jev). La primera
    vez solo se apuntan las que ya había, sin avisar (salen en la tele).
  - (3.8, lo pidió Isa el 29 oct 2026) Noticias urgentes del pueblo: los mismos titulares de Noticias de Almería de las últimas 12 horas que Jev
    da por urgentes (algo que afecta ahora a la gente del pueblo: un incendio, una inundación, una carretera cortada, un desalojo, una alerta
    sanitaria), que no sean un corte (esos ya van aparte). Solo con Jev.
  - (3.8) Novedades de barco dragón de la Federación Andaluza de Piragüismo (extras.json «fap», fap.py en la tarea diaria): una competición
    nueva, o un cambio de fecha o de sede, una suspensión o un aplazamiento. La primera vez solo se apuntan.
  - (3.8) En las convocatorias del SAS, el último día del plazo de solicitudes si se sabe (sas.py lo calcula con el calendario de la Junta).

  python3 avisos_movil.py --estado avisos_enviados.json [--extras extras.json] [--lugar Adra --ine 04003 --lat 36.7489 --lon -3.0206]

Imprime una línea JSON: {"nuevos": [{"tipo", "texto", "enlace", "clave"}], "fallos": […], "guardar": bool} y apunta en --estado lo enviado
(se olvida a los 30 días), para no repetirlo; «guardar» dice si --estado ha cambiado (también sin nada nuevo: lo que se olvida y las ofertas
que se apuntan la primera vez), para subirlo. Sale con 0 aunque falle alguna fuente; con 2 si fallan todas.
"""
import argparse, datetime as dt, gzip, io, json, math, os, re, sys, tarfile, unicodedata, urllib.parse, urllib.request
from xml.etree import ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # jev.py, al lado (con -I no se mira la carpeta del script)
import jev, zona
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
LUGAR = "Adra"                       # el pueblo de la tele (también el del sandbox de Composio, composio_jev.py)
UA = "TiempoYRadar/1.0 (avisos personales al movil)"
AEMET = "https://www.aemet.es"
IGN = "https://www.ign.es/web/ign/portal/ultimos-terremotos/-/ultimos-terremotos/get10dias"
NDA = ["https://www.noticiasdealmeria.com/rss/seccion/65/"]
CIERRES = "https://services3.arcgis.com/5VitVYyVLQYnzXCo/arcgis/rest/services/Cierres_webPublicas_v/FeatureServer/0/query"
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


def piezas_rss(xml, lugar, desde):
    """Las noticias del RSS que nombran el pueblo (título o entradilla), publicadas desde «desde»."""
    res, raiz = [], ET.fromstring(xml)
    for it in raiz.iter("item"):
        tit = (it.findtext("title") or "").strip()
        ent = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it.findtext("description") or "")).strip()[:700]
        if not re.search(r"\b" + re.escape(sin_tildes(lugar)) + r"\b", sin_tildes(tit + " " + ent)): continue
        try: s = dt.datetime.strptime((it.findtext("pubDate") or "").strip(), "%a, %d %b %Y %H:%M:%S %z")
        except ValueError: s = None
        if s and s < desde: continue
        res.append({"titulo": tit, "entradilla": ent, "enlace": (it.findtext("link") or "").strip(), "s": s})
    return res


class Juez:
    """Jev para los titulares (una petición por titular); sin Jev (sin clave o sin red), la regla de texto. «usado» dice cuál fue."""
    def __init__(self, pedir=None):
        self.pedir, self.activo, self.usado, self.motivo = pedir, True, "reglas", ""
        self.urgentes = []           # 3.8: las noticias urgentes del pueblo que no son cortes (se ven en la misma petición)

    def corte(self, lugar, p):
        regla = tipo_corte(p["titulo"])
        if self.activo:
            try:
                r, _ = jev.preguntar({"pueblo": lugar, "noticia": {"titulo": p["titulo"], "entradilla": p["entradilla"]}},
                                     jev.preguntas_corte(), pedir=self.pedir)
                self.usado = "Jev"
                return jev.es_corte(r, regla), r
            except jev.SinRespuesta:
                return regla, None                             # este titular no estaba en la caché de Composio: la regla
            except jev.SinJev as e:
                self.activo, self.motivo = False, str(e)       # una vez sin Jev, el resto con la regla (no se insiste)
        return regla, None


URGENTE_H = 12      # una noticia urgente de hace más de 12 horas ya no se manda


def es_urgente(r, p, ahora):
    return (r and "urgente" in r and r["urgente"]["noul"] >= jev.URGENTE and r["restablecido"]["noul"] < jev.SI
            and p.get("s") and ahora - p["s"] <= dt.timedelta(hours=URGENTE_H))


def cortes_rss(xml, lugar, desde, juez=None, ahora=None):
    """Sin juez, solo la regla de texto."""
    res, ahora = [], ahora or dt.datetime.now(TZ)
    for p in piezas_rss(xml, lugar, desde):
        tipo, r = juez.corte(lugar, p) if juez else (tipo_corte(p["titulo"]), None)
        if tipo: res.append({"tipo": tipo, "titulo": p["titulo"], "enlace": p["enlace"], "fuente": "Noticias de Almería"})
        elif juez and es_urgente(r, p, ahora):
            juez.urgentes.append({"titulo": p["titulo"], "enlace": p["enlace"], "fuente": "Noticias de Almería"})
    return res


def cortes_titulares(lugar, ahora, juez, fallos):
    """Los titulares de los dos últimos días (también lo que hace composio_jev.py en el sandbox, para que las preguntas sean las mismas)."""
    cortes, bien = [], 0
    for u in NDA:
        try: cortes += cortes_rss(pedir(u), lugar, ahora - dt.timedelta(days=2), juez, ahora); bien += 1
        except Exception as e: fallos.append(f"Noticias de Almería: {e}")
    return cortes, bien


# ------------------------------------------------------------------ cortes de agua de Hidralia (lo mismo que CortesAgua.kt de la app)
def url_cierres(ine):
    donde = f"COD_MUNI='{ine}' AND CI_ESTADO IN ('4AP','5EC')"
    return (CIERRES + "?where=" + urllib.parse.quote_plus(donde) + "&outFields=CI_ID,CI_FH_INI_PREV,CI_FH_FIN_PREV,CI_CALLES,CI_DIRECCION,CI_ESTADO,CI_MOTIVO"
            "&returnGeometry=false&orderByFields=CI_FH_INI_PREV&f=json")


def calle_cierre(d):   # «Camino de Mateo 1-3, 04770, Adra, Almería, Andalucía» → «Camino de Mateo 1-3»
    d = (d or "").strip()
    c = re.sub(r"\b(\d+[A-Za-z]?)-\1\b", r"\1", d.split(",")[0].strip())
    b = re.search(r"\(([^()]+)\)\s*$", d)
    return f"{c} ({b.group(1).strip()})" if b and b.group(1).strip() not in c else c


def otras_calles(s):
    t = (s or "").strip().rstrip(",.").strip()
    if not t or t.lower() == "null": return ""
    return f" y calles {t.lower()}" if re.fullmatch(r"(?i)colindantes|adyacentes", t) else f" (también {t})"


def hora(d): return f"{d.hour}:{d.minute:02d}"


def cortes_hidralia(js, ine, ahora, horas=36):
    x = json.loads(js)
    if "error" in x: raise ValueError(x["error"].get("message", "error"))
    res = []
    for f in x.get("features", []):
        a = f.get("attributes") or {}
        if a.get("CI_ESTADO") not in ("4AP", "5EC") or not a.get("CI_FH_INI_PREV"): continue
        ini = dt.datetime.fromtimestamp(a["CI_FH_INI_PREV"] / 1000, TZ)
        fin = dt.datetime.fromtimestamp(a["CI_FH_FIN_PREV"] / 1000, TZ) if a.get("CI_FH_FIN_PREV") and a["CI_FH_FIN_PREV"] >= a["CI_FH_INI_PREV"] else None
        if (fin or ini) < ahora or ini > ahora + dt.timedelta(hours=horas): continue   # ya pasó su previsión (el visor no lo cierra) o falta mucho
        sitio = calle_cierre(a.get("CI_DIRECCION")) + otras_calles(a.get("CI_CALLES"))
        if ini <= ahora: cuando_ = "ahora" + (f", hasta {cuando(fin.isoformat(), ahora)} (previsión)" if fin else "")
        else:
            dias = (ini.date() - ahora.date()).days
            dia = "hoy" if dias == 0 else "mañana" if dias == 1 else f"el {DIAS[ini.weekday()]} {ini.day}"
            cuando_ = f"{dia} de {hora(ini)} a {hora(fin)}" if fin and fin.date() == ini.date() else f"{cuando(ini.isoformat(), ahora)}" + (f" hasta {cuando(fin.isoformat(), ahora)}" if fin else "")
        motivo = "avería" if a.get("CI_MOTIVO") == "AVE" else "obras de mejora del servicio"
        res.append({"tipo": "agua", "titulo": sitio, "fuente": "Hidralia", "clave": f"hidralia:{a.get('CI_ID')}",
                    "enlace": f"https://gisaguapublic.agbar.net/?municipio_id={ine}&cierre_id={a.get('CI_ID')}",
                    "texto": f"Corte de agua (Hidralia) {cuando_} en {sitio}: {motivo}."})
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
        k = c.get("clave") or "corte:" + (c.get("enlace") or c["titulo"])
        if k in estado: continue
        out.append({"tipo": "corte", "clave": k, "enlace": c.get("enlace", ""), "texto": c.get("texto") or f"Corte de {c['tipo']} anunciado: {c['titulo']} ({c['fuente']})."})
    return out


# ------------------------------------------------------------------ ofertas de empleo nuevas de la zona (3.7)
MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_dia(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{DIAS[d.weekday()]} {d.day} {MES[d.month - 1]}"


def hasta(iso):
    try: d = dt.date.fromisoformat((iso or "")[:10])
    except ValueError: return ""
    return f" · hasta el {d.day} {MES[d.month - 1]}"


def frase(t):
    """Lo que el SAE da en mayúsculas, como una frase (como frase() de la tele)."""
    t = re.sub(r"\s+", " ", t or "").strip()
    if re.search(r"[a-záéíóúñ]", t): return t
    t = t.lower(); t = t[:1].upper() + t[1:]
    t = re.sub(r"([.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
    return re.sub(r"\b[abc][12]\b", lambda m: m.group(0).upper(), t)


COLECTIVO = {"garantia_juvenil": "Garantía Juvenil", "mayores_45": "mayores de 45", "parados_larga": "parados de larga duración",
             "discapacidad": "personas con discapacidad", "programa_empleo": "programa de empleo y formación"}


def colectivo(e):
    c = COLECTIVO.get((e or {}).get("colectivo"))
    return f" · solo {c}" if c and c != COLECTIVO["programa_empleo"] else f" · {c}" if c else ""


def plazo_sas(d):
    h = d.get("hasta")
    return hasta(h).replace(" · hasta el", " · solicitudes hasta el") if h else ""


def ofertas(estado, sae, x, ahora):
    """Las ofertas de empleo de la zona que no se han avisado aún. La primera vez que llega cada lista (SAE, Junta, SAS), ninguna: se apuntan."""
    hoy = ahora.date().isoformat(); out = []
    et_sae = ((x.get("etiquetas") or {}).get("sae")) or {}
    for o in sae:
        out.append({"tipo": "empleo", "clave": "empleo:sae:" + o["id"], "enlace": o["url"],
                    "texto": f"💼 Empleo público (SAE): {frase(o['puesto'])} · {', '.join(o['sitios'][:3])}{hasta(o['hasta'])}{colectivo(et_sae.get(o['id']))}."})
    for i, e in (((x.get("etiquetas") or {}).get("ofertas")) or {}).items():
        if not e.get("zona") or not e.get("puesto") or (e.get("hasta") and e["hasta"] < hoy): continue
        out.append({"tipo": "empleo", "clave": "empleo:junta:" + i, "texto": f"💼 Oferta de la Junta ({e.get('entidad') or 'ente instrumental'}): {e['puesto']}{hasta(e.get('hasta'))}{colectivo(e)}.",
                    "enlace": f"https://www.juntadeandalucia.es/organismos/transparencia/empleo-publico/entidades-instrumentales/ofertas-empleo/detalle/{i}.html"})
    for d in (((x.get("sas") or {}).get("avisar")) or []):
        r = d.get("resumen") or ""
        out.append({"tipo": "empleo", "clave": "empleo:sas:" + d["url"], "enlace": d["url"],
                    "texto": f"💼 SAS, convocatoria ({d.get('boletin') or 'BOJA'}): {r[:180] + ('…' if len(r) > 180 else '')}{plazo_sas(d)}."})
    # 3.8: las novedades de barco dragón de la Federación Andaluza de Piragüismo
    for n in (((x.get("fap") or {}).get("novedades")) or []):
        if n.get("dia") and n["dia"] < hoy: continue
        dia = f" · {fecha_dia(n['dia'])}" if n.get("dia") else ""
        lugar = f" en {n['lugar']}" if n.get("lugar") else ""
        ins = f" · inscripción hasta el {fecha_dia(n['inscripcion'])}" if n.get("inscripcion") and n["inscripcion"] >= hoy else ""
        out.append({"tipo": "regata", "clave": "fap:" + n["enlace"], "enlace": n["enlace"],
                    "texto": f"🐉 Barco dragón (Federación Andaluza{', cambio' if n.get('cambio') else ''}): {n['titulo']}{dia}{lugar}{ins}."})
    res = []
    for pre in ("empleo:sae:", "empleo:junta:", "empleo:sas:", "fap:"):    # cada lista, la primera vez que llega, solo se apunta
        primera = pre not in estado                                      # la marca de la lista (se renueva: no se olvida)
        for o in out:
            if not o["clave"].startswith(pre) or o["clave"] in estado: continue
            if primera: estado[o["clave"]] = ahora.isoformat(timespec="minutes")
            else: res.append(o)
        if primera and not any(o["clave"].startswith(pre) for o in out): continue   # sin nada aún de esa lista: se espera a que llegue
        estado[pre] = ahora.date().isoformat()
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--estado", required=True); p.add_argument("--extras", default="extras.json")
    p.add_argument("--lugar", default=LUGAR); p.add_argument("--ine", default="04003")
    p.add_argument("--lat", type=float, default=36.7489); p.add_argument("--lon", type=float, default=-3.0206)
    o = p.parse_args()
    ahora = dt.datetime.now(TZ)
    try:
        with open(o.estado, encoding="utf-8") as f: estado = json.load(f)
    except FileNotFoundError:
        estado = {}
    antes = json.dumps(estado, sort_keys=True)
    fallos, aemet, sismos, cortes, bien, x = [], [], [], [], 0, {}
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
    juez = Juez()
    c, b = cortes_titulares(o.lugar, ahora, juez, fallos); cortes += c; bien += b
    try: cortes += cortes_hidralia(pedir(url_cierres(o.ine)).decode("utf-8"), o.ine, ahora); bien += 1
    except Exception as e: fallos.append(f"Hidralia: {e}")
    n = nuevos(estado, aemet, sismos, cortes, ahora)
    for u in juez.urgentes:                                  # 3.8: noticias urgentes del pueblo (solo con Jev)
        k = "urgente:" + u["enlace"]
        if k not in estado and k not in {a["clave"] for a in n}:
            n.append({"tipo": "noticia", "clave": k, "enlace": u["enlace"], "texto": f"📰 Urgente en {o.lugar}: {u['titulo']} ({u['fuente']})."})
    sae = []
    try: sae = zona.ofertas_sae(zona.lista_sae(), ahora) if zona.aplica(o.ine) else []; bien += 1
    except Exception as e: fallos.append(f"ofertas del SAE: {e}"[:160])      # las demás listas (Junta, SAS, FAP) siguen
    try: n += ofertas(estado, sae, x if isinstance(x, dict) else {}, ahora)
    except Exception as e: fallos.append(f"ofertas de empleo: {e}"[:160])
    for a in n: estado[a["clave"]] = ahora.isoformat(timespec="minutes")
    limite = (ahora - dt.timedelta(days=30)).isoformat()
    estado = {k: v for k, v in estado.items() if v >= limite}
    with open(o.estado, "w", encoding="utf-8") as f: json.dump(estado, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({"nuevos": n, "fallos": fallos, "titulares": juez.usado + (f" ({juez.motivo})" if juez.motivo else ""),
                      "guardar": json.dumps(estado, sort_keys=True) != antes}, ensure_ascii=False))
    sys.exit(0 if bien else 2)


if __name__ == "__main__":
    main()
