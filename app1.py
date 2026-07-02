import json
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from excel_export import send_stats_workbook
from replay_parser import ReplayParser
from stats import process_replay_folder


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TANK_DB_FILE = BASE_DIR / "tank_db.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "512"))
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "0") == "1"

app = Flask(__name__, static_folder="static")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

parser = ReplayParser(os.getenv("WOTBREPLAY_INSPECTOR_BIN", "wotbreplay-inspector"))
tank_db = {}

if TANK_DB_FILE.exists():
    with TANK_DB_FILE.open(encoding="utf-8") as tank_file:
        tank_db = {int(key): value for key, value in json.load(tank_file).items()}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    parser_path = parser.path()
    checks = {
        "parser": bool(parser_path),
        "tank_db": bool(tank_db),
    }
    return jsonify({
        "ok": all(checks.values()),
        "checks": checks,
        "parser": parser_path,
        "tank_count": len(tank_db),
        "max_upload_mb": MAX_UPLOAD_MB,
        "public_mode": PUBLIC_MODE,
    })


@app.route("/api/process", methods=["POST"])
def process():
    if PUBLIC_MODE:
        return jsonify({"error": "Folder paths are disabled in public mode. Upload replay files instead."}), 403
    if not parser.available():
        return parser_missing_response()

    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path"}), 400

    return jsonify(process_replay_folder(folder, parser, tank_db))


@app.route("/api/upload", methods=["POST"])
def upload():
    if not parser.available():
        return parser_missing_response()

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="blitz_replays_")
    try:
        saved = save_replay_uploads(files, tmp_dir)
        if saved == 0:
            return jsonify({"error": "No .wotbreplay files found in upload"}), 400
        return jsonify(process_replay_folder(tmp_dir, parser, tank_db))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/api/export", methods=["POST"])
def export():
    data = request.json or {}
    return send_stats_workbook(data.get("our_team", []), data.get("enemy_team", []))


def save_replay_uploads(files, target_dir):
    saved = 0
    for uploaded_file in files:
        if not uploaded_file.filename.endswith(".wotbreplay"):
            continue
        file_name = os.path.basename(uploaded_file.filename)
        uploaded_file.save(os.path.join(target_dir, file_name))
        saved += 1
    return saved


def parser_missing_response():
    return jsonify({"error": "wotbreplay-inspector is not installed or not in PATH"}), 503


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
