"""Pruebas de acuiferos.py con filas reales del fichero de la REDIAM de 2024 (tres puntos de control: Las Albuferas, Puente del Río y Tarambana)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acuiferos

FIJO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_acuiferos_2024.csv")


class Acuiferos(unittest.TestCase):
    def setUp(self):
        with open(FIJO, encoding="utf-8", newline="") as f:
            self.p = {k: acuiferos.resumen(v) for k, v in acuiferos.leer(f).items()}

    def test_puntos_y_distancias(self):
        self.assertEqual(set(self.p), {"2144-3-0035", "CA0615001", "MD5267"})
        a = self.p["2144-3-0035"]
        self.assertEqual(a["nombre"], "Las Albuferas"); self.assertEqual(a["masa"], "ES060MSBT060-015")
        self.assertAlmostEqual(a["km"], 5.6, delta=0.1); self.assertAlmostEqual(a["lat"], 36.7573, delta=0.001)

    def test_ultimos_valores(self):
        a = self.p["2144-3-0035"]
        self.assertEqual(a["no3"], {"valor": 16.1, "texto": "16,1", "fecha": "2024-07-23"})
        self.assertEqual(a["ce"]["valor"], 466.0); self.assertEqual(a["no3Max"], 17.5)
        self.assertEqual(self.p["CA0615001"]["cl"]["valor"], 303.0)

    def test_detectado_sin_metales(self):
        # el glifosato, dos veces (0,48 y 0,96 µg/l); el zinc y los fluoruros (inorgánicos) no
        d = self.p["2144-3-0035"]["detectado"]
        self.assertEqual([(x["nombre"], x["max"], x["veces"]) for x in d], [("Glifosato", 0.96, 2)])
        self.assertEqual(self.p["CA0615001"]["detectado"], [])
        self.assertEqual(self.p["MD5267"]["nombre"], "Sondeo paraje tarambana")
        self.assertEqual([x["nombre"] for x in self.p["MD5267"]["detectado"]], ["Trifluralina"])


if __name__ == "__main__":
    unittest.main()
