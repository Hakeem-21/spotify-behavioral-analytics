import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set clean aesthetic style
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'Arial', 'font.family': 'sans-serif'})

DB_NAME = "spotify_analytics.db"
conn = sqlite3.connect(DB_NAME)

print("Generating visualizations from SQLite database...")

# -------------------------------------------------------------
# Chart 1: Funnel & Drop-off by Session Position
# -------------------------------------------------------------
query_funnel = """
SELECT 
    session_position,
    ROUND(CAST(SUM(CASE WHEN not_skipped = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) AS completion_rate,
    ROUND(CAST(SUM(CASE WHEN skip_1 = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) AS instant_skip_rate
FROM listening_sessions
WHERE session_position <= 15
GROUP BY session_position
ORDER BY session_position ASC;
"""
df_funnel = pd.read_sql_query(query_funnel, conn)

plt.figure(figsize=(10, 5))
plt.plot(df_funnel['session_position'], df_funnel['completion_rate'], marker='o', linewidth=2.5, color='#1DB954', label='Completion Rate (%)')
plt.plot(df_funnel['session_position'], df_funnel['instant_skip_rate'], marker='s', linewidth=2, linestyle='--', color='#E22134', label='Instant Skip (<5s) Rate (%)')
plt.title("Playback Retention Funnel Across Track Positions (1-15)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Track Position in Session", fontsize=11)
plt.ylabel("Percentage (%)", fontsize=11)
plt.xticks(df_funnel['session_position'])
plt.ylim(0, 100)
plt.legend(frameon=True)
plt.tight_layout()
plt.savefig("funnel_dropoff.png", dpi=300)
plt.close()
print("Saved: funnel_dropoff.png")

# -------------------------------------------------------------
# Chart 2: Skip Distribution: Free vs. Premium Tiers
# -------------------------------------------------------------
query_tiers = """
SELECT 
    CASE WHEN premium = 1 THEN 'Premium' ELSE 'Free Tier' END AS user_tier,
    ROUND(AVG(skip_1) * 100, 2) AS early_skips,
    ROUND(AVG(skip_2) * 100, 2) AS mid_skips,
    ROUND(AVG(not_skipped) * 100, 2) AS fully_completed
FROM listening_sessions
GROUP BY premium;
"""
df_tiers = pd.read_sql_query(query_tiers, conn)
df_melted = df_tiers.melt(id_vars=['user_tier'], value_vars=['early_skips', 'mid_skips', 'fully_completed'],
                          var_name='metric', value_name='percentage')

metric_labels = {
    'early_skips': 'Early Skips (<5s)',
    'mid_skips': 'Mid-Track Skips',
    'fully_completed': 'Completed Naturally'
}
df_melted['metric'] = df_melted['metric'].map(metric_labels)

plt.figure(figsize=(9, 5))
bar = sns.barplot(data=df_melted, x='metric', y='percentage', hue='user_tier', palette=['#1DB954', '#535353'])
plt.title("Behavioral Divergence: Free vs. Premium Subscription Tiers", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Playback Outcome", fontsize=11)
plt.ylabel("Percentage of Total Stream Events (%)", fontsize=11)
plt.ylim(0, 100)
for p in bar.patches:
    height = p.get_height()
    if height > 0:
        bar.annotate(f"{height:.1f}%", (p.get_x() + p.get_width() / 2., height + 1.5),
                     ha='center', va='baseline', fontsize=10, fontweight='semibold')
plt.legend(title="Tier", frameon=True)
plt.tight_layout()
plt.savefig("tier_behavior_comparison.png", dpi=300)
plt.close()
print("Saved: tier_behavior_comparison.png")

# -------------------------------------------------------------
# Chart 3: Acoustic Friction Heatmap (Skip vs Complete)
# -------------------------------------------------------------
query_acoustic = """
SELECT 
    CASE 
        WHEN ls.not_skipped = 1 THEN 'Completed'
        WHEN ls.skip_1 = 1 THEN 'Instant Skip'
        ELSE 'Mid Skip'
    END AS outcome,
    AVG(tf.danceability) AS danceability,
    AVG(tf.energy) AS energy,
    AVG(tf.valence) AS valence,
    AVG(tf.acousticness) AS acousticness,
    AVG(tf.speechiness) AS speechiness
FROM listening_sessions ls
JOIN track_features tf ON ls.track_id_clean = tf.track_id
GROUP BY outcome;
"""
df_acoustic = pd.read_sql_query(query_acoustic, conn).set_index('outcome')

plt.figure(figsize=(9, 4))
sns.heatmap(df_acoustic, annot=True, fmt=".3f", cmap="YlGnBu", cbar=True, linewidths=1)
plt.title("Acoustic Attribute Comparison by Playback Outcome", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Acoustic Features", fontsize=11)
plt.ylabel("Listening Outcome", fontsize=11)
plt.tight_layout()
plt.savefig("acoustic_friction_heatmap.png", dpi=300)
plt.close()
print("Saved: acoustic_friction_heatmap.png")

# -------------------------------------------------------------
# Chart 4: Session Churn Cliff (Skip Cascades)
# -------------------------------------------------------------
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
            WHEN skip_2 = 0 THEN '0. Completed'
            WHEN skip_2 = 1 AND prev_skip_1 = 0 THEN '1. First Skip'
            WHEN skip_2 = 1 AND prev_skip_1 = 1 AND prev_skip_2 = 0 THEN '2. Two Skips'
            WHEN skip_2 = 1 AND prev_skip_1 = 1 AND prev_skip_2 = 1 THEN '3. 3+ Skips'
            ELSE 'Other'
        END AS skip_streak_stage
    FROM session_events
)
SELECT 
    skip_streak_stage,
    ROUND(CAST(SUM(is_session_exit) AS FLOAT) / COUNT(*) * 100, 2) AS immediate_churn_rate_pct
FROM classified_events
WHERE skip_streak_stage != 'Other'
GROUP BY skip_streak_stage
ORDER BY skip_streak_stage ASC;
"""
df_churn = pd.read_sql_query(query_churn, conn)

plt.figure(figsize=(8, 5))
bar_churn = sns.barplot(
    data=df_churn,
    x="skip_streak_stage",
    y="immediate_churn_rate_pct",
    palette=["#1DB954", "#FFA726", "#FF7043", "#D32F2F"]
)
plt.title("Session Churn Cliff: Churn Rate vs. Skip Streak Length", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Consecutive Skip Streak Stage", fontsize=11)
plt.ylabel("Immediate Session Abandonment Rate (%)", fontsize=11)
plt.ylim(0, max(df_churn["immediate_churn_rate_pct"]) * 1.25)

for p in bar_churn.patches:
    height = p.get_height()
    if height > 0:
        bar_churn.annotate(
            f"{height:.2f}%",
            (p.get_x() + p.get_width() / 2.0, height),
            ha="center", va="bottom", xytext=(0, 4),
            textcoords="offset points", fontweight="bold", fontsize=10
        )
plt.tight_layout()
plt.savefig("churn_cascade_cliff.png", dpi=300)
plt.close()
print("Saved: churn_cascade_cliff.png")

# -------------------------------------------------------------
# Chart 5: Acoustic Delta Transitions (Context Whiplash)
# -------------------------------------------------------------
query_acoustic_deltas = """
WITH track_transitions AS (
    SELECT 
        ls.session_id,
        ls.session_position,
        ls.skip_1,
        ls.skip_2,
        ls.not_skipped,
        tf.energy,
        tf.danceability,
        LAG(tf.energy) OVER (
            PARTITION BY ls.session_id 
            ORDER BY ls.session_position
        ) AS prev_energy,
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
        ABS(energy - prev_energy) AS delta_energy,
        ABS(danceability - prev_danceability) AS delta_danceability,
        CASE 
            WHEN skip_1 = 1 THEN 'Instant Skip (<5s)'
            WHEN skip_2 = 1 THEN 'Mid Skip'
            WHEN not_skipped = 1 THEN 'Completed'
            ELSE 'Other'
        END AS outcome_label
    FROM track_transitions
    WHERE prev_energy IS NOT NULL
)
SELECT 
    outcome_label,
    ROUND(AVG(delta_energy), 4) AS avg_delta_energy,
    ROUND(AVG(delta_danceability), 4) AS avg_delta_danceability
FROM calculated_deltas
WHERE outcome_label != 'Other'
GROUP BY outcome_label
ORDER BY outcome_label ASC;
"""
df_deltas = pd.read_sql_query(query_acoustic_deltas, conn)

df_deltas_melted = df_deltas.melt(
    id_vars=["outcome_label"],
    value_vars=["avg_delta_energy", "avg_delta_danceability"],
    var_name="acoustic_metric",
    value_name="mean_delta"
)
df_deltas_melted["acoustic_metric"] = df_deltas_melted["acoustic_metric"].replace({
    "avg_delta_energy": "Δ Energy",
    "avg_delta_danceability": "Δ Danceability"
})

plt.figure(figsize=(9, 5))
bar_deltas = sns.barplot(
    data=df_deltas_melted,
    x="outcome_label",
    y="mean_delta",
    hue="acoustic_metric",
    palette=["#1DB954", "#2E77D0"]
)
plt.title("Acoustic Friction: Mean Absolute Shift (|Track_t - Track_t-1|)", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Playback Outcome", fontsize=11)
plt.ylabel("Mean Absolute Difference", fontsize=11)
plt.legend(title="Acoustic Dimension", frameon=True)

for p in bar_deltas.patches:
    height = p.get_height()
    if height > 0:
        bar_deltas.annotate(
            f"{height:.3f}",
            (p.get_x() + p.get_width() / 2.0, height),
            ha="center", va="bottom", xytext=(0, 4),
            textcoords="offset points", fontsize=9, fontweight="semibold"
        )
plt.tight_layout()
plt.savefig("acoustic_delta_comparison.png", dpi=300)
plt.close()
print("Saved: acoustic_delta_comparison.png")

# -------------------------------------------------------------
# Chart 6: Intent Vectors (Start Reason Performance)
# -------------------------------------------------------------
query_intent_vectors = """
SELECT 
    hist_user_behavior_reason_start AS start_reason,
    ROUND(AVG(skip_2) * 100, 2) AS skip_rate_pct
FROM listening_sessions
GROUP BY hist_user_behavior_reason_start
HAVING COUNT(*) > 100
ORDER BY skip_rate_pct DESC;
"""
df_intent = pd.read_sql_query(query_intent_vectors, conn)

plt.figure(figsize=(9, 5))
bar_intent = sns.barplot(
    data=df_intent,
    x="skip_rate_pct",
    y="start_reason",
    palette="crest_r"
)
plt.title("Intent Vectors: Skip Rate by Session Start Trigger", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Skip Rate (%)", fontsize=11)
plt.ylabel("Reason Start Trigger", fontsize=11)
plt.xlim(0, max(df_intent["skip_rate_pct"]) * 1.15)

for p in bar_intent.patches:
    width = p.get_width()
    bar_intent.annotate(
        f"{width:.1f}%",
        (width, p.get_y() + p.get_height() / 2.0),
        ha="left", va="center", xytext=(5, 0),
        textcoords="offset points", fontweight="bold", fontsize=9
    )
plt.tight_layout()
plt.savefig("intent_vector_breakdown.png", dpi=300)
plt.close()
print("Saved: intent_vector_breakdown.png")

# Finally close connection
conn.close()
print("\nAll 6 visual assets (Phase 1 & Phase 2) successfully generated!")