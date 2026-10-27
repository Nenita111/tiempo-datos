"""Agenda del pueblo (pantalla Hoy de la tele): actividades que anuncia el Ayuntamiento (web municipal, sus redes, notas de
prensa) o un medio local citándolo. La agenda de la web municipal no se mantiene, así que se apuntan una a una cuando se ven:
las capturas del buzón de Drive o la búsqueda web de la tarea diaria.

  python3 agenda.py extras.json --titulo "Concierto de Santa Cecilia de la Banda Municipal" --fecha 2026-11-22 [--hora 20:00] \
      [--hasta 2026-11-23] [--lugar "Centro Cultural"] --enlace https://… [--fuente "Ayuntamiento de Adra"] [--ine 04003]
  python3 agenda.py extras.json          (solo quita lo que ya pasó)

Solo se apunta lo que se ha leído en la fuente: qué, el día (y la hora si la dice) y dónde. Nada deducido: sin día, no se apunta.
Se quitan solas al pasar el último día.
"""
import argparse, datetime as dt, json, re, sys
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")


def podar(x, hoy=None):
    hoy = hoy or dt.datetime.now(TZ).date()
    x["agenda"] = sorted((a for a in x.get("agenda", []) if dt.date.fromisoformat(a.get("hasta") or a["fecha"]) >= hoy),
                         key=lambda a: (a["fecha"], a.get("hora") or ""))
    return x


def anadir(x, titulo, fecha, hora=None, hasta=None, lugar=None, enlace=None, fuente="Ayuntamiento de Adra", ine="04003"):
    titulo = re.sub(r"\s+", " ", (titulo or "")).strip()
    if not titulo: raise ValueError("falta el título")
    f = dt.date.fromisoformat(fecha)
    if hasta and dt.date.fromisoformat(hasta) < f: raise ValueError("--hasta es anterior a --fecha")
    if hora and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora): raise ValueError("hora: HH:MM")
    a = {"titulo": titulo, "fecha": f.isoformat(), "fuente": fuente, "ine": ine}
    if hora: a["hora"] = hora
    if hasta and hasta != fecha: a["hasta"] = hasta
    if lugar: a["lugar"] = re.sub(r"\s+", " ", lugar).strip()
    if enlace: a["enlace"] = re.sub(r"\?.*$", "", enlace.strip()) if "instagram.com" in enlace else enlace.strip()
    mismo = lambda o: o["fecha"] == a["fecha"] and (o["titulo"].lower() == titulo.lower() or (enlace and o.get("enlace") == a.get("enlace")))
    x["agenda"] = [o for o in x.get("agenda", []) if not mismo(o)] + [a]
    return x


def main():
    p = argparse.ArgumentParser()
    p.add_argument("extras"); p.add_argument("--titulo"); p.add_argument("--fecha"); p.add_argument("--hora"); p.add_argument("--hasta")
    p.add_argument("--lugar"); p.add_argument("--enlace"); p.add_argument("--fuente", default="Ayuntamiento de Adra"); p.add_argument("--ine", default="04003")
    o = p.parse_args()
    with open(o.extras, encoding="utf-8") as f: x = json.load(f)
    if o.titulo or o.fecha:
        if not (o.titulo and o.fecha): sys.exit("Falta --titulo o --fecha")
        anadir(x, o.titulo, o.fecha, o.hora, o.hasta, o.lugar, o.enlace, o.fuente, o.ine)
    podar(x)
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    with open(o.extras, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    print(f"{len(x['agenda'])} actividades en la agenda de {o.extras}")


if __name__ == "__main__":
    main()
