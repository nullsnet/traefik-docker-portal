# AGENTS.md

## What This Is

A single-file Flask app that queries the Traefik API to build a service discovery portal. Runs inside Docker, connects to an external `proxy` network, and is itself routed through Traefik via labels.

## Architecture

- **`app.py`** — the entire application. Entry point, all routes, business logic.
- **`templates/`** — Jinja2 templates (`index.html`, `manifest_body.json`). Bootstrap 5 frontend with PWA support.
- **`static/`** — CSS, JS, service worker, icons.
- **`services.json`** — optional static services list, mounted as `/etc/services.json` at runtime. Section-based format: each entry has `title` and `services` array of `{name, url}` objects.

## How to Run

```bash
docker compose up --build
```

The app listens on `0.0.0.0:5001`. It requires a running Traefik instance reachable via `TRAEFIK_API_URL` (default `http://traefik:8080`) and the external Docker network `proxy`.

## Configuration (All Environment Variables)

| Variable | Default | Purpose |
|---|---|---|
| `TRAEFIK_API_URL` | `http://traefik:8080` | Traefik dashboard API endpoint |
| `DOMAIN_SUFFIX` | *(empty)* | Appended to short hostnames for URL construction |
| `PAGE_HEADING` | `Service Portal 🚀` | Page title / heading |
| `LINK_TARGET` | `_self` | Target attribute on service links |
| `STATIC_SERVICES_FILE` | `/etc/services.json` | Path to static services JSON file |
| `PORTAL_PORT` | `5001` | Flask listen port |

No `.env` file is used. All configuration comes from `compose.yml` environment block or host-level env vars.

## Key Behaviors

- **Favicon proxy** (`/favicon/<service_name>`) — fetches favicons from internal service URLs to bypass Authelia authentication. Caches results in `_internal_urls` / `_favicon_paths` global dicts (in-memory, no persistence across restarts).
- **Internal router filtering** — skips routers whose provider is `internal` or whose service name starts with `api@` or `dashboard@`.
- **URL construction** — strips subdomains beyond the first dot and appends `DOMAIN_SUFFIX`. Uses `https://` for hosts containing a dot, `http://` otherwise.
