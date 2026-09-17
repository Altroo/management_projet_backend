import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import MarianMTModel, MarianTokenizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("opus_translation")

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))

MODEL_PATHS = {
    "en": "/models/fr-en",
    "fr": "/models/en-fr",
}
MODELS = {}
TOKENIZERS = {}
INFERENCE_LOCK = threading.Lock()
MIN_GENERATION_TOKENS = 64
MAX_GENERATION_TOKENS = 256


def load_models():
    for target_language, path in MODEL_PATHS.items():
        TOKENIZERS[target_language] = MarianTokenizer.from_pretrained(
            path, local_files_only=True
        )
        MODELS[target_language] = MarianMTModel.from_pretrained(
            path, local_files_only=True, use_safetensors=False
        ).eval()
    logger.info("OPUS-MT models loaded")


def translate(texts, target_language):
    tokenizer = TOKENIZERS[target_language]
    model = MODELS[target_language]
    translated = []
    with INFERENCE_LOCK, torch.inference_mode():
        for offset in range(0, len(texts), 32):
            batch = texts[offset : offset + 32]
            encoded = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            source_tokens = int(encoded["attention_mask"].sum(dim=1).max().item())
            generation_limit = min(
                max((source_tokens * 2) + 16, MIN_GENERATION_TOKENS),
                MAX_GENERATION_TOKENS,
            )
            generated = model.generate(
                **encoded,
                num_beams=4,
                do_sample=False,
                early_stopping=True,
                max_length=generation_limit,
                no_repeat_ngram_size=3,
            )
            translated.extend(
                tokenizer.batch_decode(generated, skip_special_tokens=True)
            )
    return translated


class Handler(BaseHTTPRequestHandler):
    server_version = "opus-translation/1"

    def _json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok"})
            return
        self._json_response(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/translate":
            self._json_response(404, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_response(400, {"error": "invalid_content_length"})
            return
        if content_length < 2 or content_length > 1_000_000:
            self._json_response(413, {"error": "request_too_large"})
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(400, {"error": "invalid_json"})
            return
        texts = payload.get("texts") if isinstance(payload, dict) else None
        target_language = (
            payload.get("target_language") if isinstance(payload, dict) else None
        )
        if (
            target_language not in MODEL_PATHS
            or not isinstance(texts, list)
            or not texts
            or len(texts) > 100
            or not all(
                isinstance(text, str) and 0 < len(text) <= 5_000 for text in texts
            )
            or sum(map(len, texts)) > 50_000
        ):
            self._json_response(400, {"error": "invalid_request"})
            return
        started = time.monotonic()
        try:
            translations = translate(texts, target_language)
        except Exception:
            logger.exception(
                "translation failed target=%s items=%d characters=%d",
                target_language,
                len(texts),
                sum(map(len, texts)),
            )
            self._json_response(500, {"error": "translation_failed"})
            return
        logger.info(
            "translation completed target=%s items=%d characters=%d duration_ms=%d",
            target_language,
            len(texts),
            sum(map(len, texts)),
            round((time.monotonic() - started) * 1000),
        )
        self._json_response(200, {"translations": translations})

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    load_models()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
