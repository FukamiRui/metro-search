import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from google.transit import gtfs_realtime_pb2

import models

FEED_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F"
FEED_NAMES = ["gtfs-ace", "gtfs-bdfm", "gtfs-g", "gtfs-jz", "gtfs-nqrw", "gtfs-l", "gtfs", "gtfs-si"]
FEED_RECORD = "subway-vehicles"
REFRESH_SECONDS = 30


def fetch_feed(name):
    with urllib.request.urlopen(FEED_BASE + name, timeout=30) as response:
        raw = response.read()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw)
    return feed


def parse_vehicles(feeds):
    rows = []
    for feed in feeds:
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            vehicle = entity.vehicle
            rows.append(models.VehiclePosition(
                trip_id=vehicle.trip.trip_id,
                route_id=vehicle.trip.route_id,
                stop_id=vehicle.stop_id,
                status=gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name(vehicle.current_status),
                timestamp=vehicle.timestamp,
            ))
    return rows


def get_refresh_record(db):
    return db.query(models.FeedRefresh).filter(models.FeedRefresh.feed_name == FEED_RECORD).first()


def refresh_vehicles(db):
    with ThreadPoolExecutor(max_workers=len(FEED_NAMES)) as pool:
        feeds = list(pool.map(fetch_feed, FEED_NAMES))

    rows = parse_vehicles(feeds)
    now = int(time.time())

    db.query(models.VehiclePosition).delete()
    db.add_all(rows)

    record = get_refresh_record(db)
    if record is None:
        db.add(models.FeedRefresh(feed_name=FEED_RECORD, refreshed_at=now))
    else:
        record.refreshed_at = now
    db.commit()


def load_vehicles(db):
    record = get_refresh_record(db)
    is_stale = record is None or int(time.time()) - record.refreshed_at > REFRESH_SECONDS
    if is_stale:
        try:
            refresh_vehicles(db)
        except Exception as e:
            db.rollback()
            print(f"Vehicle refresh failed, using stored positions: {e}")

    stops = {}
    for stop in db.query(models.Stop).all():
        stops[stop.stop_id] = stop

    vehicles = []
    for row in db.query(models.VehiclePosition).all():
        stop = stops.get(row.stop_id)
        vehicles.append({
            "trip_id": row.trip_id,
            "route": row.route_id,
            "status": row.status,
            "stop_id": row.stop_id,
            "stop_name": stop.stop_name if stop else None,
            "lat": float(stop.stop_lat) if stop else None,
            "lon": float(stop.stop_lon) if stop else None,
            "timestamp": row.timestamp,
        })
    return vehicles
