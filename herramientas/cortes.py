"""Cortes anunciados (agua, luz, tráfico) que no salen en los periódicos: los que publica el Ayuntamiento en sus redes
(Instagram) y llegan a mano, con un enlace o una captura. Se guardan en extras.json y la tele los junta con los de las noticias.

  python3 cortes.py extras.json --tipo luz --titulo "Corte de luz el martes 28 de 8:00 a 14:00 en calle Natalio Rivas y alrededores" \
      --hasta 2026-10-28 --enlace https://www.instagram.com/p/XXXX/ [--fuente "Instagram del Ayuntamiento de Adra"] [--ine 04003]

Solo se apunta lo que se ha visto en la publicación: qué se corta, cuándo (último día) y dónde. Se quitan solos al pasar el día.
"""
import argparse, datetime as dt, json, re, sys
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
TIPOS = ("agua", "luz", "trafico")


def podar(x, hoy=None):
    hoy = hoy or dt.datetime.now(TZ).date()
    x["cortes"] = [c for c in x.get("cortes", []) if dt.date.fromisoformat(c["hasta"]) >= hoy]
    return x


def anadir(x, tipo, titulo, hasta, enlace=None, fuente="Instagram del Ayuntamiento de Adra", ine="04003", publicado=None):
    if tipo not in TIPOS: raise ValueError(f"tipo: {', '.join(TIPOS)}")
    dt.date.fromisoformat(hasta)
    c = {"tipo": tipo, "titulo": titulo.strip(), "fuente": fuente, "hasta": hasta, "ine": ine,
         "s": int((publicado or dt.datetime.now(TZ)).timestamp())}
    if enlace: c["enlace"] = re.sub(r"\?.*$", "", enlace.strip()) if "instagram.com" in enlace else enlace.strip()
    x["cortes"] = [o for o in x.get("cortes", []) if not (enlace and o.get("enlace") == c.get("enlace"))] + [c]
    return x


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras"); a.add_argument("--tipo", choices=TIPOS); a.add_argument("--titulo"); a.add_argument("--hasta")
    a.add_argument("--enlace"); a.add_argument("--fuente", default="Instagram del Ayuntamiento de Adra"); a.add_argument("--ine", default="04003")
    o = a.parse_args()
    x = json.load(open(o.extras, encoding="utf-8"))
    if o.tipo:
        if not (o.titulo and o.hasta): sys.exit("Falta --titulo o --hasta")
        anadir(x, o.tipo, o.titulo, o.hasta, o.enlace, o.fuente, o.ine)
    podar(x)
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(x['cortes'])} cortes en {o.extras}")


if __name__ == "__main__":
    main()
