from flask import Flask, request, jsonify
import subprocess
import tempfile
import os

app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    lang = data.get("lang")
    code = data.get("code")
    
    if lang == "python":
        try:
            result = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=10)
            return jsonify({"stdout": result.stdout, "stderr": result.stderr})
        except Exception as e:
            return jsonify({"error": str(e)})
    
    elif lang == "c":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".c") as f:
            f.write(code.encode())
            cfile = f.name
        exe_file = cfile + ".out"
        try:
            compile_result = subprocess.run(["gcc", cfile, "-o", exe_file], capture_output=True, text=True)
            if compile_result.returncode != 0:
                return jsonify({"stdout": compile_result.stdout, "stderr": compile_result.stderr})
            run_result = subprocess.run([exe_file], capture_output=True, text=True)
            return jsonify({"stdout": run_result.stdout, "stderr": run_result.stderr})
        finally:
            os.remove(cfile)
            if os.path.exists(exe_file):
                os.remove(exe_file)
    
    elif lang == "bash":
        try:
            result = subprocess.run(["bash", "-c", code], capture_output=True, text=True, timeout=10)
            return jsonify({"stdout": result.stdout, "stderr": result.stderr})
        except Exception as e:
            return jsonify({"error": str(e)})
    
    else:
        return jsonify({"error": "Unsupported language"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
