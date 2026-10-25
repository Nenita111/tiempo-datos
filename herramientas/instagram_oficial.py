"""Sorteos de cuentas de la zona con la API oficial de Instagram (Business Discovery), sin entrar en Instagram.

Lee las publicaciones públicas recientes de una lista de cuentas profesionales (comercios, ayuntamientos, medios)
y devuelve las que hablan de un sorteo. Hace falta una cuenta profesional propia enlazada a una página de Facebook
y una app de Meta en modo desarrollo. El token y el id de esa cuenta van en variables de entorno (IG_TOKEN e
IG_USER_ID), nunca en el repositorio ni en la salida. Una petición por cuenta.

  python3 instagram_oficial.py @cuenta1 @cuenta2 … [--dias 21] > candidatos.json

Solo propone: el sorteo se apunta con sorteos.py si en el texto se ven premio, pueblo, fecha y hora de fin.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.error, urllib.parse, urllib.request

API = "https://graph.facebook.com/v24.0"
CUENTA = re.compile(r"^@?([A-Za-z0-9._]{1,30})$")
SORTEO = re.compile(r"sorte(o|os|amos|a|an)\b|giveaway|regalamos|concurso", re.I)


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


def pedir(cuenta, token, uid, abrir=urllib.request.urlopen):
    url = f"{API}/{uid}?" + urllib.parse.urlencode({"fields": campos(cuenta)})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with abrir(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        try: msg = json.load(e).get("error", {}).get("message", "")
        except ValueError: msg = ""
        raise RuntimeError(f"HTTP {e.code}: {msg.replace(token, '***')}"[:300]) from None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("cuentas", nargs="+"); a.add_argument("--dias", type=int, default=21)
    o = a.parse_args()
    token, uid = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not uid: sys.exit("Sin configurar: faltan las variables de entorno IG_TOKEN e IG_USER_ID.")
    ahora, salida = dt.datetime.now(dt.timezone.utc), {"leidas": [], "errores": {}, "candidatos": []}
    for c in o.cuentas:
        try:
            salida["candidatos"] += candidatos(pedir(c, token, uid), ahora, o.dias)
            salida["leidas"].append(cuenta_limpia(c))
        except (ValueError, RuntimeError, OSError) as e:
            salida["errores"][c] = str(e).replace(token, "***")
    json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
