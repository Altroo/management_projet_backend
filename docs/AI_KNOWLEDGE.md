# Reviewed Management Projet knowledge

Twelve approved JSON documents describe native project/customer/supplier search, project creation, quote statuses/validated estimates, expenses, receipts, financial metrics, payment schedules, actual budgets, navigation, permissions and confirmed changes. Each document has application ID, version hash, category, required native capabilities, source metadata and French/English excerpts. No private records or raw repository dumps are indexed.

Run `python manage.py sync_ai_knowledge` to validate approvals, schemas, sensitive-text checks and language scope, update changed hashes, and remove obsolete documents in this application's scope. An empty source folder refuses destructive replacement. Changes do not require retraining.

The implementation uses the existing PostgreSQL JSON metadata filters and a small permission-filtered weighted lexical index. A separate vector service is unnecessary for twelve reviewed procedures. pgvector is not installed or required by this integration; embeddings are not claimed. Larger semantic corpora would require a measured pgvector comparison before introducing another store. The current lexical approach can miss paraphrases and retrieves up to three documents.

Application/workspace/capability filtering precedes reading restricted titles/content or calculating document frequencies. Document versions/capabilities are rechecked before streaming and replay. The selected reviewed excerpt is delivered in the current message language; the small planner does not rewrite native menu labels or financial procedures. Invalid/outdated sources invalidate history. User conversations are never automatically training sources.
