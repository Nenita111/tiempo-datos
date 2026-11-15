"""revisar_fuentes.py: las fuentes que piden solo las cabeceras, una foto o el principio de un vídeo. PRUEBA: la red, de mentira
(respuestas con la forma de las de verdad); ninguna sale a internet."""
import datetime as dt, email.utils, io, os, sys, unittest, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import revisar_fuentes as RF

JPG = b"\xff\xd8" + b"0" * 3000


def hace(**k):
    return email.utils.format_datetime(dt.datetime.now(dt.timezone.utc) - dt.timedelta(**k), usegmt=True)


class Respuesta:
    def __init__(self, cuerpo=b"", **cabeceras): self.cuerpo, self.headers = cuerpo, {k.replace("_", "-"): v for k, v in cabeceras.items()}
    def read(self, n=None): return self.cuerpo if n is None else self.cuerpo[:n]
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Red:
    """urlopen de mentira: a cada dirección (por un trozo suyo), su respuesta o su fallo; apunta lo pedido."""
    def __init__(self, **por_trozo): self.por, self.vistas = por_trozo, []

    def __call__(self, req, timeout=None):
        self.vistas.append((req.get_method(), req.full_url, req.get_header("User-agent"), timeout))
        for trozo, r in self.por.items():
            if trozo in req.full_url:
                if isinstance(r, Exception): raise r
                return r
        raise AssertionError("no esperada: " + req.full_url)


def error(codigo): return urllib.error.HTTPError("https://prueba.invalid/", codigo, "x", {}, io.BytesIO(b""))


class Fuentes(unittest.TestCase):
    def con(self, **por):
        red = Red(**por)
        orig = urllib.request.urlopen
        urllib.request.urlopen = red
        self.addCleanup(setattr, urllib.request, "urlopen", orig)
        return red

    def test_paro_solo_la_cabecera_y_el_anio_anterior_si_falta(self):
        y = dt.datetime.now(RF.TZ).year
        red = self.con(**{f"municipios_{y}_csv": error(404), f"municipios_{y - 1}_csv": Respuesta(Last_Modified="Mon, 02 Nov 2026 08:00:00 GMT")})
        self.assertEqual(RF.paro(RF.ADRA), f"CSV de {y - 1}, Mon, 02 Nov 2026 08:00:00 GMT")
        self.assertEqual([(v[0], v[2], v[3]) for v in red.vistas], [("HEAD", RF.UA, 45)] * 2)      # el agente de la app, una vez cada una
        self.con(**{"municipios_": error(404)})
        with self.assertRaises(ValueError): RF.paro(RF.ADRA)
        self.con(**{"municipios_": error(503)})                                                 # otro fallo no es «no está»: sale tal cual
        with self.assertRaises(urllib.error.HTTPError): RF.paro(RF.ADRA)

    def test_sequia(self):
        mod = hace(days=10)
        red = self.con(InformeSequia=Respuesta(Content_Type="application/pdf", Last_Modified=mod))
        self.assertEqual(RF.sequia(RF.ADRA), f"modificado {mod}"); self.assertEqual(red.vistas[0][0], "HEAD")
        self.con(InformeSequia=Respuesta(Content_Type="text/html"))
        with self.assertRaisesRegex(ValueError, "no es un PDF"): RF.sequia(RF.ADRA)
        self.con(InformeSequia=Respuesta(Content_Type="application/pdf", Last_Modified=hace(days=80)))
        with self.assertRaisesRegex(ValueError, "no se ha renovado"): RF.sequia(RF.ADRA)

    def test_sol_video(self):
        red = self.con(latest_512_0171=Respuesta(Last_Modified="hoy", Content_Length="7300000"))
        self.assertEqual(RF.solVideo(RF.ADRA), "7 MB, hoy"); self.assertEqual(red.vistas[0][0], "HEAD")
        self.con(latest_512_0171=Respuesta(Content_Length="512"))
        with self.assertRaisesRegex(ValueError, "pesa 512 bytes"): RF.solVideo(RF.ADRA)

    def test_calar_vivo_solo_el_principio(self):
        video = b"--borde\r\nContent-Type: image/jpeg\r\nContent-Length: 51234\r\n\r\n" + JPG * 1000       # un vídeo que no acaba
        red = self.con(EYE56=Respuesta(video, Content_Type="multipart/x-mixed-replace; boundary=borde"))
        self.assertEqual(RF.calarVivo(RF.ADRA), "vídeo MJPEG"); self.assertEqual(red.vistas[0][:1] + red.vistas[0][3:], ("GET", 30))
        self.con(EYE56=Respuesta(video, Content_Type="image/jpeg"))
        with self.assertRaisesRegex(ValueError, "ya no es vídeo"): RF.calarVivo(RF.ADRA)
        self.con(EYE56=Respuesta(b"x" * 300 + b"Content-Length: 5", Content_Type="multipart/x-mixed-replace"))   # más allá de los 300 bytes no mira
        with self.assertRaisesRegex(ValueError, "Content-Length"): RF.calarVivo(RF.ADRA)

    def test_ruta_las_cuatro_camaras(self):
        red = self.con(camarasEtraffic=Respuesta(JPG, Last_Modified="Sun, 15 Nov 2026 10:30:00 GMT"))
        self.assertEqual(RF.ruta(RF.ADRA), "fotos de 516 11:30, 519 11:30, 521 11:30, 526 11:30")      # la hora, la de España
        self.assertEqual([v[0] for v in red.vistas], ["GET"] * 4)
        self.con(camarasEtraffic=Respuesta(b"cartel gris"))
        with self.assertRaisesRegex(ValueError, "no manda una foto"): RF.ruta(RF.ADRA)

    def test_pedir_guarda_lo_ultimo_y_no_insiste(self):
        red = self.con(aemet=Respuesta("<prediccion>ñ</prediccion>".encode()), caida=error(503))
        self.assertEqual(RF.texto("https://www.aemet.es/xml/x.xml"), "<prediccion>ñ</prediccion>")
        self.assertEqual(RF.ULTIMA.b, "<prediccion>ñ</prediccion>".encode())                    # para la segunda mirada de Jev
        self.assertEqual(red.vistas[0][:3], ("GET", "https://www.aemet.es/xml/x.xml", RF.UA))
        with self.assertRaises(urllib.error.HTTPError): RF.pedir("https://caida.invalid/")
        self.assertEqual(len(red.vistas), 2)                                                    # un 503 no se reintenta: la revisión no insiste
        RF.pedir("https://www.aemet.es/b", b"{}", "application/json", agente=RF.UA_WIKI)
        self.assertEqual(red.vistas[-1][:3], ("POST", "https://www.aemet.es/b", RF.UA_WIKI))


if __name__ == "__main__":
    unittest.main()
