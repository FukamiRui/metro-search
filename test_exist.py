import pytest
from fastapi.testclient import TestClient
from main import app, calculate_nearest_station, PROJECT_CACHE, models, SessionLocal, search_transfer_cached

@pytest.fixture(autouse=True)
def setup_cache():
    """Loading texture"""
    from main import PROJECT_CACHE, SessionLocal
    import models


    #Check cache is not empty, otherwise load again
    if not PROJECT_CACHE["stations_spatial_data"]:
        db = SessionLocal()

        # Do like a lifespan
        stations = db.query(models.Stop).all()
        PROJECT_CACHE["stations_spatial_data"] = [
            {"stop_name": s.stop_name, "stop_lat": float(s.stop_lat), "stop_lon": float(s.stop_lon)}
            for s in stations if s.stop_lat and s.stop_lon
        ]
        PROJECT_CACHE["stop_name_to_ids"] = {}
        for s in stations:
            PROJECT_CACHE["stop_name_to_ids"].setdefault(s.stop_name, []).append(s.stop_id)
        db.close()



@pytest.mark.parametrize("station, expected_exists", [
    ("1 Av", True),     
    ("18 Av", True),
    ("KingsCross", False),
    ("", False),
    (None, False),
    (" ", False),
    ("start_station", False),
    ("<script>alert(1)</script>", False)

])
def test_station_exists(station, expected_exists):
    from main import PROJECT_CACHE
    exists = (station is not None) and (station in PROJECT_CACHE["stop_name_to_ids"])
    assert exists == expected_exists

