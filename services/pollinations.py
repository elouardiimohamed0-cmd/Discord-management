import os
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger("rachad_bot.pollinations")

# FREE Pollinations endpoints — no API key required for basic use!
IMAGE_URL = "https://image.pollinations.ai/prompt/"
VIDEO_URL = "https://video.pollinations.ai/"

class PollinationsClient:
    def __init__(self):
        # Optional: API key for higher rate limits, but NOT required
        self.api_key = os.getenv("POLLINATIONS_API_KEY") or os.getenv("LEONARDO_API_KEY")
        if self.api_key:
            logger.info("[POLLINATIONS] API key found (optional, using for higher limits)")
        else:
            logger.info("[POLLINATIONS] No API key — using FREE tier (no key required)")

    def is_available(self):
        # Always available — free tier doesn't need a key!
        return True

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1536) -> bytes:
        """Generate an image via Pollinations FREE tier. No key needed."""
        encoded_prompt = quote(prompt)
        url = f"{IMAGE_URL}{encoded_prompt}"
        params = {
            "width": width,
            "height": height,
            "seed": -1,
            "nologo": "true",
        }
        if self.api_key:
            params["key"] = self.api_key

        logger.info("[POLLINATIONS] Generating image (FREE): %s (%dx%d)", prompt[:60], width, height)
        resp = requests.get(url, params=params, timeout=120)
        logger.info("[POLLINATIONS] Response status: %d", resp.status_code)

        if resp.status_code == 429:
            logger.warning("[POLLINATIONS] Rate limited — add POLLINATIONS_API_KEY for higher limits")
            raise RuntimeError("Pollinations rate limited. Add API key for higher limits.")

        resp.raise_for_status()
        logger.info("[POLLINATIONS] Image generated: %d bytes", len(resp.content))
        return resp.content

    def generate_video(self, prompt: str, duration: int = 5, width: int = 1024, height: int = 1024) -> bytes:
        """Generate a video via Pollinations FREE tier. No key needed."""
        encoded_prompt = quote(prompt)
        url = f"{VIDEO_URL}{encoded_prompt}"
        aspect = "9:16" if height > width else "16:9"
        params = {
            "width": width,
            "height": height,
            "duration": duration,
            "aspectRatio": aspect,
            "seed": -1,
        }
        if self.api_key:
            params["key"] = self.api_key

        logger.info("[POLLINATIONS] Generating video (FREE): %s (%ds, %s)", prompt[:60], duration, aspect)
        resp = requests.get(url, params=params, timeout=180)
        logger.info("[POLLINATIONS] Response status: %d", resp.status_code)

        if resp.status_code == 429:
            logger.warning("[POLLINATIONS] Rate limited — add POLLINATIONS_API_KEY for higher limits")
            raise RuntimeError("Pollinations rate limited. Add API key for higher limits.")

        resp.raise_for_status()
        logger.info("[POLLINATIONS] Video generated: %d bytes", len(resp.content))
        return resp.content
