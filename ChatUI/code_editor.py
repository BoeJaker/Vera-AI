from flask import Flask, request, send_file, jsonify, render_template_string
import subprocess
import tempfile
import os
import shutil
import pathlib
import threading
import time
import sys
import serial.tools.list_ports

app = Flask(__name__, static_folder="static", template_folder="static")

# --------------------- Homepage ---------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")

# --------------------- Compile Endpoint ---------------------
@app.route("/compile", methods=["POST"])
def compile_sketch():
    """
    Expects JSON:
      {
        "board": "esp32" | "arduino",
        "fqbn": "<fully-qualified-board-name>",
        "code": "<sketch source>"
      }
    Returns compiled binary or error JSON.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON provided"}), 400

    code = data.get("code", "")
    fqbn = data.get("fqbn")
    if not fqbn:
        return jsonify({"error": "Missing 'fqbn' parameter (fully-qualified board name)."}), 400

    tmpdir = tempfile.mkdtemp(prefix="build_")
    try:
        sketch_dir = os.path.join(tmpdir, "sketch")
        os.makedirs(sketch_dir, exist_ok=True)

        sketch_name = "sketch"
        sketch_file = os.path.join(sketch_dir, f"{sketch_name}.ino")
        with open(sketch_file, "w", encoding="utf-8") as f:
            f.write(code)

        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir, exist_ok=True)

        # Compile using arduino-cli
        cmd = [
            "arduino-cli",
            "compile",
            "--fqbn",
            fqbn,
            "--output-dir",
            out_dir,
            sketch_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if proc.returncode != 0:
            return jsonify({"error": "Compile failed", "stdout": proc.stdout, "stderr": proc.stderr}), 500

        # Return largest binary
        candidates = [os.path.join(root, f)
                      for root, _, files in os.walk(out_dir)
                      for f in files]
        if not candidates:
            return jsonify({"error": "No compiled artifact found"}), 500

        candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
        artifact = candidates[0]

        return send_file(artifact, as_attachment=True, attachment_filename=os.path.basename(artifact))

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

# --------------------- USB Flashing Endpoint ---------------------
@app.route("/flash", methods=["POST"])
def flash_sketch():
    """
    Expects JSON: { "port": "/dev/ttyUSB0" or "COM3", "fqbn": "...", "code": "..." }
    Compiles and flashes the board via arduino-cli.
    """
    data = request.get_json(force=True)
    code = data.get("code", "")
    fqbn = data.get("fqbn")
    port = data.get("port")

    if not code or not fqbn or not port:
        return jsonify({"error": "Missing code, fqbn, or port"}), 400

    tmpdir = tempfile.mkdtemp(prefix="flash_")
    try:
        sketch_dir = os.path.join(tmpdir, "sketch")
        os.makedirs(sketch_dir, exist_ok=True)
        sketch_file = os.path.join(sketch_dir, "sketch.ino")
        with open(sketch_file, "w") as f:
            f.write(code)

        cmd = [
            "arduino-cli",
            "upload",
            "-p", port,
            "--fqbn", fqbn,
            sketch_dir
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            return jsonify({"error": "Flash failed", "stdout": proc.stdout, "stderr": proc.stderr}), 500

        return jsonify({"status": "ok", "stdout": proc.stdout})

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

# --------------------- List Connected Boards ---------------------
@app.route("/ports", methods=["GET"])
def list_ports():
    """
    Returns a JSON array of available serial ports.
    """
    ports = []
    for p in serial.tools.list_ports.comports():
        ports.append({"device": p.device, "description": p.description})
    return jsonify(ports)

# --------------------- Serial Monitor ---------------------
# Optional: You can run a separate WebSocket server or long-polling for live serial logs.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
