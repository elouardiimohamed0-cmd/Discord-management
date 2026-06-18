#!/usr/bin/env python3
"""
Generate 9 premium card backgrounds once, save to assets/templates/.
Run this ONCE on your Fly.io machine via SSH.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.leonardo import LeonardoClient

TEMPLATES = {
    "mvp": "Golden trophy celebration, confetti, stadium lights, dramatic lighting, EA FC style card background, dark with gold accents, 1024x1536",
    "fraud": "Dramatic red courtroom, guilty verdict, shame spotlight, dark atmosphere, EA FC style card background, 1024x1536",
    "ghost": "Misty empty football pitch, purple fog, ghostly atmosphere, abandoned stadium, EA FC style card background, 1024x1536",
    "carry": "Superhero lifting team, blue energy explosion, epic cinematic, EA FC style card background, 1024x1536",
    "court": "Wooden courtroom, judge gavel, dramatic shadows, legal drama, EA FC style card background, 1024x1536",
    "playmaker": "Green football pitch, creative passing lanes, artistic vision, EA FC style card background, 1024x1536",
    "sniper": "Target crosshair, precision strike, bullet trail, EA FC style card background, 1024x1536",
    "ball_loser": "Broken ball, disappointed crowd, comedic failure, EA FC style card background, 1024x1536",
    "match": "Epic stadium intro, floodlights, roaring crowd, green pitch, EA FC style card background, 1024x1536",
}

def main():
    client = LeonardoClient()
    if not client.is_available():
        print("ERROR: LEONARDO_API_KEY not set!")
        sys.exit(1)

    os.makedirs("assets/templates", exist_ok=True)

    for name, prompt in TEMPLATES.items():
        path = f"assets/templates/{name}.png"
        if os.path.exists(path):
            print(f"SKIP: {name} already exists")
            continue

        print(f"GENERATING: {name}...")
        print(f"  Prompt: {prompt[:80]}...")
        try:
            img_bytes = client.generate_image(prompt)
            with open(path, "wb") as f:
                f.write(img_bytes)
            print(f"  SAVED: {path} ({len(img_bytes)} bytes)")
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\nDone! Templates saved in assets/templates/")

if __name__ == "__main__":
    main()
