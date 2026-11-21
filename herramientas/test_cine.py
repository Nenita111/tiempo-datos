import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cine

MUESTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras", "cine_sensacine.html")


class Cine(unittest.TestCase):
    def test_sesiones_de_hoy(self):
        P = cine.peliculas(open(MUESTRA, encoding="utf-8").read(), "2026-11-21")
        self.assertEqual(P[0]["titulo"], "Los Juegos del Hambre: Amanecer en la cosecha")
        self.assertIn("16:00", P[0]["horas"])
        self.assertEqual(len(P), 2)

    def test_otro_dia_nada(self):
        self.assertEqual(cine.peliculas(open(MUESTRA, encoding="utf-8").read(), "2026-11-30"), [])


if __name__ == "__main__":
    unittest.main()
