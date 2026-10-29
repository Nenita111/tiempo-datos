"""Tarea diaria, la parte que no hace falta buscar: quita lo pasado (cortes, agenda, colectas de sangre, sorteos), pone al día el
calendario del cielo, las plagas, los virus respiratorios y la sequía y revisa las fuentes de la app. Todo de una vez y con un
resumen de una línea, para que la tarea programada gaste pocos tokens (antes leía la salida de cada script).

  python3 -I herramientas/diario.py extras.json [--sin-revision]

Con Jev (jev.py): los titulares con cortes (titulares.py), la receta según el tiempo (receta.py), las etiquetas del SAS (sas.py) y
los sorteos de la zona de sortea2.com ya filtrados (sortea2.py); sin Jev, esos pasos no tocan nada (o, sortea2, filtran solo por pueblo).

Imprime una línea JSON: {"pasos": {"cielo": "ok …", "sequia": "código 2: …", …}, "sortea2": [candidatos], "agenda": N, "sangre": N,
"sorteos": N, "cortes": N, "rotas": ["fuente: fallo", …]}. Sale con código 0 aunque falle un paso (lo dice el resumen; un paso que falla
deja lo que había). La revisión de fuentes deja su informe en revision.json (no se sube: está en .gitignore).
"""
import json, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASOS = [   # nombre, script, tiempo máximo (s); todos reciben extras.json
    ("cortes", "cortes.py", 60), ("agenda", "agenda.py", 60), ("sangre", "sangre.py", 60), ("sorteos", "sorteos.py --podar", 60),
    ("cielo", "cielo.py", 300), ("raif", "raif.py", 300), ("respiratorias", "respiratorias.py", 300), ("sequia", "sequia.py", 900),
    # con Jev (jev.py); sin él no tocan nada
    ("titulares", "titulares.py", 300), ("receta", "receta.py", 120), ("sas", "sas.py", 600),
]


def correr(args, tiempo):
    try:
        r = subprocess.run([sys.executable, "-I", *args], cwd=RAIZ, capture_output=True, text=True, timeout=tiempo)
    except subprocess.TimeoutExpired:
        return None, f"no acabó en {tiempo} s"
    lineas = [l for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()]
    return r.returncode, (lineas[-1] if lineas else "")[:240]


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    extras = os.path.abspath(sys.argv[1]); revisar = "--sin-revision" not in sys.argv
    pasos = {}
    for nombre, script, tiempo in PASOS:
        s, *opc = script.split()
        cod, ultima = correr([os.path.join(RAIZ, "herramientas", s), extras, *opc], tiempo)
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
           "agenda": len(x.get("agenda") or []), "sangre": len((x.get("sangre") or {}).get("colectas") or []),
           "sorteos": len(x.get("sorteos") or []), "cortes": len(x.get("cortes") or [])}
    if revisar:
        inf = os.path.join(RAIZ, "revision.json")
        cod, ultima = correr([os.path.join(RAIZ, "herramientas", "revisar_fuentes.py"), "--json", inf], 900)
        try:
            f = json.load(open(inf, encoding="utf-8"))["fuentes"]
            res["rotas"] = [f"{y['fuente']}: {y['detalle']}"[:200] for y in f if y["estado"] == "ROTA"]
            res["fuentes"] = f"{sum(y['estado'] != 'ROTA' for y in f)}/{len(f)} bien"
        except (OSError, ValueError, KeyError):
            res["rotas"] = [f"revisar_fuentes.py no acabó ({ultima or cod})"]
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
