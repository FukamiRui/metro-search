from collections import deque
import math
import bisect  
from sqlalchemy.orm import Session, aliased
import models

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
    stop_name_to_ids = cache_data["stop_name_to_ids"]
    stop_id_to_name = cache_data["stop_id_to_name"]
    station_departure_map = cache_data["station_departure_map"]
    station_departure_times_only = cache_data["station_departure_times_only"]
    trip_schedules = cache_data["trip_schedules"]
    trip_to_route = cache_data["trip_to_route"]

    if start_station_name not in stop_name_to_ids or end_station_name not in stop_name_to_ids:
        return {"status": "Fail", "message": "Origin or Destination station name not recognized in cache."}

    end_station_ids = set(stop_name_to_ids[end_station_name])
    queue = deque([(start_station_name, departure_time_limit, [])])
    visited_stations = {start_station_name: departure_time_limit}
    results = []

    while queue:
        current_station, current_time, path = queue.popleft()
        if len(path) >= 3: continue

        curr_station_ids = stop_name_to_ids.get(current_station, [])
        for sid in curr_station_ids:
            departures = station_departure_map.get(sid, [])
            dep_times = station_departure_times_only.get(sid, [])
            
            start_idx = bisect.bisect_left(dep_times, current_time)
        
            for dep in departures[start_idx : start_idx + 5]:
                trip_id = dep["trip_id"]
                schedules = trip_schedules.get(trip_id, [])
                for sch in schedules:
                    if sch["stop_sequence"] <= dep["stop_sequence"]: continue
                    
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
                            "path": path + [{"route_id": trip_to_route.get(trip_id), "board_station": current_station, "getoff_station": stop_id_to_name.get(next_sid), "departure_time": dep["departure_time"], "arrival_time": arr_time}]
                        })
                        continue

                    next_s_name = stop_id_to_name.get(next_sid)
                    if next_s_name and (next_s_name not in visited_stations or visited_stations[next_s_name] > arr_time):
                        visited_stations[next_s_name] = arr_time
                        queue.append((next_s_name, arr_time, path + [{"route_id": trip_to_route.get(trip_id), "board_station": current_station, "getoff_station": next_s_name, "departure_time": dep["departure_time"], "arrival_time": arr_time}]))
    return {"status": "Success", "results": sorted(results, key=lambda x: x["real_arrival_time"])}

def calculate_nearest_station(user_lat: float, user_lon: float, spatial_cache: list) -> str:

    best_station = None
    min_distance_km = float('inf')
    R = 6371.0
    
    user_lat_rad = math.radians(user_lat)
    user_lon_rad = math.radians(user_lon)

    if user_lat == None or user_lon == None:
        return None
    
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
        except:
            continue
            
    return best_station




def search_direct_db(db: Session, start_stop_name: str, end_stop_name: str, PROJECT_CACHE: dict, departure_time_limit: str):
    
    
    
    start_stop_ids = PROJECT_CACHE["stop_name_to_ids"].get(start_stop_name, [])
    end_stop_ids = PROJECT_CACHE["stop_name_to_ids"].get(end_stop_name, [])

    if not start_stop_ids or not end_stop_ids:
        return {"next_trains": []}

 
    t1_board = aliased(models.StopTime)
    t1_alight = aliased(models.StopTime)
    t2_board = aliased(models.StopTime)
    t2_alight = aliased(models.StopTime)
    trip1 = aliased(models.Trip)
    trip2 = aliased(models.Trip)
    
    
    s1 = aliased(models.Stop)
    s2 = aliased(models.Stop)

    
    results = (
        db.query(t1_board, t1_alight, t2_board, t2_alight, trip1, trip2)
      
        .join(t1_alight, t1_board.trip_id == t1_alight.trip_id)
        .join(trip1, t1_board.trip_id == trip1.trip_id)
        
      
        .join(s1, t1_alight.stop_id == s1.stop_id)
        .join(s2, s1.stop_name == s2.stop_name)
        .join(t2_board, s2.stop_id == t2_board.stop_id)
        
       
        .join(t2_alight, t2_board.trip_id == t2_alight.trip_id)
        .join(trip2, t2_board.trip_id == trip2.trip_id)
        
    
        .filter(
            t1_board.stop_id.in_(start_stop_ids),
            t2_alight.stop_id.in_(end_stop_ids),
            t1_board.stop_sequence < t1_alight.stop_sequence,
            t2_board.stop_sequence < t2_alight.stop_sequence,
            
        
            t1_board.departure_time >= departure_time_limit,
            t1_alight.arrival_time <= t2_board.departure_time
        )
        .order_by(t2_alight.arrival_time.asc())
        .limit(5)
        .all()
    )

    
    next_trains = []
    for start_time, end_time, trip in results:
        next_trains.append({
            "route_id": trip.route_id,
            "trip_headsign": trip.trip_headsign or f"To {end_stop_name}",
            "departure_time": start_time.departure_time,
            "arrival_time": end_time.arrival_time
        })

    return {"next_trains": next_trains}

def search_transfer_db(db: Session, start_station_name: str, end_station_name: str, PROJECT_CACHE: dict, departure_time_limit: str):
    """

    """
    stop_name_to_ids = PROJECT_CACHE["stop_name_to_ids"]
    stop_id_to_name = PROJECT_CACHE["stop_id_to_name"]

    start_ids = stop_name_to_ids.get(start_station_name, [])
    end_ids = stop_name_to_ids.get(end_station_name, [])

    if not start_ids or not end_ids:
        return {"status": "Success", "results": []}

 
    t1_board = aliased(models.StopTime)
    t1_alight = aliased(models.StopTime)

    t2_board = aliased(models.StopTime)
    t2_alight = aliased(models.StopTime)

    trip1 = aliased(models.Trip)
    trip2 = aliased(models.Trip)

    query_results = (
        db.query(t1_board, t1_alight, t2_board, t2_alight, trip1, trip2)
        

        .join(t1_alight, t1_board.trip_id == t1_alight.trip_id)
        .join(trip1, t1_board.trip_id == trip1.trip_id)
        
     
        .join(t2_board, t1_alight.stop_id == t2_board.stop_id)
        

        .join(t2_alight, t2_board.trip_id == t2_alight.trip_id)
        .join(trip2, t2_board.trip_id == trip2.trip_id)
        
    
        .filter(
            t1_board.stop_id.in_(start_ids),
            t2_alight.stop_id.in_(end_ids),
            t1_board.stop_sequence < t1_alight.stop_sequence,
            t2_board.stop_sequence < t2_alight.stop_sequence,
            t1_board.departure_time >= departure_time_limit
        )
        .order_by(t2_alight.arrival_time.asc())
        .limit(5)
        .all()
    )
   
    

    formatted_results = []
    for t1_b, t1_a, t2_b, t2_a, tr1, tr2 in query_results:
        if t1_a.arrival_time > t2_b.departure_time:
            continue
        
        path = [
            {
                "route_id": tr1.route_id,
                "board_station": start_station_name,
                "getoff_station": stop_id_to_name.get(t1_a.stop_id, "Unknown"),
                "departure_time": t1_b.departure_time,
                "arrival_time": t1_a.arrival_time
            },
            {
                "route_id": tr2.route_id,
                "board_station": stop_id_to_name.get(t2_b.stop_id, "Unknown"),
                "getoff_station": end_station_name,
                "departure_time": t2_b.departure_time,
                "arrival_time": t2_a.arrival_time
            }
        ]
        
        formatted_results.append({
            "real_departure_time": t1_b.departure_time,
            "real_arrival_time": t2_a.arrival_time,
            "status": "Success",
            "path": path
        })

    return {"status": "Success", "results": formatted_results}