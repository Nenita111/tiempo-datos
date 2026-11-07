"""El polen en el aire de Almería (4.31, lo pidió Isa el 7 nov 2026: «niveles de polen de Almería»). De la Red Española de Aerobiología de
la Sociedad Española de Alergología e Inmunología Clínica (SEAIC, Comité de Aerobiología; www.polenes.com, estación de Almería): los granos
por metro cúbico de aire de cada día, por tipo (recuentos medidos con captador volumétrico). La web es una aplicación Meteor sin API: los
datos llegan por su protocolo DDP sobre SockJS (peticiones POST a /sockjs/…/xhr), como los pide la propia página; su robots.txt no existe
(404: sin restricciones). La red sube los recuentos por tandas, con semanas de retraso: se dice el día del último dato. Los niveles (bajo,
moderado y alto) son los cortes que usa la propia web para colorear cada tipo (solo los trae para nueve); los demás, solo el recuento.
Nada de previsión: la web no da ninguna.

  python3 -I herramientas/polen.py extras.json

Imprime una línea JSON: {"polen": "AAAA-MM-DD" (último día), "dias": N} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, json, os, random, string, sys, time, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
WEB = "https://www.polenes.com"
ESTACION = 4          # Almería
TIPOS = {1: "Alnus (aliso)", 2: "Alternaria (hongo)", 3: "Artemisa", 4: "Betula (abedul)", 5: "Carex", 6: "Castanea (castaño)",
         7: "Cupresáceas", 8: "Fraxinus (fresno)", 9: "Gramíneas", 10: "Mercurialis", 11: "Morus (morera)", 12: "Olivo",
         13: "Palmeras", 14: "Pino", 15: "Plantago (llantén)", 16: "Plátano de sombra", 17: "Populus (chopo)",
         18: "Amarantáceas (salsola)", 19: "Quercus (encina)", 20: "Rumex (acedera)", 21: "Ulmus (olmo)", 22: "Urticáceas (parietaria)"}
# los cortes (granos/m³) con los que la web pinta verde, naranja y rojo (su código, 7 nov 2026)
CORTES = {9: (10, 50), 12: (100, 200), 7: (50, 135), 22: (10, 20), 18: (10, 20), 15: (10, 50), 16: (50, 130), 19: (100, 200), 4: (100, 200)}


def post(url, datos=b""):
    req = urllib.request.Request(url, data=datos, method="POST", headers={"Content-Type": "text/plain", "User-Agent": comun.UA_APP})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode("utf-8")


def pedir_dias(desde, hasta, est=ESTACION, enviar=post, dormir=time.sleep):
    """Las tramas de la suscripción «graphPollenData» (la de las gráficas de la web) de una estación entre dos días."""
    base = f"{WEB}/sockjs/{random.randint(100, 999)}/{''.join(random.choice(string.ascii_lowercase) for _ in range(8))}"
    if not enviar(base + "/xhr").startswith("o"): raise ValueError("polenes.com no abre la sesión")
    msgs = [json.dumps({"msg": "connect", "version": "1", "support": ["1"]}),
            json.dumps({"msg": "sub", "id": "s1", "name": "graphPollenData", "params": [desde.strftime("%Y%m%d"), hasta.strftime("%Y%m%d"), est]})]
    enviar(base + "/xhr_send", json.dumps(msgs).encode())
    tramas = []
    for _ in range(8):
        t = enviar(base + "/xhr"); tramas.append(t)
        if '\\"msg\\":\\"ready\\"' in t or '"msg":"ready"' in t: return tramas
        dormir(1)
    raise ValueError("polenes.com no ha acabado de mandar los datos")


def filas(tramas, est=ESTACION):
    """{«AAAA-MM-DD»: {tipo: granos/m³}} de las tramas SockJS («a[…]» con mensajes DDP «added» de la colección polenes2015)."""
    res = {}
    for t in tramas:
        for linea in t.splitlines():
            if not linea.startswith("a["): continue
            for x in json.loads(linea[1:]):
                m = json.loads(x)
                f = m.get("fields") or {}
                if m.get("msg") != "added" or m.get("collection") != "polenes2015" or f.get("idEstacion") != est: continue
                d = str(f.get("fecha"))
                if len(d) != 8: continue
                res[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = {int(k): v for k, v in f.items() if k.isdigit() and isinstance(v, (int, float))}
    return res


def nivel(t, v):
    c = CORTES.get(t)
    if not c: return None
    return "alto" if v >= c[1] else "moderado" if v >= c[0] else "bajo"


def resumen(f, hoy):
    """El último día con recuento (lo que hay en el aire, por tipo, de más a menos), la semana hasta ese día (lo máximo de cada tipo) y,
    del último año, lo máximo de cada mes de los tipos que llegan a moderado (o, sin cortes, a 10 granos/m³)."""
    dias = sorted(d for d in f if d <= hoy.isoformat())
    if not dias: raise ValueError("sin recuentos")
    ult = dias[-1]
    tipo = lambda t, v: dict({"id": t, "nombre": TIPOS.get(t, str(t)), "valor": round(v, 1)}, **({"nivel": nivel(t, v)} if nivel(t, v) else {}))
    hoyp = sorted(((t, v) for t, v in f[ult].items() if v > 0), key=lambda x: -x[1])
    sem = [d for d in dias if d > (dt.date.fromisoformat(ult) - dt.timedelta(days=7)).isoformat()]
    maxsem = {}
    for d in sem:
        for t, v in f[d].items(): maxsem[t] = max(maxsem.get(t, 0), v)
    # el año: 12 meses hasta el del último dato
    u = dt.date.fromisoformat(ult)
    meses = [((u.year * 12 + u.month - 1 - k) // 12, (u.year * 12 + u.month - 1 - k) % 12 + 1) for k in range(11, -1, -1)]
    anio = {}
    for d in dias:
        a, m = int(d[:4]), int(d[5:7])
        if (a, m) not in meses: continue
        i = meses.index((a, m))
        for t, v in f[d].items():
            anio.setdefault(t, [0] * 12)[i] = max(anio.get(t, [0] * 12)[i], v)
    umbral = lambda t: CORTES[t][0] if t in CORTES else 10
    cal = [{"id": t, "nombre": TIPOS.get(t, str(t)), "max": [round(v) for v in m], "niveles": [nivel(t, v) for v in m] if t in CORTES else None}
           for t, m in anio.items() if max(m) >= umbral(t)]
    cal.sort(key=lambda c: -max(c["max"]) / (CORTES[c["id"]][1] if c["id"] in CORTES else 50))   # sin cortes, como si el alto fuera 50
    return {"estacion": "Almería", "dia": ult, "tipos": [tipo(t, v) for t, v in hoyp],
            "semana": [tipo(t, v) for t, v in sorted(maxsem.items(), key=lambda x: -x[1]) if v > 0],
            "meses": [f"{a}-{m:02d}" for a, m in meses], "calendario": cal[:8], "dias": len(dias),
            "fuente": "SEAIC, Red Española de Aerobiología (polenes.com), estación de Almería", "enlace": WEB}


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    try:
        r = resumen(filas(pedir_dias(hoy - dt.timedelta(days=400), hoy)), hoy)
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    if x.get("polen") != r:
        x["polen"] = r
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"polen": r["dia"], "dias": r["dias"], "tipos": len(r["tipos"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
