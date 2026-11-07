"""Pruebas de ayudas.py con respuestas reales de la API de la BDNS del 7 nov 2026 (prueba_bdns_20261107.json, recortadas)."""
import datetime as dt, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas

FIJO = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_bdns_20261107.json"), encoding="utf-8"))
HOY = dt.date(2026, 11, 7)
DET = {str(d["codigoBDNS"]): d for d in FIJO["detalles"]}


class Ayudas(unittest.TestCase):
    def f(self, num, hoy=HOY):
        return ayudas.ficha(DET[num], "Junta de Andalucía", hoy)

    def test_organos(self):
        o = ayudas.organos(FIJO["local"], FIJO["autonomica"])
        self.assertEqual(o["Adra"], [5656]); self.assertEqual(sorted(o["Diputación de Almería"]), [15, 2606, 2607, 2608])
        # la Junta, sin las delegaciones del Gobierno en otras provincias (la de Almería, sí)
        self.assertIn(3747, o["Junta de Andalucía"]); self.assertNotIn(3748, o["Junta de Andalucía"]); self.assertGreater(len(o["Junta de Andalucía"]), 150); self.assertIn(5907, o["Junta de Andalucía"])

    def test_con_fechas(self):
        a = self.f("938972")   # Prácticas profesionales no laborales: del 6 al 19 nov
        self.assertEqual((a["estado"], a["desde"], a["hasta"], a["titulo"]), ("abierta", "2026-11-06", "2026-11-19", "Prácticas profesionales no laborales"))
        self.assertEqual(a["enlace"], "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/938972"); self.assertEqual(a["importe"], 500000)
        self.assertEqual(self.f("938972", dt.date(2026, 11, 20))["estado"], "cerrada")
        p = self.f("929244")   # la parada del arrastre del Mediterráneo: del 11 al 25 ene 2027
        self.assertEqual((p["estado"], p["desde"]), ("proxima", "2027-01-11"))
        self.assertEqual(p["titulo"], "Ayudas por la Parada Temporal de la flota de Arrastre de fondo que faena en el Mediterráneo")

    def test_plazo_en_texto(self):
        # «15 días naturales» desde el 22 jul: cerró el 5 ago aunque la BDNS diga «abierto»
        self.assertEqual(ayudas.plazo(DET["919648"], HOY)[0], "cerrada")
        self.assertEqual(ayudas.plazo(DET["919648"], dt.date(2026, 8, 5))[2], dt.date(2026, 8, 5))
        # varios plazos (escuelas infantiles): el último, y el texto
        e = self.f("896099"); self.assertEqual((e["estado"], e["hasta"]), ("abierta", "2027-06-30")); self.assertIn("31 diciembre 2026", e["plazo"])
        # sin fecha: el texto del plazo
        self.assertEqual(self.f("929233")["plazo"], "Último día de la parada"); self.assertEqual(self.f("932330")["plazo"], "sin fecha de cierre")
        self.assertEqual(ayudas.fechas_en("20 de Eenero de 2027"), [dt.date(2027, 1, 20)])

    def test_fuera(self):
        for n in ("926523", "924013"):   # instrumentales y nominativas: no se piden
            self.assertEqual(self.f(n)["estado"], "cerrada")
        self.assertEqual(self.f("550671")["estado"], "cerrada")   # Adra, 2021, plazo en días sin la fecha de publicación
        x = dict(DET["938972"], descripcion="CONCESIÓN DIRECTA DE UNA SUBVENCIÓN A PRUEBA")   # PRUEBA: con nombre, no sale
        self.assertEqual(ayudas.plazo(x, HOY)[0], "cerrada")
        x = dict(DET["938972"], regiones=[{"descripcion": "ES612 - Cádiz"}])   # PRUEBA: para Cádiz, no
        self.assertEqual(ayudas.plazo(x, HOY)[0], "cerrada")

    def test_titulos_y_organos(self):
        self.assertEqual(self.f("911146")["titulo"][:46], "Ayudas a la natalidad y adopción en municipios")
        self.assertTrue(self.f("932330")["titulo"].startswith("Subvenciones para apoyo a mujeres empresarias"))
        self.assertIn("provincia de Almería", self.f("932330")["titulo"])
        self.assertEqual(self.f("935159")["titulo"], "Incentivos del plan renove vehículos Andalucía")
        self.assertEqual(self.f("938972")["organo"], "Consejería de Empleo, Empresa y Trabajo Autónomo")
        self.assertEqual(self.f("938972")["para"], ["personas", "autónomos y pymes", "entidades", "empresas"])

    def test_orden(self):
        L = sorted((a for a in (self.f(n) for n in DET) if a["estado"] in ("abierta", "proxima")), key=ayudas.orden)
        self.assertEqual(L[0]["num"], "938972"); self.assertEqual(L[-1]["num"], "929244")


if __name__ == "__main__":
    unittest.main()
