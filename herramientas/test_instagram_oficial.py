"""Pruebas de instagram_oficial.py con una respuesta de ejemplo (forma documentada de Business Discovery; datos inventados).

  python3 -m unittest herramientas/test_instagram_oficial.py
"""
import datetime as dt, io, json, os, sys, unittest, urllib.error

sys.path.insert(0, os.path.dirname(__file__))
import instagram_oficial as ig

AHORA = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)
EJEMPLO = {"business_discovery": {"username": "comercio_ejemplo", "id": "1", "media": {"data": [
    {"id": "a", "timestamp": "2026-10-24T09:00:00+0000", "permalink": "https://www.instagram.com/p/EJEMPLO1/",
     "caption": "🎁 SORTEO 🎁 Cesta de productos. Para participar sigue la cuenta. Termina el 31/10 a las 23:59. Solo Adra."},
    {"id": "b", "timestamp": "2026-10-23T09:00:00+0000", "permalink": "https://www.instagram.com/p/EJEMPLO2/",
     "caption": "Nuevo horario de invierno"},
    {"id": "c", "timestamp": "2026-08-01T09:00:00+0000", "permalink": "https://www.instagram.com/p/EJEMPLO3/",
     "caption": "Sorteamos dos entradas"},
    {"id": "d", "timestamp": "2026-10-22T09:00:00+0000", "permalink": "https://www.instagram.com/p/EJEMPLO4/",
     "caption": "¡GIVEAWAY! Gana un bono"},
    {"id": "e", "permalink": "https://www.instagram.com/p/EJEMPLO5/", "caption": "sorteo sin fecha de publicación"}]}},
    "id": "999"}


class Oficial(unittest.TestCase):
    def test_solo_sorteos_recientes(self):
        c = ig.candidatos(EJEMPLO, AHORA)
        self.assertEqual([x["enlace"] for x in c], ["https://www.instagram.com/p/EJEMPLO1/", "https://www.instagram.com/p/EJEMPLO4/"])
        self.assertEqual(c[0]["cuenta"], "@comercio_ejemplo")
        self.assertIn("23:59", c[0]["texto"])
        self.assertEqual(len(ig.candidatos(EJEMPLO, AHORA, dias=120)), 3)
        self.assertEqual(ig.candidatos({}, AHORA), [])

    def test_cuentas_no_dejan_meter_nada_en_la_consulta(self):
        self.assertEqual(ig.cuenta_limpia("@mi.tienda_adra"), "mi.tienda_adra")
        for mala in ("a){id}", "x y", "", "@" + "a" * 31):
            with self.assertRaises(ValueError): ig.cuenta_limpia(mala)
        self.assertEqual(ig.campos("@tienda"), "business_discovery.username(tienda){username,media.limit(12){caption,permalink,timestamp}}")

    def test_el_token_va_en_cabecera_y_nunca_sale(self):
        visto = {}

        def abrir(req, timeout):
            visto["url"], visto["auth"] = req.full_url, req.get_header("Authorization")
            cuerpo = json.dumps({"error": {"message": "Invalid token SECRETO123"}}).encode()
            raise urllib.error.HTTPError(req.full_url, 400, "Bad", {}, io.BytesIO(cuerpo))

        with self.assertRaises(RuntimeError) as e: ig.pedir("@tienda", "SECRETO123", "999", abrir)
        self.assertNotIn("SECRETO123", visto["url"])
        self.assertEqual(visto["auth"], "Bearer SECRETO123")
        self.assertNotIn("SECRETO123", str(e.exception))
        self.assertIn("HTTP 400", str(e.exception))
        self.assertTrue(visto["url"].startswith(ig.API + "/999?fields=business_discovery.username%28tienda%29"))

    def test_sin_token_la_cabecera_la_pone_el_proxy(self):
        visto = {}

        def abrir(req, timeout):
            visto["auth"] = req.get_header("Authorization")
            return io.BytesIO(json.dumps(EJEMPLO).encode())

        self.assertEqual(ig.pedir("@tienda", None, "999", abrir)["business_discovery"]["username"], "comercio_ejemplo")
        self.assertIsNone(visto["auth"])

    def test_id_propio_con_token_de_pagina_o_de_usuario(self):
        def respuestas(por_ruta):
            def abrir(req, timeout):
                ruta = req.full_url[len(ig.API) + 1:].split("?")[0]
                r = por_ruta[ruta]
                if isinstance(r, int):
                    raise urllib.error.HTTPError(req.full_url, r, "x", {}, io.BytesIO(b'{"error":{"message":"no","code":100}}'))
                return io.BytesIO(json.dumps(r).encode())
            return abrir

        pagina = respuestas({"me": {"instagram_business_account": {"id": "1784"}, "id": "55"}})
        self.assertEqual(ig.id_propio(None, pagina), "1784")
        usuario = respuestas({"me": 400, "me/accounts": {"data": [{"id": "1"}, {"id": "2", "instagram_business_account": {"id": "1785"}}]}})
        self.assertEqual(ig.id_propio(None, usuario), "1785")
        nada = respuestas({"me": 400, "me/accounts": {"data": [{"id": "1"}]}})
        with self.assertRaises(RuntimeError): ig.id_propio(None, nada)
        sin_secreto = respuestas({"me": 400, "me/accounts": 400})
        with self.assertRaises(RuntimeError): ig.id_propio(None, sin_secreto)


if __name__ == "__main__":
    unittest.main()
