"""La zona de empleo de la tele (lo pidió Isa el 29 oct 2026), lo mismo que Empleo.Zona de la app: la provincia de Almería sin el Levante
(ni, desde 4.2, lo que está a 10 km de Serón, Tíjola u Olula del Río),
la costa de Granada de Motril hacia Almería y lo que es para toda Andalucía. Y las ofertas de empleo público del SAE de esa zona (lo mismo que
Empleo.ofertasSae), para las etiquetas de Jev (etiquetas.py) y los avisos al móvil (avisos_movil.py).
"""
import datetime as dt, html, json, re, unicodedata, urllib.parse, urllib.request
import comun      # al lado: quien importa zona ya tiene esta carpeta en su camino

SAE = "https://saempleo.es/ags/api/MS-HERMES/hermes/ofertas/ofertaspublicadas"     # la lista que pide su página «Ofertas de empleo»; sin robots.txt
SAE_FICHA = "https://saempleo.es/ags/candidaturas/lista-ofertas-publicas/detalle-oferta?origin=portal&ofertaId="
UA = comun.UA_TAREAS

# comarca Levante Almeriense: Orden de 14 de marzo de 2003, mapa de comarcas de Andalucía (BOJA 59, de 27/03/2003)
LEVANTE = {"ANTAS", "BEDAR", "CARBONERAS", "CUEVAS DEL ALMANZORA", "LOS GALLARDOS", "GARRUCHA", "HUERCAL OVERA", "LUBRIN", "MOJACAR", "PULPI",
           "SORBAS", "TURRE", "VERA"}
# la costa de Granada de Motril hacia Almería: municipios y pueblos de su costa
COSTA = {"MOTRIL", "CALAHONDA", "CARCHUNA", "TORRENUEVA", "TORRENUEVA COSTA", "GUALCHOS", "CASTELL DE FERRO", "RUBITE", "POLOPOS", "LA MAMOLA",
         "SORVILAN", "MELICENA", "ALBUNOL", "LA RABITA", "EL POZUELO"}
# 4.2 (lo pidió Isa el 30 oct 2026: «no me interesan las ofertas de Serón, Tíjola ni Olula del Río ni 10 km alrededor de esos pueblos»): los
# municipios cuya cabecera está a 10 km o menos (en línea recta) de la de alguno de los tres; cabeceras municipales de la capa «Núcleos urbanos»
# de los Datos Espaciales de Referencia de Andalucía (DERA, IECA; WFS DERA_g7_sistema_urbano, 30 oct 2026). Lo mismo que Empleo.Zona.ALMANZORA.
ALMANZORA = {"04069": "OLULA DEL RIO", "04083": "SERON", "04092": "TIJOLA", "04021": "BAYARQUE", "04018": "ARMUNA DE ALMANZORA", "04062": "MACAEL",
             "04044": "FINES", "04087": "SUFLI", "04084": "SIERRO", "04076": "PURCHENA", "04061": "LUCAR", "04085": "SOMONTIN", "04056": "LAROYA",
             "04096": "URRACAL", "04008": "ALCONTAR", "04072": "PARTALOA", "04031": "CANTORIA", "04019": "BACARES", "04058": "LIJAR"}
FUERA = LEVANTE | set(ALMANZORA.values())
# lo del SAS que es solo de esos pueblos o del Alto Almanzora (con mayúscula: «fines» es también una palabra), como soloFueraSas de la tele
ALMANZORA_SAS = re.compile(r"\b(?:Ser[oó]n|T[ií]jola|Olula del R[ií]o|Bayarque|Armuña de Almanzora|Macael|Fines|Sufl[ií]|Sierro|Purchena|L[uú]car|"
                           r"Somont[ií]n|Laroya|Urr[aá]cal|Alc[oó]ntar|Partaloa|Cantoria|Bacares|L[ií]jar|Alto Almanzora)(?![A-Za-zÁÉÍÓÚáéíóúÑñ])")
# los nombres con tildes, por su código INE: los de la provincia, de municipios_almeria.json (INE, «Relación de municipios y códigos ... a 1 de
# enero de 2026»), y los de la costa de Granada, aquí
NOMBRES = {ine: n for n, ine, *_ in comun.municipios()} | {
    "18006": "Albuñol", "18093": "Gualchos", "18140": "Motril", "18162": "Polopos", "18170": "Rubite", "18177": "Sorvilán", "18916": "Torrenueva Costa"}


def aplica(ine): return (ine or "")[:2] == "04"            # la zona, con el pueblo en la provincia de Almería


def plano(s):
    """«EJIDO, EL» → «EL EJIDO», «Huércal-Overa» → «HUERCAL OVERA»."""
    t = unicodedata.normalize("NFD", s or "")
    t = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9, ]", " ", "".join(c for c in t if unicodedata.category(c) != "Mn").upper())).strip()
    m = re.match(r"^(.*), (EL|LA|LOS|LAS)$", t)
    return f"{m.group(2)} {m.group(1)}" if m else t


def levante(municipio): return plano(municipio) in LEVANTE
def fuera(municipio): return plano(municipio) in FUERA           # 4.2: el Levante y lo de alrededor de Serón, Tíjola y Olula del Río
FUERA_SAE = {"NIJAR"}                                           # 4.7 (lo pidió Isa el 31 oct 2026): en las del SAE, tampoco Níjar
def fuera_sae(municipio): return fuera(municipio) or plano(municipio) in FUERA_SAE


def costa(sitio):
    p = plano(re.sub(r'\(.*?\)|".*?"', " ", sitio or ""))
    return p in COSTA or any(p.startswith(c + " ") for c in COSTA)


def nombre(ine, n):
    if ine in NOMBRES: return NOMBRES[ine]
    t = re.sub(r"\s+", " ", (n or "").strip()); m = re.match(r"^(.*), (EL|LA|LOS|LAS)$", t)
    t = f"{m.group(2)} {m.group(1)}" if m else t
    return " ".join(w if i and w in ("de", "del", "la", "las", "los", "el", "y") else "-".join(x[:1].upper() + x[1:] for x in w.split("-"))
                    for i, w in enumerate(t.lower().split(" ")))


def lista_sae(pedir=None):
    if pedir: return pedir(SAE)
    r = urllib.request.Request(SAE, data=b"{}", headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as f: return json.loads(f.read().decode("utf-8"))


def ofertas_sae(lista, ahora):
    """Las de empleo público («ofertaPublica»: S) en plazo con algún sitio de la zona; primero las que acaban antes (como la app)."""
    res = []
    for o in lista or []:
        if o.get("ofertaPublica") != "S": continue
        try: fin = dt.datetime.strptime(o.get("fechaFin", ""), "%d-%m-%Y %H:%M")
        except ValueError: continue
        if fin < ahora.replace(tzinfo=None): continue
        sitios = (o.get("ubicacionesMultiples") or []) + (o.get("ubicacionesItinerantes") or []) or [o]
        aqui = []
        for s in sitios:
            p, m = (s.get("provincia") or {}).get("id", ""), (s.get("municipio") or {})
            if m.get("nombre") and ((p == "04" and not fuera_sae(m["nombre"])) or (p == "18" and costa(m["nombre"]))):
                n = nombre(m.get("id", ""), m["nombre"])
                if n not in aqui: aqui.append(n)
        if not aqui or not o.get("idOferta"): continue
        res.append({"id": o["idOferta"], "puesto": re.sub(r"\s+", " ", o.get("denominacionPuesto") or "").strip(), "sitios": aqui,
                    "hasta": fin.isoformat(timespec="minutes"), "texto": re.sub(r"\s+", " ", o.get("textoLibreDifusion") or "").strip()[:1500],
                    "ocupacion": (o.get("ocupacionPrincipal") or {}).get("nombre", ""), "url": SAE_FICHA + urllib.parse.quote(o["idOferta"])})
    res.sort(key=lambda x: (x["hasta"], x["id"]))
    return res


def lugares_ficha(h):
    """Los lugares de trabajo de la ficha de una oferta de los entes de la Junta (lo mismo que Empleo.ficha): [(sitio, provincia)].
    4.1: un lugar que no dice su provincia («Sede central») va con la provincia vacía (antes se perdía)."""
    b = re.search(r"(?s)field--name-field-ofem-lugartrabajo(.*?)(?:block-field-blocknode|</main>)", h)
    out = []
    for m in re.findall(r'(?s)class="field__item">(.*?)</div>', b.group(1) if b else ""):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m))).strip()     # 4.1: «&quot;La Cepa&quot;» como en la tele
        p = re.match(r"^(.*?)\s*(?:\((\d+)\))?\s*\(([^()]+)\)$", t)
        if p: out.append((p.group(1).strip(), p.group(3).strip()))
        elif t: out.append((t, ""))
    return out


def levante_sitio(sitio):
    """Un sitio de la ficha de la Junta («Huércal-Overa (2)», «Vera "Hospital"») del Levante Almeriense."""
    p = plano(re.sub(r'\(.*?\)|".*?"', " ", sitio or ""))
    return p in LEVANTE or any(p.startswith(x + " ") for x in LEVANTE)


def fuera_sitio(sitio):
    """4.2: un sitio de la ficha de la Junta («Macael (2)») del Levante o de alrededor de Serón, Tíjola y Olula del Río."""
    p = plano(re.sub(r'\(.*?\)|".*?"', " ", sitio or ""))
    return p in FUERA or any(p.startswith(x + " ") for x in FUERA)


def solo_fuera_sas(texto):
    """4.2: un título del SAS que solo nombra esos pueblos o el Alto Almanzora (o el Levante) y ningún otro sitio de la zona ni de otra provincia."""
    lev = re.compile(r"(?i)Hu[eé]rcal[- ]Overa|La Inmaculada|\b(?:Vera|Garrucha|Moj[aá]car|Carboneras|Pulp[ií]|Antas|B[eé]dar|Turre|Lubr[ií]n|Sorbas|"
                     r"Cuevas del Almanzora|Los Gallardos)\b")
    t = texto or ""
    if not (lev.search(t) or ALMANZORA_SAS.search(t)): return False
    resto = ALMANZORA_SAS.sub(" ", lev.sub(" ", t))
    return not re.search(r"(?i)Torrec[aá]rdenas|Poniente|Distrito (?:Sanitario )?(?:de Atención Primaria )?Almer[ií]a|Almanzora|El Ejido|Roquetas|"
                         r"Sevilla|M[aá]laga|C[oó]rdoba|C[aá]diz|Huelva|Ja[eé]n|Granada", resto)


def junta_en_zona(lugares):
    """Como Empleo.dondeOferta con la zona (4.0, lo pidió Isa: «los mismos criterios geográficos que en el SAE»): algún sitio en Almería
    fuera del Levante o en la costa hasta Motril, o para toda Andalucía. 4.1 (lo pidió Isa: «muestra las ofertas activas que no indiquen
    provincia o que sean para todas»): también las que no dicen provincia (sin lugares en la ficha o algún lugar sin ella). Quien llama se
    asegura de que la ficha llegó bien (`ficha_valida`)."""
    prov = {p for _, p in lugares if p}
    return (not lugares or any(not p for _, p in lugares) or len(prov) >= 8
            or any((p == "Almería" and not fuera_sitio(s)) or (p == "Granada" and costa(s)) for s, p in lugares)
            or any(re.search(r"(?i)andaluc|todas las provincias", f"{s} {p}") for s, p in lugares))


def ficha_valida(h):
    """La página es la ficha de una oferta (tiene su plazo o su fecha de publicación), no un error o una página de mantenimiento."""
    return bool(re.search(r"field-ofem-fecha-(?:publi|ini)", h or ""))
