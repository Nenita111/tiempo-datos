"""Pruebas de polen.py con las tramas reales de polenes.com (SEAIC, estación de Almería) del 7 nov 2026 (prueba_polen_20261107.json)."""
import datetime as dt, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polen

FIJO = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_polen_20261107.json"), encoding="utf-8"))
HOY = dt.date(2026, 11, 7)


class Polen(unittest.TestCase):
    def setUp(self):
        self.f = polen.filas(FIJO["tramas"])

    def test_filas(self):
        self.assertEqual((min(self.f), max(self.f)), ("2026-03-01", "2026-10-13"))
        self.assertEqual(self.f["2026-05-13"][12], 255)       # el olivo, en lo más alto del año
        self.assertEqual(self.f["2026-05-15"][9], 80)         # las gramíneas

    def test_resumen(self):
        r = polen.resumen(self.f, HOY)
        self.assertEqual(r["dia"], "2026-10-13")              # el último que ha subido la red (con semanas de retraso)
        self.assertEqual([(t["nombre"], t["valor"]) for t in r["tipos"]], [("Alternaria (hongo)", 1), ("Palmeras", 1)])
        self.assertEqual(r["semana"][0], {"id": 9, "nombre": "Gramíneas", "valor": 6, "nivel": "bajo"})
        self.assertEqual(r["meses"][0], "2025-11"); self.assertEqual(r["meses"][-1], "2026-10")
        c = {x["nombre"]: x for x in r["calendario"]}
        self.assertEqual(c["Olivo"]["max"][6], 255); self.assertEqual(c["Olivo"]["niveles"][6], "alto")
        self.assertEqual(c["Gramíneas"]["niveles"][6:8], ["alto", "moderado"])
        self.assertIsNone(c["Pino"]["niveles"])
        self.assertEqual(r["calendario"][0]["nombre"], "Amarantáceas (salsola)")   # 34 con alto en 20: el que más pasa de su corte

    def test_niveles(self):
        self.assertEqual([polen.nivel(12, v) for v in (99, 100, 200)], ["bajo", "moderado", "alto"])
        self.assertIsNone(polen.nivel(2, 500))                # la web no da cortes para Alternaria


if __name__ == "__main__":
    unittest.main()
