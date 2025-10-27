import os
from flask import Flask, request, render_template, send_file, abort, Response, redirect, url_for
from werkzeug.utils import secure_filename, safe_join

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mov", "mkv"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4GB limit (adjust as needed)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page: upload form and list of videos
@app.route("/", methods=["GET"])
def index():
    files = sorted(os.listdir(app.config["UPLOAD_FOLDER"]))
    return render_template("index.html", files=files)

# Upload endpoint
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return redirect(url_for("index"))
    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)
    return redirect(url_for("index"))

# Helper to serve range requests (for seeking)
def file_stream_generator(path, start, length=None, chunk_size=8192):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while True:
            read_size = chunk_size if remaining is None else min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            yield data
            if remaining is not None:
                remaining -= len(data)
                if remaining <= 0:
                    break

# Video streaming endpoint with HTTP Range support
@app.route("/video/<path:filename>")
def video(filename):
    safe_path = safe_join(app.config["UPLOAD_FOLDER"], filename)
    if not safe_path or not os.path.exists(safe_path):
        return abort(404)

    file_size = os.path.getsize(safe_path)
    range_header = request.headers.get("Range", None)

    if range_header:
        # Example Range: bytes=1000- or bytes=1000-2000
        range_value = range_header.strip().lower()
        if not range_value.startswith("bytes="):
            return abort(400)
        ranges = range_value.replace("bytes=", "").split("-")
        try:
            start = int(ranges[0]) if ranges[0] else 0
        except ValueError:
            start = 0
        try:
            end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
        except ValueError:
            end = file_size - 1

        if start >= file_size:
            return abort(416)  # Range Not Satisfiable

        length = end - start + 1
        resp = Response(file_stream_generator(safe_path, start, length), status=206, mimetype="video/mp4")
        resp.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
        resp.headers.add("Accept-Ranges", "bytes")
        resp.headers.add("Content-Length", str(length))
        return resp
    else:
        # No range header — serve whole file (may be heavy)
        return send_file(safe_path, conditional=True, as_attachment=False)

# Simple delete (optional) - careful if deployed publicly; for demo only
@app.route("/delete/<path:filename>", methods=["POST"])
def delete_file(filename):
    safe_path = safe_join(app.config["UPLOAD_FOLDER"], filename)
    if safe_path and os.path.exists(safe_path):
        os.remove(safe_path)
    return redirect(url_for("index"))

if __name__ == "__main__":
    # local dev: port 5000
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
