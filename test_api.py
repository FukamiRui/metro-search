import pytest
from fastapi.testclient import TestClient
from main import app, calculate_nearest_station, PROJECT_CACHE, search_transfer_db, search_direct_db
from search import search_transfer_cached, search_direct_cached
from database import SessionLocal

# ====================================================
# Fixtures for loading data at the first
# ====================================================
@pytest.fixture(scope="session", autouse=True)
def client():
    with TestClient(app) as c:
        yield c  

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------
# Base Functions Cases
# --------------------------
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
def test_time(db_session, start, end, departure_time):
    res = search_transfer_db(db_session, start, end, PROJECT_CACHE, departure_time_limit=departure_time)

    assert res["status"] == "Success"
    assert len(res["results"]) > 0, "The result was empty, no route is found"

    arrival_times = [r["real_arrival_time"] for r in res["results"]]
    assert len(arrival_times) > 0
    assert arrival_times[0] >= departure_time, \
         f"Arrival time {arrival_times[0]} is before departure time {departure_time}!"


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


@pytest.mark.parametrize("start, end, expected_success", [
    ("1 Av", "8 Av", True),                                 
    ("116 St-Columbia University", "125 St", True),        
    ("1 Av", "18 Av", False),                              
    ("Found Station", "8 Av", False),                       
    (" ", "111111111", False)                               
])
def test_direct(db_session, start, end, expected_success):
    res = search_direct_db(db_session, start, end, PROJECT_CACHE, departure_time_limit="00:00:00")
    assert res["status"] == "Success"

    if expected_success:
        assert len(res["results"]) > 0, "The result is empty, it seems transfer route is only found"

        first_path = res["results"][0]["path"]
        assert len(first_path) == 1
        assert first_path[0]["board_station"] == start
        assert first_path[0]["getoff_station"] == end
    else:
        assert len(res["results"]) == 0, "Returned result, even though it wasn't found"


@pytest.mark.parametrize("start, end, expected_transfer_station", [
    ("1 Av", "18 Av", "8 Av"),
    ("116 St-Columbia University", "47-50 Sts-Rockefeller Ctr", ["125 St", "Cathedral Pkwy (110 St)", "59 St-Columbus Circle"]),  
    ("Found Station", "True", None),
    (" ", "111111111", None)
])
def test_transfer(db_session, start, end, expected_transfer_station):
    res = search_transfer_db(db_session, start, end, PROJECT_CACHE, departure_time_limit="00:00:00")

    if expected_transfer_station is None:
        assert res.get("status") in ["Success", "Fail"]
        assert len(res.get("results", [])) == 0
    else:
        assert res["status"] == "Success"
        assert len(res["results"]) > 0, "No matching result found"

        first_path = res["results"][0]["path"]
        actual_transfer_station = first_path[0]["getoff_station"]

        assert actual_transfer_station in expected_transfer_station, (
            f"No matching Transfer, Expected result: {expected_transfer_station}, Returned result: {actual_transfer_station}"
        )


@pytest.mark.parametrize("start, end, expected_has_trains", [
    ("1 Av", "8 Av", True),
    ("1 Av", "1 Av", False),
    ("InvalidStation", "8 Av", False),
    ("1 Av", "InvalidStation", False)
])
def test_search_direct_cached(start, end, expected_has_trains):
    search_direct_caches = {
        "stop_name_to_ids": PROJECT_CACHE.get("stop_name_to_ids", {}),
        "stop_id_to_name": PROJECT_CACHE.get("stop_id_to_name", {}),
        "station_departure_map": PROJECT_CACHE.get("station_departure_map", {}),
        "station_departure_times_only": PROJECT_CACHE.get("station_departure_times_only", {}),
        "trip_schedules": PROJECT_CACHE.get("trip_schedules", {}),
        "trip_to_route": PROJECT_CACHE.get("trip_to_route", {}),
        "trip_id_to_object": PROJECT_CACHE.get("trip_id_to_object", {})  
    }
    res = search_direct_cached(start, end, search_direct_caches, departure_time_limit="00:00:00")
    assert res["status"] == "Success"
    assert isinstance(res["next_trains"], list)
    


@pytest.mark.parametrize("start, end, expected_status", [
    ("1 Av", "18 Av", "Success"),
    ("InvalidStation", "18 Av", "Fail"),
    ("1 Av", "InvalidStation", "Fail"),
    (" ", "True", "Fail"),
    ("print(f{DATABASE_URL})", "A", "Fail")
])
def test_search_transfer_cached(start, end, expected_status):
    mock_cache = {
        "stop_name_to_ids": PROJECT_CACHE.get("stop_name_to_ids", {}),
        "stop_id_to_name": PROJECT_CACHE.get("stop_id_to_name", {}),
        "station_departure_map": PROJECT_CACHE.get("station_departure_map", {}),
        "station_departure_times_only": PROJECT_CACHE.get("station_departure_times_only", {}),
        "trip_schedules": PROJECT_CACHE.get("trip_schedules", {}),
        "trip_to_route": PROJECT_CACHE.get("trip_to_route", {})
    }
    res = search_transfer_cached(start, end, mock_cache, departure_time_limit="00:00:00")
    assert res["status"] == expected_status

# --------------------------
# Tests with Fake Datas
# --------------------------

def test_search_direct_cachedII():

    mock_cache = {
        "stop_name_to_ids": {"StartSt": ["S1"], "EndSt": ["E1"]},
        "station_departure_map": {
            "S1": [
                {"trip_id": f"T{i}", "stop_sequence": 1, "departure_time": f"08:0{i}:00"}
                for i in range(10) 
            ]
        },
        "station_departure_times_only": {
            "S1": [f"08:0{i}:00" for i in range(10)]
        },
        "trip_schedules": {
            f"T{i}": [
                {"stop_id": "S1", "stop_sequence": 1, "arrival_time": f"08:0{i}:00"},
                {"stop_id": "E1", "stop_sequence": 2, "arrival_time": f"08:1{i}:00"}
            ] for i in range(10)
        },
        "trip_id_to_object": {
            f"T{i}": {"route_id": "L", "trip_headsign": "Uptown"} for i in range(10)
        },
        "stop_id_to_name": {"S1": "StartSt", "E1": "EndSt"}
    }

    res = search_direct_cached("StartSt", "EndSt", mock_cache, departure_time_limit="08:00:00")
    assert res["status"] == "Success"
    assert len(res["next_trains"]) == 8 


    empty_deps_cache = mock_cache.copy()
    empty_deps_cache["station_departure_map"] = {"S1": []}
    res_empty = search_direct_cached("StartSt", "EndSt", empty_deps_cache, departure_time_limit="08:00:00")
    assert res_empty["status"] == "Success"
    assert len(res_empty["next_trains"]) == 0


def test_search_transfer_cachedII():
    mock_cache = {
        "stop_name_to_ids": 
        {
            "StartSt": ["S1"],
            "TransferSt": ["T1"],
            "EndSt": ["E1"]
        },
        "stop_id_to_name": 
        {
            "S1": "StartSt",
            "T1": "TransferSt",
            "E1": "EndSt"
        },
        "station_departure_map": 
        {
            "S1": [{"trip_id": "TRIP1", "stop_sequence": 1, "departure_time": "08:00:00"}],
            "T1": [{"trip_id": "TRIP2", "stop_sequence": 1, "departure_time": "08:30:00"}]
        },
        "station_departure_times_only": 
        {
            "S1": ["08:00:00"],
            "T1": ["08:30:00"]
        },
        "trip_schedules": 
        {
            "TRIP1": 
            [
                {"stop_id": "S1", "stop_sequence": 1, "arrival_time": "08:00:00"},
                {"stop_id": "T1", "stop_sequence": 2, "arrival_time": "08:20:00"}
            ],
            "TRIP2": 
            [
                {"stop_id": "T1", "stop_sequence": 1, "arrival_time": "08:30:00"},
                {"stop_id": "E1", "stop_sequence": 2, "arrival_time": "08:50:00"}
            ]
        },
        "trip_to_route": {"TRIP1": "RouteA", "TRIP2": "RouteB"}
    }
    res = search_transfer_cached("StartSt", "EndSt", mock_cache, departure_time_limit="07:50:00")
    assert res["status"] == "Success"
    assert len(res["results"]) > 0
    assert res["results"][0]["real_arrival_time"] == "08:50:00"