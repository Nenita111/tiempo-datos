import datetime as dt, json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import agenda


class Agenda(unittest.TestCase):
    def test_anadir_y_no_repetir(self):
        x = {"vuelos": [1]}
        agenda.anadir(x, "Concierto  de la Banda", "2026-11-22", "20:00", lugar="Centro Cultural", enlace="https://www.instagram.com/p/AB/?igsh=xx")
        agenda.anadir(x, "concierto de la banda", "2026-11-22", "20:30")   # el mismo, corregido
        self.assertEqual(len(x["agenda"]), 1)
        self.assertEqual(x["agenda"][0]["hora"], "20:30")
        self.assertEqual(x["vuelos"], [1])
        agenda.anadir(x, "Mercadillo", "2026-11-20", lugar="Paseo", enlace="https://www.instagram.com/p/CD/?igsh=1")
        self.assertEqual(x["agenda"][-1]["enlace"], "https://www.instagram.com/p/CD/")

    def test_datos_que_faltan_o_mal(self):
        with self.assertRaises(ValueError): agenda.anadir({}, "", "2026-11-22")
        with self.assertRaises(ValueError): agenda.anadir({}, "X", "22/11/2026")
        with self.assertRaises(ValueError): agenda.anadir({}, "X", "2026-11-22", hora="8h")
        with self.assertRaises(ValueError): agenda.anadir({}, "X", "2026-11-22", hasta="2026-11-21")

    def test_podar_lo_pasado_y_ordenar(self):
        x = {"agenda": [{"titulo": "B", "fecha": "2026-11-02"}, {"titulo": "A", "fecha": "2026-10-20"},
                        {"titulo": "Expo", "fecha": "2026-10-01", "hasta": "2026-11-30"}, {"titulo": "C", "fecha": "2026-11-01", "hora": "18:00"}]}
        agenda.podar(x, dt.date(2026, 10, 27))
        self.assertEqual([a["titulo"] for a in x["agenda"]], ["Expo", "C", "B"])

    def test_linea_de_ordenes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "extras.json")
            with open(f, "w") as h: json.dump({"butano": {"precio": 18.84}}, h)
            r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "agenda.py"), f, "--titulo", "Feria del libro",
                                "--fecha", (dt.date.today() + dt.timedelta(days=3)).isoformat(), "--lugar", "Plaza"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(f) as h: x = json.load(h)
            self.assertEqual(x["agenda"][0]["titulo"], "Feria del libro")
            self.assertIn("butano", x); self.assertIn("actualizado", x)


if __name__ == "__main__":
    unittest.main()
