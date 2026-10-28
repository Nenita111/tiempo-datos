"""Sequía y escasez de agua en la cuenca (pantalla Semana de la tele, junto a los embalses): del «Informe de escasez y sequía»
mensual oficial de la Junta de Andalucía (SAIH Hidrosur, Dirección General de Infraestructuras del Agua) para la Demarcación
Hidrográfica de las Cuencas Mediterráneas Andaluzas: el agua embalsada de la demarcación, el índice y el escenario de escasez
de cada Unidad Territorial de Escasez (UTE) y el índice y el estado de sequía de cada Unidad Territorial de Sequía (UTS). Tal cual
los da el informe; nada calculado.

  python3 sequia.py extras.json [--unidades "UTS 12,UTE 14,UTE 15"]

Las unidades destacadas (las que salen en la tele) son, por defecto, las de Adra: UTS 12 (cuenca del río Adra y acuífero del
Campo de Dalías), UTE 14 (Campo de Dalías) y UTE 15 (cabecera del río Grande de Adra).
Guarda en extras.json «sequia». El PDF pesa unos 14 MB: solo se baja si su fecha de modificación ha cambiado. Si falla, sale con
código 2 y deja lo que había. Necesita pdftotext (poppler).
"""
import argparse, datetime as dt, email.utils, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
PDF = "https://www.redhidrosurmedioambiente.es/saih/assets/pdf/InformeSequia.pdf"
PAGINA = "https://www.redhidrosurmedioambiente.es/saih/"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
UA = {"User-Agent": "TiempoYRadar/1.0"}
ESCENARIOS = ["Normalidad", "Prealerta", "Alerta", "Emergencia"]
ESTADOS = ["Ausencia", "Sequía prolongada"]


def pedir(u, metodo="GET"):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA, method=metodo), timeout=120)
        except (ConnectionError, urllib.error.URLError) as e:
            if i == 2 or getattr(e, "code", None) in (403, 404): raise
            time.sleep(5 * (i + 1))


def texto_pdf(datos):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        with open(p, "wb") as f: f.write(datos)
        return subprocess.run(["pdftotext", "-layout", "-l", "10", p, "-"], capture_output=True, text=True, check=True).stdout


def num(s):
    return float(s.replace(".", "").replace(",", "."))


def mes(t):
    """«SEPTIEMBRE 2026» de la portada → «2026-09»."""
    m = re.search(r"\b(" + "|".join(MESES) + r")\s+(\d{4})\b", t, re.I)
    if not m: raise ValueError("informe sin mes")
    return f"{m.group(2)}-{MESES.index(m.group(1).lower()) + 1:02d}"


def embalses(t):
    """El agua embalsada de la demarcación de las Cuencas Mediterráneas Andaluzas este mes y el anterior."""
    f = re.search(r"Mes Actual:\s+Mes Anterior:\s*\n.*?(\d\d/\d\d/\d{4})\s+(\d\d/\d\d/\d{4})", t, re.S)
    m = re.search(r"D\.H\. Cuencas Mediterráneas\s*\n\s*([\d.]+)\s+([\d.]+)\s+([\d,]+)%\s+([\d.]+)\s+([\d,]+)%", t)
    if not m: raise ValueError("informe sin el agua embalsada de las Cuencas Mediterráneas")
    o = {"capacidad": num(m.group(1)), "volumen": num(m.group(2)), "pct": num(m.group(3)), "volumenAnterior": num(m.group(4)), "pctAnterior": num(m.group(5))}
    if f:
        iso = lambda s: dt.datetime.strptime(s, "%d/%m/%Y").date().isoformat()
        o["fecha"], o["fechaAnterior"] = iso(f.group(1)), iso(f.group(2))
    return o


def unidades(t, titulo, siguiente, prefijo, estados):
    """Las filas de la tabla de unidades (UTE o UTS) de las Cuencas Mediterráneas: código, nombre, índice y escenario o estado.
    Los nombres largos van en dos líneas, encima y debajo de la del código (que entonces no lleva nombre)."""
    i = t.find(titulo)
    if i < 0: raise ValueError(f"informe sin la tabla «{titulo}»")
    j = t.find(siguiente, i)
    ls = [l.rstrip() for l in t[i:j if j > 0 else len(t)].splitlines()]
    nota = re.compile(r"^\s*(\(|CÓDIGO|ÍNDICE|ESCASEZ|SEQUÍA|Datos|Unidades|\d+\s*$)")
    res = []
    for k, l in enumerate(ls):
        m = re.match(rf"^\s*({prefijo})\s+(\d\d)\b(.*)$", l)
        if not m: continue
        campos = [c.strip() for c in re.split(r"\s{2,}", m.group(3).strip()) if c.strip()]
        nombre = [c for c in campos if not re.fullmatch(r"\d,\d\d", c) and not any(c.startswith(e) for e in estados)]
        indice = next((c for c in campos if re.fullmatch(r"\d,\d\d", c)), None)
        estado = next((c for c in campos if any(c.startswith(e) for e in estados)), None)
        if not nombre:   # el nombre, en las líneas de encima y de debajo (la de debajo puede traer el índice)
            antes = ls[k - 1].strip() if k > 0 and not nota.match(ls[k - 1]) and not re.match(rf"^\s*{prefijo}\s", ls[k - 1]) else ""
            despues = ls[k + 1].strip() if k + 1 < len(ls) and not nota.match(ls[k + 1]) and not re.match(rf"^\s*{prefijo}\s", ls[k + 1]) else ""
            d = [c for c in re.split(r"\s{2,}", despues) if c]
            if d and re.fullmatch(r"\d,\d\d", d[-1]):
                indice = indice or d[-1]; d = d[:-1]
            nombre = [x for x in [antes, " ".join(d)] if x]
        n = re.sub(r"\s*\(\*+\)\s*$", "", " ".join(nombre)).strip()
        res.append({"codigo": f"{m.group(1)} {m.group(2)}", "nombre": n, "indice": num(indice) if indice else None,
                    "estado": re.sub(r"\s*\(.*\)$", "", estado).strip() if estado else None})
    if not res: raise ValueError(f"la tabla «{titulo}» viene vacía")
    return res


def informe(t):
    o = {"mes": mes(t), "demarcacion": "Cuencas Mediterráneas Andaluzas", "embalses": embalses(t)}
    o["escasez"] = unidades(t, "Unidades Territoriales de Escasez en la D.H. Cuencas Mediterráneas", "Unidades Territoriales de Escasez en la D.H. Cuencas de Guadalete",
                            "UTE", ESCENARIOS)
    o["sequia"] = unidades(t, "Unidades Territoriales de Sequía en la D.H. Cuencas Mediterráneas", "Unidades Territoriales de Sequía en la D.H. Cuencas de Guadalete",
                           "UTS", ESTADOS)
    return o


def main():
    a = argparse.ArgumentParser(); a.add_argument("extras"); a.add_argument("--unidades", default="UTS 12,UTE 14,UTE 15")
    p = a.parse_args()
    with open(p.extras, encoding="utf-8") as f: x = json.load(f)
    viejo = x.get("sequia") or {}
    destacadas = [u.strip() for u in p.unidades.split(",") if u.strip()]
    try:
        r = pedir(PDF, "HEAD")
        mod = r.headers.get("Last-Modified", "")
        if viejo.get("modificado") == mod and viejo.get("destacadas") == destacadas:
            print(json.dumps({"mes": viejo.get("mes"), "nuevo": False}, ensure_ascii=False)); return
        o = informe(texto_pdf(pedir(PDF).read()))
        cod = {u["codigo"] for u in o["escasez"] + o["sequia"]}
        falta = [u for u in destacadas if u not in cod]
        if falta: raise ValueError(f"el informe no trae {', '.join(falta)}")
        o.update({"destacadas": destacadas, "modificado": mod, "enlace": PDF, "pagina": PAGINA,
                  "fuente": "Junta de Andalucía (SAIH Hidrosur, informe de escasez y sequía)"})
    except Exception as e:
        print(json.dumps({"fallo": str(e)}, ensure_ascii=False)); sys.exit(2)
    x["sequia"] = o
    x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    with open(p.extras, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    print(json.dumps({"mes": o["mes"], "nuevo": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
