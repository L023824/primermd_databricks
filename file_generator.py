"""
file_generator.py — primerMD (Databricks edition), direct-generation mode

Generates the six scaffold files directly, server-side, with no live
connection to anything. This is a deliberate return to how the very first
File Primer worked (static templating), with one difference: the original
Redshift app had its own DB connection and could resolve real column names
into the files it wrote. This app was built without holding any credentials
at all — so direct generation here means placeholders stay placeholders
wherever the schema hasn't been typed in by hand (via a KPI's "describe
rules" mode, or table hints). Anything that would have needed a live
connection (real column resolution, an Outlook/Teams search) is written
into the files as an explicit to-do for whoever opens the project next in
Claude Code or Claude.ai with MCP — not silently faked.
"""

from datetime import datetime, timezone

from domain_context import DOMAIN_CONTEXT
from playbook import PLAYBOOK, get_patterns
from prompt_builder import _domain_blurb, _render_kpi_block, _slugify


STYLING_GUIDE_MD = """# Styling guide — Lilly BI&A

## Lilly brand colors
- Primary red: `#D52B1E` (brand accent, primary actions, key data series)
- Red dark (hover/emphasis): `#A01F14`
- Grays: `#F8F8F8` (bg) / `#E0E0E0` (borders) / `#5E5E5E` (secondary text) / `#1E1E1E` (primary text)
- Status colors: green `#1B7B3A` (positive/on-track), amber `#8A5700` (caution/at-risk), blue `#0047BB` (informational)

## Chart conventions
- Lead with the brand red for the focal series (e.g. Jaypirca, Ebglyss); competitor/market series in grays
- Status colors (green/amber/red) reserved for performance-against-target signals only — don't reuse them decoratively
- Always label the most recent period if it's subject to data lag/truncation

## Typography
- Sans-serif throughout (Helvetica Neue / Arial fallback) — no serif in dashboards
- Numbers: tabular/monospace alignment in tables so magnitudes are easy to compare down a column

## Layout
- Lead with the headline metric, then supporting detail — don't bury the answer under methodology
- Collapsible/secondary sections for diagnostic detail (e.g. market penetration, audit flags) so the primary view stays scannable

## Accessibility
- Never rely on color alone to convey status — pair with a label or icon
- Maintain WCAG AA contrast for all text on colored backgrounds
"""


def _tables_in_scope_block(form: dict) -> str:
    catalog = form.get("catalog", "").strip()
    schemas = form.get("schemas", [])
    table_hints = form.get("table_hints", "").strip()
    schema_list = ", ".join(f"{catalog}.{s}" for s in schemas) if schemas else catalog or "[catalog not specified]"
    lines = [f"- Catalog / schema(s): `{schema_list}`"]
    if table_hints:
        for t in [t.strip() for t in table_hints.replace("\n", ",").split(",") if t.strip()]:
            lines.append(f"- `{t}` — [confirm grain and columns against live schema before use]")
    else:
        lines.append("- No specific tables named yet — confirm candidates against live schema before use.")
    return "\n".join(lines)


def gen_claude_md(form: dict, patterns: list[dict]) -> str:
    project_name = form.get("project_name", "Untitled project")
    product = form.get("product", "")
    ta = form.get("therapeutic_area", "")
    indication = form.get("indication", "")
    catalog = form.get("catalog", "")
    visual_output = bool(form.get("visual_output"))
    kpis = form.get("kpis", [])
    description = form.get("description", "").strip()

    kpi_rows = "\n".join(f"- {k.get('name','[unnamed]')}" for k in kpis if (k.get("name") or "").strip()) or "_(no KPIs defined yet)_"

    vocab = form.get("vocab", [])
    vocab_rows = "\n".join(
        f"| {v.get('term','').strip() or '[unnamed]'} | {v.get('alias','').strip() or '—'} | {v.get('definition','').strip() or '[not described]'} |"
        for v in vocab if (v.get("term") or "").strip()
    ) or "| _(no vocabulary entries yet)_ | | |"

    pattern_names = ", ".join(p["name"] for p in patterns) if patterns else "none selected yet"

    files_list = ["CLAUDE.md", "EXAMPLES.md", "kpi_definitions.md", "schema_reference.md", "stakeholder_notes.md"]
    if visual_output:
        files_list.insert(4, "styling_guide.md")

    domain_blurb = _domain_blurb(ta, indication)
    domain_section = domain_blurb if domain_blurb else "No pre-baked domain context on file for this TA/indication."

    return f"""# {project_name} — Claude context

## Role & project
{description if description else f'This project supports {product or "[product]"} ({ta or "[TA]"} / {indication or "[indication]"}) BI&A analytics on Databricks.'}
Generated directly by primerMD — no live schema discovery has happened yet. Treat table/column names
below as starting hints, not confirmed fact, until checked against the live catalog.

## Domain context
{domain_section}

## Tools & stack
- Platform: Databricks (Unity Catalog), catalog `{catalog or "[not specified]"}`
- SQL dialect: Spark SQL, not Redshift — three-part namespace (`catalog.schema.table`) required.
  No WLM query-abort risk, so CTEs are fine where Redshift needed persistent temp tables.
  `QUALIFY` is available and preferred over a wrapping subquery for rank-then-filter patterns.

## Data environment
### Tables in scope
{_tables_in_scope_block(form)}

> These were not validated against a live connection when this file was generated. Before writing
> any SQL against them, confirm table access and real column names — via Databricks MCP in a
> Claude.ai session, or `describe_table`/`information_schema` if you're in Claude Code with a
> live connection.

## SQL conventions (Lilly BI&A standard)
- Prefer `CREATE OR REPLACE TEMP VIEW` for intermediate steps; materialize a real Delta table only
  for something expensive that's reused across multiple downstream queries.
- Use `QUALIFY` to collapse rank-then-filter idioms instead of a wrapping subquery.
- Always run a fan-out check (`COUNT(*)` vs `COUNT(DISTINCT id)`) after any join.

## KPIs in scope
{kpi_rows}

## Terms I use → what I mean
| Term | Alias | Definition / Convention |
|------|-------|--------------------------|
{vocab_rows}

## Relevant patterns for this project
{pattern_names}

## What to avoid
- Don't invent column names that weren't confirmed live or typed in by hand.
- Don't report the most recent month as complete without a window-truncation check.
- Don't collapse multiple KPIs into one generic query — each has its own grain/time window/logic.

## How I want Claude to respond
- Ask before guessing at schema details this file doesn't cover.
- Show the SQL, then a one-line explanation of what it does — not the reverse.

## File inventory
{chr(10).join(f"- `{f}`" for f in files_list)}
"""


def gen_examples_md(form: dict, patterns: list[dict]) -> str:
    project_name = form.get("project_name", "Untitled project")
    if not patterns:
        return f"""# EXAMPLES.md — {project_name}

No SQL patterns were selected when this file was generated. Pull from the BI&A Databricks
playbook (12 patterns: deduplication, date spine, rolling window, YoY, cohort, funnel,
priority waterfall, cumulative ever-flag, inter-fill gap, window truncation audit, full outer
join actuals-vs-goals, top-N ranking) once the schema is known.
"""
    index = "\n".join(f"- [{p['name']}](#{_slugify(p['name'])})" for p in patterns)
    blocks = "\n\n".join(f"## {p['name']} {{#{_slugify(p['name'])}}}\n{p['sql']}" for p in patterns)
    return f"""# EXAMPLES.md — {project_name}

Placeholders (`<id_col>`, `<date_col>`, `<catalog>.<schema>.<table>`, etc.) below are not yet
resolved to real column names — this file was generated without a live schema connection.
Resolve them against the actual tables before running anything.

## Pattern index
{index}

{blocks}
"""


def gen_kpi_definitions_md(form: dict, playbook_by_id: dict) -> str:
    project_name = form.get("project_name", "Untitled project")
    kpis = form.get("kpis", [])
    if not kpis:
        return f"# kpi_definitions.md — {project_name}\n\nNo KPIs defined yet.\n"
    blocks = "\n\n".join(_render_kpi_block(k, playbook_by_id) for k in kpis)
    return f"# kpi_definitions.md — {project_name}\n\n{blocks}\n"


def gen_schema_reference_md(form: dict) -> str:
    project_name = form.get("project_name", "Untitled project")
    return f"""# schema_reference.md — {project_name}

This file was generated without a live Databricks connection, so it's a starting point, not a
validated reference. Table-level business meaning, join keys, and gotchas below are placeholders
until confirmed.

{_tables_in_scope_block(form)}

## To do before relying on this file
- Confirm each table's grain (one row per what?)
- Confirm join keys between tables
- Note any late-binding views, managed vs. external table distinctions, or naming quirks
- Update this file once confirmed — via Databricks MCP in Claude.ai, or live in Claude Code
"""


def gen_additional_info_md(form: dict) -> str:
    project_name = form.get("project_name", "Untitled project")
    es = form.get("email_search", {}) or {}
    subject_kw = (es.get("subject_keywords") or "").strip()
    participants = (es.get("participants") or "").strip()
    keywords = (es.get("keywords") or "").strip()
    scope = (es.get("scope") or "full_chain").strip()
    recency_days = (es.get("recency_days") or "").strip()

    email_section = "Not requested."
    if subject_kw or participants or keywords:
        criteria = []
        if subject_kw:
            criteria.append(f"- Subject contains: {subject_kw}")
        if participants:
            criteria.append(f"- From / participants: {participants}")
        if keywords:
            criteria.append(f"- Keywords: {keywords}")
        criteria.append(
            "- Scope: "
            + ("only the most recent message per matching subject/thread"
               if scope == "most_recent" else "the full mail chain — every message in matching threads")
        )
        if recency_days:
            criteria.append(f"- Recency: only messages from the last {recency_days} days")
        email_section = (
            "Not yet run — this app has no live Outlook/Teams connection. To run this search, open "
            "a Claude.ai session with the Microsoft 365 connector on and ask it to search using:\n\n"
            + "\n".join(criteria)
        )

    return f"""# stakeholder_notes.md (Additional Information) — {project_name}

## Owner / DRI
[not specified]

## Outlook / Teams context search
{email_section}

## Communication preferences
[not specified]

## Key decisions & open items
| Item | Status | Owner | Date |
|------|--------|-------|------|
| *[decision or open question]* | Open | — | {datetime.now(timezone.utc).strftime('%Y-%m-%d')} |

## Prior analyses to reference
- *[Link or describe any predecessor analysis this builds on]*
"""


def generate_all_files(form: dict) -> dict:
    playbook_by_id = {p["id"]: p for p in PLAYBOOK}
    pattern_ids = list(form.get("pattern_ids", []))
    for kpi in form.get("kpis", []):
        if kpi.get("sql_source_mode") == "playbook" and kpi.get("sql_playbook_entry"):
            pid = kpi["sql_playbook_entry"]
            if pid not in pattern_ids:
                pattern_ids.append(pid)
    patterns = get_patterns(pattern_ids)

    files = {
        "CLAUDE.md": gen_claude_md(form, patterns),
        "EXAMPLES.md": gen_examples_md(form, patterns),
        "kpi_definitions.md": gen_kpi_definitions_md(form, playbook_by_id),
        "schema_reference.md": gen_schema_reference_md(form),
        "stakeholder_notes.md": gen_additional_info_md(form),
    }
    if form.get("visual_output"):
        files["styling_guide.md"] = STYLING_GUIDE_MD
    return files
