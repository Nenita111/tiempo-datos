"""Sorteos de Instagram de la zona para la tele (pantalla Noticias), guardados en extras.json.

La tele no entra en Instagram: los sorteos se apuntan aquí (los encontrados en la web pública o los que llegan a mano)
y la tele los enseña hasta que acaba su plazo, con un código QR (lo dibuja la propia tele) para abrir la publicación con el móvil.

  python3 sorteos.py extras.json --anadir --cuenta @tienda --premio "Cesta de productos" --lugar Adra \
      --hasta 2026-10-31T23:59 --enlace https://www.instagram.com/p/XXXX/ [--como "seguir y mencionar a 2"] [--fuente "web"]
  python3 sorteos.py extras.json --buscado            # apunta que hoy se ha buscado (aunque no haya ninguno)
  python3 sorteos.py extras.json --podar              # quita los que ya han acabado
"""
import argparse, datetime as dt, json, re, sys
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
ZONA = "de Motril a Almería"


def enlace_limpio(url):
    """Sin «?igsh=…» ni «?utm_…»: el QR sale más pequeño y fácil de leer."""
    url = url.strip()
    return re.sub(r"\?.*$", "", url) if "instagram.com" in url else url


def hora(texto):
    """«2026-10-31T23:59» (hora de España) → ISO con su desfase, para que la tele no dude."""
    t = dt.datetime.fromisoformat(texto)
    return (t if t.tzinfo else t.replace(tzinfo=TZ)).isoformat(timespec="minutes")


def podar(x, ahora=None):
    ahora = ahora or dt.datetime.now(TZ)
    x["sorteos"] = [s for s in x.get("sorteos", []) if dt.datetime.fromisoformat(s["hasta"]) > ahora]
    for s in x["sorteos"]: s.pop("qr", None)   # el QR ya lo dibuja la tele
    return x


def anadir(x, cuenta, premio, lugar, hasta, enlace, como=None, fuente=None):
    enlace = enlace_limpio(enlace)
    s = {"cuenta": cuenta if cuenta.startswith("@") else "@" + cuenta, "premio": premio.strip(), "lugar": lugar.strip(),
         "hasta": hora(hasta), "enlace": enlace, "comprobado": dt.date.today().isoformat()}
    if como: s["como"] = como.strip()
    if fuente: s["fuente"] = fuente.strip()
    x["sorteos"] = [o for o in x.get("sorteos", []) if o.get("enlace") != enlace] + [s]   # el mismo enlace no se repite
    x["sorteos"].sort(key=lambda o: o["hasta"])
    return x


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras")
    a.add_argument("--anadir", action="store_true"); a.add_argument("--podar", action="store_true"); a.add_argument("--buscado", action="store_true")
    for c in ("cuenta", "premio", "lugar", "hasta", "enlace", "como", "fuente"): a.add_argument("--" + c)
    o = a.parse_args()
    x = json.load(open(o.extras, encoding="utf-8"))
    if o.anadir:
        falta = [c for c in ("cuenta", "premio", "lugar", "hasta", "enlace") if not getattr(o, c)]
        if falta: sys.exit("Falta: " + ", ".join(falta))
        anadir(x, o.cuenta, o.premio, o.lugar, o.hasta, o.enlace, o.como, o.fuente)
    podar(x)
    x.setdefault("sorteos", [])
    x["sorteosZona"] = ZONA
    if o.buscado or o.anadir: x["sorteosBuscado"] = dt.date.today().isoformat()
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")   # la tele se queda con el más nuevo
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(x['sorteos'])} sorteos activos en {o.extras}")


if __name__ == "__main__":
    main()
