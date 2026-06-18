import os
import requests
import logging

logger = logging.getLogger("rachad_bot.leonardo")

LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
LEONARDO_URL = "https://cloud.leonardo.ai/api/rest/v1/generations"

class LeonardoClient:
    def __init__(self):
        self.api_key = LEONARDO_API_KEY

    def is_available(self):
        return bool(self.api_key)

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1536) -> bytes:
        """Generate a single image. Returns PNG bytes."""
        if not self.api_key:
            raise RuntimeError("LEONARDO_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "prompt": prompt,
            "modelId": "e71a1c2f-4f14-4414-974c-a913e62972d2",
            "width": width,
            "height": height,
            "num_images": 1,
            "guidance_scale": 7,
            "alchemy": True,
            "photoReal": True,
            "photoRealVersion": "v2",
        }

        resp = requests.post(LEONARDO_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        generation_id = data["sdGenerationJob"]["generationId"]

        import time
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{LEONARDO_URL}/{generation_id}", headers=headers, timeout=30)
            poll.raise_for_status()
            poll_data = poll.json()

            images = poll_data.get("generations_by_pk", {}).get("generated_images", [])
            if images:
                img_url = images[0]["url"]
                img_resp = requests.get(img_url, timeout=30)
                img_resp.raise_for_status()
                return img_resp.content

        raise RuntimeError("Leonardo generation timed out")
