#!/usr/bin/env bash
set -euo pipefail

model_root="${AI_TRANSLATION_MODEL_DIRECTORY:-$(pwd)/translation-models}"

download_model() {
  local direction="$1"
  local repository="$2"
  local revision="$3"
  shift 3
  local model_dir="${model_root}/${direction}"
  mkdir -p "${model_dir}"

  while [[ "$#" -gt 0 ]]; do
    local filename="$1"
    local expected_sha256="$2"
    shift 2
    local destination="${model_dir}/${filename}"
    local partial="${destination}.part"

    if [[ -f "${destination}" ]]; then
      local current_sha256
      current_sha256="$(sha256sum "${destination}" | awk '{print $1}')"
      if [[ "${current_sha256}" == "${expected_sha256}" ]]; then
        echo "Already verified: ${destination}"
        continue
      fi
      echo "Checksum mismatch for existing file: ${destination}" >&2
      exit 1
    fi

    local url="https://huggingface.co/${repository}/resolve/${revision}/${filename}?download=true"
    curl --fail --location --continue-at - --output "${partial}" "${url}"
    local downloaded_sha256
    downloaded_sha256="$(sha256sum "${partial}" | awk '{print $1}')"
    if [[ "${downloaded_sha256}" != "${expected_sha256}" ]]; then
      echo "Downloaded checksum mismatch: ${destination}" >&2
      exit 1
    fi
    mv "${partial}" "${destination}"
    chmod 0444 "${destination}"
    echo "Verified: ${destination}"
  done
}

download_model \
  "fr-en" \
  "Helsinki-NLP/opus-mt-fr-en" \
  "c4aed37b318c763fd177aa449b44e3b783cc6c02" \
  "config.json" "b3be13d046d9899d7aab8cf4ed624d9a79f5776038ba793f6b4d2ce3e02192f7" \
  "generation_config.json" "4956fb9a7caaad7579cf8bb789c1e578b8a1cf48a0a8b779fda2f95dd10bbaa5" \
  "pytorch_model.bin" "599b819e3488f0fb888fef09511370ce4c0388b6f0f6beeb49a1f4b19043bebc" \
  "source.spm" "78d0e717c77053f1c4b856d8661d9cb87c64f083a35418c087b9146300e4f585" \
  "target.spm" "173e9f493a668fe396d599e28d414a201193094e6ffd7a4678e5aab0f6d3d838" \
  "tokenizer_config.json" "47de9ce87378593016432f8dc657202c03913ab3ce0c15d7f78d51edfc3ff9a3" \
  "vocab.json" "945c604346ce15ce4aff9001001e7f925e336d942c4087017f191871162cbdc4"

download_model \
  "en-fr" \
  "Helsinki-NLP/opus-mt-en-fr" \
  "dd7f6540a7a48a7f4db59e5c0b9c42c8eea67f18" \
  "config.json" "df92c371911b45282caac6101fe7e7f5d5e9af7f9a99356067ffe306278ce72b" \
  "generation_config.json" "4956fb9a7caaad7579cf8bb789c1e578b8a1cf48a0a8b779fda2f95dd10bbaa5" \
  "pytorch_model.bin" "cc1de10b49342ad2f33e06bc4474ddd6eaca278474903c4a8636ce15680d64de" \
  "source.spm" "173e9f493a668fe396d599e28d414a201193094e6ffd7a4678e5aab0f6d3d838" \
  "target.spm" "78d0e717c77053f1c4b856d8661d9cb87c64f083a35418c087b9146300e4f585" \
  "tokenizer_config.json" "3492a8555368d21fc116cac84bdf551aee16783413be3afbfe4823de045960cf" \
  "vocab.json" "945c604346ce15ce4aff9001001e7f925e336d942c4087017f191871162cbdc4"

echo "Pinned OPUS-MT translation models installed under ${model_root}"
