"""
app.py — primerMD (Databricks edition)

Everything the Redshift-era app.py did to hold and protect a live DB
connection — _store_creds/_get_creds/_clear_creds, get_conn, /connect,
/disconnect, /load_session, /validate — is gone. This app never talks to a
database, and has no Microsoft 365 connection either. Two generation modes:

  - /new/generate_files (primary): builds the six scaffold files directly,
    server-side, using only what's typed into the form. No live schema
    resolution or email/Teams search happens here — see file_generator.py
    for exactly what that means for file content.
  - /new/generate_prompt (secondary): the original approach — hands a
    prompt to a Claude.ai session (with Databricks + M365 MCP connected)
    to do live schema discovery and email/Teams search before generating.

Stage 2 (next): /library — upload, browse, and full-text search past
scaffold sets (adds the SQLite-backed piece we scoped separately).
"""

import io
import json
import zipfile

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from domain_context import DOMAIN_CONTEXT
from playbook import PLAYBOOK
from worked_examples import WORKED_EXAMPLES
from prompt_builder import build_response, build_session_log_skeleton
from file_generator import generate_all_files

app = Flask(__name__, static_folder="static", static_url_path="")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


@app.route("/")
@app.route("/new")
def new():
    return send_from_directory(app.static_folder, "new.html")


@app.route("/meta")
def meta():
    """Static page data, served as JSON rather than baked in via server-side templating."""
    return jsonify({
        "domain_context_index": {
            ta: list(indications.keys()) for ta, indications in DOMAIN_CONTEXT.items()
        },
        "playbook": [
            {"id": p["id"], "name": p["name"], "desc": p["desc"]} for p in PLAYBOOK
        ],
        "worked_examples": [
            {"id": p["id"], "name": p["name"], "desc": p["desc"]} for p in WORKED_EXAMPLES
        ],
    })


@app.route("/domain_context", methods=["GET"])
def domain_context():
    """Unchanged from the Redshift-era app — pure lookup, no DB involved."""
    ta = request.args.get("ta", "").strip()
    indication = request.args.get("indication", "").strip()
    empty = {"disease_state": "", "market_context": "", "key_population": "", "drug_performance": ""}
    if not ta or not indication:
        return jsonify(empty)
    return jsonify(DOMAIN_CONTEXT.get(ta, {}).get(indication, empty))


def _validate_required(form):
    required = ["project_name", "product", "catalog"]
    missing = [f for f in required if not form.get(f)]
    return missing


def _build_record(form, files):
    record = build_session_log_skeleton(form, prompt="")
    record["mode"] = "direct_files"
    record["outcome"]["files_generated"] = len(files)
    record["outcome"]["notes"] = "Generated directly by primerMD — no live schema resolution or email/Teams search performed."
    del record["prompt_sent"]
    return record


@app.route("/new/generate_files", methods=["POST"])
def generate_files():
    form = request.get_json(force=True) or {}
    missing = _validate_required(form)
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    files = generate_all_files(form)
    record = _build_record(form, files)
    return jsonify({"files": files, "session_log": json.dumps(record, indent=2)})


@app.route("/new/download", methods=["POST"])
def download_files():
    form = request.get_json(force=True) or {}
    missing = _validate_required(form)
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    files = generate_all_files(form)
    record = _build_record(form, files)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
        # session.json ships in the same zip — same convention as the
        # Redshift-era app, so reloading a project later means "load the
        # session.json out of the zip you already saved", not a separate
        # copy-paste step.
        zf.writestr("session.json", json.dumps(record, indent=2))
    buf.seek(0)
    slug = (form.get("project_name") or "primermd-scaffold").lower().replace(" ", "-")
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"{slug}.zip")


@app.route("/new/generate_prompt", methods=["POST"])
def generate_prompt():
    """The original approach — kept as a secondary option for when live schema
    resolution or an email/Teams search actually needs to happen in a Claude.ai
    session, rather than being left as placeholders in directly-generated files."""
    form = request.get_json(force=True) or {}
    missing = _validate_required(form)
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400
    return jsonify(build_response(form))


@app.route("/status")
def status():
    return jsonify({"ok": True, "mode": "databricks-mcp", "db_connection_held_by_app": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8500, debug=False)
