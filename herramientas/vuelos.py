"""Vuelos baratos para la tele (pantalla Hoy), guardados en extras.json a partir de la búsqueda de Kiwi.com.

Cómo se busca está en CLAUDE.md. Cada búsqueda (una por aeropuerto) se guarda en un fichero, de una de dos formas:
  - la respuesta de Kiwi tal cual (JSON con "itineraries"), o
  - una línea por vuelo:  precio|enlace|destino IATA|ciudad destino|ida AAAA-MM-DD|origen vuelta IATA|vuelta AAAA-MM-DD|compañía ida|compañía vuelta

  python3 vuelos.py extras.json LEI=lei.txt GRX=grx.json AGP=agp.txt RMU=rmu.txt --buscado 2026-10-25 \
      --busqueda "ida y vuelta en noviembre, 2 a 5 noches, vuelos directos, salida al menos 3 días después de la búsqueda (Kiwi.com)"
  python3 vuelos.py extras.json --sesion --busqueda "…"   # sin ficheros: las respuestas de Kiwi de la sesión de hoy

Con --sesion no hace falta copiar nada: las respuestas del conector de Kiwi quedan en el registro de la sesión de Claude Code
(~/.claude/projects/**/*.jsonl, o en …/tool-results/ si son grandes) y se toma la última de cada aeropuerto de las últimas 12 horas
(las búsquedas del puente, con la vuelta en días fijos, son de puente.py y aquí no cuentan).

Guarda hasta 6 por aeropuerto (del más barato al más caro) con su enlace de Kiwi (la tele dibuja el QR del más barato).
Si el más barato desde un aeropuerto cuesta al menos un 10 % menos que lo más barato de los 14 días anteriores, imprime además una
línea «Aviso: ✈️ Vuelo barato desde …» (la tarea diaria la manda al móvil); los mínimos de cada día se recuerdan en estado_diario.json.
Los campos antiguos («vuelos», «vuelosOrigen» y «vuelosFecha»: solo Almería, lo mismo que «aeropuertos» con otro formato) ya no se
escriben y se quitan si siguen: la app los lee solo de un extras.json sin «aeropuertos», que ya no hay.
"""
import argparse, datetime as dt, glob, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # comun.py, al lado (con -I no se mira la carpeta del script)
import comun

ORIGEN = {"LEI": "Almería", "GRX": "Granada", "AGP": "Málaga", "RMU": "Murcia"}
ORDEN = ["LEI", "GRX", "AGP", "RMU"]
# ciudades con varios aeropuertos: se dice cuál (en la tarjeta no cabe, va en «nota»)
AEROPUERTO = {"LGW": "Gatwick", "STN": "Stansted", "LTN": "Luton", "LHR": "Heathrow", "SEN": "Southend", "LCY": "London City",
              "TFN": "Tenerife Norte", "TFS": "Tenerife Sur", "MXP": "Malpensa", "BGY": "Bérgamo", "LIN": "Linate",
              "CDG": "Charles de Gaulle", "ORY": "Orly", "BVA": "Beauvais", "FCO": "Fiumicino", "CIA": "Ciampino",
              "BRU": "Zaventem", "CRL": "Charleroi", "TSF": "Treviso", "EIN": "Eindhoven",
              "NYO": "Skavsta", "ARN": "Arlanda", "TRF": "Torp", "OSL": "Gardermoen", "SXF": "Schönefeld", "BER": "Brandeburgo"}
CIUDAD = {"Las Palmas de Gran Canaria": "Gran Canaria"}
ANTIGUOS = ("vuelos", "vuelosOrigen", "vuelosFecha")      # lo de Almería repetido para la app de antes de «aeropuertos»: fuera


def compania(n):
    n = n.strip()
    for quita in (" Airlines", " Air Lines", " Malta", " UK", " Hungary", " Abu Dhabi"):
        n = n.replace(quita, "")
    return {"Binter Canarias": "Binter", "Wizz Air": "Wizz Air"}.get(n, n)


def de_kiwi(itinerario):
    ida, vuelta = itinerario["outbound"], itinerario.get("inbound") or {}
    s_ida, s_vta = ida["segments"], vuelta.get("segments") or [{}]
    return {"precio": itinerario["price"], "enlace": itinerario.get("bookingUrl"), "llega": ida["to"], "ciudad": s_ida[-1]["toCity"],
            "ida": ida["departureTime"][:10], "sale_vuelta": vuelta.get("from", ida["to"]), "vuelta": (vuelta.get("departureTime") or "")[:10],
            "c_ida": s_ida[0].get("carrierName", ""), "c_vta": s_vta[0].get("carrierName", ""), "escalas": ida.get("stops", 0) + vuelta.get("stops", 0)}


def de_linea(l):
    p = [x.strip() for x in l.split("|")]
    return {"precio": float(p[0]), "enlace": p[1], "llega": p[2], "ciudad": p[3], "ida": p[4], "sale_vuelta": p[5], "vuelta": p[6],
            "c_ida": p[7], "c_vta": p[8] if len(p) > 8 else p[7], "escalas": 0}


def leer(fichero):
    texto = open(fichero, encoding="utf-8").read().strip()
    if texto.startswith("{"):
        return [de_kiwi(i) for i in json.loads(texto)["itineraries"]]
    return [de_linea(l) for l in texto.splitlines() if l.strip() and not l.startswith("#")]


def cadenas(o):
    """Las cadenas de un JSON, también las que son a su vez JSON (el resultado del conector va dentro del registro)."""
    if isinstance(o, str):
        if o[:1] in "{[" and '"itineraries"' in o:
            try: yield json.loads(o); return
            except ValueError: pass
        yield o
    elif isinstance(o, dict):
        if "itineraries" in o and "query" in o: yield o; return
        for v in o.values(): yield from cadenas(v)
    elif isinstance(o, list):
        for v in o: yield from cadenas(v)


RAIZ_SESION = os.path.join(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")), "projects")


def respuestas(raiz=RAIZ_SESION, horas=12):
    """Las respuestas de Kiwi del registro de la sesión (las de las últimas «horas»), de la más vieja a la más nueva."""
    limite = time.time() - horas * 3600
    fich = [f for f in glob.glob(os.path.join(raiz, "**", "*.jsonl"), recursive=True) + glob.glob(os.path.join(raiz, "**", "tool-results", "*"), recursive=True)
            if os.path.getmtime(f) >= limite]
    fich.sort(key=os.path.getmtime)
    for f in fich:
        try:
            with open(f, encoding="utf-8", errors="replace") as fich_: crudo = fich_.read()
        except OSError: continue
        if "itineraries" not in crudo: continue
        for l in (crudo.splitlines() if f.endswith(".jsonl") else [crudo]):
            if "itineraries" not in l: continue
            try: o = json.loads(l)
            except ValueError: continue
            for d in cadenas(o):
                if isinstance(d, dict) and d.get("itineraries"): yield d


def de_la_sesion(raiz=RAIZ_SESION, horas=12):
    """{aeropuerto: vuelos} con la última respuesta de Kiwi de cada aeropuerto de origen en el registro de la sesión (la última manda).
    Las búsquedas con la vuelta en días fijos («returning», las del puente: puente.py) no cuentan."""
    res = {}
    for d in respuestas(raiz, horas):
        if "returning" in str(d.get("query") or ""): continue
        origen = d["itineraries"][0]["outbound"]["from"]
        res[origen] = [de_kiwi(i) for i in d["itineraries"] if i["outbound"]["from"] == origen]
    return res


def aeropuertos(busquedas, n=6):
    """[{origen, codigo, vuelos}] de {código: vuelos leídos}: los n más baratos de cada aeropuerto, en el orden de siempre."""
    out = []
    for cod in sorted(busquedas, key=lambda c: ORDEN.index(c) if c in ORDEN else 99):
        lista = sorted((vuelo(r) for r in busquedas[cod]), key=lambda v: v["precio"])[:n]
        if lista: out.append({"origen": ORIGEN.get(cod, cod), "codigo": cod, "vuelos": lista})
    return out


def vuelo(r):
    v = {"destino": CIUDAD.get(r["ciudad"], r["ciudad"]), "ida": r["ida"], "vuelta": r["vuelta"],
         "precio": int(r["precio"]) if float(r["precio"]).is_integer() else r["precio"],
         "compania": " / ".join(dict.fromkeys(c for c in (compania(r["c_ida"]), compania(r["c_vta"])) if c)),
         "escalas": "directo" if not r["escalas"] else f"{r['escalas']} escalas"}
    a, b = AEROPUERTO.get(r["llega"]), AEROPUERTO.get(r["sale_vuelta"])
    if a and b and a != b:
        v["nota"] = f"ida a {a}, vuelta desde {b}"
    elif a:
        v["nota"] = a
    if r.get("enlace"):
        v["enlace"] = r["enlace"]
    return v


def actualizar(x, busquedas, buscado, busqueda):
    x["aeropuertos"] = aeropuertos(busquedas)
    x["vuelosBuscado"] = buscado
    x["vuelosBusqueda"] = busqueda
    x["antelacionMinimaDias"] = 3
    x["actualizado"] = comun.ahora().isoformat(timespec="minutes")   # la tele se queda con el más nuevo
    for antiguo in ANTIGUOS: x.pop(antiguo, None)
    return x


BARATO, DIAS_BARATO, MIN_DIAS = 0.9, 14, 7     # vuelo barato: un 10 % menos que lo más barato de los 14 días de antes (con 7 apuntados al menos)


def baratos(ruta, x, dia):
    """Avisos al móvil de vuelo barato (15 nov 2026, lo pidió Isa): el más barato de hoy desde un aeropuerto, si cuesta al menos un 10 % menos
    que el más barato de cada uno de los DIAS_BARATO días anteriores. El más barato de cada día se recuerda en estado_diario.json
    («vuelosMin», 30 días por aeropuerto): hasta tener MIN_DIAS días apuntados no se avisa de nada. Una línea por aeropuerto."""
    hist = comun.recuerdo(ruta, {}, "vuelosMin") or {}
    corto = lambda f: f"{int(f[8:10])} {comun.MESES[int(f[5:7]) - 1][:3]}"
    avisos = []
    for a in x.get("aeropuertos") or []:
        if not a.get("vuelos"): continue
        v = min(a["vuelos"], key=lambda v: v["precio"])
        antes = [e for e in hist.get(a["codigo"], []) if e[0] != dia.isoformat()]
        previos = [p for d, p in antes if (dia - dt.timedelta(days=DIAS_BARATO)).isoformat() <= d < dia.isoformat()]
        if len(previos) >= MIN_DIAS and v["precio"] <= BARATO * min(previos):
            avisos.append(f"✈️ Vuelo barato desde {a['origen']}: {v['destino']}, del {corto(v['ida'])} al {corto(v['vuelta'])}, {v['precio']} € "
                          f"(lo más barato en {DIAS_BARATO} días era {min(previos)} €){': ' + v['enlace'] if v.get('enlace') else ''}")
        hist[a["codigo"]] = (antes + [[dia.isoformat(), v["precio"]]])[-30:]
    comun.recordar(ruta, {}, "vuelosMin", hist)
    return avisos


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras"); a.add_argument("ficheros", nargs="*", help="CÓDIGO=fichero, p. ej. LEI=lei.txt")
    a.add_argument("--sesion", action="store_true", help="las respuestas de Kiwi del registro de la sesión (las de las últimas 12 h)")
    a.add_argument("--buscado", default=comun.hoy().isoformat()); a.add_argument("--busqueda", required=True)
    o = a.parse_args()
    x = comun.leer(o.extras)
    busquedas = de_la_sesion() if o.sesion else {}
    busquedas.update({par.split("=", 1)[0].upper(): leer(par.split("=", 1)[1]) for par in o.ficheros})
    if not busquedas: sys.exit("No hay búsquedas de Kiwi (ni ficheros ni en la sesión): no se toca nada")
    faltan = [c for c in ORDEN if c not in busquedas]
    if faltan: print("Sin búsqueda de: " + ", ".join(faltan), file=sys.stderr)
    actualizar(x, busquedas, o.buscado, o.busqueda)
    comun.guardar(o.extras, x)
    print(", ".join(f"{a['origen']} {len(a['vuelos'])}" for a in x["aeropuertos"]))
    for aviso in baratos(o.extras, x, dt.date.fromisoformat(o.buscado)): print("Aviso: " + aviso)      # la tarea los manda al móvil


if __name__ == "__main__":
    main()
