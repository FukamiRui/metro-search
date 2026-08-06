import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")

print(f"DEBUG: The URL is -> {DATABASE_URL}")
print(f"DEBUG: GTFS directory -> {GTFS_DIR}")


def import_csv_to_db(file_name, table_name, use_cols):
    """
    Reads a GTFS CSV (TXT) file efficiently using Pandas
    and bulk-inserts the data into the PostgreSQL database.
    """

    file_path = os.path.join(GTFS_DIR, file_name)

    print(f"[PROCESS] Importing {file_path} into '{table_name}' table...")

    if not os.path.exists(file_path):
        print(f"❌ ERROR: File '{file_path}' not found.")
        return

    try:
        df = pd.read_csv(
            file_path,
            usecols=use_cols,
            dtype=str
        )

        df.to_sql(
            table_name,
            con=engine,
            if_exists="append",
            index=False
        )

        print(f"✅ SUCCESS: Loaded {len(df)} rows into '{table_name}' table.\n")

    except Exception as e:
        print(f"❌ ERROR: Failed to import {file_path}. Reason: {e}\n")


if __name__ == "__main__":
    print("=== STARTING MTA SUBWAY GTFS DATA IMPORT ===\n")

    import_csv_to_db(
        file_name="routes.txt",
        table_name="routes",
        use_cols=[
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_type"
        ]
    )

    import_csv_to_db(
        file_name="stops.txt",
        table_name="stops",
        use_cols=[
            "stop_id",
            "stop_name",
            "stop_lat",
            "stop_lon"
        ]
    )

    import_csv_to_db(
        file_name="trips.txt",
        table_name="trips",
        use_cols=[
            "trip_id",
            "route_id",
            "service_id",
            "trip_headsign"
        ]
    )

    import_csv_to_db(
        file_name="stop_times.txt",
        table_name="stop_times",
        use_cols=[
            "trip_id",
            "stop_id",
            "arrival_time",
            "departure_time",
            "stop_sequence"
        ]
    )

    print("=== ALL GTFS DATA IMPORTED SUCCESSFULLY ===")