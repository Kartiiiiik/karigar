# Karigar — Jewellery Shop Accounts Management

Mobile-first web app to manage a jewellery shop's **gold and cash ledgers**
across three roles — **Owner, Manager, Karigar**. React (Vite) frontend +
Django REST backend in a single monorepo.

> **Domain primer.** A *karigar* is a goldsmith/artisan. The shop issues gold
> to karigars, who return finished ornaments. Each karigar is an account in the
> shop's books: **Dr = given to the karigar**, **Cr = received from them**.
> Gold ledgers balance in **net weight** (grams); cash ledgers in **NPR**.

---

## Status

| Milestone | Scope | State |
|-----------|-------|-------|
| **M1** | Scaffold, auth, roles, app shell, health check, seed, Docker | ✅ Done |
| **M2** | Karigars + ornaments CRUD with balances | ✅ Done |
| **M3** | Gold ledger (net-weight logic, photos, wastage, orders) | ✅ Done |
| **M4** | Cash ledger | ✅ Done |
| **M5** | Karigar self-view (read-only, scoped) | ✅ Done |
| **M6** | Reports + BS/AD calendar, Excel/PDF export | ✅ Done |
| **M7** | Backups (manual + scheduled) + audit history | ✅ Done |
| **M8** | Production hardening + tests + CI | ✅ Done |

> The API layer uses **Django Ninja** (not DRF). Interactive OpenAPI docs are
> served at **`/api/v1/docs`** in development.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the live schema + API reference,
and [docs/BACKUPS.md](docs/BACKUPS.md) for the backup/restore architecture and full flow.

---

## Repository layout

```
Karigar/
├── backend/            # Django 5 + DRF + SimpleJWT
│   ├── config/         # settings (base/dev/prod), celery, urls, wsgi/asgi
│   └── apps/           # common, accounts, ledger, reports, backups
├── frontend/           # React 18 + Vite + Tailwind + React Router
├── docs/ARCHITECTURE.md
├── docker-compose.yml  # db, redis, backend, worker, beat, frontend
├── .github/workflows/  # CI: lint + tests + migration check + build
└── .env.example
```

---

## Tech stack

**Backend:** Django 5, **Django Ninja** (Pydantic schemas) + **django-ninja-jwt**
for the API/auth layer (no DRF), PostgreSQL (psycopg 3), Celery + Redis +
django-celery-beat, django-simple-history, openpyxl, WeasyPrint, pyzipper
(AES backups), nepali-datetime, Pillow, django-storages, WhiteNoise, Gunicorn.

**Frontend:** React 18, Vite, Tailwind CSS, React Router v6, axios,
react-hook-form, Zustand, lucide-react (icons), nepali-date-converter.

---

## Quick start (local, without Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate      Unix:  source .venv/bin/activate
pip install -r requirements-dev.txt

# Fast path with SQLite (local dev only):
export USE_SQLITE=True                  # Windows (Git Bash): same; PowerShell: $env:USE_SQLITE="True"
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Backend runs at http://localhost:8000. Health check:
http://localhost:8000/api/v1/health/

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies `/api` → `:8000`.

### Demo logins

All seeded users share the password **`Karigar@123`**:

| Username | Role |
|----------|------|
| `owner` | Owner (superuser) |
| `manager` | Manager |
| `karigar1`, `karigar2` | Karigar |

---

## Run with Docker (full stack)

```bash
cp .env.example .env        # edit DJANGO_SECRET_KEY and passwords
docker compose up --build
```

- Frontend (nginx): http://localhost:8080
- Backend API: proxied via the frontend at `/api`, or directly inside the network
- The `backend` service runs migrations + `collectstatic` on boot; `worker` and
  `beat` skip that (`RUN_MIGRATIONS=0`).

Seed demo data inside the running stack:

```bash
docker compose exec backend python manage.py seed_demo
```

---

## Environment variables

Copy `.env.example` → `.env`. Key groups: Django (`DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`),
Database (`DATABASE_URL`, `USE_SQLITE`), Redis/Celery, Email (backups),
Media/object storage (S3), and production hardening flags. **Secrets are read
from the environment only and are never committed.**

---

## Testing & linting

```bash
# Backend
cd backend
pytest                       # unit + API tests
ruff check .                 # lint
python manage.py makemigrations --check --dry-run   # no missing migrations

# Frontend
cd frontend
npm run lint
npm run build
```

CI (GitHub Actions) runs all of the above on every push/PR against a real
Postgres service.

---

## Production notes

- `config.settings.prod` enforces `DEBUG=False`, requires `DJANGO_SECRET_KEY`
  and `DJANGO_ALLOWED_HOSTS`, refuses SQLite, and enables HSTS, secure cookies,
  and SSL redirect.
- Media uploads (ornament photos) go to **S3-compatible object storage** in prod
  via `django-storages` (`USE_S3=True`).
- Static files are served by WhiteNoise (compressed, hashed).
- The frontend is built to static assets and served by nginx, which also
  reverse-proxies `/api` and `/media` to the backend.
- A `/api/v1/health/` endpoint reports liveness + DB readiness for load
  balancers and container healthchecks.
