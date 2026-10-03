# Spotify User Behavior & Session Churn Analytics

An end-to-end data analytics and business intelligence pipeline uncovering session abandonment dynamics, subscription tier friction, acoustic transition shock, and consecutive skip cascades. Built with SQLite, Python, and Microsoft Power BI.

---

## 📌 Project Overview
User churn on music streaming platforms often manifests within individual listening sessions before leading to long-term account cancellation. This project analyzes the behavioral patterns behind track skips and session drop-offs by processing playback event logs and audio feature metadata.

### Core Objectives
* **Session Drop-off Funnel:** Measure track-by-track retention and skip progression across session positions 1–15.
* **Tier Divergence Analysis:** Compare behavioral friction (early skips, mid-track skips, shuffle adoption) between Free and Premium subscribers.
* **Acoustic Transition Whiplash:** Quantify $\vert{}Track_t - Track_{t-1}\vert{}$ deltas in energy, danceability, and tempo to evaluate acoustic dissonance causing immediate (<5s) abandonment.
* **Skip Cascade Dynamics:** Model immediate session churn probability as consecutive skip streaks compound (0 to 3+ skips) using SQL window functions.
* **Intent Vector Analysis:** Evaluate playback initiation triggers (Manual Selection, Continuous Autoplay, Forward Skip Button, App Launch) against skip vulnerability and session completion.

---

## 🏗 Architecture & Pipeline Design

The project enforces a **Single Source of Truth (SSOT)** and **Separation of Concerns** pattern:

```text
[Raw Logs & Track Features]
  (log_mini.csv, tf_mini.csv)
             │
             ▼
      etl_pipeline.py
             │
             ▼
  [SQLite Database Engine]
   (spotify_analytics.db)
             │
             ├─── reads tagged queries ◄─── analysis_queries.sql
             ▼                              (Single Source of Truth)
    export_to_powerbi.py
   (Cleans labels & unpivots matrices)
             │
             ▼
   [Staging Layer: /powerbi_data]
   ├── pbi_funnel.csv
   ├── pbi_tiers.csv
   ├── pbi_acoustic_heatmap.csv
   ├── pbi_churn_cliff.csv
   ├── pbi_acoustic_deltas.csv
   └── pbi_intent_vectors.csv
             │
             ▼
 [Power BI Executive Report]
(spotify_behavioral_dashboard.pbix)
```
---
* Ingestion Layer (etl_pipeline.py): Ingests raw session event logs and track audio features into an indexed local SQLite database (spotify_analytics.db).

* Analytical Engine (analysis_queries.sql): Central repository of production-grade SQL queries leveraging Common Table Expressions (CTEs), multi-step window functions (LAG(), LEAD()), and conditional aggregations.

* Orchestrator & Export Pipeline (export_to_powerbi.py): Parses tagged SQL queries using regex, executes them, translates raw internal codes into business-friendly dimensions (e.g., mapping clickrow to Manual Song Selection), reshapes data matrices, and writes staging CSVs to powerbi_data/.

* BI Presentation Layer (spotify_behavioral_dashboard.pbix): A custom-designed dark-mode Power BI dashboard styled with Spotify's brand identity.
---
## 📊 Power BI Dashboard Visuals
* Playback Retention Funnel (Line and Clustered Column Chart): Tracks completion rate vs. early (<5s) and mid-track skip rates across session positions 1–15.
* Subscription Tier Divergence (Clustered Column Chart): Compares Free vs. Premium tiers across early skips, mid-track skips, completion rates, and shuffle adoption.
* Acoustic Attribute Profile (Matrix Heatmap): Displays mean normalized scores for danceability, energy, tempo, valence, and popularity across listening outcomes (Completed Naturally, Instant Skip, Mid-track Skip).
* Session Churn Cliff (Clustered Column Chart): Visualizes the probability of immediate session termination across compounding skip streaks (0. Completed, 1. First Skip, 2. Two Skips, 3. 3+ Skips).
* Acoustic Transition Shock (Clustered Column Chart): Quantifies average acoustic step-change ($\vert{}\Delta\vert{}$) in energy, tempo, and danceability between adjacent songs.
* Playback Intent Vectors (Clustered Bar Chart): Measures skip rates across initiation triggers (Manual Song Selection, Autoplay, Forward Skip Button, App Launch).
---
## 🛠 Tech Stack
* **Database:** SQLite3

* **Data Processing & ETL:** Python 3 (Pandas, SQLite3, Regular Expressions)

* **Query Engineering:** Advanced SQL (CTEs, Window Functions, Lag/Lead Analysis)

* **Business Intelligence:** Microsoft Power BI Desktop
---
## 📁 Repository Structure
```text
├── powerbi_data/                    # Clean staging CSVs feeding Power BI
│   ├── pbi_acoustic_deltas.csv
│   ├── pbi_acoustic_heatmap.csv
│   ├── pbi_churn_cliff.csv
│   ├── pbi_funnel.csv
│   ├── pbi_intent_vectors.csv
│   └── pbi_tiers.csv
├── analysis_queries.sql             # SSOT: Tagged analytical SQL queries
├── dashboard_overview.png           # High-resolution dashboard screenshot
├── etl_pipeline.py                  # Ingestion script & schema initialization
├── export_to_powerbi.py             # Orchestration pipeline (SQL -> Clean CSVs)
├── log_mini.csv                     # Raw Spotify session logs
├── README.md                        # Documentation
├── spotify_analytics.db             # Local relational database
├── spotify_behavioral_dashboard.pbix# Interactive Power BI report file
└── tf_mini.csv                      # Raw track audio features
```
## 🚀 Execution & Reproduction Guide
### 1. Ingest Data into SQLite
Run the ingestion pipeline to create and populate the relational tables and indexes:
```Bash
python etl_pipeline.py
```
### 2. Generate Staging CSVs
Execute the orchestration script to parse queries from analysis_queries.sql, transform the datasets, and export staging CSVs:
```bash
python export_to_powerbi.py
```
### 3. Open and Refresh Power BI
Open spotify_behavioral_dashboard.pbix in Power BI Desktop. The pre-rendered visuals and calculations are saved inside the .pbix file. To re-fetch local data after running the scripts, update your local directory path under Transform Data $\rightarrow$ Data source settings and click Refresh.