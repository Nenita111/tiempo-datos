"""La receta de hoy elegida con Jev según el tiempo que hace (tarea diaria, con diario.py), para la tarjeta de temporada de Hoy.

Las recetas son las de la tele (recetas.json, copia de RECETAS de la página, en el mismo orden). Del tiempo de hoy de AEMET (XML del
municipio) el código saca cómo es el día en palabras (frío, templado, calor; lluvia probable o seco; viento) y Jev elige, entre las
recetas del mes que no han salido en los últimos 7 días (ni la de ayer, sea de Jev o de la rotación de la tele), la que mejor pega.
Se guarda en extras.json «receta»: {"fecha", "nombre", "tiempo", "recientes"}. La tele la enseña solo ese día; si no hay (sin Jev,
sin red o sin AEMET), la de su rotación de siempre.

  python3 -I herramientas/receta.py extras.json [--ine 04003]
"""
import argparse, datetime as dt, json, os, sys, urllib.request
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

TZ = ZoneInfo("Europe/Madrid")
AQUI = os.path.dirname(os.path.abspath(__file__))
UA = "TiempoYRadar/1.0 (tareas de la tele)"


def recetas():
    return json.load(open(os.path.join(AQUI, "recetas.json"), encoding="utf-8"))


def del_mes(R, mes): return [r for r in R if mes in r["meses"]]


def rotacion(R, d):
    """La de la tele cuando no hay elegida (recetaDeHoy de index.html, igual): cada día la siguiente de su mes; el día 1, si repetiría la de ayer, la anterior."""
    n = (d - dt.date(1970, 1, 1)).days
    L = del_mes(R, d.month); r = L[n % len(L)]
    if d.day > 1: return r
    A = del_mes(R, (d - dt.timedelta(days=1)).month)
    return L[(n - 1) % len(L)] if A[(n - 1) % len(A)] is r else r


def tiempo_de(xml, hoy):
    """Cómo es el día en palabras (para Jev; los números se quedan aquí)."""
    raiz = ET.fromstring(xml)
    dia = next((d for d in raiz.iter("dia") if d.get("fecha") == hoy.isoformat()), None)
    if dia is None: raise ValueError(f"AEMET no trae el {hoy}")
    tmax = int(dia.findtext("temperatura/maxima"))
    prob = max([int(p.text) for p in dia.findall("prob_precipitacion") if (p.text or "").strip().isdigit()] or [0])
    viento = max([int(v.findtext("velocidad")) for v in dia.findall("viento") if (v.findtext("velocidad") or "").strip().isdigit()] or [0])
    racha = max([int(r.text) for r in dia.findall("racha_max") if (r.text or "").strip().isdigit()] or [0])
    temp = "cold" if tmax <= 14 else "cool" if tmax <= 19 else "mild" if tmax <= 25 else "warm" if tmax <= 30 else "hot"
    lluvia = "rain likely" if prob >= 60 else "some chance of rain" if prob >= 30 else "dry"
    return {"temperature": temp, "rain": lluvia, "wind": "windy" if viento >= 40 or racha >= 60 else "light wind",
            "sky": (dia.find("estado_cielo[@periodo='00-24']").get("descripcion") or "") if dia.find("estado_cielo[@periodo='00-24']") is not None else ""}


def elegir(R, hoy, tiempo, recientes, pedir=None):
    """El nombre que elige Jev entre las del mes que no han salido hace poco (con 2 o más para elegir)."""
    fuera = {x["nombre"] for x in recientes if (hoy - dt.date.fromisoformat(x["fecha"])).days <= 7}
    fuera.add(next((x["nombre"] for x in recientes if x["fecha"] == (hoy - dt.timedelta(days=1)).isoformat()), rotacion(R, hoy - dt.timedelta(days=1))["nombre"]))
    ops = {r["nombre"]: r["como"] for r in del_mes(R, hoy.month) if r["nombre"] not in fuera}
    if len(ops) < 2: return None
    r, _ = jev.preguntar({"tiempo_hoy": tiempo, "mes": jev.MESES[hoy.month - 1]}, jev.preguntas_receta(ops), pedir=pedir)
    return r["plato"]["choice"] if r["plato"]["choice"] in ops else None


def main():
    a = argparse.ArgumentParser(); a.add_argument("extras"); a.add_argument("--ine", default="04003"); o = a.parse_args()
    hoy = dt.datetime.now(TZ).date()
    x = json.load(open(o.extras, encoding="utf-8"))
    viejo = x.get("receta") or {}
    if viejo.get("fecha") == hoy.isoformat():
        print(json.dumps({"receta": viejo["nombre"], "ya": True}, ensure_ascii=False)); return
    R = recetas()
    try:
        xml = urllib.request.urlopen(urllib.request.Request(f"https://www.aemet.es/xml/municipios/localidad_{o.ine}.xml", headers={"User-Agent": UA}), timeout=40).read()
        tiempo = tiempo_de(xml, hoy)
        nombre = elegir(R, hoy, tiempo, viejo.get("recientes", []))
    except jev.SinJev as e:
        print(json.dumps({"receta": None, "motivo": str(e)}, ensure_ascii=False)); return
    if not nombre:
        print(json.dumps({"receta": None, "motivo": "pocas recetas para elegir"}, ensure_ascii=False)); return
    recientes = [r for r in viejo.get("recientes", []) if (hoy - dt.date.fromisoformat(r["fecha"])).days < 7] + [{"fecha": hoy.isoformat(), "nombre": nombre}]
    x["receta"] = {"fecha": hoy.isoformat(), "nombre": nombre, "tiempo": tiempo, "recientes": recientes}
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"receta": nombre, "tiempo": tiempo}, ensure_ascii=False))


if __name__ == "__main__":
    main()
