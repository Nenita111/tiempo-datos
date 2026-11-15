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
def respuesta(url, ua=UA_APP, cuerpo=None, tipo=None, aceptar=None, timeout=60, intentos=3, pausa=3, dormir=time.sleep, metodo=None, hasta=None):
    """(bytes, cabeceras) de la respuesta. Reintenta los cortes de conexión, los 429 y los 5xx (con espera creciente); un 4xx, no (no va
    a cambiar). Con intentos=1 no insiste. metodo="HEAD": solo las cabeceras; hasta=N: solo los primeros N bytes (un vídeo que no acaba)."""
    cab = {"User-Agent": ua}
    if tipo: cab["Content-Type"] = tipo
    if aceptar: cab["Accept"] = aceptar
    for n in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab, method=metodo), timeout=timeout) as r:
                return (r.read() if hasta is None else r.read(hasta)), getattr(r, "headers", {})
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or n == intentos - 1: raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if n == intentos - 1: raise
        dormir(pausa * (n + 1))


def pedir(url, ua=UA_APP, cuerpo=None, tipo=None, aceptar=None, timeout=60, intentos=3, pausa=3, dormir=time.sleep):
    """Los bytes de la respuesta, con los reintentos de respuesta()."""
    return respuesta(url, ua, cuerpo, tipo, aceptar, timeout, intentos, pausa, dormir)[0]


def cabeceras(url, ua=UA_APP, timeout=60, intentos=3, pausa=3, dormir=time.sleep):
    """Las cabeceras de la respuesta a un HEAD, con los mismos reintentos: para saber si un fichero grande ha cambiado («Last-Modified»)
    sin bajarlo."""
    return respuesta(url, ua, timeout=timeout, intentos=intentos, pausa=pausa, dormir=dormir, metodo="HEAD")[1]


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


# ------------------------------------------------------------------ lo que los scripts recuerdan y la tele no lee
ESTADO = "estado_diario.json"       # al lado de extras.json; se sube con él


def _ruta_estado(ruta):
    return os.path.join(os.path.dirname(os.path.abspath(ruta)), ESTADO)


def _estado(ruta):
    try: e = leer(_ruta_estado(ruta))
    except (OSError, ValueError): return {}
    return e if isinstance(e, dict) else {}


def recuerdo(ruta, x, clave):
    """Lo que un script recuerda de un día para otro y la tele no lee (las ayudas ya cerradas, el programa leído de «Adra en la Senda»…):
    de estado_diario.json, al lado de extras.json (ruta). Hasta el 15 nov 2026 iba dentro de extras.json: si sigue allí y el estado no lo
    tiene, vale ese. Sin nada, None (el script empieza de cero: solo tarda más)."""
    e = _estado(ruta)
    return e[clave] if clave in e else x.get(clave)


def recordar(ruta, x, clave, valor):
    """Lo apunta en estado_diario.json (solo si ha cambiado) y lo quita de extras.json si seguía allí. Dice si lo ha quitado: entonces hay que
    publicar extras.json."""
    e = _estado(ruta)
    if clave not in e or e[clave] != valor:
        e[clave] = valor
        guardar(_ruta_estado(ruta), e, sort_keys=True)
    return x.pop(clave, None) is not None


# ------------------------------------------------------------------ lo que la página entiende de extras.json
PAGINA = os.path.join(AQUI, "..", "nube", "pagina", "index.html")      # la página publicada: la misma de la tele (la pone publicar_nube.py)
ESPERA_V = 7        # días desde que se publica una página que entiende un extras.json más corto hasta que se le da


def extras_v(ruta, dia=None, pagina=None):
    """La versión de extras.json que ya se puede escribir. La dice la página publicada («const EXTRAS_V = N»; sin eso, 1), pero solo vale
    ESPERA_V días después de verla por primera vez (se apunta en estado_diario.json): la tele instala la versión nueva cuando Isa la acepta
    con el mando, y hasta entonces sigue con la de antes.
      2: el «enlace» de un curso o de una ayuda no se guarda si es el de su lista más su número (sin_enlaces_deducibles)."""
    try:
        with open(pagina or PAGINA, encoding="utf-8") as f: m = re.search(r"\bconst EXTRAS_V = (\d+)\b", f.read())
    except OSError: m = None
    v = int(m.group(1)) if m else 1
    if v <= 1: return 1
    dia = dia or hoy()
    e = _estado(ruta)
    visto = e.get("extrasV") or {}
    if visto.get("v") != v:
        ya = visto.get("v", 1) if dia.isoformat() >= visto.get("vale", "9999") else visto.get("antes", 1)
        visto = e["extrasV"] = {"v": v, "antes": ya, "vale": (dia + dt.timedelta(days=ESPERA_V)).isoformat()}
        guardar(_ruta_estado(ruta), e, sort_keys=True)
    return v if dia.isoformat() >= visto["vale"] else visto["antes"]


def sin_enlaces_deducibles(lista, base, clave):
    """Quita de cada elemento de la lista el «enlace» que es el de la lista más su número (base + "/" + elemento[clave]): son todos y pesan
    más que el resto de la ficha; la página lo deduce (EXTRAS_V 2)."""
    for o in lista:
        if o.get("enlace") == f"{base}/{o.get(clave)}": del o["enlace"]
    return lista


def apuntar_aviso(ruta, texto):
    """Deja un aviso para el móvil de Isa (una línea): diario.py los recoge al acabar («avisar») y la tarea diaria los manda."""
    e = _estado(ruta)
    if texto not in e.setdefault("avisos", []):
        e["avisos"].append(texto)
        guardar(_ruta_estado(ruta), e, sort_keys=True)


def recoger_avisos(ruta):
    """Los avisos que han dejado los scripts (apuntar_aviso), que dejan de estar pendientes."""
    e = _estado(ruta)
    avisos = e.pop("avisos", [])
    if avisos: guardar(_ruta_estado(ruta), e, sort_keys=True)
    return avisos


def decir(o):
    """El resumen de un paso: una línea JSON (diario.py se queda con la última)."""
    print(json.dumps(o, ensure_ascii=False))


def fallar(e, codigo=1):
    """Un paso que no ha podido: lo dice en su línea ({"error": …}) y sale con su código; extras.json queda como estaba."""
    decir({"error": str(e)[:200]})
    sys.exit(codigo)
