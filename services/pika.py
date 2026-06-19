import os
import requests
import logging
import time

logger = logging.getLogger("rachad_bot.pika")

PIKA_URL = "https://api.pika.art/v1/generations"

class PikaClient:
    def __init__(self):
        self.api_key = os.getenv("PIKA_API_KEY")  # ← Read at runtime, not import

    def is_available(self):
        return bool(self.api_key)

    def generate_video(self, prompt: str, duration: int = 3, motion: int = 2) -> bytes:
        """Generate a video. Returns MP4 bytes."""
        if not self.api_key:
            raise RuntimeError("PIKA_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "prompt": prompt,
            "duration": duration,
            "motion": motion,
            "aspect_ratio": "9:16",
        }

        resp = requests.post(PIKA_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        job_id = data.get("id") or data.get("job", {}).get("id")

        for _ in range(60):
            time.sleep(5)
            poll = requests.get(f"{PIKA_URL}/{job_id}", headers=headers, timeout=30)
            poll.raise_for_status()
            poll_data = poll.json()

            status = poll_data.get("status") or poll_data.get("job", {}).get("status")
            if status == "completed":
                video_url = poll_data.get("video_url") or poll_data.get("job", {}).get("video_url")
                if video_url:
                    vid_resp = requests.get(video_url, timeout=60)
                    vid_resp.raise_for_status()
                    return vid_resp.content
            elif status in ("failed", "error"):
                raise RuntimeError(f"Pika generation failed: {poll_data}")

        raise RuntimeError("Pika generation timed out")
