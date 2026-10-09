# Registered Management Projet tools

| Tool | Native purpose | Access |
|---|---|---|
| search_records | AND-filtered description/project/customer/supplier/status/date search | read |
| get_record | Known or validated current-page record | read |
| financial_summary | Receipts, spending, profit, fees, entered budget, validated quote estimates | read |
| navigate | Verified lists/detail/edit/new forms; names require search first | read; edit/create as applicable |
| knowledge | Approved French/English workflow excerpts | document capabilities |
| previous_results | Revalidated saved results and one-based selection | read |
| project_report | Existing project PDF offer | read + print |
| prepare_change | Preview permitted changes/deletion; never executes | read + native update/delete |

Resources are native projects, customers, suppliers, quotes, expenses, revenues, payment schedules, actual-budget entries, categories and subcategories. Categories/subcategories are searchable; they have no invented standalone navigation destination. Schedules/budget entries open their parent project. Role/account changes and unsupported application modules are excluded.

Input JSON schemas reject extra keys; IDs, search lengths, pagination and date ranges are bounded. `limit <= 10`, `offset <= 100`. Tool SQL has a five-second statement deadline, with elapsed-time checks before delivery. Python business helpers are not forcibly interrupted mid-call. Standard safe error codes include NOT_AUTHENTICATED, PERMISSION_DENIED, NOT_FOUND, MULTIPLE_MATCHES, INVALID_ARGUMENTS, CONTEXT_EXPIRED, TOOL_TIMEOUT, BUSY and APPLICATION_UNAVAILABLE.

`financial_summary` reuses native dashboard/expense/fee helpers and `project_estimate_summary`; estimates count validated TTC quotes. Periods use Africa/Casablanca. Budget/estimate metrics are all-time only; unsupported period combinations are rejected. MAD remains the native currency; no exchange rates or model arithmetic are introduced.

`prepare_change` accepts only the registered editable scalar fields. Actual execution occurs through `/actions/{id}/confirm/`, not through a model tool. Creating records, attachment changes and bulk operations use existing application forms and are not automatic assistant writes.

Slash module shortcuts cover /projets, /clients, /fournisseurs, /devis, /depenses, /revenus, /echeances, /budgets and /categories. /voir, /bilan, /pdf, /modifier, /supprimer and /aide explain usage when sent alone. English aliases are supported. Descriptions work without remembering IDs; matching cards provide authorized actions.
