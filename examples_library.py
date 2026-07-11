"""
examples_library.py — primerMD (Databricks edition)

Static, always-included worked-examples reference, ported from the Redshift-era
primerMD's hand-curated EXAMPLES.md (19 real query patterns spanning diabetes,
obesity, oncology, and autoimmune data — HCP segmentation, TUA, SoM waterfall,
dosing classification, mode-of-administration classification, cross-TA overlap).

Unlike the 12-pattern PLAYBOOK in playbook.py (abstract templates with
<id_col>/<date_col> placeholders, picked per-KPI), this file is not templated
per project — it ships identically with every scaffold as a style/complexity
reference and a source of directly reusable business logic. See its own header
for translation notes (dialect changes, catalog placeholder, preserved caveats).
"""

EXAMPLES_LIBRARY_MD = """# examples_library.md — BI&A worked SQL examples (Databricks/Spark SQL)

> Ported from the Redshift-era primerMD's worked-examples reference (19 real query patterns
> spanning diabetes/obesity/oncology/autoimmune data, HCP segmentation, TUA, SoM, dosing, and
> mode-of-administration classification). Dialect converted to Databricks/Spark SQL:
> persistent Redshift temp tables → `CREATE OR REPLACE TEMP VIEW`, `DATEADD`/`TO_CHAR` → 
> `add_months`/`date_format`, `::type` casts → `CAST(... AS type)`, two-part `schema.table`
> → three-part `<catalog>.schema.table` (confirm the real catalog name against your Unity
> Catalog metastore and replace every `<catalog>` placeholder before running).
>
> Business logic, thresholds, and every "safe to adjust" / "not safe to adjust" caveat below
> are preserved exactly as documented in the original — these encode real prior decisions
> (e.g. why the AA/321/1L/BTK-Naive waterfall order matters, why INNER JOIN is intentional in
> the cross-TA overlap query). Treat them as load-bearing, not incidental commentary.
>
> This is a static reference file, not templated per project — it ships identically with every
> scaffold. Use it alongside `EXAMPLES.md` (the per-KPI stubs) as a style/complexity guide, and
> as a source of directly reusable patterns for TUA, SoM, dosing, and MoA work in particular.

---

## Example 1 — Diabetes Patient Summary with Claims

**Business Question:** How many active diabetes patients do we have, what is their total paid claims, and how many have had an activity call this year?

```sql
-- Diabetes patient summary: active patients, claims, and outreach activity for 2024

WITH diabetes_base AS (
    -- Distinct active diabetes patients diagnosed in last 2 years
    SELECT DISTINCT
        patient_id,
        diagnosis_date
    FROM <catalog>.apld_ex.elaad_diabetes_masterdata
    WHERE diagnosis_date >= add_months(current_date(), -24)
),

claims_summary AS (
    SELECT
        customer_id,
        SUM(paid_amount)           AS total_paid,
        COUNT(DISTINCT claim_id)   AS claim_count
    FROM <catalog>.apld_ex.elaad_fct_mx
    WHERE service_date BETWEEN '2024-01-01' AND '2024-12-31'
    GROUP BY customer_id
),

activity_summary AS (
    SELECT
        patient_id,
        COUNT(*)                   AS total_calls,
        MAX(activity_date)         AS last_call_date
    FROM <catalog>.sas.activity_calls
    WHERE activity_date BETWEEN '2024-01-01' AND '2024-12-31'
    GROUP BY patient_id
)

SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    d.diagnosis_date,
    COALESCE(cl.total_paid, 0)    AS total_paid_2024,
    COALESCE(cl.claim_count, 0)   AS claim_count_2024,
    COALESCE(ac.total_calls, 0)   AS activity_calls_2024,
    ac.last_call_date,
    CASE
        WHEN ac.patient_id IS NOT NULL THEN 'Contacted'
        ELSE 'Not Contacted'
    END                           AS outreach_status
FROM diabetes_base d
INNER JOIN <catalog>.sas.customer c
    ON d.patient_id = c.customer_id
LEFT JOIN claims_summary cl
    ON d.patient_id = cl.customer_id
LEFT JOIN activity_summary ac
    ON d.patient_id = ac.patient_id
ORDER BY total_paid_2024 DESC;
```

---

## Example 2 — Obesity + Diabetes Comorbidity Flag

**Business Question:** Which customers appear in both the obesity and diabetes masterdatas? Flag them as comorbid.

```sql
-- Comorbidity flag: identify patients present in both diabetes and obesity masterdata

WITH diabetes_patients AS (
    SELECT DISTINCT patient_id
    FROM <catalog>.apld_ex.elaad_diabetes_masterdata
),

obesity_patients AS (
    SELECT DISTINCT patient_id
    FROM <catalog>.apld_ex.elaad_obesity_masterdata
)

SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    CASE WHEN d.patient_id IS NOT NULL THEN 1 ELSE 0 END AS has_diabetes,
    CASE WHEN o.patient_id IS NOT NULL THEN 1 ELSE 0 END AS has_obesity,
    CASE
        WHEN d.patient_id IS NOT NULL
         AND o.patient_id IS NOT NULL THEN 'Comorbid'
        WHEN d.patient_id IS NOT NULL THEN 'Diabetes Only'
        WHEN o.patient_id IS NOT NULL THEN 'Obesity Only'
        ELSE 'Neither'
    END AS condition_segment
FROM <catalog>.sas.customer c
LEFT JOIN diabetes_patients d ON c.customer_id = d.patient_id
LEFT JOIN obesity_patients o  ON c.customer_id = o.patient_id
WHERE c.status = 'active'
ORDER BY condition_segment, c.customer_name;
```

---

## Example 3 — Monthly Claims Trend

**Business Question:** Show me the monthly total paid claims trend for the last 12 months.

```sql
-- Monthly claims trend: last 12 months of paid claims, with MoM change

WITH monthly AS (
    SELECT
        DATE_TRUNC('month', service_date)  AS month,
        SUM(paid_amount)                   AS total_paid,
        COUNT(DISTINCT customer_id)        AS unique_patients
    FROM <catalog>.apld_ex.elaad_fct_mx
    WHERE service_date >= add_months(DATE_TRUNC('month', current_date()), -12)
    GROUP BY 1
),

with_lag AS (
    SELECT
        month,
        total_paid,
        unique_patients,
        LAG(total_paid) OVER (ORDER BY month) AS prior_month_paid
    FROM monthly
)

SELECT
    month,
    total_paid,
    unique_patients,
    prior_month_paid,
    ROUND(
        (total_paid - prior_month_paid) * 100.0 / NULLIF(prior_month_paid, 0),
    1) AS mom_pct_change
FROM with_lag
ORDER BY month;
```

---

## Example 4 — Top 10 Highest-Cost Diabetes Patients

**Business Question:** Who are the top 10 diabetes patients by total paid claims in 2024?

```sql
-- Top 10 diabetes patients by claims cost in 2024

WITH diabetes_claims AS (
    SELECT
        f.customer_id,
        SUM(f.paid_amount)          AS total_paid,
        COUNT(DISTINCT f.claim_id)  AS claim_count
    FROM <catalog>.apld_ex.elaad_fct_mx f
    INNER JOIN <catalog>.apld_ex.elaad_diabetes_masterdata d
        ON f.customer_id = d.patient_id
    WHERE f.service_date BETWEEN '2024-01-01' AND '2024-12-31'
    GROUP BY f.customer_id
),

ranked AS (
    SELECT
        dc.customer_id,
        c.customer_name,
        c.region,
        dc.total_paid,
        dc.claim_count,
        ROW_NUMBER() OVER (ORDER BY dc.total_paid DESC) AS cost_rank
    FROM diabetes_claims dc
    LEFT JOIN <catalog>.sas.customer c
        ON dc.customer_id = c.customer_id
)

SELECT
    cost_rank,
    customer_id,
    customer_name,
    region,
    total_paid,
    claim_count
FROM ranked
WHERE cost_rank <= 10
ORDER BY cost_rank;
```

---

## Example 5 — Activity Call Funnel

**Business Question:** Of our diabetes patients, how many were identified, called, and had a claim filed afterward?

```sql
-- Call funnel for diabetes patients: identified → called → post-call claim

WITH identified AS (
    SELECT DISTINCT patient_id
    FROM <catalog>.apld_ex.elaad_diabetes_masterdata
),

called AS (
    SELECT DISTINCT patient_id
    FROM <catalog>.sas.activity_calls
    WHERE activity_type = 'outreach_call'
      AND activity_date >= '2024-01-01'
),

claimed_after_call AS (
    SELECT DISTINCT f.customer_id
    FROM <catalog>.apld_ex.elaad_fct_mx f
    INNER JOIN called cl
        ON f.customer_id = cl.patient_id
    WHERE f.service_date >= '2024-01-01'
)

SELECT
    COUNT(DISTINCT i.patient_id)     AS step_1_identified,
    COUNT(DISTINCT c.patient_id)     AS step_2_called,
    COUNT(DISTINCT ca.customer_id)   AS step_3_claimed,

    ROUND(
        COUNT(DISTINCT c.patient_id) * 100.0 /
        NULLIF(COUNT(DISTINCT i.patient_id), 0), 1
    )                                AS call_rate_pct,

    ROUND(
        COUNT(DISTINCT ca.customer_id) * 100.0 /
        NULLIF(COUNT(DISTINCT c.patient_id), 0), 1
    )                                AS post_call_claim_rate_pct

FROM identified i
LEFT JOIN called c        ON i.patient_id = c.patient_id
LEFT JOIN claimed_after_call ca ON i.patient_id = ca.customer_id;
```

---

## Example 6 — Power BI DAX: Rolling 3-Month Paid Claims

**Business Question:** Create a DAX measure for rolling 3-month paid claims for a Power BI dashboard.

```dax
// Rolling 3-Month Paid Claims
// Context: 'fct_mx' table with 'paid_amount' and 'service_date' columns

Rolling 3M Paid Claims = 
VAR LastVisibleDate = MAX('fct_mx'[service_date])
VAR StartDate = DATEADD(LASTDATE('fct_mx'[service_date]), -3, MONTH)
RETURN
    CALCULATE(
        SUM('fct_mx'[paid_amount]),
        DATESBETWEEN('fct_mx'[service_date], StartDate, LastVisibleDate)
    )
```

**When to use DAX vs SQL:** If this metric needs to respond dynamically to slicer selections in Power BI, keep it in DAX. If it's a fixed lookback used across multiple reports, compute it upstream in Databricks and bring in the result.

---

## Example 7 — Tableau LOD: Average Claims Per Customer by Region

**Business Question:** Show the average claims per customer for each region, regardless of other filters applied.

```
// Tableau LOD expression — fixed to Region, ignores other dashboard filters

{ FIXED [Region] : AVG([Paid Amount]) }
```

Use `FIXED` when you want the calculation to ignore view-level filters (e.g., date or product filters) but still respect context filters (like data source filters).

---

## Example 8 — Rolling 6-month NBRx (BTK product)

**Business Question:** What is the rolling 6-month NBRx count per HCP for a given BTK product?

```sql
-- grain: one row per HCP per month (after date_trunc)
-- rolling window: 6 months ending on current month
-- date format: yyyy-mm-dd (date_trunc output — safe for BETWEEN comparisons)
-- safe to adjust: window length (change ROWS BETWEEN N-1 PRECEDING), product filter, roll up to territory/national
-- NOT safe to adjust: window function ordering — ORDER BY month must be ascending for correct cumulation
-- NOTE: product values are all CAPS (e.g. 'PIRTOBRUTINIB') — check generic_name not brand name
-- threshold/config: product filter and date range — see kpi_definitions.md for TA-specific values
-- dependency: standalone — no upstream temp tables required
-- downstream: temp_nbrx_rolling is referenced by Examples 9 and 10 if running as a suite;
--   recreate this block first if running those examples independently

CREATE OR REPLACE TEMP VIEW temp_nbrx_rolling AS
SELECT
    eph_reference_id,
    month,
    generic_name,
    SUM(new_to_brand_flag) OVER (
        PARTITION BY eph_reference_id, generic_name
        ORDER BY month
        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
    ) AS nbrx_rolling_6m
FROM (
    SELECT *, DATE_TRUNC('month', service_date) AS month
    FROM <catalog>.apld_ex.elaad_oncology_masterdata
)
WHERE generic_name = 'PIRTOBRUTINIB'
  AND month BETWEEN '2024-01-01' AND '2026-03-31'
;
```

---

## Example 9 — NBRx period-over-period growth, HCP level

**Business Question:** For each HCP, how did NBRx change between a pre-period and a post-period?

```sql
-- grain: one row per HCP
-- use case: HCP targeting and tier movement — who grew, who declined
-- safe to adjust: pre/post date ranges, product filter, add territory/region grouping
-- NOT safe to adjust: FULL OUTER JOIN — required to capture HCPs present in only one period;
--   changing to LEFT or INNER JOIN will drop HCPs with zero NBRx in either period
-- NOTE: HCPs with zero NBRx in either period will appear with 0 — NULLIF guards against divide-by-zero
-- threshold/config: pre/post date ranges and product filter — see kpi_definitions.md for TA-specific values
-- dependency: standalone — no upstream temp tables required

CREATE OR REPLACE TEMP VIEW temp_nbrx_pre AS
SELECT
    eph_reference_id,
    SUM(new_to_brand_flag) AS nbrx_pre
FROM (
    SELECT *, DATE_TRUNC('month', service_date) AS month
    FROM <catalog>.apld_ex.elaad_oncology_masterdata
)
WHERE generic_name = 'PIRTOBRUTINIB'
  AND month BETWEEN '2025-11-01' AND '2026-01-31'   -- Nov 2025 – Jan 2026; varies by objective
GROUP BY eph_reference_id
;

CREATE OR REPLACE TEMP VIEW temp_nbrx_post AS
SELECT
    eph_reference_id,
    SUM(new_to_brand_flag) AS nbrx_post
FROM (
    SELECT *, DATE_TRUNC('month', service_date) AS month
    FROM <catalog>.apld_ex.elaad_oncology_masterdata
)
WHERE generic_name = 'PIRTOBRUTINIB'
  AND month BETWEEN '2026-02-01' AND '2026-04-30'   -- Feb 2026 – Apr 2026; varies by objective
GROUP BY eph_reference_id
;

CREATE OR REPLACE TEMP VIEW temp_nbrx_growth_hcp AS
SELECT
    COALESCE(post.eph_reference_id, pre.eph_reference_id) AS eph_reference_id,
    COALESCE(pre.nbrx_pre, 0)                             AS nbrx_pre,
    COALESCE(post.nbrx_post, 0)                           AS nbrx_post,
    COALESCE(post.nbrx_post, 0) - COALESCE(pre.nbrx_pre, 0) AS nbrx_abs_change,
    ROUND(
        (COALESCE(post.nbrx_post, 0) - COALESCE(pre.nbrx_pre, 0)) * 100.0
        / NULLIF(COALESCE(pre.nbrx_pre, 0), 0),
    1)                                                    AS nbrx_pct_change
FROM temp_nbrx_pre pre
FULL OUTER JOIN temp_nbrx_post post
    ON pre.eph_reference_id = post.eph_reference_id
;
```

---

## Example 10 — NBRx period-over-period growth, market level

**Business Question:** How did total NBRx change between a pre-period and a post-period across all HCPs?

```sql
-- grain: single summary row
-- use case: brand performance reporting, launch curve assessment
-- safe to adjust: pre/post date ranges, product filter
-- NOT safe to adjust: two-step temp view structure — standard SQL can't reference
--   aliases (nbrx_pre, nbrx_post) defined in the same SELECT for arithmetic;
--   always materialise aggregates first, then derive change metrics in a second step
-- time periods: parameterised by objective — see kpi_definitions.md for project-specific windows
-- threshold/config: product filter and date ranges — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required

-- NOTE: nbrx_pre/nbrx_post aliases not available in same SELECT —
--   aggregates materialised in temp_nbrx_growth_market, arithmetic in separate step

CREATE OR REPLACE TEMP VIEW temp_nbrx_periods AS
SELECT
    DATE_TRUNC('month', service_date)                    AS month,
    new_to_brand_flag
FROM <catalog>.apld_ex.elaad_oncology_masterdata
WHERE generic_name = 'PIRTOBRUTINIB'
  AND DATE_TRUNC('month', service_date) BETWEEN '2025-11-01' AND '2026-04-30'
;

CREATE OR REPLACE TEMP VIEW temp_nbrx_growth_market AS
SELECT
    SUM(CASE WHEN month BETWEEN '2025-11-01' AND '2026-01-31'
             THEN new_to_brand_flag ELSE 0 END)          AS nbrx_pre,
    SUM(CASE WHEN month BETWEEN '2026-02-01' AND '2026-04-30'
             THEN new_to_brand_flag ELSE 0 END)          AS nbrx_post
FROM temp_nbrx_periods
;

CREATE OR REPLACE TEMP VIEW temp_nbrx_growth_market_final AS
SELECT
    nbrx_pre,
    nbrx_post,
    nbrx_post - nbrx_pre                                 AS nbrx_abs_change,
    ROUND(
        (nbrx_post - nbrx_pre) * 100.0 / NULLIF(nbrx_pre, 0),
    1)                                                   AS nbrx_pct_change
FROM temp_nbrx_growth_market
;
```

---

## Example 11 — HCP account type segmentation

**Business Question:** How do we classify each HCP's account as Community, Academic, IDN, or Other — and roll it up to a binary Community vs Non-Community flag?

```sql
-- grain: one row per HCP (npi_id)
-- output: account_segment_granular (Community / Academic / IDN / Other) + account_segment (Community / Non-Community)
-- logic: priority CASE waterfall — order matters, first match wins
-- safe to adjust: academic keyword list, student threshold (currently known >= 30 AND pct_student >= 0.15)
-- NOT safe to adjust: layer order — forced overrides must always fire before academic/IDN logic
-- OBU-specific: sub-account overrides in Layer 2 (final_account_id hardcodes) are OBU business rules — replace with TA-equivalent if reusing
-- threshold/config: student pct threshold and known HCP floor — see kpi_definitions.md for TA-specific values
-- dependency: <catalog>.obu.obu_flagged_accounts (GPO/DSA flags) is OBU-specific — confirm TA equivalent before reusing
-- NOTE: account_segment (rollup) derived in a separate temp view — cannot reference
--   account_segment_granular alias in the same SELECT where it is defined

CREATE OR REPLACE TEMP VIEW temp_forced_overrides AS
SELECT DISTINCT
    final_account_id,
    map AS account_segment_granular
FROM <catalog>.obu.obu_flagged_accounts
WHERE gpo_flag = 1
   OR dsa_flag = 1
;

CREATE OR REPLACE TEMP VIEW temp_idn_names AS
SELECT DISTINCT
    UPPER(TRIM(bus_nm)) AS bus_nm
FROM <catalog>.bia_conform.onekey_hco_org_detl_master
WHERE cot_fclt_typ_desc ILIKE '%integrated%'
  AND bus_nm IS NOT NULL
;

CREATE OR REPLACE TEMP VIEW temp_student_summary AS
SELECT
    omd.final_account_id,
    omd.final_account_nm,
    SUM(CASE
            WHEN a.graduate_medical_training_to_date >
                 CASE
                     WHEN EXTRACT(MONTH FROM current_date()) BETWEEN 1 AND 9
                         THEN to_date(concat('09/30/', CAST(EXTRACT(YEAR FROM current_date()) AS STRING)), 'MM/dd/yyyy')
                     ELSE to_date(concat('09/30/', CAST(EXTRACT(YEAR FROM current_date()) + 1 AS STRING)), 'MM/dd/yyyy')
                 END
            THEN 1 ELSE 0
        END)                                               AS students,
    SUM(CASE
            WHEN a.graduate_medical_training_to_date <=
                 CASE
                     WHEN EXTRACT(MONTH FROM current_date()) BETWEEN 1 AND 9
                         THEN to_date(concat('09/30/', CAST(EXTRACT(YEAR FROM current_date()) AS STRING)), 'MM/dd/yyyy')
                     ELSE to_date(concat('09/30/', CAST(EXTRACT(YEAR FROM current_date()) + 1 AS STRING)), 'MM/dd/yyyy')
                 END
            THEN 1 ELSE 0
        END)                                               AS nonstudents,
    students + nonstudents                                 AS known,
    COUNT(omd.npi_id)                                      AS npis,
    CASE
        WHEN known = 0 THEN NULL
        ELSE CAST(
            (CAST(students AS DECIMAL(10,4)) * 100) / CAST(known AS DECIMAL(10,4))
        AS DECIMAL(10,4)) / 100
    END                                                    AS pct_student
FROM <catalog>.bia_shared.onekey_master_data omd
LEFT JOIN <catalog>.bia.ama_physician_master a
    ON omd.npi_id = a.npi
GROUP BY 1, 2
;

CREATE OR REPLACE TEMP VIEW temp_hcp_base AS
SELECT
    sdm.npi_id,
    sdm.l3_id,
    sdm.l2_id,
    omd.final_account_id,
    omd.final_account_nm,
    omd.eph_cust_reference_id
FROM <catalog>.de.system_data_master sdm
LEFT JOIN <catalog>.bia_shared.onekey_master_data omd
    ON omd.npi_id = sdm.npi_id
;

CREATE OR REPLACE TEMP VIEW temp_hcp_account_segment AS
SELECT
    b.npi_id,
    b.eph_cust_reference_id,
    b.final_account_id,
    b.final_account_nm,
    CASE
        -- Layer 1: Forced overrides (GPO / DSA flagged accounts)
        WHEN fo.account_segment_granular IS NOT NULL
            THEN fo.account_segment_granular

        -- Layer 2: Sub-account overrides (OBU-specific business rules)
        WHEN b.final_account_id = '18128395'
             AND b.l3_id IN ('18361425','18164381','18154039')
            THEN 'Community'
        WHEN b.final_account_id = '17773625'
             AND b.l3_id = '17773506'
            THEN 'Community'
        WHEN b.final_account_id = '17773625'
             AND b.l3_id = '18157167'
            THEN 'Academic'
        WHEN b.final_account_id = '17773625'
             AND b.l2_id = '18957022'
            THEN 'Community'

        -- Layer 3: Academic (student ratio OR institution name match)
        -- threshold: known >= 30 AND pct_student >= 0.15 — see kpi_definitions.md
        WHEN (
            (s.known >= 30 AND s.pct_student >= 0.15)
            OR b.final_account_nm ILIKE '%UNIVERSITY%'
            OR b.final_account_nm ILIKE '%COLLEGE%'
            OR b.final_account_nm ILIKE '%SCHOOL OF MEDICINE%'
            OR b.final_account_nm ILIKE '%RESEARCH%'
            OR b.final_account_nm ILIKE '%ACADEMIC%'
            OR b.final_account_nm ILIKE '%TEACHING%'
            OR b.final_account_nm ILIKE '%MAYO CLINIC%'
            OR b.final_account_nm ILIKE '%CLEVELAND CLINIC%'
            OR b.final_account_nm ILIKE '%JOHNS HOPKINS%'
            OR b.final_account_nm ILIKE '%STANFORD%'
            OR b.final_account_nm ILIKE '%DUKE%'
            OR b.final_account_nm ILIKE '%UCSF %'
            OR b.final_account_nm ILIKE '%UC DAVIS%'
            OR b.final_account_nm ILIKE '%UCSD %'
            OR b.final_account_nm ILIKE '%UCI %'
            OR b.final_account_nm ILIKE '%UCLA %'
            OR b.final_account_nm ILIKE '%UCR %'
            OR b.final_account_nm ILIKE '%MD ANDERSON%'
            OR b.final_account_nm ILIKE '%VANDERBILT%'
            OR b.final_account_nm ILIKE '%HARVARD%'
            OR b.final_account_nm ILIKE '%YALE%'
            OR b.final_account_nm ILIKE '%COLUMBIA%'
            OR b.final_account_nm ILIKE '%NORTHWESTERN%'
            OR b.final_account_nm ILIKE '%SLOAN KETTERING%'
            OR b.final_account_nm ILIKE '%DARTMOUTH%'
            OR b.final_account_nm ILIKE '%MASS GENERAL%'
            OR b.final_account_nm ILIKE '%UNIVERSITARIO%'
            OR b.final_account_nm ILIKE '%UC %'
            OR b.final_account_nm ILIKE '%UCF %'
        ) THEN 'Academic'

        -- Layer 4: IDN name match
        WHEN idn.bus_nm IS NOT NULL
            THEN 'IDN'

        -- Layer 5: Default
        ELSE 'Other'
    END                                                    AS account_segment_granular

FROM temp_hcp_base b
LEFT JOIN temp_forced_overrides fo
    ON fo.final_account_id = b.final_account_id
LEFT JOIN temp_idn_names idn
    ON UPPER(b.final_account_nm) = idn.bus_nm
LEFT JOIN temp_student_summary s
    ON s.final_account_id = b.final_account_id
;

-- NOTE: account_segment_granular alias cannot be referenced in the same SELECT
-- where it is defined. Rollup is added in a separate step below.
-- Referencing it directly in the SELECT above (CASE WHEN account_segment_granular = 'Community')
-- will error in Spark SQL too — always materialise first, then derive.

CREATE OR REPLACE TEMP VIEW temp_hcp_account_segment_final AS
SELECT
    *,
    CASE
        WHEN account_segment_granular = 'Community' THEN 'Community'
        ELSE 'Non-Community'
    END AS account_segment
FROM temp_hcp_account_segment
;
```

---

## Example 12 — SoM bucket classification and concordance by regimen

**Business Question:** How do we classify each patient into a Jaypirca SoM eligibility bucket, and what share of eligible patients in each bucket received Jaypirca (concordance)?

```sql
-- grain: one row per patient × month × line × SoM_flag (market level), plus HCP-level variant below
-- output: SoM_flag (AA / 321 / 1L / BTK Naive), regimen_prioritized, concordance rate
-- logic: priority CASE waterfall — order matters, first match wins (AA before 321 before 1L before BTK Naive)
-- safe to adjust: eligible_date cutoff, month filter, regimen LIKE patterns
-- NOT safe to adjust: waterfall layer order — AA must fire before 321, 1L before BTK Naive
-- OBU-specific: source table (<catalog>.obu.cll_line_initiations), SoM bucket labels, cBTKi/Ven line flags
-- dependency: cbtki_min_line, cll_min_bcl2_line, cll_min_jay_line must exist in source table
-- threshold/config: eligible_date cutoff (currently 2023-12-01), month filter (currently >= 2023-02) — see kpi_definitions.md
-- NOTE: patient_priority and final_lines materialised separately to avoid alias
--   reference issues; concordance window functions computed after final deduplication

CREATE OR REPLACE TEMP VIEW temp_classified_lines AS
SELECT
    prsn_id,
    patient_id,
    line,
    month,
    eligible_date,
    regimen_prioritized,
    SoM_flag,
    SUM(line_initiation) AS pats
FROM (
    SELECT
        deduped.patient_id,
        deduped.regimen,
        deduped.line,
        deduped.prsn_id,
        deduped.eligible_date,
        deduped.line_initiation,
        deduped.month,

        CASE
            WHEN deduped.regimen LIKE '%PIRTO%'
                THEN '# Eligible Patients that received Jaypirca'
            WHEN deduped.regimen LIKE '%VEN%'
                 AND (deduped.regimen LIKE '%ACALA%' OR deduped.regimen LIKE '%ZANU%' OR deduped.regimen LIKE '%IBRU%')
                THEN '# Eligible Patients that received BTK-Ven'
            WHEN deduped.regimen LIKE '%VEN%'
                THEN '# Eligible Patients that received Ven'
            WHEN deduped.regimen LIKE '%ACALA%'
                THEN '# Eligible Patients that received BTK'
            WHEN deduped.regimen LIKE '%ZANU%'
                THEN '# Eligible Patients that received BTK'
            WHEN deduped.regimen LIKE '%IBRU%'
                THEN '# Eligible Patients that received BTK'
            ELSE '# Eligible Patients that received Other'
        END AS regimen_prioritized,

        CASE
            WHEN deduped.line > deduped.cbtki_min_line
             AND deduped.line > deduped.cll_min_bcl2_line
             AND (deduped.cll_min_jay_line IS NULL OR deduped.cll_min_jay_line >= deduped.line)
            THEN 'Jaypirca AA SoM'
            WHEN deduped.line > deduped.cbtki_min_line
             AND (deduped.cll_min_jay_line IS NULL OR deduped.line <= deduped.cll_min_jay_line)
            THEN 'Jaypirca 321 SoM'
            WHEN deduped.line = 1
            THEN 'Jaypirca 1L SoM'
            WHEN deduped.cbtki_min_line IS NULL
              OR (deduped.line < deduped.cbtki_min_line AND deduped.line >= 2)
            THEN 'Jaypirca BTK Naive SoM'
        END AS SoM_flag

    FROM (
        SELECT DISTINCT
            patient_id, regimen, line,
            eph_reference_id                                       AS prsn_id,
            date_format(common_date, 'yyyy-MM')                        AS month,
            CASE WHEN DATE_TRUNC('month', common_date) >= '2023-12-01'
                 THEN 1 ELSE 0 END                                 AS eligible_date,
            line_initiation, cbtki_min_line, cll_min_bcl2_line, cll_min_jay_line
        FROM <catalog>.obu.cll_line_initiations
    ) deduped
    WHERE deduped.line_initiation = 1
) tagged
WHERE SoM_flag IS NOT NULL
  AND month >= '2023-02'
GROUP BY prsn_id, patient_id, line, month, eligible_date, regimen_prioritized, SoM_flag
HAVING SUM(line_initiation) > 0
;

CREATE OR REPLACE TEMP VIEW temp_patient_priority AS
SELECT
    patient_id, month, line,
    MIN(CASE SoM_flag
            WHEN 'Jaypirca AA SoM'        THEN 1
            WHEN 'Jaypirca 321 SoM'       THEN 2
            WHEN 'Jaypirca 1L SoM'        THEN 3
            WHEN 'Jaypirca BTK Naive SoM' THEN 4
        END)                                                       AS best_priority
FROM temp_classified_lines
GROUP BY patient_id, month, line
;

CREATE OR REPLACE TEMP VIEW temp_final_lines AS
SELECT cl.*
FROM temp_classified_lines cl
JOIN temp_patient_priority pp
    ON cl.patient_id = pp.patient_id
   AND cl.month      = pp.month
   AND cl.line       = pp.line
WHERE CASE cl.SoM_flag
          WHEN 'Jaypirca AA SoM'        THEN 1
          WHEN 'Jaypirca 321 SoM'       THEN 2
          WHEN 'Jaypirca 1L SoM'        THEN 3
          WHEN 'Jaypirca BTK Naive SoM' THEN 4
      END = pp.best_priority
;

CREATE OR REPLACE TEMP VIEW temp_som_concordance_market AS
SELECT DISTINCT
    patient_id, line, month, regimen_prioritized, pats, SoM_flag,
    SUM(pats) OVER (PARTITION BY SoM_flag, month)                  AS total_pats,
    ROUND(
        SUM(CASE WHEN regimen_prioritized = '# Eligible Patients that received Jaypirca'
                 THEN pats ELSE 0 END)
            OVER (PARTITION BY SoM_flag, month)
        / NULLIF(SUM(pats) OVER (PARTITION BY SoM_flag, month), 0)
    , 4)                                                           AS concordance,
    SUM(CASE WHEN eligible_date = 1 THEN pats END)
        OVER (PARTITION BY SoM_flag, month)                        AS eligible_patients_seen
FROM temp_final_lines
;

-- HCP-level: one row per prsn_id × month × SoM_flag
-- concordance at HCP level = share of that HCP's eligible patients who received Jaypirca
-- see kpi_definitions.md — do not interpret as a binary flag
CREATE OR REPLACE TEMP VIEW temp_som_concordance_hcp AS
SELECT
    prsn_id, month, SoM_flag,
    SUM(pats)                                                      AS total_pats_hcp,
    SUM(CASE WHEN regimen_prioritized = '# Eligible Patients that received Jaypirca'
             THEN pats ELSE 0 END)                                 AS jaypirca_pats_hcp,
    ROUND(
        SUM(CASE WHEN regimen_prioritized = '# Eligible Patients that received Jaypirca'
                 THEN pats ELSE 0 END)
        / NULLIF(SUM(pats), 0)
    , 4)                                                           AS concordance_hcp,
    SUM(CASE WHEN eligible_date = 1 THEN pats ELSE 0 END)          AS eligible_patients_seen_hcp
FROM temp_final_lines
GROUP BY prsn_id, month, SoM_flag
;
```

---

## Example 13 — Trialists, Users, and Adopters (TUA) by HCP × month

**Business Question:** How do we classify each HCP by their cumulative NBRx milestone for a given product — and track how that classification evolves month over month?

```sql
-- grain: one row per HCP (prsn_id) × month × tua_stage
-- tua thresholds are TA-specific — set at the top before running
-- OBU:   trialist=1, user=2, adopter>=3 (3-bucket model)
-- Other: trialist=1, adopter>=5, no user bucket (2-bucket model)
-- safe to adjust: brand filter, date floor, thresholds below
-- NOT safe to assume: month gaps exist — HCPs with no NBRx in a month have no row;
--   cumulative is carried forward via window function over active months only;
--   if gap-filled cumulative is needed, a date spine is required (see rolling window pattern)
-- source: <catalog>.apld_ex.elaad_oncology_masterdata — brand_name filter in CAPS
-- threshold/config: tua thresholds — see kpi_definitions.md for TA-specific values
-- dependency: standalone — no upstream temp tables required
-- downstream: temp_hcp_monthly_nbrx is used by Example 14 (net new HCPs);
--   if running Example 14 after this, skip recreating temp_hcp_monthly_nbrx
-- NOTE: cumulative_nbrx alias not available in same SELECT —
--   tua_stage derived in a separate temp view below

-- ────────────────────────────────────────────────
-- PARAMETERS: set thresholds here before running
-- trialist_threshold : cumulative NBRx = 1        (same across TAs)
-- user_threshold     : cumulative NBRx = 2        (OBU only — remove WHEN block for other TAs)
-- adopter_threshold  : cumulative NBRx >= 3 (OBU) or >= 5 (other TAs)
-- ────────────────────────────────────────────────

CREATE OR REPLACE TEMP VIEW temp_hcp_monthly_nbrx AS
SELECT
    rendering_provider_id                                          AS prsn_id,
    CAST(DATE_TRUNC('month', service_date) AS DATE)                AS month,
    COUNT(DISTINCT patient_id)                                     AS monthly_nbrx
FROM <catalog>.apld_ex.elaad_oncology_masterdata
WHERE brand_name = 'JAYPIRCA'
  AND new_to_brand_flag = 1
  AND service_date >= '2023-01-01'
  AND rendering_provider_id IS NOT NULL
GROUP BY 1, 2
HAVING COUNT(DISTINCT patient_id) > 0
;

CREATE OR REPLACE TEMP VIEW temp_hcp_cumulative AS
SELECT
    prsn_id, month, monthly_nbrx,
    SUM(monthly_nbrx) OVER (
        PARTITION BY prsn_id
        ORDER BY month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                              AS cumulative_nbrx
FROM temp_hcp_monthly_nbrx
;

CREATE OR REPLACE TEMP VIEW temp_tua_hcp_month AS
SELECT
    prsn_id, month, monthly_nbrx, cumulative_nbrx,
    CASE
        WHEN cumulative_nbrx = 1  THEN 'Trialist'
        WHEN cumulative_nbrx = 2  THEN 'User'       -- OBU only; remove for other TAs
        WHEN cumulative_nbrx >= 3 THEN 'Adopter'    -- change to >= 5 for other TAs
    END                                                            AS tua_stage
FROM temp_hcp_cumulative
WHERE cumulative_nbrx > 0
;
```

---

## Example 14 — Net new HCPs per month

**Business Question:** Which HCPs wrote their first-ever NBRx for a given product in a given month, and how many net new HCPs did we add each month?

```sql
-- grain: one row per HCP (prsn_id) × month — only months where HCP is net new
-- net new definition: first calendar month the HCP appears with NBRx > 0, all-time
-- safe to adjust: brand filter, date floor
-- NOT safe to adjust: definition of first_nbrx_month — this is all-time debut,
--   not relative to a lookback window; if reactivation tracking is needed,
--   that is a separate pattern (lookback window approach)
-- threshold/config: brand filter and date floor — see kpi_definitions.md
-- dependency: builds on temp_hcp_monthly_nbrx from Example 13 (TUA)
--   if running standalone, recreate temp_hcp_monthly_nbrx first:
--
--   CREATE OR REPLACE TEMP VIEW temp_hcp_monthly_nbrx AS
--   SELECT
--       rendering_provider_id                    AS prsn_id,
--       CAST(DATE_TRUNC('month', service_date) AS DATE) AS month,
--       COUNT(DISTINCT patient_id)               AS monthly_nbrx
--   FROM <catalog>.apld_ex.elaad_oncology_masterdata
--   WHERE brand_name = 'JAYPIRCA'
--     AND new_to_brand_flag = 1
--     AND rendering_provider_id IS NOT NULL
--   GROUP BY 1, 2
--   HAVING COUNT(DISTINCT patient_id) > 0;
--
-- NOTE: first_nbrx_month alias derived in a separate step

CREATE OR REPLACE TEMP VIEW temp_hcp_first_month AS
SELECT
    prsn_id,
    MIN(month)                                                     AS first_nbrx_month
FROM temp_hcp_monthly_nbrx
GROUP BY prsn_id
;

CREATE OR REPLACE TEMP VIEW temp_net_new_hcp AS
SELECT
    prsn_id,
    first_nbrx_month                                               AS month,
    1                                                              AS is_net_new
FROM temp_hcp_first_month
;

CREATE OR REPLACE TEMP VIEW temp_net_new_summary AS
SELECT
    month,
    COUNT(DISTINCT prsn_id)                                        AS net_new_hcps,
    SUM(COUNT(DISTINCT prsn_id)) OVER (
        ORDER BY month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                              AS cumulative_net_new_hcps
FROM temp_net_new_hcp
GROUP BY month
;
```

---

## Example 15 — Dosing schedule classification by product

**Business Question:** For each claim, what is the patient's dosing schedule — based on days supply at fill time and actual gap to next fill — and how does it compare to the expected injection frequency for that product?

```sql
-- grain: one row per claim per patient per brand
-- two dosing methods computed per claim:
--   dosing        : schedule inferred from days_supply at fill time (plan-time schedule)
--   dosing_method2: schedule inferred from actual gap to next fill (adherence behavior)
--   use dosing for plan-time analysis; use dosing_method2 for actual adherence behavior
-- safe to adjust: brand filter, date floor, dosing thresholds, age cutoff
-- NOT safe to adjust: dosing threshold structure — thresholds are label-specific per brand
--   and must be confirmed before substituting a different product
-- multi-product: run Steps 1-3 once per product with its own thresholds and date floor,
--   then UNION ALL the product temp tables in Step 4
-- drug strength note: each brand has a specific strength (e.g. 300mg/200mg for Dupixent,
--   250mg for Ebglyss, 30mg for Nemluvio) — confirm strength values before reusing
-- age filter: >= 12 years — AD-specific pediatric label threshold; confirm for other indications
-- source filter: atopic_derm_trx = 1 required — filters to AD market claims only
-- lead_dt: next fill date derived via LEAD() over patient × brand × service_date
-- first_date: first fill date derived via MIN() over patient × brand × ntb episode (sum_ntb)
-- time window: varies by objective — see kpi_definitions.md for project-specific date range
-- threshold/config: age cutoff, date floor, drug strength values — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required
-- NOTE: sum_ntb alias not available in Step 1 SELECT — first_date derived in Step 2;
--   days_before_next_fill alias not available in Step 3 — lead_dt - rx_fill_date recomputed inline

-- Step 1: derive lead_dt and ntb episode marker
CREATE OR REPLACE TEMP VIEW temp_ad_base AS
SELECT
    brand_name                                                     AS brand,
    claim_id,
    eph_reference_id                                               AS prsn_id,
    patient_id,
    service_date                                                   AS rx_fill_date,
    drug_strength,
    quantity,
    days_supply,
    EXTRACT(YEAR FROM service_date) - patient_birth_year           AS patient_age,
    LEAD(service_date) OVER (
        PARTITION BY patient_id, brand_name
        ORDER BY service_date
    )                                                              AS lead_dt,
    SUM(new_to_brand_flag) OVER (
        PARTITION BY patient_id, brand_name
        ORDER BY service_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                              AS sum_ntb
FROM <catalog>.apld_ex.elaad_autoimmune_masterdata
WHERE brand_name = 'DUPIXENT'
  AND atopic_derm_trx = 1
  AND service_date >= '2019-04-01'
;

-- Step 2: derive first_date per patient × brand × ntb episode
CREATE OR REPLACE TEMP VIEW temp_ad_with_first AS
SELECT
    *,
    MIN(rx_fill_date) OVER (
        PARTITION BY patient_id, brand, sum_ntb
        ORDER BY rx_fill_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )                                                              AS first_date
FROM temp_ad_base
;

-- Step 3: dosing classification
-- Dupixent 300mg: 2 pens per injection, q2w window = (quantity/2)*14 ± 7
-- Dupixent 200mg: 1.1 pen ratio, q2w window = ROUND(quantity/1.1)*14 ± 7
-- swap CASE blocks entirely when changing product — thresholds are not portable
CREATE OR REPLACE TEMP VIEW temp_dosing_dupixent AS
SELECT
    brand, claim_id, prsn_id, patient_id,
    rx_fill_date, first_date, quantity, drug_strength, days_supply,
    rx_fill_date - first_date                                      AS days_after_first_fill,
    lead_dt - rx_fill_date                                         AS days_before_next_fill,
    CASE
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND days_supply BETWEEN ((quantity/2)*14 - 7) AND ((quantity/2)*14 + 7)
            THEN '1 injection in 2 weeks'
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND days_supply < ((quantity/2)*14 - 7)
            THEN '1 injection in <2 weeks'
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND days_supply > ((quantity/2)*14 + 7)
            THEN '1 injection in >2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND days_supply BETWEEN (ROUND((quantity/1.1),0)*14 - 7) AND (ROUND((quantity/1.1),0)*14 + 7)
            THEN '1 injection in 2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND days_supply < (ROUND((quantity/1.1),0)*14 - 7)
            THEN '1 injection in <2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND days_supply > (ROUND((quantity/1.1),0)*14 + 7)
            THEN '1 injection in >2 weeks'
        ELSE 'Non-Categorized'
    END                                                            AS dosing,
    CASE
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND (lead_dt - rx_fill_date) BETWEEN ((quantity/2)*14 - 7) AND ((quantity/2)*14 + 7)
            THEN '1 injection in 2 weeks'
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND (lead_dt - rx_fill_date) < ((quantity/2)*14 - 7)
            THEN '1 injection in <2 weeks'
        WHEN drug_strength ILIKE '%300%' AND MOD(quantity, 2) = 0
             AND (lead_dt - rx_fill_date) > ((quantity/2)*14 + 7)
            THEN '1 injection in >2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND (lead_dt - rx_fill_date) BETWEEN (ROUND((quantity/1.1),0)*14 - 7) AND (ROUND((quantity/1.1),0)*14 + 7)
            THEN '1 injection in 2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND (lead_dt - rx_fill_date) < (ROUND((quantity/1.1),0)*14 - 7)
            THEN '1 injection in <2 weeks'
        WHEN drug_strength ILIKE '%200%'
             AND (lead_dt - rx_fill_date) > (ROUND((quantity/1.1),0)*14 + 7)
            THEN '1 injection in >2 weeks'
        ELSE 'Non-Categorized'
    END                                                            AS dosing_method2
FROM temp_ad_with_first
WHERE patient_age >= 12
;

-- Step 4: multi-product consolidation + HCP specialty join
-- repeat Steps 1-3 for each additional brand with brand-specific filters and thresholds
-- <catalog>.sas.customer join key: prsn_id = eph_reference_id (confirm column name in <catalog>.sas.customer)
CREATE OR REPLACE TEMP VIEW temp_dosing_consolidated AS
SELECT
    a.*,
    b.ly_mjr_spclty_cd,
    b.ly_mjr_spclty_desc_txt,
    b.ly_spclty_grp
FROM (
    SELECT * FROM temp_dosing_dupixent
    -- UNION ALL SELECT * FROM temp_dosing_ebglyss    -- uncomment when adding Ebglyss
    -- UNION ALL SELECT * FROM temp_dosing_nemluvio   -- uncomment when adding Nemluvio
) a
LEFT JOIN <catalog>.sas.customer b ON a.prsn_id = b.prsn_id
;
```

---

## Example 16 — Mode of administration classification by product

**Business Question:** For each claim, what is the mode of administration — IV, SC, or Oral — for a given immunology product?

```sql
-- grain: one row per claim (claim_id)
-- output: mode_of_administration (IV / SC / ORAL / -)
-- logic: priority CASE waterfall per product — order matters, IV conditions checked before SC default
-- safe to adjust: product list
-- NOT safe to adjust: J-codes, NDC codes, drug strength values per product —
--   these are billing-code-level identifiers; confirm with IMM team before modifying
-- source filter: atopic_derm_trx = 1 required — AD market claims only
-- column mapping:
--   source_flag = 'MX' → medical/infusion claim (was FLAG='P' in source)
--   source_flag = 'RX' → retail pharmacy claim (was FLAG='R' in source)
--   px_code       → PRC_CD  |  ndc → NDC_CD  |  generic_name → PRODUCT
-- IMM-specific: product list and J-codes are IMM/IBD-specific
-- threshold/config: NDC codes and J-codes per product — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required

CREATE OR REPLACE TEMP VIEW temp_moa AS
SELECT
    claim_id,
    brand_name                                                     AS main_product,
    source_flag,
    px_code,
    ndc,
    drug_strength,
    generic_name,
    eph_reference_id                                               AS prsn_id,
    patient_id,
    service_date,
    CASE
        WHEN brand_name = 'CIMZIA' THEN 'SC'
        WHEN brand_name = 'ENTYVIO'
             AND (
                 (source_flag = 'MX' AND px_code IN ('J3380', 'C9026'))
              OR (source_flag = 'MX' AND ndc IN ('64764030020'))
              OR (source_flag = 'MX' AND ndc IS NULL AND px_code IN ('J3490', 'J3590', 'C9399', 'S9359'))
              OR (source_flag = 'RX' AND drug_strength IN ('300 MG'))
             ) THEN 'IV'
        WHEN brand_name = 'ENTYVIO' THEN 'SC'
        WHEN brand_name = 'HUMIRA' THEN 'SC'
        WHEN brand_name = 'OMVOH'
             AND (
                 (source_flag = 'MX' AND px_code IN ('J2267', 'C9168'))
              OR (source_flag = 'MX' AND ndc IN ('00002757501'))
              OR (source_flag = 'MX' AND ndc IS NULL AND px_code IN ('J3490', 'J3590', 'C9399', 'S9359'))
              OR (source_flag = 'RX' AND drug_strength IN ('300 MG/15 ML'))
             ) THEN 'IV'
        WHEN brand_name = 'OMVOH' THEN 'SC'
        WHEN brand_name = 'REMICADE' AND generic_name <> 'ZYMFENTRA' THEN 'IV'
        WHEN brand_name = 'REMICADE' THEN 'SC'
        WHEN brand_name = 'RINVOQ' THEN 'ORAL'
        WHEN brand_name = 'SIMPONI'
             AND (px_code IN ('J1602') OR ndc IN ('57894035001'))
            THEN 'IV'
        WHEN brand_name = 'SIMPONI' THEN 'SC'
        WHEN brand_name = 'SKYRIZI'
             AND (
                 (source_flag = 'MX' AND px_code IN ('J2327'))
              OR (source_flag = 'MX' AND ndc IN ('00074501501'))
              OR (source_flag = 'MX' AND ndc IS NULL AND px_code IN ('J3490', 'J3590', 'C9399', 'S9359'))
              OR (source_flag = 'RX' AND drug_strength IN ('600 MG/10 ML'))
             ) THEN 'IV'
        WHEN brand_name = 'SKYRIZI' THEN 'SC'
        WHEN brand_name = 'STELARA'
             AND (
                 (source_flag = 'MX' AND px_code IN ('J3358', 'Q9989', 'C9261', 'C9487'))
              OR (source_flag = 'MX' AND ndc IN ('57894005427'))
              OR (source_flag = 'MX' AND ndc IS NULL AND px_code IN ('J3490', 'J3590', 'C9399', 'S9359'))
              OR (source_flag = 'RX' AND drug_strength IN ('130 MG/26 ML'))
             ) THEN 'IV'
        WHEN brand_name = 'STELARA' THEN 'SC'
        WHEN brand_name = 'TREMFYA'
             AND (
                 (source_flag = 'MX' AND px_code IN ('J1628', 'C9029'))
              OR (source_flag = 'MX' AND ndc IN ('57894065001', '57894065002'))
              OR (source_flag = 'MX' AND ndc IS NULL AND px_code IN ('J3490', 'J3590', 'C9399', 'S9359'))
              OR (source_flag = 'RX' AND drug_strength IN ('200 MG/20 ML'))
             ) THEN 'IV'
        WHEN brand_name = 'TREMFYA' THEN 'SC'
        WHEN brand_name = 'TYSABRI' THEN 'IV'
        WHEN brand_name = 'VELSIPITY' THEN 'ORAL'
        WHEN brand_name = 'XELJANZ' THEN 'ORAL'
        WHEN brand_name = 'ZEPOSIA' THEN 'ORAL'
        ELSE '-'
    END                                                            AS mode_of_administration
FROM <catalog>.apld_ex.elaad_autoimmune_masterdata
WHERE atopic_derm_trx = 1
;
```

---

## Example 17 — HCPs who received a promotional detail for a given brand

**Business Question:** Which HCPs received a qualifying promotional detail for a given brand within a specified time period?

```sql
-- grain: one row per HCP (eph_reference_id) — distinct, no duplicates
-- output: unique list of HCPs who received a qualifying detail
-- qualifying detail definition:
--   department = 'RETAIL' (excludes non-retail channels e.g. hospital/IDN)
--   call_classification excludes 'SAMPLE ONLY' and 'EVENT ONLY' (promotional contact required)
--   promotional_vs_logistical = 'PROMOTIONAL' (excludes logistics-only calls)
--   customer_type_code = 'HCP' (excludes non-HCP contacts e.g. office staff)
-- safe to adjust: product_name, date range, department, exclusion list
-- NOT safe to assume: call_classification and promotional_vs_logistical filters are
--   both required — removing either will inflate HCP counts with non-promotional contacts
-- time window: varies by objective — see kpi_definitions.md for project-specific date range
-- threshold/config: product_name, department, date range — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required

CREATE OR REPLACE TEMP VIEW temp_detailed_hcps AS
SELECT DISTINCT
    eph_reference_id
FROM <catalog>.sas.activity_calls
WHERE product_name = 'EBGLYSS'
  AND department = 'RETAIL'
  AND call_classification NOT IN ('SAMPLE ONLY', 'EVENT ONLY')
  AND promotional_vs_logistical = 'PROMOTIONAL'
  AND activity_date BETWEEN '2025-04-01' AND '2026-03-31'
  AND customer_type_code = 'HCP'
;
```

---

## Example 18 — HCPs who wrote NBRx for a specific patient age group

**Business Question:** Which HCPs wrote new brand prescriptions for patients within a specified age range in a given time period?

```sql
-- grain: one row per HCP (eph_reference_id) — distinct, no duplicates
-- output: unique list of HCPs who wrote qualifying NBRx for target age group
-- age calculation: derived from service_date year minus patient_birth_year
--   this is a year-level approximation — patients near their birthday in the service month
--   may be miscategorised by up to 1 year
-- safe to adjust: age threshold, date range, indication filter
-- NOT safe to assume: patient_birth_year = 0 is a sentinel value in ELAAD
--   (not a real birth year) — always filter patient_birth_year IS NOT NULL
--   to exclude these records before applying age logic
-- age filter: < 12 years is AD-specific pediatric threshold —
--   confirm cutoff before reusing for other indications
-- time window: varies by objective — see kpi_definitions.md for project-specific date range
-- threshold/config: age cutoff, indication flag, date range — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required

CREATE OR REPLACE TEMP VIEW temp_hcps_pediatric_nbrx AS
SELECT DISTINCT
    eph_reference_id
FROM <catalog>.apld_ex.elaad_autoimmune_masterdata
WHERE atopic_derm_new_to_brand_flag = 1
  AND service_date BETWEEN '2025-04-01' AND '2026-03-31'
  AND patient_birth_year IS NOT NULL
  AND (EXTRACT(YEAR FROM service_date) - patient_birth_year) < 12
;
```

---

## Example 19 — Cross-TA patient overlap analysis

**Business Question:** Which patients are being treated across two therapeutic areas simultaneously, and what products are they on in each TA?

```sql
-- grain: one row per overlapping patient
-- output: overlap patient list with most recent product per TA
-- use case: cross-TA utilization, comorbidity analysis, market opportunity sizing
-- safe to adjust: TA sources (swap masterdata tables), indication filters, date range, product lists
-- NOT safe to adjust: INNER JOIN in overlap_patients — this is intentional;
--   only patients present in BOTH TAs qualify; changing to LEFT JOIN inflates the pool
-- biosimilar remapping: GENERIC_NAME LIKE patterns for Humira/Remicade/Stelara are
--   IMM-specific — confirm equivalent remapping logic for other TAs before reusing
-- market basket logic: full_market and oral_market flags use NDC lookup against
--   elaad_dim_product_plus — market basket definition varies by TA and objective;
--   confirm MARKET_BASKET value with TA lead before reusing
-- time window: varies by objective — see kpi_definitions.md for project-specific date range
-- threshold/config: indication filters, market basket values, date range — see kpi_definitions.md
-- dependency: standalone — no upstream temp tables required
-- NOTE: ROW_NUMBER alias not available in same SELECT — filtered in outer subquery
-- TA sources in this example:
--   TA 1: <catalog>.apld_ex.elaad_autoimmune_masterdata (IBD — inflammatory_bowel_disease_trx > 0)
--   TA 2: <catalog>.apld_ex.elaad_obesity_masterdata (Obesity — class = 'INCRETIN OMM')
--   swap either source + indication filter to run a different TA pairing

CREATE OR REPLACE TEMP VIEW temp_ta1_data AS
SELECT
    patient_id, brand_name, service_date, claim_id, class,
    CASE
        WHEN generic_name LIKE '%ADALIMUMAB%'  THEN 'HUMIRA'
        WHEN generic_name LIKE '%INFLIXIMAB%'  THEN 'REMICADE'
        WHEN generic_name LIKE '%USTEKINUMAB%' THEN 'STELARA'
        ELSE brand_name
    END                                                            AS main_product
FROM <catalog>.apld_ex.elaad_autoimmune_masterdata
WHERE inflammatory_bowel_disease_trx > 0
  AND service_date BETWEEN '2025-01-01' AND '2026-04-30'
;

CREATE OR REPLACE TEMP VIEW temp_ta2_data AS
SELECT
    patient_id, brand_name, service_date, claim_id,
    CASE WHEN ndc IN (
        SELECT DISTINCT ndc FROM <catalog>.apld_ex.elaad_dim_product_plus
        WHERE market_basket = 'INCRETIN OMM'
    ) THEN 1 ELSE 0 END                                            AS full_market,
    CASE WHEN ndc IN (
        SELECT DISTINCT ndc FROM <catalog>.apld_ex.elaad_dim_product_plus
        WHERE brand_name IN ('WEGOVY PILL', 'FOUNDAYO')
    ) THEN 1 ELSE 0 END                                            AS oral_market
FROM <catalog>.apld_ex.elaad_obesity_masterdata
WHERE service_date BETWEEN '2025-01-01' AND '2026-04-30'
  AND class = 'INCRETIN OMM'
;

-- INNER JOIN is intentional — do not change to LEFT JOIN
CREATE OR REPLACE TEMP VIEW temp_overlap_patients AS
SELECT DISTINCT a.patient_id
FROM temp_ta1_data a
INNER JOIN temp_ta2_data b ON a.patient_id = b.patient_id
;

CREATE OR REPLACE TEMP VIEW temp_recent_ta1 AS
SELECT
    patient_id,
    MAX(CASE WHEN rn_overall = 1 THEN main_product END)            AS recent_ta1_product,
    MAX(CASE WHEN class = 'IL-23' AND rn_class = 1
             THEN main_product END)                                AS recent_ta1_il23_product
FROM (
    SELECT
        patient_id, main_product, service_date, class,
        ROW_NUMBER() OVER (PARTITION BY patient_id
                           ORDER BY service_date DESC, claim_id DESC) AS rn_overall,
        ROW_NUMBER() OVER (PARTITION BY patient_id, class
                           ORDER BY service_date DESC, claim_id DESC) AS rn_class
    FROM temp_ta1_data
) t
GROUP BY patient_id
;

CREATE OR REPLACE TEMP VIEW temp_recent_ta2 AS
SELECT
    patient_id,
    MAX(CASE WHEN rn_full = 1 THEN brand_name END)                 AS recent_ta2_product,
    MAX(CASE WHEN oral_market = 1 AND rn_oral = 1
             THEN brand_name END)                                  AS recent_ta2_oral_product
FROM (
    SELECT
        patient_id, brand_name, service_date, full_market, oral_market,
        ROW_NUMBER() OVER (PARTITION BY patient_id
                           ORDER BY service_date DESC, claim_id DESC) AS rn_full,
        ROW_NUMBER() OVER (PARTITION BY patient_id, oral_market
                           ORDER BY service_date DESC, claim_id DESC) AS rn_oral
    FROM temp_ta2_data
) t
GROUP BY patient_id
;

-- extend by joining back to temp_ta1_data / temp_ta2_data for product flags or TRx counts
CREATE OR REPLACE TEMP VIEW temp_overlap_final AS
SELECT
    p.patient_id,
    r1.recent_ta1_product,
    r1.recent_ta1_il23_product,
    r2.recent_ta2_product,
    r2.recent_ta2_oral_product
FROM temp_overlap_patients p
LEFT JOIN temp_recent_ta1 r1 ON r1.patient_id = p.patient_id
LEFT JOIN temp_recent_ta2 r2 ON r2.patient_id = p.patient_id
;
```

---

*Add new examples here as your team builds them. The more examples, the better Claude understands your patterns.*"""
