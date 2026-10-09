# Management Projet application discovery

Scope: management_projet only, after explicit user authorization to move to Phase 2. Facturation remains integrated; no other application is modified.

## Backend and identity
Django 6.1.1 / DRF 3.18.1, PostgreSQL, Redis, Channels/Daphne, Celery, django-simple-history. The local account.CustomUser is trusted through dj-rest-auth JWTAuthentication and native SSO mapping. Numeric identities are not shared with Facturation. Authentication secrets never enter planner context.

## Native access model
core.permissions exposes can_view, can_print, can_create, can_update and can_delete using stored user flags. Staff bypass these flags. Protected frontend pages use these same permissions. QuoteAccess explicitly checks can_view; some older backend GET endpoints check only authentication. The assistant enforces the existing can_view capability consistently rather than copying those permissive older GET handlers. No new role hierarchy or staff-only financial permission is introduced.

## Company boundaries
company.CompanyProfile is a singleton report identity. There are no Membership objects, company-owned project foreign keys or company tabs. The adapter uses the one local workspace (scope key 1), rejecting every other key; it does not import Facturation companies or invent multi-company tenancy. All currently view-authorized users can read this workspace under native rules.

## Entities and APIs
project: Client, Supplier, Category, SubCategory, Project, ProjectAttachment, ProjectPaymentSchedule, ProjectRealBudgetEntry. depense: Expense and attachments. revenu: Revenue and attachments. devis: Quote and attachments. Typed API filters are project.ProjectFilter, devis.QuoteFilter, depense.ExpenseFilter, revenu.RevenueFilter. APIs: /api/project/, /api/project/clients/, /api/project/suppliers/, /api/project/payment-schedules/, /api/project/real-budget-entries/, /api/depense/, /api/revenu/, /api/devis/. /api/account/ is independently restricted; password/role/account mutation is not exposed to the model.

## Financial behavior
Existing project.views._project_dashboard_payload and _multi_project_dashboard_payload define revenue, expenses, service fees, profit, budget use and real budgets. devis.services.project_estimate_summary counts validated TTC quotes only. Expense.frais_de_service_montant is the native fee calculation. The assistant must reuse these calculations and distinguish actual receipts, spending, estimates, budget entries and profit. Currency in native forms is Dhs/MAD. Relative dates use Africa/Casablanca.

## Frontend
Next.js 16.3.8, React 19.3, TypeScript, MUI 9.4, Redux Toolkit Query, Auth.js. src/app/dashboard/layout.tsx persists across authenticated dashboard navigation. Profile/token selectors and useLanguage already exist. Native route helpers expose projects, clients, suppliers, quotes, expenses and revenues; schedules and budget entries live in project detail rather than standalone detail routes. Theme primary comes from getDefaultTheme; reuse textButton, darkTooltip and ActionModals. Existing detail back buttons call router.back and require explicit list destinations for assistant navigation.

## Existing AI and infrastructure
Translation/grammar/rewrite endpoints /api/ai/assist/ are separate and must stay untouched. The central Chat AI Assistant Colibri CPU model already serves Facturation; Management Projet will reuse it through an explicit private-network override, with no second model/backend implementation. Observed server: 62 GiB RAM, approximately 33 GiB available, 130 GiB disk free, low load; other apps and models are running. No production infrastructure or environment was modified during discovery.

## Risks and integration constraints
Fresh permission checks before tools, streamed delivery and history replay; no authorization from chat text, frontend context or model roles. Bound records/schema sizes. History stores replay descriptors rather than private result snapshots. Exact-target confirmation, state fingerprint and native view/serializer authorization for writes; durable actor audit survives conversation removal. All record text is untrusted. Only reviewed bilingual knowledge enters RAG/training; no production financial records. Existing permissive native APIs, destructive project cascades, missing model arguments and incomplete broad model acceptance require explicit tests and reporting.
