# Networking: how the frontend, nginx, and backend are connected

This document explains, end to end, how a browser request reaches the right
place in the Karigar stack — the React SPA, the Django API, the Django admin,
uploaded media, and static files — and why it is wired this way.

---

## 1. The big picture

```
                                          Docker network "karigar_default"
                                        ┌───────────────────────────────────────┐
  Browser                               │                                         │
  http://localhost:8080                 │   ┌─────────────┐        ┌───────────┐  │
        │                               │   │  frontend   │        │  backend  │  │
        │   :8080  (the ONLY published  │   │  (nginx)    │        │ (gunicorn │  │
        └──────────  port) ────────────┼──▶│  :80        │        │  Django)  │  │
                                        │   │             │        │  :8000    │  │
                                        │   │  reverse    │──────▶ │           │  │
                                        │   │  proxy      │  api/  │           │  │
                                        │   └─────────────┘  admin/│           │  │
                                        │         serves     media/│           │  │
                                        │         the SPA    static/└─────┬─────┘  │
                                        │                                 │        │
                                        │                    ┌───────┐  ┌─┴─────┐  │
                                        │                    │ redis │  │  db   │  │
                                        │                    │ :6379 │  │ :5432 │  │
                                        │                    └───────┘  └───────┘  │
                                        └───────────────────────────────────────┘
```

**Key idea:** only the **frontend (nginx)** container publishes a port to your
computer (`8080:80`). The backend, database, and redis have **no published
ports** — they are reachable *only* from inside the Docker network. The browser
never talks to Django directly; every request goes through nginx, which either
serves the SPA or forwards the request to the backend.

---

## 2. The containers (from `docker-compose.yml`)

| Service    | Image / build      | Published port     | Reachable inside network as |
|------------|--------------------|--------------------|-----------------------------|
| `frontend` | `./frontend` nginx | **`8080:80`** ✅    | `frontend:80`               |
| `backend`  | `./backend` Django | none               | `backend:8000`              |
| `db`       | postgres:17        | none               | `db:5432`                   |
| `redis`    | redis:7            | none               | `redis:6379`                |
| `worker`   | Django + Celery    | none               | —                           |
| `beat`     | Django + Celery    | none               | —                           |

Docker Compose gives every service a **DNS name equal to its service name** on a
shared private network. That is why nginx can say `proxy_pass http://backend:8000`
and Django can say `postgres://…@db:5432/…` — `backend` and `db` resolve to the
respective containers automatically. These names are **not** reachable from your
host; only `localhost:8080` is.

---

## 3. How the SPA is built and served

The React app is a **build-time bundle**, not a running Node server in production:

1. `frontend/Dockerfile` runs `vite build`, producing static files (`index.html`
   + hashed JS/CSS under `/assets/`).
2. Those files are copied into the nginx image at `/usr/share/nginx/html`.
3. nginx serves them on port 80 (published as `8080`).

So "the frontend" in production = **nginx serving static files**. There is no
React dev server involved.

---

## 4. How the SPA calls the API (same-origin)

The browser-side code never hardcodes a backend host. In
`frontend/src/lib/api.js`:

```js
export const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";
const api = axios.create({ baseURL: API_BASE });
```

`/api/v1` is a **relative, same-origin path**. When the app is open at
`http://localhost:8080`, a call to `GET /karigars/` actually hits
`http://localhost:8080/api/v1/karigars/`. Because it is the *same origin* as the
page, there is no CORS preflight and no cross-site cookie problem. nginx then
forwards it to the backend (next section).

**Auth is a JWT in a header, not a cookie.** After login the SPA stores the
access/refresh tokens and sends `Authorization: Bearer <token>` on every request
(see the axios request interceptor in `api.js`). This is why the *app* works
perfectly over plain HTTP — it does not rely on cookies at all.

---

## 5. nginx: the reverse proxy (`frontend/nginx.conf`)

nginx has two jobs: **serve the SPA** and **forward backend paths**. Each
`location` block decides where a request goes:

| Path prefix   | What nginx does                                  | Why                                                        |
|---------------|--------------------------------------------------|------------------------------------------------------------|
| `/assets/`    | Serve SPA bundle files (long cache)              | Vite's hashed JS/CSS                                       |
| `/api/`       | `proxy_pass http://backend:8000`                 | The Django Ninja REST API                                  |
| `/admin/`     | `proxy_pass http://backend:8000`                 | The server-rendered Django admin                           |
| `/static/`    | `proxy_pass http://backend:8000`                 | Django/admin CSS+JS (served by WhiteNoise)                 |
| `/media/`     | `proxy_pass http://backend:8000`                 | User-uploaded photos (served by Django from disk)          |
| `/` (else)    | `try_files $uri $uri/ /index.html`               | SPA fallback so client-side routes (`/gold`, `/bandaki`) load |

The **SPA fallback** is important: React Router owns paths like `/karigars` and
`/bandaki`. Those are not real files, so nginx returns `index.html` and the
browser-side router renders the right page. Anything that must be handled by
*Django* (`/api/`, `/admin/`, `/static/`, `/media/`) is matched **before** that
fallback and proxied to the backend instead.

`client_max_body_size 20M;` at the top allows photo uploads to pass through.

---

## 6. Why the backend port is not published

Publishing only nginx means:

- **One entry point.** Everything is same-origin on `:8080` — simpler CORS,
  simpler cookies, one URL to expose (e.g. through ngrok).
- **Smaller attack surface.** Postgres, redis, and gunicorn are not exposed to
  the host or the LAN; they are only reachable by sibling containers.
- **The proxy can add/normalise headers** (`Host`, `X-Forwarded-For`,
  `X-Forwarded-Proto`) before Django sees the request.

The trade-off: anything on the backend that you want to reach from a browser
(like `/admin/`) **must have an nginx `location` for it** — otherwise it falls
through to the SPA and you get the React app instead of Django. That is exactly
why `/admin/` and `/static/` were added to `nginx.conf`.

---

## 7. The Django admin (the special case)

Unlike the SPA/API, the admin is a **server-rendered Django app that uses session
cookies**, not JWTs. Three things must all be true for it to work:

1. **A route exists** — `location /admin/` proxies to the backend (§5).
2. **Its assets load** — `location /static/` proxies to the backend, and
   `STATIC_URL = "/static/"` (leading slash, so admin templates emit absolute
   `/static/admin/...` URLs). WhiteNoise serves those from `STATIC_ROOT` after
   `collectstatic` runs on boot.
3. **Its cookies survive** — Django's session and CSRF cookies. In production
   `config/settings/prod.py` defaults these to **secure** (HTTPS-only):

   ```python
   SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=True)
   CSRF_COOKIE_SECURE    = env.bool("DJANGO_CSRF_COOKIE_SECURE",    default=True)
   CSRF_TRUSTED_ORIGINS  = env.list("DJANGO_CSRF_TRUSTED_ORIGINS",  default=[])
   ```

   Over **plain HTTP** (e.g. `http://localhost:8080`) a *secure* cookie is never
   sent, so admin login would silently fail. For the local HTTP run, `.env` sets
   both to `False` and lists the proxy origin so the admin login POST passes
   Django's CSRF origin check:

   ```
   DJANGO_SESSION_COOKIE_SECURE=False
   DJANGO_CSRF_COOKIE_SECURE=False
   DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,https://<your-ngrok>
   ```

   **In real HTTPS production keep these `True`** and put your `https://` admin
   origin in `DJANGO_CSRF_TRUSTED_ORIGINS`.

Admin URL: **http://localhost:8080/admin/** — log in with the superuser from
`DJANGO_SUPERUSER_*` (created on boot; see `apps/accounts/management/commands/ensure_superuser.py`).

---

## 8. Development mode is different (Vite dev server)

When you run the frontend with `npm run dev` (not Docker), there is a **live Vite
dev server on port 5173** with hot reload. It has its *own* proxy
(`frontend/vite.config.js`) that mirrors what nginx does in production:

```js
server: {
  port: 5173,
  proxy: {
    "/api":   { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
    "/media": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
  },
}
```

So in dev the browser hits `http://localhost:5173`, the Vite server proxies
`/api` and `/media` to a Django running at `http://localhost:8000` (typically
`python manage.py runserver`, which *does* listen on 8000 locally). Same
same-origin trick, different proxy. Note the dev proxy does **not** cover
`/admin` — in dev you reach the admin directly at `http://localhost:8000/admin/`.

| | Dev (`npm run dev`) | Docker / prod |
|---|---|---|
| SPA served by | Vite dev server `:5173` | nginx `:8080` (built files) |
| Proxy for `/api`, `/media` | Vite `server.proxy` | nginx `location` blocks |
| Backend reached at | `localhost:8000` (runserver) | `backend:8000` (container DNS) |
| Admin | `localhost:8000/admin/` directly | `localhost:8080/admin/` via nginx |

---

## 9. Media (uploaded photos)

`USE_S3=False`, so uploads are written to the local filesystem at
`MEDIA_ROOT = /app/media`, which is **bind-mounted to a host folder**
(`${MEDIA_HOST:-./media-files}:/app/media`) so photos survive container
removal. Django serves them at `MEDIA_URL = /media/` in all modes (see
`config/urls.py`), and nginx proxies `/media/` to the backend. When you later
move to S3, set `USE_S3=True` + the `AWS_*` vars and storage switches
automatically — no nginx change needed. (See also the media notes in the repo.)

---

## 10. Request-flow examples

**App login (SPA):**
`POST localhost:8080/api/v1/auth/login/` → nginx `/api/` → `backend:8000` →
Django Ninja returns JWTs → SPA stores them, sends `Authorization: Bearer …`
afterwards.

**Loading a data page:**
Browser opens `localhost:8080/gold` → nginx SPA fallback returns `index.html` →
React Router renders the Gold page → it calls `GET /api/v1/gold-entries/` →
nginx `/api/` → backend.

**Admin:**
`localhost:8080/admin/` → nginx `/admin/` → backend (Django admin HTML) →
browser also loads `/static/admin/*.css` → nginx `/static/` → backend
(WhiteNoise). Session cookie is set (secure=False locally) → you stay logged in.

**A photo `<img>`:**
`GET localhost:8080/media/karigars/x.jpg` → nginx `/media/` → backend serves the
file from `/app/media` (the bind-mounted host folder).

---

## 11. Access URLs (Docker run)

| What | URL |
|---|---|
| Shop app (SPA) | http://localhost:8080/ |
| REST API | http://localhost:8080/api/v1/ |
| Health check | http://localhost:8080/api/v1/health/ |
| Django admin | http://localhost:8080/admin/ |
| Subscription status | http://localhost:8080/api/v1/subscription/status |

Exposing publicly with **ngrok**: tunnel to port **8080 only** (`ngrok http 8080`).
Add the ngrok host to `DJANGO_ALLOWED_HOSTS` and the `https://…ngrok…` origin to
`DJANGO_CSRF_TRUSTED_ORIGINS`. Because ngrok gives you HTTPS, you can (and should)
keep the cookie-secure flags `True` when tunnelling.

---

## 12. Troubleshooting

- **`502 Bad Gateway` on `/api`, `/admin`, `/static`:** the backend is still
  booting (it runs migrations + `collectstatic` + `ensure_superuser` before
  gunicorn accepts connections) or has crashed. Check
  `docker compose logs backend`; wait for `Booting worker`.
- **`/admin/` shows the React app:** nginx is missing the `/admin/` location, or
  you rebuilt the frontend image without the updated `nginx.conf`
  (`docker compose up -d --build --force-recreate frontend`).
- **Admin login "just reloads" / won't stay logged in:** cookies are secure-only
  over HTTP. Set `DJANGO_SESSION_COOKIE_SECURE=False` and
  `DJANGO_CSRF_COOKIE_SECURE=False`, add your origin to
  `DJANGO_CSRF_TRUSTED_ORIGINS`, then recreate the backend so the new `.env`
  loads (`docker compose up -d --force-recreate backend`).
- **Admin CSS missing (unstyled page):** `/static/` not proxied, or
  `STATIC_URL` lacks its leading slash, or `collectstatic` did not run.
- **Env change not taking effect:** editing `.env` requires a container
  **recreate** (`--force-recreate`), not just a restart — Compose loads env at
  container creation.
- **`nginx.conf` change not taking effect:** it is baked into the frontend
  image; rebuild it (`docker compose up -d --build frontend`).

---

*Files referenced:* `docker-compose.yml`, `frontend/nginx.conf`,
`frontend/vite.config.js`, `frontend/src/lib/api.js`, `backend/config/urls.py`,
`backend/config/settings/base.py`, `backend/config/settings/prod.py`,
`backend/entrypoint.sh`.
