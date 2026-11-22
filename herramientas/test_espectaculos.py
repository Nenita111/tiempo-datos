"""Pruebas de espectaculos.py con respuestas reales del 22 nov 2026 (prueba_espectaculos_20261122.json, recortadas)."""
import contextlib, datetime as dt, io, json, os, re, shutil, sys, tempfile, unittest, unittest.mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import espectaculos as E, comun

AQUI = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(AQUI, "prueba_espectaculos_20261122.json"), encoding="utf-8"))
HOY = dt.date(2026, 11, 22)


class Espectaculos(unittest.TestCase):
    def test_turismo_almeria(self):
        t = {p["titulo"]: p for p in E.turismo_almeria(F["turismoEventos"], F["turismoLugares"], HOY)}
        n = t["Concierto: Nixon en Almería"]
        self.assertEqual((n["fecha"], n["hora"], n["tipo"], n["lugar"], n["precio"]), ("2026-11-28", "21:30", "Concierto", "Berlin Social Club", "19,80 €"))
        self.assertEqual(t["El Cascanueces. Ballet Clásico Internacional"]["tipo"], "Danza")
        self.assertTrue(t["Banda Municipal de Almería: Una mirada a nuestros solistas (3)"].get("gratis"))
        self.assertTrue(t["Chanqueños pa Belén en familia"].get("infantil"))
        # el título no dice de qué es: en un auditorio o un teatro, «Espectáculo»
        self.assertEqual(t["Sara Baras Infinita"]["tipo"], "Espectáculo")
        # ni el cine ni las exposiciones
        self.assertFalse(any("xposici" in k for k in t))
        self.assertEqual(len(t), 6)

    def test_roquetas(self):
        r = E.roquetas(F["roquetasMusica"], "musica", HOY)
        self.assertEqual(r[0], {"titulo": "Día Internacional del Flamenco", "fecha": "2026-11-27", "tipo": "Flamenco", "hora": "21:00",
                                "lugar": "Teatro Auditorio de Roquetas", "municipio": "Roquetas de Mar",
                                "enlace": r[0]["enlace"], "fuente": "Ayuntamiento de Roquetas de Mar"})
        # sin «Música:» delante; dos sesiones el mismo día, una sola fila con sus dos horas
        j = [p for p in E.juntar(r) if p["titulo"] == "Así canta Jerez en navidad"]
        self.assertEqual([(p["fecha"], p["hora"]) for p in j], [("2026-12-18", "20:00 y 22:30")])
        # lo de más de 60 días, todavía no
        self.assertTrue(all(p["fecha"] <= "2027-01-21" for p in r))

    def test_ejido(self):
        portada = E.ejido_portada(F["ejidoPortada"])
        fechas = {u: E.ejido_fecha(t) for u, t in F["ejidoFichas"].items()}
        e = {p["titulo"]: p for p in E.ejido(portada, fechas, HOY)}
        p = e["Luis Piedrahita «Apocalípticamente correcto»"]
        self.assertEqual((p["fecha"], p["hora"], p["lugar"]), ("2026-12-11", "21:00", "Auditorio de El Ejido"))
        # la productora o la lista de delante, fuera del título («Música – Mulhacén Producciones…», «Gala especial – Magia…»)
        self.assertEqual(e["Mulhacén Producciones «Amor en los 80: La chica de ayer»"]["tipo"], "Concierto")
        self.assertEqual(e["Magia para todos «MagicDuo»"]["tipo"], "Magia")
        self.assertEqual(e["Candileja musicales para todos «Dumbo, el musical»"]["tipo"], "Musical")
        # el cine, los talleres y las visitas, no
        self.assertFalse(any(re.search(r"cine|taller|visita", k, re.I) for k in e))
        self.assertFalse(E.candidato_ejido("Visitas guiadas al Yacimiento de Ciavieja – «De guía una arqueóloga» – Sábado, 28 de noviembre"))

    def test_motril(self):
        m = E.motril(F["motril"], HOY)
        self.assertTrue(m and all(p["municipio"] == "Motril" for p in m))
        self.assertFalse(any(p["titulo"].lower().startswith("cine") for p in m))
        self.assertTrue(all(not p.get("hora") or re.fullmatch(r"\d\d:\d\d", p["hora"]) for p in m))

    def test_tipos(self):
        self.assertEqual(E.tipo_de("Concierto Especial de Navidad «Raíz», de la Agrupación Musical"), "Concierto")
        self.assertEqual(E.tipo_de("COCO, el musical"), "Musical")
        self.assertEqual(E.tipo_de("Stand up comedy Artenvacío: Luis Álvaro"), "Humor")
        self.assertIsNone(E.tipo_de("Presentación de un libro", sala="Biblioteca"))
        self.assertIsNone(E.fila("Taller de teatro", HOY, HOY))
        self.assertEqual(E.hora_motril("21 h"), "21:00")

    def test_main_deja_lo_de_la_fuente_que_falla(self):
        d = tempfile.mkdtemp()
        try:
            ruta = os.path.join(d, "extras.json")
            viejo = {"titulo": "Algo de Motril", "fecha": "2026-12-01", "tipo": "Teatro", "municipio": "Motril", "fuente": "Motril Turismo"}
            pasado = dict(viejo, titulo="Ya pasó", fecha="2026-11-01")
            comun.guardar(ruta, {"espectaculos": {"lista": [viejo, pasado], "fuentes": ["Motril Turismo"]}})
            portada = F["ejidoPortada"]

            def pedir(u, **k):
                if "eventon-api" in u: return json.dumps({"data": F["turismoEventos"], "pagination": {"total_pages": 1}}).encode()
                if "evenlocation" in u: return json.dumps({"data": F["turismoLugares"]}).encode()
                if "farocultural" in u: return (F["roquetasMusica"] if u.endswith("/musica") else "").encode()
                if u == E.EJIDO + "/": return portada.encode()
                if "ai1ec_event=" in u: return F["ejidoFichas"].get(u, "").encode()
                raise OSError("sin red")
            with unittest.mock.patch.object(comun, "pedir", pedir), unittest.mock.patch.object(comun, "hoy", lambda: HOY), \
                 unittest.mock.patch.object(E.time, "sleep", lambda s: None), unittest.mock.patch.object(sys, "argv", ["x", ruta]), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                E.main()
            r = json.loads(out.getvalue().strip().splitlines()[-1])
            self.assertEqual(r["fallos"][0][:15], "Motril Turismo:")
            x = comun.leer(ruta)
            L = x["espectaculos"]["lista"]
            self.assertIn(viejo, L)
            self.assertNotIn(pasado, L)
            self.assertEqual(L, sorted(L, key=lambda p: (p["fecha"], p.get("hora") or "", p["titulo"])))
            # las fechas de El Ejido, en estado_diario.json (no en extras.json)
            self.assertNotIn("fechasEjido", x)
            self.assertTrue(comun.recuerdo(ruta, x, "fechasEjido"))
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
