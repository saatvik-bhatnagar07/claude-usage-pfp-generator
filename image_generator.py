"""Generates a techno pixel art image locally using SDXL Turbo.

Runs stabilityai/sdxl-turbo via HuggingFace diffusers on MPS (Apple Silicon).
1-4 step generation — fast with good quality (~6.5GB model).
Resizes output to 1024x1024 for Slack.
"""

import io

import torch
from diffusers import AutoPipelineForText2Image
from PIL import Image

# Lazy-loaded pipeline singleton — avoids reloading the model on every call
_pipeline = None


def _get_pipeline():
    """Load the SD Turbo pipeline once, cached for subsequent calls."""
    global _pipeline
    if _pipeline is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        # Use float32 on MPS — float16 causes black images on Apple Silicon
        _pipeline = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float32,
        )
        _pipeline = _pipeline.to(device)
        _pipeline.enable_attention_slicing()
    return _pipeline


def generate_image(prompt: str) -> bytes:
    """Generate an image from prompt using SD Turbo and return 1024x1024 PNG bytes.

    Args:
        prompt: The assembled image generation prompt.

    Returns:
        PNG image bytes, resized to 1024x1024.
    """
    pipeline = _get_pipeline()

    # SD Turbo: guidance_scale=0.0, 1 step for fastest generation
    # 4 steps gives better quality at minimal cost
    result = pipeline(
        prompt=prompt,
        guidance_scale=0.0,
        num_inference_steps=4,
        width=512,
        height=512,
    )

    image = result.images[0]
    return _resize_to_square(image, 1024)


def _resize_to_square(image: Image.Image, size: int) -> bytes:
    """Resize a PIL Image to an exact square PNG."""
    w, h = image.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        image = image.crop((left, top, left + side, top + side))

    image = image.resize((size, size), Image.LANCZOS)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
