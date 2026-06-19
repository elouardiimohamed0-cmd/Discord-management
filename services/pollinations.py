import os
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger("rachad_bot.pollinations")

BASE_URL = "https://gen.pollinations.ai"

class PollinationsClient:
    def __init__(self):
        # Check POLLINATIONS_API_KEY first, fallback to LEONARDO_API_KEY for backward compat
        self.api_key = os.getenv("POLLINATIONS_API_KEY") or os.getenv("LEONARDO_API_KEY")

    def is_available(self):
        return bool(self.api_key)

    def _headers(self):
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1536) -> bytes:
        """Generate an image via Pollinations. Returns image bytes."""
        if not self.api_key:
            raise RuntimeError("No API key set. Set POLLINATIONS_API_KEY in Fly secrets.")

        encoded_prompt = quote(prompt)
        url = f"{BASE_URL}/image/{encoded_prompt}"
        params = {
            "model": "flux",
            "width": width,
            "height": height,
            "seed": -1,
            "nologo": "true",
        }

        logger.info("[POLLINATIONS] Generating image: %s (%dx%d)", prompt[:60], width, height)
        resp = requests.get(url, headers=self._headers(), params=params, timeout=120)
        resp.raise_for_status()
        logger.info("[POLLINATIONS] Image generated: %d bytes", len(resp.content))
        return resp.content

    def generate_video(self, prompt: str, duration: int = 5, width: int = 1024, height: int = 1024) -> bytes:
        """Generate a video via Pollinations. Returns MP4 bytes."""
        if not self.api_key:
            raise RuntimeError("No API key set. Set POLLINATIONS_API_KEY in Fly secrets.")

        encoded_prompt = quote(prompt)
        url = f"{BASE_URL}/video/{encoded_prompt}"
        aspect = "9:16" if height > width else "16:9"
        params = {
            "model": "seedance",
            "width": width,
            "height": height,
            "duration": duration,
            "aspectRatio": aspect,
            "seed": -1,
        }

        logger.info("[POLLINATIONS] Generating video: %s (%ds, %s)", prompt[:60], duration, aspect)
        resp = requests.get(url, headers=self._headers(), params=params, timeout=180)
        resp.raise_for_status()
        logger.info("[POLLINATIONS] Video generated: %d bytes", len(resp.content))
        return resp.content
