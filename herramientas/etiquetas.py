"""Etiquetas para lo que la tele enseña por su cuenta (tarea diaria, con diario.py): lo que se puede saber con exactitud, en el código; lo que
hay que entender del texto, con Jev (jev.py). Se leen las mismas listas que lee la tele y se guarda en extras.json «etiquetas», por clave:

  - «alim» {enlace de la ficha de la AESAN: {"alergeno"}}: el alérgeno no declarado de cada alerta alimentaria (Jev, de los 14 obligatorios).
  - «med» {código de la AEMPS: {"sinReceta", "devolver"}}: si se vende sin receta lo dice la base oficial de medicamentos CIMA (por el número
    de registro de cada medicamento); si hay que devolver los de casa, Jev con el texto de la medida.
  - «prod» {id de Safety Gate: {"ninos"}}: si es para niños: los juguetes y artículos de puericultura por su categoría; los demás, Jev.
  - «ofertas» {id de la oferta de la Junta: {"nivel", "experiencia"}}: la titulación mínima y si la experiencia es requisito (Jev, con la ficha).
Y en extras.json mismo: la agenda sin la misma actividad apuntada dos veces (Jev compara las del mismo día) y en cada sorteo cómo se participa
(«participa», una etiqueta de una lista fija). Sin Jev, solo lo exacto (sin receta, categoría de juguetes) y no toca la agenda ni los sorteos.
Lo ya etiquetado no se vuelve a preguntar; lo que la tele ya no enseña se olvida.

  python3 -I herramientas/etiquetas.py extras.json
"""
import datetime as dt, html, json, os, re, sys, urllib.error, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

TZ = ZoneInfo("Europe/Madrid")
UA = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def pedir(url, cuerpo=None, tipo=None, timeout=60):
    cab = {"User-Agent": UA} | ({"Content-Type": tipo} if tipo else {})
    with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def limpio(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


# ------------------------------------------------------------------ AESAN (como Alimentarias.kt)
AESAN = "https://www.aesan.gob.es"
BLOQUES = {"general": ("alertas-alimentarias-de-interes-para-toda-la-poblacion", 7),
           "complementos": ("alertas-alimentarias-para-personas-que-consumen-complementos-alimenticios", 30),
           "alergias": ("alertas-alimentarias-para-personas-con-alergias-intolerancias", 30)}


def fecha_aesan(s):
    m = re.search(r"(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+(\d{4})", s)
    if not m or m.group(2).lower() not in MESES: return None
    try: return dt.date(int(m.group(3)), MESES.index(m.group(2).lower()) + 1, int(m.group(1)))
    except ValueError: return None


def alertas_aesan(h, hoy):
    """[(enlace completo, título)] de las que enseña la tele: hasta 5 por bloque y 10 en total."""
    out = []
    for tipo, (ancla, dias) in BLOQUES.items():
        ini = h.find(ancla)
        if ini < 0: continue
        fin = h.find('class="text-block ', ini + 60); bloque = h[ini:fin if fin > 0 else len(h)]
        n = 0
        for m in re.finditer(r'(?s)<a class="seeMoreCardSlide[^"]*" href="([^"]+)" title="([^"]+)">.*?seeMoreCard-heading__value">([^<]+)<', bloque):
            f = fecha_aesan(m.group(3))
            if f and f >= hoy - dt.timedelta(days=dias) and n < 5:
                out.append((AESAN + m.group(1), html.unescape(m.group(2)).strip())); n += 1
    return out[:10]


# ------------------------------------------------------------------ AEMPS (como Consumo.kt)
AEMPS = "https://www.aemps.gob.es/comunicacion/alertas/alertas-farmaceuticas-y-retiradas-de-lotes-de-medicamentos-de-uso-humano-por-defectos-de-calidad/"


def lista_aemps(h):
    i = h.find("normalizedData")
    if i < 0: raise ValueError("AEMPS: la página no trae la lista")
    return json.JSONDecoder().raw_decode(h[h.index("[", i):])[0]


def llega_a_farmacias(a):
    if a.get("product") == "Sustancia activa": return False
    d = (a.get("distributionInformation") or "").lower()
    return "dispensaci" in d or not ("hospital" in d or "centros médicos" in d or "clínica" in d)


def medicamentos_aemps(h, hoy, dias=45):
    dia = lambda ms: dt.datetime.fromtimestamp(ms / 1000, TZ).date()
    L = [a for a in lista_aemps(h) if a.get("date") and hoy - dt.timedelta(days=dias) <= dia(a["date"]) <= hoy and llega_a_farmacias(a)]
    return sorted(L, key=lambda a: -a["date"])[:10]


def sin_receta(registros, consultar=None):
    """True si alguna presentación se vende sin receta según CIMA; False si todas piden receta; None si CIMA no lo sabe.
    El campo «cn» de la lista de la AEMPS es el número de registro del medicamento (61201, 1251964002), no el código nacional."""
    consultar = consultar or (lambda n: json.loads(pedir(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={n}", timeout=30)))
    vistos = []
    for n in registros:
        if not re.fullmatch(r"\d{4,12}", str(n or "")): continue
        try: vistos.append(consultar(n).get("receta"))
        except (urllib.error.URLError, ValueError, TimeoutError): continue
    vistos = [v for v in vistos if isinstance(v, bool)]
    return (False in vistos) if vistos else None


# ------------------------------------------------------------------ Safety Gate (como Consumo.kt)
SG = "https://ec.europa.eu/safety-gate-alerts/public/api"
DE_NINOS = re.compile(r"(?i)toys|childcare|juguete|puericultura")


def cuerpo_sg(anios, n=20):
    return json.dumps({"criteria": {"notifyingCountry": ["ES"], "year": anios}, "searchCriteriaForNotification": False, "isLaunched": True,
                       "isLaunchSearch": True, "pagination": {"numberElements": n, "page": 0, "sortField": "PUBLICATION_DATE", "sortOrder": "DESC",
                       "totalElements": 0}, "language": "es", "displayDefaultResults": False, "isForMostRecent": False}).encode()


def productos_sg(js, hoy, dias=90):
    out = []
    for x in js.get("content") or []:
        try: f = dt.datetime.fromisoformat(x["publicationDate"].replace("Z", "+00:00")).astimezone(TZ).date()
        except (KeyError, ValueError): continue
        if f >= hoy - dt.timedelta(days=dias): out.append({"id": str(x["id"]), "producto": limpio((x.get("product") or {}).get("name"))})
    return out[:10]


def ficha_sg(d):
    p = d.get("product") or {}
    desc = next((limpio(v.get("description")) for v in p.get("versions") or [] if (v.get("language") or {}).get("key") == "ES"), "")
    return {"categoria": (p.get("productCategory") or {}).get("key", ""), "descripcion": desc[:600]}


# ------------------------------------------------------------------ ofertas de la Junta (como Empleo.kt)
JUNTA = "https://www.juntadeandalucia.es"
OFERTAS = JUNTA + "/organismos/transparencia/empleo-publico/entidades-instrumentales/ofertas-empleo.html"


def filas_ofertas(h):
    out = []
    for tr in re.findall(r"(?s)<tr>(.*?)</tr>", h.split("<tbody", 1)[-1] if "<tbody" in h else ""):
        m = re.search(r"ofertas-empleo/detalle/(\d+)\.html", tr)
        if m: out.append(m.group(1))
    return out


def ficha_oferta(h):
    tit = re.search(r'(?s)field--name-field-ofem-titulacion-oficial[\s"].*?class="field__item">(.*?)</div>', h)
    t = limpio(re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", h))
    i = t.find("Titulación oficial requerida"); j = t.find("Más Información", i)
    return {"titulacion": limpio(tit.group(1)) if tit else "", "requisitos": t[i:j if j > i else i + 2500][:2500] if i >= 0 else ""}


# ------------------------------------------------------------------ todo
def etiquetar(x, hoy, red=pedir, pedir_jev=None):
    """Pone «etiquetas» en x y arregla agenda y sorteos. Devuelve un resumen. Sin Jev, solo lo exacto."""
    E = x.get("etiquetas") or {}
    nuevas = {k: {} for k in ("alim", "med", "prod", "ofertas")}
    hay_jev, motivo, n = True, "", {"alim": 0, "med": 0, "prod": 0, "ofertas": 0, "agenda_quitadas": 0, "sorteos": 0}
    fallos = []

    def jev_(estado, preguntas):
        nonlocal hay_jev, motivo
        if not hay_jev: return None
        try: return jev.preguntar(estado, preguntas, pedir=pedir_jev)[0]
        except jev.SinJev as e: hay_jev, motivo = False, str(e); return None

    try:
        for enlace, titulo in alertas_aesan(red(AESAN + "/alertas/alertas-alimentarias"), hoy):
            ya = (E.get("alim") or {}).get(enlace)
            if ya: nuevas["alim"][enlace] = ya; continue
            r = jev_({"alerta": {"titulo": titulo}}, jev.preguntas_alergeno())
            if r: nuevas["alim"][enlace] = {"alergeno": r["alergeno"]["choice"]}; n["alim"] += 1
    except Exception as e: fallos.append(f"AESAN: {e}"[:160]); nuevas["alim"] = E.get("alim") or {}
    try:
        for a in medicamentos_aemps(red(AEMPS), hoy):
            k = a.get("code") or ""; ya = (E.get("med") or {}).get(k) or {}
            et = dict(ya)
            if "sinReceta" not in et:
                et["sinReceta"] = sin_receta([p.get("cn") for p in a.get("products") or []])
            if "devolver" not in et:
                r = jev_({"alerta": {"medida": limpio(a.get("precautionaryMeasures"))[:1500]}}, jev.preguntas_medicamento())
                if r: et["devolver"] = r["devolver"]["noul"]
            if et != ya: n["med"] += 1
            nuevas["med"][k] = et
    except Exception as e: fallos.append(f"AEMPS: {e}"[:160]); nuevas["med"] = E.get("med") or {}
    try:
        L = productos_sg(json.loads(red(SG + "/search", cuerpo_sg([hoy.year, hoy.year - 1]), "application/json")), hoy)
        for p in L:
            ya = (E.get("prod") or {}).get(p["id"])
            if ya: nuevas["prod"][p["id"]] = ya; continue
            f = ficha_sg(json.loads(red(f"{SG}/notification/{p['id']}?language=es")))
            if DE_NINOS.search(f["categoria"]): nuevas["prod"][p["id"]] = {"ninos": 1.0}; n["prod"] += 1; continue
            r = jev_({"producto": {"nombre": p["producto"], "descripcion": f["descripcion"]}}, jev.preguntas_producto())
            if r: nuevas["prod"][p["id"]] = {"ninos": r["ninos"]["noul"]}; n["prod"] += 1
    except Exception as e: fallos.append(f"Safety Gate: {e}"[:160]); nuevas["prod"] = E.get("prod") or {}
    try:
        ids = []
        for pag in range(4):
            h = red(f"{OFERTAS}?field_ofem_fecha_fin_value%5B1%5D=1&items_per_page=50&sort_by=field_ofem_fecha_publi_value&page={pag}")
            nuevos = filas_ofertas(h); ids += nuevos
            if len(nuevos) < 50: break
        preguntadas = 0
        for i in ids:
            ya = (E.get("ofertas") or {}).get(i)
            if ya: nuevas["ofertas"][i] = ya; continue
            if not hay_jev or preguntadas >= 60: continue
            f = ficha_oferta(red(f"{JUNTA}/organismos/transparencia/empleo-publico/entidades-instrumentales/ofertas-empleo/detalle/{i}.html"))
            r = jev_({"oferta": f}, jev.preguntas_oferta()); preguntadas += 1
            if r: nuevas["ofertas"][i] = {"nivel": r["nivel"]["choice"], "experiencia": r["experiencia"]["noul"]}; n["ofertas"] += 1
    except Exception as e: fallos.append(f"ofertas de la Junta: {e}"[:160]); nuevas["ofertas"] = E.get("ofertas") or {}

    # la agenda sin repetidos: solo las del mismo día, por parejas
    ag = x.get("agenda") or []; fuera = set()
    for i, a in enumerate(ag):
        for j in range(i):
            if j in fuera or i in fuera or ag[j].get("fecha") != a.get("fecha"): continue
            r = jev_({"a": {k: ag[j].get(k) for k in ("titulo", "lugar", "hora")}, "b": {k: a.get(k) for k in ("titulo", "lugar", "hora")}}, jev.preguntas_mismo_evento())
            if r and r["mismo"]["noul"] >= 0.8:
                fuera.add(i if len(json.dumps(a)) <= len(json.dumps(ag[j])) else j)   # se queda la que tiene más datos
    if fuera: x["agenda"] = [a for k, a in enumerate(ag) if k not in fuera]; n["agenda_quitadas"] = len(fuera)
    # cómo se participa en cada sorteo
    for s in x.get("sorteos") or []:
        if s.get("participa"): continue
        r = jev_({"sorteo": {"premio": s.get("premio"), "como": s.get("como") or ""}}, jev.preguntas_participa())
        if r and r["participa"]["choice"] != "otro": s["participa"] = r["participa"]["choice"]; n["sorteos"] += 1

    x["etiquetas"] = nuevas | {"fecha": hoy.isoformat()}
    return {"nuevas": n, "juez": "Jev" if hay_jev else f"sin Jev ({motivo})", "fallos": fallos}


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    x = json.load(open(sys.argv[1], encoding="utf-8"))
    r = etiquetar(x, dt.datetime.now(TZ).date())
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    json.dump(x, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
