"""Jev sin red: las respuestas son de mentira (con la forma de la API, api.typesafe.ai/v1/systemone) para probar el código que las usa."""
import datetime as dt, io, json, os, sys, tempfile, unittest, urllib.error
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(__file__))
import jev, avisos_movil as A, titulares as T, receta as R, sortea2 as S2, sas, etiquetas as ET, comprobar_captura as CC, revisar_fuentes as RF

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
        cortes, no, cand = T.juzgar(piezas, "Adra", "04003", pedir, hoy=dt.date(2026, 10, 28))
        self.assertEqual([(c["enlace"], c["tipo"], c["hasta"], c["jev"]) for c in cortes], [("https://x/a", "agua", "2026-10-29", True)])
        self.assertEqual(no, ["https://x/b"])          # la regla lo daría por corte (en Berja): la tele no lo enseña
        self.assertEqual(A.tipo_corte(piezas[1]["titulo"]), "agua")
        self.assertEqual(cand, [])

    def test_actividades_y_colectas(self):
        pub = dt.datetime(2026, 10, 28, 9, 0, tzinfo=TZ)
        piezas = [{"titulo": "PRUEBA: Adra celebra el sábado 31 su feria del libro en la plaza", "entradilla": "", "enlace": "https://x/f", "s": pub},
                  {"titulo": "PRUEBA: Colecta de sangre en Adra", "entradilla": "", "enlace": "https://x/s", "s": pub}]
        base = dict(anuncia=noul(0.0), tipo=choice("otro"), en_pueblo=noul(0.9), restablecido=noul(0.0), mes=choice("not_stated"))
        r = {"https://x/f": base | {"actividad": noul(0.92), "colecta": noul(0.0), "dia": choice("31")},
             "https://x/s": base | {"actividad": noul(0.2), "colecta": noul(0.95), "dia": choice("not_stated")}}
        pedir = lambda cu, t: {"answers": r[next(p["enlace"] for p in piezas if p["titulo"] == cu["state"]["noticia"]["titulo"])]}
        _, _, cand = T.juzgar(piezas, "Adra", "04003", pedir, hoy=dt.date(2026, 10, 28))
        self.assertEqual([(c["tipo"], c["enlace"], c["dia"]) for c in cand], [("actividad", "https://x/f", "2026-10-31"), ("colecta", "https://x/s", None)])
        self.assertIn("actividad", jev.preguntas_titular()); self.assertIn("anuncia", jev.preguntas_titular())


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
    """Los mismos ficheros reales que EmpleoTest de la app (BOJA 208 del 27 oct; del BOE del 26 oct, solo lo del SAS y otra, sin el nombre de la persona): lo mismo que lee la tele."""
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


class Etiquetas(unittest.TestCase):
    """Las listas reales del 29 oct (AESAN, AEMPS, Safety Gate) y las ofertas de la Junta del 27 oct, recortadas; Jev, de mentira."""
    def m(self, n): return open(os.path.join(os.path.dirname(__file__), "muestras", n), encoding="utf-8").read()

    def red(self, url, cuerpo=None, tipo=None):
        if "aesan" in url: return self.m("aesan_alertas_20261029.html")
        if "aemps.gob.es" in url: return self.m("aemps_lista_20261029.html")
        if url.endswith("/search"): return self.m("safetygate_busqueda_20261029.json")
        if "/notification/" in url:
            i = url.split("/notification/")[1].split("?")[0]
            try: return self.m(f"safetygate_ficha_{i}.json")
            except FileNotFoundError: return json.dumps({"product": {"productCategory": {"key": "product.category.electrical.appliances"}, "versions": []}})
        if "ofertas-empleo.html" in url: return self.m("ofertas_20261027.html")
        if "/detalle/" in url: return self.m("oferta_688570.html")
        raise AssertionError(url)

    def jev(self, cu, t):
        q = cu["questions"]
        if "alergeno" in q: return {"answers": {"alergeno": choice("leche" if "leche" in cu["state"]["alerta"]["titulo"].lower() else "ninguno")}}
        if "devolver" in q: return {"answers": {"devolver": noul(0.85 if "paciente" in cu["state"]["alerta"]["medida"].lower() else 0.1)}}
        if "ninos" in q: return {"answers": {"ninos": noul(0.2)}}
        if "nivel" in q: return {"answers": {"nivel": choice("grado"), "experiencia": noul(0.15)}}
        if "mismo" in q: return {"answers": {"mismo": noul(0.95 if "feria" in cu["state"]["a"]["titulo"].lower() and "feria" in cu["state"]["b"]["titulo"].lower() else 0.05)}}
        if "participa" in q: return {"answers": {"participa": choice("seguir_mencionar")}}
        raise AssertionError(q)

    def test_todo(self):
        x = {"agenda": [{"titulo": "PRUEBA: Feria del libro", "fecha": "2026-10-31", "lugar": "Plaza"},
                        {"titulo": "PRUEBA: Feria del libro de Adra", "fecha": "2026-10-31", "lugar": "Plaza de la Constitución", "hora": "11:00"},
                        {"titulo": "PRUEBA: Concierto", "fecha": "2026-10-31"}],
             "sorteos": [{"premio": "PRUEBA: cesta", "como": "seguir y etiquetar a 2 amigos"}]}
        cima = {"61201": True, "79371": True}
        orig = ET.sin_receta
        ET.sin_receta = lambda regs, consultar=None: orig(regs, lambda n: {"receta": cima.get(n, True)})
        try: r = ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=self.jev)
        finally: ET.sin_receta = orig
        e = x["etiquetas"]
        self.assertEqual(r["juez"], "Jev"); self.assertEqual(r["fallos"], [])
        self.assertEqual(len(e["alim"]), 10)
        self.assertEqual(len(e["med"]), 5); self.assertTrue(all(v["sinReceta"] is False for k, v in e["med"].items() if k != "R_35/2026"))
        self.assertEqual(e["prod"]["10118906"], {"ninos": 1.0})                       # juguete: por su categoría, sin preguntar
        self.assertEqual(len(e["ofertas"]), 17); self.assertEqual(next(iter(e["ofertas"].values())), {"nivel": "grado", "experiencia": 0.15})
        self.assertEqual([a["titulo"] for a in x["agenda"]], ["PRUEBA: Feria del libro de Adra", "PRUEBA: Concierto"])   # se queda la de más datos
        self.assertEqual(x["sorteos"][0]["participa"], "seguir_mencionar")
        # otra vez: lo ya etiquetado no se pregunta
        preguntas = []
        ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=lambda cu, t: preguntas.append(cu) or self.jev(cu, t))
        self.assertEqual([q for q in preguntas if "nivel" in q["questions"] or "alergeno" in q["questions"]], [])

    def test_sin_jev_solo_lo_exacto(self):
        def p403(c, t): raise error(403)
        x = {"agenda": [{"titulo": "a", "fecha": "2026-10-31"}, {"titulo": "a", "fecha": "2026-10-31"}]}
        r = ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=p403)
        self.assertTrue(r["juez"].startswith("sin Jev")); self.assertEqual(len(x["agenda"]), 2)
        self.assertEqual(x["etiquetas"]["prod"], {"10118906": {"ninos": 1.0}}); self.assertEqual(x["etiquetas"]["ofertas"], {})


class Captura(unittest.TestCase):
    def test_dato_que_no_cuadra(self):
        texto = "PRUEBA: ¡Sorteo! @tienda_prueba regala una cesta. Participa hasta el 5 de noviembre."
        def pedir(cu, t):
            assert cu["state"]["texto"] == texto
            return {"answers": {"premio": noul(0.95), "hasta": noul(0.2)}}          # «a las 20:00» no lo dice
        r = CC.comprobar(texto, {"premio": "una cesta", "hasta": "5 de noviembre de 2026 a las 20:00"}, pedir)
        self.assertEqual((r["ok"], r["no_cuadra"]), (False, ["hasta"]))
        self.assertIn("ends", jev.preguntas_captura({"hasta": "x"})["hasta"]["instructions"])
        def p403(c, t): raise error(403)
        self.assertTrue(CC.comprobar(texto, {"premio": "x"}, p403)["ok"])         # sin Jev no bloquea


class SegundaMirada(unittest.TestCase):
    def test_pista(self):
        pagina = b"<html><body><table><tr><td>Precio medio 0,12 euros/kWh</td></tr></table></body></html>"
        self.assertIn("parece seguir", RF.segunda_mirada("luz", "ValueError: sin precios", pagina, pedir_jev=lambda c, t: {"answers": {"sigue": noul(0.9)}}))
        self.assertIn("ya no parece", RF.segunda_mirada("luz", "ValueError: sin precios", pagina, pedir_jev=lambda c, t: {"answers": {"sigue": noul(0.1)}}))
        self.assertEqual(RF.segunda_mirada("luz", "x", pagina, pedir_jev=lambda c, t: {"answers": {"sigue": noul(0.5)}}), "")


class Composio(unittest.TestCase):
    """Jev por el conector de Composio: en el sandbox, COMPOSIO (run_composio_tool) y GUARDADAS; en la tarea, JEV_CACHE (respuestas de mentira)."""
    def setUp(self):
        self.env = {k: os.environ.get(k) for k in ("JEV_CACHE", "JEV_FALTAN", "TYPESAFE_API_KEY")}
        for k in self.env: os.environ.pop(k, None)
        jev.COMPOSIO, jev.GUARDADAS, jev._CACHE = None, {}, None
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        jev.COMPOSIO, jev.GUARDADAS, jev._CACHE = None, {}, None

    def composio(self, respuestas, vistas=None):
        def run(slug, args):
            self.assertEqual(slug, "JEV_EVALUATE_STATE"); self.assertEqual(set(args), {"model", "state", "questions"})
            if vistas is not None: vistas.append(args)
            return {"data": {"answers": respuestas(args), "model": args["model"], "usage": {}}, "error": None}, None
        return run

    def a_la_tarea(self):
        """Lo que guardó el sandbox, a un fichero; la tarea lo lee con JEV_CACHE (y sin Composio)."""
        f = os.path.join(self.dir, "cache.json")
        json.dump(jev.GUARDADAS, open(f, "w", encoding="utf-8"))
        jev.COMPOSIO, jev._CACHE = None, None
        os.environ["JEV_CACHE"] = f; os.environ["JEV_FALTAN"] = f + ".faltan"
        open(f + ".faltan", "w").close()
        return f

    def test_ida_y_vuelta_titulares(self):
        pub = dt.datetime(2026, 10, 28, 9, 0, tzinfo=TZ)
        piezas = [{"titulo": "PRUEBA: Adra se quedará sin agua el jueves 29", "entradilla": "", "enlace": "https://x/a", "s": pub},
                  {"titulo": "PRUEBA: Adra presenta la feria", "entradilla": "", "enlace": "https://x/c", "s": pub}]
        corte = dict(anuncia=noul(0.95), tipo=choice("agua"), en_pueblo=noul(0.9), restablecido=noul(0.0), dia=choice("29"), mes=choice("not_stated"))
        nada = dict(anuncia=noul(0.0), tipo=choice("otro"), en_pueblo=noul(0.5), restablecido=noul(0.0), dia=choice("not_stated"), mes=choice("not_stated"))
        vistas = []
        jev.COMPOSIO = self.composio(lambda a: corte if "agua" in a["state"]["noticia"]["titulo"] else nada, vistas)
        sandbox = T.juzgar(piezas, "Adra", "04003", hoy=dt.date(2026, 10, 28))
        self.assertEqual(len(vistas), 2); self.assertEqual(len(jev.GUARDADAS), 2)
        self.a_la_tarea()
        tarea = T.juzgar(piezas, "Adra", "04003", hoy=dt.date(2026, 10, 28))
        self.assertEqual(tarea, sandbox)                                   # las mismas preguntas: las mismas respuestas
        self.assertEqual([c["enlace"] for c in tarea[0]], ["https://x/a"])
        # un titular que el sandbox no vio (llegó después): ese, sin Jev; los demás, igual
        nuevo = {"titulo": "PRUEBA: titular nuevo", "entradilla": "", "enlace": "https://x/n", "s": pub}
        self.assertEqual(T.juzgar(piezas + [nuevo], "Adra", "04003", hoy=dt.date(2026, 10, 28)), sandbox)
        self.assertEqual(len(open(os.environ["JEV_FALTAN"]).read().split()), 1)

    def test_sin_respuesta_solo_ese(self):
        self.a_la_tarea()                                                  # caché vacía
        d = [{"texto": "PRUEBA … Servicio Andaluz de Salud", "url": "u1", "boletin": "BOJA"}]
        self.assertEqual(sas.etiquetar(d, {}), {})                         # sin etiqueta (mañana otra vez), sin cortar el paso
        j = A.Juez()
        self.assertEqual(j.corte("Adra", {"titulo": "PRUEBA: corte de agua en Adra", "entradilla": ""}), ("agua", None))
        self.assertTrue(j.activo)                                          # el siguiente se sigue preguntando
        xml = Sortea2.XML.replace("</channel>", Sortea2.PRUEBA + "</channel>")
        c = S2.candidatos(xml)
        self.assertEqual([x["jev"] for x in c["candidatos"]], [None])      # va de candidato, sin juzgar
        with self.assertRaises(jev.SinRespuesta): jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})

    def test_errores_de_composio(self):
        esperas = []
        jev.time.sleep, dormir = esperas.append, jev.time.sleep
        try:
            def sin_saldo(slug, args): return None, "The user's Composio wallet is out of credits"
            jev.COMPOSIO = sin_saldo
            with self.assertRaises(jev.SinJev): jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})
            jev.COMPOSIO = lambda slug, args: (None, "HTTP 422: validation error")
            with self.assertRaises(ValueError): jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})
            n = []
            def a_la_tercera(slug, args):
                n.append(1)
                return (None, "timeout") if len(n) < 3 else ({"data": {"data": {"answers": {"q": noul(0.8)}, "model": "jev-1.13.0"}}}, None)
            jev.COMPOSIO = a_la_tercera
            self.assertEqual(jev.preguntar({"x": 2}, {"q": jev.noul("Is it?")})[0]["q"]["noul"], 0.8)
            self.assertEqual(esperas, [2, 4])
        finally:
            jev.time.sleep = dormir

    def test_clave_estable(self):
        a = {"state": {"b": 1, "a": "ñ"}, "model": "jev-1.13.0", "questions": {"q": {"type": "noul", "instructions": "x"}}}
        b = {"questions": {"q": {"instructions": "x", "type": "noul"}}, "model": "jev-1.13.0", "state": {"a": "ñ", "b": 1}}
        self.assertEqual(jev.clave(a), jev.clave(b))
        self.assertNotEqual(jev.clave(a), jev.clave(a | {"model": "jev-latest"}))

    def test_sandbox_sabe_que_pasos(self):
        import diario
        nombres = [n for n, _, _ in diario.PASOS]
        self.assertTrue(set(diario.PREVIOS + diario.CON_JEV) <= set(nombres))
        self.assertLess(max(nombres.index(n) for n in diario.PREVIOS), min(nombres.index(n) for n in diario.CON_JEV))
        g = {"run_composio_tool": None, "upload_local_file": None}
        exec(open(os.path.join(os.path.dirname(__file__), "composio_jev.py"), encoding="utf-8").read(), g)
        self.assertTrue(all(callable(g[f]) for f in ("jev_correr", "jev_esperar", "jev_captura")))


if __name__ == "__main__":
    unittest.main()
