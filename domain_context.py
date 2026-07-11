"""
domain_context.py — primerMD (Databricks edition)

Reused verbatim from the Redshift-era primerMD app.py. Pure data, zero DB
dependency — pre-baked disease state / market context / key population /
drug performance content per therapeutic area + indication. Surfaced on the
/new intake form and folded into the generated prompt so Claude.ai starts
the session with the right domain framing, not just schema/KPI mechanics.
"""

DOMAIN_CONTEXT = {
    "Oncology": {
        "CLL": {
            "disease_state": (
                "B-cell malignancy and the most common adult leukemia in Western countries. "
                "Follows an indolent course; treatment is triggered by symptoms, cytopenias, or rapid progression. "
                "BTK inhibitors have become standard of care across lines of therapy."
            ),
            "market_context": (
                "BTK inhibitor-dominated market. Ibrutinib (Imbruvica) established the class; "
                "acalabrutinib (Calquence) and zanubrutinib (Brukinsa) competitive in 1L+. "
                "Post-covalent BTKi segment growing as patients progress. "
                "BCL-2 inhibitor venetoclax (Venclexta) relevant in combination and sequential settings."
            ),
            "key_population": (
                "Adults with CLL/SLL. 1L defined as first systemic therapy. "
                "Post-BTKi segment = patients who progressed on or are intolerant of a prior covalent BTKi. "
                "Key diagnosis anchor: ICD-10 C91.1."
            ),
            "drug_performance": (
                "Lilly: Jaypirca (pirtobrutinib) — non-covalent BTKi. "
                "Current approved indication (Dec 2025 traditional approval, BRUIN CLL-321): "
                "adults with relapsed or refractory CLL/SLL who have previously been treated with "
                "a covalent BTK inhibitor. Removes the prior accelerated-approval requirement of "
                "≥2 lines including both a BTKi and BCL-2 inhibitor — now accessible directly "
                "after covalent BTKi failure. "
                "Anticipatory 1L CLL approval in pipeline — analytics should be built to support "
                "both post-covalent BTKi and 1L HCP opportunity identification. "
                "Competitive context: covalent BTKi class (ibrutinib, acalabrutinib, zanubrutinib) "
                "dominates 1L; venetoclax combinations active in BTKi-intolerant patients; "
                "post-BTKi segment is Jaypirca's current core but 1L launch will require "
                "targeting a significantly broader HCP universe."
            ),
        },
        "MCL": {
            "disease_state": (
                "Aggressive B-cell non-Hodgkin lymphoma with poor prognosis. "
                "BTK inhibitors are the backbone of relapsed/refractory therapy. "
                "High relapse rates after covalent BTKi treatment remain a significant clinical challenge."
            ),
            "market_context": (
                "Ibrutinib, acalabrutinib, and zanubrutinib established in R/R MCL. "
                "Post-BTKi MCL is an underserved segment with limited options prior to pirtobrutinib approval. "
                "Frontline chemoimmunotherapy (BR, R-CHOP, Nordic) followed by ASCT in eligible patients."
            ),
            "key_population": (
                "Adults with relapsed/refractory MCL. "
                "Post-BTKi segment = progressed on ≥1 prior BTKi. "
                "Key diagnosis anchor: ICD-10 C83.1."
            ),
            "drug_performance": (
                "Lilly: Jaypirca (pirtobrutinib) — indicated for R/R MCL after ≥2 prior lines including a BTKi. "
                "Positioned in a setting with high unmet need following covalent BTKi failure. "
                "Competitive context: brexucabtagene autoleucel (Tecartus) CAR-T active in post-BTKi; "
                "limited chemotherapy options in later lines."
            ),
        },
        "eBC": {
            "disease_state": (
                "Early breast cancer confined to the breast and/or regional lymph nodes; curative intent. "
                "HR+/HER2- is the dominant subtype in the adjuvant CDK4/6i setting. "
                "CDK4/6 inhibitors are now standard of care in the adjuvant setting for high-risk patients."
            ),
            "market_context": (
                "CDK4/6 inhibitor adjuvant market — abemaciclib (Verzenio) and ribociclib (Kisqali) both approved. "
                "Palbociclib (Ibrance) does not have an adjuvant approval. "
                "Adjuvant endocrine backbone is aromatase inhibitor or tamoxifen. "
                "High-risk patient identification (nodal involvement, tumor size, grade) drives eligibility; "
                "Ki-67 requirement removed from Verzenio label in 2023. "
                "Kisqali adjuvant approval (Sep 2024, NATALEE) includes node-negative patients — "
                "broader eligible population than Verzenio's node-positive focus."
            ),
            "key_population": (
                "High-risk HR+/HER2- early breast cancer patients post-surgery. "
                "Risk defined by nodal involvement and Ki-67 expression. "
                "Key diagnosis anchor: ICD-10 C50.x."
            ),
            "drug_performance": (
                "Lilly: Verzenio (abemaciclib) — CDK4/6 inhibitor approved in adjuvant HR+/HER2- eBC "
                "with high recurrence risk (≥4 nodes, or 1-3 nodes + tumor ≥5cm or grade 3); "
                "2-year treatment duration per monarchE. "
                "monarchE 7-year OS analysis (Aug 2025) showed statistically significant overall survival "
                "benefit — first CDK4/6i with OS data in the adjuvant setting. "
                "Competitive context: Kisqali (ribociclib, Novartis) approved adjuvant Sep 2024 (NATALEE); "
                "3-year treatment duration at 400mg; includes node-negative patients — "
                "broader label but no OS data to date. Direct competition in the node-positive segment."
            ),
        },
        "mBC": {
            "disease_state": (
                "Incurable HR+/HER2- advanced or metastatic breast cancer. "
                "Treatment goal is disease control and quality of life. "
                "CDK4/6 inhibitors combined with endocrine therapy are 1L standard of care. "
                "Endocrine resistance and ESR1 mutations are key later-line challenges."
            ),
            "market_context": (
                "CDK4/6 inhibitor market — palbociclib (Ibrance), ribociclib (Kisqali), "
                "abemaciclib (Verzenio) all approved in 1L+. "
                "PI3K/AKT pathway agents and antibody-drug conjugates (ADCs) active in later lines. "
                "Oral SERDs (elacestrant/Orserdu) established in ESR1-mutant later-line setting. "
                "Inluriyo entering a competitive later-line endocrine therapy landscape."
            ),
            "key_population": (
                "Adults with HR+/HER2- advanced or metastatic breast cancer. "
                "Prior CDK4/6i exposure increasingly common in later-line patients. "
                "ESR1 mutation status relevant for SERD positioning. "
                "Key diagnosis anchor: ICD-10 C50.x with metastatic staging."
            ),
            "drug_performance": (
                "Lilly: Verzenio (abemaciclib) — CDK4/6 inhibitor in 1L+ mBC in combination with endocrine therapy. "
                "Inluriyo (imlunestrant) — oral selective estrogen receptor degrader (SERD); "
                "indicated for ER+/HER2- advanced/metastatic BC after prior endocrine therapy. "
                "Differentiated by oral route vs. fulvestrant (injectable SERD) and activity in ESR1-mutant disease. "
                "Competitive context: Orserdu (elacestrant) established oral SERD; "
                "ADCs (Enhertu, Trodelvy) active in later lines regardless of ER status."
            ),
        },
    },

    "Immunology": {
        "Atopic Dermatitis": {
            "disease_state": (
                "Chronic inflammatory skin condition driven by Th2 pathway dysregulation, "
                "primarily IL-4 and IL-13 signaling. "
                "Characterized by pruritus, skin barrier disruption, and flares. "
                "Severity ranges from mild to severe; moderate-to-severe patients are the systemic therapy target."
            ),
            "market_context": (
                "IL-4/IL-13 pathway dominates biologics. "
                "Dupixent (dupilumab, Sanofi/Regeneron) is market leader with broad label (ages 6 months+). "
                "Ebglyss (lebrikizumab, Sep 2024 US approval) and Adbry (tralokinumab) compete in anti-IL-13 space. "
                "JAK inhibitors (Rinvoq/upadacitinib, Cibinqo/abrocitinib) active in moderate-severe segment. "
                "TCS/TCI use as background therapy is a key dependency metric for analytics. "
                "Dosing convenience is a differentiator: Ebglyss Q8W maintenance (6 injections/year) "
                "approved Jun 2026 — only biologic in class approved at this frequency without mandatory topicals."
            ),
            "key_population": (
                "Moderate-to-severe AD adults inadequately controlled on topical therapy. "
                "Prior biologic exposure (especially dupilumab) increasingly common in later-line patients. "
                "Key diagnosis anchor: ICD-10 L20.x."
            ),
            "drug_performance": (
                "Lilly: Ebglyss (lebrikizumab) — high-affinity anti-IL-13 monoclonal antibody. "
                "US FDA approved Sep 2024 for adults and adolescents ≥12 years weighing ≥40kg. "
                "Dosing: 500mg loading (2×250mg at weeks 0 and 2), then 250mg Q2W until response, "
                "then Q2W or Q8W (6 injections/year) maintenance — approved Q8W Jun 2026. "
                "Only biologic in class with approved Q8W maintenance without mandatory topical co-therapy. "
                "Pediatric expansion (ages 6mo–<12yr) in pipeline (ADorable-1 phase 3 positive topline). "
                "Competitive context: Dupixent (dupilumab) targets IL-4Rα blocking both IL-4 and IL-13 — "
                "broader mechanism, established leader; Adbry (tralokinumab) also anti-IL-13; "
                "JAK inhibitors offer oral option but carry class-level safety labeling requirements."
            ),
        },
        "Psoriasis": {
            "disease_state": (
                "Chronic immune-mediated skin disease; plaque psoriasis is the most common form. "
                "IL-17 and IL-23 pathways are the primary targets for moderate-to-severe disease. "
                "High efficacy bar — PASI 90/100 clearance is now the expected benchmark."
            ),
            "market_context": (
                "IL-17 inhibitors (Cosentyx/secukinumab, Taltz/ixekizumab) and "
                "IL-23 inhibitors (Skyrizi/risankizumab, Tremfya/guselkumab) dominate the biologic market. "
                "Skyrizi (AbbVie) is the fastest-growing asset. "
                "Biosimilar pressure on older TNF inhibitors. "
                "Taltz competes across both PSO and PSA indications."
            ),
            "key_population": (
                "Adults with moderate-to-severe plaque psoriasis. "
                "Biologic-naive and biologic-experienced segments both relevant. "
                "Key diagnosis anchor: ICD-10 L40.0."
            ),
            "drug_performance": (
                "Lilly: Taltz (ixekizumab) — anti-IL-17A monoclonal antibody; "
                "approved for moderate-to-severe plaque psoriasis. "
                "Rapid onset of action; high PASI 90/100 response rates. "
                "Competitive context: Cosentyx (secukinumab, Novartis) established IL-17A competitor; "
                "Skyrizi (risankizumab, AbbVie) IL-23 inhibitor gaining share with strong durability data; "
                "Tremfya (guselkumab, J&J) IL-23 competitor."
            ),
        },
        "Psoriatic Arthritis": {
            "disease_state": (
                "Chronic inflammatory arthritis associated with psoriasis. "
                "Affects joints, entheses, and skin; heterogeneous presentation. "
                "IL-17 and IL-23 inhibitors, TNF inhibitors, and JAK inhibitors all active. "
                "Treat-to-target approach with minimal disease activity (MDA) as goal."
            ),
            "market_context": (
                "TNF inhibitors (Humira, Enbrel) remain widely used despite biosimilar entry. "
                "IL-17 inhibitors (Taltz, Cosentyx) active across joint and skin domains. "
                "IL-23 inhibitors (Skyrizi, Tremfya) approved in PSA. "
                "JAK inhibitors (Rinvoq, Xeljanz) offer oral option. "
                "Market moving toward agents with dual skin and joint efficacy."
            ),
            "key_population": (
                "Adults with active psoriatic arthritis. "
                "Biologic-naive and TNF-experienced segments both relevant. "
                "Patients with significant skin involvement benefit from dual-domain agents. "
                "Key diagnosis anchor: ICD-10 L40.5."
            ),
            "drug_performance": (
                "Lilly: Taltz (ixekizumab) — anti-IL-17A antibody approved for active PSA; "
                "demonstrates efficacy across joint, skin, and enthesitis domains. "
                "Competitive context: Cosentyx (secukinumab) direct IL-17A competitor; "
                "Skyrizi (risankizumab) and Tremfya (guselkumab) IL-23 inhibitors gaining in PSA; "
                "TNF biosimilars (adalimumab biosimilars) create pricing pressure in earlier lines."
            ),
        },
        "IBD": {
            "disease_state": (
                "Umbrella term for Crohn's disease (CD) and ulcerative colitis (UC). "
                "Chronic relapsing-remitting inflammation of the GI tract. "
                "Anti-TNF agents are established; IL-23, JAK inhibitors, and gut-selective biologics "
                "are increasingly used in moderate-to-severe and biologic-refractory patients."
            ),
            "market_context": (
                "Humira (adalimumab) biosimilar entry reshaping the market economics. "
                "Skyrizi (risankizumab, AbbVie) and Rinvoq (upadacitinib, AbbVie) strong in CD and UC. "
                "Entyvio (vedolizumab, Takeda) gut-selective with strong safety profile. "
                "Stelara (ustekinumab, J&J) IL-12/23 inhibitor losing exclusivity. "
                "High unmet need remains in biologic-refractory patients."
            ),
            "key_population": (
                "Adults with moderate-to-severe Crohn's disease or ulcerative colitis "
                "inadequately controlled on conventional or biologic therapy. "
                "Key diagnosis anchors: ICD-10 K50.x (Crohn's disease), K51.x (ulcerative colitis)."
            ),
            "drug_performance": (
                "Lilly: Omvoh (mirikizumab) — anti-IL-23p19 monoclonal antibody. "
                "Approved for moderately to severely active UC (Oct 2023) and Crohn's disease (Jan 2025, VIVID-1) — "
                "now covers the full IBD spectrum. "
                "First biologic in >15 years to disclose 2-year phase 3 efficacy data in CD at time of approval. "
                "Single-injection once-monthly SC maintenance approved Oct 2025 for UC (simplified from 2-injection). "
                "Gained first-line biologic formulary coverage from 2 of 3 largest PBMs effective Jan 2025. "
                "Competitive context: Skyrizi (risankizumab, AbbVie) approved in both UC and CD — "
                "direct IL-23 competitor with strong market position; "
                "Entyvio (vedolizumab, Takeda) gut-selective with strong safety data; "
                "Rinvoq (upadacitinib, AbbVie) JAK inhibitor active in both UC and CD."
            ),
        },
    },

    "Neuroscience": {
        "Alzheimer's Disease": {
            "disease_state": (
                "Progressive neurodegenerative disease; amyloid plaques and tau tangles are pathological hallmarks. "
                "Early symptomatic AD — mild cognitive impairment (MCI) to mild dementia — "
                "is the current treatment target for disease-modifying therapies. "
                "Amyloid confirmation by PET or CSF biomarker required for treatment eligibility."
            ),
            "market_context": (
                "Anti-amyloid antibody class is the first disease-modifying treatment category for AD. "
                "Leqembi (lecanemab, Eisai/Biogen) received full FDA approval Jul 2023 (traditional) — first in class; "
                "Kisunla (donanemab, Lilly) received full FDA approval Jul 2024 (TRAILBLAZER-ALZ 2). "
                "Market still early-stage — amyloid confirmation (PET or CSF), infusion infrastructure, "
                "ARIA monitoring with MRI, and ApoE4 testing are significant adoption barriers. "
                "Payer coverage evolving; CMS coverage expanding; both drugs now have Medicare coverage. "
                "Kisunla label updated Jul 2025 with modified titration schedule that reduces ARIA-E risk "
                "from ~24% to ~14% while preserving amyloid clearance efficacy."
            ),
            "key_population": (
                "Adults with early symptomatic Alzheimer's disease confirmed by amyloid biomarker "
                "(PET scan or CSF analysis). "
                "ApoE4 carrier status relevant for ARIA risk stratification and patient selection. "
                "Key diagnosis anchor: ICD-10 G30.x."
            ),
            "drug_performance": (
                "Lilly: Kisunla (donanemab) — anti-amyloid beta antibody targeting N3pG amyloid. "
                "Differentiated by potential treatment completion endpoint based on amyloid clearance — "
                "unique among the class. Monthly IV infusion. "
                "Lilly: AMYVID (florbetapir F 18) — FDA-approved PET imaging agent for amyloid beta "
                "neuritic plaque density in adults with cognitive impairment. "
                "AMYVID is a critical upstream asset — amyloid PET confirmation is required for "
                "Kisunla treatment eligibility, making AMYVID part of the patient identification "
                "and diagnostic funnel analytics. "
                "Key analytics implication: AMYVID scan rates and amyloid confirmation rates are "
                "leading indicators for the Kisunla-eligible population. "
                "Competitive context: Leqembi (lecanemab, Eisai/Biogen) biweekly dosing vs. Kisunla monthly; "
                "ARIA profiles differ — direct head-to-head data not available; "
                "Vizamyl (flutemetamol, GE Healthcare) and Neuraceq (florbetaben, Life Molecular) "
                "are competing amyloid PET tracers to AMYVID; "
                "CSF biomarker testing (Lumipulse) is an alternative to PET for amyloid confirmation."
            ),
        },
    },

    "Metabolic": {
        "Obesity": {
            "disease_state": (
                "Chronic disease defined by excess adiposity with metabolic and cardiovascular consequences. "
                "GLP-1 receptor agonists have redefined the treatment paradigm — "
                "weight loss of 15–25% is now achievable pharmacologically. "
                "Obesity is increasingly recognized as a disease requiring long-term management, "
                "not a lifestyle issue."
            ),
            "market_context": (
                "GLP-1/GIP class dominant — Wegovy (semaglutide, Novo Nordisk) and "
                "Zepbound (tirzepatide, Lilly) are leading injectable options. "
                "Supply constraints easing as manufacturing scales. "
                "Oral semaglutide (Rybelsus) and oral GLP-1s in pipeline. "
                "Significant payer and access pressure; step therapy and prior authorization requirements common. "
                "Compounding market created friction; Foundayo addresses specific access segments."
            ),
            "key_population": (
                "Adults with BMI ≥30, or BMI ≥27 with at least one weight-related comorbidity "
                "(T2D, hypertension, dyslipidemia, obstructive sleep apnea). "
                "Key diagnosis anchor: ICD-10 E66.x."
            ),
            "drug_performance": (
                "Lilly: Zepbound (tirzepatide) — dual GLP-1/GIP receptor agonist approved for chronic weight management; "
                "superior weight loss vs. semaglutide demonstrated in SURMOUNT trials. "
                "Also approved Dec 2024 for moderate-to-severe OSA in adults with obesity (BMI ≥30) — "
                "first and only FDA-approved pharmacological treatment for OSA. "
                "Foundayo (tirzepatide) — same molecule as Zepbound, positioned for "
                "specific payer and access segments (not a compounding-resistant formulation distinction "
                "so much as a channel and access strategy). "
                "Competitive context: Wegovy (semaglutide 2.4mg, Novo Nordisk) established market leader "
                "by volume; oral semaglutide and CagriSema in Novo pipeline represent future competition; "
                "orforglipron (oral GLP-1, Lilly) in late-stage development as potential oral option."
            ),
        },
        "Diabetes": {
            "disease_state": (
                "Chronic metabolic disease of insulin resistance and progressive beta-cell dysfunction. "
                "GLP-1 receptor agonists are now the preferred add-on after metformin given "
                "CV and weight benefits. "
                "SGLT-2 inhibitors are relevant for patients with CKD or heart failure comorbidities. "
                "Market shifting toward combination cardiometabolic management."
            ),
            "market_context": (
                "GLP-1 class growing rapidly — Ozempic (semaglutide, Novo Nordisk) is the dominant injectable; "
                "Jardiance (empagliflozin, BI/Lilly) strong in CKD/HF segment. "
                "Mounjaro (tirzepatide) competing on superior HbA1c reduction and weight loss. "
                "Oral semaglutide (Rybelsus) and tirzepatide oral formulations in development. "
                "Class competition intensifying with pipeline GLP-1/GIP and triple agonists."
            ),
            "key_population": (
                "Adults with type 2 diabetes inadequately controlled on oral agents. "
                "GLP-1 naive and GLP-1 experienced segments both relevant. "
                "Cardiovascular risk, CKD, and obesity comorbidities drive treatment selection. "
                "Key diagnosis anchor: ICD-10 E11.x."
            ),
            "drug_performance": (
                "Lilly: Mounjaro (tirzepatide) — dual GLP-1/GIP agonist; "
                "superior HbA1c reduction vs. semaglutide demonstrated in SURPASS trials. "
                "Differentiated by meaningful weight loss benefit on top of glycemic control. "
                "Competitive context: Ozempic (semaglutide 1mg, Novo Nordisk) — established weekly injectable; "
                "Trulicity (dulaglutide, Lilly) earlier-generation GLP-1 still active in market; "
                "SGLT-2 class (Jardiance, Farxiga) preferred in CKD/HF regardless of GLP-1 use."
            ),
        },
        "Sleep Apnea": {
            "disease_state": (
                "Obstructive sleep apnea (OSA) caused by upper airway collapse during sleep. "
                "Historically managed with CPAP as the only effective intervention. "
                "GLP-1 receptor agonists have demonstrated meaningful AHI reduction in "
                "patients with obesity-related OSA, creating a new pharmacological treatment category."
            ),
            "market_context": (
                "Nascent pharmacological market — CPAP remains standard of care and is not displaced. "
                "Zepbound is the first and currently only FDA-approved pharmacological treatment "
                "for moderate-to-severe OSA in adults with obesity. "
                "Market development requires OSA patient identification through sleep medicine and "
                "primary care channels. "
                "Payer coverage for OSA indication still developing."
            ),
            "key_population": (
                "Adults with moderate-to-severe OSA (AHI ≥15 events/hour) and obesity (BMI ≥30). "
                "Patients who are CPAP-intolerant or inadequately controlled are key targets. "
                "Key diagnosis anchor: ICD-10 G47.33."
            ),
            "drug_performance": (
                "Lilly: Zepbound (tirzepatide) — first and only FDA-approved pharmacological treatment "
                "for moderate-to-severe OSA in adults with obesity. "
                "SURMOUNT-OSA trial demonstrated significant AHI reduction. "
                "Competitive context: No direct pharmacological competitors currently approved in OSA. "
                "CPAP device manufacturers (ResMed, Philips) represent the incumbent standard of care."
            ),
        },
    },
}
