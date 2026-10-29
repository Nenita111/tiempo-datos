"""Segunda mirada a lo que se va a apuntar de una captura del buzón (sorteos, cortes, agenda, colectas), con Jev.

Claude lee la captura y escribe lo que dice en un fichero de texto (tal cual, sin resumir). Antes de apuntar, este script pregunta a Jev,
dato por dato, si ese texto dice lo que se va a apuntar («¿dice que acaba el 2026-11-05 a las 23:59?»). Si alguno no cuadra, la captura
no se apunta y se queda para revisar. Sin Jev (sin clave o sin red) no bloquea nada: lo dice y sale con 0.

  python3 -I herramientas/comprobar_captura.py --texto /tmp/buzon/ID.txt --tipo sorteo --dato cuenta=@tienda --dato premio="Cesta" --dato hasta="5 de noviembre de 2026, 23:59"

Con --tipo (sorteo, corte, actividad o colecta), Jev dice además qué anuncia el texto; si ve otra cosa con seguridad, no cuadra «tipo».

Imprime una línea JSON {"ok": bool, "datos": {campo: probabilidad}, "no_cuadra": [campos], "juez": …}. Sale con 1 si algo no cuadra.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev

UMBRAL = 0.6        # por debajo, el dato no se ve en el texto: no se apunta


TIPO_SEGURO = 0.7    # 3.7: si Jev ve otra cosa (sorteo, corte, actividad, colecta) con esta seguridad, no cuadra el tipo


def comprobar(texto, datos, pedir=None, tipo=None):
    try: r, _ = jev.preguntar({"texto": texto[:6000]}, jev.preguntas_captura(datos, tipo), pedir=pedir)
    except (jev.SinJev, ValueError) as e: return {"ok": True, "datos": {}, "no_cuadra": [], "juez": f"sin Jev ({e}): no se ha comprobado"}
    p = {c: r[c]["noul"] for c in datos}
    mal = [c for c, v in p.items() if v < UMBRAL]
    res = {"datos": p, "juez": "Jev"}
    if tipo:
        t = r.get("_tipo") or {}
        res["tipo"] = t.get("choice")
        if t.get("choice") not in (tipo, None) and (t.get("confidence") or 0) >= TIPO_SEGURO: mal.append("tipo")
    return {"ok": not mal, **res, "no_cuadra": mal}


def main():
    a = argparse.ArgumentParser(); a.add_argument("--texto", required=True); a.add_argument("--dato", action="append", default=[])
    a.add_argument("--tipo", choices=sorted(set(jev.TIPOS_CAPTURA) - {"otro"}))
    o = a.parse_args()
    datos = dict(d.split("=", 1) for d in o.dato if "=" in d)
    if not datos: sys.exit("Falta algún --dato campo=valor")
    r = comprobar(open(o.texto, encoding="utf-8").read(), datos, tipo=o.tipo)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
