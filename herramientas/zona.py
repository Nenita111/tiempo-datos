"""La zona de empleo de la tele (lo pidió Isa el 29 oct 2026), lo mismo que Empleo.Zona de la app: la provincia de Almería sin el Levante,
la costa de Granada de Motril hacia Almería y lo que es para toda Andalucía. Y las ofertas de empleo público del SAE de esa zona (lo mismo que
Empleo.ofertasSae), para las etiquetas de Jev (etiquetas.py) y los avisos al móvil (avisos_movil.py).
"""
import datetime as dt, json, re, unicodedata, urllib.parse, urllib.request

SAE = "https://saempleo.es/ags/api/MS-HERMES/hermes/ofertas/ofertaspublicadas"     # la lista que pide su página «Ofertas de empleo»; sin robots.txt
SAE_FICHA = "https://saempleo.es/ags/candidaturas/lista-ofertas-publicas/detalle-oferta?origin=portal&ofertaId="
UA = "TiempoYRadar/1.0 (tareas de la tele)"

# comarca Levante Almeriense: Orden de 14 de marzo de 2003, mapa de comarcas de Andalucía (BOJA 59, de 27/03/2003)
LEVANTE = {"ANTAS", "BEDAR", "CARBONERAS", "CUEVAS DEL ALMANZORA", "LOS GALLARDOS", "GARRUCHA", "HUERCAL OVERA", "LUBRIN", "MOJACAR", "PULPI",
           "SORBAS", "TURRE", "VERA"}
# la costa de Granada de Motril hacia Almería: municipios y pueblos de su costa
COSTA = {"MOTRIL", "CALAHONDA", "CARCHUNA", "TORRENUEVA", "TORRENUEVA COSTA", "GUALCHOS", "CASTELL DE FERRO", "RUBITE", "POLOPOS", "LA MAMOLA",
         "SORVILAN", "MELICENA", "ALBUNOL", "LA RABITA", "EL POZUELO"}
# los nombres con tildes, por su código INE (INE, «Relación de municipios y códigos ... a 1 de enero de 2026»)
NOMBRES = {
    "04001": "Abla", "04002": "Abrucena", "04003": "Adra", "04004": "Albanchez", "04005": "Alboloduy", "04006": "Albox",
    "04007": "Alcolea", "04008": "Alcóntar", "04009": "Alcudia de Monteagud", "04010": "Alhabia", "04011": "Alhama de Almería",
    "04012": "Alicún", "04013": "Almería", "04014": "Almócita", "04015": "Alsodux", "04016": "Antas", "04017": "Arboleas",
    "04018": "Armuña de Almanzora", "04019": "Bacares", "04020": "Bayárcal", "04021": "Bayarque", "04022": "Bédar",
    "04023": "Beires", "04024": "Benahadux", "04026": "Benitagla", "04027": "Benizalón", "04028": "Bentarique", "04029": "Berja",
    "04030": "Canjáyar", "04031": "Cantoria", "04032": "Carboneras", "04033": "Castro de Filabres", "04034": "Cóbdar",
    "04035": "Cuevas del Almanzora", "04036": "Chercos", "04037": "Chirivel", "04038": "Dalías", "04041": "Enix", "04043": "Felix",
    "04044": "Fines", "04045": "Fiñana", "04046": "Fondón", "04047": "Gádor", "04048": "Los Gallardos", "04049": "Garrucha",
    "04050": "Gérgal", "04051": "Huécija", "04052": "Huércal de Almería", "04053": "Huércal-Overa", "04054": "Íllar",
    "04055": "Instinción", "04056": "Laroya", "04057": "Laujar de Andarax", "04058": "Líjar", "04059": "Lubrín",
    "04060": "Lucainena de las Torres", "04061": "Lúcar", "04062": "Macael", "04063": "María", "04064": "Mojácar",
    "04065": "Nacimiento", "04066": "Níjar", "04067": "Ohanes", "04068": "Olula de Castro", "04069": "Olula del Río",
    "04070": "Oria", "04071": "Padules", "04072": "Partaloa", "04073": "Paterna del Río", "04074": "Pechina", "04075": "Pulpí",
    "04076": "Purchena", "04077": "Rágol", "04078": "Rioja", "04079": "Roquetas de Mar", "04080": "Santa Cruz de Marchena",
    "04081": "Santa Fe de Mondújar", "04082": "Senés", "04083": "Serón", "04084": "Sierro", "04085": "Somontín", "04086": "Sorbas",
    "04087": "Suflí", "04088": "Tabernas", "04089": "Taberno", "04090": "Tahal", "04091": "Terque", "04092": "Tíjola",
    "04093": "Turre", "04094": "Turrillas", "04095": "Uleila del Campo", "04096": "Urrácal", "04097": "Velefique",
    "04098": "Vélez-Blanco", "04099": "Vélez-Rubio", "04100": "Vera", "04101": "Viator", "04102": "Vícar", "04103": "Zurgena",
    "04901": "Las Tres Villas", "04902": "El Ejido", "04903": "La Mojonera", "04904": "Balanegra", "18006": "Albuñol",
    "18093": "Gualchos", "18140": "Motril", "18162": "Polopos", "18170": "Rubite", "18177": "Sorvilán", "18916": "Torrenueva Costa"}


def aplica(ine): return (ine or "")[:2] == "04"            # la zona, con el pueblo en la provincia de Almería


def plano(s):
    """«EJIDO, EL» → «EL EJIDO», «Huércal-Overa» → «HUERCAL OVERA»."""
    t = unicodedata.normalize("NFD", s or "")
    t = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9, ]", " ", "".join(c for c in t if unicodedata.category(c) != "Mn").upper())).strip()
    m = re.match(r"^(.*), (EL|LA|LOS|LAS)$", t)
    return f"{m.group(2)} {m.group(1)}" if m else t


def levante(municipio): return plano(municipio) in LEVANTE


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
            if m.get("nombre") and ((p == "04" and not levante(m["nombre"])) or (p == "18" and costa(m["nombre"]))):
                n = nombre(m.get("id", ""), m["nombre"])
                if n not in aqui: aqui.append(n)
        if not aqui or not o.get("idOferta"): continue
        res.append({"id": o["idOferta"], "puesto": re.sub(r"\s+", " ", o.get("denominacionPuesto") or "").strip(), "sitios": aqui,
                    "hasta": fin.isoformat(timespec="minutes"), "texto": re.sub(r"\s+", " ", o.get("textoLibreDifusion") or "").strip()[:1500],
                    "ocupacion": (o.get("ocupacionPrincipal") or {}).get("nombre", ""), "url": SAE_FICHA + urllib.parse.quote(o["idOferta"])})
    res.sort(key=lambda x: (x["hasta"], x["id"]))
    return res


def lugares_ficha(h):
    """Los lugares de trabajo de la ficha de una oferta de los entes de la Junta (lo mismo que Empleo.ficha): [(sitio, provincia)]."""
    b = re.search(r"(?s)field--name-field-ofem-lugartrabajo(.*?)(?:block-field-blocknode|</main>)", h)
    out = []
    for m in re.findall(r'(?s)class="field__item">(.*?)</div>', b.group(1) if b else ""):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip()
        p = re.match(r"^(.*?)\s*(?:\((\d+)\))?\s*\(([^()]+)\)$", t)
        if p: out.append((p.group(1).strip(), p.group(3).strip()))
    return out


def junta_en_zona(lugares):
    """Como Empleo.dondeOferta con la zona: algún sitio en Almería o en la costa hasta Motril, para toda Andalucía o sin sitio."""
    prov = {p for _, p in lugares}
    return (not lugares or len(prov) >= 8 or any(p == "Almería" or (p == "Granada" and costa(s)) for s, p in lugares)
            or any(re.search(r"(?i)andaluc|todas las provincias", s) for s, _ in lugares))
