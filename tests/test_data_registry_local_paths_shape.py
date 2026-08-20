from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_registry_validator(registry: Path, repo_root: Path):
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_data_registry.py"),
            "--repo-root",
            str(repo_root),
            "--registry",
            str(registry),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def valid_source(local_paths):
    source = {
        "source_id": "TEST-SOURCE",
        "title": "Test source",
        "publisher": "Test publisher",
        "source_kind": "official_open_data",
        "url": "https://example.com/source",
        "accessed_date": "2026-08-20",
        "file_type": "webpage",
        "authority_level": "A0",
        "timeliness_level": "T0",
        "public_access_status": "public_url",
        "license_summary": "Public test source.",
        "review_status": "approved",
        "usable_for_formal": "yes",
        "allowed_uses": ["testing"],
        "prohibited_uses": ["none"],
        "topics": ["testing"],
    }
    source["local_paths"] = local_paths
    return source


class DataRegistryLocalPathsShapeTests(unittest.TestCase):
    def test_local_paths_rejects_non_array_containers_without_crashing(self) -> None:
        malformed_values = ["data/file.json", {"path": "data/file.json"}, 7, None]
        for value in malformed_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                registry = {
                    "schema_version": "0.1.0",
                    "updated_date": "2026-08-20",
                    "sources": [valid_source(value)],
                }
                path = root / "registry.json"
                path.write_text(json.dumps(registry), encoding="utf-8")

                completed = run_registry_validator(path, repo_root=root)

                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertEqual(completed.stderr, "")
                report = json.loads(completed.stdout)
                self.assertFalse(report["ok"])
                self.assertIn("TEST-SOURCE: local_paths must be an array", report["errors"])


if __name__ == "__main__":
    unittest.main()
