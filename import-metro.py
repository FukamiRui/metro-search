import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set.")

engine = create_engine(DATABASE_URL)

BASE_DIR = Path(__file__).resolve().parent
GTFS_DIR = BASE_DIR / "data" / "gtfs"

def import_csv_to_db(file_name: Path, table_name: str, use_cols: list[str]):
    """
    Reads a GTFS CSV (TXT) file efficiently using Pandas 
    and bulk-inserts the data into the PostgreSQL database.
    """
    print(f"[PROCESS] Importing {file_name.name} into '{table_name}' table...")
    
    if not file_name.exists():
        print(f"❌ ERROR: File '{file_name}' not found.")
        return

    try:
        df = pd.read_csv(file_name, usecols=use_cols, dtype=str)
  
        df = df.drop_duplicates()
        
        df.to_sql(table_name, con=engine, if_exists='append', index=False)
        print(f"✅ SUCCESS: Loaded {len(df)} rows into '{table_name}' table.\n")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to import {file_name.name}. Reason: {e}\n")

if __name__ == "__main__":
    print("=== STARTING MTA SUBWAY GTFS DATA IMPORT ===\n")
    
    import models
    from database import Base
    Base.metadata.create_all(bind=engine)
    
    # ① Import routes.txt
    import_csv_to_db(
        file_name=GTFS_DIR / "routes.txt",
        table_name="routes",
        use_cols=["route_id", "route_short_name", "route_long_name", "route_type"]
    )
    
    # ② Import trips.txt
    import_csv_to_db(
        file_name=GTFS_DIR / "trips.txt",
        table_name="trips",
        use_cols=["trip_id", "route_id", "service_id", "trip_headsign"]
    )

    # ③ Import stops.txt
    import_csv_to_db(
        file_name=GTFS_DIR / "stops.txt",
        table_name="stops",
        use_cols=["stop_id", "stop_name", "stop_lat", "stop_lon"]
    )
    
    # ④ Import stop_times.txt 
    import_csv_to_db(
        file_name=GTFS_DIR / "stop_times.txt",
        table_name="stop_times",
        use_cols=["trip_id", "stop_id", "arrival_time", "departure_time", "stop_sequence"]
    )

    print("=== ALL GTFS DATA IMPORTED SUCCESSFULLY ===")