# Twilio SMS (Mkulima Sokoni)

Transactional SMS for **verification decisions** and **support ticket replies** (admin to user). Twilio is optional and gated by feature flags so the API keeps working if Twilio is off or misconfigured.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TWILIO_VERIFICATION_SMS_ENABLED` | Set `true` to send SMS after admin approve/reject verification. |
| `TWILIO_SUPPORT_SMS_ENABLED` | Set `true` to SMS the ticket owner when an admin posts a **non-internal** reply. |
| `TWILIO_ACCOUNT_SID` | Twilio account SID. |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (keep secret; never commit). |
| `TWILIO_MESSAGING_SERVICE_SID` | Preferred sender (Messaging Service). |
| `TWILIO_FROM_NUMBER` | Fallback E.164 sender if no Messaging Service. |
| `TWILIO_VERIFY_APPROVED_CONTENT_SID` | Optional Twilio Content template SID for **approved** (uses variables `name`, `role`). |
| `TWILIO_VERIFY_REJECTED_CONTENT_SID` | Optional Content template SID for **rejected** (`name`, `role`, `reason`). |
| `TWILIO_VERIFY_APPROVED_BODY` | Plain body if no approved Content SID; supports `{name}`, `{role}`. |
| `TWILIO_VERIFY_REJECTED_BODY` | Plain body if no rejected Content SID; supports `{name}`, `{role}`, `{reason}`. |
| `PUBLIC_APP_URL` | Base URL for links in support SMS (e.g. `https://your-app.vercel.app`). |
| `SUPPORT_TICKET_DEEP_LINK_BASE` | Optional override for support links only (defaults to `PUBLIC_APP_URL`). |

**Deferred (not implemented in routes):**

- `TWILIO_SUPPORT_NOTIFY_NUMBERS` — SMS staff when users open tickets or reply.
- `POST /api/webhooks/twilio/sms` — inbound SMS appended as ticket messages (validate Twilio signatures).

## Behaviour

1. **Verification** — After `PATCH /api/auth/admin/users/<user_id>/verification` succeeds, if `TWILIO_VERIFICATION_SMS_ENABLED` and the user has a normalizable `phone_number`, an SMS is sent. Errors are logged only; the HTTP response stays `200` with the same JSON body.

2. **Support** — After `POST /api/support/admin/tickets/<id>/messages` with `is_internal_note: false`, if `TWILIO_SUPPORT_SMS_ENABLED`, the ticket requester receives a short message plus a deep link (`?supportTicket=<uuid>`) to the role-appropriate dashboard HTML.

## Phone numbers

Numbers are normalized with a Kenya-first heuristic (`0…` → `+254…`, `254…` → `+254…`). For other countries, store E.164 (`+…`) in `users.phone_number`.

## Compliance and ops

- Register appropriate **transactional** / **Content** templates with Twilio and carriers for your markets (e.g. Kenya).
- Do not log full message bodies or tokens at INFO in production.
- For Phase 2 inbound webhooks, use [Twilio request validation](https://www.twilio.com/docs/usage/webhooks/webhooks-security) and expose a public HTTPS URL (e.g. Vercel).

## Dependency

Python package: `twilio` (see `requirements.txt`).
