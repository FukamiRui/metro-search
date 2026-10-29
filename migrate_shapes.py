import os
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gtfs")

trips = pd.read_csv(os.path.join(GTFS_DIR, "trips.txt"), usecols=["trip_id", "shape_id"], dtype=str)
shapes = pd.read_csv(os.path.join(GTFS_DIR, "shapes.txt"), dtype=str)
feed = pd.read_csv(os.path.join(GTFS_DIR, "feed_info.txt"), dtype=str)

print("[1/4] Adding shape_id column to trips...")
with engine.begin() as c:
    c.execute(text("ALTER TABLE trips ADD COLUMN IF NOT EXISTS shape_id VARCHAR"))

print("[2/4] Writing trip to shape mapping...")
trips.to_sql("trip_shapes", con=engine, if_exists="replace", index=False, chunksize=10000, method="multi")
with engine.begin() as c:
    c.execute(text("UPDATE trips SET shape_id = ts.shape_id FROM trip_shapes ts WHERE trips.trip_id = ts.trip_id"))
    c.execute(text("DROP TABLE trip_shapes"))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_trips_shape_id ON trips (shape_id)"))

print("[3/4] Loading shape points (this can take a minute)...")
shapes.to_sql("shapes", con=engine, if_exists="replace", index=False, chunksize=10000, method="multi")
with engine.begin() as c:
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_shapes_shape_id ON shapes (shape_id)"))

print("[4/4] Loading feed info...")
feed.to_sql("feed_info", con=engine, if_exists="replace", index=False)

with engine.connect() as c:
    filled = c.execute(text("SELECT count(*) FROM trips WHERE shape_id IS NOT NULL")).scalar()
    points = c.execute(text("SELECT count(*) FROM shapes")).scalar()
print(f"Done. Trips with shape: {filled}, shape points: {points}")
