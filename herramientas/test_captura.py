"""Pruebas de captura.py: el base64 de una descarga de Drive se encuentra esté donde esté y sale la imagen entera.

  python3 -m unittest herramientas/test_captura.py
"""
import base64, io, json, os, sys, tempfile, time, unittest

sys.path.insert(0, os.path.dirname(__file__))
import captura
from PIL import Image

FID = "1AbCdEfGhIjKlMnOpQrStUvWxYz012345"
OTRO = "1ZzZzZzZzZzZzZzZzZzZzZzZzZzZz9999"


def png(w=40, h=20, color=(200, 30, 30)):
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


def respuesta(fid, datos):
    return json.dumps({"content": base64.b64encode(datos).decode(), "id": fid, "mimeType": "image/png", "title": "x.png"})


class Captura(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.raiz = os.path.join(self.d, "projects")
        os.makedirs(os.path.join(self.raiz, "-home", "sesion", "tool-results"))

    def escribir(self, ruta, texto, edad=0):
        p = os.path.join(self.raiz, ruta)
        open(p, "w", encoding="utf-8").write(texto)
        t = time.time() - edad
        os.utime(p, (t, t))
        return p

    def test_en_el_registro_de_la_sesion(self):
        datos = png()
        linea_mia = {"type": "assistant", "message": {"content": [{"type": "tool_use", "input": {"fileId": FID}}]}}
        linea = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                          "content": [{"type": "text", "text": respuesta(FID, datos)}]}]}}
        self.escribir("-home/sesion.jsonl", json.dumps(linea_mia) + "\n" + json.dumps(linea) + "\n")
        self.assertEqual(base64.b64decode(captura.buscar(FID, raiz=self.raiz)), datos)

    def test_guardada_aparte_como_lista_json(self):
        datos = png(60, 30)
        texto = json.dumps([{"type": "text", "text": respuesta(FID, datos)}], indent=2)
        self.escribir("-home/sesion/tool-results/mcp-google-drive-1.txt", texto)
        self.assertEqual(base64.b64decode(captura.buscar(FID, raiz=self.raiz)), datos)

    def test_guardada_aparte_como_texto(self):
        datos = png(70, 30)
        p = self.escribir("-home/sesion/tool-results/mcp-google-drive-2.txt", respuesta(FID, datos))
        self.assertEqual(base64.b64decode(captura.buscar(FID, desde=p)), datos)

    def test_no_confunde_ficheros_y_coge_la_descarga_mas_nueva(self):
        vieja, nueva, otra = png(10, 10), png(12, 12), png(14, 14, (0, 0, 255))
        self.escribir("-home/sesion/tool-results/a.txt", respuesta(FID, vieja), edad=600)
        self.escribir("-home/sesion/tool-results/b.txt", respuesta(OTRO, otra), edad=0)
        self.escribir("-home/sesion/tool-results/c.txt", respuesta(FID, nueva), edad=60)
        self.assertEqual(base64.b64decode(captura.buscar(FID, raiz=self.raiz)), nueva)
        self.assertEqual(base64.b64decode(captura.buscar(OTRO, raiz=self.raiz)), otra)
        self.assertIsNone(captura.buscar("1NoEstaNoEstaNoEstaNoEsta000000", raiz=self.raiz))

    def test_tipo_por_la_firma(self):
        self.assertEqual(captura.tipo(png()), "png")
        self.assertEqual(captura.tipo(b"\xff\xd8\xff\xe0resto"), "jpg")

    def test_recortes_cubren_toda_la_captura_alta(self):
        ruta = os.path.join(self.d, "alta.png")
        im = Image.new("RGB", (1080, 2400), "white")
        for y in range(0, 2400, 100): im.paste((0, 0, 0), (0, y, 1080, y + 4))   # rayas para ver el solape
        im.save(ruta)
        partes = captura.recortes(ruta, self.d, "alta")
        self.assertGreaterEqual(len(partes), 2)
        alto = 0
        for p in partes:
            with Image.open(p) as t:
                self.assertEqual(t.width, 1000)
                alto += t.height
        self.assertGreater(alto, 2400 * 1000 / 1080)        # con solape, más que la captura reducida
        ancha = os.path.join(self.d, "ancha.png")
        Image.new("RGB", (1920, 1080), "white").save(ancha)
        self.assertEqual(captura.recortes(ancha, self.d, "ancha"), [])
        otra = os.path.join(self.d, "texto.bin")
        open(otra, "wb").write(b"1\r\n2\r\n")
        self.assertEqual(captura.recortes(otra, self.d, "texto"), [])


if __name__ == "__main__":
    unittest.main()
