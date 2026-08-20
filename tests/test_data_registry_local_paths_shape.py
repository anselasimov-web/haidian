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


def source_with(local_paths):
    return {
        "source_id": "DATA-SRC-LOCAL-PATHS-SHAPE",
        "title": "Local paths shape fixture",
        "publisher": "Test publisher",
        "source_kind": "official_open_data",
        "url": "https://example.com/source",
        "accessed_date": "2026-08-20",
        "file_type": "webpage",
        "authority_level": "A0",
        "timeliness_level": "T0",
        "public_access_status": "public_url",
        "license_summary": "Test fixture license boundary.",
        "review_status": "approved",
        "usable_for_formal": "yes",
        "allowed_uses": ["test validation"],
        "prohibited_uses": ["production use"],
        "topics": ["validation"],
        "local_paths": local_paths,
    }


class DataRegistryLocalPathsShapeTests(unittest.TestCase):
    def test_local_paths_rejects_non_array_values_without_crashing(self) -> None:
        malformed_values = [
            "brief/source.md",
            {"path": "brief/source.md"},
            1,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "registry.json"
            for value in malformed_values:
                with self.subTest(value=value):
                    registry = {
                        "schema_version": "0.1.0",
                        "updated_date": "2026-08-20",
                        "sources": [source_with(value)],
                    }
                    registry_path.write_text(json.dumps(registry), encoding="utf-8")
                    completed = run_registry_validator(registry_path, root)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    report = json.loads(completed.stdout)
                    self.assertIn(
                        "DATA-SRC-LOCAL-PATHS-SHAPE: local_paths must be an array of strings",
                        report["errors"],
                    )


if __name__ == "__main__":
    unittest.main()
