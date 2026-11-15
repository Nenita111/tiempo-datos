"""El próximo puente y sus vuelos (15 nov 2026, lo pidió Isa): extras.json → «puente».

  python3 -I herramientas/puente.py extras.json            # paso diario: cuál es el próximo puente (calendario oficial de la Junta)
  python3 -I herramientas/puente.py extras.json --sesion   # apunta sus vuelos: los de Kiwi del registro de la sesión que caen en él

Puente: tres días libres seguidos o más (sábados, domingos y festivos de Andalucía y del pueblo), o dos ratos libres más cortos con un solo
día laborable entre ellos que sumen cuatro días; siempre con algún festivo. Se toma el primero que empieza dentro de ANTELACION + 1 días o más (para poder salir la víspera
con la antelación de los demás vuelos) y de HORIZONTE como mucho. Los festivos son los del calendario laboral de la Junta para el pueblo
(sas.festivos); si el del año que viene aún no está, solo cuentan los de este.

Los vuelos: ida la víspera o el primer día, vuelta el último día o el de antes, directos y con MIN_NOCHES noches al menos. La tarea diaria
los busca en Kiwi una vez a la semana (diario.py lo dice en «toca».puente con las fechas ya escritas para Kiwi) y los apunta con --sesion.

«puente»: {desde, hasta, festivos: [{fecha, nombre}], laborables (los de en medio, si los hay), fuente, buscado, aeropuertos (como los
de los demás vuelos)}. Al cambiar de puente, los vuelos del anterior se van.
"""
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # comun.py, al lado (con -I no se mira la carpeta del script)
import comun, sas, vuelos

ANTELACION, HORIZONTE, CADA, MIN_NOCHES = 3, 120, 7, 2
FUENTE = "Festivos: calendario laboral de la Junta de Andalucía. Vuelos: Kiwi.com"
MENORES = {"de", "del", "la", "las", "el", "los", "en", "y", "a"}
UN = dt.timedelta(days=1)


def nombre(s):
    """«DÍA DE LA CONSTITUCIÓN ESPAÑOLA» (así lo da el calendario) → «Día de la Constitución Española»."""
    p = s.split()
    return " ".join(w.lower() if i and w.lower() in MENORES else w.title() for i, w in enumerate(p))


def puentes(fest, desde, hasta):
    """Los puentes que empiezan en [desde, hasta]: (primer día, último día, sus festivos, el laborable de en medio si lo hay). Un bloque
    de tres días libres seguidos o más; o dos bloques más cortos con un solo laborable entre ellos (el puente) que sumen cuatro días."""
    libre = lambda d: d.weekday() >= 5 or d in fest
    largo = lambda a, b: (b - a).days + 1
    d, fin, bloques = desde - 7 * UN, hasta + 7 * UN, []
    while libre(d - UN): d -= UN
    while d <= fin:
        if libre(d):
            a = d
            while libre(d + UN): d += UN
            bloques.append((a, d))
        d += UN
    out = []
    for (a, b), (a2, b2) in zip(bloques, bloques[1:] + [(fin + 9 * UN,) * 2]):
        if largo(a, b) >= 3: fin_p, lab = b, []
        elif (a2 - b).days == 2 and largo(a2, b2) < 3 and largo(a, b2) >= 4: fin_p, lab = b2, [b + UN]
        else: continue
        f = [a + n * UN for n in range(largo(a, fin_p)) if a + n * UN in fest]
        if f and desde <= a <= hasta: out.append((a, fin_p, f, lab))
    return out


def proximo(fest, hoy):
    """El «puente» de extras.json (sin vuelos) con el próximo puente, o None si no hay ninguno a la vista."""
    p = puentes(fest, hoy + dt.timedelta(days=ANTELACION + 1), hoy + dt.timedelta(days=HORIZONTE))
    if not p: return None
    a, b, f, lab = p[0]
    out = {"desde": a.isoformat(), "hasta": b.isoformat(), "festivos": [{"fecha": d.isoformat(), "nombre": nombre(fest[d])} for d in f]}
    if lab: out["laborables"] = [d.isoformat() for d in lab]
    return dict(out, fuente=FUENTE)


def ventana(p):
    """Los días de la búsqueda: ida la víspera o el primer día; vuelta, el último día o el de antes."""
    a, b = dt.date.fromisoformat(p["desde"]), dt.date.fromisoformat(p["hasta"])
    return {"ida": [a - UN, a], "vuelta": [b - UN, b]}


def toca(x, hoy):
    """Si hoy toca buscar los vuelos del puente (una vez cada CADA días), las fechas como las pide Kiwi: {"ida": [dd/mm/aaaa, dd/mm/aaaa],
    "vuelta": […]}; si no, None."""
    p = x.get("puente")
    if not p: return None
    v = ventana(p)
    if v["ida"][0] < hoy + dt.timedelta(days=ANTELACION): return None
    if p.get("buscado") and dt.date.fromisoformat(p["buscado"]) > hoy - dt.timedelta(days=CADA): return None
    return {k: [d.strftime("%d/%m/%Y") for d in f] for k, f in v.items()}


def del_puente(p, respuestas):
    """{aeropuerto: vuelos} con los vuelos de las respuestas de Kiwi que caen en el puente: directos, ida y vuelta en sus días y con
    MIN_NOCHES noches al menos; de cada ciudad, el más barato (si hay dos respuestas con la misma, la última manda a igual precio)."""
    v = ventana(p)
    ida, vuelta = ({d.isoformat() for d in (f[0], f[1])} for f in (v["ida"], v["vuelta"]))
    res = {}
    for d in respuestas:
        for i in d["itineraries"]:
            if not i.get("inbound"): continue
            r = vuelos.de_kiwi(i)
            if r["escalas"] or r["ida"] not in ida or r["vuelta"] not in vuelta: continue
            if (dt.date.fromisoformat(r["vuelta"]) - dt.date.fromisoformat(r["ida"])).days < MIN_NOCHES: continue
            de = res.setdefault(i["outbound"]["from"], {})
            if r["ciudad"] not in de or r["precio"] <= de[r["ciudad"]]["precio"]: de[r["ciudad"]] = r
    return {cod: list(de.values()) for cod, de in res.items()}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras"); a.add_argument("--sesion", action="store_true", help="apunta los vuelos de Kiwi del registro de la sesión")
    a.add_argument("--buscado", default=None)
    o = a.parse_args()
    x, hoy = comun.leer(o.extras), comun.hoy()
    if o.sesion:
        p = x.get("puente")
        if not p: sys.exit("No hay puente apuntado: no se toca nada")
        b = del_puente(p, vuelos.respuestas())
        if not b: sys.exit("No hay vuelos de Kiwi para el puente en la sesión: no se toca nada")
        nuevo = dict(p, buscado=o.buscado or hoy.isoformat(), aeropuertos=vuelos.aeropuertos(b))
        comun.poner(o.extras, x, "puente", nuevo)
        print(f"Puente del {p['desde']} al {p['hasta']}: " + ", ".join(f"{e['origen']} {len(e['vuelos'])}" for e in nuevo["aeropuertos"]))
        return
    fest = sas.festivos(sorted({hoy.year, (hoy + dt.timedelta(days=HORIZONTE)).year}), sas.pedir)
    if not any(d.year == hoy.year for d in fest): comun.fallar(f"el calendario de la Junta no da los festivos de {hoy.year}")
    nuevo, viejo = proximo(fest, hoy), x.get("puente")
    if nuevo is None:
        if viejo is not None: x.pop("puente"); comun.publicar(o.extras, x)
        return comun.decir({"puente": None})
    if viejo and (viejo.get("desde"), viejo.get("hasta")) == (nuevo["desde"], nuevo["hasta"]):      # el mismo: con sus vuelos
        nuevo.update({k: viejo[k] for k in ("buscado", "aeropuertos") if k in viejo})
    comun.poner(o.extras, x, "puente", nuevo)
    comun.decir({"puente": f"{nuevo['desde']}/{nuevo['hasta']}", "festivos": [f["nombre"] for f in nuevo["festivos"]],
                 "vuelos": sum(len(e["vuelos"]) for e in nuevo.get("aeropuertos") or []), "buscado": nuevo.get("buscado")})


if __name__ == "__main__":
    main()
