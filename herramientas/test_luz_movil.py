"""Pruebas de luz_movil.py sin red (respuestas con la forma de ESIOS y REData; precios de ejemplo).

  python3 -m unittest herramientas/test_luz_movil.py
"""
import datetime as dt, os, sys, unittest

sys.path.insert(0, os.path.dirname(__file__))
import luz_movil as L


def esios(valores):
    return {"indicator": {"values_updated_at": "2026-10-25T20:17:22.000+01:00", "values": valores}}


class LuzMovil(unittest.TestCase):
    def test_esios_por_dia_solo_peninsula_y_en_orden(self):
        j = esios([{"value": 120.5, "datetime": "2026-10-26T01:00:00.000+01:00", "geo_id": 8741},
                   {"value": 98.0, "datetime": "2026-10-26T00:00:00.000+01:00", "geo_id": 8741},
                   {"value": 150.0, "datetime": "2026-10-25T23:00:00.000+01:00", "geo_id": 8741},
                   {"value": 300.0, "datetime": "2026-10-26T00:00:00.000+01:00", "geo_id": 8742}])   # Canarias: fuera
        por_dia, pub = L.de_esios(j)
        self.assertEqual(por_dia["2026-10-26"], [["00:00", 0.098], ["01:00", 0.1205]])
        self.assertEqual(por_dia["2026-10-25"], [["23:00", 0.15]])
        self.assertTrue(pub.startswith("2026-10-25T20:17"))

    def test_redata_serie_pvpc(self):
        j = {"included": [{"type": "Precio mercado spot", "attributes": {"values": [{"value": 1, "datetime": "2026-10-26T00:00:00.000+01:00"}]}},
                          {"type": "PVPC", "attributes": {"last-update": "2026-10-25T20:17:22.000+01:00", "values": [
                              {"value": 182.71, "datetime": "2026-10-26T00:00:00.000+01:00"}, {"value": 163.55, "datetime": "2026-10-26T01:00:00.000+01:00"}]}}]}
        por_dia, pub = L.de_redata(j)
        self.assertEqual(por_dia, {"2026-10-26": [["00:00", 0.18271], ["01:00", 0.16355]]})
        self.assertEqual(pub[:16], "2026-10-25T20:17")

    def test_resumen_y_tres_horas_seguidas(self):
        p = [[f"{h:02d}:00", v] for h, v in enumerate([.20, .18, .10, .09, .11, .30, .25, .12])]
        r = L.resumen(p)
        self.assertEqual((r["imin"], r["imax"], r["tres"]), (3, 5, 2))     # 02–05 h: 0,10 + 0,09 + 0,11
        self.assertAlmostEqual(r["tres_media"], .10)
        self.assertAlmostEqual(r["media"], .16875)

    def test_colores_iguales_que_en_la_tele(self):
        self.assertEqual(L.color(.10, .10, .40), "#50ccaa")
        self.assertEqual(L.color(.25, .10, .40), "#f5c542")
        self.assertEqual(L.color(.40, .10, .40), "#ff6b5b")

    def test_dia_de_25_horas(self):
        p = [["00:00", .1], ["01:00", .1], ["02:00", .1], ["02:00", .1], ["03:00", .1]]
        self.assertEqual(L.etiquetas(p), ["00 h", "01 h", "02 h", "02 h (2.ª)", "03 h"])

    def test_pagina_con_todas_las_horas_y_sin_inventar(self):
        p = [[f"{h:02d}:00", round(.08 + h * .005, 5)] for h in range(24)]
        h = L.html(p, dt.date(2026, 10, 26), "2026-10-25T20:17:22.000+01:00", "ESIOS", hoy_media=.2)
        self.assertEqual(h.count('class="fila'), 24)
        self.assertIn("Lunes 26 de octubre", h)
        self.assertIn("Precio de la luz mañana", h)
        self.assertIn("publicado a las 20:17", h)
        self.assertIn("de 0 a 3 h", h)
        self.assertIn("% que hoy", h)


if __name__ == "__main__":
    unittest.main()
