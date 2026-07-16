import pytest
from fastapi.testclient import TestClient
from main import app, calculate_nearest_station, PROJECT_CACHE, models, SessionLocal, search_transfer_cached

#To download setups
@pytest.fixture(scope="session", autouse=True)
def setup_cache():
    from main import PROJECT_CACHE, SessionLocal
    import models
    db = SessionLocal()
    
    # Get all datas and stores
    stations = db.query(models.Stop).all()

    PROJECT_CACHE["stations_spatial_data"] = [
        {"stop_name": s.stop_name, "stop_lat": float(s.stop_lat), "stop_lon": float(s.stop_lon)}
        for s in stations if s.stop_lat and s.stop_lon
    ]
    PROJECT_CACHE["stop_name_to_ids"] = {}
    for s in stations:
        PROJECT_CACHE["stop_name_to_ids"].setdefault(s.stop_name, []).append(s.stop_id)


    PROJECT_CACHE["stop_id_to_name"] = {s.stop_id: s.stop_name for s in stations}
    for s in stations:
        PROJECT_CACHE["stop_name_to_ids"].setdefault(s.stop_name, []).append(s.stop_id)
    
    all_stop_times = db.query(models.StopTime).all()
    for st in all_stop_times:
        if st.departure_time:
            PROJECT_CACHE["station_departure_map"].setdefault(st.stop_id, []).append({
                "trip_id": st.trip_id, "departure_time": str(st.departure_time).strip(), "stop_sequence": st.stop_sequence
            })
        PROJECT_CACHE["trip_schedules"].setdefault(st.trip_id, []).append({
            "stop_id": st.stop_id, "arrival_time": str(st.arrival_time).strip() if st.arrival_time else None, "stop_sequence": st.stop_sequence
        })
    # Sorting
    for sid in PROJECT_CACHE["station_departure_map"]:
        PROJECT_CACHE["station_departure_map"][sid].sort(key=lambda x: x["departure_time"])
        PROJECT_CACHE["station_departure_times_only"][sid] = [d["departure_time"] for d in PROJECT_CACHE["station_departure_map"][sid]]
    for tid in PROJECT_CACHE["trip_schedules"]:
        PROJECT_CACHE["trip_schedules"][tid].sort(key=lambda x: x["stop_sequence"])
        
    db.close()

@pytest.mark.parametrize("start, end, departure_time, expected_arrival", [
    ("Grand Central-42 St", "47-50 Sts-Rockefeller Ctr", "00:37:30", "00:42:00"),
    ("18 Av", "1 Av", "01:28:30", "01:57:00")
])
def test_time(start, end, departure_time, expected_arrival):
    from main import PROJECT_CACHE
    
    # Search
    res = search_transfer_cached(start, end, PROJECT_CACHE, departure_time_limit=departure_time)
    
    assert res["status"] == "Success"
    assert len(res["results"]) > 0, "The result was empty, no route is found"
    
    #Debug
    arrival_times = [r["real_arrival_time"] for r in res["results"]]
    assert expected_arrival in arrival_times, \
        f"Arriving time doesn't match. Expected result: {expected_arrival}, Found time list: {arrival_times}"

    print(f"SUCCESS: Route found. Expected arrival {expected_arrival} is in results.")


# 3. Test for nearest station
@pytest.mark.parametrize("lat, lon, expected_station", [
    (40.7439, -73.9870, "28 St"),
    (51.5078, -0.1275, None),#London
    (0, 0, None),
    (" ", " ", None),
    ("", "", None),
    (10 * 200, 200 * -5, None)
]) 
def test_search_nearest_station(lat, lon, expected_station):
    
    res = calculate_nearest_station(lat, lon) 
    
    print(f"\nDEBUG: Calculated result is: {res}")
    if res == float():
        assert res == expected_station


# 2. Finished
@pytest.mark.parametrize("start, end, expected_status", [
    ("Times Sq-42 St", "14 St", 200),
    ("InvalidStation", "14 St", 400),
    ("Times Sq-42 St", "InvalidStation", 400),
    ("InvalidStation", "InvalidStation", 400),
    ("start_station", "end_station", 400),
    ("", " ", 400)
])
def test_search_route_cases(start, end, expected_status):
    with TestClient(app) as client:
        response = client.get(f"/search_route?start_stop_name={start}&end_stop_name={end}")
        assert response.status_code == expected_status
        if response.status_code == 200:
            assert "all_trains" in response.json()

