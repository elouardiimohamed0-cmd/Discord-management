import os
import subprocess
import sys

TEMPLATES_DIR = "assets/templates"

def ensure_templates_exist():
    """Generate templates on first boot if missing."""
    required = [
        "mvp.png", "fraud.png", "ghost.png", "carry.png",
        "court.png", "playmaker.png", "sniper.png", "ball_loser.png"
    ]

    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    missing = [
        f for f in required 
        if not os.path.exists(os.path.join(TEMPLATES_DIR, f))
    ]

    if missing:
        print(f"[BOOT] Missing templates: {missing}")
        print("[BOOT] Starting template generation (this takes ~10-15 min)...")

        result = subprocess.run(
            [sys.executable, "generate_templates.py"],
            capture_output=True,
            text=True,
            timeout=1200  # 20 minutes max
        )

        print(result.stdout)
        if result.stderr:
            print(f"[BOOT] stderr: {result.stderr}")

        if result.returncode != 0:
            print("[BOOT] ⚠️ Template generation failed, falling back to gradients.")
        else:
            print("[BOOT] ✅ All templates generated.")
    else:
        print("[BOOT] ✅ All templates present.")

# Run immediately on import — BEFORE discord bot starts
ensure_templates_exist()

# ─── REST OF YOUR MAIN.PY BELOW ───
# import discord
# from discord.ext import commands
# ... your existing bot code ...
