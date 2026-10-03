"""
Spotify Analytics - Automated Power BI Data Pipeline
---------------------------------------------------
Parses analytical queries from 'analysis_queries.sql', executes them
against 'spotify_analytics.db', reshapes/cleans metrics into business-friendly
labels, and exports CSV files into 'powerbi_data/' for Power BI ingestion.
"""

import os
import re
import sqlite3
import pandas as pd

# Configuration & Constants
DB_PATH = "spotify_analytics.db"
SQL_FILE_PATH = "analysis_queries.sql"
OUTPUT_DIR = "powerbi_data"

# Label Mappings for Clean BI Presentation
REASON_LABEL_MAP = {
    "trackdone": "Autoplay (Track Finished)",
    "fwdbtn": "Forward Skip Button",
    "clickrow": "Manual Song Selection",
    "appstart": "App Launch",
    "backbtn": "Back Button",
    "playbtn": "Play / Resume Button",
    "remote": "Remote Device Transfer",
    "popup": "In-App Notification / Popup",
}

TIER_METRIC_MAP = {
    "early_skip_pct": "Early Skip Rate (<5s)",
    "mid_skip_pct": "Mid-Track Skip Rate",
    "completion_rate_pct": "Full Completion Rate",
    "shuffle_adoption_pct": "Shuffle Adoption Rate",
}

ACOUSTIC_DELTA_METRIC_MAP = {
    "avg_delta_energy": "Δ Energy",
    "avg_delta_danceability": "Δ Danceability",
    "avg_delta_tempo_bpm": "Δ Tempo (BPM)",
}


def ensure_output_directory(directory_path: str) -> None:
    """Ensures the destination output directory exists."""
    os.makedirs(directory_path, exist_ok=True)


def parse_sql_queries(filepath: str) -> dict[str, str]:
    """
    Parses tagged SQL queries (-- [query_name]) from a .sql file
    into a clean dictionary of {query_name: query_sql}.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"SQL file not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as file:
        sql_content = file.read()

    pattern = r"--\s*\[(\w+)\]\s*\n(.*?)(?=(?:--\s*\[\w+\])|\Z)"
    matches = re.findall(pattern, sql_content, re.DOTALL)

    return {name.strip(): query.strip() for name, query in matches}


def export_funnel_metrics(conn: sqlite3.Connection, query: str) -> None:
    """Visual 1: Playback Retention Funnel across session positions."""
    print("  -> Exporting: pbi_funnel.csv...")
    df = pd.read_sql_query(query, conn)

    # Rename columns to match Power BI schema
    df = df.rename(columns={
        "completion_rate_pct": "completion_rate",
        "instant_skip_rate_pct": "instant_skip_rate"
    })

    target_cols = [c for c in ["session_position", "completion_rate", "instant_skip_rate"] if c in df.columns]
    output_path = os.path.join(OUTPUT_DIR, "pbi_funnel.csv")
    df[target_cols].to_csv(output_path, index=False)


def export_tier_divergence(conn: sqlite3.Connection, query: str) -> None:
    """Visual 2: Subscription Tier Behavioral Comparison (Free vs Premium)."""
    print("  -> Exporting: pbi_tiers.csv...")
    df_raw = pd.read_sql_query(query, conn)
    df_raw = df_raw.rename(columns={"subscription_tier": "user_tier"})

    metric_cols = [c for c in TIER_METRIC_MAP.keys() if c in df_raw.columns]
    df_melted = pd.melt(
        df_raw,
        id_vars=["user_tier"],
        value_vars=metric_cols,
        var_name="metric",
        value_name="percentage",
    )
    df_melted["metric"] = df_melted["metric"].map(TIER_METRIC_MAP).fillna(df_melted["metric"])

    output_path = os.path.join(OUTPUT_DIR, "pbi_tiers.csv")
    df_melted.to_csv(output_path, index=False)


def export_acoustic_matrix(conn: sqlite3.Connection, query: str) -> None:
    """Visual 3: Acoustic Attribute Profile Matrix (Melted for Heatmap)."""
    print("  -> Exporting: pbi_acoustic_heatmap.csv...")
    df_raw = pd.read_sql_query(query, conn)
    df_raw = df_raw.rename(columns={"listening_outcome": "outcome"})

    feature_cols = [c for c in df_raw.columns if c.startswith("avg_")]
    df_melted = pd.melt(
        df_raw,
        id_vars=["outcome"],
        value_vars=feature_cols,
        var_name="acoustic_feature",
        value_name="mean_score",
    )
    df_melted["acoustic_feature"] = (
        df_melted["acoustic_feature"]
        .str.replace("avg_", "", regex=False)
        .str.replace("_", " ", regex=False)
        .str.title()
    )

    output_path = os.path.join(OUTPUT_DIR, "pbi_acoustic_heatmap.csv")
    df_melted.to_csv(output_path, index=False)


def export_churn_cliff(conn: sqlite3.Connection, query: str) -> None:
    """Visual 4: Skip Streak Stage vs Immediate Session Churn Probability."""
    print("  -> Exporting: pbi_churn_cliff.csv...")
    df = pd.read_sql_query(query, conn)

    target_cols = [c for c in ["skip_streak_stage", "immediate_churn_rate_pct"] if c in df.columns]
    output_path = os.path.join(OUTPUT_DIR, "pbi_churn_cliff.csv")
    df[target_cols].to_csv(output_path, index=False)


def export_acoustic_deltas(conn: sqlite3.Connection, query: str) -> None:
    """Visual 5: Track Transition Delta Shock (|Track_t - Track_{t-1}|)."""
    print("  -> Exporting: pbi_acoustic_deltas.csv...")
    df_raw = pd.read_sql_query(query, conn)

    delta_cols = [c for c in df_raw.columns if "delta" in c]
    df_melted = pd.melt(
        df_raw,
        id_vars=["outcome_label"],
        value_vars=delta_cols,
        var_name="acoustic_metric",
        value_name="mean_delta",
    )
    df_melted["acoustic_metric"] = (
        df_melted["acoustic_metric"]
        .map(ACOUSTIC_DELTA_METRIC_MAP)
        .fillna(df_melted["acoustic_metric"])
    )

    output_path = os.path.join(OUTPUT_DIR, "pbi_acoustic_deltas.csv")
    df_melted.to_csv(output_path, index=False)


def export_intent_vectors(conn: sqlite3.Connection, query: str) -> None:
    """Visual 6: Playback Initiation Trigger Performance & Skip Rates."""
    print("  -> Exporting: pbi_intent_vectors.csv...")
    df = pd.read_sql_query(query, conn)

    # Convert cryptic app codes to clean executive labels
    df["start_reason"] = df["start_reason"].map(REASON_LABEL_MAP).fillna(df["start_reason"])

    target_cols = [c for c in ["start_reason", "skip_rate_pct"] if c in df.columns]
    output_path = os.path.join(OUTPUT_DIR, "pbi_intent_vectors.csv")
    df[target_cols].to_csv(output_path, index=False)


def run_pipeline() -> None:
    """Main orchestration function to execute all export stages."""
    print("=" * 60)
    print("Spotify Behavioral Analytics - Power BI Data Pipeline")
    print("=" * 60)

    ensure_output_directory(OUTPUT_DIR)
    queries = parse_sql_queries(SQL_FILE_PATH)
    print(f"Loaded {len(queries)} tagged SQL queries from '{SQL_FILE_PATH}'.\n")

    conn = sqlite3.connect(DB_PATH)

    try:
        if "query_funnel" in queries:
            export_funnel_metrics(conn, queries["query_funnel"])
        if "query_tiers" in queries:
            export_tier_divergence(conn, queries["query_tiers"])
        if "query_acoustic_profile" in queries:
            export_acoustic_matrix(conn, queries["query_acoustic_profile"])
        if "query_churn" in queries:
            export_churn_cliff(conn, queries["query_churn"])
        if "query_acoustic_deltas" in queries:
            export_acoustic_deltas(conn, queries["query_acoustic_deltas"])
        if "query_intent_vectors" in queries:
            export_intent_vectors(conn, queries["query_intent_vectors"])

        print("\nAll 6 staging CSVs successfully updated!")
    finally:
        conn.close()


if __name__ == "__main__":
    run_pipeline()