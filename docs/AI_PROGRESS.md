# Phase 2: Management Projet progress

Scope: Management Projet integration only. Separately authorized Design Workflow shared-model training inspected its adapter read-only and did not deploy its source. Contrat, reservation and gestion_magasin remain untouched. Production source/hook release is approved; feature/model activation and real-account acceptance remain unperformed.

- IMPLEMENTED: native architecture, JWT, permissions, trusted singleton-company context and entity discovery; optional shared-engine hooks and checksummed 0.2.0 wheel.
- IMPLEMENTED: owned conversations, typed read/search/navigation/PDF tools, authoritative financial calculations, permission-aware approved English/French knowledge and incremental synchronization, exact-target confirmed updates/deletes, native history and durable actor audit.
- IMPLEMENTED: authenticated root-layout chat, one fixed bottom-right button, native Facturation-matched palette, current-message language, useful immediate suggestions, slash help, structured cards, history, cancellation/retry, route/minimize persistence and native overlay priority.
- IMPLEMENTED: fifteen named native form/detail return controls navigate to their actual lists. Category editing returns to the existing expenses list. Generic not-found Retour remains generic history navigation. MCP Playwright verified details opened from the dashboard return to the users list.
- IMPLEMENTED: greetings bypass the model and business queries and persist a localized welcome; narrow complete-sentence received/spent aggregate requests use the existing authorized financial executor. Business-qualified requests keep the registered model catalog. Clarification messages use Management Projet's supported metrics and current English/French message, with the native interface language as neutral fallback.
- IMPLEMENTED: synthetic versioned datasets, schema/sensitive-value/split checks, frozen held-out evaluation, server-only balanced shared fine-tuning, export, all three retained application comparisons and actual CPU probe.
- PARTIALLY IMPLEMENTED: broad natural-language reliability and production acceptance. The final candidate misses the 95% tool/argument targets and is not activated. Correct authorization and declining training loss are not model-quality acceptance.
- PLANNED: separately gated production feature/model activation and authenticated real-account assistant acceptance.

## Actual validation

After pulling the other agent's backend changelog commit and frontend dark-mode/version commits, the entire combined backend passed **605 tests and 84 subtests**, with two pre-existing Django select_related deprecation warnings. Frontend passed **882 tests in 139 suites**; the enabled production build passed. The latest single reviewer confirmed AppUpdate, theme/providers, changelog routes and native page changes are preserved. The only pull conflict was the authenticated dashboard layout, resolved with both AppUpdate and the gated assistant.

Earlier retained Facturation assistant regression: 831 passed with the same optional shared core. Real local native desktop/mobile smoke: 20/20, with no API mocks. Additional MCP verification reproduced the hello failure and confirmed a welcome with no cards or business query, French greeting language switching, a correct native monthly expense total and exact list navigation. Security tests use real isolated PostgreSQL locks and signed JWTs, covering revoked access, expiry, confirmation races, changed children, object/conversation isolation, restricted counts, untrusted data/navigation and audit attribution. No unresolved critical bypass was found in the executed cases; this is not a guarantee outside those cases.

## Training and measured limitations

Final shared v2 trained on the approved server: 366 optimization steps, 122 exposures per application, English/French only, 10 threads, last-eight-layer LoRA, 8K context and no truncation. Peak training RSS was 16.82 GiB. Management Projet candidate: 44/60 correct tools, 27/50 eligible exact arguments, 60/60 valid structures; baseline: 44/60, 25/50, 60/60. All retained comparisons completed. Candidate selection remains unreliable for some metrics, arguments, clarification and context; the broad quality gate is unmet. Existing production weights remain unchanged.

The isolated eight-request Colibri probe measured 8.108 s sequential mean, 11.857 s at concurrency two, 56.59 decode tokens/s excluding prefill, 2.63 GiB peak RSS and zero errors. One decoder slot and warm-cache/small-sample limitations apply. Application trusted handlers are not scored as raw-model successes. See AI_FINE_TUNING.md and the central shared-model comparison.

## Source and deployment

Created: chat_ai package, additive migration, approved knowledge, isolated test settings, wheel/manifest, AI documents, private-network override and reviewed deployment templates; frontend chat components/API/tests/local-only smoke script; central dataset/generator/trainer/export/evaluator/report extensions. Modified: native settings/URLs/dependency build, authenticated layout, fifteen return controls, public-safe README/config/ignore examples. Native business schemas, permissions and calculations were not replaced.

The approved production hooks build before replacing only application services, retain actual previous image IDs privately, take a private database copy before migration, preserve DB/Redis/model services and gracefully reload existing gateways. Hook templates contain no connection details; operator settings/backups remain private. Source release still requires exact remote-head, build/migration/health and business-record verification. Flags default off. No destructive operation was tested on production data. A shared-model replacement would also affect Facturation and is not included in the approved source/hook release.

Final post-pull MCP verification also passed: native dark-mode/changelog controls remain present; “hello” gives only a welcome; actual model project search returns the synthetic authorized project; the AI card opens details and the named list button returns to `/dashboard/projects`, preserving one conversation panel. TypeScript and changed-source ESLint passed.
