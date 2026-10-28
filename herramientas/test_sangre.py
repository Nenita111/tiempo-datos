"""Pruebas de sangre.py (las colectas son de PRUEBA: fechas y lugares inventados para probar el programa)."""
import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sangre


class Pruebas(unittest.TestCase):
    def test_anadir_y_podar(self):
        x = {}
        sangre.anadir(x, "2026-11-17", "  Centro de Salud  de Adra ", "https://ejemplo.org/a?b=1", "PRUEBA", ["17:00-21:00", "9.30 a 13,30"])
        c = x["sangre"]["colectas"][0]
        self.assertEqual(c["lugar"], "Centro de Salud de Adra"); self.assertEqual(c["horas"], [["17:00", "21:00"], ["09:30", "13:30"]])
        self.assertEqual(c["enlace"], "https://ejemplo.org/a?b=1")      # solo se quita el «?…» de Instagram
        sangre.anadir(x, "2026-11-17", "Centro de Salud de Adra", "https://ejemplo.org/b", "PRUEBA", ["17:30-21:00"])
        self.assertEqual(len(x["sangre"]["colectas"]), 1)                # el mismo día y pueblo: se sustituye
        sangre.anadir(x, "2026-10-20", "Plaza", "https://ejemplo.org/c", "PRUEBA")
        sangre.podar(x, dt.date(2026, 10, 28))
        self.assertEqual([c["fecha"] for c in x["sangre"]["colectas"]], ["2026-11-17"])   # la del 20 ya pasó

    def test_sin_datos_no_se_apunta(self):
        for args in [("2026-11-17", "", "https://e.org", "F"), ("2026-11-17", "Lugar", "", "F"), ("2026-11-17", "Lugar", "https://e.org", " ")]:
            with self.assertRaises(ValueError): sangre.anadir({}, *args)
        with self.assertRaises(ValueError): sangre.anadir({}, "2026-11-17", "L", "https://e.org", "F", ["21:00-17:00"])
        with self.assertRaises(ValueError): sangre.anadir({}, "17/11/2026", "L", "https://e.org", "F")


if __name__ == "__main__":
    unittest.main()
