"""puente.py: el próximo puente y sus vuelos (15 nov 2026). El calendario (muestras/calendario_adra_2026.json) y la respuesta de Kiwi
(muestras/kiwi_puente_LEI_20261115.json) son los de verdad; PRUEBA: la red (de mentira) y el día de hoy."""
import contextlib, datetime as dt, io, json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun, diario, puente, sas, vuelos

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras")
CAL = open(os.path.join(M, "calendario_adra_2026.json"), encoding="utf-8").read()
KIWI = comun.leer(os.path.join(M, "kiwi_puente_LEI_20261115.json"))
D = dt.date


def red(url):
    """El calendario de 2026; el de 2027, «aún sin publicar»."""
    if "year=2026" in url: return CAL
    raise OSError("sin publicar (PRUEBA)")


FEST = sas.festivos([2026], red)


class Puentes(unittest.TestCase):
    def test_nombre(self):
        self.assertEqual(puente.nombre("DÍA DE LA CONSTITUCIÓN ESPAÑOLA"), "Día de la Constitución Española")
        self.assertEqual(puente.nombre("FIESTA LOCAL EN ADRA (ALMERÍA)"), "Fiesta Local en Adra (Almería)")
        self.assertEqual(puente.nombre("LA INMACULADA"), "La Inmaculada")

    def test_los_de_2026(self):
        p = [(a.isoformat()[5:], b.isoformat()[5:], len(f), [x.isoformat()[5:] for x in lab]) for a, b, f, lab in puente.puentes(FEST, D(2026, 1, 1), D(2026, 12, 31))]
        self.assertEqual(p, [("01-01", "01-04", 1, ["01-02"]),      # Año Nuevo en jueves: con el viernes de puente
                             ("01-03", "01-06", 1, ["01-05"]),      # Reyes en martes: con el lunes
                             ("04-02", "04-05", 2, []),             # Jueves y Viernes Santo
                             ("05-01", "05-03", 1, []),
                             ("09-05", "09-08", 1, ["09-07"]),      # fiestas de Adra, martes y jueves: dos puentes, no uno de nueve días
                             ("09-10", "09-13", 1, ["09-11"]),
                             ("10-10", "10-12", 1, []), ("10-31", "11-02", 1, []),
                             ("12-05", "12-08", 2, []),             # Constitución (pasada al lunes) e Inmaculada
                             ("12-25", "12-27", 1, [])])
        # el Día de Andalucía (sábado 28 feb) y la Asunción (sábado 15 ago) no dan puente; un fin de semana cualquiera, tampoco
        self.assertEqual(puente.puentes({}, D(2026, 1, 1), D(2026, 12, 31)), [])

    def test_el_proximo(self):
        p = puente.proximo(FEST, D(2026, 11, 15))
        self.assertEqual(p, {"desde": "2026-12-05", "hasta": "2026-12-08", "fuente": puente.FUENTE,
                             "festivos": [{"fecha": "2026-12-07", "nombre": "Día de la Constitución Española"}, {"fecha": "2026-12-08", "nombre": "Inmaculada Concepción"}]})
        self.assertEqual(puente.proximo(FEST, D(2026, 12, 1))["desde"], "2026-12-05")      # a 4 días: aún se puede salir la víspera con 3 de antelación
        self.assertEqual(puente.proximo(FEST, D(2026, 12, 2))["desde"], "2026-12-25")      # a 3: el siguiente
        self.assertEqual(puente.proximo(FEST, D(2026, 8, 20))["laborables"], ["2026-09-07"])
        self.assertIsNone(puente.proximo(FEST, D(2026, 12, 22)))                           # sin el calendario de 2027, nada a la vista
        self.assertIsNone(puente.proximo(FEST, D(2026, 5, 2)))                             # el siguiente (5 sep) queda a más de 120 días

    def test_toca_una_vez_a_la_semana(self):
        p = puente.proximo(FEST, D(2026, 11, 15)); fechas = {"ida": ["04/12/2026", "05/12/2026"], "vuelta": ["07/12/2026", "08/12/2026"]}
        self.assertIsNone(puente.toca({}, D(2026, 11, 15)))
        self.assertEqual(puente.toca({"puente": p}, D(2026, 11, 15)), fechas)
        self.assertIsNone(puente.toca({"puente": dict(p, buscado="2026-11-15")}, D(2026, 11, 21)))
        self.assertEqual(puente.toca({"puente": dict(p, buscado="2026-11-15")}, D(2026, 11, 22)), fechas)
        self.assertIsNone(puente.toca({"puente": p}, D(2026, 12, 2)))                      # ya no da tiempo: salida a menos de 3 días
        self.assertEqual(diario.toca({"puente": p, "vuelosBuscado": "2026-11-15"}, D(2026, 11, 15)), {"vuelos": False, "web": False, "puente": fechas})
        self.assertEqual(diario.toca({"vuelosBuscado": "2026-11-15"}, D(2026, 11, 16)), {"vuelos": True, "web": True})

    def test_los_vuelos_del_puente(self):
        p = puente.proximo(FEST, D(2026, 11, 15))
        b = puente.del_puente(p, [KIWI])
        self.assertEqual(sorted(b), ["LEI"]); self.assertEqual(len(b["LEI"]), 7)
        a = vuelos.aeropuertos(b)
        self.assertEqual([(v["destino"], v["ida"], v["vuelta"], v["precio"]) for v in a[0]["vuelos"]][:2],
                         [("Sevilla", "2026-12-04", "2026-12-07", 133), ("Madrid", "2026-12-05", "2026-12-07", 172)])
        self.assertEqual(len(a[0]["vuelos"]), 6); self.assertTrue(all(v["escalas"] == "directo" and v["enlace"].startswith("https://kiwi.com/") for v in a[0]["vuelos"]))
        # los de otros días no entran (los de este puente no valen para el de Navidad), ni los de una sola noche o con escalas
        self.assertEqual(puente.del_puente(puente.proximo(FEST, D(2026, 12, 2)), [KIWI]), {})
        raro = json.loads(json.dumps(KIWI)); i = raro["itineraries"]
        i[0]["outbound"]["stops"] = 1                                                      # PRUEBA: con una escala
        i[1]["inbound"]["departureTime"] = "2026-12-06T10:00:00"                           # PRUEBA: vuelta antes de tiempo
        del i[2]["inbound"]                                                                # PRUEBA: solo ida
        self.assertEqual(len(puente.del_puente(p, [raro])["LEI"]), 4)
        # dos respuestas con la misma ciudad: la más barata
        otra = json.loads(json.dumps(KIWI)); otra["itineraries"] = otra["itineraries"][:1]; otra["itineraries"][0]["price"] = 120   # PRUEBA
        self.assertEqual(min(v["precio"] for v in puente.del_puente(p, [KIWI, otra])["LEI"]), 120)
        self.assertEqual(min(v["precio"] for v in puente.del_puente(p, [otra, KIWI])["LEI"]), 120)

    def test_la_busqueda_del_puente_no_pisa_la_de_cada_dia(self):
        with tempfile.TemporaryDirectory() as d:
            normal = dict(KIWI, query="LEI → Europe on 18/11/2026–20/12/2026, 1 adult, 2–5 nights [≤0 stops/sector; one per city]", itineraries=KIWI["itineraries"][:2])
            with open(os.path.join(d, "a.jsonl"), "w", encoding="utf-8") as f:
                for r in (normal, KIWI): f.write(json.dumps({"toolUseResult": json.dumps(r)}) + "\n")
            self.assertEqual(len(vuelos.de_la_sesion(raiz=d)["LEI"]), 2)                   # la del puente («returning») vino después y no cuenta
            self.assertEqual(len(list(vuelos.respuestas(raiz=d))), 2)


class Paso(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        self.ruta = os.path.join(d, "extras.json")
        comun.guardar(self.ruta, {"cortes": [], "actualizado": "2026-11-14T06:12+01:00"})
        for mod, nombre, valor in ((sas, "pedir", red), (comun, "hoy", lambda: self.hoy), (vuelos, "respuestas", lambda: [KIWI])):
            self.addCleanup(setattr, mod, nombre, getattr(mod, nombre)); setattr(mod, nombre, valor)
        self.hoy = D(2026, 11, 15)

    def correr(self, *opc):
        argv = sys.argv; sys.argv = ["puente.py", self.ruta, *opc]; s = io.StringIO()
        try:
            with contextlib.redirect_stdout(s): puente.main()
        finally: sys.argv = argv
        return s.getvalue().strip(), comun.leer(self.ruta)

    def test_de_un_dia_para_otro(self):
        dicho, x = self.correr()
        self.assertEqual(json.loads(dicho), {"puente": "2026-12-05/2026-12-08", "festivos": ["Día de la Constitución Española", "Inmaculada Concepción"], "vuelos": 0, "buscado": None})
        self.assertNotIn("aeropuertos", x["puente"]); self.assertNotEqual(x["actualizado"], "2026-11-14T06:12+01:00")
        dicho, x = self.correr("--sesion")
        self.assertEqual(dicho, "Puente del 2026-12-05 al 2026-12-08: Almería 6")
        self.assertEqual((x["puente"]["buscado"], len(x["puente"]["aeropuertos"][0]["vuelos"])), ("2026-11-15", 6))
        hora = x["actualizado"]
        self.hoy = D(2026, 11, 20); dicho, x2 = self.correr()                              # el mismo puente: con sus vuelos y sin tocar el fichero
        self.assertEqual((x2, json.loads(dicho)["vuelos"]), (x, 6)); self.assertEqual(x2["actualizado"], hora)
        self.hoy = D(2026, 12, 2); dicho, x = self.correr()                                # el siguiente: sin los vuelos del anterior
        self.assertEqual((x["puente"]["desde"], x["puente"]["hasta"], "aeropuertos" in x["puente"], "buscado" in x["puente"]), ("2026-12-25", "2026-12-27", False, False))
        with self.assertRaises(SystemExit) as c: self.correr("--sesion")                   # los vuelos de la sesión son de otros días
        self.assertIn("no se toca nada", str(c.exception.code)); self.assertNotIn("aeropuertos", comun.leer(self.ruta)["puente"])
        self.hoy = D(2026, 12, 23); dicho, x = self.correr()                               # ninguno a la vista: fuera
        self.assertEqual((json.loads(dicho), "puente" in x), ({"puente": None}, False))

    def test_sin_calendario_no_se_toca_nada(self):
        _, antes = self.correr()
        sas.pedir = lambda url: (_ for _ in ()).throw(OSError("sin red (PRUEBA)"))
        s = io.StringIO()
        with contextlib.redirect_stdout(s), self.assertRaises(SystemExit) as c:
            sys.argv, argv = ["puente.py", self.ruta], sys.argv
            try: puente.main()
            finally: sys.argv = argv
        self.assertEqual(c.exception.code, 1); self.assertEqual(json.loads(s.getvalue()), {"error": "el calendario de la Junta no da los festivos de 2026"})
        self.assertEqual(comun.leer(self.ruta), antes)


if __name__ == "__main__":
    unittest.main()
