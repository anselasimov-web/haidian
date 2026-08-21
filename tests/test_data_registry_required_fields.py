from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DataRegistryRequiredFieldTests(unittest.TestCase):
    def test_missing_published_date_is_rejected(self) -> None:
        registry = json.loads(
            (REPO_ROOT / "data" / "source_registry.json").read_text(encoding="utf-8")
        )
        self.assertTrue(registry["sources"])
        source_id = registry["sources"][0]["source_id"]
        registry["sources"][0].pop("published_date", None)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "validate_data_registry.py"),
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

        self.assertNotEqual(
            completed.returncode, 0, completed.stdout + completed.stderr
        )
        report = json.loads(completed.stdout)
        self.assertFalse(report["ok"])
        self.assertIn(f"{source_id}: missing published_date", report["errors"])


if __name__ == "__main__":
    unittest.main()
