# Shared English/French model specialization

This adapter reuses the existing self-hosted Qwen3.5-0.8B model through Colibri CPU inference: 8K context, maximum 512 output tokens, native tool calls and thinking disabled. The central model manifest records the pinned Apache-2.0 model revision. Existing development/translation/grammar services are unchanged. No per-application model download is required.

Management Projet v1 uses synthetic supported operations: 82 training, 10 validation and 60 independent held-out cases (30 English, 30 French). Generator validation checks native schemas, sensitive values and normalized exact split duplicates and forbids database queries. Semantic near-duplicate exclusion is limited as recorded in the manifest.

The first shared v1 candidate executed 164 server-only steps but regressed: existing v4 44/60 tools, 25/50 exact arguments, 60/60 structures; v1 42/60, 23/50, 59/60. It was rejected and never activated. Its interrupted retained Facturation comparison is not a complete result. The initial 4K preflight rejected oversized examples before training; the measured 8K restart avoids truncation.

The final balanced shared v2 corpus retains Facturation and Management Projet and adds separately approved Design Workflow synthetic training: 614 training, 112 validation examples. It executed 366 steps on the approved Linux server, 122 application exposures each, using ten CPU threads, last-eight-layer LoRA rank 8/alpha 16, seed 17 and 1,187,840 trainable parameters. Validation loss: 0.092866 → 0.075527. Peak RSS: 16.82 GiB. Recorded wall time: 3,970.35 seconds, including the user-requested pause. Training and export ran on the server; no production artifact was replaced.

| Management Projet metric | Existing Facturation v4 | Shared v2 candidate |
|---|---|---|
| Correct tool | 44/60 (73.33%) | 44/60 (73.33%) |
| Exact arguments, eligible cases | 25/50 (50%) | 27/50 (54%) |
| Valid structure | 60/60 (100%) | 60/60 (100%) |
| Mean / P95 request latency | 7.702 / 9.059 s | 7.899 / 9.375 s |

Candidate English: 23/30 tools, 14/25 exact arguments. French: 21/30 tools, 13/25 exact arguments. All 24 search tools were selected correctly, but only 13 search arguments matched exactly. Metrics, clarification and context interpretation remain unreliable. The 95% tool/argument targets remain unmet, so the candidate is not accepted for production replacement. Backend permission checks are independently enforced.

The same frozen protocol measured retained Facturation candidate 55/80 tools, 29/66 exact arguments, 76/80 structures; Design Workflow 41/60, 23/48, 60/60. The Facturation eligible denominator changed from historical 76 to 66 because the current evaluator excludes clarification as well as knowledge; this protocol change is not counted as training improvement. Optional declared defaults are normalized; other arguments and clarification language/reason are strict.

The separate eight-request CPU probe measured sequential mean/P95 8.108/8.555 s, concurrency-two 11.857/16.112 s, 56.59 decode tokens/s excluding prefill, 2.63 GiB peak RSS and 3.996 busy cores; zero request errors. It uses warm caches and one decoder slot and is not capacity certification. Runtime profile attribution, same-process identity and model/runtime hashes were verified.

Greetings, exact slash usage, approved workflow handlers and narrow full-sentence aggregate handlers are tested as trusted application behavior, not credited as raw-model benchmark successes. Unmatched requests still use the replaceable provider. No confidential records or conversations are training inputs. Reproducible generators, trainer, exporter, frozen evaluator and sanitized evidence live in the central Chat AI Assistant source. Raw operator provenance, weights, adapters and browser evidence remain ignored/private. Model and feature activation require their separate release gate.
