from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _service_block(compose: str, service: str) -> str:
    lines = compose.splitlines()
    start = lines.index(f"  {service}:")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("  ") and not lines[index].startswith("    ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_local_judit_credentials_and_callback_are_worker_only() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    for service in ("worker-1", "worker-2"):
        block = _service_block(compose, service)
        assert "JUDIT_API_KEY: ${JUDIT_API_KEY:-}" in block
        assert "JUDIT_CALLBACK_URL: ${JUDIT_CALLBACK_URL:-}" in block

    for service in ("api", "scheduler"):
        block = _service_block(compose, service)
        assert "JUDIT_API_KEY" not in block
        assert "JUDIT_CALLBACK_URL" not in block


def test_local_env_example_keeps_callback_opt_in_and_secret_free() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "JUDIT_CALLBACK_URL=" in env_example
    assert "JUDIT_API_KEY=" in env_example
    assert "JUDIT_CALLBACK_URL=https://" not in env_example
