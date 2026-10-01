import os
import sqlite3
import pandas as pd

# File paths
LOGS_FILE = "log_mini.csv"
TRACKS_FILE = "tf_mini.csv"
DB_NAME = "spotify_analytics.db"


def run_etl():
    if not os.path.exists(LOGS_FILE) or not os.path.exists(TRACKS_FILE):
        print(f"Error: Missing CSV files. Please check paths in: {os.getcwd()}")
        return

    print("--- Step 1: Loading CSV files into Pandas DataFrames ---")
    logs_df = pd.read_csv(LOGS_FILE)
    tracks_df = pd.read_csv(TRACKS_FILE)

    print(f"Loaded {len(logs_df):,} event log rows.")
    print(f"Loaded {len(tracks_df):,} track feature rows.")

    print("\n--- Step 2: Ingesting into SQLite Database ---")
    conn = sqlite3.connect(DB_NAME)

    # Ingest data into relational tables
    logs_df.to_sql("listening_sessions", conn, if_exists="replace", index=False)
    tracks_df.to_sql("track_features", conn, if_exists="replace", index=False)

    print("\n--- Step 3: Creating Indexes for Performance Optimization ---")
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON listening_sessions(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_track_id ON listening_sessions(track_id_clean);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tf_track_id ON track_features(track_id);")
    conn.commit()

    conn.close()
    print(f"\nETL Complete. Database '{DB_NAME}' created successfully with optimized indexes!")


if __name__ == "__main__":
    run_etl()