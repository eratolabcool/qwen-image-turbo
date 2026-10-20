# Qwen Image 2.1 Turbo — RunPod Serverless worker

Serverless GPU endpoint for **Qwen/Qwen-Image-2.1-Turbo** (8-step turbo
checkpoint of Qwen-Image-2.1, 7B visual generation architecture). Text-to-image
and image editing via the native Diffusers `QwenImage21Pipeline`.

## Request contract

```bash
curl -X POST "https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer {RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"A cute corgi puppy in a field of wildflowers, golden hour","width":1024,"height":1024}}'
```

Async variant: `POST /run` → poll `GET /status/{id}`.

### Input fields

| field            | type    | default | notes                                        |
| ---------------- | ------- | ------- | -------------------------------------------- |
| `prompt`         | str     | —       | required                                     |
| `negative_prompt`| str     | —       | only used when `true_cfg_scale` > 1          |
| `true_cfg_scale` | float   | 1.0     | CFG=1 is the model default                   |
| `image`          | str     | —       | editing: URL or base64 (data-URI ok)         |
| `width`          | int     | 1024    |                                             |
| `height`         | int     | 1024    |                                             |
| `num_images`     | int     | 1       | 1–4                                          |
| `seed`           | int     | —       | deterministic when set                       |
| `use_kv_cache`   | bool    | true    | prefix KV cache (recommended, faster)        |
| `format`         | str     | png     | `png` \| `jpeg` \| `webp`                    |
| `quality`        | int     | 90      | jpeg/webp quality                            |

### Output

```json
{
  "status": "success",
  "model": "Qwen/Qwen-Image-2.1-Turbo",
  "images": [{"mime": "image/png", "base64": "..."}],
  "width": 1024,
  "height": 1024,
  "elapsed_sec": 12.3
}
```

Images are returned as base64 (self-contained; decode client-side or use a data
URI directly).

## Transparent images (RGBA)

The model generates native transparency when prompted:

```
This is an RGBA image with transparency. A cute cartoon dragon sticker. The image has alpha channel and the background is transparent.
```

## Deploy

```bash
cp .env.example .env   # fill in RUNPOD_API_KEY
./deploy.sh
```

The script builds the image, pushes it, creates a serverless template, then
creates the endpoint.

### GPU / memory

The full checkpoint is ~32 GB in bf16 (text encoder 17.5 GB + transformer
14.2 GB + VAE 0.7 GB), so a **48 GB+ GPU is required**. Default `NVIDIA L40S`
(fast); `NVIDIA A40` is the cheaper 48 GB option. 24 GB cards OOM without CPU
offload.

### Cold start

Weights are downloaded from Hugging Face at cold start (`hf_transfer` enabled,
~32 GB → a few minutes on RunPod's network). The endpoint keeps workers warm for
`idle-timeout` (300 s) to avoid re-downloading between bursts. To eliminate the
download entirely, attach a RunPod **Network Volume** pre-populated with the
weights and set `HF_HOME` to its mount path.

## Troubleshooting

- **Worker logs**: `runpodctl serverless logs --id {ENDPOINT_ID}`
- **Model mount/status**: `runpodctl serverless model-status {ENDPOINT_ID}`
- **Check endpoint health**: `runpodctl serverless health {ENDPOINT_ID}`
