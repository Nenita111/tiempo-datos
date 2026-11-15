"""Tarea diaria, la parte que no hace falta buscar: quita lo pasado (cortes, agenda, colectas de sangre, sorteos), pone al día el
calendario del cielo, las plagas, los virus respiratorios, los cruceros del puerto de Almería (4.16), las inspecciones de las playas (4.26), la agenda cultural de la Junta (4.27), las aguas subterráneas (4.28), las ayudas abiertas, los cursos gratis, el polen, los planes gratis o al aire libre (4.31), las ofertas de provisión temporal del SAS de la zona (4.38), las estafas en circulación (avisos del INCIBE, 15 nov 2026) y la sequía y revisa las fuentes de la app. Todo de una vez y con un
resumen de una línea, para que la tarea programada gaste pocos tokens (antes leía la salida de cada script).

  python3 -I herramientas/diario.py extras.json [--sin-revision]
  JEV_CACHE=/tmp/jev/cache.json python3 -I herramientas/diario.py extras.json      # Jev por Composio (composio_jev.py, antes en el sandbox)

Con Jev (jev.py): los titulares con cortes, y los que anuncian actividades o colectas en el pueblo como candidatos (titulares.py), la
receta según el tiempo (receta.py), las etiquetas del SAS y el plazo de sus convocatorias (sas.py), las de la AESAN, la AEMPS, Safety Gate,
las ofertas de la Junta y del SAE y la agenda, la agenda sin repetidos y cómo se participa en cada sorteo y sus requisitos (etiquetas.py),
las novedades de barco dragón de la Federación Andaluza de Piragüismo (fap.py) y los sorteos de la zona de sortea2.com ya filtrados
(sortea2.py); sin Jev, esos pasos no tocan nada (o solo lo exacto).

Imprime una línea JSON: {"bien": N (los pasos que fueron bien, sin contarlos uno a uno), "pasos": {solo los que fallaron o fueron sin
Jev: "sequia": "código 2: …", …}, "sortea2": [candidatos], "agenda_titulares": […],
"sangre_titulares": […], "agenda": N, "sangre": N,
"sorteos": N, "cortes": N, "toca": {"vuelos": …, "web": …, "puente": {"ida": […], "vuelta": […]} (solo si toca)}, "subir": ["extras.json", "estado_diario.json"] (lo que se sube si ha cambiado),
"jev": "N respuestas por Composio, M sin respuesta", "rotas": ["fuente: fallo", …], "avisar": ["⚠️ Tele: «vuelos» falla desde el 11 nov: …", …]
(solo si hay algo que lleva 2 días o más fallando: la tarea lo manda al móvil; se repite cada 7 días mientras siga)}.
«toca» (4.10, menos tokens): los vuelos, una vez al día (4.13, lo pidió Isa: antes, un día sí y otro no); las búsquedas web de sorteos,
agenda y colectas, los lunes y los jueves (los candidatos de sortea2 y de los titulares, todos los días); los vuelos del próximo
puente (puente.py), una vez a la semana, con las fechas de ida y de vuelta ya escritas para Kiwi. Sale con código 0 aunque falle un paso (lo dice el resumen; un paso que falla
deja lo que había). La revisión de fuentes deja su informe en revision.json (no se sube: está en .gitignore).
"""
import datetime as dt, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # comun.py, al lado (con -I no se mira la carpeta del script)
import comun, puente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASOS = [   # nombre, script, tiempo máximo (s); todos reciben extras.json
    ("cortes", "cortes.py", 60), ("agenda", "agenda.py", 60), ("sangre", "sangre.py", 60), ("sorteos", "sorteos.py --podar", 60),
    # con Jev (jev.py); sin él no tocan nada. Justo después de los que quitan lo pasado, como en el sandbox (3.9: antes iban detrás de la
    # sequía, que puede tardar 15 minutos, y lo que cambiaba entretanto ya no estaba en la caché de Composio)
    ("titulares", "titulares.py", 300), ("receta", "receta.py", 120), ("sas", "sas.py", 600), ("etiquetas", "etiquetas.py", 900),
    ("fap", "fap.py", 300),
    ("cielo", "cielo.py", 300), ("raif", "raif.py", 300), ("respiratorias", "respiratorias.py", 300), ("cruceros", "cruceros.py", 120), ("playas", "playas.py", 180), ("agendaJunta", "agenda_junta.py", 180), ("acuiferos", "acuiferos.py", 900),
    # 4.31: ayudas abiertas (BDNS), cursos gratis (Junta), polen (SEAIC) y planes gratis o al aire libre (los senderos, quitados en 4.35)
    ("ayudas", "ayudas.py", 900), ("cursos", "cursos.py", 180), ("polen", "polen.py", 180), ("actividades", "actividades.py", 240),
    # 4.38: las ofertas de provisión temporal del SAS de la zona (unas 20 páginas de su web, con pausa: 2 o 3 minutos)
    ("sasOfertas", "sas_ofertas.py", 600),
    # 4.41: los próximos campeonatos internacionales de barco dragón (IDBF y Paddle Europe; solo mira lunes y jueves)
    ("dragon", "dragon.py", 120),
    # 15 nov 2026: las estafas en circulación (avisos del INCIBE para la ciudadanía, de su RSS)
    ("estafas", "incibe.py", 120),
    # 15 nov 2026: el próximo puente (calendario laboral de la Junta); sus vuelos los busca la tarea una vez a la semana («toca».puente)
    ("puente", "puente.py", 120),
    ("sequia", "sequia.py", 900),
]
# el sandbox de Composio (composio_jev.py) repite estos, en este orden, para que Jev vea lo mismo: los que quitan lo pasado (cambian lo que
# ven las etiquetas) y los que preguntan a Jev; los demás no le tocan y no se repiten
# lo que hay que contar de un paso que acabó bien: que fue sin Jev o que algo falló
AVISA = re.compile(r'sin Jev|"fallos": \[\s*"|"error|faltan?\b')
PREVIOS, CON_JEV = ("cortes", "agenda", "sangre", "sorteos"), ("titulares", "receta", "sas", "etiquetas", "fap")


def correr(args, tiempo):
    try:
        r = subprocess.run([sys.executable, "-I", *args], cwd=RAIZ, capture_output=True, text=True, timeout=tiempo)
    except subprocess.TimeoutExpired:
        return None, f"no acabó en {tiempo} s"
    lineas = [l for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()]
    return r.returncode, (lineas[-1] if lineas else "")


def toca(x, hoy=None):
    """Lo que la tarea tiene que buscar hoy: los vuelos (4 búsquedas de Kiwi), si aún no se han buscado hoy; las búsquedas web, los
    lunes y los jueves; y, una vez a la semana, los vuelos del próximo puente («puente»: las fechas de ida y de vuelta para Kiwi)."""
    hoy = hoy or comun.hoy()
    t = {"vuelos": (x.get("vuelosBuscado") or "") < hoy.isoformat(), "web": hoy.weekday() in (0, 3)}
    p = puente.toca(x, hoy)
    if p: t["puente"] = p
    return t


AVISO_DIAS, AVISO_CADA = 2, 7        # se avisa al móvil de lo que lleva 2 días fallando, y luego cada 7


def dia_corto(d):
    return f"{d.day} {comun.MESES[d.month - 1][:3]}"


def parado(extras, problemas, dia):
    """Lo que hay que avisar al móvil: lo que lleva AVISO_DIAS días o más fallando (15 nov 2026, lo pidió Isa: los vuelos estuvieron cinco
    días sin actualizarse y solo lo decía el informe de la tarea). problemas: {nombre: (qué pasa hoy, desde qué día si lo dicen los datos o
    None)}. Desde cuándo falla cada cosa se recuerda en estado_diario.json («fallos»); lo que hoy va bien se olvida. Se avisa el día que
    cumple AVISO_DIAS y luego cada AVISO_CADA: una línea por cosa."""
    antes = comun.recuerdo(extras, {}, "fallos") or {}
    ahora, avisos = {}, []
    for nombre, (texto, desde) in problemas.items():
        desde = desde or (antes.get(nombre) or {}).get("desde") or dia.isoformat()
        ahora[nombre] = {"desde": desde}
        dias = (dia - dt.date.fromisoformat(desde)).days
        if dias >= AVISO_DIAS and (dias - AVISO_DIAS) % AVISO_CADA == 0:
            avisos.append(f"⚠️ Tele: «{nombre}» falla desde el {dia_corto(dt.date.fromisoformat(desde))}" + (f": {texto}" if texto else ""))
    comun.recordar(extras, {}, "fallos", ahora)
    return avisos


def problemas(x, pasos, codigos, res, dia):
    """Lo que hoy no ha ido: los pasos que han fallado (no los que solo fueron sin Jev), Jev si no estaba, las fuentes rotas de la revisión y
    los vuelos si ayer no se buscaron (hoy aún no toca: se buscan después de este script)."""
    p = {n: (t[:120], None) for n, t in pasos.items() if codigos.get(n, 0) != 0}
    if re.search(r"sin Jev|¿falló el sandbox", res.get("jev", "")): p["Jev"] = (res["jev"][:120], None)
    for r in res.get("rotas") or []:
        n, _, detalle = r.partition(": ")
        if n != "extras": p["fuente " + n if detalle else "revisión de fuentes"] = ((detalle or n)[:120], None)   # «extras» es lo de los vuelos
    b = x.get("vuelosBuscado")
    if b and (dia - dt.date.fromisoformat(b)).days >= 2:
        p["vuelos"] = (f"sin búsqueda de Kiwi desde el {dia_corto(dt.date.fromisoformat(b))} (¿el conector?)", (dt.date.fromisoformat(b) + dt.timedelta(days=1)).isoformat())
    return p


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    extras = os.path.abspath(sys.argv[1]); revisar = "--sin-revision" not in sys.argv
    codigos = {}
    pasos, titulares, bien = {}, {}, []
    cache = os.environ.get("JEV_CACHE", "").strip()
    if cache:                                    # cada script apunta ahí las preguntas que no estaban en la caché
        faltan = os.environ["JEV_FALTAN"] = cache + ".faltan"
        open(faltan, "w").close()
    for nombre, script, tiempo in PASOS:
        s, *opc = script.split()
        cod, ultima = correr([os.path.join(RAIZ, "herramientas", s), extras, *opc], tiempo)
        if nombre == "titulares" and cod == 0:
            try: titulares = json.loads(ultima); ultima = json.dumps({k: v for k, v in titulares.items() if k not in ("agenda", "colectas")}, ensure_ascii=False)
            except ValueError: pass
        ultima = ultima[:240]; codigos[nombre] = cod
        if cod == 0 and not AVISA.search(ultima): bien.append(nombre); continue      # 3.9: lo que fue bien no se cuenta (menos tokens)
        pasos[nombre] = ("ok" if cod == 0 else f"código {cod}" if cod is not None else "fallo") + (f": {ultima}" if ultima else "")
    # sorteos de la zona en sortea2.com, ya filtrados (con Jev, si lo hay): Claude solo mira estos
    try:
        r = subprocess.run([sys.executable, "-I", os.path.join(RAIZ, "herramientas", "sortea2.py")], cwd=RAIZ, capture_output=True, text=True, timeout=180)
        s2 = json.loads(r.stdout.strip().splitlines()[-1])
        if s2["juez"] == "Jev": bien.append("sortea2")
        else: pasos["sortea2"] = f"ok: {s2['vistos']} vistos, {len(s2['candidatos'])} candidatos ({s2['juez']})"
    except Exception as e:
        s2 = {"candidatos": []}; pasos["sortea2"] = f"fallo: {e}"[:240]; codigos["sortea2"] = 1
    x = comun.leer(extras)
    res = {"bien": len(bien), "pasos": pasos, "sortea2": [{"enlace": c["enlace"], "pueblos": c["pueblos"], "texto": c["texto"][:400]} for c in s2["candidatos"]],
           "agenda_titulares": titulares.get("agenda", []), "sangre_titulares": titulares.get("colectas", []),
           "agenda": len(x.get("agenda") or []), "sangre": len((x.get("sangre") or {}).get("colectas") or []),
           "sorteos": len(x.get("sorteos") or []), "cortes": len(x.get("cortes") or []), "toca": toca(x),
           "subir": ["extras.json", comun.ESTADO]}          # lo que hay que subir si ha cambiado: los datos y lo que recuerdan los scripts
    if cache:
        try: n = len(comun.leer(cache))
        except (OSError, ValueError): n = 0
        m = len(set(open(faltan).read().split()))
        res["jev"] = f"{n} respuestas por Composio, {m} sin respuesta" + (" (¿falló el sandbox?)" if not n else "")
    elif not os.environ.get("TYPESAFE_API_KEY", "").strip():
        res["jev"] = "sin Jev: falta la caché de Composio (JEV_CACHE)"
    if revisar:
        inf = os.path.join(RAIZ, "revision.json")
        cod, ultima = correr([os.path.join(RAIZ, "herramientas", "revisar_fuentes.py"), "--json", inf], 900)
        try:
            f = comun.leer(inf)["fuentes"]
            res["rotas"] = [f"{y['fuente']}: {y['detalle']}"[:200] for y in f if y["estado"] == "ROTA"]
            res["fuentes"] = f"{sum(y['estado'] != 'ROTA' for y in f)}/{len(f)} bien"
            res["faltan_claves"] = [y["detalle"] for y in f if "falta la variable" in y.get("detalle", "")]   # ESIOS: la pone Isa en el entorno (Jev va por Composio)
        except (OSError, ValueError, KeyError):
            res["rotas"] = [f"revisar_fuentes.py no acabó ({ultima or cod})"]
    avisar = comun.recoger_avisos(extras) + parado(extras, problemas(x, pasos, codigos, res, comun.hoy()), comun.hoy())
    if avisar: res["avisar"] = avisar            # al móvil: lo que han dejado los scripts (estafas nuevas…) y lo que lleva días fallando
    comun.decir(res)


if __name__ == "__main__":
    main()
