"""Tarea diaria, la parte que no hace falta buscar: quita lo pasado (cortes, agenda, colectas de sangre, sorteos), pone al día el
calendario del cielo, las plagas, los virus respiratorios y la sequía y revisa las fuentes de la app. Todo de una vez y con un
resumen de una línea, para que la tarea programada gaste pocos tokens (antes leía la salida de cada script).

  python3 -I herramientas/diario.py extras.json [--sin-revision]
  JEV_CACHE=/tmp/jev/cache.json python3 -I herramientas/diario.py extras.json      # Jev por Composio (composio_jev.py, antes en el sandbox)

Con Jev (jev.py): los titulares con cortes, y los que anuncian actividades o colectas en el pueblo como candidatos (titulares.py), la
receta según el tiempo (receta.py), las etiquetas del SAS y el plazo de sus convocatorias (sas.py), las de la AESAN, la AEMPS, Safety Gate,
las ofertas de la Junta y del SAE y la agenda, la agenda sin repetidos y cómo se participa en cada sorteo y sus requisitos (etiquetas.py),
las novedades de barco dragón de la Federación Andaluza de Piragüismo (fap.py) y los sorteos de la zona de sortea2.com ya filtrados
(sortea2.py); sin Jev, esos pasos no tocan nada (o solo lo exacto).

Imprime una línea JSON: {"pasos": {"cielo": "ok …", "sequia": "código 2: …", …}, "sortea2": [candidatos], "agenda_titulares": […],
"sangre_titulares": […], "agenda": N, "sangre": N,
"sorteos": N, "cortes": N, "jev": "N respuestas por Composio, M sin respuesta", "rotas": ["fuente: fallo", …]}. Sale con código 0 aunque falle un paso (lo dice el resumen; un paso que falla
deja lo que había). La revisión de fuentes deja su informe en revision.json (no se sube: está en .gitignore).
"""
import json, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASOS = [   # nombre, script, tiempo máximo (s); todos reciben extras.json
    ("cortes", "cortes.py", 60), ("agenda", "agenda.py", 60), ("sangre", "sangre.py", 60), ("sorteos", "sorteos.py --podar", 60),
    ("cielo", "cielo.py", 300), ("raif", "raif.py", 300), ("respiratorias", "respiratorias.py", 300), ("sequia", "sequia.py", 900),
    # con Jev (jev.py); sin él no tocan nada
    ("titulares", "titulares.py", 300), ("receta", "receta.py", 120), ("sas", "sas.py", 600), ("etiquetas", "etiquetas.py", 900),
    ("fap", "fap.py", 300),
]
# el sandbox de Composio (composio_jev.py) repite estos, en este orden, para que Jev vea lo mismo: los que quitan lo pasado (cambian lo que
# ven las etiquetas) y los que preguntan a Jev; los demás no le tocan y no se repiten
PREVIOS, CON_JEV = ("cortes", "agenda", "sangre", "sorteos"), ("titulares", "receta", "sas", "etiquetas", "fap")


def correr(args, tiempo):
    try:
        r = subprocess.run([sys.executable, "-I", *args], cwd=RAIZ, capture_output=True, text=True, timeout=tiempo)
    except subprocess.TimeoutExpired:
        return None, f"no acabó en {tiempo} s"
    lineas = [l for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()]
    return r.returncode, (lineas[-1] if lineas else "")


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    extras = os.path.abspath(sys.argv[1]); revisar = "--sin-revision" not in sys.argv
    pasos, titulares = {}, {}
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
        ultima = ultima[:240]
        if cod == 0 and not ultima.startswith("{"): ultima = ""     # «N cortes en …»: el número ya va en el resumen
        pasos[nombre] = ("ok" if cod == 0 else f"código {cod}" if cod is not None else "fallo") + (f": {ultima}" if ultima else "")
    # sorteos de la zona en sortea2.com, ya filtrados (con Jev, si lo hay): Claude solo mira estos
    try:
        r = subprocess.run([sys.executable, "-I", os.path.join(RAIZ, "herramientas", "sortea2.py")], cwd=RAIZ, capture_output=True, text=True, timeout=180)
        s2 = json.loads(r.stdout.strip().splitlines()[-1])
        pasos["sortea2"] = f"ok: {s2['vistos']} vistos, {len(s2['candidatos'])} candidatos ({s2['juez']})"
    except Exception as e:
        s2 = {"candidatos": []}; pasos["sortea2"] = f"fallo: {e}"[:240]
    x = json.load(open(extras, encoding="utf-8"))
    res = {"pasos": pasos, "sortea2": [{"enlace": c["enlace"], "pueblos": c["pueblos"], "texto": c["texto"][:400]} for c in s2["candidatos"]],
           "agenda_titulares": titulares.get("agenda", []), "sangre_titulares": titulares.get("colectas", []),
           "agenda": len(x.get("agenda") or []), "sangre": len((x.get("sangre") or {}).get("colectas") or []),
           "sorteos": len(x.get("sorteos") or []), "cortes": len(x.get("cortes") or [])}
    if cache:
        try: n = len(json.load(open(cache, encoding="utf-8")))
        except (OSError, ValueError): n = 0
        m = len(set(open(faltan).read().split()))
        res["jev"] = f"{n} respuestas por Composio, {m} sin respuesta" + (" (¿falló el sandbox?)" if not n else "")
    elif not os.environ.get("TYPESAFE_API_KEY", "").strip():
        res["jev"] = "sin Jev: falta la caché de Composio (JEV_CACHE)"
    if revisar:
        inf = os.path.join(RAIZ, "revision.json")
        cod, ultima = correr([os.path.join(RAIZ, "herramientas", "revisar_fuentes.py"), "--json", inf], 900)
        try:
            f = json.load(open(inf, encoding="utf-8"))["fuentes"]
            res["rotas"] = [f"{y['fuente']}: {y['detalle']}"[:200] for y in f if y["estado"] == "ROTA"]
            res["fuentes"] = f"{sum(y['estado'] != 'ROTA' for y in f)}/{len(f)} bien"
            res["faltan_claves"] = [y["detalle"] for y in f if "falta la variable" in y.get("detalle", "")]   # ESIOS: la pone Isa en el entorno (Jev va por Composio)
        except (OSError, ValueError, KeyError):
            res["rotas"] = [f"revisar_fuentes.py no acabó ({ultima or cod})"]
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
