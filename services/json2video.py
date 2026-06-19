import os
import requests
import logging
import time

logger = logging.getLogger("rachad_bot.json2video")

JSON2VIDEO_URL = "https://api.json2video.com/v2"

class JSON2VideoClient:
    def __init__(self):
        self.api_key = os.getenv("JSON2VIDEO_API_KEY")
        if self.api_key:
            logger.info("[JSON2VIDEO] API key loaded")
        else:
            logger.warning("[JSON2VIDEO] No API key found. Set JSON2VIDEO_API_KEY in Fly secrets.")

    def is_available(self):
        return bool(self.api_key)

    def generate_video(self, prompt: str, duration: int = 5, width: int = 1024, height: int = 1024) -> bytes:
        """Generate a video via JSON2Video. Returns MP4 bytes."""
        if not self.api_key:
            raise RuntimeError("JSON2VIDEO_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # JSON2Video works with scenes/scenarios
        payload = {
            "resolution": "story-9-16" if height > width else "hd",
            "scenes": [
                {
                    "comment": prompt,
                    "duration": duration,
                }
            ],
        }

        logger.info("[JSON2VIDEO] Generating video: %s (%ds)", prompt[:60], duration)

        # Create movie
        resp = requests.post(
            f"{JSON2VIDEO_URL}/movies",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        job = resp.json()
        project_id = job.get("project_id") or job.get("movie", {}).get("project_id")

        # Poll for completion
        for _ in range(60):
            time.sleep(5)
            status_resp = requests.get(
                f"{JSON2VIDEO_URL}/movies/{project_id}",
                headers=headers,
                timeout=30
            )
            status_resp.raise_for_status()
            status = status_resp.json()

            if status.get("status") == "done" or status.get("movie", {}).get("status") == "done":
                video_url = status.get("url") or status.get("movie", {}).get("url")
                if video_url:
                    vid_resp = requests.get(video_url, timeout=120)
                    vid_resp.raise_for_status()
                    logger.info("[JSON2VIDEO] Video generated: %d bytes", len(vid_resp.content))
                    return vid_resp.content

            if status.get("status") in ("failed", "error"):
                raise RuntimeError(f"JSON2Video generation failed: {status}")

        raise RuntimeError("JSON2Video generation timed out")
