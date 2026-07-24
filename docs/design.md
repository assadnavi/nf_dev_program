# Technical Design — Funding Program Automation

Companion to [`requirements.md`](./requirements.md). Describes how the functional requirements are implemented: data model, state handling, storage, and access control. Implementation language/framework is intentionally not decided yet — nothing below depends on that choice.

## 1. Guiding principles

- Single deployable app, single SQLite database file. No external services (no DB server, no object storage, no email service).
- The database file is the entire persisted state of the system, including attached documents (stored as BLOBs) — one file to back up.
- Keep the schema small and literal; avoid generic/config-driven abstractions until a concrete future need is identified (see [requirements.md §6](./requirements.md)).

## 2. Data model

### `admins`

| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| username | TEXT, unique | |
| password_hash | TEXT | salted hash (e.g. bcrypt/argon2), never plaintext |
| created_at | TEXT (ISO 8601) | |

No self-registration — the first admin account is created via a one-off bootstrap step (seed script / CLI command), not a public sign-up page. Additional admins are created by an existing admin from within the app.

Designed so a future SSO integration only needs to add an alternate lookup path (e.g. an `sso_subject` column) rather than restructure this table — no such column is added now, since SSO isn't happening yet.

### `programs`

| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| deadline | TEXT (ISO 8601 datetime) | gates new submissions only, see §3 |
| created_by | INTEGER, FK → admins.id | |
| created_at | TEXT (ISO 8601) | |

No `status`/`draft` column — a program is open for submissions the instant it's created; whether it's still accepting submissions is computed as `now < deadline`, not stored.

### `applications`

| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| program_id | INTEGER, FK → programs.id | |
| access_token | TEXT, unique | random, unguessable (e.g. 32 bytes, CSPRNG, URL-safe encoding) — the applicant's only way back into their own application, reused unchanged across every later stage (upfront invoice, final invoice) |
| email | TEXT | as entered by the applicant, not validated against any list |
| proposal_filename | TEXT | original filename of the initial attachment |
| proposal_mimetype | TEXT | |
| proposal_blob | BLOB | the project proposal document |
| state | TEXT | one of `submitted`, `accepted`, `refused` only — see §3 for why the later stages aren't additional `state` values |
| decision_comment | TEXT, nullable | optional, free text, set at Accept/Refuse time |
| decided_by | INTEGER, nullable, FK → admins.id | |
| decided_at | TEXT (ISO 8601), nullable | |
| upfront_invoice_filename | TEXT, nullable | set once the upfront invoice is uploaded |
| upfront_invoice_mimetype | TEXT, nullable | |
| upfront_invoice_blob | BLOB, nullable | |
| upfront_invoice_received_at | TEXT (ISO 8601), nullable | |
| work_approved_by | INTEGER, nullable, FK → admins.id | set when Admin confirms the funded work is done |
| work_approved_at | TEXT (ISO 8601), nullable | |
| work_approval_comment | TEXT, nullable | optional, free text — mirrors `decision_comment`'s pattern *(pending your confirmation, see §3)* |
| final_invoice_filename | TEXT, nullable | set once the final invoice is uploaded |
| final_invoice_mimetype | TEXT, nullable | |
| final_invoice_blob | BLOB, nullable | |
| final_invoice_received_at | TEXT (ISO 8601), nullable | also the true completion timestamp of the whole application |
| submitted_at | TEXT (ISO 8601) | |

No `whitelist`/organization table — per requirements, email legitimacy is judged manually by Admin during review, not enforced by the system.

## 3. Application state machine

`state` only stores the one true branch point: `submitted → accepted`, or `submitted → refused` (terminal). Everything after acceptance is a **linear** sequence with no further branching, so instead of adding more `state` values, it's tracked as a run of nullable columns evaluated in order — each one either isn't set yet (blocking the next step) or is set (unlocking it):

1. `state = accepted`, `upfront_invoice_received_at IS NULL` → display: **Accepted (Upfront Invoice Pending)**
2. `upfront_invoice_received_at IS NOT NULL`, `work_approved_at IS NULL` → display: **Upfront Invoice Received (Awaiting Work Approval)**
3. `work_approved_at IS NOT NULL`, `final_invoice_received_at IS NULL` → display: **Work Approved (Final Invoice Pending)**
4. `final_invoice_received_at IS NOT NULL` → display: **Complete** (terminal — this is now the real end)

This extends the same modeling approach already agreed for the Accepted/Invoice-Pending split — a single `accepted` state plus derived display label — rather than switching approaches partway through.

Transitions:
- `submitted → accepted` / `submitted → refused`: admin decision, optional `decision_comment`, sets `decided_by`/`decided_at`.
- Upfront invoice uploaded: automatic, via the applicant's access-token link (requires `state = accepted`). Sets `upfront_invoice_*` and `upfront_invoice_received_at`.
- Work approved: **manual admin decision** (requires `upfront_invoice_received_at` set, `work_approved_at` still null). Sets `work_approved_by`/`work_approved_at` (+ `work_approval_comment` if confirmed). This is the one non-automatic step in the whole post-acceptance sequence.
- Final invoice uploaded: automatic, via the same access-token link (requires `work_approved_at` set). Sets `final_invoice_*` and `final_invoice_received_at` — application is now `Complete`.
- No transition ever leaves `refused` or reopens a `Complete` application.

## 4. Access model

Two separate access paths, no shared session concept between them:

**Admin access** — authenticated, session-cookie based (username/password against `admins`). Full read/write access to programs and applications, including viewing every application regardless of state (per requirements §3.3, nothing is ever hidden).

**Applicant access** — no accounts, two distinct unauthenticated entry points:
1. `POST /apply/{programId}/` — public, open to anyone, only guarded by `now < programs.deadline`. Creates one `applications` row, generates the `access_token`, stores `submitted` state. One-shot: no corresponding edit/update endpoint exists.
2. `GET/POST /application/{accessToken}/` — reopens a specific application by token, at any point in its life. What's shown depends on the derived status from §3: an upfront-invoice upload form once `Accepted (Upfront Invoice Pending)`, a plain "awaiting work approval" message once `Upfront Invoice Received`, a final-invoice upload form once `Work Approved`, and a plain completion message once `Complete`. Possession of the token is the only credential at every stage — no secondary email check, and no new token is ever issued. This route is only ever reached because Admin manually copied the link from the application's detail page and sent it to the applicant — the app itself never emails it out.

## 5. Admin views

- **Program list** (`/dashboard/`) — every program with name, deadline, and a count of its applications broken down by state.
- **Program detail** (`/dashboard/programs/{id}/`) — the list of applications belonging to that program, one row each, showing: email, submission date, and current status: `Submitted`, `Accepted (Upfront Invoice Pending)`, `Upfront Invoice Received (Awaiting Work Approval)`, `Work Approved (Final Invoice Pending)`, `Complete`, or `Refused`. Filterable/sortable by status so Admin can, for example, pull up only the still-`Submitted` ones to review, or only the ones sitting in `Upfront Invoice Received` waiting on a work-approval decision.
- **Application detail** (`/dashboard/applications/{id}/`) — full record: email, proposal document (view/download), current status, decision controls (Accept/Refuse + optional comment) when still `submitted`, the unique access-token link (once accepted, so Admin can copy it into their own email to the applicant), the upfront invoice document (view/download) once uploaded, a **work approval control** once the upfront invoice is received (marks `work_approved_by`/`work_approved_at`, + optional comment — pending confirmation, see §3), the final invoice document (view/download) once uploaded, and a **status history** section.

**Status history**: reconstructed directly from the timestamp columns already on the `applications` row — no separate events table needed for this. Displayed as a simple chronological list, each entry shown only once its timestamp is set:
  - Submitted — `submitted_at`
  - Accepted / Refused — `decided_at`, with `decision_comment` if one was given
  - Upfront invoice received — `upfront_invoice_received_at`
  - Work approved — `work_approved_at`, with `work_approval_comment` if one was given
  - Final invoice received (Complete) — `final_invoice_received_at`

This is how Admin knows an application's status at any time — it's always visible in the program detail list, reiterated on the application's own detail page, and now accompanied by the timeline of when each transition happened.

## 6. File handling

- Initial proposal: accepts `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`; no size limit or content inspection beyond MIME/extension.
- Upfront invoice and final invoice: both accept `application/pdf` only (per requirements §3.4).
- All three are stored as BLOBs directly in the `applications` row (see §1) and streamed back on download/view rather than served as static files.

## 6a. UI text

Every piece of user-facing text (page headings, labels, button captions, flash messages, form errors, status labels) lives in `funding/site_text.py` as a single nested dict, `SITE_TEXT` — not hardcoded in templates or views. Editing that one file changes the live site immediately (Django's dev-server autoreloader watches all `.py` files, no other change needed).

- Static entries (no embedded variables) are exposed to every template as `text.section.key` via a context processor (`funding/context_processors.py`), so most templates just reference `{{ text.program_list.empty }}` directly.
- Entries containing embedded Django template syntax (e.g. `"Applications close on {{ program.deadline }}."`) need the `{% text "section.key" %}` template tag instead (`funding/templatetags/site_text_tags.py`) — it renders the stored fragment through Django's own template engine against the current page's context, so the embedded `{{ variable }}` resolves normally. Plain `{{ text.section.key }}` would just print that fragment as inert text.
- Python-side text (flash messages, `ValueError` messages raised by the model's state-transition methods, `Http404` messages) is sourced the same way via `get_text('section.key')` (static) or `render_text('section.key', **vars)` (needs variable substitution, e.g. the programme name in "Programme created" messages).

## 7. Non-functional notes

- Expected scale (~200 applications/year) means no indexing/partitioning concerns; a handful of indexes (`applications.program_id`, `applications.access_token`) are enough.
- Backup = copy the SQLite file. No separate backup path for documents since they live inside it.
- SQLite's own locking handles concurrent writes safely (the concern flagged earlier about flat JSON files doesn't apply here).

## 7a. Deployment (Docker)

The app runs in a single Docker container (`Dockerfile` + `docker-compose.yml`), matching the constraint already established in §7: SQLite needs one persistent instance with durable disk, not multiple ephemeral replicas — a single container with a mounted volume is a direct fit, and portable to any VPS/cloud host without re-tooling.

- **Image** vs **data** are kept strictly separate: the `data/` directory (holding `db.sqlite3`) is excluded from the build via `.dockerignore` and never baked into the image. At runtime the container reads/writes it via a **bind mount** — `./data:/data` in `docker-compose.yml` — mapping the project's own `data/` directory straight into the container. This is a deliberate choice over a Docker-managed named volume: a named volume's backing file lives inside Docker's own internal storage, invisible from the project folder and only inspectable via `docker exec`/`docker cp` — confusing in practice (this was tried first, then switched after exactly that confusion came up). The bind mount means there is only ever **one** `data/db.sqlite3`, directly visible and copyable with normal tools, and it's the same file whether the app is run via Docker or plain local `manage.py runserver`. Rebuilding the image or fully recreating the container never touches it, since it isn't part of the image at all — verified by tearing the container down completely (`docker compose down`) and confirming the data was still there after `docker compose up -d`.
- **Startup** (`docker-entrypoint.sh`): runs `manage.py migrate --noinput` (idempotent, safe every start) then execs `gunicorn` — a real WSGi server, not the dev-only `manage.py runserver`.
- **Config via environment**, read in `config/settings.py` with dev-friendly fallback defaults so plain local `manage.py runserver` usage needs no environment setup at all:
  - `DJANGO_SECRET_KEY` — falls back to the original dev-only key
  - `DJANGO_DEBUG` — falls back to `True`
  - `DJANGO_ALLOWED_HOSTS` — comma-separated, falls back to `localhost,127.0.0.1`
  - `DJANGO_DB_PATH` — falls back to `BASE_DIR / 'data' / 'db.sqlite3'` (the plain local file, kept in a dedicated `data/` directory rather than the project root); Docker sets this to `/data/db.sqlite3`, which the bind mount maps back to that same local file
- These are supplied via a local `.env` file (`env_file:` in `docker-compose.yml`), gitignored and dockerignored — never committed, never baked into the image. **Caveat hit during setup**: Compose applies shell-style `$VAR` interpolation to `.env` values, so a secret key containing a literal `$` gets silently corrupted unless escaped as `$$`, or (the approach taken here) the generated key simply avoids `$` entirely.
- Admin bootstrap is still the manual one-off step described in §2 (`manage.py createsuperuser`, run once via `docker compose exec web ...`) — no auto-creation via env vars, consistent with the existing design.
- Static file serving (e.g. for Django's own `/admin/` site) is not set up — the app's own pages don't reference any local static assets (Bootstrap loads from a CDN), so this was left out rather than adding whitenoise/nginx for a page the app doesn't actually use.

## 7b. Coolify readiness (code-side changes only — platform setup is a separate step)

Two settings were added in `config/settings.py` ahead of deploying to Coolify (a self-hosted PaaS that terminates HTTPS via its own reverse proxy and forwards plain HTTP to the container). Both are no-ops for local/plain Docker use and only take effect once actually deployed behind such a proxy:

- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` — without this, Django can't tell a proxied request was originally HTTPS.
- `CSRF_TRUSTED_ORIGINS` — env-driven (`DJANGO_CSRF_TRUSTED_ORIGINS`, comma-separated), empty by default. Needs to be set to the real deployed origin (e.g. `https://yourapp.example.com`) once there is one.

Deliberately **not yet done** (next step, once these are confirmed working locally): initializing a git repository (Coolify deploys from a git remote), and the Coolify-side configuration — persistent storage for `/data` (a Coolify-managed volume, not the local bind-mount-to-repo-path approach, since that's tied to the git checkout and isn't reliable across redeploys on a platform that re-pulls code), environment variables entered in Coolify's UI, domain/HTTPS, and replica count fixed at 1 (SQLite assumes a single writer).

## 8. Future extensibility (prototype disclaimer)

This is a prototype; requirements and design are expected to change. Three changes have been named as likely, though not yet scoped:

- **Email notifications** — currently every state transition (submit, accept/refuse, either invoice upload, work approval) is silent. Nothing is built for this now, but implementation should route each transition through one clear operation each (e.g. a single `acceptApplication(...)`, `refuseApplication(...)`, `submitApplication(...)`, `uploadUpfrontInvoice(...)`, `approveWork(...)`, `uploadFinalInvoice(...)`) rather than inline state updates scattered across handlers — so a notification call can be dropped into one place per transition later instead of requiring a hunt through the codebase.
- **An admin-facing activity/event view** ("latest changes") — not built now, and no events table exists yet. The timestamp columns already on `applications` cover per-application history (see §5's status history); a cross-entity feed of recent activity would need a dedicated append-only log (entity type/id, action, actor, timestamp) if/when this is actually scoped. Not adding that table pre-emptively — it's a clear, contained addition later, not something worth guessing the shape of now.
- **Manual payment tracking for both invoices** — Admin may want to mark each of the upfront and final invoices as "paid" once they've actually sent the money (the payment itself stays outside the system either way). Not built now; the natural addition later is a nullable `upfront_invoice_paid_at` / `final_invoice_paid_at` pair of columns, which doesn't require restructuring anything above.

The intent here is not to pre-build either feature or add generic hooks/plugin points for them, just to keep the state-transition code centralized enough that they stay easy additions rather than refactors.

## 9. Open items

- Language/framework choice — deferred, not required to validate this design.
