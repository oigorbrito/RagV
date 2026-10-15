"""RagV Desktop: janela nativa para o frontend FastAPI existente."""

import sys
import urllib.error
import urllib.request


URL = "http://127.0.0.1:8000"


def api_ready():
    try:
        with urllib.request.urlopen(
            f"{URL}/ready", timeout=3
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main():
    if not api_ready():
        print(
            "RagV indisponível. Inicie os serviços com "
            "'docker compose up -d --build'.",
            file=sys.stderr,
        )
        return 1

    try:
        import webview
    except ImportError:
        print(
            "Instale pywebview: python -m pip install pywebview",
            file=sys.stderr,
        )
        return 2

    webview.create_window(
        "RagV Desktop",
        URL,
        width=1200,
        height=800,
        min_size=(800, 600),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
