from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

# In-memory job store: job_id -> {status, log, done}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

DATA_INPUT = Path("data/input")
DATA_OUTPUT = Path("data/output")


def _run_generation(job_id: str) -> None:
    """Run resume generation in a background thread."""
    import subprocess

    with _jobs_lock:
        _jobs[job_id]["log"].append("Starting resume generation...")

    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )

    combined = (result.stdout + ("\n" + result.stderr if result.stderr.strip() else "")).strip()
    lines = [line for line in combined.splitlines() if line.strip()]

    with _jobs_lock:
        _jobs[job_id]["log"].extend(lines)
        if result.returncode == 0:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["log"].append("All done! Resumes emailed successfully.")
        else:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["log"].append("Generation failed. Check the log above for details.")
        _jobs[job_id]["done"] = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    links_raw = request.form.get("links", "").strip()
    if not links_raw:
        return jsonify({"error": "No job links provided."}), 400

    # Sanitise: keep only non-empty lines
    lines = [ln.strip() for ln in links_raw.splitlines() if ln.strip()]
    if not lines:
        return jsonify({"error": "No valid job links found."}), 400

    # Write links to the input file (the only file the pipeline reads from)
    DATA_INPUT.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    (DATA_INPUT / "job_links.txt").write_text("\n".join(lines), encoding="utf-8")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "log": [], "done": False}

    t = threading.Thread(target=_run_generation, args=(job_id,), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
