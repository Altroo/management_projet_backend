# Changelog and release announcements

The first versioned release is **4.2.0**, dated 9 October 2026. The history
contains 35 bilingual entries derived from 179 unique reachable commits across
the two repositories. Historical versions are reconstructed product milestones,
not evidence of production deployment dates or public API compatibility.

`changelog-history-sources.json` records the import heads, full commit hashes,
dates, subjects, bodies, file lists, milestone evidence and date classifications.
The curated content is in `ws/migrations/data/0003_changelog_history.json`.
Uncommitted AI chat work is outside this release.

## Publication

1. Deploy the backend and run migrations `ws.0002` and `ws.0003`.
2. Deploy the matching frontend and verify its `/api/app-version` response.
3. In the Changelog admin, publish the 9 October entry. It is initially a draft.
4. Save the Maintenance state with version `4.2.0` after confirming frontend
   health. Leave maintenance off when the application is ready.

The history seed uses `get_or_create` by date. Re-running it preserves editor
changes and publication state. It does not announce a release. Maintenance saves
and deletes broadcast the latest committed state; direct queryset updates do not
broadcast. The fallback `0.1.0` is a compatibility floor, not the current release.

`GET /api/ws/changelog/` is authenticated and read-only. It excludes drafts and
future entries. `GET /api/ws/maintenance/` is public and unthrottled. Both return
`Cache-Control: no-store`. Changelog admin publication requires both languages.

## Verification

Use `management_projet_backend.settings_changelog_test` for release checks. It
always selects a dedicated PostgreSQL database on localhost:5432 and uses local
email, cache and Channels backends. Never create preview users in production.

```sh
DJANGO_SETTINGS_MODULE=management_projet_backend.settings_changelog_test .venv/bin/python -m pytest ws/tests.py ws/test_changelog.py -q --no-cov
DJANGO_SETTINGS_MODULE=management_projet_backend.settings_changelog_test .venv/bin/python manage.py makemigrations --check --dry-run
```

Initial verification: 29 backend tests and 837 frontend tests passed. Full
frontend lint, TypeScript checking and the Next.js production build passed.
Browser verification used isolated ports 3037/8037 and a dedicated local database:

- Staff and ordinary-member access; direct link after Settings; mobile drawer.
- Both languages, all 35 entries, oldest/newest entries, error/retry and no extra
  timeline heading or horizontal overflow at 390px.
- Real websocket announcements from admin saves; same/older versions stay quiet;
  maintenance hides updates; Later dismisses one version; a newer release prompts.
- Unavailable frontend keeps the form and typed input intact with a retryable error.
- An open 4.1.9 test bundle updates to 4.2.0, preserving path, query and hash and
  removing the temporary update marker after the new bundle loads.
- Dark preference in server HTML and after reload, Poppins, nested form themes,
  unsaved input retention, charts with and without data, and matching card/header
  surfaces without elevation overlays. Logos and document presentation remain intact.

The first rollout cannot notify tabs running JavaScript from before this protocol.
Those tabs require one ordinary refresh; subsequent releases can notify them.
