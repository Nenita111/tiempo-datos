"""Precio de la luz de mañana (PVPC) en una imagen para el móvil: una fila por hora, con su barra y su precio.

  python3 luz_movil.py salida.png [--dia AAAA-MM-DD] [--esperar MIN] [--apk app/Tiempo.apk]

Fuente: Red Eléctrica. Primero ESIOS (indicador 1001, península); su clave la pone el proxy del entorno en la nube
(«network secret», cabecera x-api-key) y aquí no se ve ni se guarda. Si ESIOS no responde, la API pública REData,
una sola vez. Precios en €/kWh del término de energía del PVPC 2.0TD (con peajes y cargos, sin impuestos).
Sale con código 4 si los precios de ese día aún no están publicados (y no dibuja nada).
"""
import argparse, asyncio, datetime as dt, json, os, subprocess, sys, tempfile, time, zipfile, zoneinfo

TZ = zoneinfo.ZoneInfo("Europe/Madrid")
UA = "TiempoYRadar/1.0 (precio de la luz para el movil; https://github.com/Nenita111/tiempo-datos)"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
SIN_PRECIOS = 4


def curl(url, *cabeceras):
    cmd = ["curl", "-sS", "-f", "--max-time", "40", "-A", UA]
    for c in cabeceras: cmd += ["-H", c]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode: raise IOError(r.stderr.decode()[:160].strip())
    return json.loads(r.stdout)


# ---------------------------------------------------------------- lectura de precios
def de_esios(j):
    """ESIOS (indicador 1001) → {fecha: [["HH:MM", €/kWh], …]} de la península, y cuándo se publicó."""
    por_dia = {}
    for x in sorted(j["indicator"]["values"], key=lambda x: x["datetime"]):
        if x.get("geo_id") not in (8741, None): continue           # 8741 = península
        por_dia.setdefault(x["datetime"][:10], []).append([x["datetime"][11:16], round(x["value"] / 1000, 5)])
    return por_dia, j["indicator"].get("values_updated_at")


def de_redata(j):
    """REData (precios de mercados en tiempo real, serie PVPC) → {fecha: [["HH:MM", €/kWh], …]} y cuándo se publicó."""
    s = next(i for i in j["included"] if i["type"] == "PVPC")["attributes"]
    por_dia = {}
    for x in s["values"]:
        por_dia.setdefault(x["datetime"][:10], []).append([x["datetime"][11:16], round(x["value"] / 1000, 5)])
    return por_dia, s.get("last-update")


def leer(desde, hasta):
    """Precios de [desde, hasta] y de dónde salen. ESIOS y, si no responde, REData (una sola petición)."""
    fallos = []
    try:
        j = curl(f"https://api.esios.ree.es/indicators/1001?start_date={desde}T00:00&end_date={hasta}T23:59&geo_ids[]=8741",
                 "Accept: application/json; application/vnd.esios-api-v1+json")
        return (*de_esios(j), "ESIOS", fallos)
    except Exception as e:
        fallos.append(f"ESIOS: {e}")
    try:
        j = curl(f"https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real?start_date={desde}T00:00&end_date={hasta}T23:59&time_trunc=hour")
        return (*de_redata(j), "REData", fallos)
    except Exception as e:
        fallos.append(f"REData: {e}")
    return {}, None, None, fallos


# ---------------------------------------------------------------- resumen
def coma(x, d=3): return f"{x:.{d}f}".replace(".", ",")


def resumen(precios):
    ps = [p for _, p in precios]
    imin = min(range(len(ps)), key=lambda i: ps[i]); imax = max(range(len(ps)), key=lambda i: ps[i])
    media = sum(ps) / len(ps)
    # las tres horas seguidas más baratas (para lavadora, lavavajillas, horno…)
    tres = min(range(len(ps) - 2), key=lambda i: sum(ps[i:i + 3])) if len(ps) >= 3 else imin
    return dict(imin=imin, imax=imax, media=media, tres=tres, tres_media=sum(ps[tres:tres + 3]) / 3 if len(ps) >= 3 else ps[imin])


def color(p, mn, mx):
    """Los mismos tres colores que la tarjeta de la luz de la tele (barata, media, cara) según su sitio en el día."""
    f = (p - mn) / max(1e-9, mx - mn)
    return "#50ccaa" if f < .33 else "#f5c542" if f < .66 else "#ff6b5b"


def etiquetas(precios):
    """«00 h», «01 h»…; en el día de 25 horas la hora repetida sale como «02 h (2.ª)»."""
    vistas, out = set(), []
    for t, _ in precios:
        h = t[:2]
        out.append(f"{h} h (2.ª)" if h in vistas else f"{h} h"); vistas.add(h)
    return out


# ---------------------------------------------------------------- dibujo
def html(precios, dia, publicado, fuente, hoy_media=None, fuente_letra=None):
    R = resumen(precios)
    ps = [p for _, p in precios]; mn, mx = min(ps), max(ps)
    fecha = f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]}"
    pub = ""
    if publicado:
        try: pub = f" a las {dt.datetime.fromisoformat(publicado.replace('Z', '+00:00')).astimezone(TZ):%H:%M}"
        except ValueError: pub = ""
    comp = ""
    if hoy_media:
        d = (R["media"] - hoy_media) / hoy_media * 100
        comp = f"<small>hoy {coma(hoy_media)} · {'+' if d > 0 else '−'}{coma(abs(d), 0)} %</small>"
    filas = []
    for i, ((t, p), et) in enumerate(zip(precios, etiquetas(precios))):
        marca = " min" if i == R["imin"] else " max" if i == R["imax"] else ""
        franja = " tres" if R["tres"] <= i < R["tres"] + 3 else ""
        filas.append(f'<div class="fila{marca}{franja}"><span class="h">{et}</span><span class="pista"><i style="width:{max(3, p / mx * 100):.1f}%;'
                     f'background:{color(p, mn, mx)}"></i></span><b>{coma(p)}</b></div>')
    letra = f'@font-face{{font-family:A;src:url("file://{fuente_letra}") format("woff2");font-weight:200 800}}' if fuente_letra else ""
    th = R["tres"]
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{letra}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:540px;height:1200px}}
body{{font-family:A,"Atkinson Hyperlegible",system-ui,sans-serif;color:#eef2f7;padding:30px 22px 20px;display:flex;flex-direction:column;gap:14px;
  background:radial-gradient(700px 400px at 12% -10%,#17243b 0%,rgba(23,36,59,0) 62%),radial-gradient(600px 380px at 106% 112%,#1e1932 0%,rgba(30,25,50,0) 56%),#0b111b;
  font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}}
.k{{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:#8d9ab0;font-weight:800}}
h1{{font-size:34px;line-height:1.08;font-weight:800;margin-top:6px;letter-spacing:-.01em}}
.sub{{font-size:14px;color:#a9b4c6;margin-top:6px;font-weight:600;line-height:1.35}}
.cajas{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}}
.caja{{background:rgba(255,255,255,.06);border-radius:14px;padding:9px 10px}}
.caja span{{display:block;font-size:12px;color:#8d9ab0;font-weight:800;letter-spacing:.06em;text-transform:uppercase}}
.caja b{{display:block;font-size:22px;font-weight:800;margin-top:3px}}.caja small{{display:block;font-size:13px;color:#a9b4c6;font-weight:600;margin-top:1px}}
.caja.b b{{color:#50ccaa}}.caja.c b{{color:#ff6b5b}}
.tres-n{{font-size:14.5px;color:#cfd7e3;font-weight:600;background:rgba(80,204,170,.10);border-left:4px solid #50ccaa;border-radius:8px;padding:7px 10px}}
.tres-n b{{color:#50ccaa}}
.graf{{flex:1;display:flex;flex-direction:column;justify-content:space-between;background:rgba(255,255,255,.035);border-radius:16px;padding:8px 10px}}
.fila{{display:grid;grid-template-columns:62px 1fr 64px;align-items:center;gap:8px;flex:1;border-radius:7px;padding:0 4px}}
.h{{font-size:15px;color:#a9b4c6;font-weight:700;white-space:nowrap}}
.pista{{height:62%;display:flex;align-items:center}}.pista i{{display:block;height:100%;border-radius:0 6px 6px 0}}
.fila b{{font-size:16px;font-weight:800;text-align:right}}
.fila.tres{{background:rgba(80,204,170,.10)}}
.fila.min b{{color:#50ccaa}}.fila.max b{{color:#ff6b5b}}.fila.min .h,.fila.max .h{{color:#eef2f7}}
.pie{{font-size:12.5px;color:#7f8ba0;font-weight:600;line-height:1.35}}
</style></head><body>
<div><div class="k">Luz · precio por horas (PVPC)</div><h1>Mañana, {fecha}</h1>
<p class="sub">€/kWh de cada hora · publicado por Red Eléctrica{pub}</p></div>
<div class="cajas"><div class="caja b"><span>Más barata</span><b>{etiquetas(precios)[R['imin']]}</b><small>{coma(mn)} €</small></div>
<div class="caja c"><span>Más cara</span><b>{etiquetas(precios)[R['imax']]}</b><small>{coma(mx)} €</small></div>
<div class="caja"><span>Media</span><b>{coma(R['media'])}</b>{comp}</div></div>
<p class="tres-n">Las 3 horas seguidas más baratas: <b>de {precios[th][0][:2]}:00 a {(int(precios[min(th + 2, len(precios) - 1)][0][:2]) + 1) % 24:02d}:00</b> · {coma(R['tres_media'])} € de media (lavadora, lavavajillas, horno)</p>
<div class="graf">{"".join(filas)}</div>
<p class="pie">Término de energía del PVPC 2.0TD, con peajes y cargos y sin impuestos. Fuente: Red Eléctrica ({fuente}). Imagen hecha a las {dt.datetime.now(TZ):%H:%M}.</p>
</body></html>"""


def letra_de_apk(apk):
    if not apk or not os.path.exists(apk): return None
    d = tempfile.mkdtemp(prefix="letra_")
    with zipfile.ZipFile(apk) as z:
        n = "assets/fuentes/atkinson.woff2"
        if n not in z.namelist(): return None
        z.extract(n, d)
    return os.path.join(d, n)


async def foto(pagina, salida):
    from playwright.async_api import async_playwright
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(pagina)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 540, "height": 1200}, device_scale_factor=2)
        await pg.goto("file://" + f.name)
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=salida)
        await b.close()
    os.unlink(f.name)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("salida")
    a.add_argument("--dia", help="por defecto, mañana")
    a.add_argument("--esperar", type=int, default=0, help="minutos que se espera a que se publiquen (solo con ESIOS; mira cada 4 min)")
    a.add_argument("--apk", help="APK de la app, para usar su misma letra")
    o = a.parse_args()
    hoy = dt.datetime.now(TZ).date()
    dia = dt.date.fromisoformat(o.dia) if o.dia else hoy + dt.timedelta(days=1)
    fin = time.time() + o.esperar * 60
    while True:
        por_dia, publicado, fuente, fallos = leer(min(hoy, dia), dia)
        precios = por_dia.get(dia.isoformat())
        if precios or fuente != "ESIOS" or time.time() + 240 > fin: break
        print("Aún no están publicados; vuelvo a mirar en 4 minutos.", file=sys.stderr, flush=True)
        time.sleep(240)
    if not precios:
        print(f"Sin precios del {dia}: " + ("; ".join(fallos) or f"{fuente} aún no los tiene"), file=sys.stderr)
        sys.exit(SIN_PRECIOS)
    hoy_p = por_dia.get(hoy.isoformat()) if dia != hoy else None
    hoy_media = sum(p for _, p in hoy_p) / len(hoy_p) if hoy_p else None
    asyncio.run(foto(html(precios, dia, publicado, fuente, hoy_media, letra_de_apk(o.apk)), o.salida))
    R = resumen(precios)
    print(json.dumps({"dia": dia.isoformat(), "fuente": fuente, "horas": len(precios), "min": [precios[R["imin"]][0], precios[R["imin"]][1]],
                      "max": [precios[R["imax"]][0], precios[R["imax"]][1]], "media": round(R["media"], 4), "fallos": fallos}, ensure_ascii=False))


if __name__ == "__main__":
    main()
