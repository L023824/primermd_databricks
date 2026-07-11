"""
playbook.py — primerMD (Databricks edition)

The BI&A SQL pattern library, carried over from the Redshift-era primerMD
and translated to Databricks SQL / Unity Catalog conventions.

What changed vs. the original, and why:

  - No live column detection. The original engine regex-matched real column
    names from a connected Redshift session and substituted them into each
    template. That connection now lives inside the Claude.ai session itself
    (via the Databricks MCP tools), not inside this app — so these patterns
    are shipped as reference SQL with placeholder columns
    (<id_col>, <date_col>, ...) and an instruction for Claude to resolve
    those placeholders against the real schema it discovers live.

  - Persistent temp tables -> temp views / CTEs where safe. The Redshift
    version leaned on `DROP TABLE IF EXISTS` + `CREATE TABLE AS` for every
    intermediate step specifically to dodge Redshift's WLM query-abort risk
    on large CTEs. Databricks/Spark doesn't have that failure mode, so the
    default here is `CREATE OR REPLACE TEMP VIEW` (session-scoped, lazily
    evaluated). Where a step is genuinely expensive and worth materializing
    once (e.g. a large dedup base reused by several downstream queries),
    the pattern says so explicitly and uses a real Delta table instead.

  - Three-part namespace. Every FROM clause assumes catalog.schema.table,
    not Redshift's schema.table.

  - QUALIFY where it removes a subquery. Databricks SQL supports QUALIFY
    (Redshift doesn't) — used in dedup and top-N since it collapses the
    window-function-then-filter idiom into one clause.

  - Date functions renamed to Spark SQL equivalents (DATEADD -> date_add /
    add_months, DATEDIFF -> datediff, DATE_TRUNC unchanged).
"""

PLAYBOOK = [
    {
        "id": "deduplication",
        "name": "Deduplication",
        "desc": "Keep one row per entity; detect fan-out after joins",
        "kpi_keywords": ["unique", "distinct", "dedupe", "one per", "per patient", "per hcp"],
        "sql": """
**When to use:** Any table with one row per event where you need one row per entity (patient, HCP, fill).

```sql
-- Deduplication: keep the latest record per <id_col>
-- Databricks: QUALIFY removes the need for a wrapping subquery + WHERE rn = 1

CREATE OR REPLACE TEMP VIEW temp_dedup_base AS
SELECT *
FROM <catalog>.<schema>.<table>
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY <id_col>
    ORDER BY <date_col> DESC        -- keep most recent record
) = 1;

-- Verify: row count should equal DISTINCT <id_col> count
-- SELECT COUNT(*), COUNT(DISTINCT <id_col>) FROM temp_dedup_base;
```

**Fan-out check** — always run this after a join to detect unexpected row multiplication:
```sql
SELECT
    COUNT(*)                      AS total_rows,
    COUNT(DISTINCT <id_col>)      AS distinct_entities
FROM temp_dedup_base;
```
""",
    },
    {
        "id": "date_spine",
        "name": "Date spine",
        "desc": "Continuous date sequence for gap-free time-series",
        "kpi_keywords": ["trend", "monthly", "weekly", "time series", "over time", "mat", "rolling"],
        "sql": """
**When to use:** Time-series analysis where gaps in dates would silently drop months from your output.
Always join your metrics onto the spine rather than generating dates from the data itself.

```sql
-- Date spine: one row per month between two dates
-- sequence() replaces the Redshift ROW_NUMBER()-as-counter trick

CREATE OR REPLACE TEMP VIEW temp_date_spine AS
SELECT explode(sequence(
    date_trunc('month', DATE'2023-01-01'),
    date_trunc('month', current_date()),
    interval 1 month
)) AS spine_month;

-- Join your metrics onto the spine to fill gaps with zero
SELECT
    s.spine_month,
    COALESCE(m.metric_value, 0) AS metric_value
FROM temp_date_spine s
LEFT JOIN (
    SELECT
        date_trunc('month', <date_col>) AS month,
        COUNT(DISTINCT <id_col>)        AS metric_value
    FROM <catalog>.<schema>.<table>
    GROUP BY 1
) m ON s.spine_month = m.month
ORDER BY s.spine_month;
```
""",
    },
    {
        "id": "rolling_window",
        "name": "Rolling window",
        "desc": "Rolling sums / averages; MAT; inter-period smoothing",
        "kpi_keywords": ["rolling", "mat", "moving", "3 month", "6 month", "12 month", "smoothed"],
        "sql": """
**When to use:** Smoothing noisy monthly metrics, rolling MAT (moving annual total),
or inter-fill gap windows.

> Unlike Redshift, Databricks SQL supports `RANGE BETWEEN` with real intervals — but
> `ROWS BETWEEN N PRECEDING` is still the safer default when your grain is already
> monthly, since it doesn't depend on there being no gaps in the date column.

```sql
-- Rolling 3-month sum — pre-aggregate to monthly grain first
CREATE OR REPLACE TEMP VIEW temp_monthly_base AS
SELECT
    date_trunc('month', <date_col>)   AS month,
    <id_col>,
    SUM(<val_col>)                    AS monthly_value
FROM <catalog>.<schema>.<table>
GROUP BY 1, 2;

SELECT
    month,
    <id_col>,
    monthly_value,
    SUM(monthly_value) OVER (
        PARTITION BY <id_col>
        ORDER BY month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW   -- 3-month rolling
    ) AS rolling_3m_sum,
    AVG(monthly_value) OVER (
        PARTITION BY <id_col>
        ORDER BY month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_3m_avg
FROM temp_monthly_base
ORDER BY <id_col>, month;
```
""",
    },
    {
        "id": "yoy",
        "name": "YoY comparison",
        "desc": "Year-over-year and period-over-period metrics",
        "kpi_keywords": ["yoy", "year over year", "prior year", "growth", "change vs", "vs prior", "qoq", "mom"],
        "sql": """
**When to use:** Period-over-period trending — quarterly business reviews, brand performance decks.

```sql
CREATE OR REPLACE TEMP VIEW temp_yoy AS
SELECT
    <id_col>,
    SUM(CASE WHEN year(<date_col>) = year(current_date())
             THEN 1 ELSE 0 END)                       AS cy_count,
    SUM(CASE WHEN year(<date_col>) = year(current_date()) - 1
             THEN 1 ELSE 0 END)                       AS py_count
FROM <catalog>.<schema>.<table>
WHERE <date_col> >= add_months(date_trunc('year', current_date()), -24)
GROUP BY 1;

SELECT
    <id_col>,
    cy_count,
    py_count,
    cy_count - py_count                                              AS yoy_abs_change,
    ROUND((cy_count - py_count) * 100.0 / NULLIF(py_count, 0), 1)    AS yoy_pct_change
FROM temp_yoy
ORDER BY yoy_abs_change DESC;
```
""",
    },
    {
        "id": "cohort",
        "name": "Cohort analysis",
        "desc": "Group by first event date; track retention / persistence by offset",
        "kpi_keywords": ["cohort", "retention", "persistence", "days on therapy", "dot", "time to", "first fill", "index"],
        "sql": """
**When to use:** Tracking retention, persistence, or engagement from a patient's/HCP's first event.
Classic use case: first Rx date as cohort anchor, then measure refill behavior by month offset.

```sql
CREATE OR REPLACE TEMP VIEW temp_cohort_anchor AS
SELECT
    <id_col>,
    MIN(<date_col>)                       AS first_event_date,
    date_trunc('month', MIN(<date_col>))  AS cohort_month
FROM <catalog>.<schema>.<table>
GROUP BY 1;

-- Activity by months-since-first-event
SELECT
    ca.cohort_month,
    months_between(e.<date_col>, ca.first_event_date)   AS months_since_start,
    COUNT(DISTINCT e.<id_col>)                           AS active_entities
FROM <catalog>.<schema>.<table> e
INNER JOIN temp_cohort_anchor ca
    ON e.<id_col> = ca.<id_col>
WHERE e.<date_col> >= ca.first_event_date
GROUP BY 1, 2
ORDER BY 1, 2;
```
""",
    },
    {
        "id": "funnel",
        "name": "Funnel analysis",
        "desc": "Sequential step tracking with conversion rates",
        "kpi_keywords": ["funnel", "conversion", "journey", "step", "pipeline", "opportunity", "identified", "trialist", "writer"],
        "sql": """
**When to use:** Patient journey funnels (identified -> diagnosed -> prescribed -> filled -> refilled),
HCP targeting funnels (universe -> segmented -> called -> written).

```sql
CREATE OR REPLACE TEMP VIEW temp_funnel_steps AS
SELECT
    t1.<id_col>,
    1                                                          AS step_1_in_universe,
    CASE WHEN t2.<id_col> IS NOT NULL THEN 1 ELSE 0 END       AS step_2_qualified
    -- Add further steps: join additional tables and flag 1/0
FROM <catalog>.<schema>.<table_1> t1
LEFT JOIN <catalog>.<schema>.<table_2> t2
    ON t1.<id_col> = t2.<id_col>;

-- Summary with conversion rates
SELECT
    COUNT(*)                                                   AS step_1_universe,
    SUM(step_2_qualified)                                      AS step_2_qualified,
    ROUND(SUM(step_2_qualified) * 100.0 / NULLIF(COUNT(*), 0), 1)  AS step_1_to_2_pct
FROM temp_funnel_steps;
```
""",
    },
    {
        "id": "waterfall",
        "name": "Priority CASE waterfall",
        "desc": "Mutually exclusive segmentation; SoM buckets; TUA classification",
        "kpi_keywords": ["segment", "mutually exclusive", "share of market", "som", "tua", "trialist", "user", "adopter", "bucket", "classify"],
        "sql": """
**When to use:** Assigning patients or HCPs to mutually exclusive segments where an entity
could qualify for multiple buckets — share of market segments, TUA classification,
patient eligibility buckets. Priority order in the CASE determines the segment assigned.

> BI&A standard: use a priority-based CASE waterfall, not multiple overlapping flags.
> Document the priority order so it can be audited.

```sql
CREATE OR REPLACE TEMP VIEW temp_segmented AS
SELECT
    <id_col>,
    <status_col>,
    CASE
        WHEN <condition_tier_1>  THEN 'Segment A'    -- highest priority
        WHEN <condition_tier_2>  THEN 'Segment B'
        WHEN <condition_tier_3>  THEN 'Segment C'
        ELSE                          'Other'         -- catch-all last
    END AS segment,
    CASE WHEN <condition_tier_1> THEN 1 ELSE 0 END   AS flag_tier_1,
    CASE WHEN <condition_tier_2> THEN 1 ELSE 0 END   AS flag_tier_2,
    CASE WHEN <condition_tier_3> THEN 1 ELSE 0 END   AS flag_tier_3
FROM <catalog>.<schema>.<table>;

-- Verify mutual exclusivity: every row should have exactly one segment
SELECT segment, COUNT(*) AS n FROM temp_segmented GROUP BY 1 ORDER BY 2 DESC;
```
""",
    },
    {
        "id": "ever_flag",
        "name": "Cumulative ever-flag (TUA)",
        "desc": "Trialist / User / Adopter classification; once-ever milestone tracking",
        "kpi_keywords": ["trialist", "user", "adopter", "tua", "ever", "cumulative", "net new", "first time", "new writer"],
        "sql": """
**When to use:** Trialist / User / Adopter (TUA) classification — once an entity crosses a
threshold it stays classified at that level. Also: ever-prescribed, ever-diagnosed flags.

> Gotcha: if the source table has one row per event, cumulate *before* joining to other tables
> to avoid fan-out inflating counts (this is the lb=97/98-style issue from the Jaypirca TUA
> pipeline — same risk applies here regardless of platform).

```sql
CREATE OR REPLACE TEMP VIEW temp_event_counts AS
SELECT
    <id_col>,
    MIN(<date_col>)                        AS first_event_date,
    COUNT(DISTINCT DATE(<date_col>))       AS distinct_event_days,
    COUNT(*)                               AS total_events
FROM <catalog>.<schema>.<table>
GROUP BY 1;

CREATE OR REPLACE TEMP VIEW temp_ever_classified AS
SELECT
    <id_col>,
    first_event_date,
    distinct_event_days,
    -- Adjust thresholds to match business definitions
    CASE
        WHEN distinct_event_days >= 4 THEN 'Adopter'
        WHEN distinct_event_days >= 2 THEN 'User'
        WHEN distinct_event_days >= 1 THEN 'Trialist'
        ELSE                               'None'
    END AS classification,
    CASE WHEN distinct_event_days >= 1 THEN 1 ELSE 0 END AS is_trialist,
    CASE WHEN distinct_event_days >= 2 THEN 1 ELSE 0 END AS is_user,
    CASE WHEN distinct_event_days >= 4 THEN 1 ELSE 0 END AS is_adopter
FROM temp_event_counts;
```
""",
    },
    {
        "id": "fill_gap",
        "name": "Inter-fill gap classification",
        "desc": "Days between fills; therapy persistence; lapse detection",
        "kpi_keywords": ["persistence", "gap", "lapse", "days on therapy", "dot", "refill", "fill", "discontinuation", "adherence"],
        "sql": """
**When to use:** Therapy persistence, gap analysis, days-on-therapy (DOT) calculations.
Classifies each fill interval as continuous, short gap, or lapse.

```sql
CREATE OR REPLACE TEMP VIEW temp_fill_gaps AS
SELECT
    <id_col>,
    <date_col>                                                 AS fill_date,
    LAG(<date_col>) OVER (
        PARTITION BY <id_col>
        ORDER BY <date_col>
    )                                                          AS prior_fill_date,
    DATEDIFF(
        <date_col>,
        LAG(<date_col>) OVER (PARTITION BY <id_col> ORDER BY <date_col>)
    )                                                          AS days_since_prior_fill,
    ROW_NUMBER() OVER (
        PARTITION BY <id_col>
        ORDER BY <date_col>
    )                                                          AS fill_number
FROM <catalog>.<schema>.<table>;

-- Classify gaps — adjust thresholds to match therapy / days-supply assumptions
SELECT
    <id_col>,
    fill_date,
    prior_fill_date,
    days_since_prior_fill,
    fill_number,
    CASE
        WHEN fill_number = 1              THEN 'Index Fill'
        WHEN days_since_prior_fill <= 45  THEN 'Continuous'
        WHEN days_since_prior_fill <= 90  THEN 'Short Gap'
        ELSE                                   'Lapse / Restart'
    END AS persistence_status
FROM temp_fill_gaps
ORDER BY <id_col>, fill_date;
```
""",
    },
    {
        "id": "window_truncation",
        "name": "Window truncation audit",
        "desc": "Detect data lag in most recent period before reporting trends",
        "kpi_keywords": ["trend", "refresh", "latest", "recent", "lag", "incomplete", "partial month", "truncat"],
        "sql": """
**When to use:** Any time you see unexpected metric *improvements* in a period-over-period
refresh — especially at the most recent month. Almost always a window truncation artifact.

> BI&A standard: always check for truncation before attributing trend changes to real behaviour.
> This applies identically on Databricks — it's a data-freshness issue, not a platform one.

```sql
-- Step 1: compare row density across months
SELECT
    date_trunc('month', <date_col>)          AS month,
    COUNT(*)                                  AS row_count,
    COUNT(*) * 1.0 / MAX(COUNT(*)) OVER ()    AS pct_of_peak_month
FROM <catalog>.<schema>.<table>
GROUP BY 1
ORDER BY 1 DESC
LIMIT 6;

-- Interpretation:
-- If the most recent month is < 80% of the prior month, it is likely truncated.
-- Do NOT report the most recent month as a completed period.

-- Step 2: find data freshness (max date in table)
SELECT MAX(<date_col>) AS latest_record_date FROM <catalog>.<schema>.<table>;
```
""",
    },
    {
        "id": "full_outer",
        "name": "Full outer join — actuals vs goals",
        "desc": "Merge actuals and targets preserving all months from both sides",
        "kpi_keywords": ["goal", "target", "vs goal", "pct to goal", "attainment", "quota", "plan vs actual"],
        "sql": """
**When to use:** Combining actuals with goals/targets when either side may have months the other
doesn't — goal-based tracking views, SoM cohort flag updates across monthly snapshots.

> Gotcha on UNION type casting carries over from Redshift: if actuals use `INT` and goals use
> `BIGINT`, cast both sides explicitly before combining.

```sql
CREATE OR REPLACE TEMP VIEW temp_actuals_vs_goals AS
SELECT
    COALESCE(a.month, g.month)         AS month,
    COALESCE(a.<id_col>, g.<id_col>)   AS <id_col>,
    a.actual_value,
    g.goal_value,
    COALESCE(a.actual_value, 0)        AS actual_filled,
    COALESCE(g.goal_value, 0)          AS goal_filled,
    ROUND(
        COALESCE(a.actual_value, 0) * 100.0
        / NULLIF(COALESCE(g.goal_value, 0), 0),
    1)                                 AS pct_to_goal
FROM (
    SELECT
        date_trunc('month', <date_col>) AS month,
        <id_col>,
        COUNT(DISTINCT <id_col>)        AS actual_value
    FROM <catalog>.<schema>.<table_1>
    GROUP BY 1, 2
) a
FULL OUTER JOIN (
    SELECT
        CAST(month AS DATE)         AS month,
        CAST(<id_col> AS STRING)    AS <id_col>,   -- cast to match actuals — adjust type
        CAST(goal_value AS INT)     AS goal_value
    FROM <catalog>.<schema>.<table_2>
) g
ON  a.month     = g.month
AND a.<id_col>  = g.<id_col>;
```
""",
    },
    {
        "id": "topn",
        "name": "Top-N ranking",
        "desc": "Rank entities by metric; overall and within group",
        "kpi_keywords": ["top", "rank", "decile", "highest", "lowest", "leaderboard", "opportunity", "priority"],
        "sql": """
**When to use:** HCP opportunity ranking, patient cost stratification, territory leaderboards.
Use `DENSE_RANK()` when ties should share a rank position; `ROW_NUMBER()` for exactly N rows.

```sql
-- QUALIFY collapses the rank-then-filter idiom into one clause
SELECT
    <id_col>,
    <val_col>,
    <status_col>,
    ROW_NUMBER()  OVER (ORDER BY <val_col> DESC)                    AS overall_rank,
    DENSE_RANK()  OVER (ORDER BY <val_col> DESC)                    AS overall_rank_dense,
    ROW_NUMBER()  OVER (PARTITION BY <status_col>
                        ORDER BY <val_col> DESC)                    AS rank_within_segment
FROM <catalog>.<schema>.<table>
QUALIFY overall_rank <= 10;   -- adjust N, or drop QUALIFY to keep the full ranked set
```
""",
    },
]


from worked_examples import WORKED_EXAMPLES

ALL_PATTERNS = PLAYBOOK + WORKED_EXAMPLES


def get_pattern(pattern_id: str) -> dict | None:
    return next((p for p in ALL_PATTERNS if p["id"] == pattern_id), None)


def get_patterns(pattern_ids: list[str]) -> list[dict]:
    by_id = {p["id"]: p for p in ALL_PATTERNS}
    return [by_id[pid] for pid in pattern_ids if pid in by_id]
