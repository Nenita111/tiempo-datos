"""Sorteos de cuentas de la zona con la API oficial de Instagram (Business Discovery), sin entrar en Instagram.

Lee las publicaciones públicas recientes de una lista de cuentas profesionales (comercios, ayuntamientos, medios)
y devuelve las que hablan de un sorteo. Hace falta una cuenta profesional propia enlazada a una página de Facebook
y una app de Meta en modo desarrollo. El token de la página va en la variable IG_TOKEN del entorno en la nube (si no, se espera que lo añada el proxy: Bearer
para graph.facebook.com): lo añade el proxy y la sesión no lo ve. Con él, el id de la cuenta de Instagram se averigua
solo (IG_USER_ID lo fija a mano). Si existe IG_TOKEN se usa ese (pruebas); nunca se escribe en el repositorio ni en la
salida. Una petición por cuenta.

  python3 instagram_oficial.py @cuenta1 @cuenta2 … [--dias 21] > candidatos.json
  python3 instagram_oficial.py --probar      # ¿está configurado y deja leer cuentas ajenas?

Sale con código 3 si no está configurado. Solo propone: el sorteo se apunta con sorteos.py si en el texto se ven
premio, pueblo, fecha y hora de fin.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.error, urllib.parse, urllib.request

API = "https://graph.facebook.com/v24.0"
CUENTA = re.compile(r"^@?([A-Za-z0-9._]{1,30})$")
SORTEO = re.compile(r"sorte(o|os|amos|a|an)\b|giveaway|regalamos|concurso", re.I)
SIN_CONFIGURAR = 3


def cuenta_limpia(c):
    m = CUENTA.match(c.strip())
    if not m: raise ValueError(f"cuenta no válida: {c!r}")
    return m.group(1)


def campos(cuenta, n=12):
    return f"business_discovery.username({cuenta_limpia(cuenta)}){{username,media.limit({n}){{caption,permalink,timestamp}}}}"


def candidatos(resp, ahora, dias=21):
    """Publicaciones de los últimos `dias` días cuyo texto habla de un sorteo."""
    bd = resp.get("business_discovery") or {}
    usuario, salen = bd.get("username"), []
    for m in (bd.get("media") or {}).get("data", []):
        texto = m.get("caption") or ""
        try: cuando = dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError): continue
        if ahora - cuando > dt.timedelta(days=dias) or not SORTEO.search(texto): continue
        salen.append({"cuenta": "@" + usuario, "enlace": m.get("permalink"), "publicado": cuando.isoformat(), "texto": texto})
    return salen


def leer(ruta, params, token, abrir=urllib.request.urlopen):
    """GET a la API Graph. token=None: la cabecera la pone el proxy del entorno (network secret)."""
    url = f"{API}/{ruta}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with abrir(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        try: err = json.load(e).get("error", {})
        except ValueError: err = {}
        msg = err.get("message", "")
        if token: msg = msg.replace(token, "***")
        raise RuntimeError(f"HTTP {e.code} (código {err.get('code', '?')}): {msg}"[:300]) from None


def pedir(cuenta, token, uid, abrir=urllib.request.urlopen):
    return leer(uid, {"fields": campos(cuenta)}, token, abrir)


def id_propio(token, abrir=urllib.request.urlopen):
    """Id de la cuenta profesional propia: con token de página sale de la página; con token de usuario, de sus páginas."""
    try:
        r = leer("me", {"fields": "instagram_business_account"}, token, abrir)
        if (r.get("instagram_business_account") or {}).get("id"): return r["instagram_business_account"]["id"]
    except RuntimeError:
        pass
    r = leer("me/accounts", {"fields": "instagram_business_account"}, token, abrir)
    for p in r.get("data", []):
        if (p.get("instagram_business_account") or {}).get("id"): return p["instagram_business_account"]["id"]
    raise RuntimeError("el token no tiene ninguna cuenta de Instagram profesional enlazada")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("cuentas", nargs="*"); a.add_argument("--dias", type=int, default=21)
    a.add_argument("--probar", action="store_true")
    o = a.parse_args()
    token, uid = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    tapar = (lambda s: s.replace(token, "***")) if token else (lambda s: s)
    if uid and not uid.isdigit(): sys.exit("IG_USER_ID debe ser solo cifras.")
    if not uid:
        try: uid = id_propio(token)
        except (RuntimeError, OSError) as e:
            print(tapar(f"Sin configurar: {e}"), file=sys.stderr)
            sys.exit(SIN_CONFIGURAR)
    if o.probar:
        try:
            r = pedir("@instagram", token, uid)
            n = len(((r.get("business_discovery") or {}).get("media") or {}).get("data", []))
            print(json.dumps({"ig_user_id": uid, "prueba": f"bien: lee cuentas ajenas ({n} publicaciones de @instagram)"}, ensure_ascii=False))
        except (RuntimeError, OSError) as e:
            print(json.dumps({"ig_user_id": uid, "prueba": "fallo: " + tapar(str(e))}, ensure_ascii=False))
            sys.exit(1)
        return
    salida = {"ig_user_id": uid, "leidas": [], "errores": {}, "candidatos": []}
    ahora = dt.datetime.now(dt.timezone.utc)
    for c in o.cuentas:
        try:
            salida["candidatos"] += candidatos(pedir(c, token, uid), ahora, o.dias)
            salida["leidas"].append(cuenta_limpia(c))
        except (ValueError, RuntimeError, OSError) as e:
            salida["errores"][c] = tapar(str(e))
    json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
