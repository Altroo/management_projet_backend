# Prepared deployment and rollback

Management Projet source publication and reviewed deployment-hook replacement are approved. Feature/model activation remains unperformed. Source is prepared locally, pulled and pushed normally; never patch a server Git checkout directly. Existing translation/grammar/dev services and Facturation deployment remain untouched.

The backend Dockerfile includes the checksummed central 0.2.0 wheel before dependency installation. Review `vendor/chat-ai-core-manifest.json`, source commits, migration `chat_ai.0001_initial`, test/build evidence and final candidate acceptance before release. Backend `CHAT_AI_ASSISTANT_ENABLED` and frontend `NEXT_PUBLIC_CHAT_AI_ASSISTANT_ENABLED` default false. A frontend build is required when changing its public build flag.

`deploy/chat-ai.override.yml` joins only the Management Projet web service to the existing private inference network. It starts no new model service and publishes no model port. Provide the operator's existing network name, accepted immutable model ID, private inference URL and dedicated model key through ignored environment configuration. Keep deployment hooks/hosts/secrets outside public documents. Compose validation and actual operator settings must precede authorized activation.

After explicit production approval: release reviewed source through normal Git, build the native application, apply the chat migration, synchronize reviewed knowledge, connect the private network, verify model/auth/health, and enable only this application's flags. Test authenticated native reads, financial values, safe navigation, history, denial and existing translation/grammar behavior live. Test writes only on an explicitly approved disposable record; do not infer permission to delete real financial data.

Health uses the existing `/api/health/` for Django and the inference service's private `/health`. Monitor audit outcomes, inference queue/busy errors, timed-out tools, model/version, response latency and RSS/CPU. Ordinary conversation retention defaults 30 days; schedule `purge_ai_history` through existing operating processes, preserving confirmed write audits.

Rollback: disable this app's frontend/backend flags and restore the prior native source/build. Keep the additive chat tables/audits for review. A shared-model replacement affects Facturation too and requires a separately identified approval and retained artifact; do not switch that model merely because this adapter was implemented.

## Reviewed source-release hook

The local `deploy/management-projet.post-receive` template builds only web/celery/beat, records actual previous image IDs, makes a private database restore copy before the additive migration, checks/synchronizes approved knowledge and updates application services without stopping DB/Redis/models. The frontend template preserves the shared proxy and reloads it gracefully. The other agent's pulled changelog migrations and dark-mode/version source remain intact. Private operator Git configuration supplies the checkout, HTTPS health route and backup directory; no host, SSH connection or secret is in public documentation. Source receipt alone is not deployment proof: verify hook exit/build, migrations, public health, private gateway, business-record fingerprints and unchanged model service start times.
