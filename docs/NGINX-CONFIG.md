# The nginx config, explained line by line

This walks through every directive in `frontend/nginx.conf` — what each key
does, and why it is there for *this* project. The file has one job: **serve the
built React SPA, and forward the paths that belong to Django to the backend.**

Inside the container this file is copied to `/etc/nginx/conf.d/default.conf`
(see `frontend/Dockerfile`), which nginx loads automatically.

---

## The full file

```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 20M;

    root /usr/share/nginx/html;
    index index.html;

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/  { proxy_pass http://backend:8000; ... }
    location /static/ { proxy_pass http://backend:8000; ... }
    location /media/  { proxy_pass http://backend:8000; ... }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## `server { ... }`

A **virtual server** block — one website's worth of configuration. nginx can
host many `server` blocks; here there is just one, so it answers every request
that arrives on the container.

---

## `listen 80;`

The TCP port nginx accepts connections on **inside the container**. It is `80`
(plain HTTP). `docker-compose.yml` maps this to your host with `ports: "8080:80"`,
which is why you browse to `http://localhost:8080`. nginx itself only ever knows
about `80`; the `8080` mapping is Docker's doing, outside this file.

---

## `server_name _;`

Which `Host:` header this block should match. `_` is a catch-all "no real name" —
it matches any hostname (`localhost`, `192.168.x.x`, an ngrok URL, …). Since this
is the only server block, a catch-all is exactly what we want: respond to
everything.

---

## `client_max_body_size 20M;`

The largest request body nginx will accept before returning **413 Payload Too
Large**. The default is only 1 MB, which would reject photo uploads. This raises
it to 20 MB so uploading karigar/ornament photos through `/api/` works. It
applies to the whole server block, including the proxied upload endpoints.

---

## `root /usr/share/nginx/html;`

The folder on disk nginx serves files from. This is where the **built SPA** was
copied during the image build (`COPY --from=builder /app/dist ...`). So `root`
points at the compiled React app: `index.html`, and the hashed JS/CSS.

## `index index.html;`

The default file to serve when a request maps to a directory (e.g. `/`). For a
single-page app that is always `index.html` — the one HTML file that boots React.

---

## Locations — how nginx chooses one

Each `location` says "for URLs starting with this prefix, do this." For any
request, nginx picks **one** location using these rules (simplified):

1. An exact match (`location = /path`) wins outright. *(none used here)*
2. Otherwise the **longest matching prefix** wins — *not* file order.
3. A location with no proxy/handler just serves files from `root`.

So `/api/gold-entries/` matches `location /api/` (prefix, 5 chars) rather than
`location /` (1 char), because the longer prefix wins. `/gold` matches only
`location /`. This "longest prefix" rule is why the specific backend paths
(`/api/`, `/admin/`, `/static/`, `/media/`) are handled by their own blocks while
everything else falls through to the SPA fallback. **The order they appear in the
file does not matter for prefix locations — specificity does.**

---

## `location /assets/ { ... }`

```nginx
location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

Serves the SPA's compiled JS/CSS bundles (Vite outputs them under `/assets/` with
**content-hashed filenames** like `index-a1b2c3.js`). There is no `proxy_pass`,
so nginx serves these straight from `root`.

- `expires 1y;` — tells browsers to cache these files for a year (sends
  `Expires`/`Cache-Control: max-age` headers).
- `add_header Cache-Control "public, immutable";` — `public` = any cache may
  store it; `immutable` = "this file will never change, don't even revalidate."

This aggressive caching is **safe because the filenames are hashed**: when you
rebuild and the content changes, the filename changes too, so the browser fetches
the new name instead of a stale cached file. `index.html` itself is *not* under
`/assets/`, so it is not long-cached — it always loads fresh and points at the
newest hashed bundles.

---

## `location /api/ { ... }` — the reverse proxy

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

This is where "reverse proxy" happens. Any request whose path starts with `/api/`
is **forwarded to the backend** instead of served from disk.

### `proxy_pass http://backend:8000;`
Forward the request to `http://backend:8000`. `backend` is the **Docker service
name**, which resolves on the internal Docker network to the backend container;
`8000` is the port gunicorn listens on there. (This works without publishing
port 8000 to your host — container-to-container traffic uses the private
network. See `docs/NETWORKING.md`.)

Because the prefix here ends in `/` and `proxy_pass` has **no path** after the
host, nginx forwards the **full original path**. So `/api/v1/karigars/` arrives
at the backend as `/api/v1/karigars/` — unchanged. Django's URLconf expects the
`/api/v1/...` prefix, so we deliberately pass it through intact.

### The `proxy_set_header` lines
When nginx forwards a request, the backend would otherwise only see nginx as the
client. These headers preserve the original request details:

- **`Host $host`** — pass the hostname the browser asked for. Django checks this
  against `ALLOWED_HOSTS`, and uses it to build absolute URLs. Without it the
  backend would see `backend` as the host.
- **`X-Real-IP $remote_addr`** — the client's real IP address (otherwise the
  backend sees nginx's internal IP). Useful for logging/rate-limiting.
- **`X-Forwarded-For $proxy_add_x_forwarded_for`** — the standard "chain of
  clients" header; appends the client IP to any existing list. Same purpose as
  above, in the conventional multi-proxy format.
- **`X-Forwarded-Proto $scheme`** — whether the *browser* used `http` or `https`
  (`$scheme` is nginx's incoming scheme). Django reads this (via
  `SECURE_PROXY_SSL_HEADER`) to know if the original request was secure, since to
  gunicorn every proxied request looks like plain HTTP. This drives things like
  secure-cookie and HTTPS-redirect decisions.

---

## `location /admin/ { ... }`

Identical proxying to `/api/`. It exists because the **Django admin is a
server-rendered app on the backend**, not part of the React SPA. Without this
block, `/admin/` would fall through to the SPA fallback (`/index.html`) and you
would see the React app instead of Django's admin. The same forwarding headers
are set so admin login (which uses cookies + CSRF) works behind the proxy.

---

## `location /static/ { ... }`

```nginx
location /static/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
}
```

Serves **Django's own static files** — chiefly the admin's CSS/JS. On the backend
these are collected by `collectstatic` and served by WhiteNoise at `/static/`.
This block is only needed so the **admin page looks styled**; the SPA does not use
`/static/` (its assets are under `/assets/`), so the two never collide. Fewer
headers here because static files don't need the client-IP/scheme context that
the API/admin do.

---

## `location /media/ { ... }`

```nginx
location /media/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
}
```

Serves **user-uploaded files** — the karigar/ornament photos. While `USE_S3` is
off, Django stores these on disk (`/app/media`, bind-mounted to a host folder)
and serves them at `/media/`. nginx forwards `/media/...` to the backend so an
`<img src="/media/karigars/x.jpg">` resolves. (If you later switch to S3, images
would be served from the bucket and this block becomes unused.)

---

## `location / { try_files $uri $uri/ /index.html; }` — the SPA fallback

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

The **catch-all** (shortest prefix — matches anything the blocks above didn't).
`try_files` tells nginx to try each option in order and serve the first that
exists:

1. `$uri` — a file at that exact path (e.g. `/favicon.ico`, `/logo.png`).
2. `$uri/` — a directory at that path.
3. `/index.html` — **the fallback if neither exists.**

This is the crucial trick for a single-page app. React Router owns client-side
routes like `/gold`, `/karigars`, `/bandaki`. Those are **not real files** on
disk, so steps 1–2 fail and nginx returns `index.html`. The browser loads the
SPA, and React Router reads the URL and renders the correct page. Without this,
refreshing on `/gold` or deep-linking to it would 404, because there is no
`gold.html`.

Note the backend paths are matched by their **longer prefixes above**, so they
never reach this fallback — only genuinely SPA/asset paths do.

---

## Putting it together: where each request goes

| Request | Matched location | Result |
|---|---|---|
| `GET /` | `/` | serves `index.html` (React boots) |
| `GET /gold` | `/` | no file → `index.html` → React Router renders Gold |
| `GET /assets/index-abc123.js` | `/assets/` | served from disk, cached 1 year |
| `GET /api/v1/gold-entries/` | `/api/` | proxied → `backend:8000` (Django Ninja) |
| `GET /admin/` | `/admin/` | proxied → `backend:8000` (Django admin) |
| `GET /static/admin/css/base.css` | `/static/` | proxied → backend (WhiteNoise) |
| `GET /media/karigars/x.jpg` | `/media/` | proxied → backend (uploaded photo) |

---

## Two common "gotchas" this file avoids

- **Trailing slash on `proxy_pass`.** Because `proxy_pass http://backend:8000;`
  has **no trailing path**, nginx forwards the original URI unchanged. If it were
  `proxy_pass http://backend:8000/;` (with a `/`), nginx would *strip* the
  location prefix — `/api/v1/...` could arrive as `/v1/...` and break routing. We
  deliberately keep it path-less so Django sees the full `/api/v1/...`.
- **Order vs. specificity.** You can list these locations in any order; nginx
  uses the **longest matching prefix**, not file order. `/api/` always beats `/`
  for an `/api/...` URL regardless of position.

---

*Related docs:* `docs/NETWORKING.md` (how the containers connect and why the
backend port isn't published), `frontend/Dockerfile` (how the SPA is built and
this config is installed).
