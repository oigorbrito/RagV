"""Testes isolados do launcher RagV Desktop."""

import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "ragv_desktop.py"

spec = importlib.util.spec_from_file_location(
    "ragv_desktop", LAUNCHER
)
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopLauncherTests(unittest.TestCase):

    @patch.object(desktop.urllib.request, "urlopen")
    def test_api_ready_success(self, urlopen):
        response = MagicMock()
        response.status = 200
        urlopen.return_value.__enter__.return_value = response

        self.assertTrue(desktop.api_ready())

    @patch.object(desktop.urllib.request, "urlopen")
    def test_api_ready_unavailable(self, urlopen):
        urlopen.side_effect = OSError("connection refused")

        self.assertFalse(desktop.api_ready())

    @patch.object(desktop, "show_error")
    @patch.object(desktop, "api_ready", return_value=False)
    def test_main_fails_when_api_unavailable(self, _ready, mock_show_error):
        self.assertEqual(desktop.main(), 1)
        mock_show_error.assert_called_once_with(
            "RagV indisponivel. Verifique o Docker e a API."
        )

    @patch.object(desktop, "show_error")
    @patch.object(desktop, "api_ready", return_value=True)
    def test_main_fails_when_webview_missing(self, _ready, mock_show_error):
        with patch.dict(sys.modules, {"webview": None}):
            self.assertEqual(desktop.main(), 2)
            mock_show_error.assert_called_once_with(
                "O componente pywebview nao foi encontrado."
            )

    @patch.object(desktop, "api_ready", return_value=True)
    def test_main_opens_existing_frontend(self, _ready):
        fake_webview = MagicMock()

        with patch.dict(sys.modules, {"webview": fake_webview}):
            result = desktop.main()

        self.assertEqual(result, 0)
        fake_webview.create_window.assert_called_once()
        fake_webview.start.assert_called_once()

        args, kwargs = fake_webview.create_window.call_args
        self.assertEqual(args[0], "RagV Desktop")
        self.assertEqual(args[1], desktop.URL)

    def test_show_error_native_dialog(self):
        mock_msgbox = MagicMock()
        fake_windll = MagicMock()
        fake_windll.user32.MessageBoxW = mock_msgbox

        with patch("ctypes.windll", fake_windll, create=True):
            desktop.show_error("Falha de teste")

        mock_msgbox.assert_called_once_with(
            None, "Falha de teste", "RagV Desktop", 0x10
        )

    @patch("sys.stderr")
    def test_show_error_fallback(self, mock_stderr):
        fake_windll = MagicMock()
        fake_windll.user32.MessageBoxW.side_effect = OSError("sem suporte")

        with patch("ctypes.windll", fake_windll, create=True):
            desktop.show_error("Erro de fallback")

        mock_stderr.write.assert_called()


if __name__ == "__main__":
    unittest.main()
