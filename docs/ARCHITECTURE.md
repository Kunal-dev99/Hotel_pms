# Architecture — AI Hotel Booking & Operations Platform (live)

**Goal:** an AI receptionist (text, WhatsApp, voice) built on an internally owned, multi-property PMS for ten hotels. The PMS is the system of record for inventory, rates and reservations.

**Signed-off version:** `AI_Hotel_Platform_Management_Visual_Architecture_and_Cycles_v5_Internal_PMS.docx` (project root). Its text is extracted to [`architecture_spec.txt`](architecture_spec.txt) for grep; diagrams are not included in the extract. **This file is the live version.** When the two disagree, raise it as a decision entry.

> Status: stub. The module map below is a proposal derived from spec §15. Tables and endpoints are filled in phase by phase by the solution-architect.

## Stack (D-05, D-06)

| Layer | Choice |
|---|---|
| Backend | FastAPI · Pydantic v2 · SQLAlchemy 2.0 async · asyncpg · Alembic |
| Database | PostgreSQL 16 |
| Frontend | Next.js 14 App Router · TypeScript · Tailwind · shadcn/ui |
| API contract | Backend OpenAPI → generated TS types (`openapi-typescript`) |
| Channels | Twilio WhatsApp, Twilio Voice / Conversation Relay (cycles 3–4) |
| Deploy | Oracle Cloud Infrastructure (OCI). Service choice is open (see D-06) |

## Core principles (from spec §1, §3)

- **The LLM interprets and proposes, the harness constrains and validates, and deterministic PMS services execute.** The PMS service response is the only authoritative confirmation.
- The AI harness is a principal that can only call typed, permission-checked services (D-04).
- Every reservation mutation carries actor/channel, timestamp, property scope, idempotency key and an audit event.
- Tenancy: tenant = hotel group → properties. Every row carries `tenant_id` (+ `property_id`), and one `person_id` is used across roles (D-07).

## Layering (backend)

```
Router  →  Service  →  Repository  →  Database
(HTTP)     (rules,      (all SQL,      (models,
            txns,        principal      Alembic)
            events)      scope filter)
```

Cross-module calls go service → service only. Every module has `router.py, schemas.py, models.py, service.py, repository.py, events.py, constants.py`.

## Module map (proposed)

| Module | Key tables (proposed) | Endpoint prefix | Cycle |
|---|---|---|---|
| `core` (db, auth, audit, settings) | `audit_events`, `settings` | — | 1 |
| `tenancy` | `tenants`, `properties`, `property_policies`, `tax_fee_rules` | `/api/v1/tenants`, `/api/v1/properties` | 1 |
| `iam` (staff & access) | `persons`, `staff_members`, `roles`, `permissions`, `role_permissions`, `staff_property_access` | `/api/v1/auth`, `/api/v1/staff` | 1 |
| `inventory` | `room_types`, `rooms`, `inventory_days`, `room_blocks` | `/api/v1/properties/{id}/room-types`, `/rooms`, `/availability` | 1 |
| `rates` | `rate_plans`, `rate_prices`, `rate_restrictions` | `/api/v1/properties/{id}/rate-plans`, `/quotes` | 1 |
| `reservations` | `reservations`, `reservation_rooms`, `reservation_status_history`, `idempotency_keys` | `/api/v1/reservations` | 1 |
| `guests` (CRM) | `guest_profiles` (→ `persons`), `guest_consents` | `/api/v1/guests` | 1 |
| `ai_harness` | `conversations`, `conversation_turns`, `tool_invocations` | `/api/v1/assistant` | 2 |
| `channels` (WhatsApp/Voice) | `channel_messages`, `call_sessions`, `notification_deliveries` | `/api/v1/webhooks/twilio/*` | 3–4 |
| `exceptions` | `exception_records`, `exception_acknowledgements` | `/api/v1/exceptions` | 2–3 |
| `frontdesk` | `stays`, `room_assignments` | `/api/v1/frontdesk` | 5 |
| `housekeeping` | `room_status_log`, `housekeeping_tasks`, `maintenance_tickets` | `/api/v1/housekeeping`, `/api/v1/maintenance` | 5 |
| `billing` | `folios`, `folio_lines`, `payments` (provider refs only), `invoices` | `/api/v1/folios` | 5 |
| `guest_services` | `outlets`, `service_requests` | `/api/v1/services` | 5 |
| `reports` | read models / views | `/api/v1/reports` | 5 |

## Open questions (spec §8)

- Is external PMS coexistence or migration needed for any hotel?
- Booking/amend/cancel/escalation policies need approval.
- Twilio templates, voice languages, transfer destinations and recording retention.
- Model benchmarking before production selection.
- The OCI service selection (D-06).
