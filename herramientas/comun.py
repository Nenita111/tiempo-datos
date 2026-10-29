"""Lo común a los scripts de la nube (3.9, lo pidió Isa: «optimiza y factoriza»): la zona horaria, las peticiones con reintentos, el texto
limpio de una página y guardar extras.json sin dejarlo a medias.

Cada script sigue diciendo con qué agente pide (el de la app o el suyo): aquí no se cambia ninguno, ni para saltarse un bloqueo.
"""
import html, json, os, re, tempfile, time, unicodedata, urllib.error, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
UA_APP = "Mozilla/5.0 (Linux; Android 11; AFT) TiempoYRadar/1.0"       # el de la app de la tele
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def pedir(url, ua=UA_APP, cuerpo=None, tipo=None, aceptar=None, timeout=60, intentos=3, pausa=3, dormir=time.sleep):
    """Los bytes de la respuesta. Reintenta los cortes de conexión, los 429 y los 5xx (con espera creciente); un 4xx, no (no va a cambiar)."""
    cab = {"User-Agent": ua}
    if tipo: cab["Content-Type"] = tipo
    if aceptar: cab["Accept"] = aceptar
    for n in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=timeout) as r: return r.read()
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or n == intentos - 1: raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if n == intentos - 1: raise
        dormir(pausa * (n + 1))


def limpio(s):
    """El texto de un trozo de HTML: sin etiquetas, sin entidades y con los espacios juntos."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def leer(ruta):
    with open(ruta, encoding="utf-8") as f: return json.load(f)


def guardar(ruta, x):
    """extras.json (o el que sea) a un fichero temporal al lado y luego en su sitio: si el paso se corta a medias (diario.py lo mata al
    pasarse de tiempo), el de antes sigue entero."""
    d = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".guardando-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ruta)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
