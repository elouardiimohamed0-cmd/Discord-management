import os
import requests
import logging

logger = logging.getLogger("rachad_bot.fal")

FAL_URL = "https://queue.fal.run"

class FalClient:
    def __init__(self):
        self.api_key = os.getenv("FAL_API_KEY")
        if self.api_key:
            logger.info("[FAL] API key loaded")
        else:
            logger.warning("[FAL] No API key found. Set FAL_API_KEY in Fly secrets.")

    def is_available(self):
        return bool(self.api_key)

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1536) -> bytes:
        """Generate an image via fal.ai. Returns image bytes."""
        if not self.api_key:
            raise RuntimeError("FAL_API_KEY not set")

        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
            "num_images": 1,
        }

        logger.info("[FAL] Generating image: %s (%dx%d)", prompt[:60], width, height)

        # Submit job
        resp = requests.post(
            f"{FAL_URL}/fal-ai/flux/dev",
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        job = resp.json()
        request_id = job.get("request_id")

        # Poll for result
        import time
        for _ in range(60):
            time.sleep(2)
            status_resp = requests.get(
                f"{FAL_URL}/fal-ai/flux/dev/requests/{request_id}",
                headers={"Authorization": f"Key {self.api_key}"},
                timeout=30
            )
            if status_resp.status_code == 200:
                result = status_resp.json()
                if result.get("status") == "completed":
                    images = result.get("images", [])
                    if images:
                        img_url = images[0].get("url")
                        if img_url:
                            img_resp = requests.get(img_url, timeout=60)
                            img_resp.raise_for_status()
                            logger.info("[FAL] Image generated: %d bytes", len(img_resp.content))
                            return img_resp.content
                elif result.get("status") == "failed":
                    raise RuntimeError(f"FAL generation failed: {result}")

        raise RuntimeError("FAL generation timed out")
