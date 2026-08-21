from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_data_registry.py"


class DataRegistrySubmissionAliasTests(unittest.TestCase):
    def test_symlink_alias_into_submissions_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "submissions" / "alice" / "proposal.md"
            victim.parent.mkdir(parents=True)
            victim.write_text("participant content", encoding="utf-8")

            alias = root / "data" / "reviewed-source.md"
            alias.parent.mkdir(parents=True)
            try:
                alias.symlink_to(victim)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            registry = {
                "schema_version": "0.1.0",
                "updated_date": "2026-08-21",
                "sources": [
                    {
                        "source_id": "ALIASED-SUBMISSION",
                        "title": "Aliased submission",
                        "publisher": "Test publisher",
                        "source_kind": "cleared_user_document",
                        "url": "data/reviewed-source.md",
                        "published_date": None,
                        "accessed_date": "2026-08-21",
                        "file_type": "markdown",
                        "authority_level": "CLEARED_USER_DOCUMENT",
                        "timeliness_level": "NA",
                        "public_access_status": "cleared_for_repo",
                        "license_summary": "Test-only cleared source.",
                        "review_status": "approved",
                        "usable_for_formal": "yes",
                        "allowed_uses": ["test"],
                        "prohibited_uses": ["none"],
                        "topics": ["test"],
                    }
                ],
            }
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--repo-root",
                    str(root),
                    "--registry",
                    str(registry_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertIn(
            "ALIASED-SUBMISSION: data registry must not reference submitted proposal files: data/reviewed-source.md",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
