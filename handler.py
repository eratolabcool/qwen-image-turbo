"""RunPod serverless worker for Qwen-Image-2.1-Turbo.

Text-to-image and image editing via the `QwenImage21Pipeline` from Diffusers.

Input contract (JSON `input`):
    prompt          (str, required)  text prompt
    negative_prompt (str, optional)  only used when true_cfg_scale > 1
    true_cfg_scale  (float, optional, default 1.0) classifier-free guidance
    image           (str, optional)  condition image for editing: URL or base64
                                     (optionally a `data:image/...;base64,` prefix)
    width           (int, optional)  default 1024
    height          (int, optional)  default 1024
    num_images      (int, optional)  1..4, default 1
    seed            (int, optional)  deterministic when set
    use_kv_cache    (bool, optional) default True (recommended, faster)
    format          (str, optional)  "png" | "jpeg" | "webp", default "png"
    quality         (int, optional)  jpeg/webp quality, default 90

Output:
    {
      "status": "success",
      "model": "Qwen/Qwen-Image-2.1-Turbo",
      "images": [{"mime": "image/png", "base64": "..."}, ...],
      "width": ..., "height": ...,
      "elapsed_sec": ...
    }
"""

import base64
import io
import os
import time

import runpod
import torch
from diffusers import QwenImage21Pipeline

MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen-Image-2.1-Turbo")

_pipe = None


def load_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe

    print(f"[worker] loading {MODEL_ID} ...")
    t0 = time.time()
    _pipe = QwenImage21Pipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    print(f"[worker] model loaded in {time.time() - t0:.1f}s")
    return _pipe


def _decode_base64_image(data: str):
    """Return bytes for a base64 image string (optionally a data URI)."""
    s = data.strip()
    if s.startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _load_condition_image(image_spec):
    """Accept a URL or base64/data-URI string and return a PIL RGBA image."""
    from PIL import Image

    if isinstance(image_spec, str):
        s = image_spec.strip()
        if s.startswith(("http://", "https://")):
            from diffusers.utils import load_image

            return load_image(s).convert("RGBA")
        return Image.open(io.BytesIO(_decode_base64_image(s))).convert("RGBA")

    raise ValueError("`image` must be a URL string or a base64 string")


def handler(job):
    inp = job.get("input", {}) or {}

    prompt = (inp.get("prompt") or "").strip()
    if not prompt:
        return {"status": "error", "error": "`prompt` is required"}

    pipe = load_pipe()

    width = int(inp.get("width", 1024))
    height = int(inp.get("height", 1024))

    num_images = int(inp.get("num_images", 1))
    num_images = max(1, min(num_images, 4))

    seed = inp.get("seed")
    generator = None
    if seed is not None:
        generator = torch.Generator("cpu").manual_seed(int(seed))

    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_images_per_prompt": num_images,
        "use_kv_cache": bool(inp.get("use_kv_cache", True)),
    }
    if generator is not None:
        kwargs["generator"] = generator
    if inp.get("negative_prompt"):
        kwargs["negative_prompt"] = inp["negative_prompt"]
        kwargs["true_cfg_scale"] = float(inp.get("true_cfg_scale", 1.0))
    if inp.get("image"):
        kwargs["image"] = _load_condition_image(inp["image"])

    t0 = time.time()
    result = pipe(**kwargs)
    elapsed = time.time() - t0

    fmt = (inp.get("format") or "png").lower()
    if fmt not in ("png", "jpeg", "webp"):
        fmt = "png"
    quality = int(inp.get("quality", 90))

    images = []
    for im in result.images:
        buf = io.BytesIO()
        if fmt == "jpeg":
            im.convert("RGB").save(buf, format="JPEG", quality=quality)
            mime = "image/jpeg"
        elif fmt == "webp":
            im.save(buf, format="WEBP", quality=quality)
            mime = "image/webp"
        else:
            im.save(buf, format="PNG")
            mime = "image/png"
        images.append({"mime": mime, "base64": base64.b64encode(buf.getvalue()).decode("utf-8")})

    return {
        "status": "success",
        "model": MODEL_ID,
        "images": images,
        "width": width,
        "height": height,
        "elapsed_sec": round(elapsed, 2),
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
