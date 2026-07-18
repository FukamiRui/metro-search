
import pytest
from fastapi.testclient import TestClient
from main import app, calculate_nearest_station, PROJECT_CACHE, search_transfer_db, search_direct_db
from database import SessionLocal

@pytest.fixture(scope="session", autouse=True)
def client():
    
    with TestClient(app) as c:
        yield c  


@pytest.mark.parametrize("start, end, expected_status", [
    ("Times Sq-42 St", "14 St", 200),
    ("InvalidStation", "14 St", 400),
    ("Times Sq-42 St", "InvalidStation", 400),
    ("InvalidStation", "InvalidStation", 400),
    ("start_station", "end_station", 400),
    ("", " ", 400)
])
def test_search_route_cases(client, start, end, expected_status):

    response = client.get(f"/search_route?start_stop_name={start}&end_stop_name={end}")
    assert response.status_code == expected_status
    if response.status_code == 200:
        assert "all_trains" in response.json()


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
    exists = (station is not None) and (station in PROJECT_CACHE["stop_name_to_ids"])
    assert exists == expected_exists

@pytest.mark.parametrize("lat, lon, expected_station", [
    (40.7439, -73.9870, "28 St"),
    (51.5078, -0.1275, None), # London
    (0, 0, None),
    (" ", " ", None),
    ("", "", None),
    (10 * 200, 200 * -5, None)
]) 
def test_search_nearest_station(lat, lon, expected_station):
    res = calculate_nearest_station(lat, lon) 
    if not isinstance(res, str): # Error handling for float/None cases
        assert res == expected_station


@pytest.mark.parametrize("start, end, departure_time", [
    ("Grand Central-42 St", "47-50 Sts-Rockefeller Ctr", "00:37:30"),
    ("18 Av", "1 Av", "01:28:30")
])
def test_time(start, end, departure_time):
    db = SessionLocal()
    try: 
        res = search_transfer_db(db, start, end, PROJECT_CACHE, departure_time_limit=departure_time)
    
        assert res["status"] == "Success"
        assert len(res["results"]) > 0, "The result was empty, no route is found"
    
        arrival_times = [r["real_arrival_time"] for r in res["results"]]
    
        assert len(arrival_times) > 0
    
        assert arrival_times[0] >= departure_time, \
             f"Arrival time {arrival_times[0]} is before departure time {departure_time}!"
    finally:
        db.close()
    
@pytest.mark.parametrize("station_name, expected_exist, min_lat, max_lat, min_lon, max_lon", [
    ("1 Av", True, 40.7, 40.8, -74.0, -73.9),     
    ("34 St-Penn Station", True, 40.7, 40.8, -74.0, -73.9),
    ("Grand Central-42 St", True, 40.7, 40.8, -74.0, -73.95),
    ("KingsCross", False, 0.0, 0.0, 0.0, 0.0), 
    ("", False, 0.0, 0.0, 0.0, 0.0),
    (None, False, 0.0, 0.0, 0.0, 0.0),
    ("stop_name", False, 100000, -100000, 2030, -2030) 
])
def test_data_station_exists(station_name, expected_exist, min_lat, max_lat, min_lon, max_lon):
    
    spatial_data = PROJECT_CACHE.get("stations_spatial_data", [])

    result = next((s for s in spatial_data if s["stop_name"] == station_name), None)

    if expected_exist:
        assert result is not None, f"Expected station '{station_name}' was not found in cache."

        lat = result["stop_lat"]
        lon = result["stop_lon"]
        

        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert min_lat <= lat <= max_lat, f"Station '{station_name}': LAT {lat} is out of range."
        assert min_lon <= lon <= max_lon, f"Station '{station_name}': LON {lon} is out of range." 
    else:
        assert result is None, f"Unexpected data '{station_name}' is in CACHE."