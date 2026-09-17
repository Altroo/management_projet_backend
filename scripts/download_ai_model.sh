#!/usr/bin/env bash
set -euo pipefail

repository="unsloth/Qwen3.6-35B-A3B-GGUF"
revision="a483e9e6cbd595906af30beda3187c2663a1118c"
filename="Qwen3.6-35B-A3B-UD-Q5_K_M.gguf"
expected_sha256="c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932"
model_dir="${AI_MODEL_DIRECTORY:-$(pwd)/models}"
destination="${model_dir}/${filename}"
partial="${destination}.part"

mkdir -p "${model_dir}"

if [[ -f "${destination}" ]]; then
  current_sha256="$(sha256sum "${destination}" | awk '{print $1}')"
  if [[ "${current_sha256}" == "${expected_sha256}" ]]; then
    echo "Model already present and verified: ${destination}"
    exit 0
  fi
  echo "Existing model checksum does not match; refusing to overwrite it." >&2
  exit 1
fi

url="https://huggingface.co/${repository}/resolve/${revision}/${filename}?download=true"
curl --fail --location --continue-at - --output "${partial}" "${url}"

downloaded_sha256="$(sha256sum "${partial}" | awk '{print $1}')"
if [[ "${downloaded_sha256}" != "${expected_sha256}" ]]; then
  echo "Downloaded model checksum mismatch." >&2
  exit 1
fi

mv "${partial}" "${destination}"
chmod 0444 "${destination}"
echo "Verified model installed at ${destination}"
