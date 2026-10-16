"""Optional Rpy desktop window. Does not own or stop Docker services."""
from __future__ import annotations

import argparse
import ipaddress
import sys
import urllib.error
import urllib.parse
import urllib.request


def local_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Only plain HTTP loopback origins are supported")
    if parsed.path not in ("", "/"):
        raise ValueError("Specify the origin only, without a path")
    try:
        host = parsed.hostname
        if not host or not ipaddress.ip_address(host).is_loopback:
            raise ValueError("Origin must use a numeric loopback IP address")
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid loopback origin") from exc
    if port is None:
        raise ValueError("Explicit port is required")
    return f"http://{host}:{port}"


def is_ready(origin: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{origin}/ready", timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the existing Rpy UI in a desktop window")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    try:
        origin = local_origin(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    if not is_ready(origin):
        print(
            f"Rpy is not ready at {origin}. Start the existing stack with "
            "'docker compose up -d --build' and try again.",
            file=sys.stderr,
        )
        return 1
    try:
        import webview
    except ImportError:
        print("Install optional desktop dependency: pip install pywebview", file=sys.stderr)
        return 2
    webview.create_window("Rpy — Inteligência processual", origin, width=1100, height=760, min_size=(760, 540))
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
