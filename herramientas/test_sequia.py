import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import sequia

M = os.path.join(os.path.dirname(__file__), "muestras")


class Sequia(unittest.TestCase):
    """Texto (pdftotext -layout, páginas 1 a 10) del informe real de escasez y sequía de septiembre de 2026 (SAIH Hidrosur, Junta de
    Andalucía), descargado el 28 de octubre de 2026."""

    def setUp(self):
        with open(os.path.join(M, "sequia_sep2026_p1-10.txt"), encoding="utf-8") as f: self.t = f.read()

    def test_informe(self):
        o = sequia.informe(self.t)
        self.assertEqual(o["mes"], "2026-09")
        self.assertEqual(o["embalses"], {"capacidad": 1144.0, "volumen": 753.0, "pct": 65.8, "volumenAnterior": 790.0, "pctAnterior": 69.0,
                                         "fecha": "2026-09-30", "fechaAnterior": "2026-08-31"})
        e = {u["codigo"]: u for u in o["escasez"]}
        s = {u["codigo"]: u for u in o["sequia"]}
        self.assertEqual(len(e), 20); self.assertEqual(len(s), 16)
        self.assertEqual(e["UTE 14"], {"codigo": "UTE 14", "nombre": "Campo de Dalías", "indice": 0.71, "estado": "Normalidad"})
        self.assertEqual(e["UTE 15"]["nombre"], "Cabecera río Grande de Adra")
        self.assertEqual(e["UTE 03"]["estado"], "Prealerta")   # «Prealerta (¹)»: la nota fuera
        self.assertIsNone(e["UTE 18"]["estado"])               # Níjar: el informe no da escenario (solo el índice, 0,39)
        self.assertEqual(e["UTE 04"]["nombre"], "Cordillera Penibética entre las cuencas Guadalhorce y Guadiaro")   # en dos líneas
        self.assertEqual(s["UTS 12"], {"codigo": "UTS 12", "nombre": "Cuenca del río Adra y acuífero del Campo de Dalías", "indice": 0.69, "estado": "Ausencia"})
        self.assertEqual(s["UTS 03"]["indice"], 0.58)           # el índice, en la línea de debajo de la del código
        self.assertEqual(s["UTS 11"]["nombre"], "Cuencas vertientes al mar entre las desembocaduras de los ríos Guadalfeo y Adra")


if __name__ == "__main__":
    unittest.main()
