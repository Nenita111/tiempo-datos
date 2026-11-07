"""Pruebas de actividades.py con respuestas reales del 7 nov 2026 (prueba_actividades_20261107.json, recortadas)."""
import datetime as dt, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actividades as A

F = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_actividades_20261107.json"), encoding="utf-8"))
HOY = dt.date(2026, 11, 7)


class Actividades(unittest.TestCase):
    def test_turismo_almeria(self):
        t = {p["titulo"]: p for p in A.turismo_almeria(F["turismoEventos"], F["turismoLugares"], HOY)}
        m = next(p for k, p in t.items() if k.startswith("III Marcha Saludable"))
        # 15 nov a las 10:00 (la API la da como si fuera UTC: 10:00 de aquí), gratis, al aire libre y de senderismo
        self.assertEqual((m["inicio"], m["hora"], m.get("gratis"), m.get("aireLibre"), m.get("senderismo")), ("2026-11-15", "10:00", True, True, True))
        self.assertEqual(m["lugar"], "Parking de la Bola Azul")
        b = t["AlmeriJazz: Banda Municipal de Almería"]
        self.assertEqual((b["inicio"], b["hora"], b.get("gratis"), b.get("aireLibre")), ("2026-11-08", "12:00", True, None))
        self.assertTrue(t[next(k for k in t if "catamarán" in k)]["aireLibre"])
        # un curso de siete meses, no; una charla en el Pabellón de Historia Natural no es «al aire libre»
        self.assertFalse(any("Coro-Combo" in k for k in t))
        self.assertIsNone(next((p for k, p in t.items() if k.startswith("Almería mira al mar")), {}).get("aireLibre"))
        # una exposición del 9 nov al 8 ene (dos meses): no
        self.assertFalse(any("memoria construida" in k for k in t))

    def test_diputacion(self):
        d = A.dipalme(F["dipalme"], HOY)
        self.assertEqual([(p["titulo"], p["inicio"], p.get("senderismo")) for p in d if p["programa"].startswith("Rutas")][:2],
                         [("Senda de la Hidroeléctrica Laujar de Andarax", "2026-11-07", True), ("Sendero de la Uva Canjáyar", "2026-11-15", True)])
        self.assertTrue(all("Tenis" not in p["programa"] for p in d))
        # Calar Alto (Gérgal) y el desierto de Tabernas quedan fuera de la franja de Almería a Motril
        self.assertFalse(any("Calar Alto" in p["titulo"] or "Tabernas" in p["titulo"] for p in d))
        self.assertEqual(d[0]["municipio"], "Laujar de Andarax")

    def test_motril_sin_precio_no(self):
        # los de Motril de ese día no dicen que sean gratis ni son al aire libre (concierto de 9 €, exposiciones, cine)
        self.assertEqual(A.motril(F["motril"], HOY), [])

    def test_adra_en_la_senda(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_senda_20261107.json"), encoding="utf-8") as f: S = json.load(f)
        T = A.senda_programa(S["texto"])
        self.assertEqual([a["inicio"] for a in T], ["2026-10-11", "2026-11-29", "2027-01-10", "2027-01-29", "2027-04-03", "2027-06-27"])
        g = T[0]
        self.assertEqual((g["titulo"], g["detalle"], g["precio"], g["hora"], g["salida"], g["senderismo"]),
                         ("Senda Aguamora y Río Guadalfeo", "8 km · 3 h · dificultad baja · desnivel 178 m · desde 10 años", "15 €", "salida a las 07:30", "Cruz Roja Adra", True))
        b = T[1]; self.assertTrue(b["gratis"]); self.assertEqual(b["titulo"], "Sendero Rambla de Bolaños. Los 4 Bancos"); self.assertEqual(b["salida"], "Merendero Rambla de Bolaños")
        self.assertEqual(T[2]["titulo"], "Scape Room Parque Geominero del Cerro del Toro, Motril"); self.assertEqual(T[2]["precio"], "Por determinar")
        self.assertEqual((T[3]["inicio"], T[3]["fin"]), ("2027-01-29", "2027-01-31")); self.assertEqual((T[4]["inicio"], T[4]["fin"]), ("2027-04-03", "2027-04-04"))
        self.assertEqual(T[5]["fin"], "2027-07-04")
        # en los próximos 45 días (desde el 7 nov): solo la de Bolaños, gratis; con su enlace y el teléfono de Juventud
        L = A.adra_senda(T, S["pdf"], HOY)
        self.assertEqual([(p["titulo"], p.get("gratis"), p["aireLibre"], p["senderismo"]) for p in L], [("Sendero Rambla de Bolaños. Los 4 Bancos", True, True, True)])
        self.assertEqual(L[0]["fuente"], "Ayuntamiento de Adra (Adra en la Senda)"); self.assertIn("677 942 005", L[0]["inscripcion"]); self.assertEqual(L[0]["lugar"], "salida desde Merendero Rambla de Bolaños")
        # la portada enlaza el PDF de la temporada
        self.assertTrue(A.SENDA_PDF.search(S["portada"]))
        # sin pedir el PDF otra vez si el enlace no cambia (y la portada, solo los lunes)
        x = {"sendaAdra": {"pdf": S["pdf"], "temporada": T, "visto": "2026-11-06"}}
        self.assertIs(A.pedir_senda(x, lambda *a, **k: 1 / 0, HOY), x["sendaAdra"])

    def test_ventana(self):
        self.assertTrue(A.ventana(dt.date(2026, 11, 15), dt.date(2026, 11, 15), HOY))
        self.assertFalse(A.ventana(dt.date(2026, 12, 30), dt.date(2026, 12, 30), HOY))   # más de 45 días
        self.assertFalse(A.ventana(dt.date(2026, 11, 6), dt.date(2026, 11, 6), HOY))      # ya pasó


if __name__ == "__main__":
    unittest.main()
