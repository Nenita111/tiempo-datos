"""Lo común a los scripts de la nube (3.9, lo pidió Isa: «optimiza y factoriza»; ampliado el 15 nov 2026: «optimiza y factoriza, evita
datos duplicados»): la zona horaria y el día de hoy, el pueblo y sus coordenadas, los municipios de la provincia, las peticiones con
reintentos, el texto limpio de una página o de un PDF y guardar extras.json sin dejarlo a medias y con su hora.

Cada script sigue diciendo con qué agente pide (el de la app o el suyo): aquí no se cambia ninguno, ni para saltarse un bloqueo.
"""
import datetime as dt, html, json, math, os, re, subprocess, sys, tempfile, time, unicodedata, urllib.error, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
UA_APP = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app de la tele
UA_CORTO = "TiempoYRadar/1.0"                                           # el de los informes en PDF (Junta, IGN)
UA_TAREAS = "TiempoYRadar/1.0 (tareas de la tele)"                      # el de las tareas que preguntan a Jev
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
# el pueblo de la tele: su nombre, su código INE y su centro (latitud, longitud); antes, repetidos en cada script
LUGAR, INE, ADRA = "Adra", "04003", (36.7480, -3.0213)
AQUI = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ el día y la hora (siempre los de España, vaya como vaya el servidor)
def ahora():
    return dt.datetime.now(TZ)


def hoy():
    return ahora().date()


# ------------------------------------------------------------------ peticiones
def _responder(url, ua, cuerpo, tipo, aceptar, timeout, intentos, pausa, dormir, metodo=None):
    """(bytes, cabeceras) de la respuesta. Reintenta los cortes de conexión, los 429 y los 5xx (con espera creciente); un 4xx, no (no va
    a cambiar)."""
    cab = {"User-Agent": ua}
    if tipo: cab["Content-Type"] = tipo
    if aceptar: cab["Accept"] = aceptar
    for n in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab, method=metodo), timeout=timeout) as r:
                return r.read(), getattr(r, "headers", {})
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or n == intentos - 1: raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if n == intentos - 1: raise
        dormir(pausa * (n + 1))


def pedir(url, ua=UA_APP, cuerpo=None, tipo=None, aceptar=None, timeout=60, intentos=3, pausa=3, dormir=time.sleep):
    """Los bytes de la respuesta. Reintenta los cortes de conexión, los 429 y los 5xx (con espera creciente); un 4xx, no (no va a cambiar)."""
    return _responder(url, ua, cuerpo, tipo, aceptar, timeout, intentos, pausa, dormir)[0]


def cabeceras(url, ua=UA_APP, timeout=60, intentos=3, pausa=3, dormir=time.sleep):
    """Las cabeceras de la respuesta a un HEAD, con los mismos reintentos: para saber si un fichero grande ha cambiado («Last-Modified»)
    sin bajarlo."""
    return _responder(url, ua, None, None, None, timeout, intentos, pausa, dormir, metodo="HEAD")[1]


# ------------------------------------------------------------------ textos
def limpio(s):
    """El texto de un trozo de HTML: sin etiquetas, sin entidades y con los espacios juntos."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def solo_ascii(s):
    """Sin tildes ni nada que no sea ASCII, y en minúsculas: para buscar un pueblo o una palabra en un titular."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def num(s):
    """«1.234,5» (como se escribe aquí) → 1234.5."""
    return float(s.replace(".", "").replace(",", "."))


def enlace_limpio(url):
    """Los enlaces de Instagram, sin «?igsh=…» ni «?utm_…»: el QR sale más pequeño y fácil de leer. Los demás, como vienen."""
    url = url.strip()
    return re.sub(r"\?.*$", "", url) if "instagram.com" in url else url


def texto_pdf(datos, *opciones, tiempo=None, comprobar=True):
    """El texto de un PDF con pdftotext (poppler) y sus opciones («-layout», «-l», «4»…). Con comprobar, un PDF que no se lee es un fallo;
    sin él, da lo que haya salido."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", *opciones, p, "-"], capture_output=True, text=True, timeout=tiempo, check=comprobar).stdout


# ------------------------------------------------------------------ distancias y municipios
def km(a, b):
    """Los kilómetros, en línea recta, entre dos puntos (latitud, longitud) cercanos."""
    return math.hypot((a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110.57)


def municipios():
    """Los municipios de la provincia de Almería (municipios_almeria.json: INE e IGN, Nomenclátor Geográfico Básico), cada uno
    [nombre, código INE, latitud, longitud] (los de la capital de su municipio)."""
    return leer(os.path.join(AQUI, "municipios_almeria.json"))["municipios"]


def coordenadas():
    """{nombre sin tildes y en minúsculas: (latitud, longitud)} de los municipios de la provincia."""
    return {sin_tildes(m[0]): (m[2], m[3]) for m in municipios()}


# ------------------------------------------------------------------ extras.json
def leer(ruta):
    with open(ruta, encoding="utf-8") as f: return json.load(f)


def guardar(ruta, x, **formato):
    """extras.json (o el que sea) a un fichero temporal al lado y luego en su sitio: si el paso se corta a medias (diario.py lo mata al
    pasarse de tiempo), el de antes sigue entero."""
    d = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".guardando-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1, **formato)
        os.replace(tmp, ruta)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def publicar(ruta, x, cuando=None):
    """Guarda extras.json con su hora en «actualizado»: la tele se queda con el más nuevo."""
    x["actualizado"] = (cuando or ahora()).isoformat(timespec="minutes")
    guardar(ruta, x)


def poner(ruta, x, clave, nuevo):
    """Pone x[clave] y lo publica, solo si ha cambiado (si no, el fichero no se toca y la tele no lo vuelve a bajar). Dice si ha cambiado."""
    if x.get(clave) == nuevo: return False
    x[clave] = nuevo
    publicar(ruta, x)
    return True


def decir(o):
    """El resumen de un paso: una línea JSON (diario.py se queda con la última)."""
    print(json.dumps(o, ensure_ascii=False))


def fallar(e, codigo=1):
    """Un paso que no ha podido: lo dice en su línea ({"error": …}) y sale con su código; extras.json queda como estaba."""
    decir({"error": str(e)[:200]})
    sys.exit(codigo)
