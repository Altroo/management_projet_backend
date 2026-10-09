# Management Projet chat API

All routes use existing JWT authentication under `/api/ai/v1/`, native feature gating and no-store responses.

| Method | Path | Purpose |
|---|---|---|
| GET | capabilities/ | Native permissions, singleton workspace, permitted suggestions/shortcuts |
| POST | conversations/ | Create an owned conversation with company_id=1 |
| GET | conversations/?company_id=1 | List up to 30 live owned conversations |
| GET | conversations/{uuid}/ | Reopen history with current authorized results |
| DELETE | conversations/{uuid}/ | Delete owned conversation; write audits remain |
| POST | conversations/{uuid}/messages/ | text, request_id UUID, bounded context |
| POST | conversations/{uuid}/selection/ | Select a record from the live previous result set for edit/delete |
| POST | actions/{uuid}/confirm/ | Explicit confirmed=true; owned, valid, single-use proposal |
| POST | feedback/ | Helpful/unhelpful feedback for an owned assistant message |

Message context permits only interface_language (en/fr) and a native resource/identifier page hint. Hints are not authorization. User IDs, role names, alternate company IDs and arbitrary URLs are rejected. Completed request IDs cannot be reused with changed instructions.

`Accept: text/event-stream` enables authenticated SSE: message.started, tool.started, tool.completed, message.delta, message.completed, error. Progress events omit raw business results. The completion payload contains authoritative structured cards. JSON mode returns the same completed message. JWT expiry, permission revocation, cancellation, timeout, partial responses and bounded queues are handled. Credentials stay in headers, not stream URLs.

Read, mutation, inference and confirmation requests have separate throttles. Database leases serialize inference within the adapter; the shared Colibri runtime uses one KV slot and a bounded queue across applications. Model transport cancellation is checked between upstream events; a blocked upstream socket has a bounded read timeout, so cancellation is not instant during prefill.
