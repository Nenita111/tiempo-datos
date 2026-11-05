"""agenda_junta.py. PRUEBA: eventos con la forma del conjunto de datos de la Junta."""
import datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agenda_junta as a

def test_utm():
    la, lo = a.utm30_a_latlon(370931.12802988, 4062870.7750675)   # Biblioteca Provincial de Málaga
    assert abs(la - 36.7027) < 1e-3 and abs(lo + 4.4450) < 1e-3

def test_leer():
    hoy = dt.date(2026, 11, 5)
    E = [{"title": "Posidonia <b>oceánica</b>", "location": "Almería", "coordinates": [{"longitude": None, "latitude": None}],
          "date_registration": [{"start_date_registration": "2026-11-07", "end_date_registration": "2026-11-07"}], "schedule": "De 08:00h a 14:00h"},
         {"title": "Taller", "location": "Málaga", "coordinates": [{"longitude": "370931.1", "latitude": "4062870.8"}],
          "date_registration": [{"start_date_registration": "2026-11-07", "end_date_registration": None}]},
         {"title": "Pasado", "location": "Adra", "date_registration": [{"start_date_registration": "2026-10-01", "end_date_registration": "2026-10-02"}]},
         {"title": "Jornadas", "location": "Almería", "coordinates": None, "date_registration": [{"start_date_registration": "2026-11-26", "end_date_registration": "2026-11-27"}]}]
    r = a.leer(E, hoy, {"almeria": (36.8381, -2.4597), "adra": (36.7493, -3.0146)})
    assert [x["titulo"] for x in r] == ["Posidonia oceánica", "Jornadas"]          # Málaga, a más de 60 km; lo pasado, fuera
    assert 45 <= r[0]["km"] <= 55 and r[0]["horario"] == "De 08:00h a 14:00h" and r[1]["hasta"] == "2026-11-27"
