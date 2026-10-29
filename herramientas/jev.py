"""Jev (TypeSafe System One) para las tareas de la tele: un cliente sin dependencias y todas las preguntas en un solo sitio
(es lo que hay que revisar y ajustar: las preguntas, los umbrales y lo que se le enseña).

Jev no escribe nada: contesta preguntas cerradas (sí/no con su probabilidad, una opción de una lista, un nivel) sobre lo que se le da.
Aquí decide cosas que una regla de texto hace mal (si un titular anuncia un corte, si un sorteo es de un comercio de la zona, qué
receta pega con el tiempo de hoy, de qué tipo es una disposición del SAS); las fechas, las cuentas y lo que se puede comprobar con
exactitud se hacen en el código. Las preguntas van en inglés (Jev rinde mejor) y los textos, tal cual, en español.

La clave: en la nube, «network secret» del entorno (sitio api.typesafe.ai, cabecera «Authorization: Bearer …»), que pone el proxy
sin que la sesión la vea; o la variable TYPESAFE_API_KEY (en un ordenador). Nunca en el repositorio ni en la salida. Sin clave
(401/403) o sin red: SinJev, y cada script sigue como antes de Jev (reglas de texto o nada).
"""
import json, os, time, urllib.error, urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MODELO = "jev-1.13.0"        # fijado: los umbrales se ajustan contra esta versión


class SinJev(Exception):
    """No se puede preguntar a Jev (sin clave, sin red o caído): se sigue sin él."""


def _pedir(cuerpo, timeout):
    cab = {"Content-Type": "application/json", "User-Agent": "TiempoYRadar/1.0 (tareas de la tele)"}
    clave = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if clave: cab["Authorization"] = f"Bearer {clave}"       # si no, la pone el proxy (network secret)
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


def preguntas_sas():
    return {"tipo": choice("What does `disposicion.texto` (the title of a Spanish official gazette entry about the Andalusian Health Service) do?", TIPOS_SAS),
            "provincia": choice("Which place does `disposicion.texto` concern?", PROV_SAS)}
