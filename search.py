from collections import deque
import math
import bisect  # ⚡️ これを使って時間軸の二分探索を行います[cite: 4]

def search_direct_cached(start_name: str, end_name: str, cache_data: dict, departure_time_limit: str = "00:00:00"):
    departure_time_limit = str(departure_time_limit).strip()
    
    stop_name_to_ids = cache_data["stop_name_to_ids"]
    station_departure_map = cache_data["station_departure_map"]
    station_departure_times_only = cache_data["station_departure_times_only"]  # 💡 O(1)で取得
    trip_schedules = cache_data["trip_schedules"]
    trip_id_to_object = cache_data["trip_id_to_object"]

    start_ids = stop_name_to_ids.get(start_name, [])
    end_ids = set(stop_name_to_ids.get(end_name, []))

    if not start_ids or not end_ids:
        return {"status": "Success", "next_trains": []}

    active_departures = []
    for sid in start_ids:
        deps = station_departure_map.get(sid, [])
        dep_times = station_departure_times_only.get(sid, [])  # 💡 メモリ内の配列を直接参照
        
        if not deps:
            continue
        
        # ⚡️ O(N)の再構築ループを回避し、完全な O(log N) でのピンポイント切り出し[cite: 4]
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
            # 探索の枝刈り：直近の便のみを考慮
            for dep in departures[start_idx : start_idx + 5]:
                trip_id = dep["trip_id"]
                schedules = trip_schedules.get(trip_id, [])
                
                for sch in schedules:
                    if sch["stop_sequence"] <= dep["stop_sequence"]: continue
                    
                    next_sid = sch["stop_id"]
                    arr_time = sch["arrival_time"]
                    if not arr_time: continue

                    # 目的地判定を最優先
                    if next_sid in end_station_ids:
                        results.append({
                            "real_arrival_time": arr_time,
                            "path": path + [{"route_id": trip_to_route.get(trip_id), "board_station": current_station, "getoff_station": stop_id_to_name.get(next_sid), "departure_time": dep["departure_time"], "arrival_time": arr_time}]
                        })
                        continue

                    # 次の駅を探索
                    next_s_name = stop_id_to_name.get(next_sid)
                    if next_s_name and (next_s_name not in visited_stations or visited_stations[next_s_name] > arr_time):
                        visited_stations[next_s_name] = arr_time
                        queue.append((next_s_name, arr_time, path + [{"route_id": trip_to_route.get(trip_id), "board_station": current_station, "getoff_station": next_s_name, "departure_time": dep["departure_time"], "arrival_time": arr_time}]))

    return {"status": "Success", "results": sorted(results, key=lambda x: x["real_arrival_time"])}

def calculate_nearest_station(user_lat: float, user_lon: float, spatial_cache: list) -> str:
    """
    🌍 メモリ内の空間データから最も物理距離が近い駅名を確定
    """
    best_station = None
    min_distance_km = float('inf')
    R = 6371.0
    
    user_lat_rad = math.radians(user_lat)
    user_lon_rad = math.radians(user_lon)

    if user_lat == None or user_lon == None:
        return None
    
    for station in spatial_cache:
        try:
            # 💡 models.py の変数名に修正
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