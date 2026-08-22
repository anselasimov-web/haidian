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


class DataRegistryUnknownFieldTests(unittest.TestCase):
    def test_rejects_unknown_top_level_and_source_fields(self) -> None:
        registry = json.loads((REPO_ROOT / "data" / "source_registry.json").read_text(encoding="utf-8"))
        registry["generated_by"] = "legacy-tool"
        registry["sources"][0]["publisher_name"] = registry["sources"][0]["publisher"]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")

            completed = run_registry_validator(path, repo_root=REPO_ROOT)

        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertFalse(report["ok"])
        joined = "\n".join(report["errors"])
        self.assertIn("registry: unsupported field 'generated_by'", joined)
        self.assertIn("unsupported field 'publisher_name'", joined)


if __name__ == "__main__":
    unittest.main()
