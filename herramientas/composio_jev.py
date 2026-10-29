"""Jev por el conector JEV de Composio, para las tareas programadas (lo pidió Isa el 29 oct 2026: «usa el conector de Jev de Composio de
ahora en adelante»). Se ejecuta en el sandbox de Composio (COMPOSIO_REMOTE_WORKBENCH), donde están run_composio_tool y upload_local_file:
baja la misma versión del repositorio que tiene la tarea, repite los pasos que preguntan a Jev (con jev.COMPOSIO = run_composio_tool) y
sube las respuestas (jev.GUARDADAS) a un fichero. La tarea lo baja y ejecuta sus scripts con JEV_CACHE=<ese fichero>: las mismas
preguntas encuentran su respuesta y lo que no está se queda sin Jev (jev.py lo explica). Aquí no se escribe nada que se guarde: el
extras.json del sandbox se tira; el que vale es el de la tarea.

En la tarea, una celda del workbench (SHA = `git rev-parse HEAD` del clon de la tarea, para que el código y extras.json sean los mismos):
  import urllib.request as u; exec(u.urlopen("https://raw.githubusercontent.com/Nenita111/tiempo-datos/SHA/herramientas/composio_jev.py").read().decode(), globals()); print(jev_correr("diario", "SHA"))
Si contesta «"listo": false», otra celda: print(jev_esperar()). Con «"listo": true» trae «url» (y «error» si algo falló):
  mkdir -p /tmp/jev && curl -sSL "URL" -o /tmp/jev/cache.json && JEV_CACHE=/tmp/jev/cache.json python3 -I herramientas/diario.py extras.json
Pasos: "diario" (los de diario.py que quitan lo pasado y los que preguntan a Jev, en su orden, y sortea2.py) y "avisos" (los titulares de
avisos_movil.py). Capturas del buzón, lo mismo que comprobar_captura.py: print(jev_captura("SHA", texto, {"cuenta": "@…", "hasta": "…"}, "sorteo")).
Fuentes rotas de la revisión (3.7): print(jev_revision("SHA", ["luz", …])): el sandbox las vuelve a pedir y, si la web responde pero falta la
marca, Jev dice si el dato parece seguir en la página («pistas»).

Las respuestas de Jev se guardan en el sandbox (CACHE, en /mnt/files, que Composio conserva) 14 días desde la última vez que se usaron: lo que
ya se preguntó (los mismos titulares cada 2 horas, las mismas ofertas cada día) no se vuelve a preguntar.
"""
import contextlib, io, json, os, runpy, shutil, sys, tarfile, threading, time, urllib.request, uuid

JEV_REPO = "Nenita111/tiempo-datos"
JEV_BASE = "/home/user/tiempo-datos-"
JEV_CACHE = "/mnt/files/tiempo/jev_cache.json"     # {clave: {"r": respuesta, "t": "AAAA-MM-DD" de la última vez que se usó}}
JEV_DIAS = 14
JEV_MAX = 480          # 3.9: pasados 8 minutos, lo que quede se deja sin Jev (la tarea no espera celda tras celda)
_jev = globals().setdefault("_jev", {"hilo": None, "estado": None, "raiz": None, "sha": None})


class _JevSalida:
    """Lo que escriben los scripts (fuera del hilo principal) no sale en la celda: solo el resumen."""
    def __init__(self, orig, buf): self.orig, self.buf = orig, buf
    def write(self, s): return (self.orig if threading.current_thread() is threading.main_thread() else self.buf).write(s)
    def flush(self):
        try: self.orig.flush()
        except Exception: pass
    def __getattr__(self, a): return getattr(self.orig, a)


def _jev_repo(sha):
    """El repositorio en esa versión (sin SHA, main) en una carpeta nueva; con el mismo SHA se reutiliza."""
    if sha and _jev["sha"] == sha and _jev["raiz"] and os.path.isdir(_jev["raiz"]): return _jev["raiz"]
    datos = urllib.request.urlopen(urllib.request.Request(f"https://codeload.github.com/{JEV_REPO}/tar.gz/{sha or 'main'}",
                                   headers={"User-Agent": "TiempoYRadar/1.0 (tareas de la tele)"}), timeout=90).read()
    base = JEV_BASE + uuid.uuid4().hex[:8]
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as t: t.extractall(base, filter="data")
    raiz = os.path.join(base, os.listdir(base)[0])
    for d in os.listdir("/home/user"):                     # las de otras veces (nunca la que usa un hilo en marcha)
        p = os.path.join("/home/user", d)
        if p.startswith(JEV_BASE) and p != base and not (_jev["hilo"] and _jev["hilo"].is_alive() and (_jev["raiz"] or "").startswith(p)):
            shutil.rmtree(p, ignore_errors=True)
    _jev["raiz"], _jev["sha"] = raiz, sha
    return raiz


def _jev_cargar(raiz):
    """Los módulos de herramientas/ de esa carpeta (fuera los de otra versión), con Jev por Composio."""
    h = os.path.join(raiz, "herramientas")
    nombres = {f[:-3] for f in os.listdir(h) if f.endswith(".py")}
    for m in list(sys.modules):
        if m in nombres: del sys.modules[m]
    sys.path[:] = [p for p in sys.path if not p.startswith(JEV_BASE)]
    sys.path.insert(0, h)
    os.environ["TZ"] = "Europe/Madrid"; time.tzset()      # como en la tarea (el sandbox va en UTC)
    for v in ("JEV_CACHE", "JEV_FALTAN"): os.environ.pop(v, None)
    import jev
    jev.COMPOSIO, jev.GUARDADAS, jev._CACHE = run_composio_tool, {}, {k: v["r"] for k, v in _jev_leer().items()}
    return jev


def _jev_leer():
    try:
        with open(JEV_CACHE, encoding="utf-8") as f: c = json.load(f)
        return c if isinstance(c, dict) else {}
    except (OSError, ValueError): return {}


def _jev_guardar(usadas):
    """Lo usado en esta pasada, con la fecha de hoy; fuera lo que no se usa desde hace más de JEV_DIAS días."""
    import datetime as dt
    hoy = dt.date.today(); c = _jev_leer()
    for k, r in usadas.items(): c[k] = {"r": r, "t": hoy.isoformat()}
    c = {k: v for k, v in c.items() if (hoy - dt.date.fromisoformat(v.get("t", "2000-01-01"))).days <= JEV_DIAS}
    try:
        os.makedirs(os.path.dirname(JEV_CACHE), exist_ok=True)
        with open(JEV_CACHE + ".tmp", "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False)
        os.replace(JEV_CACHE + ".tmp", JEV_CACHE)
    except OSError: pass
    return len(c)


def _jev_paso(raiz, script, *args):
    """Un script como en la tarea (python3 herramientas/<script> <args>, desde la raíz). Lo que imprime no importa: solo sus preguntas."""
    argv, cwd = sys.argv[:], os.getcwd()
    sys.argv = [script, *args]; os.chdir(raiz)
    try:
        runpy.run_path(os.path.join(raiz, "herramientas", script), run_name="__main__")
        return "ok"
    except SystemExit as e:
        return "ok" if e.code in (None, 0) else f"código {e.code}"
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"[:200]
    finally:
        sys.argv = argv; os.chdir(cwd)


def _jev_diario(raiz, est):
    import diario
    x = os.path.join(raiz, "extras.json")
    for nombre, script, _ in diario.PASOS:
        if nombre in diario.PREVIOS + diario.CON_JEV:
            s, *opc = script.split()
            est["pasos"][nombre] = _jev_paso(raiz, s, x, *opc)
    est["pasos"]["sortea2"] = _jev_paso(raiz, "sortea2.py")


def _jev_avisos(raiz, est):
    import datetime as dt, avisos_movil as A
    fallos = []
    _, bien = A.cortes_titulares(A.LUGAR, dt.datetime.now(A.TZ), A.Juez(), fallos)
    est["pasos"]["titulares"] = "ok" if bien else "; ".join(fallos)[:200] or "sin titulares"


def _jev_trabajo(paso, sha, est):
    t0 = time.time()
    try:
        raiz = _jev_repo(sha)
        jev = _jev_cargar(raiz)
        jev.LIMITE = t0 + JEV_MAX
        {"diario": _jev_diario, "avisos": _jev_avisos}[paso](raiz, est)
        if jev.CAIDO: est["caido"] = jev.CAIDO[:200]          # Composio dejó de contestar (o se acabó el tiempo): lo demás, sin Jev
        f = os.path.join(os.path.dirname(raiz), "jev_cache.json")
        with open(f, "w", encoding="utf-8") as x: json.dump(jev.GUARDADAS, x, ensure_ascii=False)
        est["respuestas"] = len(jev.GUARDADAS)
        est["guardadas"] = _jev_guardar(jev.GUARDADAS)
        r, err = upload_local_file(f)
        if err: raise RuntimeError(f"no se pudo subir: {err}")
        d = r.get("data") if isinstance(r, dict) and isinstance(r.get("data"), dict) else r
        est["url"] = (d or {}).get("s3_url")
        if not est["url"]: raise RuntimeError("la subida no dio URL")
    except Exception as e:
        est["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        est["s"], est["listo"] = round(time.time() - t0), True


def _jev_resumen(est):
    return json.dumps({k: v for k, v in est.items() if k != "salida"}, ensure_ascii=False)


def jev_esperar(espera=160):
    """Espera (como mucho «espera» segundos, menos que los 180 de una celda) a que acabe lo que se arrancó con jev_correr."""
    h, est = _jev["hilo"], _jev["estado"]
    if not h: return json.dumps({"listo": False, "error": "no hay nada en marcha: jev_correr primero"}, ensure_ascii=False)
    h.join(espera)
    return _jev_resumen(est)


def jev_correr(paso, sha=None, espera=160):
    """Arranca el paso («diario» o «avisos») en un hilo y espera hasta «espera» segundos; si no ha acabado, jev_esperar()."""
    if paso not in ("diario", "avisos"): raise ValueError("paso: «diario» o «avisos»")
    h = _jev["hilo"]
    if h and h.is_alive():
        h.join(espera)                                     # otra tarea lo está usando: se espera a que acabe
        if h.is_alive(): return json.dumps({"listo": False, "ocupado": "otra tarea sigue en marcha: repite jev_correr"}, ensure_ascii=False)
    est = {"paso": paso, "sha": sha, "listo": False, "pasos": {}}
    buf = io.StringIO()
    salida = (sys.stdout, sys.stderr)
    if not isinstance(sys.stdout, _JevSalida): sys.stdout, sys.stderr = _JevSalida(sys.stdout, buf), _JevSalida(sys.stderr, buf)

    def trabajo():
        try: _jev_trabajo(paso, sha, est)
        finally:
            est["salida"] = buf.getvalue()[-2000:]
            if isinstance(sys.stdout, _JevSalida): sys.stdout, sys.stderr = salida

    _jev["hilo"], _jev["estado"] = threading.Thread(target=trabajo, daemon=True), est
    _jev["hilo"].start()
    return jev_esperar(espera)


def _jev_ocupado(espera=60):
    """Si otra tarea tiene un paso en marcha en este sandbox, se espera un minuto como mucho (una celda dura 180 s y aún hay que hacer lo
    propio); si sigue, «ocupado»: repetir la llamada en otra celda."""
    h = _jev["hilo"]
    if h and h.is_alive(): h.join(espera)
    if h and h.is_alive(): return json.dumps({"ocupado": "otra tarea sigue en marcha: repite la llamada"}, ensure_ascii=False)
    return None


def jev_captura(sha, texto, datos, tipo=None):
    """Lo de comprobar_captura.py (dato por dato, ¿lo dice la captura?; con tipo, además ¿qué anuncia?) por Composio:
    {"ok", "datos", "no_cuadra", "juez", "tipo"}."""
    o = _jev_ocupado()
    if o: return o
    raiz = _jev_repo(sha)
    jev = _jev_cargar(raiz)
    import comprobar_captura as C
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        r = C.comprobar(texto, datos, tipo=tipo)
    _jev_guardar(jev.GUARDADAS)
    return json.dumps(r, ensure_ascii=False)


def jev_revision(sha, fuentes):
    """Las fuentes que la revisión de la tarea dio por ROTAS, otra vez desde el sandbox: {"fuentes": {nombre: [estado, detalle]}}; si la web
    responde pero falta la marca, el detalle lleva la pista de Jev («el dato parece seguir en la página…»)."""
    o = _jev_ocupado()
    if o: return o
    raiz = _jev_repo(sha)
    jev = _jev_cargar(raiz)
    import revisar_fuentes as R
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        r = R.revisar(solo=set(fuentes))
    _jev_guardar(jev.GUARDADAS)
    return json.dumps({"fuentes": {n: [e, d] for n, e, d in r}}, ensure_ascii=False)
