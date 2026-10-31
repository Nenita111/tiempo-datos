"""Jev sin red: las respuestas son de mentira (con la forma de la API, api.typesafe.ai/v1/systemone) para probar el código que las usa."""
import datetime as dt, io, json, os, re, sys, tempfile, unittest, urllib.error
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(__file__))
import jev, zona, avisos_movil as A, titulares as T, receta as R, sortea2 as S2, sas, etiquetas as ET, comprobar_captura as CC, revisar_fuentes as RF, fap

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
        cortes, no, cand, _ = T.juzgar(piezas, "Adra", "04003", pedir, hoy=dt.date(2026, 10, 28))
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
        _, _, cand, _ = T.juzgar(piezas, "Adra", "04003", pedir, hoy=dt.date(2026, 10, 28))
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
            return {"answers": {"tipo": choice("nombramiento"), "provincia": choice("almeria"), "zona": choice("almeria")}}
        et = sas.etiquetar(d, {"u1": {"tipo": "lista_definitiva", "provincia": "andalucia", "zona": "andalucia"}}, pedir)
        self.assertEqual(et, {"u1": {"tipo": "lista_definitiva", "provincia": "andalucia", "zona": "andalucia"}, "u2": {"tipo": "nombramiento", "provincia": "almeria", "zona": "almeria"}})
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
        if url == zona.SAE: self.assertEqual(cuerpo, b"{}"); return self.m("sae_20261029.json")
        if "/detalle/" in url: return self.m("oferta_688570.html")
        raise AssertionError(url)

    def jev(self, cu, t):
        q, st, r = cu["questions"], cu["state"], {}
        if "alergeno" in q: r["alergeno"] = choice("leche" if "leche" in st["alerta"]["titulo"].lower() else "ninguno")
        if "producto" in q: r["producto"] = choice("lacteos" if "leche" in st["alerta"]["titulo"].lower() else "otro")    # 3.8
        if "devolver" in q: r["devolver"] = noul(0.85 if "paciente" in st["alerta"]["medida"].lower() else 0.1)
        if "ninos" in q: r["ninos"] = noul(0.2)
        if "entidad" in q: r |= {"nivel": choice("fp_superior"), "experiencia": noul(0.8), "entidad": choice("ayuntamiento")}
        elif "nivel" in q: r |= {"nivel": choice("grado"), "experiencia": noul(0.15)}
        if "colectivo" in q: r["colectivo"] = choice("garantia_juvenil" if "puesto" in st["oferta"] else "general")       # 3.8 (SAE: puesto)
        if "mismo" in q: r["mismo"] = noul(0.95 if "feria" in st["a"]["titulo"].lower() and "feria" in st["b"]["titulo"].lower() else 0.05)
        if "participa" in q: r["participa"] = choice("seguir_mencionar")
        if "gratis" in q: r |= {"gratis": noul(0.9 if "Feria" in st["actividad"]["titulo"] else 0.1), "familias": noul(0.2), "inscripcion": noul(0.05)}
        if "mayor" in q: r |= {"mayor": noul(0.9), "residente": noul(0.2)}
        if not r: raise AssertionError(q)
        return {"answers": r}

    def test_todo(self):
        x = {"agenda": [{"titulo": "PRUEBA: Feria del libro", "fecha": "2026-10-31", "lugar": "Plaza"},
                        {"titulo": "PRUEBA: Feria del libro de Adra", "fecha": "2026-10-31", "lugar": "Plaza de la Constitución", "hora": "11:00"},
                        {"titulo": "PRUEBA: Concierto", "fecha": "2026-10-31"}],
             "sorteos": [{"premio": "PRUEBA: cesta", "como": "seguir y etiquetar a 2 amigos"}]}
        cima = {"61201": True, "79371": True}
        orig = ET.sin_receta
        ET.sin_receta = lambda regs, consultar=None: orig(regs, lambda n: {"receta": cima.get(n, True)})
        ahora = ET.dt.datetime
        class Fijo(dt.datetime):                                                       # el 29 oct a las 11:00, como la lista del SAE
            @classmethod
            def now(cls, tz=None): return dt.datetime(2026, 10, 29, 11, 0, tzinfo=tz)
        ET.dt.datetime = Fijo
        try: r = ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=self.jev)
        finally: ET.sin_receta = orig; ET.dt.datetime = ahora
        e = x["etiquetas"]
        self.assertEqual(r["juez"], "Jev"); self.assertEqual(r["fallos"], [])
        self.assertEqual(len(e["alim"]), 10)
        self.assertEqual(len(e["med"]), 5); self.assertTrue(all(v["sinReceta"] is False for k, v in e["med"].items() if k != "R_35/2026"))
        self.assertEqual(e["prod"]["10118906"], {"ninos": 1.0})                       # juguete: por su categoría, sin preguntar
        self.assertEqual(len(e["ofertas"]), 17)
        o = next(iter(e["ofertas"].values()))
        self.assertEqual({k: o[k] for k in ("nivel", "experiencia", "zona", "hasta")}, {"nivel": "grado", "experiencia": 0.15, "zona": False, "hasta": "2026-10-28"})   # Almonte
        self.assertTrue(o["puesto"] and o["entidad"])
        self.assertEqual(sorted(e["sae"]), ["01-2026-48086"])   # 3.7; 4.2: sin las de Serón, Tíjola y Olula del Río
        self.assertEqual(e["sae"]["01-2026-48086"], {"nivel": "fp_superior", "experiencia": 0.8, "entidad": "ayuntamiento", "colectivo": "garantia_juvenil"})
        self.assertEqual(o["colectivo"], "general")                                    # 3.8
        self.assertTrue(all("producto" in v for v in e["alim"].values()))
        self.assertEqual(e["agenda"]["2026-10-31|PRUEBA: Feria del libro de Adra"], {"gratis": 0.9, "familias": 0.2, "inscripcion": 0.05})
        self.assertEqual(sorted(e["agenda"]), ["2026-10-31|PRUEBA: Concierto", "2026-10-31|PRUEBA: Feria del libro de Adra"])
        self.assertEqual(x["sorteos"][0]["requisitos"], {"mayor": 0.9, "residente": 0.2})
        self.assertEqual([a["titulo"] for a in x["agenda"]], ["PRUEBA: Feria del libro de Adra", "PRUEBA: Concierto"])   # se queda la de más datos
        self.assertEqual(x["sorteos"][0]["participa"], "seguir_mencionar")
        # otra vez: lo ya etiquetado no se pregunta
        preguntas = []
        ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=lambda cu, t: preguntas.append(cu) or self.jev(cu, t))
        self.assertEqual([q for q in preguntas if "mismo" not in q["questions"]], [])   # tampoco las del SAE, la agenda ni los requisitos

    def test_lo_de_antes_solo_lo_nuevo(self):
        """3.8: a lo etiquetado con 3.7 (sin producto ni colectivo) solo se le pregunta eso."""
        x = {"etiquetas": {"alim": {"https://www.aesan.gob.es/alertas/2026_76": {"alergeno": "ninguno"}},
                           "sae": {"01-2026-48086": {"nivel": "grado", "experiencia": 0.1, "entidad": "junta"}}}}
        preguntas = []
        ahora = ET.dt.datetime
        class Fijo(dt.datetime):
            @classmethod
            def now(cls, tz=None): return dt.datetime(2026, 10, 29, 11, 0, tzinfo=tz)
        ET.dt.datetime = Fijo
        try: ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=lambda cu, t: preguntas.append(cu) or self.jev(cu, t))
        finally: ET.dt.datetime = ahora
        e = x["etiquetas"]
        self.assertEqual(e["alim"]["https://www.aesan.gob.es/alertas/2026_76"], {"alergeno": "ninguno", "producto": "otro"})
        self.assertEqual(e["sae"]["01-2026-48086"], {"nivel": "grado", "experiencia": 0.1, "entidad": "junta", "colectivo": "garantia_juvenil"})
        q76 = [q for q in preguntas if q["state"].get("alerta", {}).get("titulo") and "producto" in q["questions"] and "alergeno" not in q["questions"]]
        self.assertEqual(len(q76), 1)
        self.assertEqual([set(q["questions"]) for q in preguntas if q["state"].get("oferta", {}).get("puesto") and "nivel" not in q["questions"]], [{"colectivo"}])

    def test_sin_jev_solo_lo_exacto(self):
        def p403(c, t): raise error(403)
        x = {"agenda": [{"titulo": "a", "fecha": "2026-10-31"}, {"titulo": "a", "fecha": "2026-10-31"}]}
        r = ET.etiquetar(x, dt.date(2026, 10, 29), red=self.red, pedir_jev=p403)
        self.assertTrue(r["juez"].startswith("sin Jev")); self.assertEqual(len(x["agenda"]), 2)
        self.assertEqual(x["etiquetas"]["prod"], {"10118906": {"ninos": 1.0}})
        self.assertTrue(x["etiquetas"]["ofertas"] and all("nivel" not in v and "zona" in v for v in x["etiquetas"]["ofertas"].values()))   # la zona sí (sin Jev)
        self.assertEqual(x["etiquetas"]["sae"], {})


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
        jev.COMPOSIO, jev.GUARDADAS, jev._CACHE, jev.CAIDO, jev.LIMITE = None, {}, None, "", 0.0
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        jev.COMPOSIO, jev.GUARDADAS, jev._CACHE, jev.CAIDO, jev.LIMITE = None, {}, None, "", 0.0

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
        c, no, cand, sin = T.juzgar(piezas + [nuevo], "Adra", "04003", hoy=dt.date(2026, 10, 28))
        self.assertEqual((c, no, cand), sandbox[:3]); self.assertEqual(sin, {"https://x/n"})   # el nuevo, «sin respuesta» (se conserva lo de antes)
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
            # 3.9: sin saldo, esa pregunta y las siguientes se quedan sin respuesta (SinRespuesta: lo de la caché sigue valiendo)
            with self.assertRaises(jev.SinRespuesta): jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})
            self.assertIn("credits", jev.CAIDO)
            jev._CACHE[jev.clave({"state": {"y": 1}, "model": jev.MODELO, "questions": {"q": jev.noul("Is it?")}})] = {"answers": {"q": noul(0.7)}}
            self.assertEqual(jev.preguntar({"y": 1}, {"q": jev.noul("Is it?")})[0]["q"]["noul"], 0.7)     # la de la caché, sí
            with self.assertRaises(jev.SinRespuesta): jev.preguntar({"x": 3}, {"q": jev.noul("Is it?")})  # ya no se llama a Composio
            jev.CAIDO = ""
            jev.COMPOSIO = lambda slug, args: (None, "HTTP 422: validation error")
            with self.assertRaises(jev.SinRespuesta): jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})   # solo esa pregunta
            self.assertEqual(jev.CAIDO, "")
            jev.COMPOSIO = lambda slug, args: (None, "Invalid API key for the connected account")
            with self.assertRaises(jev.SinRespuesta): jev.preguntar({"x": 4}, {"q": jev.noul("Is it?")})
            self.assertIn("API key", jev.CAIDO); jev.CAIDO = ""                                          # es de la cuenta, no de la pregunta
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


class Zona(unittest.TestCase):
    """3.7: la zona (provincia de Almería sin el Levante, la costa de Granada hasta Motril), lo mismo que Empleo.Zona de la app."""
    L = json.load(open(os.path.join(os.path.dirname(__file__), "muestras", "sae_20261029.json"), encoding="utf-8"))   # la lista real del 29 oct, recortada

    def test_como_la_app(self):
        self.assertTrue(zona.levante("HUERCAL-OVERA") and zona.levante("Gallardos, Los") and not zona.levante("ADRA"))
        self.assertTrue(zona.costa("Motril (1)") and zona.costa("CASTELL DE FERRO") and not zona.costa("Almuñécar") and not zona.costa("Granada"))
        self.assertEqual(zona.nombre("04069", "OLULA DEL RIO"), "Olula del Río"); self.assertEqual(zona.nombre("04902", "EJIDO, EL"), "El Ejido")
        o = zona.ofertas_sae(self.L, dt.datetime(2026, 10, 29, 11, 0))
        # 4.2 (lo pidió Isa): sin las de Serón (48457, 48458), Tíjola (48675) y Olula del Río (48758, 48765)
        self.assertEqual([x["id"] for x in o], ["01-2026-48086"])
        self.assertTrue(all(zona.fuera(m) for m in ["SERON", "Tíjola", "OLULA DEL RIO", "Macael", "Cantoria", "LIJAR", "Vera"]))
        self.assertFalse(any(zona.fuera(m) for m in ["Albox", "Chercos", "Adra", "Almería"])); self.assertEqual(len(zona.ALMANZORA), 19)
        self.assertFalse(zona.junta_en_zona([("Macael (2)", "Almería")])); self.assertTrue(zona.junta_en_zona([("Macael", "Almería"), ("Vícar", "Almería")]))
        self.assertTrue(zona.solo_fuera_sas("Convoca concurso de méritos para la cobertura de un puesto de Director/a de la UGC de Olula del Río"))
        self.assertTrue(zona.solo_fuera_sas("Centro de Salud de Serón y consultorio de Lúcar"))
        self.assertFalse(zona.solo_fuera_sas("Convoca, a los fines previstos, plazas del Hospital Universitario Torrecárdenas"))
        self.assertFalse(zona.solo_fuera_sas("UGC de Macael y Hospital de Poniente") or zona.solo_fuera_sas("Distrito Sanitario Almería"))
        self.assertEqual(o[0]["id"], "01-2026-48086"); self.assertEqual(o[0]["sitios"], ["Almería"])

    def test_sae_sin_nijar(self):
        """4.7 (lo pidió Isa el 31 oct 2026): en las del SAE, tampoco Níjar. La lista real del 30 oct (las 20 de empleo público de Almería y
        Granada, sin el texto libre): de las 8 de Almería quedan Almería y El Ejido."""
        L = json.load(open(os.path.join(os.path.dirname(__file__), "muestras", "sae_20261030.json"), encoding="utf-8"))
        o = zona.ofertas_sae(L, dt.datetime(2026, 10, 30, 21, 31))
        self.assertEqual([x["id"] for x in o], ["01-2026-48086", "01-2026-49266"])
        self.assertTrue(zona.fuera_sae("NIJAR") and zona.fuera_sae("Níjar") and not zona.fuera("Níjar"))
        self.assertEqual(o[0]["url"], "https://saempleo.es/ags/candidaturas/lista-ofertas-publicas/detalle-oferta?origin=portal&ofertaId=01-2026-48086")
        h = open(os.path.join(os.path.dirname(__file__), "muestras", "oferta_688570.html"), encoding="utf-8").read()
        itv = zona.lugares_ficha(h)
        self.assertEqual(itv, [("Almonte", "Huelva")]); self.assertFalse(zona.junta_en_zona(itv)); self.assertTrue(zona.ficha_valida(h))
        self.assertTrue(zona.junta_en_zona([("Motril", "Granada")]) and zona.junta_en_zona([("Vícar", "Almería")]))
        # 4.0: como en el SAE, sin el Levante
        self.assertFalse(zona.junta_en_zona([("Huércal-Overa", "Almería")]) or zona.junta_en_zona([('Vera "Hospital"', "Almería")]))
        # 4.1: las que no dicen provincia y las de toda Andalucía, sí; una página que no es la ficha no cuenta
        self.assertTrue(zona.junta_en_zona([]) and zona.junta_en_zona([("Sevilla", "Sevilla"), ("Servicios centrales", "")]))
        self.assertTrue(zona.junta_en_zona([("Varias localidades", "Andalucía")]))
        sin = zona.lugares_ficha(re.sub(r'(?s)(field--name-field-ofem-lugartrabajo.*?class="field__item">)[^<]*', r"\1Servicios centrales", h, count=1))   # PRUEBA
        self.assertEqual(sin, [("Servicios centrales", "")]); self.assertTrue(zona.junta_en_zona(sin))
        self.assertFalse(zona.ficha_valida("<html><body>En mantenimiento</body></html>"))
        self.assertEqual(zona.lugares_ficha('<div class="field--name-field-ofem-lugartrabajo"><div class="field__item">Vera &quot;Hospital&quot; (Almería)</div></main>'),
                         [('Vera "Hospital"', "Almería")])


class OfertasAlMovil(unittest.TestCase):
    """3.7: las ofertas nuevas de la zona, una vez; la primera vez de cada lista, solo se apuntan."""
    def test_nuevas(self):
        sae = zona.ofertas_sae(Zona.L, dt.datetime(2026, 10, 29, 11, 0))
        x = {"etiquetas": {"ofertas": {"689338": {"zona": True, "puesto": "INSPECTOR/A DE ITV", "entidad": "VEIASA", "hasta": "2026-11-11"},
                                        "688570": {"zona": False, "puesto": "PRUEBA", "hasta": "2026-11-11"}}},
             "sas": {"avisar": [{"url": "https://x/prueba", "boletin": "BOJA", "resumen": "PRUEBA: convoca concurso de méritos en el Hospital Universitario Poniente"}]}}
        estado = {}
        self.assertEqual(A.ofertas(estado, sae, x, AHORA), [])                    # la primera vez: nada, se apuntan
        self.assertEqual(len([k for k in estado if k.startswith("empleo:") and not k.endswith(":")]), 3)     # 1 del SAE (4.2), la ITV y la del SAS
        self.assertTrue(all(p in estado for p in ("empleo:sae:", "empleo:junta:", "empleo:sas:")))
        self.assertEqual(A.ofertas(estado, sae, x, AHORA), [])                    # ya avisadas
        x["sas"]["avisar"].append({"url": "https://x/prueba2", "boletin": "BOE", "resumen": "PRUEBA: convoca proceso selectivo"})
        n = A.ofertas(estado, sae + [dict(sae[0], id="PRUEBA-1", puesto="PEON DE JARDINERIA (PRUEBA)")], x, AHORA)
        self.assertEqual([o["clave"] for o in n], ["empleo:sae:PRUEBA-1", "empleo:sas:https://x/prueba2"])
        self.assertTrue(n[0]["texto"].startswith("💼 Empleo público (SAE): Peon de jardineria (prueba) · Almería · hasta el 31 oct"))
        self.assertIn("SAS, convocatoria (BOE)", n[1]["texto"])
        # una lista que llega por primera vez más tarde (la de la Junta, ya con su marca vacía) tampoco avisa de golpe
        e2 = {}; A.ofertas(e2, [], {}, AHORA); self.assertNotIn("empleo:junta:", e2)
        self.assertEqual(A.ofertas(e2, [], x, AHORA), []); self.assertIn("empleo:junta:", e2)
        self.assertEqual(A.frase("PERSONAL INTERINO. ESPECIALIDAD (A1.2002)"), "Personal interino. Especialidad (A1.2002)")


class SasZona(unittest.TestCase):
    def test_zona_y_avisar(self):
        d = [{"texto": "Resolución de 22 de octubre de 2026, de la Dirección General de Personal del Servicio Andaluz de Salud, por la que se convoca concurso en el Hospital Universitario Poniente (PRUEBA).", "url": "u1", "boletin": "BOJA", "fecha": "2026-10-27"},
             {"texto": "Resolución … del Servicio Andaluz de Salud, por la que se convoca concurso en el Hospital La Inmaculada (PRUEBA).", "url": "u2", "boletin": "BOJA", "fecha": "2026-10-27"},
             {"texto": "Resolución … del Servicio Andaluz de Salud, por la que se nombra a don Fulano (PRUEBA).", "url": "u3", "boletin": "BOE", "fecha": "2026-10-26"}]
        z = {"u1": "almeria", "u2": "levante", "u3": "almeria"}; t = {"u1": "convocatoria", "u2": "convocatoria", "u3": "convocatoria"}
        def pedir(cu, tt):
            u = next(x["url"] for x in d if x["texto"][:1500] == cu["state"]["disposicion"]["texto"])
            return {"answers": {"tipo": choice(t[u]), "provincia": choice("almeria"), "zona": choice(z[u])}}
        et = sas.etiquetar(d, {"u1": {"tipo": "convocatoria", "provincia": "almeria"}}, pedir)     # sin «zona»: se vuelve a preguntar
        self.assertEqual(et["u1"]["zona"], "almeria"); self.assertEqual(et["u2"]["zona"], "levante")
        a = sas.avisar(d, et)
        self.assertEqual([x["url"] for x in a], ["u1"])                          # ni lo del Levante ni lo que lleva nombres de personas
        self.assertTrue(a[0]["resumen"].startswith("Convoca concurso en el Hospital Universitario Poniente"))
        self.assertIn("zona", jev.preguntas_sas()); self.assertIn("costa_granada", jev.ZONA_SAS)
        # 4.2: aunque Jev diga «almeria», lo que es solo de la UGC de Olula del Río no se avisa (PRUEBA)
        d4 = d + [{"texto": "Resolución … del Servicio Andaluz de Salud, por la que se convoca la cobertura del puesto de Director/a de la UGC de Olula del Río (PRUEBA).",
                   "url": "u4", "boletin": "BOJA", "fecha": "2026-10-27"}]
        et["u4"] = {"tipo": "convocatoria", "provincia": "almeria", "zona": "almeria"}
        self.assertEqual([x["url"] for x in sas.avisar(d4, et)], ["u1"])


class CacheSandbox(unittest.TestCase):
    """3.7: las respuestas de Jev guardadas en el sandbox de Composio (14 días desde la última vez que se usaron)."""
    def test_guardar_y_olvidar(self):
        d = tempfile.mkdtemp()
        g = {"run_composio_tool": None, "upload_local_file": None}
        exec(open(os.path.join(os.path.dirname(__file__), "composio_jev.py"), encoding="utf-8").read(), g)
        g["JEV_CACHE"] = os.path.join(d, "c.json")
        json.dump({"vieja": {"r": {"answers": {}}, "t": "2026-09-01"}, "usada": {"r": {"answers": {}}, "t": "2026-09-01"}}, open(g["JEV_CACHE"], "w"))
        n = g["_jev_guardar"]({"usada": {"answers": {"q": noul(0.9)}}, "nueva": {"answers": {}}})
        c = json.load(open(g["JEV_CACHE"]))
        self.assertEqual(sorted(c), ["nueva", "usada"]); self.assertEqual(n, 2)
        self.assertEqual(c["usada"]["t"], dt.date.today().isoformat())
        # lo que sale de la caché en el sandbox también se sube (la tarea lo necesita)
        jev.COMPOSIO, jev.GUARDADAS = (lambda *a: self.fail("no debía preguntar")), {}
        cu = {"state": {"x": 1}, "model": jev.MODELO, "questions": {"q": jev.noul("Is it?")}}
        jev._CACHE = {jev.clave(cu): {"answers": {"q": noul(0.7)}, "model": jev.MODELO}}
        try: self.assertEqual(jev.preguntar({"x": 1}, {"q": jev.noul("Is it?")})[0]["q"]["noul"], 0.7); self.assertEqual(len(jev.GUARDADAS), 1)
        finally: jev.COMPOSIO, jev.GUARDADAS, jev._CACHE = None, {}, None

    def test_revision_solo_las_pedidas(self):
        self.assertEqual(RF.revisar(solo={"no_existe"}), [])


class CapturaTipo(unittest.TestCase):
    def test_tipo(self):
        texto = "PRUEBA: Corte de agua el jueves en la calle Natalio Rivas de 8 a 14 h."
        def pedir(cu, t): return {"answers": {"hasta": noul(0.9), "_tipo": choice("corte", 0.95)}}
        r = CC.comprobar(texto, {"hasta": "jueves"}, pedir, tipo="sorteo")
        self.assertFalse(r["ok"]); self.assertEqual(r["no_cuadra"], ["tipo"]); self.assertEqual(r["tipo"], "corte")
        self.assertTrue(CC.comprobar(texto, {"hasta": "jueves"}, pedir, tipo="corte")["ok"])
        def dudosa(cu, t): return {"answers": {"hasta": noul(0.9), "_tipo": choice("otro", 0.5)}}
        self.assertTrue(CC.comprobar(texto, {"hasta": "jueves"}, dudosa, tipo="corte")["ok"])       # si duda, no bloquea
        self.assertNotIn("_tipo", jev.preguntas_captura({"hasta": "x"}))


def muestra(n): 
    with open(os.path.join(os.path.dirname(__file__), "muestras", n), encoding="utf-8") as f: return f.read()


class PlazoSas(unittest.TestCase):
    """3.8: el plazo de solicitudes de las convocatorias del SAS (frases reales de la BOJA 208/11 y el calendario real de la Junta para Adra)."""
    def inh(self):
        return sas.inhabiles({2026}, red=lambda u: muestra("calendario_adra_2026.json") if "year=2026" in u else (_ for _ in ()).throw(OSError("aún no")))

    def test_frases_y_cuentas(self):
        fr = sas.frases_plazo(muestra("boja_2026_208_11_plazos.txt").replace("\n", " "))
        self.assertEqual((fr[0][1], fr[0][2]), (10, "habiles")); self.assertIn("solicitudes", fr[0][0])     # primero la de las solicitudes
        self.assertIn((1, "meses"), [(n, u) for _, n, u in fr])
        inh = self.inh()
        self.assertIn(dt.date(2026, 11, 2), inh)                              # el lunes siguiente a Todos los Santos (Andalucía)
        self.assertIn(dt.date(2026, 9, 8), inh)                               # fiesta local de Adra
        self.assertEqual(sas.fin_plazo(dt.date(2026, 10, 27), 10, "habiles", inh), dt.date(2026, 11, 11))
        self.assertEqual(sas.fin_plazo(dt.date(2026, 10, 27), 1, "meses", inh), dt.date(2026, 11, 27))
        self.assertEqual(sas.fin_plazo(dt.date(2026, 1, 31), 1, "meses", inh), dt.date(2026, 3, 2))         # 28 feb es sábado → lunes 2 mar
        self.assertEqual(sas.fin_plazo(dt.date(2026, 10, 27), 15, "naturales", inh), dt.date(2026, 11, 11))
        self.assertEqual(sas.fin_plazo(dt.date(2026, 12, 4), 3, "habiles", inh), dt.date(2026, 12, 11))     # 7 y 8 dic, festivos
        self.assertTrue(sas.desde_publicacion(fr[0][0], "BOJA"))
        self.assertFalse(sas.desde_publicacion("PRUEBA: veinte días hábiles desde la publicación del extracto en el Boletín Oficial del Estado.", "BOJA"))
        self.assertFalse(sas.desde_publicacion("PRUEBA: plazo de diez días desde la notificación.", "BOJA"))

    def test_plazos_con_jev_y_avisar(self):
        d = [{"texto": "Resolución … del Servicio Andaluz de Salud, por la que se convoca concurso en el Distrito Poniente (PRUEBA).", "url": "u1", "boletin": "BOJA", "fecha": "2026-10-27"},
             {"texto": "Resolución … del Servicio Andaluz de Salud, por la que se convoca concurso en Sevilla (PRUEBA).", "url": "u2", "boletin": "BOJA", "fecha": "2026-10-27"},
             {"texto": "Resolución … del Servicio Andaluz de Salud, por la que se convoca concurso en el Hospital Torrecárdenas (PRUEBA).", "url": "u3", "boletin": "BOJA", "fecha": "2026-09-01"}]
        et = {"u1": {"tipo": "convocatoria", "zona": "almeria"}, "u2": {"tipo": "convocatoria", "zona": "otra"}, "u3": {"tipo": "convocatoria", "zona": "almeria"}}
        def red(u):
            if "work-calendar" in u: return muestra("calendario_adra_2026.json") if "year=2026" in u else "{}"
            return "<html><body><p>" + muestra("boja_2026_208_11_plazos.txt").replace("\n", " ") + "</p></body></html>"
        vistas = []
        def pedir(cu, t):
            vistas.append(cu)
            return {"answers": {k: noul(0.97 if "solicitudes" in f else 0.03) for k, f in cu["state"]["frases"].items()}}
        self.assertEqual(sas.plazos(d, et, red=red, pedir_jev=pedir), 2)
        self.assertEqual(len(vistas), 2)                                       # lo de otra provincia, no
        self.assertEqual(et["u1"]["plazo"], {"n": 10, "unidad": "habiles", "hasta": "2026-11-11"})
        self.assertNotIn("plazo", et["u2"])
        self.assertEqual(et["u3"]["plazo"]["hasta"], "2026-09-17")              # sin el 8 ni el 10 de septiembre (fiestas de Adra)
        self.assertEqual(set(vistas[0]["questions"]), set(vistas[0]["state"]["frases"]))     # una pregunta por frase
        self.assertEqual(sas.plazos(d, et, red=red, pedir_jev=lambda c, t: self.fail("ya tienen plazo")), 0)
        a = sas.avisar(d, et, hoy=dt.date(2026, 10, 29))
        self.assertEqual([(x["url"], x["hasta"]) for x in a], [("u1", "2026-11-11")])     # la de plazo acabado, no
        # Jev no está seguro: plazo None (no se vuelve a preguntar)
        et2 = {"u1": {"tipo": "convocatoria", "zona": "almeria"}}
        sas.plazos(d[:1], et2, red=red, pedir_jev=lambda c, t: {"answers": {k: noul(0.55) for k in c["state"]["frases"]}})
        self.assertIsNone(et2["u1"]["plazo"])
        et3 = {"u1": {"tipo": "convocatoria", "zona": "almeria"}}                 # dos frases seguras: tampoco
        sas.plazos(d[:1], et3, red=red, pedir_jev=lambda c, t: {"answers": {k: noul(0.9) for k in c["state"]["frases"]}})
        self.assertIsNone(et3["u1"]["plazo"])
        n = A.ofertas({"empleo:sas:": "2026-10-28", "empleo:sae:": "2026-10-28", "empleo:junta:": "2026-10-28", "fap:": "2026-10-28"}, [],
                      {"sas": {"avisar": [x | {"resumen": "PRUEBA: convoca concurso"} for x in a]}}, AHORA)
        self.assertTrue(n[0]["texto"].endswith("· solicitudes hasta el 11 nov."), n[0]["texto"])


class Fap(unittest.TestCase):
    """3.8: las novedades de barco dragón de la Federación Andaluza (sus listas reales del 29 oct, recortadas; Jev, de mentira)."""
    def avisos(self):
        return fap.circulares(muestra("fap_circulares_20261029.html")) + fap.noticias(muestra("fap_noticias_20261029.html"))

    def test_listas(self):
        c = fap.circulares(muestra("fap_circulares_20261029.html"))
        self.assertEqual(len(c), 12); self.assertEqual(c[0]["enlace"], "https://fapira.com/files/2026/CIRCULARES/C-2926.pdf")
        n = fap.noticias(muestra("fap_noticias_20261029.html"))
        self.assertEqual([x["fecha"] for x in n], ["2026-09-29", "2026-09-24"]); self.assertTrue(n[0]["resumen"].startswith("Cinco deportistas"))
        self.assertEqual(fap.titulo_limpio("CIRCULAR Nº 26/2026 - NORMATIVA CAMPEONATO DE ANDALUCÍA DE BARCO DRAGÓN 500m"),
                         "Normativa Campeonato de Andalucía de Barco Dragón 500 m")
        self.assertEqual(fap.datos_texto(muestra("fap_c2626_tabla.txt")), {"dia": "2026-10-31", "lugar": "C.E.A.R. La Cartuja (Sevilla)", "inscripcion": "2026-10-27"})

    def test_juzgar_y_novedades(self):
        av = self.avisos() + [{"tipo": "noticia", "titulo": "PRUEBA: Fulano Mengano, campeón en barco dragón", "enlace": "https://fapira.com/prueba-1",
                               "fecha": "2026-10-20", "resumen": ""},
                              {"tipo": "noticia", "titulo": "PRUEBA: Aplazado el Campeonato de Andalucía de Barco Dragón de invierno", "enlace": "https://fapira.com/prueba-2",
                               "fecha": "2026-10-21", "resumen": "Se celebrará en otra fecha."}]
        vistas = []
        def pedir(cu, t):
            a = cu["state"]["aviso"]; vistas.append(a["titulo"])
            dragon = "DRAG" in a["titulo"].upper()
            return {"answers": {"anuncia": noul(0.9 if dragon and "campeón" not in a["titulo"] else 0.1), "cambio": noul(0.9 if "Aplazado" in a["titulo"] else 0.05),
                                "persona": noul(0.95 if "Fulano" in a["titulo"] else 0.02)}}
        pdfs = []
        j, juez = fap.juzgar(av, {}, pedir_jev=pedir, red=lambda u: pdfs.append(u) or b"%PDF", leer_pdf=lambda b: fap.datos_texto(muestra("fap_c2626_tabla.txt")))
        self.assertEqual(juez, "Jev"); self.assertEqual(len(vistas), len(av))
        self.assertEqual(pdfs, ["https://fapira.com/files/2026/CIRCULARES/C-2626.pdf"])
        self.assertTrue(all(len(k) == 12 and "/" not in k for k in j))         # por un resumen del enlace (no el título)
        nv = fap.novedades(av, j)
        self.assertEqual([n["titulo"] for n in nv], ["PRUEBA: Aplazado el Campeonato de Andalucía de Barco Dragón de invierno",
                                                     "Normativa Campeonato de Andalucía de Barco Dragón 500 m",
                                                     "Cinco palistas del Náutico Sevilla, en el Mundial de Barco Dragón"])
        self.assertNotIn("Fulano", json.dumps(nv, ensure_ascii=False))       # el que nombra a alguien, no
        self.assertTrue(nv[0]["cambio"]); self.assertEqual(nv[1]["dia"], "2026-10-31")
        # otra vez: nada se pregunta
        self.assertEqual(fap.juzgar(av, j, pedir_jev=lambda c, t: self.fail("ya juzgado"))[0], j)
        # sin Jev: solo las circulares que dicen «dragón»
        def p403(c, t): raise error(403)
        j2, juez2 = fap.juzgar(av, {}, pedir_jev=p403, red=lambda u: b"", leer_pdf=lambda b: {})
        self.assertTrue(juez2.startswith("sin Jev"))
        self.assertEqual([n["enlace"] for n in fap.novedades(av, j2)], ["https://fapira.com/files/2026/CIRCULARES/C-2626.pdf"])

    def test_al_movil(self):
        x = {"fap": {"novedades": [{"tipo": "circular", "titulo": "Normativa Campeonato de Andalucía de Barco Dragón 500 m", "enlace": "https://x/c26",
                                    "fecha": "2026-10-08", "cambio": False, "dia": "2026-10-31", "lugar": "C.E.A.R. La Cartuja (Sevilla)", "inscripcion": "2026-10-27"}]}}
        marcas = {"empleo:sae:": "2026-10-28", "empleo:junta:": "2026-10-28", "empleo:sas:": "2026-10-28"}
        e = dict(marcas)
        self.assertEqual(A.ofertas(e, [], x, AHORA), []); self.assertIn("fap:", e)          # la primera vez, solo se apunta
        x["fap"]["novedades"].insert(0, {"tipo": "noticia", "titulo": "PRUEBA: Aplazado el Campeonato", "enlace": "https://x/p", "fecha": "2026-10-28",
                                         "cambio": True, "dia": "2026-11-14"})
        n = A.ofertas(e, [], x, AHORA)
        self.assertEqual([o["clave"] for o in n], ["fap:https://x/p"])
        self.assertEqual(n[0]["texto"], "🐉 Barco dragón (Federación Andaluza, cambio): PRUEBA: Aplazado el Campeonato · sábado 14 nov.")
        self.assertIn("anuncia", jev.preguntas_fap()); self.assertIn("persona", jev.preguntas_fap())


class Urgentes(unittest.TestCase):
    """3.8: las noticias urgentes del pueblo (Jev, en la misma petición que el corte)."""
    RSS = """<rss><channel>
<item><title>PRUEBA: Desalojadas varias viviendas en Adra por un incendio forestal</title><description>…</description><link>https://x/u1</link><pubDate>Wed, 28 Oct 2026 09:00:00 +0100</pubDate></item>
<item><title>PRUEBA: Adra presenta su programación de Navidad</title><description>…</description><link>https://x/u2</link><pubDate>Wed, 28 Oct 2026 10:00:00 +0100</pubDate></item>
<item><title>PRUEBA: Corte de agua en Adra el jueves</title><description>…</description><link>https://x/u3</link><pubDate>Wed, 28 Oct 2026 10:30:00 +0100</pubDate></item>
<item><title>PRUEBA: Incendio en Adra la semana pasada</title><description>…</description><link>https://x/u4</link><pubDate>Mon, 26 Oct 2026 08:00:00 +0100</pubDate></item>
</channel></rss>"""

    def test_urgentes(self):
        def pedir(cu, t):
            tit = cu["state"]["noticia"]["titulo"]; corte = "Corte" in tit
            return {"answers": {"anuncia": noul(0.95 if corte else 0.02), "tipo": choice("agua" if corte else "otro"), "en_pueblo": noul(0.9),
                                "restablecido": noul(0.0), "dia": choice("not_stated"), "mes": choice("not_stated"),
                                "urgente": noul(0.92 if "ncendio" in tit else 0.6 if corte else 0.05)}}
        juez = A.Juez(pedir)
        c = A.cortes_rss(self.RSS, "Adra", AHORA - dt.timedelta(days=3), juez, AHORA)
        self.assertEqual([x["enlace"] for x in c], ["https://x/u3"])
        self.assertEqual([u["enlace"] for u in juez.urgentes], ["https://x/u1"])          # la de hace dos días ya no; el corte va aparte
        self.assertIn("urgente", jev.preguntas_corte()); self.assertIn("urgente", jev.preguntas_titular())
        juez2 = A.Juez(lambda cu, t: {"answers": {k: v for k, v in pedir(cu, t)["answers"].items() if k != "urgente"}})   # respuesta vieja
        A.cortes_rss(self.RSS, "Adra", AHORA - dt.timedelta(days=3), juez2, AHORA); self.assertEqual(juez2.urgentes, [])


if __name__ == "__main__":
    unittest.main()
