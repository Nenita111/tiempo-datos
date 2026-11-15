"""Un paso que se queda sin red lo dice en una línea JSON ({"error": …}), sale con código 1 y deja extras.json como estaba. PRUEBA: la red,
de mentira (siempre falla)."""
import contextlib, io, json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avisos_movil as A, comun, sas, titulares


def sin_red(*a, **k): raise OSError("sin red (PRUEBA)")


class SinRed(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        self.ruta = os.path.join(d, "extras.json")
        comun.guardar(self.ruta, {"cortes": [], "sas": {"fecha": "2026-11-14"}, "actualizado": "2026-11-14T06:12+01:00"})

    def correr(self, main, guion):
        argv = sys.argv; sys.argv = [guion, self.ruta]
        s = io.StringIO()
        try:
            with contextlib.redirect_stdout(s), self.assertRaises(SystemExit) as c: main()
        finally: sys.argv = argv
        lineas = s.getvalue().splitlines()
        self.assertEqual(c.exception.code, 1); self.assertEqual(len(lineas), 1)          # una línea: la que lee diario.py
        self.assertEqual(json.loads(lineas[0]), {"error": "sin red (PRUEBA)"})
        self.assertEqual(comun.leer(self.ruta)["actualizado"], "2026-11-14T06:12+01:00")   # extras.json, como estaba

    def test_titulares(self):
        orig = A.pedir; A.pedir = sin_red; self.addCleanup(setattr, A, "pedir", orig)
        self.correr(titulares.main, "titulares.py")

    def test_sas(self):
        orig = sas.pedir; sas.pedir = sin_red; self.addCleanup(setattr, sas, "pedir", orig)
        self.correr(sas.main, "sas.py")


if __name__ == "__main__":
    unittest.main()
