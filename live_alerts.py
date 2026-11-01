import json
import time
import urllib.request

import models

ALERTS_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json"
FEED_NAME = "subway-alerts"
REFRESH_SECONDS = 60


def english_text(block):
    if not block:
        return ""
    for translation in block.get("translation", []):
        if translation.get("language") == "en":
            return translation.get("text", "")
    return ""


def parse_alerts(feed):
    rows = []
    for entity in feed.get("entity", []):
        alert = entity.get("alert", {})

        routes = []
        stops = []
        for informed in alert.get("informed_entity", []):
            route_id = informed.get("route_id")
            stop_id = informed.get("stop_id")
            if route_id and route_id not in routes:
                routes.append(route_id)
            if stop_id and stop_id not in stops:
                stops.append(stop_id)

        periods = alert.get("active_period") or [{}]
        period = periods[0]
        mercury = alert.get("transit_realtime.mercury_alert", {})

        rows.append(models.ServiceAlert(
            alert_id=entity.get("id"),
            alert_type=mercury.get("alert_type"),
            header=english_text(alert.get("header_text")),
            description=english_text(alert.get("description_text")),
            routes=json.dumps(routes),
            stops=json.dumps(stops),
            start_time=period.get("start"),
            end_time=period.get("end"),
        ))
    return rows


def get_refresh_record(db):
    return db.query(models.FeedRefresh).filter(models.FeedRefresh.feed_name == FEED_NAME).first()


def refresh_alerts(db):
    with urllib.request.urlopen(ALERTS_URL, timeout=30) as response:
        feed = json.load(response)

    rows = parse_alerts(feed)
    now = int(time.time())

    db.query(models.ServiceAlert).delete()
    db.add_all(rows)

    record = get_refresh_record(db)
    if record is None:
        db.add(models.FeedRefresh(feed_name=FEED_NAME, refreshed_at=now))
    else:
        record.refreshed_at = now
    db.commit()


def load_alerts(db):
    record = get_refresh_record(db)
    is_stale = record is None or int(time.time()) - record.refreshed_at > REFRESH_SECONDS
    if is_stale:
        try:
            refresh_alerts(db)
        except Exception as e:
            db.rollback()
            print(f"Alert refresh failed, using stored alerts: {e}")

    now = int(time.time())
    alerts = []
    for row in db.query(models.ServiceAlert).all():
        if row.end_time and row.end_time < now:
            continue
        alerts.append({
            "id": row.alert_id,
            "type": row.alert_type,
            "header": row.header,
            "description": row.description,
            "routes": json.loads(row.routes),
            "stops": json.loads(row.stops),
            "start": row.start_time,
            "end": row.end_time,
        })
    return alerts
