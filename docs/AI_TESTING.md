# Actual integration validation

Tests use isolated local PostgreSQL and native frontend tooling. Production business data is not used for destructive tests or model training.

| Check | Actual result |
|---|---|
| Full combined backend after pulling changelog changes | 605 passed, 84 subtests; two pre-existing Django select_related warnings |
| Full combined frontend after pulling dark mode/version changes | 882 passed, 139 suites |
| Retained Facturation assistant with optional shared core | 831 passed |
| Enabled Next production build after pull/conflict resolution | passed |
| Named return-control regression subset before pull | 57 passed, included in subsequent full combined run |
| Real local native desktop/mobile browser smoke | 20/20 passed, no API mocks |
| MCP Playwright greeting/financial/navigation verification | hello/bonjour welcome without record cards; native monthly expenses; detail opened from dashboard returns to users list |
| Single reviewer after pull | no blocker; AppUpdate, theme/providers, changelog routes and page changes preserved |
| Frozen Management Projet baseline → candidate | tools 44/60 → 44/60; eligible exact args 25/50 → 27/50; valid structure 60/60 → 60/60 |
| Full retained Facturation and Design Workflow comparisons | completed; broad shared-model acceptance remains unmet |
| Isolated CPU probe | 8 requests, 0 errors; 8.108 s sequential mean; 56.59 decode tokens/s excluding prefill; 2.63 GiB peak RSS |

Backend cases cover native financial equality, combined filters, typed arguments, native permissions, workspace/user/conversation isolation, object access, safe URLs, permission-aware restricted/malicious knowledge, current delivery authorization, actor history/audit and bounded operations. Real transaction cases verify target-lock revocation/expiry, changed-child fingerprints, a five-second confirmation/linked-quote lock deadline and compatible expense-before-quote cascade locks. ASGI cases use signed JWTs for stream expiry, revocation, cancellation and lease release. Greeting regressions assert no model/business-tool invocation; narrow aggregate tests preserve individual-record, qualified-query and count intent. Clarification tests preserve business actions and current-message/native-neutral language.

Planner mocks establish trusted backend enforcement, not model interpretation quality. The raw frozen planner misses tool/argument targets; trusted handlers are not credited as model passes. Model calls in the benchmark do not execute business operations. Latency comparisons include overlapping server jobs/QA; the separate small CPU probe is not capacity certification.

The 20-case UI smoke verifies login visibility, one fixed blue/white-icon FAB, bare slash help, native JWT/SSE records, safe navigation, route/minimize persistence, explicit list returns, desktop/mobile layout, overlay priority, reader permissions and logout cleanup. A disposable local fixture verifies explicit confirmed deletion and native actor history; no production business record was modified. Screenshots and raw browser/operator evidence are private ignored artifacts. The full smoke predates the later dark-mode/version pull; the entire combined frontend, backend and build were rerun afterward. Additional final browser checks are reported separately when executed.

Commands:
```bash
python -m pytest --ds=management_projet_backend.settings_ai_test --no-cov -q
bun x jest --runInBand --coverage=false
NEXT_PUBLIC_CHAT_AI_ASSISTANT_ENABLED=true bun run build
```
The isolated settings use an explicit local development/test database. `scripts/chat-ai-ui-smoke.cjs` refuses non-localhost URLs and requires provisioned synthetic native fixtures and an available Playwright package. Source/hook release is approved. Production feature/model activation and real-account assistant acceptance are separate and unperformed.

Final MCP check after the pull: the native dashboard showed the dark-mode control and Nouveautés entry alongside one assistant button. “hello” returned only the English welcome; a real-model project-name search returned the authorized synthetic project. Opening that card from the dashboard, then choosing Liste des projets, navigated to `/dashboard/projects` and preserved the conversation with one panel. The other user's tab was not operated. Final TypeScript and changed-source ESLint checks passed.

Latest target-provenance safeguard (2026-10-10): 78 assistant tests and 111 subtests passed, then the full isolated backend passed 618 tests and 111 subtests. Two existing select_related deprecation warnings remain. Coverage includes guessed targets from descriptive model requests, current-page and fresh-result targets, expired/incorrect resources, complete bilingual IDs, quote-number ambiguity, compound numeric prefixes and native proposal/confirmation/history behavior. Nine pure target checks are included in these counts. The reviewer found no remaining issues. These tests verify backend enforcement; they do not claim that model accuracy passed or that production was enabled.
