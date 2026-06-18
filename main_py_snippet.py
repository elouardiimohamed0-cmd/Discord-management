import os
import subprocess
import sys
import threading

TEMPLATES_DIR = "assets/templates"

def _generate_templates_async():
    """Run template generation in background thread."""
    required = [
        "mvp.png", "fraud.png", "ghost.png", "carry.png",
        "court.png", "playmaker.png", "sniper.png", "ball_loser.png"
    ]
    
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    
    missing = [
        f for f in required 
        if not os.path.exists(os.path.join(TEMPLATES_DIR, f))
    ]
    
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
            timeout=600  # 10 minutes max
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

# Start background thread immediately — bot is NOT blocked
threading.Thread(target=_generate_templates_async, daemon=True).start()

# ─── REST OF YOUR MAIN.PY BELOW ───
# import discord
# from discord.ext import commands
# ... your existing bot code ...
