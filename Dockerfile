# Qwen-Image-2.1-Turbo RunPod serverless worker.
#
# Slim Python base: torch 2.10.0's default PyPI wheel bundles its own CUDA 12.8
# runtime (nvidia-cuda-runtime-cu12==12.8.90 etc.), so no heavyweight CUDA base
# image is needed — RunPod's host provides the NVIDIA driver.
FROM python:3.11-slim-bookworm

# Small system libs that some torch/diffusers wheels expect at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install pinned Python deps (torch CUDA build, diffusers w/ QwenImage21Pipeline,
# transformers, accelerate, pillow) plus the RunPod SDK and hf_transfer for fast
# HuggingFace weight downloads.
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY handler.py .

# Fast model download at cold start; weights (~32 GB) are cached in the
# container disk and stay resident until the worker scales to zero.
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV MODEL_ID=Qwen/Qwen-Image-2.1-Turbo

CMD ["python3.11", "-u", "handler.py"]
