"""Leonardo AI client — generates premium card backgrounds once, saves forever."""
import os
import time
import logging
import requests
from io import BytesIO
from PIL import Image

logger = logging.getLogger("rachad_bot.leonardo")

class LeonardoClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("LEONARDO_API_KEY", "")
        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def generate_background(self, card_type: str, width: int = 1024, height: int = 1536) -> Image.Image:
        """Generate a premium background. Returns PIL Image RGBA."""
        if not self.is_available():
            raise RuntimeError("Leonardo API key not configured")

        prompts = {
            "mvp": "Premium golden championship sports card background, cinematic gold particles floating, dark elegant stadium atmosphere, luxury abstract geometric patterns, dramatic lighting, no text, no people, empty center area for player photo",
            "fraud": "Dark intense red and black sports card background, dramatic cinematic lighting, red smoke and embers, warning danger atmosphere, abstract dark patterns, intense mood, no text, no people, empty center",
            "ghost": "Mysterious ethereal purple and blue sports card background, ghostly mist and fog, dark cinematic atmosphere, spectral glowing particles, empty center for photo, no text, no people",
            "carry": "Epic powerful blue and cyan sports card background, electric energy arcs, lightning effects, powerful cinematic atmosphere, abstract tech patterns, no text, no people, empty center",
            "court": "Dark dramatic courtroom themed sports card background, shadows and spotlight, subtle gavel and scales motifs, intense red and black atmosphere, no text, no people, empty center",
            "playmaker": "Green football pitch themed card background, grass texture, stadium floodlights, tactical chalk lines, cinematic atmosphere, no text, no people, empty center",
            "sniper": "Sharp precision blue and silver sniper scope themed card background, target crosshair patterns, precision focused atmosphere, cinematic lighting, no text, no people, empty center",
            "ball_loser": "Chaotic comedic orange and brown sports card background, broken pieces, smoke and disaster atmosphere, cartoonish explosion, no text, no people, empty center",
            "match": "Epic stadium panorama background, floodlights, crowd silhouette, green pitch, cinematic sports atmosphere, dark vignette edges, no text, no people, empty center",
        }

        prompt = prompts.get(card_type, prompts["mvp"])

        payload = {
            "prompt": prompt,
            "modelId": "6b645e3a-d64f-4341-a9d7-8442c3a5c2f2",  # Leonardo Phoenix
            "width": width,
            "height": height,
            "num_images": 1,
            "guidance_scale": 7,
            "alchemy": True,
            "photoReal": False,
            "presetStyle": "CINEMATIC"
        }

        logger.info("[Leonardo] Creating generation for '%s'...", card_type)
        resp = requests.post(
            f"{self.base_url}/generations",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        generation_id = resp.json()["sdGenerationJob"]["generationId"]

        # Poll for completion (max 180s)
        for _ in range(36):
            time.sleep(5)
            status_resp = requests.get(
                f"{self.base_url}/generations/{generation_id}",
                headers=self.headers,
                timeout=30
            )
            data = status_resp.json()
            status = data.get("generations_by_pk", {}).get("status", "PENDING")

            if status == "COMPLETE":
                images = data["generations_by_pk"].get("generated_images", [])
                if not images:
                    raise RuntimeError("No images returned")
                url = images[0]["url"]
                img_resp = requests.get(url, timeout=30)
                img_resp.raise_for_status()
                img = Image.open(BytesIO(img_resp.content)).convert("RGBA")
                logger.info("[Leonardo] '%s' generated (%dx%d)", card_type, img.width, img.height)
                return img

            elif status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Generation failed: {status}")

        raise TimeoutError("Leonardo generation timed out after 180s")
