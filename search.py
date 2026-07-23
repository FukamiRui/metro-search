from collections import deque
import math
import bisect  
from sqlalchemy.orm import Session, aliased
import models

# Direct for [search_direct_db(), fetch_first_legs()]
MAX_FIRST_LEGS=1000
# Transfer for [fetch_second_legs()]
SECOND_LEG_BATCH_SIZE = 5000

def search_direct_cached(start_name: str, end_name: str, cache_data: dict, departure_time_limit: str = "00:00:00"):
    departure_time_limit = str(departure_time_limit).strip()
    
    stop_name_to_ids = cache_data["stop_name_to_ids"]
    station_departure_map = cache_data["station_departure_map"]
    station_departure_times_only = cache_data["station_departure_times_only"]  
    trip_schedules = cache_data["trip_schedules"]
    trip_id_to_object = cache_data["trip_id_to_object"]

    start_ids = stop_name_to_ids.get(start_name, [])
    end_ids = set(stop_name_to_ids.get(end_name, []))

    if not start_ids or not end_ids:
        return {"status": "Success", "next_trains": []}

    active_departures = []
    for sid in start_ids:
        deps = station_departure_map.get(sid, [])
        dep_times = station_departure_times_only.get(sid, [])  
        
        if not deps:
            continue
        
        idx = bisect.bisect_left(dep_times, departure_time_limit)
        active_departures.extend(deps[idx:])

    active_departures.sort(key=lambda x: x["departure_time"])

    direct_trains = []
    seen_trip_ids = set()

    for dep_node in active_departures:
        trip_id = dep_node["trip_id"]
        if trip_id in seen_trip_ids:
            continue
            
        start_seq = dep_node["stop_sequence"]
        dep_time = dep_node["departure_time"]
        schedules = trip_schedules.get(trip_id, [])
        
        for sch in schedules:
            if sch["stop_id"] in end_ids and sch["stop_sequence"] > start_seq:
                arr_time = sch["arrival_time"]
                if arr_time and arr_time > dep_time:
                    trip_info = trip_id_to_object.get(trip_id, {})
                    seen_trip_ids.add(trip_id)
                    direct_trains.append({
                        "route_id": str(trip_info.get("route_id", "1")).strip(),
                        "trip_headsign": str(trip_info.get("trip_headsign", f"To {end_name}")).strip(),
                        "departure_time": dep_time,
                        "arrival_time": arr_time
                    })
                    break 
                    
        if len(direct_trains) >= 8:
            break

    return {"status": "Success", "next_trains": direct_trains}

def search_transfer_cached(start_station_name: str, end_station_name: str, cache_data: dict, departure_time_limit: str = "00:00:00"):
    cache = load_cache_indexes(cache_data, start_station_name, end_station_name)
    if cache is None:
       return {"status": "Fail"}

    
    raw_results = bfs_transfer_searching(
    start_station_name,
    departure_time_limit,
    cache,
    )
    
    return format_bfs_results(raw_results) 
    
def load_cache_indexes(cache_data, start_station_name, end_station_name):
    stop_name_to_ids = cache_data["stop_name_to_ids"]
    stop_id_to_name = cache_data["stop_id_to_name"]
    station_departure_map = cache_data["station_departure_map"]
    station_departure_times_only = cache_data["station_departure_times_only"]
    trip_schedules = cache_data["trip_schedules"]
    trip_to_route = cache_data["trip_to_route"]

    if start_station_name not in stop_name_to_ids or end_station_name not in stop_name_to_ids:
        return None
    
    end_station_ids = set(stop_name_to_ids[end_station_name])

    return {
    "stop_name_to_ids": stop_name_to_ids,
    "stop_id_to_name": stop_id_to_name,
    "station_departure_map": station_departure_map,
    "station_departure_times_only": station_departure_times_only,
    "trip_schedules": trip_schedules,
    "trip_to_route": trip_to_route,
    "end_station_ids": end_station_ids,
    
}

def bfs_transfer_searching(start_station_name, departure_time_limit, cache):
    
    stop_name_to_ids = cache["stop_name_to_ids"]
    stop_id_to_name = cache["stop_id_to_name"]
    station_departure_map = cache["station_departure_map"]
    station_departure_times_only = cache["station_departure_times_only"]
    trip_schedules = cache["trip_schedules"]
    trip_to_route = cache["trip_to_route"]
    end_station_ids = cache["end_station_ids"]

    

    queue = deque([(start_station_name, departure_time_limit, [])])
    visited_stations = {start_station_name: departure_time_limit}
    results = []

    while queue:
        current_station, current_time, path = queue.popleft()
        if len(path) >= 3: 
            continue

        curr_station_ids = stop_name_to_ids.get(current_station, [])

        for sid in curr_station_ids:
            departures = station_departure_map.get(sid, [])
            dep_times = station_departure_times_only.get(sid, [])
            
            start_idx = bisect.bisect_left(dep_times, current_time)
        
            for dep in departures[start_idx : start_idx + 5]:
                trip_id = dep["trip_id"]
                schedules = trip_schedules.get(trip_id, [])

                for sch in schedules:
                    if sch["stop_sequence"] <= dep["stop_sequence"]: 
                        continue
                    
                    next_sid = sch["stop_id"]
                    arr_time = sch["arrival_time"]

                    if not arr_time: continue

                    if arr_time < dep["departure_time"]:
                        continue

                    if next_sid in end_station_ids:
                        real_dep_time = path[0]["departure_time"] if path else dep["departure_time"]
                        
                        results.append({
                            "real_departure_time": real_dep_time, 
                            "real_arrival_time": arr_time,
                            "path": path + [{"route_id": trip_to_route.get(trip_id), 
                                             "board_station": current_station, 
                                             "getoff_station": stop_id_to_name.get(next_sid), 
                                             "departure_time": dep["departure_time"], 
                                             "arrival_time": arr_time}]
                        })
                        continue

                    next_s_name = stop_id_to_name.get(next_sid)
                    if next_s_name and (next_s_name not in visited_stations or visited_stations[next_s_name] > arr_time):
                        visited_stations[next_s_name] = arr_time
                        queue.append((next_s_name, arr_time, path + [{"route_id": trip_to_route.get(trip_id), 
                                                                      "board_station": current_station, 
                                                                      "getoff_station": next_s_name, 
                                                                      "departure_time": dep["departure_time"], 
                                                                      "arrival_time": arr_time}]))
    return results

def format_bfs_results(results):
    return {"status": "Success", "results": sorted(results, key=lambda x: x["real_arrival_time"])}

def calculate_nearest_station(user_lat: float, user_lon: float, spatial_cache: list) -> str:
    best_station = None
    min_distance_km = float('inf')
    R = 6371.0
    
    if user_lat == None or user_lon == None:
        return None
        
    user_lat_rad = math.radians(user_lat)
    user_lon_rad = math.radians(user_lon)
    
    for station in spatial_cache:
        try:
            st_lat = float(station["stop_lat"])
            st_lon = float(station["stop_lon"])
            
            st_lat_rad = math.radians(st_lat)
            st_lon_rad = math.radians(st_lon)
            
            dlat = st_lat_rad - user_lat_rad
            dlon = st_lon_rad - user_lon_rad
            
            a = math.sin(dlat / 2)**2 + math.cos(user_lat_rad) * math.cos(st_lat_rad) * math.sin(dlon / 2)**2
            a = min(1.0, max(0.0, a))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance = R * c
            
            if distance < min_distance_km:
                min_distance_km = distance
                best_station = station["stop_name"]
        except Exception as value_error:
           raise ValueError( f"Error Occurred: {value_error}") from value_error
            
    return best_station

def search_direct_db(db: Session, start_station_name: str, end_station_name: str, PROJECT_CACHE: dict, departure_time_limit: str):
    stop_name_to_ids = PROJECT_CACHE["stop_name_to_ids"]
    start_ids = stop_name_to_ids.get(start_station_name, [])
    end_ids = stop_name_to_ids.get(end_station_name, [])

    if not start_ids or not end_ids:
        return {"status": "Success", "results": []}

    t_board = aliased(models.StopTime)
    t_alight = aliased(models.StopTime)
    trip = aliased(models.Trip)

    query_results = (
        db.query(t_board, t_alight, trip)
        .join(t_alight, t_board.trip_id == t_alight.trip_id)
        .join(trip, t_board.trip_id == trip.trip_id)
        .filter(
            t_board.stop_id.in_(start_ids),
            t_alight.stop_id.in_(end_ids),
            t_board.stop_sequence < t_alight.stop_sequence,
            t_board.departure_time >= departure_time_limit
        )
        .order_by(t_alight.arrival_time.asc())
        .limit(MAX_FIRST_LEGS)
        .all()
    )

    formatted_results = []
    for t_b, t_a, tr in query_results:
        path = [{
            "route_id": tr.route_id,
            "board_station": start_station_name,
            "getoff_station": end_station_name,
            "departure_time": t_b.departure_time,
            "arrival_time": t_a.arrival_time
        }]
        formatted_results.append({
            "real_departure_time": t_b.departure_time,
            "real_arrival_time": t_a.arrival_time,
            "status": "Success",
            "path": path
        })

    return {"status": "Success", "results": formatted_results}

#-----------------------------------------------------------------------------------------------------------------------------------
def search_transfer_db(db: Session, start_station_name: str, end_station_name: str, PROJECT_CACHE: dict, departure_time_limit: str):
  
    direct_results = search_direct_db(db, start_station_name, end_station_name, PROJECT_CACHE, departure_time_limit)
    if direct_results.get("status") == "Success" and len(direct_results["results"]) > 0:
        return direct_results
    
    stop_name_to_ids = PROJECT_CACHE["stop_name_to_ids"]
    stop_id_to_name = PROJECT_CACHE["stop_id_to_name"]

    start_ids = stop_name_to_ids.get(start_station_name, [])
    end_ids = stop_name_to_ids.get(end_station_name, [])

    if not start_ids or not end_ids:
        return {"status": "Success", "results": []}
    
    first_legs = fetch_first_legs(db, start_ids, departure_time_limit)
    second_legs = fetch_second_legs(db, end_ids, departure_time_limit)
    raw_results = merge_routes(first_legs, second_legs, start_station_name, end_station_name, stop_id_to_name)

    return format_results(raw_results)


def fetch_first_legs(db: Session, start_ids: list[str], departure_time_limit: str) -> list:
    t1_b = aliased(models.StopTime)
    t1_a = aliased(models.StopTime)
    tr1 = aliased(models.Trip)

    first_legs = (
        db.query(t1_b, t1_a, tr1)
        .join(t1_a, t1_b.trip_id == t1_a.trip_id)
        .join(tr1, t1_b.trip_id == tr1.trip_id)
        .filter(
            t1_b.stop_id.in_(start_ids),
            t1_b.stop_sequence < t1_a.stop_sequence,
            t1_b.departure_time >= departure_time_limit
        )
        .order_by(t1_b.departure_time.asc())
        .limit(MAX_FIRST_LEGS)
        .all()
    )
    return first_legs


def fetch_second_legs(db: Session, end_ids: list[str], departure_time_limit: str) -> list:
    t2_b = aliased(models.StopTime)
    t2_a = aliased(models.StopTime)
    tr2 = aliased(models.Trip)
    
    

    second_legs = (
        db.query(t2_b, t2_a, tr2)
        .join(t2_a, t2_b.trip_id == t2_a.trip_id)
        .join(tr2, t2_b.trip_id == tr2.trip_id)
        .filter(
            t2_a.stop_id.in_(end_ids),
            t2_b.stop_sequence < t2_a.stop_sequence,
            t2_b.departure_time >= departure_time_limit
        )
        .order_by(t2_a.arrival_time.asc())
        .yield_per(SECOND_LEG_BATCH_SIZE)
    )
    return second_legs

def merge_routes(first_legs, second_legs, start_station_name, end_station_name, stop_id_to_name) -> list:
    second_leg_map = {}
    for t2_b_obj, t2_a_obj, tr2_obj in second_legs:
        board_name = stop_id_to_name.get(t2_b_obj.stop_id)
        if not board_name: continue
        if board_name not in second_leg_map:
            second_leg_map[board_name] = []
        second_leg_map[board_name].append((t2_b_obj, t2_a_obj, tr2_obj))

    raw_results = []
    for t1_b_obj, t1_a_obj, tr1_obj in first_legs:
        transfer_name = stop_id_to_name.get(t1_a_obj.stop_id)
        
        if transfer_name and transfer_name in second_leg_map:
            for t2_b_obj, t2_a_obj, tr2_obj in second_leg_map[transfer_name]:
            
                if t1_a_obj.arrival_time <= t2_b_obj.departure_time:
                    path = [
                        {
                            "route_id": tr1_obj.route_id,
                            "board_station": start_station_name,
                            "getoff_station": transfer_name,
                            "departure_time": t1_b_obj.departure_time,
                            "arrival_time": t1_a_obj.arrival_time
                        },
                        {
                            "route_id": tr2_obj.route_id,
                            "board_station": transfer_name,
                            "getoff_station": end_station_name,
                            "departure_time": t2_b_obj.departure_time,
                            "arrival_time": t2_a_obj.arrival_time
                        }
                    ]
                    raw_results.append({
                        "real_departure_time": t1_b_obj.departure_time,
                        "real_arrival_time": t2_a_obj.arrival_time,
                        "status": "Success",
                        "path": path
                    })


    raw_results.sort(key=lambda x: x["real_arrival_time"])
    return raw_results

def format_results(raw_results):

    formatted_results = []
    seen_times = set()
    
    for res in raw_results:
        time_pair = (res["real_departure_time"], res["real_arrival_time"])
        if time_pair not in seen_times:
            seen_times.add(time_pair)
            formatted_results.append(res)
            
        if len(formatted_results) >= 5:
            break

    return {"status": "Success", "results": formatted_results}