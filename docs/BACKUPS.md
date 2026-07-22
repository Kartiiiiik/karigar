# Backup & Restore — Architecture & Full Flow

A deep-dive into the resilient backup/restore system: what it is, how the pieces
fit, the exact code paths, the manifest format, the HTTP API, and a
disaster-recovery runbook.

> **Core principle.** *A backup that lives inside the same Docker volume/host as
> the database is not a backup — it's a second copy of the same single point of
> failure.* Every backup is encrypted and written to a **bind-mounted host
> folder** that Docker does not own and cannot delete with `docker volume rm` /
> `docker system prune`. The list of backups is read from those folders (their
> `manifest.json` files), never from the database — so it survives a total wipe
> of the DB and every Docker volume.

---

## 1. Architecture at a glance

```
                         ┌──────────────────────────────────────────┐
                         │            Backups page (React)            │
                         │  list · run now · upload · restore modal   │
                         └───────────────┬────────────────────────────┘
                                         │ HTTPS  /api/v1/backups/*
                                         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Django (Ninja API)  apps/backups/                                           │
│                                                                             │
│  api.py ──► service.py ──► crypto.py     (Fernet encrypt/decrypt)           │
│               │      │ └─► destinations.py (LocalPathDestination + resolver)│
│               │      └───► subprocess: pg_dump -Fc / pg_restore             │
│               │                                   │                         │
│               │ manifests + audit                 │ TCP 5432                │
│               ▼                                   ▼                         │
│        models: BackupConfig, RestoreAudit    ┌─────────────┐                │
│        (schedule + audit only — NOT the      │  Postgres   │  (named volume │
│         source of truth for the list)        │  (server 17)│   — expendable)│
└───────────────────────────────────────────────────────────────────────────┘
                                         │ write encrypted file + manifest.json
                                         ▼
        ┌───────────────────────────┐        ┌───────────────────────────┐
        │  PRIMARY (required)        │        │  SECONDARY (best-effort)   │
        │  bind mount → host disk    │        │  bind mount → pen drive    │
        │  e.g. D:\SecureBackups     │        │  e.g. E:\Backups           │
        │  *.dump.enc + *.manifest   │        │  (skipped if not attached) │
        └───────────────────────────┘        └───────────────────────────┘
              ▲ outside Docker's control — `docker volume rm` never touches these
```

**Key idea:** the encrypted dumps + manifests live on plain host folders
(bind mounts). The Postgres data volume is *expendable* — it can be destroyed and
recreated, and backups are still discoverable because the app lists them by
scanning the bind-mounted folders.

---

## 2. Component / file map

| File | Responsibility |
|------|----------------|
| `apps/backups/crypto.py` | Fernet encryption using the master key from the env |
| `apps/backups/destinations.py` | `BackupDestination` contract, `LocalPathDestination`, Windows→container path resolution |
| `apps/backups/service.py` | The engine: dump, encrypt, dual-write, manifest, storage listing, upload, restore |
| `apps/backups/models.py` | `BackupConfig` (paths + schedule), `RestoreAudit` (audit trail) |
| `apps/backups/schemas.py` | Ninja/Pydantic request & response schemas |
| `apps/backups/api.py` | HTTP endpoints (config, list, run, upload, restore, audits) |
| `apps/backups/tasks.py` | Celery tasks: `run_backup_task`, `run_scheduled_backups` |
| `apps/backups/management/commands/run_backup.py` | `python manage.py run_backup` |
| `apps/backups/management/commands/backup_key.py` | `python manage.py backup_key` (generate master key) |
| `frontend/src/pages/Backups.jsx` | UI: list, config, upload, restore modal |
| `docker-compose.yml` / `backend/Dockerfile` | bind mounts + `pg_dump`/`pg_restore` client |

---

## 3. Data model (`apps/backups/models.py`)

These tables hold **only** the schedule/destination config and a restore audit
trail. They are deliberately **not** the source of truth for "which backups
exist" — that comes from the manifests on disk.

**`BackupConfig`** (one per shop)
| Field | Notes |
|-------|-------|
| `primary_path` | Destination folder as the operator types it (Windows-style allowed) |
| `secondary_path` | Removable-drive folder (best-effort) |
| `frequency` | `off` / `daily` / `weekly` / `monthly` |
| `enabled` | Whether the scheduler runs it |
| `last_run_at` | Timestamp of the last successful run |

**`RestoreAudit`** (one row per restore attempt)
| Field | Notes |
|-------|-------|
| `performed_by` | User who ran the restore |
| `backup_filename` | The backup that was restored |
| `safety_backup_filename` | The auto-created `pre_restore_safety` backup |
| `status` | `success` / `failed` |
| `message` | Details / error |
| `created_at` | When |

---

## 4. The manifest (`<filename>.manifest.json`)

Written next to **every** backup file at **each** destination that succeeded.
This is what makes recovery possible without the app's database.

```json
{
  "filename": "backup_20260722_150934_090c5c.dump.enc",
  "timestamp": "2026-07-22T15:09:34.528506+00:00",
  "size": 182264,
  "checksum_sha256": "0a0cb834acaced2161deddb5638dff9f9d4224bd3c4e7471c86e4f95d6178491",
  "source": "scheduled",
  "app_sha": "dev",
  "encrypted": true,
  "destinations": { "primary": true, "secondary": false, "secondary_reason": "drive not attached" }
}
```

- **`source`** — one of `scheduled`, `manual`, `manual_upload`, `pre_restore_safety`.
- **`checksum_sha256`** — SHA-256 of the encrypted bytes (integrity of the stored artifact).
- **`destinations`** — which locations the file was confirmed written to.

**Filename format:** `backup_<YYYYMMDD>_<HHMMSS>_<shortsha>.dump.enc` — sortable +
collision-proof (`shortsha` = `secrets.token_hex(3)`), built by
`service._timestamp_name()`.

---

## 5. Encryption (`apps/backups/crypto.py`)

- Uses **Fernet** (AES-128-CBC + HMAC-SHA256) from `cryptography`.
- The master key comes from **`BACKUP_ENCRYPTION_KEY`** (env / secrets manager).
  It is **never** stored in the DB and **never** emailed.
- Dev fallback: if the key is unset, a stable key is derived from
  `SECRET_KEY` (logs a warning). Production must set a real key.
- Key methods: `encrypt_bytes(data) -> bytes`, `decrypt_bytes(token) -> bytes`,
  `generate_key() -> str`.

Generate a key for the env:
```bash
python manage.py backup_key    # prints a fresh Fernet key
```

---

## 6. Destinations & path resolution (`apps/backups/destinations.py`)

Destinations implement a small contract so "local folder" and "cloud bucket" are
interchangeable later:

```python
class BackupDestination:
    def available(self, create=False) -> (bool, reason)
    def write(self, filename, data): ...
    def write_manifest(self, filename, manifest_json): ...
    def list_manifests(self) -> list[str]
    def read(self, filename) -> bytes
    def exists(self, filename) -> bool
```

`LocalPathDestination` is the only implementation today.

### Windows path → container path (`resolve_path`)

The backend runs in a **Linux container**, which cannot write to `D:\SecureBackups`
directly — only to bind-mounted paths. `resolve_path(configured)`:

1. If the path exists as-is (e.g. the command is run on the host) → use it.
2. Otherwise apply the longest matching prefix from **`BACKUP_PATH_MAP`** to map a
   host path to its container bind-mount.
3. Otherwise return it unchanged.

Example `BACKUP_PATH_MAP`:
```json
{ "D:\\SecureBackups": "/app/backups", "E:": "/app/backups-secondary" }
```
So a UI value of `E:\Backups\shop` resolves to `/app/backups-secondary/Backups/shop`.

### Availability semantics (important for the pen drive)

`available(create=True)` (primary) will create the folder if missing.
`available(create=False)` (secondary) requires the folder to **already exist** —
so a *detached* removable drive fails over to "skipped" instead of being silently
recreated **inside** the container (which would put the "off-site" copy back on
the same failure domain).

---

## 7. Full flows

### 7.1 Backup — `service.run_backup(shop, source)`

```
run_backup(shop, source)
 ├─ make_dump()                      # pg_dump -Fc  → archive bytes in memory
 ├─ encrypt_bytes(dump)              # Fernet → encrypted bytes (no plaintext on disk)
 └─ _store(shop, encrypted, source)
      ├─ primary.available(create=True)   → else RAISE (primary is required)
      ├─ primary.write(filename, encrypted)
      ├─ secondary.available()            → if ok: secondary.write(...)  else skip (log reason)
      ├─ build manifest {ts, size, sha256, source, app_sha, destinations}
      ├─ primary.write_manifest(...)
      └─ secondary.write_manifest(...)    (only if secondary succeeded)
 └─ BackupConfig.last_run_at = now()
```

- `make_dump()` runs `pg_dump -Fc -h <host> -p <port> -U <user> -d <db>` via
  `subprocess.run(..., env={PGPASSWORD})` and returns `stdout` (the custom-format
  archive). **Nothing is written to local plaintext disk** — the only copy that
  touches a filesystem is the *encrypted* one on the bind mount.
- "Complete" is only reported after the primary write + manifest succeed; the
  manifest records exactly which destinations hold the file.

### 7.2 Listing — `service.list_backups(shop)`

```
for dest in (primary, secondary):
    for manifest in dest.list_manifests():   # read *.manifest.json off disk
        parse JSON, merge by filename (OR the destination booleans)
return sorted(by timestamp desc)
```

- **Sourced entirely from storage**, so it works even if the DB and Docker
  volumes were destroyed and recreated empty. The DB is never consulted.

### 7.3 Manual upload — `service.ingest_upload(shop, raw, already_encrypted)`

```
if already_encrypted:  plain = decrypt_bytes(raw)      # validate we can decrypt
else:                  plain = raw
assert looks_like_pgdump(plain)   # first 5 bytes == b"PGDMP"  (custom-format header)
encrypted = raw if already_encrypted else encrypt_bytes(plain)
_store(shop, encrypted, source="manual_upload")
```

- Accepts a `.dump` (encrypted on the way in) or `.dump.enc` (validated by
  decrypting). Rejects anything that isn't a real pg_dump custom-format archive.
- After ingest it is **identical** to an automated backup (same store, same
  manifest), just tagged `source: manual_upload`.

### 7.4 Restore — `service.perform_restore(shop, filename, user)`

```
1. safety = run_backup(shop, source="pre_restore_safety")   # NON-SKIPPABLE
2. encrypted = find_backup_bytes(shop, filename)            # primary, else secondary
3. dump = decrypt_bytes(encrypted); assert looks_like_pgdump(dump)
4. restore_dump(dump):
      pg_restore --clean --if-exists --no-owner --no-privileges
                 --single-transaction -d <db>   (reads archive from stdin)
5. RestoreAudit(success)      # or RestoreAudit(failed) on any exception, then re-raise
return (safety_filename, audit)
```

- **Step 1 is mandatory** — the current state is captured before anything is
  touched, so a wrong choice is recoverable.
- **`--single-transaction` makes the restore atomic**: if it fails partway, the
  whole thing rolls back and the live DB is untouched (verified — a version
  mismatch aborted cleanly with the live data intact).
- Restore is **in-place** (chosen for reliability on a single-laptop deployment);
  the safety backup is the real net rather than a DB-swap dance.

---

## 8. HTTP API (`apps/backups/api.py`)

Base path `/api/v1/`. All require authentication; write/restore are role-gated.

| Method | Path | Auth | Body / Query | Response |
|--------|------|------|--------------|----------|
| `GET` | `/backups/config/` | staff | — | `{primary_path, secondary_path, frequency, enabled, last_run_at}` |
| `PATCH` | `/backups/config/` | staff | any of the config fields | updated config |
| `GET` | `/backups/` | staff | — | `[BackupItem]` **read from storage manifests** |
| `POST` | `/backups/run/` | staff | — | `{detail, filename?}` (Celery, or inline if broker down) |
| `POST` | `/backups/upload/` | staff | multipart `file`, `encrypted` | `{detail, filename}` |
| `GET` | `/backups/audits/` | staff | — | `[RestoreAudit]` (last 50) |
| `POST` | `/backups/restore/` | **owner** | `{filename, confirm, password}` | `{detail, safety_backup, audit_id}` |

**`BackupItem`** (from manifest): `filename, timestamp, size, checksum_sha256,
source, app_sha, destinations{}`.

**Restore guards** (all enforced server-side in `api.restore`):
- `require_owner(request)` — owner role only (admins).
- `confirm.upper() == "RESTORE"` — typed confirmation, else `400`.
- `request.auth.check_password(password)` — re-authentication, else `403`.

Example restore call:
```bash
curl -X POST /api/v1/backups/restore/ \
  -H "Authorization: Bearer <owner token>" \
  -H "Content-Type: application/json" \
  -d '{"filename":"backup_...dump.enc","confirm":"RESTORE","password":"••••"}'
# → {"detail":"Restore complete.","safety_backup":"backup_..._pre.dump.enc","audit_id":1}
```

---

## 9. Management commands & scheduling

```bash
python manage.py run_backup                 # backup all shops (source=manual)
python manage.py run_backup --shop 1 --source scheduled
python manage.py backup_key                 # print a new master key for the env
```

**Scheduling** (`apps/backups/tasks.py`): Celery Beat runs
`run_scheduled_backups` daily; each shop's `BackupConfig.frequency` + `enabled`
gate whether it actually fires (`_is_due` compares `last_run_at`). On a machine
without Celery you can point **Windows Task Scheduler** at
`python manage.py run_backup` instead — and, run on the host, it can even see a
removable drive by its real path.

---

## 10. Configuration

**Environment (`.env`)**
```ini
BACKUP_ENCRYPTION_KEY=<fernet key from `manage.py backup_key`>
BACKUP_PRIMARY_HOST=D:/SecureBackups          # host folder bind-mounted to /app/backups
BACKUP_PATH_MAP={"D:\\SecureBackups":"/app/backups","E:":"/app/backups-secondary"}
APP_GIT_SHA=<deploy sha>                        # stamped into manifests
```

**Settings (`config/settings/base.py`)** — `BACKUP_ENCRYPTION_KEY`,
`BACKUP_PRIMARY_PATH` (container path, default `/app/backups`),
`BACKUP_SECONDARY_PATH`, `BACKUP_PATH_MAP`, `PG_DUMP_BIN`, `PG_RESTORE_BIN`,
`APP_GIT_SHA`.

**docker-compose.yml** — the destination is a **bind mount**, never a named
volume:
```yaml
services:
  backend:
    environment:
      BACKUP_PRIMARY_PATH: /app/backups
    volumes:
      - ${BACKUP_PRIMARY_HOST:-./secure-backups}:/app/backups   # bind mount
  worker:
    volumes:
      - ${BACKUP_PRIMARY_HOST:-./secure-backups}:/app/backups
```
The `backend` image ships `postgresql-client` (`pg_dump`/`pg_restore`). Client and
server are both **major 17** so dumps restore without GUC mismatches.

---

## 11. Security

- **Master key** lives only in the environment / secrets manager — never in the
  repo, DB, or an email. Losing it means backups can't be decrypted; leaking it
  compromises them.
- **No password-by-email** — the old "email the zip + password in the body"
  feature was removed entirely (anyone with mailbox access got both halves).
- **Restore is owner-only** and requires **re-authentication + typed
  confirmation** before it runs.
- Encrypted at rest with authenticated encryption (Fernet), so a stolen backup
  file is useless without the key.

---

## 12. Disaster-recovery runbook

**Scenario: laptop/Docker destroyed, only the `D:\SecureBackups` folder (or the
pen drive) survives.**

1. Reinstall Docker, clone the repo, restore `.env` **including the same
   `BACKUP_ENCRYPTION_KEY`** (from your secrets manager).
2. Point `BACKUP_PRIMARY_HOST` at the surviving folder and `docker compose up -d`.
3. Open the Backups page → the backups **appear immediately** (read from the
   folder's manifests; no DB needed).
4. Click **Restore** on the desired backup → confirm → the app takes a safety
   backup and restores in-place.

**Verified:** `docker compose down -v` (destroys the Postgres volume) followed by
a fresh `up` + empty DB still lists and restores the pre-existing backup.

---

## 13. Acceptance criteria — status

| Criterion | Status |
|-----------|--------|
| Volume + containers deleted, fresh spin-up still lists & restores | ✅ verified live |
| Backup confirmed written to destination(s) before "complete" | ✅ manifest `destinations` |
| Manual upload treated identically to automated backups | ✅ `manual_upload` |
| Restore always creates a non-skippable pre-restore safety backup | ✅ `pre_restore_safety` |
| Restore requires typed confirm + shows the data-loss window | ✅ modal + server guard |

---

## 14. Constraints & notes

- **In-place restore** (not DB-swap) by design — chosen for reliability on a
  single-laptop deployment; atomic via `--single-transaction`, with the
  mandatory safety backup as the real net.
- **Removable drive by label** isn't possible from inside a Linux container; the
  secondary is a bind-mounted path (best-effort). Running `run_backup` on the
  host would allow true label-based matching.
- **Off-site**: both destinations are local (same building). The
  `BackupDestination` contract is generic, so adding a cloud bucket as one of the
  two slots later is a drop-in, not a redesign.
- **pg client/server major must match** (both 17) so `pg_restore` accepts the
  archive.
