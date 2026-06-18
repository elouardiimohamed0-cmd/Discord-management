import os
import subprocess
import sys
import threading
import socketserver
from http.server import BaseHTTPRequestHandler

TEMPLATES_DIR = "assets/templates"

# ─── HEALTH CHECK SERVER ───
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        pass  # Silence health check logs

def _start_health_server():
    try:
        with socketserver.TCPServer(("0.0.0.0", 8000), HealthHandler) as httpd:
            print("[HEALTH] Server listening on port 8000")
            httpd.serve_forever()
    except Exception as e:
        print(f"[HEALTH] Server error: {e}")

threading.Thread(target=_start_health_server, daemon=True).start()

# ─── BACKGROUND TEMPLATE GENERATION ───
def _generate_templates_async():
    required = [
        "mvp.png", "fraud.png", "ghost.png", "carry.png",
        "court.png", "playmaker.png", "sniper.png", "ball_loser.png"
    ]
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    missing = [f for f in required if not os.path.exists(os.path.join(TEMPLATES_DIR, f))]
    
    if not missing:
        print("[BOOT] ✅ All templates present.")
        return
    
    print(f"[BOOT] Missing templates: {missing}")
    print("[BOOT] Starting BACKGROUND template generation...")
    
    try:
        result = subprocess.run(
            [sys.executable, "generate_templates.py"],
            capture_output=True,
            text=True,
            timeout=600
        )
        print(result.stdout)
        if result.stderr:
            print(f"[BOOT] stderr: {result.stderr}")
        if result.returncode == 0:
            print("[BOOT] ✅ Templates generated in background.")
        else:
            print("[BOOT] ⚠️ Template generation failed, using gradients.")
    except Exception as e:
        print(f"[BOOT] ⚠️ Template generation error: {e}")

threading.Thread(target=_generate_templates_async, daemon=True).start()

# ─── YOUR EXISTING BOT CODE BELOW ───
# import discord
# from discord.ext import commands
# ...
