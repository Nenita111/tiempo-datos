import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import cielo

M = os.path.join(os.path.dirname(__file__), "muestras")


def agenda(y):
    with open(os.path.join(M, f"agenda_{y}.pdf"), "rb") as f: datos = f.read()
    return cielo.agenda(y, bajar=lambda u: datos)


class Cielo(unittest.TestCase):
    def test_agenda_2027(self):
        e = {(x["fecha"], x["titulo"]): x for x in agenda(2027)}
        self.assertEqual(e[("2027-12-22", "Empieza el invierno")]["hora"], "03:42")
        self.assertEqual(e[("2027-03-20", "Empieza la primavera")]["hora"], "21:24")
        sol = e[("2027-08-02", "Eclipse total de Sol")]
        self.assertIn("el sur de Almeria", sol["detalle"])   # tal cual lo escribe el IGN
        self.assertEqual(e[("2027-02-20", "Eclipse penumbral de Luna")]["detalle"], "Visible en toda España")
        self.assertIn(("2027-08-17", "Eclipse penumbral de Luna"), e)
        self.assertNotIn(("2027-02-06", "Eclipse anular de Sol"), e)   # no se ve en España
        self.assertIn(("2027-03-28", "Cambio de hora"), e); self.assertIn(("2027-10-31", "Cambio de hora"), e)

    def test_agenda_2026(self):
        e = {(x["fecha"], x["titulo"]) for x in agenda(2026)}
        self.assertIn(("2026-12-21", "Empieza el invierno"), e)
        self.assertIn(("2026-10-25", "Cambio de hora"), e)
        self.assertIn(("2026-08-12", "Eclipse total de Sol"), e)

    def test_lluvias(self):
        l = {x["titulo"]: x for x in cielo.lluvias(2026)}
        self.assertEqual(l["Máximo de las Gemínidas"]["fecha"], "2026-12-14")
        self.assertIn("Hasta 150 meteoros por hora", l["Máximo de las Gemínidas"]["detalle"])
        self.assertIn("fecha aproximada", l["Máximo de las Leónidas"]["detalle"])


if __name__ == "__main__":
    unittest.main()
