# Shared CPU-only AI assistant

The deployment contains one policy gateway and one private `llama.cpp` model process.
Application users call their own backend. Other application backends call the signed,
narrow gateway endpoint. No application calls `llama.cpp` directly.

## Pinned runtime

- Runtime: `ghcr.io/ggml-org/llama.cpp:server-b10991`
- Runtime digest: `sha256:79903855d3de1689e9856219283591be12ba6f40a8e65fc7223824109446ad88`
- Model repository: `unsloth/Qwen3.6-35B-A3B-GGUF`
- Model revision: `a483e9e6cbd595906af30beda3187c2663a1118c`
- File: `Qwen3.6-35B-A3B-UD-Q5_K_M.gguf`
- SHA256: `c13ce26253ea334df472bd8fbd2d6da66d8a41195c17f6fcbf44c4d20ece0932`

The vision projector is intentionally not downloaded or mounted.

## Candidate and disk policy

Test one candidate at a time and remove a failed candidate before downloading the
next one. The decision order is:

1. Qwen3.8-27B Q5_K_M was tested first and rejected after cold and warm
   250-character translations took 54.7 and 55.0 seconds.
2. Qwen3.6-35B-A3B Q5_K_M is the pinned current candidate above.
3. Qwen3.5-35B-A3B Q5_K_M only for runtime or multilingual compatibility issues.
4. Qwen3-30B-A3B-Instruct-2507 Q5_K_M as the mature fallback.

Do not use an unpinned fallback. Record its repository revision, exact filename,
SHA256, runtime image digest, benchmark result, and license before changing the
deployment configuration. Keep only the winning general model. Add the Apache-2.0
OPUS-MT `fr-en` and `en-fr` pair only if the winning Qwen model passes grammar and
professional rewriting but fails the translation quality or PDF-latency gate.

Rejected candidate record (2026-09-17): Qwen3.8 used repository
`unsloth/Qwen3.8-27B-GGUF`, revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, file
`Qwen3.8-27B-UD-Q5_K_M.gguf`, and SHA256
`2de73110cb254cbf09b54b717578dadff12ef1194e7271527e68202f39ba4bfd` with the
same pinned runtime above. It preserved every protected value in both sanitized
translation runs, but failed the no-run-above-30-seconds latency requirement.

## Start-up

1. Run `scripts/download_ai_model.sh` from the backend directory.
2. Configure a different high-entropy secret for every caller in
   `AI_ASSISTANT_SERVICE_KEYS`, for example `{"facturation":"..."}`.
3. Start and inspect the model with `docker compose --profile ai up -d ai-model` and
   `docker compose ps ai-model`.
4. Keep `AI_ASSISTANT_ENABLED=False` until the acceptance benchmark passes.
5. Enable one user through `AI_ASSISTANT_USER_IDS` before enabling all internal users.

The raw model has no host port. Peer applications can reach only the Nginx gateway at
`http://ai-assistant-gateway:8080/v1/assist` on the `ebh-ai-gateway` Docker network.
The gateway returns 404 for every other path. A peer Compose project should declare
that network as external and attach only its backend service:

```yaml
networks:
  ebh-ai-gateway:
    external: true
    name: ebh-ai-gateway
```

## Signed service request

Send a POST request with these headers:

- `X-AI-Service`: the configured application name.
- `X-AI-Timestamp`: current Unix timestamp.
- `X-AI-Request-ID`: a unique value of 16 to 128 characters.
- `X-AI-Signature`: lowercase HMAC-SHA256 hex digest.

The signed canonical value is:

```text
<timestamp>\n<service-name>\n<request-id>\n<sha256-of-exact-request-body>
```

The JSON contract matches `/api/ai/assist/`. A peer application may additionally
send up to 100 `protected_terms` (names or identifiers known to that application).
The gateway replaces those terms before inference and rejects responses that alter
their placeholders. Requests older than five minutes and reused request IDs fail.

The gateway is the stable server-level interface: new applications get their own
service name, secret, rate-limit bucket, cache namespace, and protected terms. They
join only `ebh-ai-gateway`; they must never join the model network or reuse another
application's secret. This keeps the model private while allowing the selected model
to be replaced without changing peer applications.

## Acceptance gate

Run the following with sanitized copies of real project text, after the model is
warm and with the AI cache cleared between measured runs so cache hits do not hide
inference time:

- Ten runs of roughly 250 characters: median at most 15 seconds, no run above 30.
- Ten representative project PDFs: median at most 90 seconds, no run above 180.
- Existing application API latency under load: no more than 20 percent slower.
- Translation: at least 18 of 20 samples accepted without correction.
- Grammar: at least 9 of 10 samples corrected without changing meaning.
- Professional rewrite: at least 8 of 10 clearly improved without invented facts.
- Names, identifiers, dates, numbers, currencies, emails, and URLs: 100 percent
  preserved.

Record model/runtime pins, CPU and RAM, every measured duration, quality decisions,
and errors, but never record unsanitized source or generated business text. Keep
`AI_ASSISTANT_ENABLED=False`, `AI_PDF_TRANSLATION_ENABLED=False`, and the frontend
flag disabled until all applicable checks pass. If Qwen translation alone fails,
evaluate the pinned OPUS-MT pair against the same translation gate before routing
translation away from Qwen.

For PDF QA, generate French and English reports from opposite-language content,
extract their text with `pdftotext`, render every page with Poppler, and inspect
wrapping, accents, names, totals, and page breaks. Confirm that profit, margin,
service-fee values, and real-budget values remain absent, and that French reports
continue to use `RESTE EN CAISSE`.

## Operational boundaries

- Redis DB 2 stores 30-day hashed, application-isolated results and replay markers.
- Logs contain application, operation, character count, model, cache state, duration,
  and error class only. They never contain request or generated text.
- Feature disablement stops both user and service requests with HTTP 503.
- Timeout returns HTTP 504; unavailable model returns HTTP 503.
- Disable the feature flag before stopping the model. No business-data rollback or
  database migration is required.
