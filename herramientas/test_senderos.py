"""Pruebas de senderos.py con respuestas reales de la Junta de Andalucía del 7 nov 2026 (prueba_senderos_20261107.json, recortadas)."""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import senderos as S

F = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_senderos_20261107.json"), encoding="utf-8"))


class Senderos(unittest.TestCase):
    def setUp(self):
        self.ine = S.codigos()
        self.l = {s["id"]: s for s in S.senderos(F["senderos"], F["inicios"], {k: S.ficha(v) for k, v in F["fichas"].items()}, self.ine)}

    def test_fichas(self):
        f = S.ficha(F["fichas"]["116"])
        self.assertEqual((f["nombre"], f["municipios"], f["trazado"], f["metros"], f["duracion"], f["cerrado"]),
                         ("MONTERREY", ["Laujar De Andarax"], "circular", 9670, "4 horas", False))
        self.assertTrue(S.ficha(F["fichas"]["121"])["cerrado"])                     # Punta Entinas, cerrado temporalmente
        self.assertNotIn("nombre", S.ficha(F["fichas"]["949"]))                      # la página genérica

    def test_lista(self):
        # sin la Sulayr (279 km) ni el carril cicloturista
        self.assertEqual(set(self.l), {"116", "121", "949", "452", "442"})
        m = self.l["116"]
        self.assertEqual((m["nombre"], m["km"], m["dificultad"], m["ine"], m["tiempoDe"]), ("Monterrey", 9.7, "alta", "04057", "Laujar de Andarax"))
        self.assertEqual(self.l["121"]["tiempoDe"], "El Ejido"); self.assertTrue(self.l["121"]["cerrado"])
        self.assertEqual(self.l["121"]["adraKm"], 22)
        # el inicio, el de la capa de equipamientos (UTM 30): Monterrey sale de cerca de Laujar
        self.assertAlmostEqual(m["inicio"][0], 36.99, delta=0.05); self.assertAlmostEqual(m["inicio"][1], -2.89, delta=0.05)
        self.assertLess(sum(len(p) for p in m["traza"]), 120)

    def test_sin_ficha(self):
        # Trevélez - Siete Lagunas: la ficha no sale; el nombre, con su tilde, y el tiempo de Trevélez (lo nombra)
        t = self.l["949"]
        self.assertEqual((t["nombre"], t["tiempoDe"]), ("Trevélez - Siete Lagunas", "Trevélez"))
        # Río Bermejo: sin ficha ni municipio en el nombre: el del sendero más cercano (Pueblos del Poqueira, sin ficha aquí: ninguno)
        self.assertEqual(self.l["452"]["nombre"], "Río Bermejo"); self.assertNotIn("ine", self.l["452"])

    def test_simplificar(self):
        p = [[0, 0], [0.5, 0.0001], [1, 0], [1, 1]]
        self.assertEqual(S.simplificar(p), [[0, 0], [1, 0], [1, 1]])


if __name__ == "__main__":
    unittest.main()
