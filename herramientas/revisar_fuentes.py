"""Revisión diaria de las fuentes de la app de la tele: ¿responde cada web y sigue teniendo lo que la app busca?

Para cada fuente pide lo mismo que la app (con su mismo agente) y comprueba la marca de la que depende el programa
(una expresión en la página, un campo del JSON…). Si una web cambia y la app dejaría una tarjeta vacía, sale aquí.

  python3 revisar_fuentes.py                 # Adra
  python3 revisar_fuentes.py --json informe.json

Sale con código 1 si alguna fuente está ROTA. «NO COMPROBABLE» = la web bloquea a los servidores en la nube
(p. ej. Red Eléctrica): desde casa funciona.
"""
import argparse, datetime as dt, email.utils, gzip, io, json, math, re, ssl, subprocess, sys, tarfile, urllib.error, urllib.parse, urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor
ULTIMA = threading.local()      # lo último que bajó cada hilo: si una fuente sale ROTA, Jev mira si el dato sigue en la página
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"      # el de la app (Red.kt)
UA_WIKI = "TiempoYRadar/1.0 (aplicacion personal de television)"
TZ = ZoneInfo("Europe/Madrid")
ADRA = dict(nombre="Adra", provincia="Almería", ine="04003", cp="04770", lat=36.7480, lon=-3.0213)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def pedir(url, cuerpo=None, tipo=None, agente=UA, tiempo=45):
    r = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": agente, **({"Content-Type": tipo} if tipo else {})})
    try:
        with urllib.request.urlopen(r, timeout=tiempo) as f:
            ULTIMA.b = f.read(); return ULTIMA.b
    except urllib.error.URLError as e:
        # algunas webs de la Administración negocian TLS de forma que Python no acepta y curl sí (como la tele): se reintenta con curl
        if not isinstance(e.reason, ssl.SSLError) or cuerpo is not None: raise
        c = subprocess.run(["curl", "-sS", "-f", "-L", "--max-time", str(tiempo), "-A", agente, url], capture_output=True)
        if c.returncode: raise
        ULTIMA.b = c.stdout; return c.stdout


def texto(url, **k):
    b = pedir(url, **k)
    try: return b.decode("utf-8")
    except UnicodeDecodeError: return b.decode("iso-8859-15")


def distancia(L, lat, lon):
    """Kilómetros del sitio al punto (haversine, como Lugar.km de la app)."""
    a = math.sin(math.radians(lat - L["lat"]) / 2) ** 2 + math.cos(math.radians(L["lat"])) * math.cos(math.radians(lat)) * math.sin(math.radians(lon - L["lon"]) / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(a)))


def busca(patron, t, que):
    if not re.search(patron, t): raise ValueError(f"no aparece {que}")


# ------------------------------------------------------------------ cada fuente: devuelve un resumen corto o lanza el fallo
def prevision(L):
    t = texto(f"https://www.aemet.es/xml/municipios/localidad_{L['ine']}.xml"); busca(r"<prediccion>", t, "la predicción diaria")
    t = texto(f"https://www.aemet.es/xml/municipios_h/localidad_h_{L['ine']}.xml"); busca(r"<prediccion>", t, "la predicción por horas")
    return "diaria y por horas"

def avisos(L):
    t = texto("https://www.aemet.es/es/eltiempo/prediccion/avisos")
    ruta = re.search(r"/es/geojson/download/avisos/geojson_\d+\.tar\.gz", t)
    if not ruta: raise ValueError("no encuentro el paquete de avisos")
    n = [m.name for m in tarfile.open(fileobj=io.BytesIO(gzip.decompress(pedir("https://www.aemet.es" + ruta.group(0), tiempo=60)))).getmembers()]
    if not any(re.search(r"^r_D\+[012]_", x.rsplit("/", 1)[-1]) and "_penbal_" in x for x in n): raise ValueError("el paquete no trae los resúmenes")
    return f"{len(n)} ficheros"

def playas(L):
    t = texto("https://www.aemet.es/es/eltiempo/prediccion/playas")
    c = re.findall(r'"id":"[a-z0-9-]+-(\d{7})","nombre":"[^"]*","idLocalidad":"id' + L["ine"] + '"', t)
    if not c: raise ValueError("no encuentro las playas del municipio")
    busca(r"<prediccion>", texto(f"https://www.aemet.es/xml/playas/play_v2_{c[0]}.xml"), "la predicción de la playa")
    return f"{len(set(c))} playas"

def satelite(L):
    t = texto("https://www.aemet.es/es/eltiempo/observacion/satelite/infra")
    s = re.findall(r"imagenes_d/eltiempo/observacion/satelite/(\d{12})_s93g\.jpg", t)
    if not s: raise ValueError("no encuentro las imágenes")
    return f"última {max(s)}"

def radar(L):
    b = pedir("https://www.aemet.es/es/api-eltiempo/radar/download/compo", tiempo=60)
    n = [m.name for m in tarfile.open(fileobj=io.BytesIO(gzip.decompress(b))).getmembers() if m.name.endswith(".tif")]
    if not n: raise ValueError("el paquete no trae imágenes")
    return f"{len(n)} imágenes"

def incendio(L):
    t = texto("https://www.aemet.es/es/eltiempo/prediccion/incendios")
    ruta = (re.search(r"/es/api-eltiempo/incendios/download[^\"']*", t) or [None])[0] or "/es/api-eltiempo/incendios/download"
    n = [m.name for m in tarfile.open(fileobj=io.BytesIO(gzip.decompress(pedir("https://www.aemet.es" + ruta, tiempo=90)))).getmembers()]
    if not any("peligro_p_" in x and x.endswith(".tif") for x in n): raise ValueError("el paquete no trae el peligro de la península")
    return f"{len(n)} ficheros"

def maritima(L):
    busca(r"<prediccion|<zona", texto("https://www.aemet.es/xml/maritima/FQXX47MM.xml"), "el boletín"); return "boletín"

def mareas(L):
    est = json.loads(texto("https://portus.puertos.es/portussvr/api/estaciones/rt/SEA_LEVEL?locale=es"))
    if not est: raise ValueError("sin mareógrafos")
    # 4.0 (281): lo medido por el mareógrafo de Almería 2 (3548) en las últimas 24 horas, como Mareas.medido
    rt = json.loads(texto("https://portus.puertos.es/portussvr/api/RTData/station/3548?locale=es", cuerpo=b"[27]", tipo="application/json"))
    if not rt or not any(d.get("paramEseoo") == "SeaLevel" for d in rt[0].get("datos", [])): raise ValueError("sin nivel del mar medido (RTData)")
    return f"{len(est)} mareógrafos; {len(rt)} medidas del de Almería"

def boya(L):
    est = json.loads(texto("https://portus.puertos.es/portussvr/api/estaciones/rt/WAVE?locale=es"))
    if not est: raise ValueError("sin boyas")
    return f"{len(est)} boyas"

def oleaje(L):
    u = json.loads(texto("https://portus.puertos.es/portussvr/api/ubicaciones/?locale=es"))
    if not u: raise ValueError("sin ubicaciones")
    return f"{len(u)} puntos"

def terremotos(L):
    t = texto("https://www.ign.es/web/ign/portal/ultimos-terremotos/-/ultimos-terremotos/get10dias", tiempo=60)
    n = len(re.findall(r"<td>(es\w+)</td>\s*<td>([\d/]+)</td>\s*<td>([\d:]+)</td>", t))
    if not n: raise ValueError("la tabla de terremotos ha cambiado")
    return f"{n} terremotos"

def efemerides(L):
    h = dt.datetime.now(TZ).date()
    t = texto(f"https://es.wikipedia.org/w/index.php?title={h.day}_de_{MESES[h.month - 1]}&action=raw", agente=UA_WIKI)
    busca(r"==\s*Acontecimientos\s*==", t, "la sección Acontecimientos"); return "ok"

def futbol(L):
    j = json.loads(texto("https://site.api.espn.com/apis/v2/sports/soccer/esp.2/standings"))
    if "children" not in j: raise ValueError("la clasificación ha cambiado")
    return "clasificación"

def campo(L):
    t = texto("https://www.fhalmeria.com/es/pizarra-precios.aspx", tiempo=60)
    t = re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", t))
    n = len(re.findall(r"\((\d{2})/(\d{2})/(\d{4})\)", t))
    if not n: raise ValueError("la pizarra de precios ha cambiado")
    return f"{n} subastas"

def lonja(L):
    h = dt.datetime.now(TZ).date(); fin = h - dt.timedelta(days=1); ini = fin - dt.timedelta(days=6)
    q = urllib.parse.urlencode(dict(filters=json.dumps({"listaFiltro": [{"campo": "fechaVenta", "value": [str(ini), str(fin)]}, {"campo": "provincia", "value": ["4"]}]}),
                                    agrupaciones=json.dumps({"campos": ["nombreEspecie"]}), page=0, size=200,
                                    columnasMostrar=json.dumps({"campos": ["nombreEspecie", "totalKilos", "totalEuros"]}), codigoPantalla=21))
    c = json.loads(texto("https://ws142.juntadeandalucia.es/agriculturaypesca/idapub/idaback/primeraVentaLonja/findPrimeraVentaLonja?" + q, tiempo=60)).get("content")
    if c is None: raise ValueError("la respuesta no trae «content»")
    return f"{len(c)} especies"

def trafico(L):
    t = pedir("https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml", tiempo=60)[:400000].decode("utf-8", "replace")
    busca(r"situationRecord", t, "incidencias"); return "ok"

def gasolina(L):
    j = json.loads(texto("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/FiltroProvincia/04", tiempo=60))
    if not j.get("ListaEESSPrecio"): raise ValueError("sin estaciones")
    return f"{len(j['ListaEESSPrecio'])} estaciones"

def luz(L):
    d = dt.datetime.now(TZ).date()
    try: j = json.loads(texto(f"https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real?start_date={d}T00:00&end_date={d}T23:59&time_trunc=hour"))
    except urllib.error.HTTPError as e:
        if e.code == 403: raise PermissionError("Red Eléctrica no deja entrar a servidores en la nube")
        raise
    if not j.get("included"): raise ValueError("sin precios")
    return "precios de hoy"

def esios(L):
    """La API de ESIOS con la clave de Isa (variable ESIOS_API_KEY del entorno), la que usa la tarea del precio de la luz al móvil."""
    import os
    clave = os.environ.get("ESIOS_API_KEY", "").strip()
    if not clave: raise PermissionError("falta la variable ESIOS_API_KEY en el entorno")
    d = dt.datetime.now(TZ).date()
    r = subprocess.run(["curl", "-sS", "-f", "--max-time", "40", "-A", UA, "-H", "Accept: application/json; application/vnd.esios-api-v1+json", "-H", "@-",
                        f"https://api.esios.ree.es/indicators/1001?start_date={d}T00:00&end_date={d}T23:59&geo_ids[]=8741"],
                       input=f"x-api-key: {clave}\n".encode(), capture_output=True)
    if r.returncode: raise IOError(r.stderr.decode()[:160].strip())
    if not json.loads(r.stdout)["indicator"]["values"]: raise ValueError("sin precios de hoy")
    return "precios de hoy (con la clave)"

def aire(L):
    # 4.0 (283 y 285): lo mismo que Polen.previsto (polen, índice europeo y UV de cada hora)
    j = json.loads(texto(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={L['lat']}&longitude={L['lon']}"
                         "&hourly=olive_pollen,european_aqi,uv_index&timezone=Europe%2FMadrid&forecast_days=3"))
    h = j.get("hourly") or {}
    if not h.get("european_aqi") or all(v is None for v in h.get("european_aqi")): raise ValueError("sin índice europeo previsto")
    if all(v is None for v in h.get("uv_index") or [None]): raise ValueError("sin UV previsto")
    return "ok"

def iss(L):
    # 4.0 (279): la Estación Espacial y Tiangong, del grupo «stations» de CelesTrak (una vez: no pide más de una cada 2 horas)
    t = texto("https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=TLE")
    falta = [n for n, k in (("Estación Espacial", "1 25544"), ("Tiangong", "1 48274")) if k not in t]
    if falta: raise ValueError("sin órbita de " + " ni de ".join(falta))
    return "las dos estaciones"

def luna(L):
    # la foto de la Luna de cada año de la NASA (Cielo.lunaSvs): la búsqueda responde y la de este año está
    y = dt.date.today().year
    j = json.loads(texto(f"https://svs.gsfc.nasa.gov/api/search/?search=Moon%20Phase%20and%20Libration%2C%20{y}&limit=10"))
    if not any(r.get("title", "").strip() == f"Moon Phase and Libration, {y}" for r in j.get("results", [])): raise ValueError(f"sin la página de {y}")
    return f"la de {y}" + (f" y la de {y + 1}" if any(r.get("title", "").strip() == f"Moon Phase and Libration, {y + 1}" for r in json.loads(
        texto(f"https://svs.gsfc.nasa.gov/api/search/?search=Moon%20Phase%20and%20Libration%2C%20{y + 1}&limit=10")).get("results", [])) else "")

def planeta(L):
    for u in ("https://sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_2t_global.csv",
              "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_daily_mlo.txt"):
        if len(pedir(u, tiempo=60)) < 1000: raise ValueError(f"fichero vacío: {u}")
    return "temperatura y CO₂"

def sol(L):
    if not json.loads(texto("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")): raise ValueError("sin índice Kp")
    return "Kp"

def farmacias(L):
    t = texto("https://www.cofalmeria.com/buscador-de-farmacias/?activo_guardias=on")
    n = re.search(r'vbf_vars\s*=\s*\{"nonce":"([a-z0-9]+)"', t)
    if not n: raise ValueError("no encuentro la clave del buscador (vbf_vars)")
    campos = {"action": "bearer_authentication_with_params", "nonce": n.group(1), "vbf_req_endpoint": "/farmacias-abiertas",
              "vbf_req_fecha": dt.datetime.now(TZ).date().isoformat(), "vbf_req_cp": L["cp"], "vbf_req_municipio": L["nombre"],
              "vbf_req_es_listado_geo": "false", "vbf_req_latitud": "null", "vbf_req_longitud": "null", "vbf_req_solo_guardias": "true",
              "vbf_req_aplica_filtro_fecha": "true", "vbf_req_lang": "es-ES"}
    r = json.loads(pedir("https://www.cofalmeria.com/wp-admin/admin-ajax.php", urllib.parse.urlencode(campos).encode(), "application/x-www-form-urlencoded"))
    if not r.get("success"): raise ValueError("el buscador no acepta la consulta")
    g = [f for x in r["data"]["data"].get("informacion", []) for f in x.get("contenido", []) if f.get("guardias")]
    if not g: raise ValueError("ninguna farmacia de guardia hoy (¿ha cambiado la respuesta?)")
    return f"{len(g)} de guardia"

def alimentarias(L):
    t = texto("https://www.aesan.gob.es/alertas/alertas-alimentarias")
    # la app lee los tres bloques (Alimentarias.kt): toda la población, complementos y alergias
    bloques = {"toda la población": "alertas-alimentarias-de-interes-para-toda-la-poblacion",
               "complementos": "alertas-alimentarias-para-personas-que-consumen-complementos-alimenticios",
               "alergias": "alertas-alimentarias-para-personas-con-alergias-intolerancias"}
    for nombre, ancla in bloques.items():
        if ancla not in t: raise ValueError(f"no encuentro el bloque «{nombre}»")
    i = t.find(bloques["toda la población"])
    n = len(re.findall(r'<a class="seeMoreCardSlide[^"]*" href="([^"]+)" title="([^"]+)">', t[i:]))
    if not n: raise ValueError("los bloques no traen tarjetas")
    return f"{n} alertas en los tres bloques"

def noticias(L):
    """3.9: solo Noticias de Almería. Google Noticias, Diario de Almería y La Voz de Almería prohíben en su robots.txt a los agentes como
    Claude: la tarea en la nube no los pide (la tele sí los lee, con su agente)."""
    n = texto("https://www.noticiasdealmeria.com/rss/seccion/65/").count("<item>")
    if not n: raise ValueError("sin noticias en Noticias de Almería")
    return f"{n} en Noticias de Almería (Google Noticias, Diario de Almería y La Voz no se miran desde la nube: su robots.txt no deja)"

def sonda(L):
    json.loads(texto(f"https://api.v2.sondehub.org/sondes?lat={L['lat']}&lon={L['lon']}&distance=300000&last=10800")); return "ok"

def extras(L):
    x = json.loads(texto("https://raw.githubusercontent.com/Nenita111/tiempo-datos/main/extras.json"))
    b = x.get("vuelosBuscado")
    if not b or (dt.date.today() - dt.date.fromisoformat(b)).days > 2: raise ValueError(f"vuelos sin buscar desde {b}")
    return f"vuelos del {b}, {len(x.get('sorteos', []))} sorteos"


def paro(L):
    # datos abiertos del SEPE: el CSV del año (o del anterior, en enero)
    y = dt.date.today().year
    for año in (y, y - 1):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://sede.sepe.gob.es/es/portaltrabaja/resources/sede/datos_abiertos/datos/Paro_por_municipios_{año}_csv.csv",
                                                              headers={"User-Agent": UA}, method="HEAD"), timeout=45)
            return f"CSV de {año}, {r.headers.get('Last-Modified', 'sin fecha')}"
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
    raise ValueError("no está el CSV de paro por municipios")

def afiliados(L):
    t = texto("https://www.seg-social.es/wps/portal/wss/internet/EstadisticasPresupuestosEstudios/Estadisticas/est8/est10/est305/c43ad8ea-fe79-4329-ac8e-e5758f3c4d7a/6609c55f-65e4-4e64-b1ab-8917fce27a84", tiempo=60)
    m = re.findall(r'href="/descarga/es/(Muni\w+)"', t)
    if not m: raise ValueError("la página no trae los ficheros por municipios")
    return f"último {m[0]}"

def euribor(L):
    t = texto("https://clientebancario.bde.es/pcb/es/menu-horizontal/podemosayudarte/tiposinteres/guia_textual/tiposinteresreferenciaotrostiposfrecuentes/tabla_tipos_referencia_oficiales_mercado_hipotecario.html")
    if not re.search(r'headers="[^"]*\bt151\b', t): raise ValueError("la tabla oficial ha cambiado (sin la columna del euríbor a 1 año)")
    c = pedir("https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/ti_1_7.csv")[:3000].decode("latin-1")
    if "Euríbor. A 12 meses" not in c: raise ValueError("el CSV del euríbor diario ha cambiado")
    return "tabla oficial y CSV"

def festivos(L):
    j = json.loads(texto("https://www.juntadeandalucia.es/ssdigitales/datasets/work-calendar/years"))
    if str(dt.date.today().year) not in j.get("result", []): raise ValueError("el calendario laboral no tiene este año")
    return "años " + ", ".join(j["result"][-2:])

def rayos(L):
    t = texto("https://view.eumetsat.int/geoserver/mtg_fd/li_afa/ows?service=WMS&version=1.3.0&request=GetCapabilities")
    m = re.search(r'<Dimension name="time" default="([^"]+)"', t)
    if not m: raise ValueError("EUMETView no da la hora de los rayos")
    edad = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    if edad > dt.timedelta(hours=2): raise ValueError(f"la última imagen de rayos es de hace {edad}")
    return f"última imagen {m.group(1)}"

def medicamentos(L):
    # Consumo.kt: la lista «normalizedData» que lleva dentro la página de alertas farmacéuticas de la AEMPS
    t = texto("https://www.aemps.gob.es/comunicacion/alertas/alertas-farmaceuticas-y-retiradas-de-lotes-de-medicamentos-de-uso-humano-por-defectos-de-calidad/", tiempo=60)
    i = t.find("normalizedData")
    if i < 0: raise ValueError("la página ya no trae la lista «normalizedData»")
    lista, _ = json.JSONDecoder().raw_decode(t[t.index("[", i):])
    if not lista or not {"code", "date", "products", "defectClassification"} <= set(lista[0]): raise ValueError("la lista ha cambiado de forma")
    return f"{len(lista)} alertas, la última {lista[0]['code']}"

def productos(L):
    # Consumo.kt: la búsqueda de Safety Gate (notificadas por España), como la hace su web
    y = dt.date.today().year
    q = {"criteria": {"notifyingCountry": ["ES"], "year": [y, y - 1]}, "searchCriteriaForNotification": False, "isLaunched": True, "isLaunchSearch": True,
         "pagination": {"numberElements": 5, "page": 0, "sortField": "PUBLICATION_DATE", "sortOrder": "DESC", "totalElements": 0},
         "language": "es", "displayDefaultResults": False, "isForMostRecent": False}
    j = json.loads(pedir("https://ec.europa.eu/safety-gate-alerts/public/api/search", json.dumps(q).encode(), "application/json"))
    c = j.get("content") or []
    if not c: raise ValueError("la búsqueda no devuelve notificaciones de España")
    return f"{j.get('totalElements')} de España, la última del {c[0]['publicationDate'][:10]}"

def sae(L):
    # Empleo.sae (3.6): la lista de ofertas publicadas del Servicio Andaluz de Empleo, la misma que pide su página; las de empleo público
    # («ofertaPublica»: S) de la provincia
    j = json.loads(pedir("https://saempleo.es/ags/api/MS-HERMES/hermes/ofertas/ofertaspublicadas", b"{}", "application/json"))
    if not isinstance(j, list) or not j or "idOferta" not in j[0]: raise ValueError("ya no da la lista de ofertas (sin «idOferta»)")
    pub = [o for o in j if o.get("ofertaPublica") == "S" and (o.get("provincia") or {}).get("id") == L["ine"][:2]]
    return f"{len(j)} ofertas, {len(pub)} de empleo público en la provincia"

def fap(L):
    # fap.py (3.8, tarea diaria): la lista de circulares de este año de la Federación Andaluza de Piragüismo, como la lee
    import fap as F
    y = dt.date.today().year
    c = F.circulares(pedir(F.CIRCULARES.format(y=y)).decode("utf-8", "replace"))
    if not c: raise ValueError("la página de circulares ya no da la lista (sin «el-item» con su PDF y su fecha)")
    return f"{len(c)} circulares de {y}, la última del {c[0]['fecha']}"

def agua(L):
    # Consumo.kt: SINAC, acceso al ciudadano (formularios): las redes del municipio
    ine = int(L["ine"]); prov = int(L["ine"][:2])
    t = texto("https://sinac.sanidad.gob.es/CiudadanoWeb/ciudadano/informacionRedes.do", cuerpo=f"codProvincia={prov}&codMunicipio={ine}".encode(),
              tipo="application/x-www-form-urlencoded")
    redes = re.findall(r"eleccionRedDistribucion\((\d+)\)", t)
    if not redes: raise ValueError("el SINAC no da las redes del municipio")
    return f"{len(redes)} redes"

def camara(L):
    # Entorno.kt (Camaras): el fichero DATEX II de cámaras de la DGT y la foto de la más cercana, con su hora (Last-Modified)
    t = texto("https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v37.xml", tiempo=120)
    cerca = []
    for m in re.finditer(r'(?s)<ns2:device [^>]*id="(\d+)".*?</ns2:device>', t):
        d = m.group(0)
        if "<ns2:typeOfDevice>camera</ns2:typeOfDevice>" not in d: continue
        la, lo, u = (re.search(f"<{e}>([^<]*)</{e}>", d) for e in ("loc:latitude", "loc:longitude", "fse:deviceUrl"))
        if not (la and lo and u): continue
        km = distancia(L, float(la.group(1)), float(lo.group(1)))
        if km <= 25: cerca.append((km, m.group(1), u.group(1)))
    if not cerca: raise ValueError("el fichero de la DGT no trae cámaras a menos de 25 km")
    km, cid, url = min(cerca)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=45) as f:
        jpg, mod = f.read(), f.headers.get("Last-Modified")
    if jpg[:2] != b"\xff\xd8": raise ValueError(f"la cámara {cid} no manda un JPEG")
    if mod:
        edad = dt.datetime.now(dt.timezone.utc) - email.utils.parsedate_to_datetime(mod)
        if edad > dt.timedelta(hours=2): raise ValueError(f"la foto de la cámara {cid} es de hace {edad}")
    return f"cámara {cid} a {km:.1f} km, foto de {len(jpg) // 1000} kB"

def radiacion(L):
    # Entorno.kt (Radiacion): la API del mapa de la REA del CSN y la serie horaria de la estación más cercana
    j = json.loads(pedir("https://rea.csn.es/rea-api/V1.0/mapa/estaciones"))
    f = [x for x in j.get("features", []) if (x.get("properties") or {}).get("status") == "ok_ok"]
    if not f: raise ValueError("la REA no da estaciones que midan bien")
    e = min(f, key=lambda x: distancia(L, x["geometry"]["coordinates"][1], x["geometry"]["coordinates"][0]))
    s = json.loads(pedir(f"https://rea.csn.es/rea-api/V1.0/mapa/estaciones/{e['id']}/dataseries/1h"))
    if not s: raise ValueError(f"la REA no da la serie de {e['properties'].get('name')}")
    edad = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromtimestamp(s[-1][0] / 1000, dt.timezone.utc)
    if edad > dt.timedelta(hours=6): raise ValueError(f"lo último de {e['properties'].get('name')} es de hace {edad}")
    return f"{len(f)} estaciones; {e['properties'].get('name')}: {s[-1][1]} nSv/h"

def sequia(L):
    # sequia.py (tarea diaria): el informe de escasez y sequía de Hidrosur, solo la cabecera (pesa 14 MB)
    with urllib.request.urlopen(urllib.request.Request("https://www.redhidrosurmedioambiente.es/saih/assets/pdf/InformeSequia.pdf",
                                                       headers={"User-Agent": UA}, method="HEAD"), timeout=45) as f:
        tipo, mod = f.headers.get("Content-Type", ""), f.headers.get("Last-Modified")
    if "pdf" not in tipo: raise ValueError(f"el informe no es un PDF ({tipo})")
    if mod:
        edad = dt.datetime.now(dt.timezone.utc) - email.utils.parsedate_to_datetime(mod)
        if edad > dt.timedelta(days=75): raise ValueError(f"el informe no se ha renovado desde {mod}")
    return f"modificado {mod}"


def sangre(L):
    # Sangre.kt: la tabla «Se puede donar en…» de la página del centro de transfusión de la provincia en la web del SAS
    t = texto("https://www.sspa.juntadeandalucia.es/servicioandaluzdesalud/el-sas/servicios-y-centros/informacion-por-centros/20585", tiempo=60)
    i = t.find("view-colecta-sangre")
    if i < 0: raise ValueError("la página del centro ya no trae la tabla de colectas")
    filas = re.findall(r"views-field-field-colecta-fecha\">\s*(\d\d-\d\d-\d{4})", t[i:t.find("</table>", i)])
    if not filas: raise ValueError("la tabla de colectas viene vacía")
    return f"{len(filas)} colectas, del {filas[0]} al {filas[-1]}"


def cortesAgua(L):
    # CortesAgua.kt: la capa «Puntos de cierre» del mapa de obras y afectaciones de Hidralia (Agbar), la misma consulta que su tabla
    donde = f"COD_MUNI='{L['ine']}' AND CI_ESTADO IN ('4AP','5EC')"
    u = ("https://services3.arcgis.com/5VitVYyVLQYnzXCo/arcgis/rest/services/Cierres_webPublicas_v/FeatureServer/0/query?where="
         + urllib.parse.quote_plus(donde) + "&outFields=CI_ID,CI_FH_INI_PREV,CI_FH_FIN_PREV,CI_CALLES,CI_DIRECCION,CI_ESTADO,CI_MOTIVO,EditDate"
         + "&returnGeometry=false&orderByFields=CI_FH_INI_PREV&f=json")
    x = json.loads(texto(u))
    if "error" in x: raise ValueError(f"la capa responde con error: {x['error'].get('message')}")
    if "features" not in x: raise ValueError("la respuesta no trae «features»")
    campos = {c["name"] for c in x.get("fields", [])}
    falta = {"CI_ID", "CI_FH_INI_PREV", "CI_FH_FIN_PREV", "CI_DIRECCION", "CI_ESTADO"} - campos
    if falta: raise ValueError(f"faltan campos: {', '.join(sorted(falta))}")
    return f"{len(x['features'])} cierres planificados o en curso en el visor"


def mtg(L):
    # Espacio.mtg: la capacidad de la capa Geo Colour del satélite MTG en EUMETView (la hora de la última imagen) y una imagen
    t = texto("https://view.eumetsat.int/geoserver/mtg_fd/rgb_geocolour/ows?service=WMS&request=GetCapabilities&version=1.3.0")
    m = re.search(r'<Dimension[^>]*name="time"[^>]*default="([^"]+)"', t)
    if not m: raise ValueError("la capacidad no dice la hora de la última imagen")
    ultima = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    if dt.datetime.now(dt.timezone.utc) - ultima > dt.timedelta(hours=2): raise ValueError(f"la última imagen es de {m.group(1)}")
    img = pedir("https://view.eumetsat.int/geoserver/ows?service=WMS&request=GetMap&version=1.3.0&layers=mtg_fd:rgb_geocolour&styles=&crs=EPSG:4326"
                f"&bbox={L['lat'] - 1.3},{L['lon'] - 2.3},{L['lat'] + 1.3},{L['lon'] + 2.3}&width=1100&height=800&format=image/jpeg&interpolations=bicubic&time={m.group(1)}")
    if img[:2] != b"\xff\xd8": raise ValueError("no manda JPEG")
    return f"última imagen {m.group(1)}"

def tierra(L):
    # Planeta.tierra: las fotos del último día de la cámara EPIC de la NASA
    x = json.loads(texto("https://epic.gsfc.nasa.gov/api/natural"))
    if not x or "image" not in x[0]: raise ValueError("la API no trae fotos")
    dia = x[0]["date"][:10]
    if (dt.date.today() - dt.date.fromisoformat(dia)).days > 7: raise ValueError(f"lo último es del {dia}")
    return f"{len(x)} fotos del {dia}"

def solVideo(L):
    # Espacio.solVideo: el vídeo de las últimas 48 horas del Sol (NASA SDO, AIA 171)
    r = urllib.request.Request("https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_512_0171.mp4", method="HEAD", headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=45) as f:
        mod, n = f.headers.get("Last-Modified"), int(f.headers.get("Content-Length") or 0)
    if n < 100_000: raise ValueError(f"el vídeo pesa {n} bytes")
    return f"{n // 1_000_000} MB, {mod}"

def ruta(L):
    # Camaras.trayecto (3.9, 268): las fotos de las cámaras del trayecto de Adra a Almería que elige la app (Balanegra, Santa María del
    # Águila, Vícar y Vía Parque; sin las de la entrada de Almería), con su hora
    if L["ine"] != "04003": return "NO COMPROBABLE: solo hay trayecto para Adra"
    horas = []
    for cid in ("516", "519", "521", "526"):
        with urllib.request.urlopen(urllib.request.Request(f"https://etraffic.dgt.es/camarasEtraffic/{cid}.jpg", headers={"User-Agent": UA}), timeout=45) as f:
            jpg, mod = f.read(), f.headers.get("Last-Modified")
        if len(jpg) < 2000 or jpg[:2] != b"\xff\xd8": raise ValueError(f"la cámara {cid} no manda una foto")
        horas.append(f"{cid} {email.utils.parsedate_to_datetime(mod).astimezone(TZ):%H:%M}" if mod else cid)
    return "fotos de " + ", ".join(horas)

def olas(L):
    # Olas.prevision (3.9, 275): los mapas de previsión de oleaje de Puertos del Estado (dominio Mar de Alborán): que el dominio siga en su
    # lista y que el mapa de las 00 UTC de hoy sea de la pasada de hoy o de ayer
    lista = json.loads(texto("https://portus.puertos.es/portussvr/api/mapStaticResources/VHM0Med?locale=es"))
    if not any(d.get("url", "").endswith("/wave_5") for d in lista): raise ValueError("la lista de mapas ya no trae el dominio wave_5 (Mar de Alborán)")
    hoy = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d00")
    r = urllib.request.urlopen(urllib.request.Request(f"https://portus.puertos.es/Portus/pathmaps/wave/wave_5/{hoy}/map_re.png", headers={"User-Agent": UA}), timeout=45)
    png, mod = r.read(), r.headers.get("Last-Modified")
    if png[:4] != b"\x89PNG": raise ValueError("el mapa no es una imagen PNG")
    m = email.utils.parsedate_to_datetime(mod) if mod else None
    if not m or dt.datetime.now(dt.timezone.utc) - m > dt.timedelta(hours=36): raise ValueError(f"el mapa de hoy es de una pasada vieja ({mod})")
    return f"pasada del {m.astimezone(TZ):%d/%m %H:%M}"

def viento(L):
    # Viento.ahora: el viento de ahora en la malla de 9 × 6 puntos (una petición con todos)
    la, lo = [], []
    for i in range(6):
        for j in range(9):
            la.append(f"{L['lat'] - 0.40 + 0.62 * i / 5:.3f}"); lo.append(f"{L['lon'] - 0.62 + 1.24 * j / 8:.3f}")
    x = json.loads(texto("https://api.open-meteo.com/v1/forecast?latitude=" + ",".join(la) + "&longitude=" + ",".join(lo)
                         + "&current=wind_speed_10m,wind_direction_10m,wind_gusts_10m&wind_speed_unit=kmh&timezone=Europe%2FMadrid"))
    if not isinstance(x, list) or len(x) != 54: raise ValueError(f"no trae los 54 puntos: {str(x)[:120]}")
    if any(p.get("current", {}).get("wind_speed_10m") is None for p in x): raise ValueError("algún punto sin viento")
    return f"54 puntos, {x[0]['current']['time']}"

def calarVivo(L):
    # CalarVivo: el vídeo MJPEG de la cámara de Calar Alto (solo las cabeceras y la primera imagen)
    r = urllib.request.Request("https://neteye-3.caha.es/WEBCAMs/EYE56", headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=30) as f:
        tipo = f.headers.get("Content-Type", "")
        cab = f.read(300)
    if "multipart/x-mixed-replace" not in tipo: raise ValueError(f"ya no es vídeo MJPEG ({tipo})")
    if not re.search(rb"Content-Length: \d+", cab): raise ValueError("las imágenes no traen Content-Length")
    return "vídeo MJPEG"


def jev_(L):
    """Jev (TypeSafe), para las tareas de la nube (titulares, receta, SAS, sortea2). Por Composio (JEV_CACHE): cuántas respuestas trajo
    el sandbox (vacía: NO COMPROBABLE). Con la clave: una pregunta mínima. Sin nada: NO COMPROBABLE."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jev
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        if os.environ.get("JEV_CACHE", "").strip():
            if not jev.cache(): raise PermissionError("la caché de Composio (JEV_CACHE) está vacía")
            return f"por el conector de Composio ({len(jev.cache())} respuestas)"
        raise PermissionError("sin Jev: ni la caché de Composio (JEV_CACHE) ni la variable TYPESAFE_API_KEY")
    try: r, modelo = jev.preguntar({"pueblo": L["nombre"]}, {"q": jev.noul("Is `pueblo` the name of a town?")}, intentos=2)
    except jev.SinJev as e: raise ValueError(str(e))          # hay clave y no vale: ROTA
    if not 0 <= r["q"]["noul"] <= 1: raise ValueError(f"respuesta rara: {r}")
    return f"responde ({modelo})"


FUENTES = [prevision, avisos, radar, satelite, playas, maritima, mareas, boya, oleaje, incendio, terremotos, efemerides, futbol, campo, lonja,
           trafico, gasolina, luz, aire, planeta, sol, farmacias, alimentarias, noticias, sonda, extras, paro, afiliados, euribor, festivos, rayos,
           medicamentos, productos, sae, fap, agua, camara, ruta, olas, radiacion, sequia, sangre, cortesAgua,
           mtg, tierra, solVideo, viento, calarVivo, iss, luna, jev_, esios]


def segunda_mirada(fuente, fallo, bruto, pedir_jev=None):
    """La web respondió pero falta la marca que busca la app: ¿el dato sigue en la página con otro formato? Solo una pista (con Jev)."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jev
    if not os.environ.get("TYPESAFE_API_KEY", "").strip() and pedir_jev is None and not jev.COMPOSIO: return ""   # en el sandbox de Composio, sí
    t = bruto.decode("utf-8", "replace")
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", t)))[:5000]
    try: r, _ = jev.preguntar({"fuente": fuente, "fallo": fallo, "pagina": t}, jev.preguntas_pagina(), intentos=2, pedir=pedir_jev)
    except (jev.SinJev, ValueError): return ""
    p = r["sigue"]["noul"]
    return " · Jev: el dato parece seguir en la página (¿cambio de formato?)" if p >= 0.7 else " · Jev: el dato ya no parece estar en la página" if p <= 0.3 else ""


def revisar(L=ADRA, solo=None):
    def una(f):
        ULTIMA.b = b""
        try: return f.__name__, "BIEN", f(L)
        except PermissionError as e: return f.__name__, "NO COMPROBABLE", str(e)
        except Exception as e:
            d = f"{type(e).__name__}: {e}"[:200]
            if isinstance(e, (ValueError, KeyError)) and ULTIMA.b: d += segunda_mirada(f.__name__, d, ULTIMA.b)
            return f.__name__, "ROTA", d
    with ThreadPoolExecutor(6) as ex:
        return list(ex.map(una, [f for f in FUENTES if not solo or f.__name__ in solo]))


def main():
    a = argparse.ArgumentParser(); a.add_argument("--json"); o = a.parse_args()
    r = revisar()
    for n, e, d in r: print(f"{e:15} {n:13} {d}")
    if o.json:
        json.dump({"revisado": dt.datetime.now(TZ).isoformat(timespec="minutes"), "fuentes": [dict(fuente=n, estado=e, detalle=d) for n, e, d in r]},
                  open(o.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rotas = [n for n, e, _ in r if e == "ROTA"]
    print(f"\n{len(r) - len(rotas)}/{len(r)} bien" + (f" · ROTAS: {', '.join(rotas)}" if rotas else ""))
    sys.exit(1 if rotas else 0)


if __name__ == "__main__":
    main()
