from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_data_registry.py"
REGISTRY = REPO_ROOT / "data" / "source_registry.json"


def run_registry_validator(registry: Path):
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--repo-root",
            str(REPO_ROOT),
            "--registry",
            str(registry),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class DataRegistryLocalPathsShapeTests(unittest.TestCase):
    def test_local_paths_rejects_non_array_containers_without_crashing(self) -> None:
        baseline = json.loads(REGISTRY.read_text(encoding="utf-8"))

        for invalid_value in ["brief/site-package", {"path": "brief/site-package"}, 7, None]:
            with self.subTest(local_paths=invalid_value), tempfile.TemporaryDirectory() as tmp:
                registry = json.loads(json.dumps(baseline))
                registry["sources"][0]["local_paths"] = invalid_value
                path = Path(tmp) / "registry.json"
                path.write_text(json.dumps(registry), encoding="utf-8")

                completed = run_registry_validator(path)

                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertEqual(completed.stderr, "")
                report = json.loads(completed.stdout)
                self.assertFalse(report["ok"])
                self.assertIn(
                    f"{registry['sources'][0]['source_id']}: local_paths must be an array",
                    report["errors"],
                )


if __name__ == "__main__":
    unittest.main()
