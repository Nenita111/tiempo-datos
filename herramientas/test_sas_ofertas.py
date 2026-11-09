"""sas_ofertas.py con recortes de la página oficial del SAS leída el 9 nov 2026 (muestras/sspa_ooe_*.html: el buscador y las primeras
ofertas de cada lista) y las frases del plazo de cuatro convocatorias reales (sin nombres). PRUEBA: lo que se marca así."""
import datetime as dt, os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sas, sas_ofertas as so

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muestras")
def muestra(n):
    with open(os.path.join(M, n), encoding="utf-8") as f: return f.read()

# las frases reales del plazo (convocatorias 11819, 11792, 10464 y 510), con otras frases de plazos de la misma convocatoria alrededor
PLAZOS = {
    "pb11819": "antes de la finalización del plazo de presentación de solicitudes. 4. El plazo de presentación de solicitudes y documentación "
               "correspondiente será de diez días\nhábiles, a contar desde el siguiente a la publicación de la presente convocatoria. 1. Finalizado "
               "el plazo de presentación de solicitudes, se hará pública la relación, concediendo a los excluidos un plazo de cinco días hábiles "
               "de subsanación del defecto que haya motivado la exclusión.",
    "pb11792": "PLAZO DE PRESENTACIÓN: El plazo será de 5 días hábiles, por razones de urgencia, contados desde el día siguiente al de su "
               "publicación. Contra dicha resolución se podrán presentar alegaciones en el plazo de 2 días hábiles a contar a partir del "
               "siguiente de la publicación del listado provisional en la página web del SAS.",
    "ci10464": "referidos al último día de plazo de presentación de solicitudes, y mantenerlos durante todo el proceso selectivo. El plazo de "
               "presentación de solicitudes será de diez días hábiles, contados a partir del siguiente al de publicación de la presente "
               "resolución en el Boletín Oficial de la Junta de Andalucía. concediendo a las personas interesadas un plazo de cinco días "
               "hábiles, a partir del siguiente al de la publicación para presentar alegaciones.",
    "pd510": "Plazo de presentación: Será de diez días hábiles, contados a partir del siguiente al de publicación de la presente resolución en "
             "el Boletín Oficial de la Junta de Andalucía.",
}
PDF = {"400173": "pb11819", "401108": "ci10464", "399651": "pd510", "399043": "pb11792"}


class Ofertas(unittest.TestCase):
    def test_centros_de_la_zona(self):
        cs = so.centros(muestra("sspa_ooe_pb_20261109.html"), "pb")
        self.assertEqual(len(cs), 93)
        zona = {n: so.area_de(n) for _, n, _ in cs if so.area_de(n)}
        self.assertEqual(zona, {"061 Almería Centro coordinador": "almeria", "Centro de transfusión, tejidos y células de Almería": "almeria",
                                "Distrito Almería": "almeria", "Hospital Universitario Torrecárdenas": "almeria",
                                "Distrito Poniente de Almería": "poniente", "Hospital de Poniente": "poniente",
                                "Área de gestión sanitaria Sur de Granada": "sur_granada"})
        for fuera in ("Área de gestión sanitaria Norte de Almería", "Distrito Levante-Alto Almanzora", "Hospital La Inmaculada", "Distrito Granada",
                      "Área de gestión sanitaria Nordeste Granada", "Centro de transfusión, tejidos y células de Granada", "061 Granada Centro coordinador"):
            self.assertIsNone(so.area_de(fuera), fuera)
        self.assertEqual(so.area_de("Área de gestión sanitaria Poniente de Almería"), "poniente")       # PRUEBA: si el SAS la crea
        self.assertFalse(any(s for _, _, s in cs))                                   # sin filtro, ningún centro elegido
        t = so.centros(muestra("sspa_ooe_pb_torrecardenas_20261109.html"), "pb")
        self.assertEqual([n for _, n, s in t if s], ["Hospital Universitario Torrecárdenas"])

    def test_filas(self):
        f = so.filas(muestra("sspa_ooe_pb_torrecardenas_20261109.html"))
        self.assertEqual(len(f), 5)
        self.assertEqual((f[0]["id"], f[0]["cod"], f[0]["fecha"], f[0]["boja"], len(f[0]["docs"])), ("400173", "11819", "2026-10-27", False, 1))
        self.assertEqual(f[0]["docs"][0][1], so.BASE + "/servicioandaluzdesalud/ooe_file/400173/87363/106313")
        self.assertEqual(f[0]["docs"][0][2], "Convocatoria Pública para la Provisión Temporal de un puesto de Técnico Función Administrativa opción "
                                             "Administración General para el Hospital Universitario Torrecárdenas")       # sin el «(496.39KB)»
        self.assertEqual(so.paginas(muestra("sspa_ooe_pb_torrecardenas_20261109.html")), 2)
        c = so.filas(muestra("sspa_ooe_ci_surgranada_20261109.html"))
        self.assertEqual([(x["cod"], x["fecha"], x["boja"], len(x["docs"])) for x in c],
                         [("10464", "2026-11-09", True, 1), ("10376", "2026-09-30", True, 3), ("10106", "2026-04-16", True, 5), ("9886", "2026-01-14", True, 5)])
        self.assertEqual(so.paginas(muestra("sspa_ooe_ci_surgranada_20261109.html")), 1)
        d = so.filas(muestra("sspa_ooe_pd_surgranada_20261109.html"))
        self.assertEqual((d[0]["cod"], d[0]["fecha"], d[0]["docs"][0][0]), ("510", "2026-10-15", "Convocatoria"))
        self.assertEqual(d[1]["docs"][1][0], "Resolución de adjudicación")

    def test_puesto(self):
        P = so.puesto
        self.assertEqual(P("base", "Convocatoria Pública para la Provisión Temporal de un puesto de Técnico Función Administrativa opción Administración General para el Hospital Universitario Torrecárdenas"),
                         "Técnico Función Administrativa opción Administración General")
        self.assertEqual(P("base", "Convocatoria Pública para la Provisión Temporal de 8 puestos de Médico de Familia SCCU para el AGS Sur de Granada"), "Médico de Familia SCCU (8 puestos)")
        self.assertEqual(P("base", "Oferta Acto Único para Residentes de 5 años que finalizan su formación en 2026."), "")
        ci = "Resolución de 4 de noviembre de 2026, de la Dirección General de Personal del Servicio Andaluz de Salud, por la que se convoca, mediante el sistema de concurso de méritos, la cobertura "
        self.assertEqual(P("intermedio", ci + "del puesto de cargo intermedio, próximo a quedar vacante , de Coordinador/a de Cuidados de Enfermería de la Unidad de Gestión Clínica de Ejido Norte en el Distrito Sanitario de Atención Primaria Poniente de Almería."),
                         "Coordinador/a de Cuidados de Enfermería de la Unidad de Gestión Clínica de Ejido Norte")
        self.assertEqual(P("intermedio", ci + "de cuatro puestos de cargo intermedio de Jefe/a de Equipo de Celadores en el Hospital Universitario Torrecárdenas de Almería"), "Jefe/a de Equipo de Celadores (cuatro puestos)")
        self.assertEqual(P("intermedio", ci + "de un puesto de Jefe/a de Equipo de Gestión y Servicios como encargo complementario de funciones para la Unidad de Gestión Clínica de Almuñécar en el Área de Gestión Sanitaria Sur de Granada."),
                         "Jefe/a de Equipo de Gestión y Servicios como encargo complementario de funciones para la Unidad de Gestión Clínica de Almuñécar")
        self.assertEqual(P("directivo", "Resolución de 9 de Octubre de 2026, de la Dirección General de Personal del Servicio Andaluz de Salud, por la que se anuncia convocatoria pública para cubrir puesto de trabajo de carácter directivo próximo a quedar vacante de Gerencia de Área del Área de Gestión Sanitaria Sur de Granada"),
                         "Gerencia de Área del Área de Gestión Sanitaria Sur de Granada")

    def test_estado(self):
        d = lambda *t: [("", "u", x) for x in t]
        self.assertIsNone(so.estado(d("Convocatoria")))
        self.assertEqual(so.estado(d("Convocatoria", "Resolución por la que se declara desierta")), "desierta")
        self.assertEqual(so.estado(d("Convocatoria", "Listado Provisional de Admitidos y Excluidos")), "lista provisional de admitidos")
        self.assertEqual(so.estado(d("Convocatoria", "Listado Provisional de Admitidos y Excluidos", "Corrección de errores del Listado Provisional")), "lista provisional de admitidos")
        self.assertEqual(so.estado(d("Convocatoria", "Listado Provisional", "Listado Definitivo de Admitidos y Excluidos", "Resolución Provisional de la convocatoria", "Resolución Definitiva de la convocatoria")), "resuelta")
        self.assertEqual(so.estado([("Convocatoria", "u", "Resolución de…"), ("Resolución de adjudicación", "u", "Resolución de 15 de mayo…")]), "resuelta")
        self.assertEqual(so.estado(d("Convocatoria", "PRUEBA: un documento con un nombre propio")), "con novedades")       # nunca el texto del documento

    def test_plazo(self):
        self.assertEqual(so.plazo_de(PLAZOS["pb11819"]), (10, "habiles", True))
        self.assertEqual(so.plazo_de(PLAZOS["pb11792"]), (5, "habiles", True))
        self.assertEqual(so.plazo_de(PLAZOS["ci10464"]), (10, "habiles", True))
        self.assertEqual(so.plazo_de(PLAZOS["pd510"]), (10, "habiles", True))
        self.assertIsNone(so.plazo_de("Finalizado el plazo de presentación de solicitudes, se concede un plazo de cinco días hábiles de subsanación."))
        self.assertIsNone(so.plazo_de(PLAZOS["pb11819"] + " PRUEBA: El plazo de presentación será de quince días naturales."))       # dos distintos: ninguno

    def recoger(self, antes=None, roto=None):
        pedidas = []
        def pedir(u):
            pedidas.append(u)
            if roto and roto in u: raise OSError("PRUEBA: corte de conexión")
            m = re.search(r"ooe_type=ooe_(\w+?)(?:&centro=(\d+))?(?:&page=\d+)?$", u)
            if not m: return f"%PDF {u.split('ooe_file/')[1].split('/')[0]}".encode()
            tipo, centro = m.groups()
            ab = {"puesto_base": "pb", "cargo_intermedio": "ci", "puesto_directivo": "pd"}[tipo]
            if not centro:       # el filtro de centros (el de puestos base vale para los tres en la prueba, con su nombre de campo)
                return muestra("sspa_ooe_pb_20261109.html").replace("field_oferta_pb_centro", f"field_oferta_{ab}_centro").encode()
            fich = {("pb", "12831"): "pb_torrecardenas", ("pb", "12730"): "pb_surgranada", ("ci", "12730"): "ci_surgranada", ("pd", "12730"): "pd_surgranada"}.get((ab, centro))
            if fich: return muestra(f"sspa_ooe_{fich}_20261109.html").encode()
            vacia = muestra("sspa_ooe_pb_20261109.html").replace("field_oferta_pb_centro", f"field_oferta_{ab}_centro")
            vacia = vacia[:vacia.index('<div class="views-row')] + "</div></div></form>"       # PRUEBA: ese centro, sin ofertas
            return vacia.replace(f'<option value="{centro}"', f'<option value="{centro}" selected="selected"').encode()
        pdf = lambda datos: PLAZOS.get(PDF.get(datos.decode().split()[1]), "")
        inh = lambda anios: sas.inhabiles({2026}, red=lambda u: muestra("calendario_adra_2026.json"))
        lista, res = so.recoger(pedir, dt.date(2026, 11, 9), 30, antes, pausa=lambda s: None, pdf=pdf, inhabiles=inh)
        return lista, res, pedidas

    def test_recoger(self):
        lista, res, pedidas = self.recoger()
        self.assertEqual([(o["cod"], o["tipo"], o["area"], o["fecha"]) for o in lista],
                         [("10464", "intermedio", "sur_granada", "2026-11-09"), ("11819", "base", "almeria", "2026-10-27"),
                          ("510", "directivo", "sur_granada", "2026-10-15"), ("11792", "base", "sur_granada", "2026-10-14")])
        o = {x["cod"]: x for x in lista}
        self.assertEqual(o["11819"]["plazo"], {"n": 10, "unidad": "habiles", "hasta": "2026-11-11"})       # el lunes 2 nov, inhábil en Andalucía
        self.assertEqual(o["10464"]["plazo"], {"n": 10, "unidad": "habiles", "hasta": "2026-11-23"})       # desde el BOJA del 9 nov
        self.assertEqual(o["510"]["plazo"]["hasta"], "2026-10-29")
        self.assertEqual((o["11792"]["estado"], o["11792"]["docs"], o["11792"]["plazo"]["hasta"]), ("desierta", 2, "2026-10-21"))
        self.assertEqual(o["11819"]["centro"], "Hospital Universitario Torrecárdenas")
        self.assertEqual(o["11819"]["puesto"], "Técnico Función Administrativa opción Administración General")
        self.assertTrue(o["11819"]["enlace"].startswith(so.BASE + "/servicioandaluzdesalud/ooe_file/400173/"))
        self.assertEqual(res["ofertas"], 4); self.assertEqual(res["nuevas"], 4); self.assertEqual(res["fallos"], [])
        self.assertEqual(sum("centro=" in u for u in pedidas), 21)       # los 7 centros de la zona en cada tipo; una página de cada uno
        self.assertFalse(any("page=" in u for u in pedidas))            # la segunda página no hace falta: la primera ya llega a lo antiguo
        # al día siguiente: los plazos ya están (ningún PDF)
        lista2, res2, pedidas2 = self.recoger(antes=lista)
        self.assertEqual(lista2, lista); self.assertEqual(res2["nuevas"], 0)
        self.assertFalse(any("ooe_file" in u for u in pedidas2))

    def test_un_centro_falla(self):
        lista, _, _ = self.recoger()
        lista2, res2, _ = self.recoger(antes=lista, roto="centro=12831")
        self.assertEqual([o["cod"] for o in lista2], [o["cod"] for o in lista])       # las de Torrecárdenas, las de la vez anterior
        self.assertEqual(len(res2["fallos"]), 3)                                      # en los tres tipos de oferta
        self.assertTrue(all("Torrecárdenas" in f for f in res2["fallos"]))
        sin, res3, _ = self.recoger(roto="centro=12831")
        self.assertNotIn("11819", [o["cod"] for o in sin])


if __name__ == "__main__":
    unittest.main()
