"""playas.py: las tres formas de fila de los informes de la Junta (2026). PRUEBA: filas con la forma de los PDF."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playas

def test_formas():
    t = "\n".join([
        "ALMERIA     ADRA                   PLAYA CARBONCILLO                   PLAYA CARBONCILLO PM1                   Excelente                      14/09/2026 Zona Apta para el baño      Apta para su uso",
        "ALMERIA      ADRA                   Zonas de baño marítimas   PLAYA CENSO                   PLAYA CENSO PM2                       Excelente           01/06/2026       Zona Apta para el baño      Apta para su uso",
        "ALMERIA             ADRA         PLAYA LA CARACOLA                   PLAYA LA CARACOLA PM1                       Excelente           15/06/2026        Zona No Apta para el baño   Prohibido el baño   Contaminación puntual",
        "ALMERIA     ALMERIA                PLAYA COSTACABANA                   PLAYA COSTACABANA PM2                   Excelente                      15/09/2026 Zona Apta para el baño      Apta para su uso"])
    f = playas.leer(t)
    assert [x["zona"] for x in f] == ["PLAYA CARBONCILLO", "PLAYA CENSO", "PLAYA LA CARACOLA"]
    assert [x["fecha"] for x in f] == ["2026-09-14", "2026-06-01", "2026-06-15"]
    assert f[0]["valoracion"] == "Zona Apta para el baño" and f[0]["comunicado"] == "Apta para su uso"
    assert f[2]["observaciones"] == "Contaminación puntual"
    assert playas.nombre("PLAYA EL LANCE DE LA VIRGEN") == "El Lance de la Virgen"

def test_informes():
    h = '<a href="/sites/x/maritimas_almeria_20260916.pdf">a</a><a href="/x/maritimas_cadiz_20260916.pdf">c</a><a href="/y/maritimas_almeria_20250930.pdf">b</a>'
    assert [(f.isoformat(), u[-12:]) for f, u in playas.informes(h, 2026)] == [("2026-09-16", "20260916.pdf")]
