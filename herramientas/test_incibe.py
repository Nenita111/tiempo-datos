"""incibe.py con el RSS real de avisos del INCIBE del 15 nov 2026 (muestras/incibe_avisos_20261115.xml: sus tres avisos más nuevos)."""
import contextlib, datetime as dt, io, json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun, incibe

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras", "incibe_avisos_20261115.xml"), encoding="utf-8") as f: XML = f.read()


class Incibe(unittest.TestCase):
    def test_avisos(self):
        a = incibe.avisos(XML)
        self.assertEqual([x["fecha"] for x in a], ["2026-10-21", "2026-10-14", "2026-09-28"])
        self.assertEqual(a[0]["titulo"], "Un falso concurso de baile permite a los ciberdelincuentes utilizar tu cuenta de WhatsApp")
        self.assertTrue(a[0]["enlace"].startswith("https://www.incibe.es/ciudadania/avisos/un-falso-concurso-de-baile"))
        self.assertTrue(a[0]["afecta"].startswith("Personas que hayan recibido un mensaje de WhatsApp"))
        self.assertTrue(a[0]["resumen"].startswith("Desde INCIBE hemos recibido consultas sobre un nuevo fraude."))
        self.assertEqual(a[2]["titulo"], "Correos y SMS suplantan a la DGT para robar tus datos con falsas multas")
        self.assertTrue(all("<" not in x.get("afecta", "") + x.get("resumen", "") and len(x.get("resumen", "")) <= 421 for x in a))

    def test_vigentes_y_recorte(self):
        a = incibe.avisos(XML)
        self.assertEqual(len(incibe.vigentes(a, dt.date(2026, 11, 15))), 3)                # los de los últimos 60 días
        self.assertEqual([x["fecha"] for x in incibe.vigentes(a, dt.date(2026, 12, 15))], ["2026-10-21"])
        self.assertEqual(incibe.vigentes(a, dt.date(2027, 3, 1)), [])
        self.assertEqual(incibe.recorta("uno dos tres", 20), "uno dos tres"); self.assertEqual(incibe.recorta("uno dos, tres cuatro", 9), "uno dos…")
        self.assertEqual(incibe.avisos("<rss><channel><item><title>PRUEBA sin enlace</title></item></channel></rss>"), [])

    def paso(self, ruta, hoy):
        orig = (comun.pedir, comun.hoy, sys.argv)
        comun.pedir, comun.hoy, sys.argv = (lambda u, *a, **k: XML.encode()), (lambda: hoy), ["incibe.py", ruta]
        s = io.StringIO()
        try:
            with contextlib.redirect_stdout(s): incibe.main()
        finally: comun.pedir, comun.hoy, sys.argv = orig
        return json.loads(s.getvalue())

    def test_el_paso_entero_y_el_aviso_al_movil(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        ruta = os.path.join(d, "extras.json"); comun.guardar(ruta, {"cortes": []})
        # el 22 oct: el aviso del 21 es de ayer → al móvil, una vez; los otros dos son viejos
        r = self.paso(ruta, dt.date(2026, 10, 22))
        self.assertEqual(r, {"estafas": 3, "ultimo": "2026-10-21", "al_movil": 1})
        x = comun.leer(ruta)
        self.assertEqual([a["fecha"] for a in x["estafas"]["lista"]], ["2026-10-21", "2026-10-14", "2026-09-28"])
        self.assertEqual(x["estafas"]["url"], "https://www.incibe.es/ciudadania/avisos"); self.assertEqual(x["cortes"], [])
        avisos = comun.recoger_avisos(ruta)
        self.assertEqual(len(avisos), 1); self.assertTrue(avisos[0].startswith("🛡️ Aviso del INCIBE: Un falso concurso de baile") and avisos[0].endswith(x["estafas"]["lista"][0]["enlace"]))
        self.assertEqual(comun.recoger_avisos(ruta), [])                                   # recogidos, ya no están pendientes
        # otra pasada el mismo día: ni se repite el aviso ni se toca extras.json
        self.assertEqual(self.paso(ruta, dt.date(2026, 10, 22))["al_movil"], 0)
        self.assertEqual(comun.leer(ruta), x); self.assertEqual(comun.recoger_avisos(ruta), [])
        self.assertNotIn("estafasVistas", x)                                              # lo que recuerda va en estado_diario.json

    def test_el_cortafuegos_no_es_un_rss_vacio(self):
        # desde el 19 nov 2026, «302 Security Redirect» a /estatico/defecto.incibe.es/404..html: falla diciendo eso y deja lo que había
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        ruta = os.path.join(d, "extras.json"); comun.guardar(ruta, {"estafas": {"lista": []}})
        orig = (comun.pedir, comun.fallar, sys.argv)
        comun.pedir, sys.argv = (lambda u, *a, **k: b"<!DOCTYPE html><html><body>PRUEBA 404</body></html>"), ["incibe.py", ruta]
        comun.fallar = lambda e: (_ for _ in ()).throw(AssertionError(str(e)))
        try:
            with self.assertRaisesRegex(AssertionError, "cortafuegos"): incibe.main()
        finally: comun.pedir, comun.fallar, sys.argv = orig
        self.assertEqual(comun.leer(ruta), {"estafas": {"lista": []}})

    def test_la_primera_vez_no_avisa_de_lo_viejo(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        ruta = os.path.join(d, "extras.json"); comun.guardar(ruta, {})
        self.assertEqual(self.paso(ruta, dt.date(2026, 11, 15)), {"estafas": 3, "ultimo": "2026-10-21", "al_movil": 0})
        self.assertEqual(comun.recoger_avisos(ruta), [])


if __name__ == "__main__":
    unittest.main()
