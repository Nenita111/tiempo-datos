"""Vuelos baratos para la tele (pantalla Hoy), guardados en extras.json a partir de la búsqueda de Kiwi.com.

Cómo se busca está en CLAUDE.md. Cada búsqueda (una por aeropuerto) se guarda en un fichero, de una de dos formas:
  - la respuesta de Kiwi tal cual (JSON con "itineraries"), o
  - una línea por vuelo:  precio|enlace|destino IATA|ciudad destino|ida AAAA-MM-DD|origen vuelta IATA|vuelta AAAA-MM-DD|compañía ida|compañía vuelta

  python3 vuelos.py extras.json LEI=lei.txt GRX=grx.json AGP=agp.txt RMU=rmu.txt --buscado 2026-10-25 \
      --busqueda "ida y vuelta en noviembre, 2 a 5 noches, vuelos directos, salida al menos 3 días después de la búsqueda (Kiwi.com)"

Guarda hasta 6 por aeropuerto (del más barato al más caro) con su enlace de Kiwi (la tele dibuja el QR del más barato)
y rellena también los campos antiguos («vuelos», solo Almería) para la versión vieja de la app.
"""
import argparse, datetime as dt, json, sys

ORIGEN = {"LEI": "Almería", "GRX": "Granada", "AGP": "Málaga", "RMU": "Murcia"}
ORDEN = ["LEI", "GRX", "AGP", "RMU"]
# ciudades con varios aeropuertos: se dice cuál (en la tarjeta no cabe, va en «nota»)
AEROPUERTO = {"LGW": "Gatwick", "STN": "Stansted", "LTN": "Luton", "LHR": "Heathrow", "SEN": "Southend", "LCY": "London City",
              "TFN": "Tenerife Norte", "TFS": "Tenerife Sur", "MXP": "Malpensa", "BGY": "Bérgamo", "LIN": "Linate",
              "CDG": "Charles de Gaulle", "ORY": "Orly", "BVA": "Beauvais", "FCO": "Fiumicino", "CIA": "Ciampino",
              "BRU": "Zaventem", "CRL": "Charleroi", "TSF": "Treviso", "EIN": "Eindhoven",
              "NYO": "Skavsta", "ARN": "Arlanda", "TRF": "Torp", "OSL": "Gardermoen", "SXF": "Schönefeld", "BER": "Brandeburgo"}
CIUDAD = {"Las Palmas de Gran Canaria": "Gran Canaria"}


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
    aeropuertos = []
    for cod in sorted(busquedas, key=lambda c: ORDEN.index(c) if c in ORDEN else 99):
        lista = sorted((vuelo(r) for r in busquedas[cod]), key=lambda v: v["precio"])[:6]
        if lista:
            aeropuertos.append({"origen": ORIGEN.get(cod, cod), "codigo": cod, "vuelos": lista})
    x["aeropuertos"] = aeropuertos
    x["vuelosBuscado"] = buscado
    x["vuelosBusqueda"] = busqueda
    x["antelacionMinimaDias"] = 3
    x["actualizado"] = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="minutes")   # la tele se queda con el más nuevo
    # campos antiguos (solo Almería) para la versión vieja de la app
    alm = next((a for a in aeropuertos if a["codigo"] == "LEI"), None)
    if alm:
        f = lambda d: f"{d[8:10]}/{d[5:7]}"
        x["vuelosOrigen"] = "Almería"
        x["vuelos"] = [{"destino": v["destino"], "fecha": f(v["ida"]), "vuelta": f(v["vuelta"]), "precio": f"{v['precio']} €",
                        "compania": v["compania"], "escalas": v["escalas"]} for v in alm["vuelos"]]
        d = dt.date.fromisoformat(buscado)
        x["vuelosFecha"] = f"Buscado el {d.day:02d}/{d.month:02d} · ida y vuelta"
    return x


def main():
    a = argparse.ArgumentParser()
    a.add_argument("extras"); a.add_argument("ficheros", nargs="+", help="CÓDIGO=fichero, p. ej. LEI=lei.txt")
    a.add_argument("--buscado", default=dt.date.today().isoformat()); a.add_argument("--busqueda", required=True)
    o = a.parse_args()
    x = json.load(open(o.extras, encoding="utf-8"))
    busquedas = {par.split("=", 1)[0].upper(): leer(par.split("=", 1)[1]) for par in o.ficheros}
    actualizar(x, busquedas, o.buscado, o.busqueda)
    json.dump(x, open(o.extras, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(", ".join(f"{a['origen']} {len(a['vuelos'])}" for a in x["aeropuertos"]))


if __name__ == "__main__":
    main()
