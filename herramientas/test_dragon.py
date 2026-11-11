"""dragon.py con los recortes de las páginas oficiales leídas el 11 nov 2026: los próximos campeonatos de la IDBF (y el primero de los
pasados, que no debe salir) y las primeras pruebas de 2027 del calendario de Paddle Europe (ese día, ninguna de barco dragón: la página
de la categoría venía vacía; el recorte es de «todas», para probar la lectura)."""
import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dragon

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras")
def muestra(n):
    with open(os.path.join(M, n), encoding="utf-8") as f: return f.read()


class Dragon(unittest.TestCase):
    def test_idbf(self):
        c = dragon.leer_idbf(muestra("idbf_campeonatos_20261111.html"))
        self.assertEqual(2, len(c))                      # los dos próximos; el de Hualien (2026), ya entre los pasados, no
        m, cl = c
        self.assertEqual("18th IDBF World Dragon Boat Racing Championships", m["original"])
        self.assertEqual("18.º Mundial de Barco Dragón de selecciones", m["titulo"])
        self.assertEqual(("2027-10-17", "2027-10-24", 2027), (m["desde"], m["hasta"], m["anio"]))
        self.assertEqual("Kwun Tong Promenade, Hong Kong, China", m["lugar"])
        self.assertEqual("16.º Mundial de Clubes de Barco Dragón", cl["titulo"])
        self.assertEqual("Castelldefels, Barcelona (España)", cl["lugar"])
        self.assertEqual(2028, cl["anio"]); self.assertNotIn("desde", cl)   # «Date TBC»: sin fecha todavía
        self.assertTrue(all(x["organiza"] == "IDBF" and x["enlace"] == dragon.IDBF for x in c))
        with self.assertRaises(ValueError): dragon.leer_idbf("<html>otra cosa</html>")

    def test_fechas(self):
        self.assertEqual(("2027-10-17", "2027-10-24"), dragon.fechas("17-24 October 2027"))
        self.assertEqual(("2026-08-29", "2026-09-06"), dragon.fechas("29 August-6 September 2026"))
        self.assertEqual(("2025-07-14", "2025-07-20"), dragon.fechas("14-20 July, 2025"))
        self.assertEqual(("2027-06-05", "2027-06-05"), dragon.fechas("5 June 2027"))
        for t in ("Date TBC", "TBC", "31 June 2027", "Hong Kong, China", ""): self.assertIsNone(dragon.fechas(t), t)

    def test_europa(self):
        e = dragon.leer_europa(muestra("paddle_europe_2027_20261111.html"))
        self.assertEqual(4, len(e))
        self.assertEqual({"titulo": "2027 Paddle Europe Slalom Championships", "original": "2027 Paddle Europe Slalom Championships",
                          "lugar": "Krakow, POL", "anio": 2027, "desde": "2027-05-20", "hasta": "2027-05-23", "organiza": "Paddle Europe",
                          "enlace": "https://paddle-europe.eu/calendar/2027-eca-canoe-slalom-european-championships-591"}, e[1])
        self.assertEqual("Saint-Omer (Francia)", e[0]["lugar"]); self.assertEqual("https://paddle-europe.eu/calendar", e[0]["enlace"])
        self.assertEqual([], dragon.leer_europa('<div class="calendar">\n<div class="row">\n</div>\n</div>'))   # la de barco dragón, vacía

    def test_proximos(self):
        c = dragon.leer_idbf(muestra("idbf_campeonatos_20261111.html"))
        self.assertEqual(2, len(dragon.proximos(c, dt.date(2026, 11, 11))))
        self.assertEqual(["16.º Mundial de Clubes de Barco Dragón"], [x["titulo"] for x in dragon.proximos(c, dt.date(2027, 10, 25))])   # el de Hong Kong ya pasó
        self.assertEqual([], dragon.proximos(c, dt.date(2029, 1, 1)))                     # el de 2028 sin fecha: hasta que acaba su año
        self.assertEqual("18.º Mundial de Barco Dragón de selecciones", dragon.proximos(list(reversed(c)), dt.date(2026, 11, 11))[0]["titulo"])


if __name__ == "__main__":
    unittest.main()
