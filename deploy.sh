#!/usr/bin/env bash
# qwen-image-turbo worker — build image + create RunPod serverless endpoint.
#
# Reads config from .env (gitignored) or the environment.
# Required:
#   RUNPOD_API_KEY   RunPod API key (runpod.io -> Settings -> API Keys)
#   IMAGE            Docker image, e.g. eratolabcool/qwen-image-turbo
# Optional:
#   TAG=v1           image tag
#   GPU_ID           default "NVIDIA L40S" (48GB; ~32GB model needs 48GB+)
#   MODEL_ID         default "Qwen/Qwen-Image-2.1-Turbo"
#
# Steps: build -> push -> create template -> create endpoint -> print test command.
set -euo pipefail

cd "$(dirname "$0")"

[ -f .env ] && set -a && . ./.env && set +a

IMAGE="${IMAGE:?set IMAGE (docker image name)}"
TAG="${TAG:-v1}"
GPU_ID="${GPU_ID:-NVIDIA L40S}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen-Image-2.1-Turbo}"
FULL_IMAGE="${IMAGE}:${TAG}"

: "${RUNPOD_API_KEY:?set RUNPOD_API_KEY}"
export RUNPOD_API_KEY

echo "==> building ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" .

echo "==> pushing ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo "==> creating serverless template"
TPL_ID=$(runpodctl template create \
  --name "qwen-image-21-turbo-${TAG}" \
  --image "${FULL_IMAGE}" \
  --serverless \
  --container-disk-in-gb 100 \
  -o json | jq -r '.id // .templateId // .Id // empty')
if [ -z "$TPL_ID" ]; then
  echo "!! failed to parse template id" >&2
  exit 1
fi
echo "    template id: ${TPL_ID}"

echo "==> creating serverless endpoint"
EP_ID=$(runpodctl serverless create \
  --template-id "${TPL_ID}" \
  --gpu-id "${GPU_ID}" \
  --name "qwen-image-21-turbo" \
  --idle-timeout 300 \
  --workers-max 3 \
  --execution-timeout 900 \
  --env "MODEL_ID=${MODEL_ID}" \
  --env "HF_HUB_ENABLE_HF_TRANSFER=1" \
  -o json | jq -r '.id // .endpointId // .Id // empty')
if [ -z "$EP_ID" ]; then
  echo "!! failed to parse endpoint id" >&2
  exit 1
fi
echo "    endpoint id: ${EP_ID}"

echo
echo "==> done. test with:"
cat <<EOF
curl -X POST "https://api.runpod.ai/v2/${EP_ID}/runsync" \\
  -H "Authorization: Bearer \${RUNPOD_API_KEY}" \\
  -H "Content-Type: application/json" \\
  -d '{"input":{"prompt":"A cute corgi puppy sitting in a field of wildflowers at golden hour, soft light, photorealistic","width":1024,"height":1024}}'
EOF
