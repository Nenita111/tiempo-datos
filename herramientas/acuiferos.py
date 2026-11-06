"""Las aguas subterráneas de Adra (4.28, lo pidió Isa el 6 nov 2026: «acuíferos: nitratos, salinidad, conductividad, pesticidas y estado
químico de las masas de agua subterránea; fuente: MITECO y organismos de cuenca»).

- Los análisis de cada punto de control a 15 km o menos de Adra (pozos, sondeos y manantiales de la red oficial del MITECO, sistema NABIA),
  del fichero anual que publica la REDIAM de la Junta de Andalucía (portalrediam.cica.es, «Datos_Calidad_Subterraneas», SUB_FQ_AAAA.csv,
  CC BY 4.0, «Fuente: Ministerio para la Transición Ecológica y el Reto Demográfico»; sin robots.txt). Del último muestreo de cada punto: los
  nitratos (mg/l; el límite del agua de consumo y de la norma de calidad de las aguas subterráneas, 50), la conductividad (µS/cm) y los
  cloruros (mg/l), que dicen la salinidad; y las sustancias orgánicas que se detectan (por encima de su límite de cuantificación) en el año:
  plaguicidas como el glifosato y otras (los metales y los iones, no).
- El estado de cada masa de agua subterránea (químico y cuantitativo) del plan hidrológico 2022-2027, como lo comunicó España a la Agencia
  Europea de Medio Ambiente (WISE, water.discomap.eea.europa.eu), con su contorno; y por qué no está bien (los indicadores en mal estado de la
  tabla 2 del Anejo XII del plan de las Cuencas Mediterráneas Andaluzas, Junta de Andalucía).

El fichero es de toda Andalucía (unos 40 MB): solo se baja si cambia (Last-Modified). Se guarda en extras.json («acuiferos»).

  python3 -I herramientas/acuiferos.py extras.json [fichero.csv]

Imprime una línea JSON: {"acuiferos": N puntos, "anio": AAAA, ...} o {"error": …} (sale con 1; deja lo que había).
"""
import csv, datetime as dt, io, json, math, os, sys, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun
from agenda_junta import utm30_a_latlon

TZ = ZoneInfo("Europe/Madrid")
ADRA = (36.7480, -3.0213)
RADIO_KM = 15
CARPETA = "https://portalrediam.cica.es/repositorio/05_CALIDAD_AMBIENTAL/02_AGUAS/01_CALIDAD_AGUAS/Datos_Calidad_Subterraneas/InfGeografica/InfAlfanum/"
FICHA = "https://portalrediam.cica.es/descargas?path=%2F05_CALIDAD_AMBIENTAL%2F02_AGUAS%2F01_CALIDAD_AGUAS%2FDatos_Calidad_Subterraneas"
EEA = "https://water.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD/WFD2022_GroundWaterBody_WM/MapServer/1/query"
PLAN = "https://www.juntadeandalucia.es/sites/default/files/2022-03/PH_CMA_Anejo_XII%20y%20sus%20ap%C3%A9ndices_0.pdf"
# el recuadro del mapa de la app (el de las zonas inundables) y uno más grande para las masas de agua de los puntos
CAJA = (ADRA[1] - 0.064, ADRA[0] - 0.016, ADRA[1] + 0.066, ADRA[0] + 0.052)
# Plan hidrológico de las Cuencas Mediterráneas Andaluzas 2022-2027, Anejo XII, apéndice XII.4, tabla 2 («Detalle del estado químico de las
# masas de agua subterránea»): los indicadores en mal estado (3) de las masas de la zona
CAUSAS = {
    "ES060MSBT060-013": ["salinización", "nitratos", "otros contaminantes", "aguas superficiales asociadas (MSPF)", "ecosistemas dependientes (ETDAS)",
                         "zonas protegidas de agua de consumo (ZPAC)"],
    "ES060MSBT060-014": [],
    "ES060MSBT060-015": ["salinización", "plaguicidas"],
    "ES060MSBT060-016": ["plaguicidas"],
}
# sus nombres en el plan (la Agencia Europea los tiene sin tildes ni eñes: «ALBUNOL»)
NOMBRES = {"ES060MSBT060-013": "Campo de Dalías-Sierra de Gádor", "ES060MSBT060-014": "Oeste de Sierra de Gádor", "ES060MSBT060-015": "Delta del Adra",
           "ES060MSBT060-016": "Albuñol"}
ESTADO = {"2": "bueno", "3": "malo"}
# los metales y los iones (también en µg/l) no van con lo detectado: de ellos se dice la salinidad (cloruros) aparte
INORGANICOS = {"AG", "AL", "AS", "B", "BA", "BE", "CD", "CN", "CO", "CR", "CU", "F", "FE", "HG", "LI", "MN", "MO", "NI", "PB", "SB", "SE", "SN", "SR", "TI",
               "TL", "U", "V", "ZN"}


def km(a, b):
    return math.hypot((a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110.57)


def num(s):
    try: return float(str(s).replace(",", "."))
    except (TypeError, ValueError): return None


def fecha(s):
    return str(s or "")[:10]


def leer(lineas, centro=ADRA, radio=RADIO_KM):
    """Los puntos de control a [radio] km o menos con sus análisis químicos: {código: punto}."""
    puntos = {}
    for f in csv.DictReader(lineas, delimiter=";"):
        if not str(f.get("tipo_evaluacion", "")).startswith("SUB-QUIMICO"): continue
        if str(f.get("huso", "")).strip() != "30": continue
        x, y = num(f.get("utmx")), num(f.get("utmy"))
        if x is None or y is None: continue
        la, lo = utm30_a_latlon(x, y)
        d = km(centro, (la, lo))
        if d > radio: continue
        cod = f["cod_punto_muestreo"]
        nom = comun.limpio(f.get("nom_punto_muestreo")); nom = nom.capitalize() if nom.isupper() else nom
        p = puntos.setdefault(cod, {"codigo": cod, "nombre": nom, "tipo": (f.get("tipo_punto") or "").strip().lower(),
                                    "masa": f.get("cod_masa_agua_eu"), "nombreMasa": (f.get("nom_masa_agua") or "").strip(),
                                    "lat": round(la, 5), "lon": round(lo, 5), "km": round(d, 1), "analisis": []})
        p["analisis"].append({"fecha": fecha(f.get("fecha_muestreo")), "param": f.get("cod_parametro"), "nombre": (f.get("nom_parametro") or "").strip(),
                              "valor": num(f.get("valor_parametro")), "lq": num(f.get("LQ")), "texto": (f.get("identificador_resultado") or "").strip(),
                              "unidad": (f.get("unidad") or "").strip()})
    return puntos


def resumen(p):
    """De un punto: el último valor de nitratos, conductividad y cloruros (con su fecha), el máximo de nitratos del año y lo detectado en µg/l."""
    A = p["analisis"]
    def ultimo(param):
        v = sorted((a for a in A if a["param"] == param and a["valor"] is not None), key=lambda a: a["fecha"])
        return {"valor": round(v[-1]["valor"], 1), "texto": v[-1]["texto"], "fecha": v[-1]["fecha"]} if v else None
    r = {k: p[k] for k in ("codigo", "nombre", "tipo", "masa", "nombreMasa", "lat", "lon", "km")}
    r["ultima"] = max(a["fecha"] for a in A)
    for clave, param in (("no3", "NO3"), ("ce", "COND20SITU"), ("cl", "CL")):
        u = ultimo(param)
        if u: r[clave] = u
    n = [a["valor"] for a in A if a["param"] == "NO3" and a["valor"] is not None]
    if len(n) > 1: r["no3Max"] = round(max(n), 1)
    det = {}
    for a in A:
        if a["param"] in INORGANICOS or a["unidad"].lower().replace("μ", "µ") != "µg/l" or a["valor"] is None or not a["lq"] or a["valor"] < a["lq"] or a["texto"].startswith("<"): continue
        d = det.setdefault(a["nombre"], {"nombre": a["nombre"].capitalize(), "max": a["valor"], "fecha": a["fecha"], "veces": 0})
        d["veces"] += 1
        if a["valor"] > d["max"]: d["max"], d["fecha"] = a["valor"], a["fecha"]
    r["detectado"] = sorted(({**d, "max": float(f"{d['max']:.3g}")} for d in det.values()), key=lambda d: -d["max"])
    return r


def masas(caja_puntos):
    """Las masas de agua subterránea del recuadro, con su estado y contorno (simplificado a unos 50 m)."""
    g = ",".join(f"{v:.4f}" for v in caja_puntos)
    q = (f"{EEA}?geometry={g}&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&outFields=euGroundWaterBodyCode,groundWaterBodyName,"
         "gwChemicalStatusValue,gwQuantitativeStatusValue,gwChemicalAssessmentYear&returnGeometry=true&maxAllowableOffset=0.0005&geometryPrecision=4&f=json")
    d = json.loads(comun.pedir(q, timeout=90).decode("utf-8"))
    res = []
    for f in d.get("features") or []:
        a = f.get("attributes") or {}
        cod = a.get("euGroundWaterBodyCode")
        res.append({"codigo": cod, "nombre": NOMBRES.get(cod) or str(a.get("groundWaterBodyName") or "").strip(), "quimico": ESTADO.get(str(a.get("gwChemicalStatusValue")), "sin datos"),
                    "cuantitativo": ESTADO.get(str(a.get("gwQuantitativeStatusValue")), "sin datos"), "evaluacion": str(a.get("gwChemicalAssessmentYear") or "").replace("--", "-"),
                    "causas": CAUSAS.get(cod), "anillos": (f.get("geometry") or {}).get("rings") or []})
    return res


def ultimo_fichero(hoy):
    """El fichero anual más reciente que haya (el de un año sale en febrero del siguiente) y su fecha de modificación."""
    for y in range(hoy.year, 2023, -1):
        url = f"{CARPETA}SUB_FQ_{y}.csv"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": comun.UA_APP}), timeout=60) as r:
                return y, url, r.headers.get("Last-Modified", "")
        except Exception:
            continue
    raise ValueError("no encuentro el fichero de calidad de aguas subterráneas de la REDIAM")


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]; local = sys.argv[2] if len(sys.argv) > 2 else None
    x = json.load(open(ruta, encoding="utf-8"))
    antes = x.get("acuiferos") or {}
    hoy = dt.datetime.now(TZ).date()
    try:
        if local:
            anio, url, mod = int("".join(c for c in os.path.basename(local) if c.isdigit())[:4]), CARPETA + os.path.basename(local), "local"
            lineas = open(local, encoding="utf-8", newline="")
        else:
            anio, url, mod = ultimo_fichero(hoy)
            if antes.get("fichero") == url and antes.get("modificado") == mod and antes.get("revisado", "") >= (hoy - dt.timedelta(days=30)).isoformat():
                print(json.dumps({"acuiferos": len(antes.get("puntos") or []), "anio": antes.get("anio"), "sin cambios": True}, ensure_ascii=False)); return
            lineas = io.TextIOWrapper(io.BytesIO(comun.pedir(url, timeout=600)), encoding="utf-8", newline="")
        puntos = [resumen(p) for p in leer(lineas).values()]
        if not puntos: raise ValueError(f"ningún punto de control a {RADIO_KM} km de Adra en {url}")
        puntos.sort(key=lambda p: p["km"])
        cuerpos = masas(CAJA)
        if not cuerpos: raise ValueError("la Agencia Europea de Medio Ambiente no devuelve las masas de agua")
        # las de los puntos que no salen en el recuadro del mapa, sin contorno
        faltan = {p["masa"] for p in puntos} - {c["codigo"] for c in cuerpos}
        if faltan:
            for c in masas((ADRA[1] - 0.25, ADRA[0] - 0.15, ADRA[1] + 0.25, ADRA[0] + 0.15)):
                if c["codigo"] in faltan: cuerpos.append({**c, "anillos": []})
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    nuevo = {"anio": anio, "puntos": puntos, "masas": cuerpos, "radio": RADIO_KM, "caja": list(CAJA), "fichero": url, "modificado": mod,
             "revisado": hoy.isoformat(), "enlace": FICHA, "plan": PLAN,
             "fuente": "MITECO (red de control, por la REDIAM de la Junta de Andalucía) · estado: plan hidrológico 2022-2027 (Junta de Andalucía, AEMA)"}
    if {k: v for k, v in (x.get("acuiferos") or {}).items() if k != "revisado"} != {k: v for k, v in nuevo.items() if k != "revisado"} or antes.get("revisado") != nuevo["revisado"]:
        x["acuiferos"] = nuevo
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"acuiferos": len(puntos), "anio": anio, "masas": len(cuerpos)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
