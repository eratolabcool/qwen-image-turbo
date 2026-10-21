# Qwen Image 2.1 Turbo — RunPod Serverless worker

Serverless GPU endpoint for **Qwen/Qwen-Image-2.1-Turbo** (8-step turbo
checkpoint, 7B architecture). Text-to-image + image editing via the native
Diffusers `QwenImage21Pipeline`.

## Live endpoints

Two RunPod accounts run the same worker from the same public image.

| Account | Endpoint ID | Runsync |
|---|---|---|
| eratolabcool@gmail.com | `1xhr888nye1wtz` | `https://api.runpod.ai/v2/1xhr888nye1wtz/runsync` |
| shjack803@gmail.com | `jg9y65c0o6ao94` | `https://api.runpod.ai/v2/jg9y65c0o6ao94/runsync` |

Common config: model `Qwen/Qwen-Image-2.1-Turbo`, GPU pool ADA_48_PRO
(L40S / RTX 6000 Ada / L40, 48GB), image `eratolabcool/qwen-image-turbo:v2`
(Docker Hub, public), idle-timeout 300s, execution-timeout 900s.

## Call it

```bash
# account 1 (eratolabcool@gmail.com)
curl -X POST "https://api.runpod.ai/v2/1xhr888nye1wtz/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"A cute corgi puppy in a field of wildflowers, golden hour, photorealistic","width":1024,"height":1024,"format":"jpeg"}}'

# account 2 (shjack803@gmail.com) — use $RUNPOD_API_KEY_2
curl -X POST "https://api.runpod.ai/v2/jg9y65c0o6ao94/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY_2" \
  -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"A cute corgi puppy in a field of wildflowers, golden hour, photorealistic","width":1024,"height":1024,"format":"jpeg"}}'
```

Or async: `POST /run` → poll `GET /status/{id}`.

### Input fields (this worker's contract)

| field | default | notes |
|---|---|---|
| `prompt` | — | required |
| `negative_prompt` | — | only used when `true_cfg_scale` > 1 |
| `true_cfg_scale` | 1.0 | CFG=1 is the model default |
| `image` | — | editing: URL or base64 (data-URI ok) |
| `width` / `height` | 1024 | 8-step schedule ignores `num_inference_steps` |
| `num_images` | 1 | 1–4 |
| `seed` | random | deterministic when set |
| `use_kv_cache` | true | prefix KV cache (recommended) |
| `format` | png | `png` \| `jpeg` \| `webp` |
| `quality` | 90 | jpeg/webp only |

### Output

```json
{
  "status": "success",
  "model": "Qwen/Qwen-Image-2.1-Turbo",
  "images": [{"mime": "image/jpeg", "base64": "..."}],
  "width": 1024, "height": 1024,
  "elapsed_sec": 1.44
}
```

512×512 measured at **~1.4s** warm. Images are base64 (decode client-side).

## How it was built / deployed

1. `requirements.txt` + `Dockerfile` (python:3.11-slim, torch 2.10.0 CUDA-bundled).
2. GitHub Actions (`.github/workflows/build.yml`) builds `linux/amd64` and pushes
   to Docker Hub `eratolabcool/qwen-image-turbo:{v2,latest}` — avoids the
   Apple-Silicon/arm64 problem.
3. RunPod template `zwxwxlxozu` + endpoint created with `runpodctl`.

Rebuild after code changes:

```bash
# bump tag in .github/workflows/build.yml, then
git push origin main   # triggers build; or:
gh workflow run "Build RunPod Image"
```

## Cold start & model cache

The ~32 GB checkpoint is downloaded from Hugging Face at cold start
(`hf_transfer` enabled, a few minutes on RunPod's network). `idle-timeout` is
300s, so the worker stays warm for 5 min after the last request. **Optimization
(not yet done):** attach a RunPod Network Volume and set `HF_HOME` to its mount
path so the weights survive scale-to-zero instead of re-downloading.

`flash-boot` is currently OFF (a stale flashboot snapshot served an old image
during testing). Re-enable once the image is stable.

## Troubleshooting

- `runpodctl serverless logs 1xhr888nye1wtz`
- `runpodctl serverless health 1xhr888nye1wtz`
