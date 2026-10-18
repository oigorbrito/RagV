"""RagV Desktop: janela nativa para o frontend FastAPI existente."""

import json
import os
import sys
import urllib.error
import urllib.request


URL = os.environ.get("RPY_DESKTOP_URL", "http://127.0.0.1:8000")


def get_url():
    return os.environ.get("RPY_DESKTOP_URL", URL)


def api_ready():
    try:
        with urllib.request.urlopen(
            f"{get_url()}/ready", timeout=3
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False



def show_error(message):
    """Mostra um erro mesmo sem console no Windows."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, message, "RagV", 0x10
        )
    except (AttributeError, OSError):
        print(message, file=sys.stderr)


def _inject_managed_token(window):
    token = os.environ.get("RPY_DESKTOP_TOKEN", "").strip()
    if not token:
        return
    script = (
        "(() => { const input = document.querySelector('#bearer-token'); "
        "const button = document.querySelector('#verify-token'); "
        f"if (input && button) {{ input.value = {json.dumps(token)}; "
        "input.dispatchEvent(new Event('input', {bubbles:true})); button.click(); }} })()"
    )
    try:
        window.evaluate_js(script)
    except Exception:
        # The API remains protected; a failed injection leaves the normal access UI.
        pass


def main():
    if not api_ready():
        show_error("RagV indisponivel. Verifique o Docker e a API.")
        return 1

    try:
        import webview
    except ImportError:
        show_error("O componente pywebview nao foi encontrado.")
        return 2

    window = webview.create_window(
        "RagV",
        get_url(),
        width=1200,
        height=800,
        min_size=(800, 600),
    )
    def on_loaded(*_args):
        _inject_managed_token(window)

    window.events.loaded += on_loaded
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
