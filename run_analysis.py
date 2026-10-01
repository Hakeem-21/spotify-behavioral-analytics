import sqlite3
import pandas as pd

# Display settings for clean terminal output
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

DB_NAME = "spotify_analytics.db"

def execute_query(title, query):
    print("=" * 80)
    print(f"QUERY: {title}")
    print("=" * 80)
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn)
    conn.close()
    print(df.to_string(index=False))
    print("\n")
    return df


# --- 1. Sessionization & Track Position Drop-off Funnel ---

query_funnel = """
WITH session_positions AS (
    SELECT 
        session_position,
        COUNT(*) AS total_track_plays,
        SUM(CASE WHEN not_skipped = 1 THEN 1 ELSE 0 END) AS fully_completed,
        SUM(CASE WHEN skip_1 = 1 THEN 1 ELSE 0 END) AS instant_skips,
        SUM(CASE WHEN skip_2 = 1 THEN 1 ELSE 0 END) AS mid_skips
    FROM listening_sessions
    WHERE session_position <= 10
    GROUP BY session_position
)
SELECT 
    session_position,
    total_track_plays,
    ROUND(CAST(fully_completed AS FLOAT) / total_track_plays * 100, 2) AS completion_rate_pct,
    ROUND(CAST(instant_skips AS FLOAT) / total_track_plays * 100, 2) AS instant_skip_rate_pct,
    ROUND(CAST(mid_skips AS FLOAT) / total_track_plays * 100, 2) AS mid_skip_rate_pct
FROM session_positions
ORDER BY session_position ASC;
"""

# --- 2. Skip Propensity by Subscription Tier (Free vs Premium) ---

query_tiers = """
SELECT 
    CASE WHEN premium = 1 THEN 'Premium' ELSE 'Free' END AS subscription_tier,
    COUNT(*) AS total_events,
    ROUND(AVG(skip_1) * 100, 2) AS early_skip_pct,
    ROUND(AVG(skip_2) * 100, 2) AS mid_skip_pct,
    ROUND(AVG(not_skipped) * 100, 2) AS completion_rate_pct,
    ROUND(AVG(hist_user_behavior_is_shuffle) * 100, 2) AS shuffle_adoption_pct
FROM listening_sessions
GROUP BY premium;
"""

# --- 3. Friction Detection: Consecutive Skip Chains using Window Functions ---

query_consecutive_skips = """
WITH lagged_skips AS (
    SELECT 
        session_id,
        session_position,
        skip_2 AS current_skipped,
        LAG(skip_2, 1) OVER (PARTITION BY session_id ORDER BY session_position) AS prev_track_skipped,
        LAG(skip_2, 2) OVER (PARTITION BY session_id ORDER BY session_position) AS two_tracks_ago_skipped,
        context_type
    FROM listening_sessions
)
SELECT 
    context_type,
    COUNT(*) AS total_plays,
    SUM(CASE WHEN current_skipped = 1 AND prev_track_skipped = 1 AND two_tracks_ago_skipped = 1 THEN 1 ELSE 0 END) AS three_consecutive_skips,
    ROUND(CAST(SUM(CASE WHEN current_skipped = 1 AND prev_track_skipped = 1 AND two_tracks_ago_skipped = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 3) AS consecutive_skip_rate_pct
FROM lagged_skips
GROUP BY context_type
ORDER BY consecutive_skip_rate_pct DESC;
"""

# --- 4. Acoustic Profile of Completed vs Skipped Tracks ---

query_acoustic_friction = """
SELECT 
    CASE 
        WHEN ls.not_skipped = 1 THEN 'Completed Naturally'
        WHEN ls.skip_1 = 1 THEN 'Instant Skip (<5s)'
        ELSE 'Mid-track Skip'
    END AS listening_outcome,
    COUNT(*) AS play_count,
    ROUND(AVG(tf.duration), 1) AS avg_duration_sec,
    ROUND(AVG(tf.danceability), 3) AS avg_danceability,
    ROUND(AVG(tf.energy), 3) AS avg_energy,
    ROUND(AVG(tf.tempo), 1) AS avg_tempo,
    ROUND(AVG(tf.valence), 3) AS avg_valence,
    ROUND(AVG(tf.us_popularity_estimate), 1) AS avg_popularity
FROM listening_sessions ls
JOIN track_features tf 
  ON ls.track_id_clean = tf.track_id
GROUP BY listening_outcome;
"""


# Query: Skip Cascade and Session Churn Probability

query_churn = """
WITH session_events AS (
    SELECT 
        session_id,
        session_position,
        skip_2,
        not_skipped,
        CASE 
            WHEN LEAD(session_position) OVER (
                PARTITION BY session_id 
                ORDER BY session_position
            ) IS NULL THEN 1 
            ELSE 0 
        END AS is_session_exit,
        LAG(skip_2, 1, 0) OVER (
            PARTITION BY session_id 
            ORDER BY session_position
        ) AS prev_skip_1,
        LAG(skip_2, 2, 0) OVER (
            PARTITION BY session_id 
            ORDER BY session_position
        ) AS prev_skip_2
    FROM listening_sessions
),
classified_events AS (
    SELECT 
        *,
        CASE 
            WHEN skip_2 = 0 THEN '0. No Skip (Completed)'
            WHEN skip_2 = 1 AND prev_skip_1 = 0 THEN '1. First Skip (Isolated)'
            WHEN skip_2 = 1 AND prev_skip_1 = 1 AND prev_skip_2 = 0 THEN '2. Two Consecutive Skips'
            WHEN skip_2 = 1 AND prev_skip_1 = 1 AND prev_skip_2 = 1 THEN '3. Three+ Consecutive Skips'
            ELSE 'Other'
        END AS skip_streak_stage
    FROM session_events
)
SELECT 
    skip_streak_stage,
    COUNT(*) AS total_occurrences,
    SUM(is_session_exit) AS session_exits,
    ROUND(CAST(SUM(is_session_exit) AS FLOAT) / COUNT(*) * 100, 2) AS immediate_churn_rate_pct
FROM classified_events
WHERE skip_streak_stage != 'Other'
GROUP BY skip_streak_stage
ORDER BY skip_streak_stage ASC;
"""


# Query 2: Acoustic Delta Transitions (Context Whiplash)


query_acoustic_deltas = """
WITH track_transitions AS (
    SELECT 
        ls.session_id,
        ls.session_position,
        ls.skip_1,
        ls.skip_2,
        ls.not_skipped,
        tf.energy,
        tf.tempo,
        tf.danceability,
        -- Look back at the previous track in the same session
        LAG(tf.energy) OVER (
            PARTITION BY ls.session_id 
            ORDER BY ls.session_position
        ) AS prev_energy,
        LAG(tf.tempo) OVER (
            PARTITION BY ls.session_id 
            ORDER BY ls.session_position
        ) AS prev_tempo,
        LAG(tf.danceability) OVER (
            PARTITION BY ls.session_id 
            ORDER BY ls.session_position
        ) AS prev_danceability
    FROM listening_sessions ls
    JOIN track_features tf 
      ON ls.track_id_clean = tf.track_id
),
calculated_deltas AS (
    SELECT 
        *,
        ABS(energy - prev_energy) AS delta_energy,
        ABS(tempo - prev_tempo) AS delta_tempo,
        ABS(danceability - prev_danceability) AS delta_danceability,
        CASE 
            WHEN skip_1 = 1 THEN '1. Skipped Very Early (<30s)'
            WHEN skip_2 = 1 THEN '2. Skipped Mid-Track'
            WHEN not_skipped = 1 THEN '3. Fully Completed'
            ELSE 'Other'
        END AS outcome_label
    FROM track_transitions
    WHERE prev_energy IS NOT NULL  -- Skip track 1 (no preceding track to compare)
)
SELECT 
    outcome_label,
    COUNT(*) AS sample_size,
    ROUND(AVG(delta_energy), 4) AS avg_delta_energy,
    ROUND(AVG(delta_tempo), 2) AS avg_delta_tempo_bpm,
    ROUND(AVG(delta_danceability), 4) AS avg_delta_danceability
FROM calculated_deltas
WHERE outcome_label != 'Other'
GROUP BY outcome_label
ORDER BY outcome_label ASC;
"""


# Query 3: Intent Vectors & Start Reason Performance

query_intent_vectors = """
SELECT 
    hist_user_behavior_reason_start AS start_reason,
    COUNT(*) AS total_plays,
    ROUND(AVG(skip_2) * 100, 2) AS skip_rate_pct,
    ROUND(AVG(not_skipped) * 100, 2) AS completion_rate_pct,
    -- Tracks ended by manual forward skip
    ROUND(SUM(CASE WHEN hist_user_behavior_reason_end = 'fwdbtn' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS manual_skip_end_pct,
    -- Tracks where user terminated playback
    ROUND(SUM(CASE WHEN hist_user_behavior_reason_end = 'endplay' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS session_stop_pct
FROM listening_sessions
GROUP BY hist_user_behavior_reason_start
HAVING COUNT(*) > 100
ORDER BY total_plays DESC;
"""





if __name__ == "__main__":

    execute_query("1. Session Funnel & Drop-off by Track Position", query_funnel)
    execute_query("2. Free vs Premium Behavioral Divergence", query_tiers)
    execute_query("3. Playback Friction: Consecutive Skip Chains (LAG Window Function)", query_consecutive_skips)
    execute_query("4. Acoustic Profile: Full Completion vs Instant Skip", query_acoustic_friction)
    df_churn = execute_query("Skip Cascade and Churn Probability", query_churn)
    df_deltas = execute_query("Acoustic Delta Transitions", query_acoustic_deltas)
    df_intent = execute_query("Intent Vectors and Start Reason Performance", query_intent_vectors)
