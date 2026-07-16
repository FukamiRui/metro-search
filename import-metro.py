import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Load environment variables and initialize database connection
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def import_csv_to_db(file_name, table_name, use_cols):
    """
    Reads a GTFS CSV (TXT) file efficiently using Pandas 
    and bulk-inserts the data into the PostgreSQL database.
    """
    print(f"[PROCESS] Importing {file_name} into '{table_name}' table...")
    
    # Check if the target file exists
    if not os.path.exists(file_name):
        print(f"❌ ERROR: File '{file_name}' not found.")
        return

    try:
        # Load only specified columns as string types for high performance
        df = pd.read_csv(file_name, usecols=use_cols, dtype=str)
        
        # Bulk insert into PostgreSQL (append to existing tables)
        df.to_sql(table_name, con=engine, if_exists='append', index=False)
        print(f"✅ SUCCESS: Loaded {len(df)} rows into '{table_name}' table.\n")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to import {file_name}. Reason: {e}\n")

if __name__ == "__main__":
    print("=== STARTING MTA SUBWAY GTFS DATA IMPORT ===\n")
    
    # ① Import routes.txt
    import_csv_to_db(
        file_name="routes.txt",
        table_name="routes",
        use_cols=["route_id", "route_short_name", "route_long_name", "route_type"]
    )
    
    # ② Import stops.txt
    import_csv_to_db(
        file_name="stops.txt",
        table_name="stops",
        use_cols=["stop_id", "stop_name", "stop_lat", "stop_lon"]
    )
    
    # ③ Import trips.txt
    import_csv_to_db(
        file_name="trips.txt",
        table_name="trips",
        use_cols=["trip_id", "route_id", "service_id", "trip_headsign"]
    )
    
    # ④ Import stop_times.txt (This is the largest dataset)
    import_csv_to_db(
        file_name="stop_times.txt",
        table_name="stop_times",
        use_cols=["trip_id", "stop_id", "arrival_time", "departure_time", "stop_sequence"]
    )

    print("=== ALL GTFS DATA IMPORTED SUCCESSFULLY ===")