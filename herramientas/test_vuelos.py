import datetime as dt, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import comun, vuelos

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
        x = vuelos.actualizar({"vuelos": [{"destino": "PRUEBA"}], "vuelosOrigen": "Almería", "vuelosFecha": "Buscado el 28/10", "cortes": []}, r, "2026-10-29", "prueba")
        v = x["aeropuertos"][0]["vuelos"][0]
        self.assertEqual((v["destino"], v["ida"], v["vuelta"], v["precio"], v["compania"]), ("Bucarest", "2026-11-11", "2026-11-13", 97, "Wizz Air"))
        # los campos antiguos (lo de Almería repetido con otro formato) se quitan; lo demás, ni se toca
        self.assertEqual(sorted(x), ["actualizado", "aeropuertos", "antelacionMinimaDias", "cortes", "vuelosBuscado", "vuelosBusqueda"])

    def test_aviso_de_vuelo_barato(self):
        """Avisa solo con historia bastante y un 10 % menos que lo más barato de los 14 días de antes; cada día apunta su mínimo."""
        d = lambda n: dt.date(2026, 11, n)
        x = lambda precio: {"aeropuertos": [{"origen": "Málaga", "codigo": "AGP", "vuelos": [
            {"destino": "Oporto", "ida": "2026-12-14", "vuelta": "2026-12-19", "precio": precio + 20},
            {"destino": "Ibiza", "ida": "2026-12-12", "vuelta": "2026-12-14", "precio": precio, "enlace": "https://kiwi.com/u/PRUEBA"}]},
            {"origen": "Murcia", "codigo": "RMU", "vuelos": []}]}
        with tempfile.TemporaryDirectory() as t:
            ruta = os.path.join(t, "extras.json")
            for n in range(1, 7): self.assertEqual(vuelos.baratos(ruta, x(40), d(n)), [])       # 6 días a 40 €: aún no hay historia bastante
            self.assertEqual(vuelos.baratos(ruta, x(30), d(7)), [])                              # el 7.º día solo hay 6 de antes
            self.assertEqual(vuelos.baratos(ruta, x(28), d(8)), [])                              # 28 no es un 10 % menos que 30
            self.assertEqual(vuelos.baratos(ruta, x(25), d(9)),
                             ["✈️ Vuelo barato desde Málaga: Ibiza, del 12 dic al 14 dic, 25 € (lo más barato en 14 días era 28 €): https://kiwi.com/u/PRUEBA"])
            self.assertEqual(vuelos.baratos(ruta, x(25), d(9)), vuelos.baratos(ruta, x(25), d(9)))  # repetir el mismo día no cambia la historia
            h = comun.leer(os.path.join(t, comun.ESTADO))["vuelosMin"]
            self.assertEqual(h["AGP"][-2:], [["2026-11-08", 28], ["2026-11-09", 25]]); self.assertEqual(len(h["AGP"]), 9); self.assertNotIn("RMU", h)
            self.assertEqual(vuelos.baratos(ruta, x(24), d(30)), [])                             # tras 3 semanas sin datos, sin 7 días recientes no avisa
            self.assertFalse(os.path.exists(ruta))                                              # extras.json ni se toca

    def test_nada_en_la_sesion(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(vuelos.de_la_sesion(raiz=d), {})


if __name__ == "__main__":
    unittest.main()
