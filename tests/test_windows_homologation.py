"""Cheap guardrails for installer isolation; runtime evidence is a real Windows drill."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HomologationPackageTests(unittest.TestCase):
    def test_installer_does_not_reuse_habitual_identity_or_config(self):
        text = (ROOT / "packaging/windows/RagVDesktop.iss").read_text(encoding="utf-8-sig")
        self.assertNotIn("B65C2D92-5C34-4B84-93C1-3DB9D8C27A71", text)
        self.assertNotIn("SetIniString", text)
        self.assertNotIn("ProjectPage", text)
        self.assertIn("RagV-Homologacao", text)
        self.assertIn('_homologation-payload\\project\\*', text)

    def test_launcher_has_explicit_isolated_identity_no_destructive_operations(self):
        text = (ROOT / "packaging/windows/start-homologacao.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'ragv-hml-'", text)
        self.assertIn("--project-name $composeProject", text)
        self.assertIn("New-Secret", text)
        self.assertIn("SetAccessRuleProtection", text)
        self.assertNotIn("D:\\projetos", text)
        self.assertNotIn("down -v", text)
        self.assertIn("if (-not $imageExists)", text)
        self.assertIn("up -d --no-build", text)
        self.assertIn("bootstrap_homologation.py", text)

    def test_overlay_has_no_postgres_publication_and_loopback_api(self):
        text = (ROOT / "compose.homologacao.yaml").read_text()
        self.assertIn("ports: !reset []", text)
        self.assertIn("ports: !override", text)
        self.assertIn("127.0.0.1:${RPY_API_PORT:-18080}:8000", text)
        self.assertNotIn("ragv_rpy_pgdata", text)

    def test_package_has_allowlisted_sources_and_explicit_sha(self):
        text = (ROOT / "scripts/package_windows_homologation.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("git -C $root ls-files", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("Package SHA:", text)
        self.assertIn("requirements/windows-build.txt", text)
        self.assertNotIn("Copy-Item (Join-Path $root '.env')", text)

    def test_bootstrap_is_idempotent_empty_tenant_only(self):
        text = (ROOT / "scripts/bootstrap_homologation.py").read_text()
        self.assertIn("ON CONFLICT (id) DO NOTHING", text)
        self.assertNotIn("INSERT INTO processes", text)
        self.assertNotIn("JUDIT_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
