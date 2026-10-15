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



def show_error(message):
    """Mostra um erro mesmo sem console no Windows."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, message, "RagV Desktop", 0x10
        )
    except (AttributeError, OSError):
        print(message, file=sys.stderr)


def main():
    if not api_ready():
        show_error("RagV indisponivel. Verifique o Docker e a API.")
        return 1

    try:
        import webview
    except ImportError:
        show_error("O componente pywebview nao foi encontrado.")
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
