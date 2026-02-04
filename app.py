from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os, zipfile, subprocess, shutil, json, time, io
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- কনফিগারেশন পরিবর্তন (মোবাইলের জন্য উপযোগী) ---
BASE_PATH = os.getcwd() 
UPLOAD_FOLDER = os.path.join(BASE_PATH, "uploads") 
DEFAULT_USER = "admin" 
BASE_DIR = os.path.join(UPLOAD_FOLDER, DEFAULT_USER)

# ডিরেক্টরি নিশ্চিত করা
os.makedirs(BASE_DIR, exist_ok=True)

# প্রসেস স্টোর করার ডিকশনারি
processes = {}

def find_file(root_dir, target_name):
    for root, dirs, files in os.walk(root_dir):
        if target_name in files:
            return os.path.join(root, target_name)
    return None

@app.route("/")
def index():
    apps = []
    if os.path.exists(BASE_DIR):
        for n in os.listdir(BASE_DIR):
            project_path = os.path.join(BASE_DIR, n)
            if os.path.isdir(project_path):
                proc = processes.get((DEFAULT_USER, n))
                running = (proc is not None and proc.poll() is None)
                apps.append({"name": n, "running": running})
    # templates ফোল্ডারে index.html থাকতে হবে
    return render_template("index.html", apps=apps)

@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files: return redirect(request.url)
    file = request.files["file"]
    
    if file and file.filename.endswith(".zip"):
        filename = secure_filename(file.filename)
        name = filename.rsplit('.', 1)[0]
        
        project_path = os.path.join(BASE_DIR, name)
        extract_path = os.path.join(project_path, "extracted")
        
        if os.path.exists(project_path): shutil.rmtree(project_path)
        os.makedirs(extract_path, exist_ok=True)
        
        z_path = os.path.join(project_path, filename)
        file.save(z_path)
        
        with zipfile.ZipFile(z_path, 'r') as z:
            z.extractall(extract_path)
        os.remove(z_path)
        
    return redirect(url_for("index"))

@app.route("/run/<name>")
def run(name):
    name = secure_filename(name)
    project_path = os.path.join(BASE_DIR, name)
    ext = os.path.join(project_path, "extracted")
    
    main_files = ["main.py", "app.py", "bot.py", "index.py"]
    main = next((f for f in main_files if os.path.exists(os.path.join(ext, f))), None)
    
    if main:
        l_path = os.path.join(project_path, "logs.txt")
        with open(l_path, "w", encoding="utf-8") as f:
            f.write(f"--- [SYSTEM] Starting {main} at {time.strftime('%H:%M:%S')} ---\n")
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        log_file = open(l_path, "a", encoding="utf-8")
        
        processes[(DEFAULT_USER, name)] = subprocess.Popen(
            ["python3", "-u", main], 
            cwd=ext, 
            stdout=log_file, 
            stderr=log_file, 
            stdin=subprocess.PIPE, 
            text=True,
            env=env
        )
    return redirect(url_for("index"))

@app.route("/run_termux_cmd", methods=["POST"])
def cmd():
    data = request.json
    p_name = secure_filename(data.get('project'))
    cmd_text = data.get('command')
    
    p = processes.get((DEFAULT_USER, p_name))
    if p and p.poll() is None:
        try:
            p.stdin.write(cmd_text + "\n")
            p.stdin.flush()
            return jsonify({"status": "sent"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "no_process"})

@app.route("/get_log/<name>")
def get_log(name):
    name = secure_filename(name)
    l_path = os.path.join(BASE_DIR, name, "logs.txt")
    
    log_content = ""
    if os.path.exists(l_path):
        with open(l_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            log_content = "".join(lines[-100:]) 
            
    proc = processes.get((DEFAULT_USER, name))
    running = (proc is not None and proc.poll() is None)
    return jsonify({"log": log_content, "status": "RUNNING" if running else "OFFLINE"})

@app.route("/stop/<name>")
def stop(name):
    name = secure_filename(name)
    p = processes.get((DEFAULT_USER, name))
    if p:
        p.terminate()
        del processes[(DEFAULT_USER, name)]
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
