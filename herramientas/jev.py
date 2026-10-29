"""Jev (TypeSafe System One) para las tareas de la tele: un cliente sin dependencias y todas las preguntas en un solo sitio
(es lo que hay que revisar y ajustar: las preguntas, los umbrales y lo que se le enseña).

Jev no escribe nada: contesta preguntas cerradas (sí/no con su probabilidad, una opción de una lista, un nivel) sobre lo que se le da.
Aquí decide cosas que una regla de texto hace mal (si un titular anuncia un corte, si un sorteo es de un comercio de la zona, qué
receta pega con el tiempo de hoy, de qué tipo es una disposición del SAS); las fechas, las cuentas y lo que se puede comprobar con
exactitud se hacen en el código. Las preguntas van en inglés (Jev rinde mejor) y los textos, tal cual, en español.

Cómo llega a Jev (29 oct 2026, lo pidió Isa: «usa el conector de Jev de Composio de ahora en adelante»): por el conector JEV de Composio,
con la cuenta de Isa. Los scripts no pueden llamar a un conector, así que las tareas lo hacen en dos tiempos (composio_jev.py):
  1. En el sandbox de Composio (COMPOSIO_REMOTE_WORKBENCH, donde está run_composio_tool) se ejecutan los mismos scripts sobre la misma
     versión del repositorio; cada pregunta va a Jev por Composio (COMPOSIO) y la respuesta se guarda (GUARDADAS) con su clave: el hash de
     la petición entera (estado, modelo y preguntas). Se sube y da una URL.
  2. En la sesión de la tarea se baja a un fichero y los scripts se ejecutan con JEV_CACHE=<fichero>: cada pregunta igual encuentra su
     respuesta. Si falta (la fuente cambió entre una vez y otra), SinRespuesta: ese elemento se queda sin Jev y el resto sigue.
Sin caché y con la variable TYPESAFE_API_KEY en el entorno, directo a la API (como hasta 3.5). Sin nada de eso: SinJev, y cada script sigue
como antes de Jev (reglas de texto o nada). La clave nunca en el repositorio ni en la salida.
"""
import hashlib, json, os, re, time, urllib.error, urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MODELO = "jev-1.13.0"        # fijado: los umbrales se ajustan contra esta versión


class SinJev(Exception):
    """No se puede preguntar a Jev (sin clave, sin red o caído): se sigue sin él."""


class SinRespuesta(SinJev):
    """Con la caché de Composio, esta pregunta no tiene respuesta guardada: solo este elemento se queda sin Jev (el resto sigue)."""


COMPOSIO = None       # en el sandbox de Composio, run_composio_tool (lo pone composio_jev.py)
GUARDADAS = {}        # lo que ha contestado Jev por Composio en esta ejecución: {clave: respuesta}
_CACHE = None


def clave(cuerpo):
    """La de la caché: el hash de la petición entera (igual en el sandbox y en la tarea si el estado y las preguntas son iguales)."""
    return hashlib.sha256(json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        f = os.environ.get("JEV_CACHE", "").strip()
        if f:
            try:
                with open(f, encoding="utf-8") as x: _CACHE = json.load(x)
            except (OSError, ValueError): pass
    return _CACHE


def _con_respuestas(r):
    """La respuesta de JEV_EVALUATE_STATE viene envuelta («data», a veces dos veces): el dict que lleva «answers»."""
    for _ in range(4):
        if not isinstance(r, dict): return None
        if isinstance(r.get("answers"), dict): return r
        r = r.get("data") if "data" in r else r.get("response")
    return None


def _por_composio(cuerpo, intentos=3, dormir=None):
    msg, dormir = "", dormir or time.sleep
    for n in range(intentos):
        try: r, err = COMPOSIO("JEV_EVALUATE_STATE", {"model": cuerpo["model"], "state": cuerpo["state"], "questions": cuerpo["questions"]})
        except Exception as e: r, err = None, f"{type(e).__name__}: {e}"
        d = None if err else _con_respuestas(r)
        if d: return {"answers": d["answers"], "model": d.get("model", cuerpo["model"])}
        msg = str(err or (r or {}).get("error") or "sin «answers» en la respuesta")[:300]
        if re.search(r"\b422\b|validation|invalid", msg, re.I): raise ValueError(f"Jev rechaza la pregunta: {msg}")
        if re.search(r"credit|unauthori|forbidden|\b40[13]\b|no active connection|not connected|connect (your|their) own", msg, re.I):
            raise SinJev(f"Jev por Composio: {msg}")
        if n < intentos - 1: dormir(2 * 2 ** n)
    raise SinJev(f"Jev por Composio: {msg}")


def _apuntar_falta(k):
    f = os.environ.get("JEV_FALTAN", "").strip()
    if f:
        try:
            with open(f, "a", encoding="utf-8") as x: x.write(k + "\n")
        except OSError: pass


def _pedir(cuerpo, timeout):
    k = clave(cuerpo)
    c = cache()
    if k in c:
        if COMPOSIO: GUARDADAS[k] = c[k]             # en el sandbox, lo que sale de la caché guardada también se sube (la tarea la necesita)
        return c[k]
    if COMPOSIO:
        r = _por_composio(cuerpo)
        GUARDADAS[k] = c[k] = r
        return r
    clave_api = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if os.environ.get("JEV_CACHE", "").strip() and not clave_api:
        _apuntar_falta(k)
        raise SinRespuesta("Jev: esta pregunta no está en la caché de Composio")
    cab = {"Content-Type": "application/json", "User-Agent": "TiempoYRadar/1.0 (tareas de la tele)"}
    if clave_api: cab["Authorization"] = f"Bearer {clave_api}"
    r = urllib.request.Request(URL, data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"), headers=cab, method="POST")
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read().decode("utf-8"))


def preguntar(estado, preguntas, modelo=MODELO, intentos=4, timeout=20, pedir=None, dormir=time.sleep):
    """Todas las preguntas sobre un mismo estado en una sola petición. Devuelve (respuestas, modelo que contestó).
    Reintenta 429, 529 y 5xx con espera creciente (y la de retry-after); 401/403 o sin red → SinJev; 422 → ValueError (pregunta mal hecha)."""
    pedir = pedir or _pedir
    cuerpo = {"state": estado, "model": modelo, "questions": preguntas}
    espera = 1.0
    for n in range(intentos):
        try:
            r = pedir(cuerpo, timeout)
            return r["answers"], r.get("model", modelo)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403): raise SinJev(f"Jev: sin clave o clave no válida (HTTP {e.code})") from None
            if e.code == 422: raise ValueError(f"Jev rechaza la pregunta: {e.read()[:300]!r}") from None
            if e.code not in (408, 429, 529) and e.code < 500: raise SinJev(f"Jev: HTTP {e.code}") from None
            if n == intentos - 1: raise SinJev(f"Jev: HTTP {e.code} tras {intentos} intentos") from None
            try: espera = max(espera, float(e.headers.get("retry-after") or 0))
            except (TypeError, ValueError): pass
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if n == intentos - 1: raise SinJev(f"Jev: sin conexión ({e})") from None
        dormir(min(espera, 20)); espera *= 2
    raise SinJev("Jev: sin respuesta")


def noul(instrucciones, si=None, no=None):
    q = {"type": "noul", "instructions": instrucciones}
    if si or no: q["criteria"] = {"true": si, "false": no}
    return q


def choice(instrucciones, opciones):
    return {"type": "choice", "instructions": instrucciones, "criteria": opciones}


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_MES = {str(d): None for d in range(1, 32)} | {"not_stated": "No day of the month is given"}
MESES_OPC = {m: None for m in MESES} | {"not_stated": "No month is given"}

# ------------------------------------------------------------------ 1. ¿El titular anuncia un corte de agua o de luz en el pueblo?
# estado: {"pueblo": "Adra", "noticia": {"titulo": …, "entradilla": …}}
SI, NO = 0.7, 0.3          # por encima de SI, es; por debajo de NO, no es; en medio, decide la regla de texto de antes


def preguntas_corte():
    return {
        "anuncia": noul("Does `noticia` (a Spanish news headline and its lead) announce that the water supply or the electricity supply "
                        "will be cut, or is cut right now, in some place?",
                        si="A planned or ongoing water or power cut: corte, interrupción, suspensión del suministro, apagón, sin agua, sin luz",
                        no="Anything else: the supply has been restored, irrigation or drought restrictions, prices or bills, works that do not "
                           "cut the supply, a report about an outage that is already over"),
        "tipo": choice("If `noticia` is about a cut, which supply or service is cut?",
                       {"agua": "Drinking water supply (agua potable, red de abastecimiento)",
                        "luz": "Electricity (luz, suministro eléctrico, apagón)",
                        "trafico": "A road or street closed to traffic",
                        "otro": "Something else, or no cut at all"}),
        "en_pueblo": noul("Does the cut described in `noticia` affect `pueblo` (the town itself or one of its neighbourhoods or "
                          "villages), rather than only other towns?"),
        "restablecido": noul("Does `noticia` say that the supply is already back or that the cut has ended?"),
        "dia": choice("If `noticia` gives the day of the month when the cut happens, which day is it?", DIAS_MES),
        "mes": choice("If `noticia` gives the month when the cut happens, which month is it?", MESES_OPC),
    }


def es_corte(r, regla=None):
    """Tipo de corte («agua» o «luz») o None. Seguro (≥ SI o ≤ NO), manda Jev; si duda, la regla de texto de antes."""
    a, pueblo, ya = r["anuncia"]["noul"], r["en_pueblo"]["noul"], r["restablecido"]["noul"]
    tipo = r["tipo"]["choice"]
    if ya >= SI or pueblo <= NO or a <= NO: return None
    if a >= SI and pueblo >= 0.5 and tipo in ("agua", "luz"): return tipo
    return regla if regla in ("agua", "luz") else None


# ------------------------------------------------------------------ 2. Sorteos de sortea2.com: ¿de un comercio de la zona?
# estado: {"zona": […], "promo": {"texto": …}}
def preguntas_sorteo():
    return {
        "sorteo": noul("Is `promo.texto` a giveaway, raffle or contest in which people can win a prize?"),
        "local": noul("Is the organizer of `promo` (the shop, business, club or institution that runs it) located in one of the towns "
                      "listed in `zona`, according to `promo.texto`?",
                      si="The text places the organizer in one of those towns (address, 'en Adra', the shop's town)",
                      no="The organizer is elsewhere, or a town in `zona` is only mentioned in passing"),
        "nacional": noul("Does `promo.texto` say the giveaway is open to people from all of Spain, or that the prize is shipped anywhere in Spain?"),
        "fin": noul("Does `promo.texto` state the date when the giveaway closes or when the winner is drawn?"),
    }


def sorteo_candidato(r):
    return r["sorteo"]["noul"] >= SI and r["local"]["noul"] >= 0.5 and r["nacional"]["noul"] < 0.5 and r["fin"]["noul"] >= 0.5


# ------------------------------------------------------------------ 3. La receta que pega con el tiempo de hoy
# estado: {"tiempo_hoy": {"temperatura": …, "lluvia": …, "viento": …}, "mes": …}; las opciones, las recetas del mes que no han salido hace poco
def preguntas_receta(opciones):
    """opciones: {nombre: descripción corta}."""
    return {"plato": choice("Which of these dishes is the best fit to cook at home today, given the weather in `tiempo_hoy` "
                            "(hot dishes and stews for cold or rainy days, salads and cold dishes for hot days)?", opciones)}


# ------------------------------------------------------------------ 4. Disposiciones del SAS (BOJA y BOE): tipo y provincia
# estado: {"disposicion": {"boletin": …, "texto": …}}
TIPOS_SAS = {
    "convocatoria": "Calls a selection process or competition for posts (convoca, concurso-oposición, proceso selectivo, oferta de plazas)",
    "lista_provisional": "Publishes a provisional list (lista provisional, relación provisional) of admitted, excluded or successful people",
    "lista_definitiva": "Publishes a final list (lista definitiva, relación definitiva) of admitted, excluded or successful people",
    "nombramiento": "Appoints people to posts (nombra, nombramiento, toma de posesión)",
    "cese": "Removes people from posts (cese, cesa)",
    "bolsa": "Temporary employment pool (bolsa de empleo temporal, bolsa única)",
    "traslado": "Transfer competition or allocation of posts (concurso de traslado, adjudicación de destinos)",
    "otra": "Anything else (agreements, delegations, regulations, appeals)",
}
PROV_SAS = {
    "almeria": "A centre, hospital, health district or management area in the province of Almería (Torrecárdenas, Poniente, Levante Alto Almanzora, Distrito Almería)",
    "andalucia": "The whole Andalusian Health Service, with no particular province",
    "otra": "A centre or area in another province",
    "no_consta": "The text does not say",
}


# 3.7 (lo pidió Isa el 29 oct 2026): la zona de la tele, para enseñar solo lo de Almería (sin lo que es solo del Levante), lo de la costa de
# Granada hasta Motril y lo de toda Andalucía (la comarca Levante Almeriense: Orden de 14 de marzo de 2003, BOJA 59)
ZONA_SAS = {
    "almeria": "A centre or area in the province of Almería that is not only in the Levante Almeriense comarca (Torrecárdenas, Poniente, "
               "Distrito Almería, Distrito Poniente, the Área de Gestión Sanitaria Norte de Almería as a whole, the Alto Almanzora)",
    "levante": "Only the Levante Almeriense comarca: Hospital La Inmaculada (Huércal-Overa) or a health centre in Antas, Bédar, Carboneras, "
               "Cuevas del Almanzora, Los Gallardos, Garrucha, Huércal-Overa, Lubrín, Mojácar, Pulpí, Sorbas, Turre or Vera",
    "costa_granada": "The coast of Granada from Motril towards Almería: Área de Gestión Sanitaria Sur de Granada, Hospital Santa Ana de Motril, "
                     "or a health centre in Motril, Calahonda, Castell de Ferro, Polopos, La Mamola, Albuñol or La Rábita",
    "andalucia": "The whole Andalusian Health Service, with no particular centre, area or province",
    "otra": "A centre or area in another province (including the rest of the province of Granada)",
    "no_consta": "The text does not say",
}


def preguntas_sas():
    return {"tipo": choice("What does `disposicion.texto` (the title of a Spanish official gazette entry about the Andalusian Health Service) do?", TIPOS_SAS),
            "provincia": choice("Which place does `disposicion.texto` concern?", PROV_SAS),
            "zona": choice("Which area does `disposicion.texto` concern?", ZONA_SAS)}


# ------------------------------------------------------------------ 5. Titulares: además del corte, ¿anuncia una actividad o una colecta?
# (las mismas noticias y el mismo estado que el corte: todo en una petición)
def preguntas_titular():
    return preguntas_corte() | {
        "actividad": noul("Does `noticia` announce a public activity or event (concert, fair, exhibition, festivity, sports event, talk, market) "
                          "that will take place in `pueblo` on a specific day?",
                          si="An upcoming event in that town with its day", no="News about something else, an event elsewhere, or one already held"),
        "colecta": noul("Does `noticia` announce a blood donation drive (colecta, donación de sangre) that will take place in `pueblo`?"),
    }


# ------------------------------------------------------------------ 6. Alertas alimentarias de la AESAN: ¿qué alérgeno?
# estado: {"alerta": {"titulo": …}}; los 14 alérgenos de declaración obligatoria (Reglamento (UE) 1169/2011, anexo II)
ALERGENOS = {
    "gluten": "Cereals containing gluten (gluten, trigo, cebada, centeno, avena)", "crustaceos": "Crustaceans (crustáceos)",
    "huevo": "Egg (huevo)", "pescado": "Fish (pescado)", "cacahuete": "Peanuts (cacahuete)", "soja": "Soy (soja)",
    "leche": "Milk or lactose (leche, lactosa, proteína de leche)", "frutos_cascara": "Tree nuts (almendra, avellana, nuez, anacardo, pistacho…)",
    "apio": "Celery (apio)", "mostaza": "Mustard (mostaza)", "sesamo": "Sesame (sésamo)", "sulfitos": "Sulphites (sulfitos, dióxido de azufre)",
    "altramuces": "Lupin (altramuces)", "moluscos": "Molluscs (moluscos)",
    "ninguno": "The alert is not about an undeclared allergen (pathogens, foreign bodies, contaminants, other substances)",
}


def preguntas_alergeno():
    return {"alergeno": choice("Which undeclared allergen, if any, is `alerta.titulo` (a Spanish food safety alert) about?", ALERGENOS)}


# ------------------------------------------------------------------ 7. Medicamentos retirados (AEMPS): ¿hay que devolver los de casa?
# (si se vende sin receta lo dice la base oficial CIMA, en el código; aquí solo lo que hay que entender del texto)
def preguntas_medicamento():
    return {"devolver": noul("Does `alerta.medida` (the measure in a Spanish medicine recall) ask patients or the public to return, or stop "
                             "using, the units they already have at home?",
                             si="Patients must return or stop using the affected units", no="Only pharmacies, wholesalers or hospitals must act")}


# ------------------------------------------------------------------ 8. Productos peligrosos (Safety Gate): ¿es para niños?
def preguntas_producto():
    return {"ninos": noul("Is the product in `producto` meant to be used by or for babies or children (toys, childcare articles, "
                          "children's clothing, furniture or cosmetics)?")}


# ------------------------------------------------------------------ 9. Ofertas de empleo de la Junta: titulación y experiencia
NIVELES = {
    "sin_titulo": "No qualification required", "eso": "Secondary school certificate (Graduado en ESO, Graduado Escolar)",
    "bachillerato": "Bachillerato", "fp_basica": "Basic vocational training (FP Básica)",
    "fp_medio": "Intermediate vocational training (Técnico, Grado Medio, CFGM)", "fp_superior": "Higher vocational training (Técnico Superior, Grado Superior, CFGS)",
    "grado": "University degree (Grado, Licenciatura, Diplomatura, Ingeniería, Arquitectura)", "master": "Master's degree or doctorate (Máster, Doctorado)",
    "no_consta": "The text does not say",
}


def preguntas_oferta():
    return {"nivel": choice("What is the lowest qualification level that `oferta.titulacion` accepts for the job?", NIVELES),
            "experiencia": noul("Does `oferta.requisitos` make previous work experience a mandatory requirement to apply (not just a merit that adds points)?")}


# 3.7: las ofertas de empleo público del SAE (estado: {"oferta": {"puesto", "ocupacion", "texto"}}): además, quién contrata
ENTIDADES = {
    "ayuntamiento": "A town council or a municipal body (Ayuntamiento, patronato municipal, mancomunidad)",
    "diputacion": "A provincial council (Diputación Provincial)",
    "junta": "The regional government of Andalusia or its agencies (Junta de Andalucía, consejería, SAS, SAE)",
    "estado": "The Spanish central government or its agencies",
    "empresa_publica": "A public company, foundation or consortium",
    "universidad": "A public university",
    "otra": "Another employer, or the text does not say",
}


def preguntas_oferta_sae():
    return {"nivel": choice("What is the lowest qualification level that the job described in `oferta` requires?", NIVELES),
            "experiencia": noul("Does `oferta` make previous work experience a mandatory requirement (not just a merit)?"),
            "entidad": choice("Who is the employer offering the job described in `oferta`?", ENTIDADES)}


# ------------------------------------------------------------------ 10. Agenda: ¿dos actividades son la misma?
def preguntas_mismo_evento():
    return {"mismo": noul("Do `a` and `b` (two entries of a town's agenda for the same day) describe the same event?",
                          si="The same event written differently", no="Two different events")}


# ------------------------------------------------------------------ 11. Sorteos: cómo se participa (una etiqueta de una lista fija)
PARTICIPA = {
    "seguir_mencionar": "Follow the account and like, comment, tag or mention friends on the post",
    "compra": "Buy something (in the shop or online) to get an entry",
    "presencial": "Go to the shop, stand or event in person",
    "formulario": "Fill in a form, register on a website or send a message",
    "otro": "Something else, or the text does not say",
}


def preguntas_participa():
    return {"participa": choice("How do people enter the giveaway described in `sorteo`?", PARTICIPA)}


# ------------------------------------------------------------------ 12. Buzón de capturas: ¿lo que se va a apuntar está en el texto?
# estado: {"texto": lo que dice la captura, transcrito}; una pregunta por dato
CAMPOS_CAPTURA = {
    "cuenta": "the account that publishes it is {v}", "premio": "the prize is {v}", "lugar": "it is in or for {v}",
    "hasta": "it ends (or the winner is drawn) on {v}", "fecha": "the event takes place on {v}", "horario": "the time is {v}",
    "titulo": "it is about: {v}",
}


TIPOS_CAPTURA = {
    "sorteo": "A giveaway or prize draw (sorteo, concurso, regalamos)",
    "corte": "A planned or ongoing cut of water, electricity or a road (corte, interrupción del suministro, calle cortada)",
    "actividad": "A public activity or event on a given day (concert, fair, festivity, sports event, talk, market, exhibition)",
    "colecta": "A blood donation drive (donación de sangre, colecta, Centro de Transfusión)",
    "otro": "Anything else",
}


def preguntas_captura(datos, tipo=None):
    """datos: {campo: valor}; cada uno, una pregunta «¿lo dice el texto?». Con tipo (3.7), además «¿qué es?» (TIPOS_CAPTURA)."""
    q = {c: noul(f"Does `texto` (the transcription of a social media post) say that " + CAMPOS_CAPTURA.get(c, c + " is {v}").format(v=v) + "?",
                 si="The text states it (same meaning, maybe other words or date format)", no="The text does not say it, or says something else")
         for c, v in datos.items()}
    if tipo: q["_tipo"] = choice("What does `texto` (the transcription of a social media post) announce?", TIPOS_CAPTURA)
    return q


# ------------------------------------------------------------------ 13. Revisión de fuentes: ¿el dato sigue en la página?
def preguntas_pagina():
    return {"sigue": noul("The app reads `fuente` from this web page and the automatic check failed with `fallo`. Does `pagina` still contain "
                          "that kind of current information, perhaps in a different format?")}
