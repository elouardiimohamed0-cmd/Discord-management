"""Pika client — short cinematic videos, cached forever."""
import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger("rachad_bot.pika")

class PikaClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("PIKA_API_KEY", "")
        self.base_url = "https://api.pika.art"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def generate_video(self, prompt: str, image_path: Optional[str] = None,
                       duration: int = 3, motion: int = 2) -> bytes:
        """Generate short video. Returns raw MP4 bytes."""
        if not self.is_available():
            raise RuntimeError("Pika API key not configured")

        payload = {
            "prompt": prompt,
            "duration": duration,
            "motion": motion,
        }

        files = None
        if image_path and os.path.exists(image_path):
            files = {"image": open(image_path, "rb")}

        logger.info("[Pika] Creating video generation...")
        resp = requests.post(
            f"{self.base_url}/v1/generations",
            headers=self.headers,
            json=payload,
            files=files,
            timeout=30
        )
        resp.raise_for_status()
        gen_id = resp.json().get("id")

        # Poll (max 10 min)
        for _ in range(60):
            time.sleep(10)
            status_resp = requests.get(
                f"{self.base_url}/v1/generations/{gen_id}",
                headers=self.headers,
                timeout=30
            )
            data = status_resp.json()
            status = data.get("status", "pending")

            if status == "completed":
                url = data.get("video", {}).get("url")
                if not url:
                    raise RuntimeError("No video URL returned")
                vid = requests.get(url, timeout=60)
                vid.raise_for_status()
                return vid.content

            elif status in ("failed", "cancelled"):
                raise RuntimeError(f"Video generation failed: {status}")

        raise TimeoutError("Pika generation timed out after 600s")
