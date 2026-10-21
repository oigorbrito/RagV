# Optional local desktop window

The Rpy API already serves the web UI. This launcher opens **that same UI** in
a native window using optional pywebview. It does not introduce a new frontend,
change API contracts, run migrations, or modify the RAG pipeline.

## Prerequisites

- Python 3.12 on the host
- Docker and Docker Compose with the existing Rpy stack configured
- A supported system webview runtime (for example, WebView2 on Windows)
- Install the optional GUI library in your host environment: `python -m pip install pywebview`

## Start

From the repository root:

```sh
docker compose up -d --build
python scripts/desktop_launcher.py
```

The browser mode remains available at `http://localhost:8000/`.

The launcher checks `/ready` before opening the window. If the API is not
ready, it prints a clear message and exits; it does not silently start Docker
or take ownership of pre-existing containers.

## Boundaries

- Closing the window **does not stop** API, workers, scheduler or PostgreSQL.
- It does not persist bearer tokens or credentials.
- It accepts only explicit numeric loopback HTTP origins.
- This is an optional **developer/local workstation** launcher, not a packaged
  one-click installer. Host-specific packaging and lifecycle management require
  separate validation on Windows/Linux/macOS.
- Do not expose the development Compose stack to untrusted networks; review
  published database/API ports and credentials before using real legal data.

Run `pytest -q tests/test_desktop_launcher.py` to validate its basic contract.
