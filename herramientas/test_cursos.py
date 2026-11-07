"""Pruebas de cursos.py con tarjetas reales del buscador de cursos de la Junta del 7 nov 2026 (prueba_cursos_20261107.html, recortadas)."""
import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cursos

HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_cursos_20261107.html"), encoding="utf-8").read()
HOY = dt.date(2026, 11, 7)


class Cursos(unittest.TestCase):
    def setUp(self):
        t = cursos.tarjetas(HTML)
        self.pre, self.lin = cursos.leer([d for d in t if d.get("province")], [d for d in t if not d.get("province")], HOY)

    def test_presenciales(self):
        self.assertEqual([c["id"] for c in self.pre], ["410", "399", "769", "401"])   # por fin de solicitud
        c = self.pre[2]
        self.assertEqual((c["codigo"], c["nombre"], c["fin"], c["inicio"], c["horas"]), ("SSCE05", "Inglés C1", "2026-11-13", "2026-11-23", 240))
        self.assertEqual((c["municipio"], c["km"], c["para"], c["modalidad"], c["horario"]), ("Vícar", 35, "desempleadas", "presencial", "mañana"))
        self.assertEqual(c["enlace"], "https://www.juntadeandalucia.es/empleoformacionytrabajoautonomo/formacion/web/buscador-de-cursos/769")
        self.assertEqual(self.pre[1]["nombre"], "Manipulación de alimentos de alto riesgo"); self.assertEqual(self.pre[1]["km"], 19)

    def test_en_linea(self):
        # el /5 dice «en plazo» pero acabó el 23 jul: fuera; los convocados (se abren más adelante), dentro
        ids = [c["id"] for c in self.lin]
        self.assertNotIn("5", ids); self.assertEqual(ids[0], "2787"); self.assertIn("108", ids)
        self.assertTrue(next(c for c in self.lin if c["id"] == "108")["convocado"])
        self.assertEqual(self.lin[0]["para"], "ocupadas"); self.assertEqual(self.lin[0]["modalidad"], "en línea")

    def test_pasado(self):
        t = cursos.tarjetas(HTML)
        pre, _ = cursos.leer([d for d in t if d.get("province")], [], dt.date(2026, 11, 14))
        self.assertEqual([c["id"] for c in pre], ["401"])

    def test_nombres(self):
        self.assertEqual(cursos.nombre("IFCD97 - PROGRAMACIÓN PARA SOLUCIONES DE IOT Y SMART CITY APLICABLES EN ENTORNOS 5G"),
                         ("IFCD97", "Programación para soluciones de IOT y smart city aplicables en entornos 5G"))
        self.assertEqual(cursos.nombre("SSCE20 - SEGÚN EL ?MARCO DIGITAL?")[1], "Según el marco digital")


if __name__ == "__main__":
    unittest.main()
