# Karigar — Architecture, Schema & API Reference

> **Living document.** Updated at the end of every milestone. It explains the
> database schema, the REST API, and how the frontend and backend connect.

Last updated: **Milestone 8** (all milestones complete; API on Django Ninja).

> **API framework:** the API is built with **Django Ninja** + Pydantic schemas
> (not DRF). JWT auth is provided by **django-ninja-jwt**. Interactive OpenAPI
> docs are at `/api/v1/docs`.

---

## 1. System overview

```
┌────────────┐     HTTPS      ┌──────────────┐    SQL     ┌────────────┐
│  Browser   │ ─────────────▶ │ nginx (SPA)  │            │ PostgreSQL │
│ React SPA  │   /api, /media │  + reverse   │ ─────────▶ │            │
└────────────┘ ◀───────────── │   proxy      │            └────────────┘
                    JSON       └──────┬───────┘
                                      │ /api
                                      ▼
                               ┌──────────────┐   tasks   ┌────────────┐
                               │ Django + DRF │ ────────▶ │   Redis    │
                               │  (Gunicorn)  │           │  (broker)  │
                               └──────┬───────┘           └─────┬──────┘
                                      │                         │
                                      ▼                   ┌─────┴──────┐
                               object storage (S3)        │ Celery     │
                               for media / photos         │ worker+beat│
                                                          └────────────┘
```

- **One origin in the browser.** nginx serves the built SPA and proxies `/api`
  and `/media` to Django, so CORS stays simple in production. In dev, Vite's
  proxy does the same.
- **Auth is stateless JWT.** The SPA stores access/refresh tokens (Zustand +
  localStorage) and sends `Authorization: Bearer <access>`. A response
  interceptor silently refreshes on 401.
- **API layer = Django Ninja.** One `NinjaAPI` instance (`config/api.py`) mounts
  four app routers. `JWTAuth` is the global default auth; public endpoints opt
  out with `auth=None`. Pydantic `Schema` classes replace DRF serializers; role
  checks are helper functions on `request.auth` (`apps/common/auth.py`).

---

## 2. Apps (backend)

| App | Responsibility | Milestone |
|-----|----------------|-----------|
| `common` | Abstract base models, pagination, JSON error envelope, role permissions, health check | M1 |
| `accounts` | `Shop`, custom `User` (roles), `AppSetting`, auth endpoints, manager management | M1 |
| `ledger` | `KarigarProfile`, `Ornament`, `Order`, `GoldEntry`, `CashEntry`, balances | M2–M4 |
| `reports` | Cash/Gold reports, Excel + PDF export | M6 |
| `backups` | `BackupConfig`, `BackupLog`, manual + scheduled email backups | M7 |

---

## 3. Data model

### 3.1 Conventions
- **All timestamps are timezone-aware and stored in `Asia/Kathmandu` (UTC+05:45).**
- **Dates are stored in AD (Gregorian).** BS is derived at display time only —
  never the source of truth.
- Abstract bases (in `common.models`):
  - `TimeStampedModel` → `created_at`, `updated_at`.
  - `AuthoredModel` → adds `created_by`, `updated_by` (FK to User).
- Financial records will additionally carry `django-simple-history` audit
  trails (from M7).

### 3.2 Entities implemented so far (M1)

**Shop** (`accounts.Shop`)
| Field | Type | Notes |
|-------|------|-------|
| name | CharField | |
| address | CharField | optional |
| contact | CharField | optional |

Single-shop MVP, but every user/record references a shop so multi-shop is a
non-breaking extension later.

**User** (`accounts.User`, `AUTH_USER_MODEL`)
| Field | Type | Notes |
|-------|------|-------|
| username | CharField, unique | login field |
| email | EmailField, unique/nullable | |
| full_name | CharField | |
| role | choice: `owner` / `manager` / `karigar` | drives all permissions |
| shop | FK → Shop | |
| is_active, is_staff, is_superuser | bool | |

Helper properties: `is_owner`, `is_manager`, `is_karigar`, `is_staff_role`
(owner or manager).

**AppSetting** (`accounts.AppSetting`)
| Field | Type | Notes |
|-------|------|-------|
| shop | OneToOne → Shop | |
| calendar_preference | choice: `BS` / `AD` | **display only**; editable by owner+manager (UI in M6) |

### 3.3 Planned entities (M2–M7)
`KarigarProfile` (1:1 with a karigar User: phone, location, photo, opening
gold/cash Dr-Cr, joined date, active) · `Ornament` · `Order` (nullable,
non-unique `order_number`, remarks) · `GoldEntry` (gross_weight_g, carat 22/24,
computed `net_weight_g`, direction dr/cr, photo, remarks) · `CashEntry`
(amount_npr, direction, remarks) · `BackupConfig` · `BackupLog`.

---

## 4. Roles & permissions

| Capability | Owner | Manager | Karigar |
|------------|:-----:|:-------:|:-------:|
| Super-admin (all data/actions) | ✅ | — | — |
| Create/manage manager accounts | ✅ | — | — |
| Manage karigars & ornaments | ✅ | ✅ | — |
| Gold/cash entries, edit records | ✅ | ✅ | — |
| View all ledgers & totals | ✅ | ✅ | — |
| Reports & exports | ✅ | ✅ | — |
| Change calendar (BS/AD) | ✅ | ✅ | — |
| Configure & run backups | ✅ | ✅ | — |
| View **own** ledgers (read-only) | — | — | ✅ |

Enforcement (backend, not just UI):
- Role helpers in `common.auth`: `require_staff`, `require_owner`,
  `require_roles` raise `HttpError(403)`; `JWTAuth` sets `request.auth` = User.
- Karigar object-level scoping is enforced in each endpoint's queryset via
  `_scope(request, qs)` in `ledger/api.py`, so a karigar only ever reads their
  own orders / gold / cash rows.

---

## 5. API reference

Base path: **`/api/v1/`**. All responses are JSON. Errors use a consistent
envelope:

```json
{ "error": { "code": 403, "message": "…", "detail": null } }
```

Lists are paginated — `?page`, `?page_size` (max 200) — returning
`{"results": [...], "count": n}`. Interactive docs: `/api/v1/docs`.

### 5.1 Auth & accounts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health/` | public | Liveness + DB readiness |
| `POST` | `/auth/login/` | public | `{username,password}` → `{access,refresh,user}` (throttled 10/min) |
| `POST` | `/auth/refresh/` | public | `{refresh}` → `{access,refresh}` (rotating) |
| `GET` | `/auth/me/` | any | Current user |
| `POST` | `/auth/change-password/` | any | `{old_password,new_password}` |
| `GET` | `/auth/settings/` | any | Shop calendar preference (BS/AD) |
| `PATCH` | `/auth/settings/` | staff | Change calendar preference |
| `GET/POST` | `/auth/managers/` | owner | List / create managers |
| `GET/PATCH` | `/auth/managers/{id}/` | owner | Retrieve / update a manager |
| `POST` | `/auth/managers/{id}/activate/` · `/deactivate/` | owner | Toggle active |

**JWT:** access 30 min, refresh 7 days (rotating). Tokens embed `role` +
`full_name`.

### 5.2 Ledger

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET/POST` | `/karigars/` | staff | List (search) / create (multipart: photo). Balances computed. |
| `GET/PATCH/DELETE` | `/karigars/{id}/` | staff | Get / JSON-patch / soft-delete (deactivate) |
| `POST` | `/karigars/{id}/photo/` | staff | Upload/replace photo (multipart) |
| `POST` | `/karigars/{id}/set_password/` · `/activate/` | staff | |
| `GET` | `/karigars/{id}/history/` | staff | Audit changelog |
| `GET` | `/me/karigar/` | karigar | Own profile + balances (self-view) |
| `GET/POST` | `/ornaments/` · `GET/PATCH /ornaments/{id}/` | staff | |
| `GET/POST` | `/orders/` · `GET/PATCH /orders/{id}/` (+ `/history/`) | staff write, karigar read own | filters: `karigar,status,order_number,ornament` |
| `GET/POST` | `/gold-entries/` (+ `{id}/`, `/photo/`, `/history/`) | staff write, karigar read own | create multipart; net weight auto-computed. Filters: `karigar,direction,carat,order,order_number,date_from,date_to,ordering` |
| `GET/POST` | `/cash-entries/` (+ `{id}/`, `/history/`) | staff write, karigar read own | JSON. Filters: `karigar,direction,order,date_from,date_to,ordering` |

**Uploads:** create endpoints accept multipart (`Form` + `File`); edits are JSON
PATCH with photos via the dedicated `/photo/` sub-endpoint — because Django does
not parse multipart bodies on PATCH.

### 5.3 Reports & backups

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/reports/gold/` · `/reports/cash/` | staff | `?fmt=json\|excel\|pdf & date_from & date_to & karigar`. Dates render in the shop calendar. |
| `GET/PATCH` | `/backups/config/` | staff | primary/secondary paths, frequency (off/daily/weekly/monthly), enabled |
| `GET` | `/backups/` | staff | Recent backups — **read from storage manifests, not the DB** |
| `POST` | `/backups/run/` | staff | Manual backup (Celery, or inline if broker down) |
| `POST` | `/backups/upload/` | staff | Manual upload of a `.dump`/`.dump.enc` (validated, tagged `manual_upload`) |
| `GET` | `/backups/audits/` | staff | Restore audit trail |
| `POST` | `/backups/restore/` | **owner** | Restore — owner-only, re-auth password + typed `RESTORE`, auto safety backup |

---

## 6. Frontend structure

```
src/
├── App.jsx               # role-gated route table
├── lib/
│   ├── api.js            # axios: JWT + silent-refresh interceptors, multipart handling
│   ├── date.js           # formatDate(value, calendar) — single BS/AD helper
│   └── format.js         # NPR / grams / signed Dr-Cr balance formatting
├── store/auth.js         # tokens + user (persisted); settings.js — calendar pref
├── hooks/useFetch.js     # GET with loading/error/refresh (skips when params===null)
├── components/           # Layout (responsive nav), ProtectedRoute, ui kit (Modal, etc.)
└── pages/                # Login, Dashboard, Karigars, Ornaments, Gold, Cash,
                          # Managers, Reports, Backups, Settings
```

**Calendar handling.** **BS is the default** calendar. `formatDate(adValue,
calendar)` renders dates as `27 Magh 2080` (BS) or `2024-02-10` (AD). Date
inputs submit AD ISO; when the preference is BS the picker shows a BS hint.
Reports also offer a **month + year** picker (BS or AD months) that computes the
AD range for that whole month (`monthRangeToApi`) and disables the free range.
The API contract is always AD ISO-8601; BS is presentation only.

---

## 7. Conventions & decisions

- **API framework:** Django Ninja + Pydantic (per project directive — no DRF).
  Schemas live in each app's `schemas.py`; routers in `api.py`; the single
  `NinjaAPI` is assembled in `config/api.py`.
- **PDF engine:** WeasyPrint (HTML→PDF) over ReportLab — table-heavy reports are
  easier as HTML/CSS templates, reusable for on-screen previews.
- **Scheduler:** Celery + Redis + django-celery-beat; a daily beat task runs any
  backup config that is due (weekly/monthly gate).
- **Backups (resilient):** `pg_dump -Fc` streamed to memory, Fernet-encrypted
  with a master key from the **env** (never in the DB, never emailed), written
  to **bind-mounted host folders** (primary disk + best-effort removable drive)
  — NOT Docker named volumes, so `docker volume rm`/prune can't touch them. Each
  file gets a `manifest.json` (timestamp, size, SHA-256, app sha, source,
  destinations). The **Recent backups list reads those manifests from storage**,
  not the DB, so it survives a full volume/DB wipe. Manual upload validates the
  pg_dump magic bytes. **Restore** (owner-only, re-auth + typed confirm) always
  takes a non-skippable `pre_restore_safety` backup first, then `pg_restore
  --clean --single-transaction` (atomic) over the live DB, and is audited.
  pg client and server are both major 17 so dumps restore cleanly. The
  destination layer is a generic contract (`LocalPathDestination`) so a cloud
  bucket is a drop-in third option later.
- **Gold math:** `net_weight = gross_weight × (carat / 24)`; 22kt uses 22/24
  exactly. `net_weight_g` is computed and **stored**; editing gross/carat
  recomputes it.
- **Balances (signed):** `+` = net **Dr** (karigar holds shop asset), `−` = net
  **Cr** (shop owes karigar). Opening balances seed the running totals.
- **Money:** NPR `Decimal` (2dp). **Weights:** grams `Decimal` (3dp).
- **Karigar credentials:** on create, username (slug of the name, made unique)
  and password auto-generate when not supplied; the plaintext password is
  returned **once** in the create response so the manager can share it (also
  re-settable, and shown in plain text, via reset-password).
- **Ornament names:** unique per shop **case-insensitively** (DB `Lower(name)`
  constraint + a friendly API check).
- **Ledgers & reports (two-column Dr/Cr):** cash uses **Debit / Credit** amount
  columns; gold uses **Gross**, **Net Dr**, **Net Cr** columns. The **opening**
  balance (per karigar, even when zero), the per-column **totals**, and the
  **closing** balance all render as highlighted rows with values sitting in
  their own columns — in the ledger tables, the report preview, and Excel/PDF.
- **Karigar credentials:** username auto-generates from the name; the password
  auto-generates and is **stored in plaintext** (`plain_password`) so owner/
  manager can view/copy it on the Karigars page and re-share on request. Exposed
  only on the staff-only karigar endpoints. (Security trade-off chosen for this
  internal shop tool.)
- **Dates in forms:** a calendar-aware `DateInput` shows a **BS** year/month/day
  picker when the shop calendar is BS (converting to AD for the API) and a native
  AD picker otherwise. Reports also accept a BS/AD **month + year** period.
- **Ornament quick-add:** the receive-gold form has a `+` that opens a small
  dialog to create an ornament and auto-selects it, without losing the form.
- **Ledger search:** gold & cash lists accept a free-text `search` across
  karigar name, remarks, ornament, and order number.
```
