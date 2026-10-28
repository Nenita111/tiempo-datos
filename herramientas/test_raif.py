import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import raif

M = os.path.join(os.path.dirname(__file__), "muestras")


def leer(n):
    with open(os.path.join(M, n), encoding="utf-8") as f: return f.read()


class Raif(unittest.TestCase):
    """Página de la provincia y texto (pdftotext -layout) de los boletines reales de la RAIF descargados el 28 de octubre de 2026."""

    def test_enlaces(self):
        e = raif.enlaces(leer("raif_almeria_20261028.html"))
        self.assertTrue(e["Tomate"].endswith("/Informe_EspecialInteres_Tomate.pdf"))
        self.assertTrue(e["Calabacín"].endswith("/Informe_EspecialInteres_Calabacin.pdf"))
        self.assertTrue(all(c in e for c in raif.CULTIVOS))

    def test_boletines(self):
        self.assertEqual(raif.boletin(leer("raif_Tomate_20261019.txt")), ("2026-10-19", "2026-10-23", "Mosca blanca y Trips"))
        self.assertEqual(raif.boletin(leer("raif_Pimiento_20261019.txt")), ("2026-10-19", "2026-10-23", "Mosca blanca, Trips"))
        # en el de berenjena la lista queda en la línea de encima de «Agentes más destacados:»
        self.assertEqual(raif.boletin(leer("raif_Berenjena_20261019.txt")), ("2026-10-19", "2026-10-23", "Mosca blanca, Trips"))
        # los cultivos fuera de temporada siguen con el último boletín (la tele solo enseña los de las dos últimas semanas)
        self.assertEqual(raif.boletin(leer("raif_Calabacin_20261019.txt")), ("2026-02-09", "2026-02-13", "Mosca blanca, ToLCNDV"))
        self.assertEqual(raif.boletin(leer("raif_Sandia_20261019.txt"))[:2], ("2026-04-11", "2026-04-15"))


if __name__ == "__main__":
    unittest.main()
