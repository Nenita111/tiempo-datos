"""Jev sin red: las respuestas son de mentira (con la forma de la API, api.typesafe.ai/v1/systemone) para probar el código que las usa."""
import datetime as dt, io, json, os, sys, unittest, urllib.error
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(__file__))
import jev, avisos_movil as A, titulares as T, receta as R, sortea2 as S2, sas

TZ = ZoneInfo("Europe/Madrid")
AHORA = dt.datetime(2026, 10, 28, 12, 0, tzinfo=TZ)


def noul(p): return {"type": "noul", "noul": p}
def choice(c, p=0.9): return {"type": "choice", "choice": c, "confidence": p, "probabilities": {c: p}}


def error(codigo, cab=None):
    return urllib.error.HTTPError(jev.URL, codigo, "x", cab or {}, io.BytesIO(b'{"detail":"x"}'))


class Cliente(unittest.TestCase):
    def test_peticion_y_reintentos(self):
        vistas, esperas = [], []
        def pedir(cuerpo, timeout):
            vistas.append(cuerpo)
            if len(vistas) == 1: raise error(429, {"retry-after": "3"})
            return {"model": "jev-1.13.0", "answers": {"x": noul(0.8)}}
        r, modelo = jev.preguntar({"a": 1}, {"x": jev.noul("Is it?")}, pedir=pedir, dormir=esperas.append)
        self.assertEqual((r["x"]["noul"], modelo), (0.8, "jev-1.13.0"))
        self.assertEqual(esperas, [3.0])                                  # respeta retry-after
        self.assertEqual(vistas[0]["model"], "jev-1.13.0"); self.assertEqual(vistas[0]["questions"]["x"]["type"], "noul")

    def test_sin_clave_o_sin_red(self):
        def p401(c, t): raise error(401)
        with self.assertRaises(jev.SinJev): jev.preguntar({}, {}, pedir=p401, dormir=lambda s: None)
        def sin_red(c, t): raise urllib.error.URLError("no")
        with self.assertRaises(jev.SinJev): jev.preguntar({}, {}, pedir=sin_red, dormir=lambda s: None)
        def p422(c, t): raise error(422)
        with self.assertRaises(ValueError): jev.preguntar({}, {}, pedir=p422, dormir=lambda s: None)

    def test_preguntas_bien_formadas(self):
        for q in [jev.preguntas_corte(), jev.preguntas_sorteo(), jev.preguntas_receta({"Gazpacho": "frío", "Puchero": "caliente"}), jev.preguntas_sas()]:
            for v in q.values():
                self.assertIn(v["type"], ("noul", "choice"))
                if v["type"] == "choice": self.assertTrue(2 <= len(v["criteria"]) <= 255)
        self.assertEqual(len(jev.DIAS_MES), 32)


class Cortes(unittest.TestCase):
    RSS = ('<rss><channel>'
           '<item><title>Adra se quedará sin agua el jueves en La Curva por una reparación</title><link>https://www.noticiasdealmeria.com/a</link>'
           '<pubDate>Tue, 27 Oct 2026 10:00:00 +0100</pubDate></item>'
           '<item><title>Corte de agua el viernes en Adra</title><link>https://www.noticiasdealmeria.com/b</link>'
           '<pubDate>Tue, 27 Oct 2026 10:00:00 +0100</pubDate></item>'
           '<item><title>Adra mejora la red de agua sin cortes de suministro</title><link>https://www.noticiasdealmeria.com/c</link>'
           '<pubDate>Tue, 27 Oct 2026 10:00:00 +0100</pubDate></item></channel></rss>')

    def test_jev_decide_y_si_duda_la_regla(self):
        r = {"a": dict(anuncia=noul(0.95), tipo=choice("agua"), en_pueblo=noul(0.9), restablecido=noul(0.02)),        # la regla no lo veía
             "b": dict(anuncia=noul(0.5), tipo=choice("agua", 0.6), en_pueblo=noul(0.9), restablecido=noul(0.1)),     # duda: la regla dice agua
             "c": dict(anuncia=noul(0.1), tipo=choice("otro"), en_pueblo=noul(0.8), restablecido=noul(0.05))}         # no es un corte
        def pedir(cuerpo, t):
            k = cuerpo["state"]["noticia"]["titulo"]
            return {"answers": r["a" if "La Curva" in k else "b" if "viernes" in k else "c"]}
        juez = A.Juez(pedir)
        c = A.cortes_rss(self.RSS, "Adra", AHORA - dt.timedelta(days=2), juez)
        self.assertEqual([x["enlace"][-1] for x in c], ["a", "b"])
        self.assertEqual(juez.usado, "Jev")
        self.assertEqual(A.tipo_corte("Adra se quedará sin agua el jueves en La Curva por una reparación"), None)   # lo que mejora Jev

    def test_sin_jev_la_regla(self):
        def p401(c, t): raise error(401)
        juez = A.Juez(p401)
        c = A.cortes_rss(self.RSS, "Adra", AHORA - dt.timedelta(days=2), juez)
        self.assertEqual([x["enlace"][-1] for x in c], ["b"])
        self.assertEqual(juez.usado, "reglas"); self.assertIn("401", juez.motivo)

    def test_es_corte(self):
        base = dict(anuncia=noul(0.9), tipo=choice("luz"), en_pueblo=noul(0.9), restablecido=noul(0.0))
        self.assertEqual(jev.es_corte(base), "luz")
        self.assertIsNone(jev.es_corte(base | {"restablecido": noul(0.8)}))          # ya volvió
        self.assertIsNone(jev.es_corte(base | {"en_pueblo": noul(0.2)}, "luz"))       # en otro pueblo, aunque la regla diga luz
        self.assertIsNone(jev.es_corte(base | {"tipo": choice("trafico")}))           # al móvil, solo agua y luz


class Titulares(unittest.TestCase):
    def test_fecha_dicha(self):
        pub = dt.datetime(2026, 10, 28, 9, 0, tzinfo=TZ)
        f = lambda d, m="not_stated": T.fecha_dicha({"dia": choice(d), "mes": choice(m)}, pub)
        self.assertEqual(f("30"), dt.date(2026, 10, 30))
        self.assertEqual(f("2"), dt.date(2026, 11, 2))                     # sin mes: el próximo día 2
        self.assertEqual(f("27"), dt.date(2026, 10, 27))                   # la víspera vale (noticia de un corte de ayer)
        self.assertEqual(f("5", "enero"), dt.date(2027, 1, 5))
        self.assertIsNone(f("31", "noviembre"))                             # no existe: nada
        self.assertIsNone(f("not_stated"))

    def test_juzgar(self):
        pub = dt.datetime(2026, 10, 28, 9, 0, tzinfo=TZ)
        piezas = [{"titulo": "Adra se quedará sin agua el jueves 29 en La Curva", "entradilla": "", "enlace": "https://x/a", "s": pub},
                  {"titulo": "Corte de agua en Berja; Adra, sin afecciones", "entradilla": "", "enlace": "https://x/b", "s": pub},
                  {"titulo": "Adra presenta la feria", "entradilla": "", "enlace": "https://x/c", "s": pub}]
        r = {"a": dict(anuncia=noul(0.95), tipo=choice("agua"), en_pueblo=noul(0.9), restablecido=noul(0.0), dia=choice("29"), mes=choice("not_stated")),
             "b": dict(anuncia=noul(0.9), tipo=choice("agua"), en_pueblo=noul(0.1), restablecido=noul(0.0), dia=choice("not_stated"), mes=choice("not_stated")),
             "c": dict(anuncia=noul(0.0), tipo=choice("otro"), en_pueblo=noul(0.5), restablecido=noul(0.0), dia=choice("not_stated"), mes=choice("not_stated"))}
        pedir = lambda cuerpo, t: {"answers": r[next(k for k, p in zip("abc", piezas) if p["titulo"] == cuerpo["state"]["noticia"]["titulo"])]}
        cortes, no = T.juzgar(piezas, "Adra", "04003", pedir)
        self.assertEqual([(c["enlace"], c["tipo"], c["hasta"], c["jev"]) for c in cortes], [("https://x/a", "agua", "2026-10-29", True)])
        self.assertEqual(no, ["https://x/b"])          # la regla lo daría por corte (en Berja): la tele no lo enseña
        self.assertEqual(A.tipo_corte(piezas[1]["titulo"]), "agua")


class Receta(unittest.TestCase):
    def test_tiempo_de_aemet(self):
        xml = open(os.path.join(os.path.dirname(__file__), "muestras", "aemet_04003_20261029.xml"), "rb").read()   # AEMET, Adra, 29 oct
        self.assertEqual(R.tiempo_de(xml, dt.date(2026, 10, 29)), {"temperature": "mild", "rain": "dry", "wind": "light wind", "sky": "Despejado"})
        with self.assertRaises(ValueError): R.tiempo_de(xml, dt.date(2026, 12, 1))

    def test_elegir_sin_repetir(self):
        L = R.recetas(); hoy = dt.date(2026, 10, 29)
        ayer = R.rotacion(L, hoy - dt.timedelta(days=1))["nombre"]
        recientes = [{"fecha": "2026-10-25", "nombre": "Boniato asado"}, {"fecha": "2026-10-10", "nombre": "Calabaza asada"}]
        vistas = []
        def pedir(cuerpo, t):
            ops = cuerpo["questions"]["plato"]["criteria"]; vistas.append(ops)
            return {"answers": {"plato": choice("Calabaza asada")}}
        self.assertEqual(R.elegir(L, hoy, {"temperature": "cool"}, recientes, pedir), "Calabaza asada")
        self.assertNotIn("Boniato asado", vistas[0]); self.assertNotIn(ayer, vistas[0])   # la de hace 4 días y la de ayer, fuera
        self.assertIn("Calabaza asada", vistas[0])                                          # la de hace 19 días puede volver
        self.assertTrue(all(10 in r["meses"] for r in L if r["nombre"] in vistas[0]))
        # Jev contesta algo que no estaba: nada
        self.assertIsNone(R.elegir(L, hoy, {}, [], lambda c, t: {"answers": {"plato": choice("Otra cosa")}}))


class Sortea2(unittest.TestCase):
    XML = open(os.path.join(os.path.dirname(__file__), "muestras", "sortea2_rss_20261029.xml"), "rb").read().decode("utf-8", "replace")   # el RSS real del 29 oct
    PRUEBA = ("<item><title>PRUEBA</title><link>https://www.sortea2.com/sortear/prueba-1</link><pubDate>Thu, 29 Oct 2026 08:00:00 +0100</pubDate>"
              "<description><![CDATA[ <p>Hasta el: 08/11/2026</p>PRUEBA: sorteo de una cesta en nuestra tienda de Adra hasta el 5 de noviembre ]]></description></item>")

    def test_rss_real(self):
        I = S2.items(self.XML)
        self.assertEqual(len(I), 30)
        self.assertTrue(I[0]["texto"].startswith("🎉🔥 ¡SORTEO HARBY’S!"))       # sin el «Hasta el» de sortea2
        self.assertEqual(S2.candidatos(self.XML, pedir=lambda c, t: self.fail("no hay ninguno de la zona"))["candidatos"], [])

    def test_zona_y_jev(self):
        xml = self.XML.replace("</channel>", self.PRUEBA + "</channel>")
        si = {"sorteo": noul(0.95), "local": noul(0.9), "nacional": noul(0.05), "fin": noul(0.9)}
        c = S2.candidatos(xml, pedir=lambda cu, t: {"answers": si})
        self.assertEqual([x["enlace"] for x in c["candidatos"]], ["https://www.sortea2.com/sortear/prueba-1"])
        self.assertEqual(c["candidatos"][0]["pueblos"], ["Adra"])
        self.assertEqual(S2.candidatos(xml, pedir=lambda cu, t: {"answers": si | {"nacional": noul(0.9)}})["candidatos"], [])   # para toda España: fuera
        def p401(cu, t): raise error(401)
        sin = S2.candidatos(xml, pedir=p401)
        self.assertEqual(len(sin["candidatos"]), 1); self.assertTrue(sin["juez"].startswith("sin Jev"))
        self.assertEqual(S2.en_zona("Sorteo en Almerimar y Roquetas de Mar"), ["Almerimar", "Roquetas"])


class Sas(unittest.TestCase):
    """Los mismos ficheros reales que EmpleoTest de la app (BOJA 208 del 27 oct, BOE del 26 oct): lo mismo que lee la tele."""
    def m(self, n): return open(os.path.join(os.path.dirname(__file__), "muestras", n), encoding="utf-8").read()

    def test_como_la_tele(self):
        d = sas.disposiciones_boja(self.m("boja_2026_208_s53.html"), "https://www.juntadeandalucia.es/eboja/2026/208/")
        self.assertTrue(d and all("Servicio Andaluz de Salud" in x["texto"] for x in d))
        self.assertIn("https://www.juntadeandalucia.es/boja/2026/208/10", [x["url"] for x in d])
        b = sas.boletines(self.m("boja_calendario.json"))
        self.assertIn(("2026/208", dt.date(2026, 10, 27)), b); self.assertTrue(all(len(r.split("/")[1]) <= 3 for r, _ in b))
        e = sas.sumario_boe(self.m("boe_20261026.json"))
        self.assertEqual([x["url"] for x in e], ["https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-22323"])

    def test_etiquetar_sin_repetir(self):
        d = [{"texto": "Resolución … listas definitivas … Servicio Andaluz de Salud", "url": "u1", "boletin": "BOJA"},
             {"texto": "Resolución … Hospital Universitario Torrecárdenas … Servicio Andaluz de Salud", "url": "u2", "boletin": "BOJA"}]
        preguntadas = []
        def pedir(cu, t):
            preguntadas.append(cu["state"]["disposicion"]["texto"])
            return {"answers": {"tipo": choice("nombramiento"), "provincia": choice("almeria")}}
        et = sas.etiquetar(d, {"u1": {"tipo": "lista_definitiva", "provincia": "andalucia"}}, pedir)
        self.assertEqual(et, {"u1": {"tipo": "lista_definitiva", "provincia": "andalucia"}, "u2": {"tipo": "nombramiento", "provincia": "almeria"}})
        self.assertEqual(len(preguntadas), 1)          # la ya etiquetada no se vuelve a preguntar


if __name__ == "__main__":
    unittest.main()
