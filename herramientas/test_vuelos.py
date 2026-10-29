import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import vuelos

M = os.path.join(os.path.dirname(__file__), "muestras")


class Vuelos(unittest.TestCase):
    def test_de_la_sesion(self):
        """La respuesta real de Kiwi (Almería, 29 oct) tal como queda en el registro de la sesión: dentro de un resultado de herramienta."""
        k = json.load(open(os.path.join(M, "kiwi_LEI_20261029.json"), encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "p"))
            linea = {"type": "user", "message": {"content": [{"type": "tool_result", "content": [{"type": "text", "text": json.dumps(k)}]}]}}
            viejo = dict(k, itineraries=k["itineraries"][:1])       # una búsqueda anterior del mismo aeropuerto: manda la última
            with open(os.path.join(d, "p", "s.jsonl"), "w") as f:
                f.write(json.dumps({"x": json.dumps(viejo)}) + "\n" + json.dumps(linea) + "\n" + '{"otra": "cosa con itineraries"}\n')
            r = vuelos.de_la_sesion(raiz=d)
        self.assertEqual(list(r), ["LEI"]); self.assertEqual(len(r["LEI"]), 6)
        x = vuelos.actualizar({}, r, "2026-10-29", "prueba")
        v = x["aeropuertos"][0]["vuelos"][0]
        self.assertEqual((v["destino"], v["ida"], v["vuelta"], v["precio"], v["compania"]), ("Bucarest", "2026-11-11", "2026-11-13", 97, "Wizz Air"))
        self.assertEqual(x["vuelos"][0]["precio"], "97 €")

    def test_nada_en_la_sesion(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(vuelos.de_la_sesion(raiz=d), {})


if __name__ == "__main__":
    unittest.main()
