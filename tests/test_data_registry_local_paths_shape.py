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


def run_validator(path: Path):
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--repo-root",
            str(REPO_ROOT),
            "--registry",
            str(path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class DataRegistryLocalPathsShapeTests(unittest.TestCase):
    def test_invalid_local_paths_containers_fail_closed(self) -> None:
        base = json.loads(REGISTRY.read_text(encoding="utf-8"))

        for invalid in ("data/source_registry.json", {"path": "data/source_registry.json"}, 1, None):
            with self.subTest(invalid=invalid):
                registry = json.loads(json.dumps(base))
                registry["sources"][0]["local_paths"] = invalid

                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "registry.json"
                    path.write_text(json.dumps(registry), encoding="utf-8")
                    completed = run_validator(path)

                self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                report = json.loads(completed.stdout)
                self.assertFalse(report["ok"])
                self.assertTrue(
                    any("local_paths must be an array" in error for error in report["errors"]),
                    report["errors"],
                )


if __name__ == "__main__":
    unittest.main()
