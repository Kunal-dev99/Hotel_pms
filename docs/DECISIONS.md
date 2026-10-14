# Architecture Decision Log

Format: `D-<n> Title` — **Status** · **Date** · decision · rationale · consequences.
Owner: solution-architect agent (with human approval). Entries are append-only; to change a decision, supersede it with a new entry.

---

## D-0 Project context manager

- **Status:** Installed (in-repo, minimal). Revisit if the Fusion PCS distribution becomes available.
- **Date:** 2026-10-14
- **Decision:** No external PCS distribution was available, so a stdlib-only PCS lives at `tools/pcs/pcs.py`. It writes an append-only `.project-memory/events.jsonl` plus a derived SQLite FTS5 index. `.project-memory/` is gitignored.
- **Consequences:** Memory is per-machine. Shared decisions must also be recorded here. The index can always be rebuilt with `python tools/pcs/pcs.py reindex`.

## D-01 Additive, never destructive

- **Status:** Active (standing rule)
- **Date:** 2026-10-14
- **Decision:** Gaps are closed by ADDING columns, tables, endpoints, pages and settings alongside what already exists. Forward migrations are additive-only: no `DROP` of a table, column, constraint or index, and no destructive `ALTER`.
- **Exceptions:** An exception must be named in its own decision entry with the reason, the data impact and the rollback plan, and it needs human approval before merge.

## D-02 Reversibility as a design constraint

- **Status:** Active (standing rule)
- **Date:** 2026-10-14
- **Decision:** Every schema change ships with a tested `downgrade()`, and the upgrade → downgrade → upgrade round trip runs before merge. Lifecycle actions (cancel, archive, deactivate, close) hide data and never delete it; use status/`archived_at`-style columns. New behaviour ships behind a migration or a setting, so turning it off restores the previous behaviour exactly.

## D-03 Isolation of in-progress work

- **Status:** Active (standing rule)
- **Date:** 2026-10-14
- **Decision:** Every feature is built in a separate git worktree outside the running app folder, against a copy of the database (e.g. `hotel_pms_<feature>`), never against the live dev DB.
- **Note:** Worktrees should live outside OneDrive, e.g. `C:\dev\worktrees\ai_hotel_pms-<feature>`, to avoid sync locks on `node_modules`/`.venv`.

## D-04 Fail closed on authorization

- **Status:** Active (standing rule)
- **Date:** 2026-10-14
- **Decision:** A request with no matching permission is denied; the default is deny. Row scoping runs as a repository-layer query filter derived from the authenticated principal (tenant_id, permitted property_ids). It is never taken from request parameters, so a crafted request cannot bypass it. The AI harness is a principal like any other and only calls typed, permission-checked services.

## D-05 Stack baseline

- **Status:** Active
- **Date:** 2026-10-14
- **Decision:** Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16 + Alembic. Frontend: Next.js 14 (App Router) + TypeScript + Tailwind. Design system: shadcn/ui defaults. Frontend API types are generated from the backend OpenAPI schema.

## D-06 Deployment target: Oracle Cloud Infrastructure (OCI)

- **Status:** Active. Service selection is open.
- **Date:** 2026-10-14
- **Decision:** Deploy on OCI. Candidate services are OCI Database with PostgreSQL (managed PG 16), with backend/frontend containers on OCI Container Instances or OKE, and OCI Vault for secrets. The concrete service choice will be recorded as a later decision before cycle 6 (Pilot).

## D-07 Tenancy and identity model

- **Status:** Active
- **Date:** 2026-10-14
- **Decision:** A **tenant is a hotel group**, and properties (hotels) belong to a tenant. Every tenant-owned row carries `tenant_id`, and property-scoped rows also carry `property_id`. One `person_id` is reused across all roles within a tenant (guest, staff, contact), so guest profiles are shared across that tenant's properties. Cross-tenant sharing is not allowed.
- **Rationale:** This answers the open question in architecture doc §8 ("tenant = group or property"). It is reversible because a single-property group is just a tenant with one property.

---

<!-- Never renumber existing IDs. New decisions are appended as D-05, D-06, … -->
_Never renumber existing IDs. New decisions are appended in sequence (next free ID: **D-08**)._
