"""Cortes de agua y luz en los titulares de Noticias de Almería, juzgados por Jev, para la tele (tarea diaria, con diario.py).

La tele busca sola los cortes en las noticias con una regla de texto. Con Jev, aquí se miran los titulares de los últimos 10 días que
nombran el pueblo (el mismo RSS que lee la tele y que el robots.txt del medio permite):
  - los que Jev da por corte de agua o de luz en el pueblo van a extras.json «cortes» (con «jev»: true, el medio citado y, si el
    titular dice el día, hasta ese día; si no, hasta el día siguiente a la noticia, como hace la tele);
  - los que la regla de la tele daría por corte y Jev dice claramente que no lo son van a «noEsCorte» (sus enlaces), y la tele no los enseña.
  - en la misma pregunta, si el titular anuncia una actividad o una colecta de sangre en el pueblo: se imprimen como candidatos (con
    el día si lo dice) para que la tarea diaria los mire y los apunte con agenda.py o sangre.py (aquí no se apunta nada).
Sin Jev (sin clave o sin red) no toca nada: la tele sigue con su regla.

  python3 -I herramientas/titulares.py extras.json [--lugar Adra --ine 04003]
"""
import argparse, datetime as dt, json, os, sys, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev, avisos_movil as A

TZ = ZoneInfo("Europe/Madrid")


def fecha_dicha(r, publicada):
    """El día del corte si el titular lo dice (día y, si está, mes), el más cercano desde la víspera de la noticia; si no, None."""
    d, m = r["dia"], r["mes"]
    if d["choice"] == "not_stated" or d.get("confidence", 0) < 0.5: return None
    dia = int(d["choice"])
    mes = jev.MESES.index(m["choice"]) + 1 if m["choice"] != "not_stated" and m.get("confidence", 0) >= 0.5 else None
    base = publicada.date() - dt.timedelta(days=1)
    for k in range(0, 13):
        y, mm = divmod(base.month - 1 + k, 12)
        cand_mes, cand_anio = mm + 1, base.year + y
        if mes and cand_mes != mes: continue
        try: f = dt.date(cand_anio, cand_mes, dia)
        except ValueError: continue
        if f >= base: return f
    return None


def juzgar(piezas, lugar, ine, pedir=None, hoy=None):
    """(cortes para extras, enlaces que no son cortes, candidatos a la agenda o a colecta). Sin Jev, SinJev."""
    cortes, no, cand = [], [], []
    hoy = hoy or dt.datetime.now(TZ).date()
    for p in piezas:
        try: r, _ = jev.preguntar({"pueblo": lugar, "noticia": {"titulo": p["titulo"], "entradilla": p["entradilla"]}}, jev.preguntas_titular(), pedir=pedir)
        except jev.SinRespuesta: continue          # con la caché de Composio, este titular no estaba: se queda sin juzgar (el resto sigue)
        regla = A.tipo_corte(p["titulo"])
        pub = p["s"] or dt.datetime.now(TZ)
        if r["anuncia"]["noul"] >= jev.SI and r["en_pueblo"]["noul"] >= 0.5 and r["restablecido"]["noul"] < 0.5 and r["tipo"]["choice"] in ("agua", "luz"):
            hasta = fecha_dicha(r, pub) or (pub.astimezone(TZ).date() + dt.timedelta(days=1))
            cortes.append({"tipo": r["tipo"]["choice"], "titulo": p["titulo"], "fuente": "Noticias de Almería", "enlace": p["enlace"],
                           "hasta": hasta.isoformat(), "ine": ine, "s": int(pub.timestamp()), "jev": True})
        elif regla and (r["anuncia"]["noul"] <= jev.NO or r["restablecido"]["noul"] >= jev.SI or r["en_pueblo"]["noul"] <= jev.NO):
            no.append(p["enlace"])
        for tipo in ("actividad", "colecta"):
            if r.get(tipo, {}).get("noul", 0) >= jev.SI:
                f = fecha_dicha(r, pub)
                if f is None or f >= hoy:
                    cand.append({"tipo": tipo, "titulo": p["titulo"], "enlace": p["enlace"], "dia": f.isoformat() if f else None,
                                 "publicada": pub.astimezone(TZ).date().isoformat()})
    return cortes, no, cand


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras"); a.add_argument("--lugar", default="Adra"); a.add_argument("--ine", default="04003")
    o = a.parse_args()
    ahora = dt.datetime.now(TZ)
    piezas = []
    for u in A.NDA: piezas += A.piezas_rss(A.pedir(u), o.lugar, ahora - dt.timedelta(days=10))
    try: cortes, no, cand = juzgar(piezas, o.lugar, o.ine)
    except jev.SinJev as e:
        print(json.dumps({"titulares": len(piezas), "juez": f"sin Jev ({e})"}, ensure_ascii=False)); return
    x = json.load(open(o.extras, encoding="utf-8"))
    hoy = ahora.date().isoformat()
    x["cortes"] = [c for c in x.get("cortes", []) if not c.get("jev")] + [c for c in cortes if c["hasta"] >= hoy]
    x["noEsCorte"] = no
    x["actualizado"] = ahora.isoformat(timespec="minutes")
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"titulares": len(piezas), "cortes": len(cortes), "noEsCorte": len(no), "juez": "Jev",
                      "agenda": [c for c in cand if c["tipo"] == "actividad"], "colectas": [c for c in cand if c["tipo"] == "colecta"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
