"""Colectas de sangre anunciadas en el pueblo (pantalla Hoy de la tele, en la agenda y arriba el día antes y el mismo día).

La tele ya lee sola la tabla oficial del SAS (centro de transfusión de la provincia), pero esa tabla solo trae los próximos días
(unos tres). Para saberlo antes se apuntan aquí las que anuncia una fuente oficial o un medio citándola: la guía de colectas del mes
del Centro de Transfusión, una nota del Ayuntamiento o un cartel del buzón de capturas.

  python3 sangre.py extras.json --fecha 2026-11-17 --horario 17:00-21:00 [--horario …] --lugar "Centro de Salud de Adra" \
      --enlace https://… --fuente "Centro de Transfusión de Almería (Teleprensa)" [--pueblo Adra] [--ine 04003]
  python3 sangre.py extras.json          (solo quita las que ya pasaron)

Solo se apunta lo que se ha leído: el día, el lugar y el horario, con el enlace a la fuente. Nada deducido: sin día o sin lugar, no se
apunta (sin horario, sí: la tele lo enseña sin hora). Se quitan solas al pasar el día. Guarda en extras.json «sangre».
"""
import argparse, datetime as dt, json, re, sys
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")


def podar(x, hoy=None):
    hoy = hoy or dt.datetime.now(TZ).date()
    s = x.setdefault("sangre", {})
    s["colectas"] = sorted((c for c in s.get("colectas", []) if dt.date.fromisoformat(c["fecha"]) >= hoy),
                           key=lambda c: (c["fecha"], (c.get("horas") or [[""]])[0][0]))
    return x


def horario(t):
    m = re.fullmatch(r"\s*([01]?\d|2[0-3])[:.,]([0-5]\d)\s*[-–a]\s*([01]?\d|2[0-4])[:.,]([0-5]\d)\s*", t or "")
    if not m: raise ValueError(f"horario: HH:MM-HH:MM ({t!r})")
    a, b = f"{int(m.group(1)):02d}:{m.group(2)}", f"{int(m.group(3)):02d}:{m.group(4)}"
    if a >= b: raise ValueError(f"horario: la hora de fin es anterior a la de inicio ({t!r})")
    return [a, b]


def anadir(x, fecha, lugar, enlace, fuente, horarios=(), pueblo="Adra", ine="04003"):
    f = dt.date.fromisoformat(fecha)
    lugar = re.sub(r"\s+", " ", lugar or "").strip()
    if not lugar: raise ValueError("falta el lugar")
    if not (enlace or "").startswith("http"): raise ValueError("falta el enlace a la fuente")
    if not (fuente or "").strip(): raise ValueError("falta la fuente")
    c = {"fecha": f.isoformat(), "lugar": lugar, "pueblo": pueblo, "ine": ine, "horas": [horario(h) for h in horarios],
         "enlace": re.sub(r"\?.*$", "", enlace.strip()) if "instagram.com" in enlace else enlace.strip(), "fuente": fuente.strip()}
    s = x.setdefault("sangre", {})
    s["colectas"] = [o for o in s.get("colectas", []) if not (o["fecha"] == c["fecha"] and o.get("ine") == ine)] + [c]
    return x


def main():
    p = argparse.ArgumentParser()
    p.add_argument("extras"); p.add_argument("--fecha"); p.add_argument("--horario", action="append", default=[]); p.add_argument("--lugar")
    p.add_argument("--enlace"); p.add_argument("--fuente"); p.add_argument("--pueblo", default="Adra"); p.add_argument("--ine", default="04003")
    o = p.parse_args()
    with open(o.extras, encoding="utf-8") as f: x = json.load(f)
    if o.fecha or o.lugar:
        try: anadir(x, o.fecha, o.lugar, o.enlace, o.fuente, o.horario, o.pueblo, o.ine)
        except (ValueError, TypeError) as e: sys.exit(f"No se apunta: {e}")
    podar(x)
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    with open(o.extras, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    print(f"{len(x['sangre']['colectas'])} colectas de sangre anunciadas en {o.extras}")


if __name__ == "__main__":
    main()
