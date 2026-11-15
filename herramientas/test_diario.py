"""diario.py: los avisos al móvil de lo que lleva días fallando (15 nov 2026). PRUEBA: pasos y fechas de mentira."""
import datetime as dt, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun, diario


def d(n): return dt.date(2026, 11, n)


class Parado(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, t)
        self.ruta, self.estado = os.path.join(t, "extras.json"), os.path.join(t, comun.ESTADO)

    def test_avisa_al_tercer_dia_y_luego_cada_semana(self):
        mal = {"cruceros": ('código 1: {"error": "sin la relación"}', None)}
        self.assertEqual(diario.parado(self.ruta, mal, d(13)), [])                       # el primer día no se avisa
        self.assertEqual(diario.parado(self.ruta, mal, d(14)), [])
        self.assertEqual(diario.parado(self.ruta, mal, d(15)), ['⚠️ Tele: «cruceros» falla desde el 13 nov: código 1: {"error": "sin la relación"}'])
        self.assertEqual(diario.parado(self.ruta, mal, d(15)), diario.parado(self.ruta, mal, d(15)))   # repetir el día no cambia nada
        for n in range(16, 22): self.assertEqual(diario.parado(self.ruta, mal, d(n)), [])   # ni todos los días
        self.assertEqual(len(diario.parado(self.ruta, mal, d(22))), 1)                   # a la semana, otra vez
        self.assertEqual(comun.leer(self.estado), {"fallos": {"cruceros": {"desde": "2026-11-13"}}})
        self.assertFalse(os.path.exists(self.ruta))                                      # extras.json ni se toca

    def test_lo_que_vuelve_a_ir_se_olvida(self):
        mal = {"raif": ("código 2", None), "polen": ("no acabó en 180 s", None)}
        diario.parado(self.ruta, mal, d(10)); diario.parado(self.ruta, mal, d(11))
        self.assertEqual(diario.parado(self.ruta, {"polen": ("no acabó en 180 s", None)}, d(12)), ["⚠️ Tele: «polen» falla desde el 10 nov: no acabó en 180 s"])
        self.assertEqual(diario.parado(self.ruta, {"raif": ("código 2", None)}, d(13)), [])   # raif falló el 13 después de ir bien el 12: empieza de cero
        self.assertEqual(comun.leer(self.estado)["fallos"], {"raif": {"desde": "2026-11-13"}})

    def test_los_problemas_de_hoy(self):
        pasos = {"cruceros": 'código 1: {"error": "x"}', "sas": 'ok: {"disposiciones": 3, "juez": "sin Jev (falta la caché)"}', "sequia": "fallo: no acabó en 900 s"}
        codigos = {"cruceros": 1, "sas": 0, "sequia": None, "raif": 0}
        res = {"jev": "sin Jev: falta la caché de Composio (JEV_CACHE)", "rotas": ["farmacias: ValueError: no aparece el buscador", "extras: ValueError: vuelos sin buscar desde 2026-11-10"]}
        p = diario.problemas({"vuelosBuscado": "2026-11-10"}, pasos, codigos, res, d(15))
        self.assertEqual(sorted(p), ["Jev", "cruceros", "fuente farmacias", "sequia", "vuelos"])     # «sas» fue bien (sin Jev); «extras» son los vuelos
        self.assertEqual(p["vuelos"], ("sin búsqueda de Kiwi desde el 10 nov (¿el conector?)", "2026-11-11"))
        # los vuelos de ayer aún valen (hoy se buscan después); con Jev y sin rotas, nada
        self.assertEqual(diario.problemas({"vuelosBuscado": "2026-11-14"}, {}, {"raif": 0}, {"jev": "12 respuestas por Composio, 0 sin respuesta", "rotas": []}, d(15)), {})
        self.assertEqual(sorted(diario.problemas({}, {}, {}, {"rotas": ["revisar_fuentes.py no acabó (None)"]}, d(15))), ["revisión de fuentes"])

    def test_los_vuelos_como_el_15_de_noviembre(self):
        """Lo que pasó: el conector de Kiwi faltó desde el día 11 y nadie avisó. Ahora, el 13 (dos días sin búsqueda)."""
        avisos = {}
        for n in range(11, 21):
            p = diario.problemas({"vuelosBuscado": "2026-11-10"}, {}, {}, {}, d(n))
            a = diario.parado(self.ruta, p, d(n))
            if a: avisos[n] = a
        self.assertEqual(avisos, {13: ["⚠️ Tele: «vuelos» falla desde el 11 nov: sin búsqueda de Kiwi desde el 10 nov (¿el conector?)"],
                                  20: ["⚠️ Tele: «vuelos» falla desde el 11 nov: sin búsqueda de Kiwi desde el 10 nov (¿el conector?)"]})


if __name__ == "__main__":
    unittest.main()
