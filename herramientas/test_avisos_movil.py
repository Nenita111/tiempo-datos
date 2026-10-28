import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import avisos_movil as A

TZ = A.TZ
AHORA = dt.datetime(2026, 10, 27, 21, 0, tzinfo=TZ)
CUADRO = {"type": "Polygon", "coordinates": [[[-3.2, 36.6], [-2.8, 36.6], [-2.8, 36.9], [-3.2, 36.9], [-3.2, 36.6]]]}
LEJOS = {"type": "Polygon", "coordinates": [[[-5, 40], [-4, 40], [-4, 41], [-5, 41], [-5, 40]]]}


def aviso(color, code, desde="2026-10-28T12:00:00+01:00", hasta="2026-10-28T18:59:59+01:00", par="P1", fen="PR"):
    return {"severity": color, "code": code, "onset_local": desde, "expires_local": hasta, "parametro": par, "fenomeno": fen,
            "descripcion": "Precipitación acumulada en una hora: 30 mm."}


class Avisos(unittest.TestCase):
    def test_aemet_naranja_y_rojo_de_la_zona(self):
        f = [{"geometry": CUADRO, "properties": {"Nombre_zona": "Poniente y Almería capital", "Avis_PRP1": [aviso("Naranja", "a1"), aviso("Amarillo", "a2"),
                                                                                                         aviso("Naranja", "a3", hasta="2026-10-27T10:00:00+01:00")]}},
             {"geometry": LEJOS, "properties": {"Nombre_zona": "Poniente y Almería capital - costa", "Avis_COP1": [aviso("Rojo", "c1", par="", fen="CO")]}},
             {"geometry": LEJOS, "properties": {"Nombre_zona": "Sierra de Madrid", "Avis_PRP1": [aviso("Rojo", "m1")]}}]
        r = A.avisos_aemet(f, -3.0206, 36.7489, AHORA)
        self.assertEqual(sorted(a["codigo"] for a in r), ["a1", "c1"])   # sin el amarillo, el pasado ni el de otra zona; con su costa
        n = A.nuevos({}, r, [], [], AHORA)
        self.assertIn("Aviso naranja de AEMET por lluvias en Poniente y Almería capital, mañana a las 12:00 hasta mañana a las 18:59", n[0]["texto"])
        self.assertEqual(A.nuevos({"aemet:a1": "x", "aemet:c1": "x"}, r, [], [], AHORA), [])   # una sola vez

    def test_terremotos_que_se_notan(self):
        self.assertTrue(A.se_nota(3.0, 45)); self.assertFalse(A.se_nota(3.0, 60)); self.assertTrue(A.se_nota(3.6, 95)); self.assertTrue(A.se_nota(4.1, 190))
        self.assertFalse(A.se_nota(2.9, 10))
        with open(os.path.join(os.path.dirname(__file__), "muestras", "ign_10dias_20261027.html"), encoding="utf-8") as f: html = f.read()
        self.assertEqual(A.terremotos(html, 36.7489, -3.0206), [])   # esos 10 días, ninguno se notó en Adra
        fila = ('<td>es2026prueba</td> <td>27/10/2026</td> <td>19:10:00</td> <td>20:10:00</td> <td class="tar">36.70</td> <td class="tar">-2.90</td>'
                ' <td class="tar">10.0 </td> <td class="tar">3.4 </td> <td class="tac">mbLg </td> <td class="tac">III </td> <td class="tal">SE ADRA.AL</td>')
        s = A.terremotos(fila, 36.7489, -3.0206)
        self.assertEqual(len(s), 1); self.assertEqual(s[0]["hora"].strftime("%d/%m %H:%M"), "27/10 20:10")
        n = A.nuevos({}, [], s, [], AHORA)
        self.assertEqual(n[0]["texto"], "Terremoto de magnitud 3,4 a 12 km, Adra (AL), hoy a las 20:10 (IGN).")
        self.assertTrue(n[0]["enlace"].endswith("evid=es2026prueba"))

    def test_cortes(self):
        self.assertEqual(A.tipo_corte("Corte de agua el jueves en varias calles de Adra"), "agua")
        self.assertEqual(A.tipo_corte("Se restablece el suministro de agua en Adra"), None)
        self.assertEqual(A.tipo_corte("Apagón en el centro de Adra"), "luz")
        rss = ('<rss><channel><item><title>Corte de agua el jueves en el barrio de San Sebastián de Adra</title><link>https://www.noticiasdealmeria.com/x1</link>'
               '<pubDate>Tue, 27 Oct 2026 10:00:00 +0100</pubDate></item><item><title>Corte de agua en Berja</title><link>https://www.noticiasdealmeria.com/x2</link>'
               '<pubDate>Tue, 27 Oct 2026 10:00:00 +0100</pubDate></item></channel></rss>')
        c = A.cortes_rss(rss, "Adra", AHORA - dt.timedelta(days=2))
        self.assertEqual([x["enlace"] for x in c], ["https://www.noticiasdealmeria.com/x1"])
        n = A.nuevos({}, [], [], c, AHORA)
        self.assertTrue(n[0]["texto"].startswith("Corte de agua anunciado: Corte de agua el jueves"))
        self.assertEqual(A.nuevos({n[0]["clave"]: "x"}, [], [], c, AHORA), [])

    def test_cortes_de_hidralia(self):
        # respuestas reales del 28 oct 2026 a las 22:29 (la consulta de la tabla del visor de Agbar)
        def muestra(n):
            with open(os.path.join(os.path.dirname(__file__), "muestras", n), encoding="utf-8") as f: return f.read()
        ahora = dt.datetime(2026, 10, 28, 22, 29, tzinfo=TZ)
        self.assertEqual(A.cortes_hidralia(muestra("hidralia_04003_20261028.json"), "04003", ahora), [])   # «en curso» desde el 20 oct: ya pasó
        c = A.cortes_hidralia(muestra("hidralia_30030_20261028.json"), "30030", ahora)
        self.assertEqual(len(c), 7)
        self.assertEqual(c[0]["texto"], "Corte de agua (Hidralia) mañana de 8:30 a 9:30 en Carril Torre Salinas 130-158: avería.")
        self.assertEqual(c[0]["enlace"], "https://gisaguapublic.agbar.net/?municipio_id=30030&cierre_id=224690")
        self.assertTrue(any(x["titulo"] == "Calle Pío Baroja 4-10 (Javalí Viejo)" for x in c))
        # ya empezado: «ahora, hasta…»; y una sola vez
        c2 = A.cortes_hidralia(muestra("hidralia_30030_20261028.json"), "30030", dt.datetime(2026, 10, 29, 9, 0, tzinfo=TZ), horas=0)
        self.assertEqual(c2[0]["texto"], "Corte de agua (Hidralia) ahora, hasta hoy a las 9:30 (previsión) en Carril Torre Salinas 130-158: avería.")
        n = A.nuevos({}, [], [], c2, ahora)
        self.assertEqual(n[0]["clave"], "hidralia:224690")
        self.assertEqual(A.nuevos({"hidralia:224690": "x"}, [], [], c2[:1], ahora), [])
        self.assertEqual(A.otras_calles("Colindantes"), " y calles colindantes"); self.assertEqual(A.otras_calles("null"), "")
        self.assertIn("url_cierres", dir(A)); self.assertIn("COD_MUNI%3D%2704003%27", A.url_cierres("04003"))


if __name__ == "__main__":
    unittest.main()
