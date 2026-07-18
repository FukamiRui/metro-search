from contextlib import asynccontextmanager
import math
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from database import engine, get_db, SessionLocal
import models
from search import search_direct_db, search_transfer_db
from fastapi.responses import HTMLResponse
import tracemalloc
import time

models.Base.metadata.create_all(bind=engine)


# In memorize all required datas at the first
PROJECT_CACHE = {
    "all_stations": [],          
    "stations_spatial_data": [], 
    "stop_id_to_name": {},
    "stop_name_to_ids": {},
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading NYC Subway GTFS and Spatial data into memory...")
   
    #Scaling speed
    tracemalloc.start()
    start_time = time.time()

    db = SessionLocal()
    try:
        stations = db.query(models.Stop).order_by(models.Stop.stop_name.asc()).all()
        PROJECT_CACHE["all_stations"] = [{"stop_name": s.stop_name} for s in stations]
        
        spatial_list = []
        for s in stations:
            if s.stop_lat and s.stop_lon:
                try:
                    
                    spatial_list.append({
                        "stop_name": s.stop_name,
                        "stop_lat": float(s.stop_lat),
                        "stop_lon": float(s.stop_lon)
                    })
                except ValueError:
                    continue
        PROJECT_CACHE["stations_spatial_data"] = spatial_list
        
        PROJECT_CACHE["stop_id_to_name"] = {s.stop_id: s.stop_name for s in stations}
        for s in stations:
            PROJECT_CACHE["stop_name_to_ids"].setdefault(s.stop_name, []).append(s.stop_id)
        
        print("Caching all stop times...")
        

        current_memory, peak_memory = tracemalloc.get_traced_memory()
        end_time = time.time()
        tracemalloc.stop()

        print(f" Time taking: {end_time - start_time:.2f} sec")
        print(f" Current Memory Usage: {current_memory / 10**6:.2f} MB")
        print(f" Peak Memory Usage: {peak_memory / 10**6:.2f} MB")
        # --------------------------------------------------------

        
        print(" GTFS & Spatial Data successfully cached. System is fully in-memory!")
        
    except Exception as e:
        print(f" Error during cache initialization: {e}")
    finally:
        db.close()

    yield

    print("Clearing memory cache...")
    for key in PROJECT_CACHE:
        PROJECT_CACHE[key].clear()


app = FastAPI(title="NYC Subway Route API", version="1.0.0", lifespan=lifespan)

origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def calculate_nearest_station(user_lat: float, user_lon: float) -> str:
    #1. Load caching check and loading
    stations_data = PROJECT_CACHE.get("stations_spatial_data")
    if not stations_data:
        print("Debug: stations_data is empty, loading now...")
        db = SessionLocal()
        try:
 
            # Assign station again and load
            stations = db.query(models.Stop).all()
            stations_data = [
                {"stop_name": s.stop_name, "stop_lat": float(s.stop_lat), "stop_lon": float(s.stop_lon)}
                for s in stations if s.stop_lat and s.stop_lon
            ]
            PROJECT_CACHE["stations_spatial_data"] = stations_data
        finally:
            db.close()
    if not stations_data:
        return None
    
    # 2. Culculation for distance with lan and lon
    best_station = None
    min_distance = float('inf')
    lat_to_km = 111.0
    lon_to_km = 85.0 
    # Debug
    print(f"Debug: Loaded {len(stations_data)} stations. Searching for {user_lat}, {user_lon}")
    try:
        user_lat = float(user_lat)
        user_lon = float(user_lon)
    except(ValueError, TypeError):
        return None
    
    for station in stations_data:
       

        d_lat = (station["stop_lat"] - user_lat) * lat_to_km
        d_lon = (station["stop_lon"] - user_lon) * lon_to_km
        distance_sq = d_lat**2 + d_lon**2 

        if distance_sq < min_distance:
            min_distance = distance_sq
            best_station = station["stop_name"]
    if min_distance >= 2:
         return None  
    return best_station


@app.get("/")
async def get_index():
    # load index.html
    file_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/search_route")
async def run_search_route(
    end_stop_name: str, 
    start_stop_name: str = None, 
    user_lat: float = None, 
    user_lon: float = None,
    departure_time_limit: str = "00:00:00", 
    db: Session = Depends(get_db)
):
    departure_time_limit = departure_time_limit.strip()

    if user_lat is not None and user_lon is not None:
        detected_start = calculate_nearest_station(user_lat, user_lon)
        if detected_start:
            start_stop_name = detected_start
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="Spatial cache is empty or system is warming up."
            )
    
    if not start_stop_name or start_stop_name not in PROJECT_CACHE["stop_name_to_ids"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Start station name or GPS coordinates required."
        )
    elif not end_stop_name or end_stop_name not in PROJECT_CACHE["stop_name_to_ids"] :
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination name of GPS coordinates required"
        )
    
    

    direct_res = search_direct_db(db, start_stop_name, end_stop_name, PROJECT_CACHE, departure_time_limit)
    transfer_res = search_transfer_db(db, start_stop_name, end_stop_name, PROJECT_CACHE, departure_time_limit)
    
    combined_trains = []
    
    # --- Format Direct Results ---
    direct_list = []
    if direct_res is not None and isinstance(direct_res, dict):
        direct_list = direct_res.get("next_trains") or []
    
    for t in direct_list:
        combined_trains.append({
            "is_direct": True,
            "route_id": str(t.get("route_id", "1")).strip(),
            "trip_headsign": str(t.get("trip_headsign", f"To {end_stop_name}")).strip(),
            "departure_time": t.get("departure_time"),
            "arrival_time": t.get("arrival_time"),
            "description": f"Direct Route (Started from nearest station: {start_stop_name})" if (user_lat and user_lon) else "Direct Route",
            "fare": "$2.90",
            "transfer_count": 0
        })
            
    # --- Format Transfer Results ---
    if transfer_res is not None and isinstance(transfer_res, dict):
        if transfer_res.get("status") == "Success" and "results" in transfer_res:
            for route_obj in transfer_res["results"]:
                path_data = route_obj.get("path", [])
                if not path_data:
                    continue
                
               
                route_list = []
                for p in path_data:
                    r_id = str(p.get("route_id", "")).strip()
                    if r_id not in route_list:
                        route_list.append(r_id)
                
                is_actually_direct = len(route_list) == 1
                transfer_count = len(path_data) - 1
                
                transfer_details = []
                for p in path_data:
                    r_id = str(p.get("route_id", "")).strip()
                    b_st = str(p.get("board_station", "")).strip()
                    d_tm = str(p.get("departure_time", "")).strip()
                    g_st = str(p.get("getoff_station", "")).strip()
                    a_tm = str(p.get("arrival_time", "")).strip()
                    transfer_details.append(f"Route {r_id} ({b_st} {d_tm} -> {g_st} {a_tm})")
                
                description_text = " -> ".join(transfer_details)
                if user_lat and user_lon:
                    description_text = f"[Walk to {start_stop_name}] -> " + description_text
                
                combined_trains.append({
                    "is_direct": is_actually_direct,
                    "route_id": " -> ".join(route_list),
                    "trip_headsign": f"To {end_stop_name}",
                    "departure_time": str(route_obj.get("real_departure_time")).strip(),
                    "arrival_time": str(route_obj.get("real_arrival_time")).strip(),
                    "description": "Direct Route" if is_actually_direct else description_text,
                    "fare": "$2.90",
                    "transfer_count": 0 if is_actually_direct else transfer_count
                })

    seen_trips = set()
    unique_combined = []
    for train in combined_trains:
        key = f"{train['departure_time']}_{train['route_id']}"
        if key not in seen_trips:
            seen_trips.add(key)
            unique_combined.append(train)

    unique_combined.sort(key=lambda x: x["departure_time"])
    
    return {
        "status": "Success",
        "origin_station": start_stop_name, 
        "all_trains": unique_combined
    }


@app.get("/check_stations")
async def get_all_stations(db: Session = Depends(get_db)):
    cached_data = PROJECT_CACHE.get("stations_spatial_data")
    if cached_data:
        return {
            "status": "Success",
            "sample_stations": cached_data
        }
    
    print("Warning: Spatial cache is empty. Falling back to direct DB query...")
    stations = db.query(models.Stop).order_by(models.Stop.stop_name.asc()).all()
    spatial_list = []
    for s in stations:
        if s.stop_lat and s.stop_lon:
            try:
                spatial_list.append({
                    "stop_name": s.stop_name,
                    "stop_lat": float(s.stop_lat),
                    "stop_lon": float(s.stop_lon)
                })
            except ValueError:
                continue
                
    return {
        "status": "Success",
        "sample_stations": spatial_list
    }
