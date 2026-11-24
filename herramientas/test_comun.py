"""comun.py: lo que comparten los scripts. PRUEBA: la red, de mentira (ninguna prueba sale a internet)."""
import contextlib, datetime as dt, io, json, os, shutil, sys, tempfile, unittest, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras")


class Respuesta:
    def __init__(self, cuerpo=b"hola", cabeceras=None): self.cuerpo, self.headers = cuerpo, cabeceras or {}
    def read(self): return self.cuerpo
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Red:
    """urlopen de mentira: va dando, por orden, lo que se le dice (una respuesta o un fallo) y apunta lo que se le pide."""
    def __init__(self, *pasos): self.pasos, self.vistas = list(pasos), []

    def __call__(self, req, timeout=None):
        self.vistas.append((req.get_method(), req.full_url, dict(req.header_items()), req.data, timeout))
        p = self.pasos.pop(0)
        if isinstance(p, Exception): raise p
        return p


def error(codigo): return urllib.error.HTTPError("https://prueba.invalid/", codigo, "x", {}, io.BytesIO(b""))


class Peticiones(unittest.TestCase):
    def con(self, red):
        orig = comun.urllib.request.urlopen
        comun.urllib.request.urlopen = red
        self.addCleanup(setattr, comun.urllib.request, "urlopen", orig)
        return red

    def test_reintenta_cortes_429_y_5xx(self):
        red = self.con(Red(urllib.error.URLError("corte"), error(503), Respuesta(b"bien")))
        esperas = []
        self.assertEqual(comun.pedir("https://prueba.invalid/", pausa=2, dormir=esperas.append), b"bien")
        self.assertEqual((len(red.vistas), esperas), (3, [2, 4]))                     # la espera crece
        red = self.con(Red(error(429), TimeoutError(), ConnectionResetError()))
        with self.assertRaises(ConnectionResetError): comun.pedir("https://prueba.invalid/", dormir=lambda s: None)
        self.assertEqual(len(red.vistas), 3)

    def test_un_4xx_no_se_reintenta(self):
        red = self.con(Red(error(404), Respuesta()))
        with self.assertRaises(urllib.error.HTTPError): comun.pedir("https://prueba.invalid/", dormir=lambda s: None)
        self.assertEqual(len(red.vistas), 1)

    def test_agente_cuerpo_y_cabeceras(self):
        red = self.con(Red(Respuesta(), Respuesta()))
        comun.pedir("https://prueba.invalid/a")
        comun.pedir("https://prueba.invalid/b", comun.UA_TAREAS, b"{}", "application/json", aceptar="application/json", timeout=7)
        (m1, _, c1, d1, t1), (m2, u2, c2, d2, t2) = red.vistas
        self.assertEqual((m1, c1, d1, t1), ("GET", {"User-agent": comun.UA_APP}, None, 60))
        self.assertEqual((m2, u2, d2, t2), ("POST", "https://prueba.invalid/b", b"{}", 7))
        self.assertEqual(c2, {"User-agent": comun.UA_TAREAS, "Content-type": "application/json", "Accept": "application/json"})

    def test_cabeceras_con_head(self):
        red = self.con(Red(error(500), Respuesta(b"", {"Last-Modified": "Mon, 02 Nov 2026 10:00:00 GMT"})))
        c = comun.cabeceras("https://prueba.invalid/grande.pdf", comun.UA_CORTO, dormir=lambda s: None)
        self.assertEqual(c.get("Last-Modified"), "Mon, 02 Nov 2026 10:00:00 GMT")
        self.assertEqual([v[0] for v in red.vistas], ["HEAD", "HEAD"])


class Textos(unittest.TestCase):
    def test_limpio(self):
        self.assertEqual(comun.limpio(" <p>Feria&nbsp;del <b>libro</b>\n de&amp;Adra</p> "), "Feria del libro de&Adra")
        self.assertEqual(comun.limpio(None), "")

    def test_sin_tildes_y_solo_ascii(self):
        self.assertEqual(comun.sin_tildes("ALBUÑOL · Níjar"), "albunol · nijar")       # sin tildes, pero lo demás se queda
        self.assertEqual(comun.solo_ascii("ALBUÑOL · Níjar 1.º"), "albunol  nijar 1.")   # lo que no es ASCII, fuera
        self.assertEqual(comun.sin_tildes(None), "")

    def test_num(self):
        self.assertEqual((comun.num("1.234,5"), comun.num("64"), comun.num("0,71")), (1234.5, 64.0, 0.71))

    def test_enlace_limpio(self):
        self.assertEqual(comun.enlace_limpio(" https://www.instagram.com/p/XXXX/?igsh=abc "), "https://www.instagram.com/p/XXXX/")
        self.assertEqual(comun.enlace_limpio("https://www.adra.es/agenda?id=3"), "https://www.adra.es/agenda?id=3")

    @unittest.skipUnless(shutil.which("pdftotext"), "sin pdftotext (poppler)")
    def test_texto_pdf(self):
        with open(os.path.join(M, "agenda_2026.pdf"), "rb") as f: datos = f.read()
        self.assertIn("Agenda Astron", comun.texto_pdf(datos))
        self.assertIn("Agenda Astron", comun.texto_pdf(datos, "-layout", "-l", "2", tiempo=60))
        self.assertEqual(comun.texto_pdf(b"esto no es un PDF", comprobar=False), "")
        with self.assertRaises(Exception): comun.texto_pdf(b"esto no es un PDF")


class Sitios(unittest.TestCase):
    def test_hoy_es_el_de_espana(self):
        a = comun.ahora()
        self.assertEqual(a.tzinfo, comun.TZ)
        self.assertLessEqual(abs((comun.hoy() - a.date()).days), 1)

    def test_km(self):
        almeria = (36.8381, -2.4597)
        self.assertTrue(48 <= comun.km(comun.ADRA, almeria) <= 53)
        self.assertEqual(comun.km(comun.ADRA, comun.ADRA), 0)

    def test_municipios(self):
        m = comun.municipios()
        self.assertEqual(len(m), 103)                                                  # los de la provincia de Almería
        self.assertEqual([x[0] for x in m if x[1] == comun.INE], [comun.LUGAR])
        c = comun.coordenadas()
        self.assertTrue(comun.km(comun.ADRA, c["adra"]) < 2 and "nijar" in c and "huercal-overa" in c)


class Extras(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d)
        self.ruta = os.path.join(self.d, "extras.json")

    def test_guardar_entero_y_sin_restos(self):
        comun.guardar(self.ruta, {"b": "ñ", "a": 1})
        with open(self.ruta, encoding="utf-8") as f: self.assertEqual(f.read(), '{\n "b": "ñ",\n "a": 1\n}')
        comun.guardar(self.ruta, {"b": 2, "a": 1}, sort_keys=True)
        self.assertEqual(list(comun.leer(self.ruta)), ["a", "b"])
        with self.assertRaises(TypeError): comun.guardar(self.ruta, {"no": {1, 2}})    # si falla a medias, queda el de antes
        self.assertEqual(comun.leer(self.ruta), {"a": 1, "b": 2})
        self.assertEqual(os.listdir(self.d), ["extras.json"])

    def test_publicar_pone_la_hora(self):
        x = {"cortes": []}
        comun.publicar(self.ruta, x)
        g = comun.leer(self.ruta)
        self.assertEqual(g, x)
        self.assertLess(abs((dt.datetime.fromisoformat(g["actualizado"]) - comun.ahora()).total_seconds()), 120)
        comun.publicar(self.ruta, x, dt.datetime(2026, 11, 15, 9, 30, tzinfo=comun.TZ))
        self.assertEqual(comun.leer(self.ruta)["actualizado"], "2026-11-15T09:30+01:00")

    def test_poner_solo_si_cambia(self):
        x = {"polen": {"dia": "2026-11-01"}, "actualizado": "antes"}
        comun.guardar(self.ruta, x)
        self.assertFalse(comun.poner(self.ruta, x, "polen", {"dia": "2026-11-01"}))
        self.assertEqual(comun.leer(self.ruta)["actualizado"], "antes")                # lo mismo: ni se toca el fichero ni su hora
        self.assertTrue(comun.poner(self.ruta, x, "polen", {"dia": "2026-11-02"}))
        g = comun.leer(self.ruta)
        self.assertEqual(g["polen"], {"dia": "2026-11-02"}); self.assertNotEqual(g["actualizado"], "antes")

    def test_recordar_fuera_de_extras(self):
        estado = os.path.join(self.d, comun.ESTADO)
        x = {"ayudas": {"lista": []}, "ayudasCerradas": ["1", "2"]}                    # como iba hasta el 15 nov 2026: dentro de extras.json
        self.assertEqual(comun.recuerdo(self.ruta, x, "ayudasCerradas"), ["1", "2"])    # sin estado todavía, vale el de extras.json
        self.assertIsNone(comun.recuerdo(self.ruta, x, "sendaAdra"))
        self.assertTrue(comun.recordar(self.ruta, x, "ayudasCerradas", ["1", "2", "3"]))   # lo quita de extras.json: hay que publicarlo
        self.assertEqual(x, {"ayudas": {"lista": []}}); self.assertEqual(comun.leer(estado), {"ayudasCerradas": ["1", "2", "3"]})
        self.assertEqual(comun.recuerdo(self.ruta, x, "ayudasCerradas"), ["1", "2", "3"])
        antes = os.stat(estado).st_mtime_ns
        self.assertFalse(comun.recordar(self.ruta, x, "ayudasCerradas", ["1", "2", "3"]))  # lo mismo: no se toca nada
        self.assertEqual(os.stat(estado).st_mtime_ns, antes)
        self.assertFalse(comun.recordar(self.ruta, x, "sendaAdra", {"pdf": "p"}))          # otra clave: se añade a la que había
        self.assertEqual(comun.leer(estado), {"ayudasCerradas": ["1", "2", "3"], "sendaAdra": {"pdf": "p"}})
        with open(estado, "w") as f: f.write("{roto")                                   # un estado ilegible es como no tenerlo
        self.assertIsNone(comun.recuerdo(self.ruta, {}, "sendaAdra"))

    def test_extras_v_lo_dice_la_pagina_y_espera(self):
        pag = os.path.join(self.d, "index.html")
        d = lambda n: dt.date(2026, 11, n)
        self.assertEqual(comun.extras_v(self.ruta, d(15), pag), 1)                      # sin página (o sin la marca): como siempre
        with open(pag, "w", encoding="utf-8") as f: f.write("<script>\nconst ORDEN_V = 3;\n</script>")
        self.assertEqual(comun.extras_v(self.ruta, d(15), pag), 1)
        self.assertFalse(os.path.exists(os.path.join(self.d, comun.ESTADO)))            # y sin apuntar nada
        with open(pag, "w", encoding="utf-8") as f: f.write("<script>\nconst EXTRAS_V = 2;   // lo que entiende\n</script>")
        self.assertEqual(comun.extras_v(self.ruta, d(16), pag), 1)                      # recién publicada: la tele aún puede ir con la de antes
        self.assertEqual(comun.extras_v(self.ruta, d(22), pag), 1)
        self.assertEqual(comun.extras_v(self.ruta, d(23), pag), 2)                      # a la semana, sí
        self.assertEqual(comun.leer(os.path.join(self.d, comun.ESTADO)), {"extrasV": {"v": 2, "antes": 1, "vale": "2026-11-23"}})
        with open(pag, "w", encoding="utf-8") as f: f.write("const EXTRAS_V = 3;")
        self.assertEqual(comun.extras_v(self.ruta, d(25), pag), 2)                      # otra más nueva: mientras espera, la que ya valía
        self.assertEqual(comun.extras_v(self.ruta, dt.date(2026, 12, 2), pag), 3)

    def test_sin_enlaces_deducibles(self):
        base = "https://www.prueba.invalid/cursos"
        L = [{"id": "411", "enlace": base + "/411"}, {"id": "86", "enlace": "https://otra.invalid/86"}, {"id": "7"}, {"id": "9", "enlace": base}]
        self.assertEqual(comun.sin_enlaces_deducibles(L, base, "id"), [{"id": "411"}, {"id": "86", "enlace": "https://otra.invalid/86"}, {"id": "7"}, {"id": "9", "enlace": base}])

    def test_decir_una_linea(self):
        s = io.StringIO()
        with contextlib.redirect_stdout(s): comun.decir({"cursos": 3, "fuente": "Formación"})
        self.assertEqual(s.getvalue(), '{"cursos": 3, "fuente": "Formación"}\n')
        self.assertEqual(json.loads(s.getvalue()), {"cursos": 3, "fuente": "Formación"})

    def test_fallar_lo_dice_y_sale(self):
        s = io.StringIO()
        with contextlib.redirect_stdout(s), self.assertRaises(SystemExit) as c: comun.fallar(ValueError("la relación no se ha podido leer " + "x" * 300))
        self.assertEqual(c.exception.code, 1)
        self.assertEqual(list(json.loads(s.getvalue())), ["error"]); self.assertEqual(len(json.loads(s.getvalue())["error"]), 200)



class TurismoAlmeria(unittest.TestCase):
    """24 nov 2026: la API de Turismo de Almería, una vez al día para actividades.py y espectaculos.py (respuestas de PRUEBA)."""
    def test_todas_las_paginas_y_una_vez(self):
        pedidas = []
        def pedir(u, timeout=60):
            pedidas.append(u)
            if "events" in u:
                n = int(u.rsplit("page=", 1)[1])
                return json.dumps({"data": [{"id": n}], "pagination": {"total_pages": 3}}).encode()
            return json.dumps({"data": [{"id": "l1"}]}).encode()
        with tempfile.TemporaryDirectory() as d:
            c = os.path.join(d, "t.json")
            ev, lu = comun.turismo_almeria(pedir, lambda s: None, cache=c)
            self.assertEqual([e["id"] for e in ev], [1, 2, 3]); self.assertEqual(lu, [{"id": "l1"}]); self.assertEqual(len(pedidas), 4)
            self.assertEqual(comun.turismo_almeria(pedir, lambda s: None, cache=c), (ev, lu)); self.assertEqual(len(pedidas), 4)   # de la caché
            self.assertEqual(len(comun.turismo_almeria(pedir, lambda s: None, maximo=2, cache=os.path.join(d, "u.json"))[0]), 2)


if __name__ == "__main__":
    unittest.main()
