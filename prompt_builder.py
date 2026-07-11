"""
prompt_builder.py — primerMD (Databricks edition)

This module replaces the eight `_gen_*` functions from the Redshift-era
app.py. Those functions rendered final markdown files server-side, using a
live DB connection this app held itself. That connection doesn't exist here
— Databricks access happens inside the Claude.ai session via MCP. So instead
of generating files, this module generates the *prompt* that tells Claude.ai
what to generate, using its own live MCP tools to fill in what the old code
used to get from psycopg2.

The file-format specs below (section headers, structure) are carried over
directly from the old _gen_claude_md / _gen_examples_md / _gen_kpi_definitions
/ _gen_schema_reference / _gen_styling_guide / _gen_stakeholder_notes
functions, so the six output files keep the same shape the team is already
used to reading.
"""

from datetime import datetime, timezone
import json
import re

from domain_context import DOMAIN_CONTEXT
from playbook import get_patterns, PLAYBOOK
from worked_examples import WORKED_EXAMPLES
from examples_library import EXAMPLES_LIBRARY_MD


def _domain_blurb(ta: str, indication: str) -> str:
    content = DOMAIN_CONTEXT.get(ta, {}).get(indication)
    if not content:
        return ""
    return (
        f"**Disease state:** {content['disease_state']}\n\n"
        f"**Market context:** {content['market_context']}\n\n"
        f"**Key population:** {content['key_population']}\n\n"
        f"**Drug performance:** {content['drug_performance']}\n"
    )


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _render_kpi_block(kpi: dict, playbook_by_id: dict) -> str:
    """
    Renders one structured KPI entry into the prompt. Mirrors the field set
    from the Redshift-era KPI step (name, definition, grain, time window,
    caveats/pattern notes, SQL logic source) — this is the "KPI Layer 2
    input" that was a pending item on the old primerMD backlog.
    """
    name = (kpi.get("name") or "").strip() or "Unnamed KPI"
    definition = (kpi.get("definition") or "").strip()
    grain = kpi.get("grain") or ""
    if grain == "Custom":
        grain = (kpi.get("grain_custom") or "").strip() or "Custom (unspecified)"
    time_window = kpi.get("time_window") or ""
    if time_window == "Custom window":
        time_window = (kpi.get("time_window_custom") or "").strip() or "Custom window (unspecified)"
    caveats = (kpi.get("caveats") or "").strip()

    mode = kpi.get("sql_source_mode") or ""
    sql_block = ""
    if mode == "playbook":
        pid = kpi.get("sql_playbook_entry") or ""
        pattern = playbook_by_id.get(pid)
        is_redshift = bool(kpi.get("sql_redshift_legacy"))
        mappings = kpi.get("table_mappings") or []
        if pattern:
            sql_block = (
                f"**SQL logic:** use the **{pattern['name']}** pattern from the playbook "
                f"(see the resolved pattern reference below) — resolve its placeholders "
                f"against this KPI's actual tables/columns, not a different KPI's."
            )
            if is_redshift:
                is_worked_example = pid.startswith("we_")
                real_mappings = [m for m in mappings if (m.get("redshift") or "").strip()]
                map_lines = "\n".join(
                    f"  - `{m.get('redshift','')}` → `{m.get('databricks','')}`" for m in real_mappings
                ) or "  - (no tables mapped yet — ask me for the real Redshift table(s) this pattern replaces)"
                if is_worked_example:
                    note = (
                        "\n\nThis worked example is carried over from the Redshift-era version of primerMD — "
                        "its table references are real (not abstract placeholders), but the `<catalog>` prefix "
                        "still needs resolving against the live Unity Catalog metastore. Use the mapping below "
                        "to confirm each table, not just the catalog name:\n\n"
                    )
                else:
                    note = (
                        "\n\nThis playbook pattern is carried over from the Redshift-era version of primerMD — "
                        "treat its placeholder table refs (`<catalog>.<schema>.<table>`) as needing confirmation "
                        "against the mapping below, not as already-resolved Databricks names:\n\n"
                    )
                sql_block += note + map_lines
        else:
            sql_block = "**SQL logic:** playbook pattern selected but not resolved — ask me which pattern applies."
    elif mode == "paste":
        pasted = (kpi.get("sql_pasted") or "").strip()
        is_redshift = bool(kpi.get("sql_redshift_legacy"))
        mappings = kpi.get("table_mappings") or []
        if pasted:
            if is_redshift:
                map_lines = "\n".join(
                    f"  - `{m.get('redshift','')}` → `{m.get('databricks','')}`"
                    for m in mappings if (m.get("redshift") or "").strip()
                ) or "  - (no tables detected in the pasted SQL yet)"
                sql_block = (
                    "**SQL logic:** existing **Redshift** SQL provided below — this still needs re-synthesis "
                    "for Databricks/Spark SQL (three-part namespace, no WLM-driven temp tables needed, "
                    "QUALIFY where it removes a subquery). Use the table mapping below as the starting point "
                    "for the rewrite, and confirm each target table/column against the live schema before "
                    "finalizing the EXAMPLES.md stub:\n\n"
                    f"{map_lines}\n\n"
                    f"```sql\n{pasted}\n```"
                )
            else:
                sql_block = (
                    "**SQL logic:** existing SQL provided below — verify it against the live schema, "
                    "translate to Databricks SQL if it isn't already (three-part namespace, no WLM-driven "
                    "temp tables needed), and use it as the EXAMPLES.md stub for this KPI.\n\n"
                    f"```sql\n{pasted}\n```"
                )
        else:
            sql_block = "**SQL logic:** \"paste SQL\" selected but nothing was pasted — ask me for it."
    elif mode == "describe":
        rules = kpi.get("sql_rules") or {}
        columns = (rules.get("columns") or "").strip()
        business_rules = (rules.get("business_rules") or "").strip()
        exclusions = (rules.get("exclusions") or "").strip()
        lines = ["**SQL logic:** build from the described rules below — do not invent column names not listed here; confirm them against live schema discovery first."]
        if columns:
            lines.append(f"- Columns used: {columns}")
        if business_rules:
            lines.append(f"- Business rules: {business_rules}")
        if exclusions:
            lines.append(f"- Exclusions & edge cases: {exclusions}")
        sql_block = "\n".join(lines)
    else:
        sql_block = "**SQL logic:** not specified yet — ask me before writing SQL for this KPI, or suggest a playbook pattern once you see the schema."

    parts = [f"### {name}"]
    if definition:
        parts.append(f"**Definition:** {definition}")
    parts.append(f"**Grain:** {grain or '[ask me — one row per what?]'}")
    parts.append(f"**Time window:** {time_window or '[ask me — lookback or accumulation logic]'}")
    if caveats:
        parts.append(f"**Keep in mind:** {caveats}")
    parts.append(sql_block)
    return "\n\n".join(parts)


def gen_suggested_prompts_md(form: dict) -> str:
    """
    Directional example prompts for actually working the project once the
    scaffold exists — distinct from build_prompt() above, which is the
    one-time meta-prompt that *builds* the scaffold itself. This is meant to
    ship alongside the scaffold either way: as prompt_helper.md in the
    direct-file-generation path, and as a companion block in the
    generate-a-prompt path (see build_response()).
    """
    project_name = form.get("project_name", "Untitled project").strip() or "Untitled project"
    kpis = [k for k in form.get("kpis", []) if (k.get("name") or "").strip()]
    visual_output = bool(form.get("visual_output"))
    playbook_by_id = {p["id"]: p for p in PLAYBOOK + WORKED_EXAMPLES}

    es = form.get("email_search", {}) or {}
    has_email_search = bool(
        (es.get("subject_keywords") or "").strip()
        or (es.get("participants") or "").strip()
        or (es.get("keywords") or "").strip()
    )

    lines = [
        f"# prompt_helper.md — {project_name}",
        "",
        "Directional starting points, not scripts — these are suggestions for what to type into Claude Code or a "
        "Claude.ai session once the scaffold files are in place. Adapt freely, and swap in real table/column names "
        "as you confirm them against the live schema.",
        "",
        "## Orient Claude first",
        "```",
        "Read CLAUDE.md, kpi_definitions.md, and EXAMPLES.md, then summarize back what you understand about this "
        "project and its KPIs before we start — flag anything that looks incomplete or ambiguous.",
        "```",
        "",
    ]

    if kpis:
        lines.append("## Per-KPI starting prompts")
        lines.append("")
        for k in kpis:
            name = (k.get("name") or "Unnamed KPI").strip()
            mode = k.get("sql_source_mode") or ""
            is_redshift = bool(k.get("sql_redshift_legacy"))
            if mode == "paste" and is_redshift:
                p = (
                    f"Rewrite the Redshift SQL I pasted for {name} into Databricks/Spark SQL — use the table "
                    f"mapping in kpi_definitions.md as your starting point, and confirm every table/column against "
                    f"the live schema before finalizing its EXAMPLES.md stub."
                )
            elif mode == "playbook" and is_redshift:
                pid = k.get("sql_playbook_entry") or ""
                pattern_name = playbook_by_id.get(pid, {}).get("name", "the selected pattern")
                p = (
                    f"Build {name} using the {pattern_name} pattern from EXAMPLES.md — resolve its placeholders "
                    f"against the real schema, and confirm the Redshift-to-Databricks table mapping in "
                    f"kpi_definitions.md before running anything."
                )
            elif mode == "playbook":
                pid = k.get("sql_playbook_entry") or ""
                pattern_name = playbook_by_id.get(pid, {}).get("name", "the selected pattern")
                p = (
                    f"Build {name} using the {pattern_name} pattern from EXAMPLES.md — resolve its placeholders "
                    f"against the real schema before running anything."
                )
            elif mode == "paste":
                p = (
                    f"Verify the SQL I pasted for {name} against the live schema, then use it as the working "
                    f"version for this KPI."
                )
            elif mode == "describe":
                p = (
                    f"Using the business rules described for {name} in kpi_definitions.md, write the Databricks "
                    f"SQL — ask me first if any column name isn't already confirmed against the live schema."
                )
            else:
                p = f"Build the SQL for {name} per kpi_definitions.md, at the grain and time window specified there."
            lines.append(f"**{name}**")
            lines.append("```")
            lines.append(p)
            lines.append("```")
            lines.append("")

        if len(kpis) > 1:
            names = ", ".join((k.get("name") or "Unnamed KPI").strip() for k in kpis)
            lines.append("## Cross-KPI check")
            lines.append("```")
            lines.append(
                f"Compare {names} — confirm they share a consistent grain and time-window convention, and flag "
                f"anything inconsistent before we build a combined view."
            )
            lines.append("```")
            lines.append("")
    else:
        lines.append("_(No KPIs defined yet — add at least one on the KPIs tab to get KPI-specific prompt suggestions.)_")
        lines.append("")

    lines.append("## Validate before trusting the output")
    lines.append("```")
    lines.append(
        "Before finalizing any KPI SQL, run a fan-out check (COUNT(*) vs. COUNT(DISTINCT id)) on every join, and "
        "flag anything that doesn't match 1:1 expectations."
    )
    lines.append("```")
    lines.append("")

    if visual_output:
        kpi_names = ", ".join((k.get("name") or "Unnamed KPI").strip() for k in kpis) if kpis else "the KPIs in scope"
        lines.append("## Build the visual output")
        lines.append("```")
        lines.append(
            f"Using styling_guide.md for Lilly brand conventions, build a dashboard for {kpi_names}. Lead with the "
            f"headline metric per KPI, and label the most recent period if it's subject to data lag."
        )
        lines.append("```")
        lines.append("")

    if has_email_search:
        lines.append("## Pull stakeholder context")
        lines.append("```")
        lines.append(
            "Search Outlook/Teams per the criteria in stakeholder_notes.md's Outlook/Teams context search section, "
            "then summarize anything relevant back to me — decisions, constraints, or prior analysis references — "
            "before we finalize anything."
        )
        lines.append("```")
        lines.append("")

    lines.append("## When something feels off")
    lines.append("```")
    lines.append(
        "Before you write any SQL, tell me which tables and columns you're about to assume exist that haven't yet "
        "been confirmed against the live schema."
    )
    lines.append("```")

    return "\n".join(lines)


def build_prompt(form: dict) -> str:
    """
    form keys expected:
      project_name, product, therapeutic_area, indication, tracker_type,
      catalog, schemas (list[str]), table_hints (str, freeform),
      kpis (list[dict] — see _render_kpi_block for shape; playbook-mode KPIs
      contribute their pattern automatically, no separate pattern_ids list),
      email_search (dict — subject_keywords, participants, keywords, scope, recency_days)
    """
    project_name = form.get("project_name", "Untitled project").strip()
    product = form.get("product", "").strip()
    ta = form.get("therapeutic_area", "").strip()
    indication = form.get("indication", "").strip()
    tracker_type = form.get("tracker_type", "").strip()
    description = form.get("description", "").strip()
    catalog = form.get("catalog", "").strip()
    schemas = form.get("schemas", [])
    table_hints = form.get("table_hints", "").strip()
    kpis = form.get("kpis", [])
    pattern_ids = list(form.get("pattern_ids", []))
    vocab = form.get("vocab", [])

    domain_blurb = _domain_blurb(ta, indication)
    schema_list = ", ".join(f"{catalog}.{s}" for s in schemas) if schemas else f"{catalog}.<schema>"

    all_patterns = PLAYBOOK + WORKED_EXAMPLES
    playbook_by_id = {p["id"]: p for p in all_patterns}

    # Union: manually checked patterns + any pattern a KPI points at directly,
    # so the reference SQL for a KPI-selected pattern always shows up below
    # even if the user forgot to also tick it in the pattern picker.
    for kpi in kpis:
        if kpi.get("sql_source_mode") == "playbook" and kpi.get("sql_playbook_entry"):
            pid = kpi["sql_playbook_entry"]
            if pid not in pattern_ids:
                pattern_ids.append(pid)

    patterns = get_patterns(pattern_ids)
    pattern_block = ""
    if patterns:
        pattern_block = "\n\n".join(
            f"### {p['name']}\n{p['sql']}" for p in patterns
        )

    kpi_block = ""
    if kpis:
        kpi_block = "\n\n".join(_render_kpi_block(k, playbook_by_id) for k in kpis)

    vocab_block = ""
    active_vocab = [v for v in vocab if (v.get("term") or "").strip()]
    if active_vocab:
        vocab_block = "\n".join(
            f"- **{v.get('term','').strip()}**"
            + (f" (a.k.a. {v.get('alias','').strip()})" if (v.get('alias') or "").strip() else "")
            + f": {v.get('definition','').strip() or '[not described]'}"
            for v in active_vocab
        )

    email_search = form.get("email_search", {}) or {}
    subject_kw = (email_search.get("subject_keywords") or "").strip()
    participants = (email_search.get("participants") or "").strip()
    search_kw = (email_search.get("keywords") or "").strip()
    scope = (email_search.get("scope") or "full_chain").strip()
    recency_days = (email_search.get("recency_days") or "").strip()
    has_email_search = bool(subject_kw or participants or search_kw)

    email_search_block = ""
    if has_email_search:
        criteria = []
        if subject_kw:
            criteria.append(f"- Subject contains: {subject_kw}")
        if participants:
            criteria.append(f"- From / participants: {participants}")
        if search_kw:
            criteria.append(f"- Keywords: {search_kw}")
        criteria.append(
            "- Scope: "
            + ("only the most recent message per matching subject/thread"
               if scope == "most_recent" else "the full mail chain — read every message in matching threads")
        )
        if recency_days:
            criteria.append(f"- Recency: only messages from the last {recency_days} days")
        email_search_block = (
            "## Step 4 — Pull additional context from Outlook / Teams\n"
            "Use the Microsoft 365 tools (`outlook_email_search` for mail, `chat_message_search` for Teams) "
            "to pull relevant context before finalizing the scaffold:\n\n"
            + "\n".join(criteria)
            + "\n\nSummarize anything relevant you find — decisions, constraints, prior analysis references — "
              "into the Additional Information section below. Don't fabricate results if the search comes back empty; "
              "just note that nothing matched."
        )

    prompt = f"""I'm starting a new BI&A project on Databricks and want you to build me a working-context scaffold before we do anything else. Databricks MCP is already connected in this session — use it to do real schema discovery rather than asking me to describe tables from memory.

## Project
- **Name:** {project_name}
- **Product:** {product}
- **Therapeutic area / indication:** {ta} / {indication}
- **Tracker type:** {tracker_type}
- **Description:** {description if description else "[not provided — ask me for one or two sentences before writing the Role & project paragraph]"}

## Domain context
{domain_blurb if domain_blurb else "(No pre-baked domain context on file for this TA/indication — ask me for a short brief before proceeding.)"}

## Step 1 — Live schema discovery
Using the Databricks MCP tools (`list_tables`, `describe_table`, `execute_sql` against `system.information_schema` as needed):
1. Confirm access to catalog `{catalog}`, schema(s): {schema_list}.
2. Identify the tables relevant to this project. My starting hints: {table_hints if table_hints else "(none provided — infer from the project description and confirm with me before proceeding)"}.
3. For each relevant table, pull column names, types, and — where knowable — a sense of grain (one row per what?).
4. Flag anything that looks like a late-binding view, a managed vs. external table distinction, or a naming convention I should know about.

Do not guess at column names. If something is ambiguous, run a quick `SELECT * LIMIT 5` or check `information_schema.columns` rather than assuming.

## Step 2 — KPIs in scope
Each KPI below has its own grain, time window, and SQL logic source. Treat each one as a separate
section in kpi_definitions.md and its own stub in EXAMPLES.md — don't collapse them into one generic block.

{kpi_block if kpi_block else "(No KPIs provided yet — ask me to define at least one before generating kpi_definitions.md.)"}

## Step 3 — Relevant SQL patterns for this project
The patterns below are from the BI&A Databricks SQL playbook. Resolve the `<id_col>`, `<date_col>`, `<val_col>`, `<status_col>`, and `<catalog>.<schema>.<table>` placeholders against the real schema you discovered in Step 1 before putting anything into EXAMPLES.md.

{pattern_block if pattern_block else "(No patterns pre-selected — pull from the standard 12-pattern playbook as relevant once you see the schema.)"}

{email_search_block}

## Step {5 if has_email_search else 4} — Generate the scaffold
Produce these six files, matching the structure below:

**CLAUDE.md**
- Role & project — one paragraph orienting a fresh Claude Code/Claude.ai session on what this project is and who it's for. Use the description above verbatim if provided; otherwise write one from the project/product/TA/indication.
- Tools & stack — Databricks (Unity Catalog, catalog `{catalog}`), SQL dialect notes (Spark SQL, not Redshift — no WLM abort risk, so CTEs are fine; QUALIFY is available; three-part namespace required)
- Data environment — platform, tables in scope (from Step 1), any schema gotchas found
- SQL conventions (Lilly BI&A standard) — standard temp view pattern, when to materialize a real Delta table instead
- KPIs in scope — a short bullet list of the KPI names from Step 2
- Terms I use -> what I mean — a business-vocabulary table from the entries below{" (none provided — omit or leave a placeholder row)" if not active_vocab else ""}

{vocab_block if vocab_block else ""}
- Relevant patterns for this project — list the patterns from Step 3
- What to avoid
- How I want Claude to respond (SQL style, standard query format, problem-solving approach)
- File inventory

**EXAMPLES.md** — the Step 3 patterns with placeholders resolved to real column/table names, each with a "when to use" note

**kpi_definitions.md** — one section per KPI, in the same structure I gave you above: name, definition, grain, time window, keep-in-mind caveats, and the resolved SQL logic (from playbook / pasted / described rules)

**schema_reference.md** — curated table-by-table reference: what each table is, its grain, key join columns, and anything about it that isn't obvious from information_schema alone (business meaning, known gotchas)

**styling_guide.md** — Lilly brand colors, chart conventions, typography, layout, accessibility (use the standard BI&A styling guide unless I say otherwise)

**stakeholder_notes.md** (Additional Information) — Owner/DRI; anything surfaced from the Outlook/Teams search in Step {4 if has_email_search else "N/A"}; communication preferences; key decisions & open items; prior analyses to reference

**prompt_helper.md** — a short, directional set of example prompts for actually working this project once the scaffold above exists: one to orient a fresh session (read the other files, summarize back), one per KPI in Step 2 tailored to its SQL logic source (playbook/pasted/described, and whether it needs Redshift-to-Databricks re-synthesis), a fan-out/validation check, and — if relevant — one for building the visual output and one for the Outlook/Teams search. These are suggestions to adapt, not a rigid script.

**examples_library.md** — copy this verbatim, unedited: 19 real worked BI&A query patterns (TUA, SoM waterfall, dosing/mode-of-administration classification, rolling NBRx, HCP segmentation, cross-TA overlap, and more) in Databricks/Spark SQL, ported from the team's Redshift-era reference library. It's static and not project-specific — don't regenerate or summarize it, just include the file as-is so it ships alongside the other six.

Ask me anything you need to fill gaps before generating — don't fabricate schema details, table names, or KPI logic you weren't given or couldn't confirm live.

---

The full content of **examples_library.md** is below — it's static and not project-specific.
Write it out to that filename exactly as given, verbatim, with no summarizing, editing, or
re-translation. It already resolves the Redshift-to-Databricks dialect conversion; the only
thing left unresolved is the `<catalog>` placeholder, which should stay as-is here (it gets
resolved per-table in schema_reference.md and kpi_definitions.md instead, not in this file).

{EXAMPLES_LIBRARY_MD}
"""
    return prompt.strip()


def build_session_log_skeleton(form: dict, prompt: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    project_name = form.get("project_name", "untitled")
    slug = _slugify(project_name)
    return {
        "session_id": f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
        "product": form.get("product", ""),
        "tracker_name": project_name,
        "therapeutic_area": form.get("therapeutic_area", ""),
        "indication": form.get("indication", ""),
        "created_at": now,
        "prompt_sent": prompt,
        "mcp_context": {
            "catalog": form.get("catalog", ""),
            "schemas": form.get("schemas", []),
        },
        # Full original form — this is what makes the skeleton reloadable.
        # Without it, revising a project meant retyping everything; with it,
        # "load session JSON" on the form can hydrate every field exactly
        # as it was, so you can tweak one thing and regenerate rather than
        # starting over.
        "form_inputs": form,
        "transcript": [],
        "outcome": {
            "scaffold_set_id": None,
            "files_generated": 0,
            "notes": "",
        },
    }


def build_response(form: dict) -> dict:
    prompt = build_prompt(form)
    log_skeleton = build_session_log_skeleton(form, prompt)
    return {
        "prompt": prompt,
        "session_log_skeleton": json.dumps(log_skeleton, indent=2),
        "suggested_prompts": gen_suggested_prompts_md(form),
    }
