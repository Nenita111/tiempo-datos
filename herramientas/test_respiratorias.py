import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import respiratorias as r

M = os.path.join(os.path.dirname(__file__), "muestras")


def leer(n):
    with open(os.path.join(M, n), encoding="utf-8") as f: return f.read()


class Respiratorias(unittest.TestCase):
    """Página de la temporada 2026-27 y las 4 primeras páginas (pdftotext) del informe real de la semana 42/2026."""

    def test_temporada(self):
        self.assertEqual(r.temporada(dt.date(2026, 10, 28)), "2627")
        self.assertEqual(r.temporada(dt.date(2027, 3, 1)), "2627")
        self.assertEqual(r.temporada(dt.date(2026, 9, 30)), "2526")

    def test_informes(self):
        l = r.informes(leer("iras_temporada2627_20261028.html"), r.BASE + "temporada2627.html")
        self.assertEqual([s for s, _, _ in l], ["42/2026", "41/2026", "40/2026"])
        self.assertTrue(l[0][2].startswith("https://www.juntadeandalucia.es/sites/default/files/inline-files/2026/10/"))
        self.assertEqual(r.fechas(l[0][1]), ("2026-10-12", "2026-10-18"))
        self.assertEqual(r.fechas(l[2][1]), ("2026-09-21", "2026-10-04"))   # «del 21 de septiembre al 4 de octubre»

    def test_resumen(self):
        o = r.resumen(leer("iras_sem202642_p1-4.txt"))
        self.assertEqual(o["semana"], "42/2026")
        self.assertEqual(o["iras"], {"tasa": 200.9, "previa": 240.0})
        self.assertEqual(o["gripal"], {"tasa": 1.8, "previa": 1.9})
        self.assertEqual(o["covid"], {"tasa": 2.9, "previa": 4.3})
        self.assertEqual(o["bronquiolitis"], {"tasa": 90.9, "previa": 103.9})
        self.assertEqual(o["irag"], {"tasa": 7.0, "previa": 5.9})
        self.assertEqual(o["positividad"]["gripe"], 15.4); self.assertEqual(o["positividad"]["covid"], 34.6); self.assertEqual(o["positividad"]["vrs"], 0.0)


if __name__ == "__main__":
    unittest.main()
