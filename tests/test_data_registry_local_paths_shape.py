from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_data_registry.py"
BASE_REGISTRY = json.loads((REPO_ROOT / "data" / "source_registry.json").read_text(encoding="utf-8"))


class DataRegistryLocalPathsShapeTests(unittest.TestCase):
    def test_malformed_local_paths_containers_fail_cleanly(self) -> None:
        for value in ["brief/example.md", {"path": "brief/example.md"}, 7, None]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                registry = copy.deepcopy(BASE_REGISTRY)
                registry["sources"][0]["local_paths"] = value
                path = Path(tmp) / "registry.json"
                path.write_text(json.dumps(registry), encoding="utf-8")

                completed = subprocess.run(
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

                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                report = json.loads(completed.stdout)
                self.assertIn("local_paths must be an array", "\n".join(report["errors"]))
                self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
