import io
import time
from collections import defaultdict, deque

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from pypdf import PdfWriter

MAX_FILES = 10
MAX_PAGES = 2000
MERGES_PER_MINUTE = 20

app = Flask(__name__)
# The site allows 20MB in total; the extra covers the upload form's own overhead.
app.config["MAX_CONTENT_LENGTH"] = 21 * 1024 * 1024
CORS(app, origins=["https://snbdev.com", "https://www.snbdev.com"], methods=["POST"])

_hits = defaultdict(deque)


def _client_ip():
    """The caller's address as the edge saw it. CF-Connecting-IP and the first
    X-Forwarded-For entry are whatever the caller typed, so neither is read."""
    if request.headers.get("True-Client-IP"):
        return request.headers["True-Client-IP"].strip()
    forwarded = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    return forwarded[-1] if forwarded else (request.remote_addr or "")


def _too_many():
    now = time.time()
    if len(_hits) > 20000:      # forget idle callers rather than grow forever
        for stale in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            del _hits[stale]
    seen = _hits[_client_ip()]
    while seen and now - seen[0] > 60:
        seen.popleft()
    if len(seen) >= MERGES_PER_MINUTE:
        return True
    seen.append(now)
    return False


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Total size is over the 20MB limit."}), 413


@app.route("/", methods=["GET"])
def home():
    return "PDF Merger API is Running!"


@app.route("/merge", methods=["POST"])
def merge_pdfs():
    if _too_many():
        return jsonify({"error": "Too many merges. Wait a minute and try again."}), 429
    uploaded_files = request.files.getlist("pdfs")
    if len(uploaded_files) < 2:
        return jsonify({"error": "Upload at least two PDFs."}), 400
    if len(uploaded_files) > MAX_FILES:
        return jsonify({"error": f"Upload at most {MAX_FILES} PDFs."}), 400

    # Everything stays in memory and is gone when this request ends: the site
    # promises that no file is kept, so nothing may be written to disk here.
    output = io.BytesIO()
    try:
        with PdfWriter() as writer:
            for file in uploaded_files:
                writer.append(file.stream)
                if len(writer.pages) > MAX_PAGES:
                    return jsonify({"error": f"The merged file would be over {MAX_PAGES} pages."}), 400
            writer.write(output)
    except Exception:  # noqa: BLE001 -- a broken or locked PDF raises many different types
        return jsonify({"error": "One of those files is not a readable PDF, or it is password protected."}), 400

    output.seek(0)
    response = send_file(output, mimetype="application/pdf", as_attachment=True, download_name="merged.pdf")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


if __name__ == "__main__":
    app.run()
