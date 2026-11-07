"""Ayudas y subvenciones abiertas para Adra (4.31, lo pidió Isa el 7 nov 2026: «ayudas y subvenciones abiertas para Adra, Almería y
Andalucía, con su plazo»). De la Base de Datos Nacional de Subvenciones (BDNS, Intervención General de la Administración del Estado), por su
API pública (www.infosubvenciones.es/bdnstrans/api; especificación en /bdnstrans/estaticos/doc/snpsap-api.json; sin clave; su robots.txt
no trae reglas). Las convocatorias registradas en el último año de:
  - el Ayuntamiento de Adra (todas, de los dos últimos años),
  - la Diputación de Almería y sus institutos,
  - la Junta de Andalucía (sus consejerías y agencias; sin las delegaciones de otras provincias),
para personas físicas (1) y para pymes y autónomos (3). La API no dice cuáles están abiertas (pregunta 203 de su ayuda): se mira el detalle
de cada una y su plazo (las fechas de inicio y fin de solicitud o, si no las trae, el texto del plazo: «19 de noviembre de 2026»,
«15 días naturales» desde el inicio). Las de concesión directa instrumental no se pueden pedir (pregunta 204): fuera. Las que ya han
cerrado se apuntan en «ayudasCerradas» para no volver a pedirlas.

  python3 -I herramientas/ayudas.py extras.json

Imprime una línea JSON: {"ayudas": N abiertas, "vistas": M, ...} o {"error": …} (sale con 1; deja lo que había).
"""
import datetime as dt, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

TZ = ZoneInfo("Europe/Madrid")
API = "https://www.infosubvenciones.es/bdnstrans/api"
FICHA = "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/"
TIPOS = "1,3"          # personas físicas sin actividad económica; pymes y personas físicas con actividad (autónomos)
PAUSA = 0.6
MESES = {m: i for i, m in enumerate(comun.MESES, 1)}
PROVINCIAS = ("ALMERÍA", "CÁDIZ", "CÓRDOBA", "GRANADA", "HUELVA", "JAÉN", "MÁLAGA", "SEVILLA")
NUMEROS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
MINUS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "a", "al", "por", "con", "o"}


def pedir(ruta, **q):
    time.sleep(PAUSA)
    return json.loads(comun.pedir(API + ruta + "?" + urllib.parse.urlencode(q, safe=",/"), aceptar="application/json", timeout=60))


def hojas(n):
    h = n.get("children") or []
    return [n["id"]] if not h else [i for c in h for i in hojas(c)]


def organos(local, autonomica):
    """Los órganos que convocan: los de Adra y los de la Diputación (del árbol de la Administración local) y los de la Junta (del de la
    autonómica), sin las delegaciones de la Junta en otras provincias."""
    alm = next(n for n in local if comun.sin_tildes(n["descripcion"]) == "almeria")
    adra = [i for c in alm["children"] if comun.sin_tildes(c["descripcion"]) == "adra" for i in hojas(c)]
    dip = [i for c in alm["children"] if "diputacion" in comun.sin_tildes(c["descripcion"]) for i in hojas(c)]
    anda = next(n for n in autonomica if comun.sin_tildes(n["descripcion"]) == "andalucia")
    otras = tuple(" EN " + p for p in PROVINCIAS if p != "ALMERÍA")
    junta = [c["id"] for c in anda["children"] if not c.get("children") and not c["descripcion"].upper().endswith(otras)]
    junta += [i for c in anda["children"] if c.get("children") for i in hojas(c)]
    return {"Adra": adra, "Diputación de Almería": dip, "Junta de Andalucía": junta}


def fecha(s):
    try: return dt.date.fromisoformat((s or "")[:10])
    except ValueError: return None


def fechas_en(t):
    """Las fechas escritas en un texto: «19 de noviembre de 2026», «20 de Eenero de 2027», «31 diciembre 2026», «15/01/2027»."""
    t = comun.sin_tildes(t)
    res = []
    for d, m, a in re.findall(r"\b(\d{1,2})\s*(?:de\s+)?([a-z]{3,11})\s*(?:de\s+|del\s+)?(\d{4})\b", t):
        mes = next((n for k, n in MESES.items() if m[:3] == k[:3] or m[1:4] == k[:3] or (k == "septiembre" and m[:3] == "set")), None)
        if mes:
            try: res.append(dt.date(int(a), mes, int(d)))
            except ValueError: pass
    for d, m, a in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t):
        try: res.append(dt.date(int(a), int(m), int(d)))
        except ValueError: pass
    return res


def publicado(c):
    f = [fecha(a.get("datPublicacion")) for a in c.get("anuncios") or []]
    f = [x for x in f if x]
    return min(f) if f else None


def plazo(c, hoy):
    """(estado, desde, hasta, texto): estado «abierta», «proxima», «cerrada» (no vuelve a abrirse) o None (no se sabe: no sale)."""
    # la instrumental no se puede pedir (pregunta 204); ni la concesión directa a alguien con nombre (no se pide y no se publican nombres)
    if "instrumental" in comun.sin_tildes(c.get("tipoConvocatoria")): return "cerrada", None, None, None
    if re.search(r"concesion directa de (?:una|la) subvencion a\b", comun.sin_tildes(c.get("descripcion"))): return "cerrada", None, None, None
    ini, fin = fecha(c.get("fechaInicioSolicitud")), fecha(c.get("fechaFinSolicitud"))
    ti, tf = comun.limpio(c.get("textInicio")), comun.limpio(c.get("textFin"))
    if "sin plazo" in comun.sin_tildes(ti + " " + tf): return "cerrada", None, None, None
    # para otro sitio (la región de la convocatoria: ES, ES6 Sur, ES61 Andalucía o ES611 Almería sí; ES612 Cádiz… no)
    reg = [comun.limpio(r.get("descripcion")).split(" ")[0] for r in c.get("regiones") or []]
    if reg and not any(r in ("ES", "ES6", "ES61", "ES611") for r in reg): return "cerrada", None, None, None
    texto = None
    if not fin and tf:
        n = re.search(r"\b(\d{1,3})\s*(?:d+[ií]as\s+)?(naturales|h[aá]biles)", comun.sin_tildes(tf))
        base = ini or (publicado(c) + dt.timedelta(days=1) if publicado(c) else None)
        if n and base:
            dias = int(n.group(1))
            if n.group(2) == "naturales": fin = base + dt.timedelta(days=dias - 1)
            elif base + dt.timedelta(days=dias * 7 // 5 + 14) < hoy: return "cerrada", ini, None, None   # pasado seguro, con festivos
            else: texto = f"{dias} días hábiles desde el {base.day} {comun.MESES[base.month - 1][:3]}"
        elif (u := re.search(r"\b(\d{1,2}|un|uno|dos|tres|cuatro|cinco|seis)\s+mes(?:es)?\b", comun.sin_tildes(tf))) and base:
            n = int(u.group(1)) if u.group(1).isdigit() else NUMEROS[u.group(1)]
            a, m = divmod(base.month - 1 + n, 12)
            fin_m = dt.date(base.year + a, m + 1, min(base.day, 28)) - dt.timedelta(days=1)
            if fin_m + dt.timedelta(days=31) < hoy: return "cerrada", ini, fin_m, None          # ni con un mes de ampliación
            texto = f"{tf[:60]} desde el {base.day} {comun.MESES[base.month - 1][:3]}"
        elif fechas_en(tf):
            fin = max(fechas_en(tf))
            if len(fechas_en(tf)) > 1: texto = tf[:120]       # varios plazos (p. ej., las escuelas infantiles): el último y el texto
    if fin:
        if fin < hoy: return "cerrada", ini, fin, None
        if ini and ini > hoy: return "proxima", ini, fin, texto
        return "abierta", ini, fin, texto
    # sin fecha de cierre: solo si es del último año (las de antes con un plazo en días desde una publicación que no viene, no)
    if (c.get("fechaRecepcion") or "")[:10] < (hoy - dt.timedelta(days=365)).isoformat(): return "cerrada", ini, None, None
    if c.get("abierto") or tf:
        if ini and ini > hoy: return "proxima", ini, None, tf[:120] or None
        return "abierta", ini, None, texto or tf[:120] or "sin fecha de cierre"
    return None, ini, None, None


def titulo(d):
    """El nombre de la convocatoria sin «Resolución de … por la que se convoca(n) …» ni «para el año 2026»."""
    t = comun.limpio(d)
    # «Resolución de 15 de octubre de 2026, de la DGIICA,», «ORDEN 21 DE ENERO DE 2026»
    t = re.sub(r"(?i)^(?:extracto\s+de\s+la\s+)?(?:resoluci[oó]n|orden|acuerdo|decreto)\s+(?:de\s+)?\d{1,2}\s+de\s+[a-z]+\s+(?:de\s+)?\d{4}"
               r"(?:\s*,\s*(?:de\s+la\s+|del\s+)?(?:[A-ZÁÉÍÓÚ]{3,10}|[^,]{3,90}?)(?=,)|\s+(?:de\s+la\s+|del\s+)[A-ZÁÉÍÓÚ]{3,10}(?=,))?\s*,?\s*", "", t)
    m = None
    for m in re.finditer(r"(?i)\b(?:se\s+convoca[n]?|se\s+efect[uú]a\s+la\s+convocatoria\s+de|convocatoria\s+(?:de|para)|se\s+aprueba[n]?)\b\s*", t[:260]): pass
    if m: t = t[m.end():]
    t = re.sub(r"(?i)^(?:,?\s*(?:para|en)\s+(?:el\s+(?:a[nñ]o|ejercicio)\s+)?\d{4},?\s*|,?\s*en\s+r[eé]gimen\s+de\s+concurrencia\s+competitiva,?\s*)+", "", t)
    t = re.sub(r"(?i)^incentivos\s+para\s+la\s+concesi[oó]n\s+de\s+(?=incentivos\b)", "", t)
    t = re.sub(r"(?i)^subvenciones\s+(?:(?:en|para)\s+el\s+a[nñ]o\s+\d{4},?\s*)?para\s+(?=ayudas?\b)", "", t)
    t = re.sub(r"(?i)^para\s+(?=(?:las\s+|los\s+)?(?:ayudas?|subvenci\w*|incentivos?|premios?|becas?)\b)", "", t)
    t = re.sub(r"(?i)^(?:las|los|la|el)\s+(?=(?:ayudas?|subvenci\w*|premios?|becas?)\b)", "", t).strip(" ,.;:-\"«»")
    if sum(ch.isupper() for ch in t) > 0.6 * sum(ch.isalpha() for ch in t):
        t = re.sub(r"\b(almer[ií]a|adra|andaluc[ií]a|granada|espa[nñ]a|uni[oó]n europea)\b", lambda m: m.group(1).title(), t.lower())
    return (t[:1].upper() + t[1:])[:200]


def nombre(s):
    """«CONSEJERÍA DE EMPLEO, EMPRESA Y TRABAJO AUTÓNOMO» → «Consejería de Empleo, Empresa y Trabajo Autónomo»."""
    p = (s or "").lower().split()
    return " ".join(w if (i and w in MINUS) else (w[:1].upper() + w[1:]) for i, w in enumerate(p)).replace("Prov. ", "Provincial ")


def para(c):
    t = {comun.sin_tildes(b.get("descripcion"))[:30] for b in c.get("tiposBeneficiarios") or []}
    r = []
    if any(x.startswith("personas fisicas que no") for x in t): r.append("personas")
    if any(x.startswith("pyme") for x in t): r.append("autónomos y pymes")
    if any(x.startswith("personas juridicas") for x in t): r.append("entidades")
    if any(x.startswith("gran empresa") for x in t): r.append("empresas")
    return r


def ficha(c, ambito, hoy):
    estado, ini, fin, texto = plazo(c, hoy)
    num = str(c.get("codigoBDNS") or c.get("numeroConvocatoria"))
    o = c.get("organo") or {}
    a = {"num": num, "titulo": titulo(c.get("descripcion")), "ambito": ambito, "organo": nombre(o.get("nivel3") or o.get("nivel2")),
         "estado": estado, "enlace": FICHA + num}
    if ini: a["desde"] = ini.isoformat()
    if fin: a["hasta"] = fin.isoformat()
    if texto: a["plazo"] = texto
    if c.get("presupuestoTotal"): a["importe"] = round(float(c["presupuestoTotal"]))
    if para(c): a["para"] = para(c)
    b = next((x.get("url") for x in c.get("anuncios") or [] if x.get("url")), None)
    if b: a["boletin"] = b
    if c.get("fechaRecepcion"): a["registrada"] = c["fechaRecepcion"][:10]
    return a


def orden(a):
    return (a["estado"] != "abierta", a.get("hasta") or "9999", a.get("desde") or "", a["titulo"])


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    ruta = sys.argv[1]
    x = json.load(open(ruta, encoding="utf-8"))
    hoy = dt.datetime.now(TZ).date()
    cerradas = set(x.get("ayudasCerradas") or [])
    vistas, nuevas, abiertas, fallos = 0, 0, [], []
    try:
        org = organos(pedir("/organos", vpd="GE", idAdmon="L"), pedir("/organos", vpd="GE", idAdmon="A"))
        for ambito, ids in org.items():
            if not ids: fallos.append(f"sin órganos de {ambito}"); continue
            q = {"vpd": "GE", "organos": ",".join(map(str, ids)), "pageSize": 200, "order": "fechaRecepcion", "direccion": "desc",
                 "fechaDesde": (hoy - dt.timedelta(days=730 if ambito == "Adra" else 365)).strftime("%d/%m/%Y")}
            if ambito != "Adra": q["tiposBeneficiario"] = TIPOS
            lista, pag = [], 0
            while True:
                r = pedir("/convocatorias/busqueda", page=pag, **q)
                lista += r.get("content") or []
                if r.get("last", True) or pag > 10: break
                pag += 1
            for c in lista:
                num = str(c.get("numeroConvocatoria"))
                vistas += 1
                if num in cerradas: continue
                try: d = pedir("/convocatorias", vpd="GE", numConv=num)
                except Exception as e: fallos.append(f"{num}: {str(e)[:60]}"); continue
                nuevas += 1
                a = ficha(d, ambito, hoy)
                if a["estado"] == "cerrada": cerradas.add(num)
                elif a["estado"]: abiertas.append(a)
                elif (c.get("fechaRecepcion") or "9999")[:10] < (hoy - dt.timedelta(days=60)).isoformat(): cerradas.add(num)   # sin plazo
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]}, ensure_ascii=False)); sys.exit(1)
    if len(fallos) > max(5, nuevas // 4):
        print(json.dumps({"error": f"{len(fallos)} fallos", "fallos": fallos[:5]}, ensure_ascii=False)); sys.exit(1)
    # las líneas de una misma convocatoria (mismo título, plazo y órgano), una vez
    vistos = {}
    for a in sorted(abiertas, key=orden):
        k = (a["titulo"], a.get("hasta"), a.get("plazo"), a["organo"])
        if k in vistos: vistos[k]["lineas"] = vistos[k].get("lineas", 1) + 1; vistos[k]["importe"] = vistos[k].get("importe", 0) + a.get("importe", 0)
        else: vistos[k] = a
    abiertas = list(vistos.values())
    vivas = {"lista": abiertas, "fuente": "Base de Datos Nacional de Subvenciones (BDNS)", "enlace": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias"}
    if x.get("ayudas", {}).get("lista") != abiertas or set(x.get("ayudasCerradas") or []) != cerradas:
        x["ayudas"] = dict(vivas, dia=hoy.isoformat())
        x["ayudasCerradas"] = sorted(cerradas, key=lambda s: (len(s), s))
        x["actualizado"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
        comun.guardar(ruta, x)
    print(json.dumps({"ayudas": len(abiertas), "vistas": vistas, "pedidas": nuevas, "cerradas": len(cerradas), "fallos": fallos[:3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
