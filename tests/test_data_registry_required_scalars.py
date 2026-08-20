from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_data_registry import validate_registry  # noqa: E402


class DataRegistryRequiredScalarTests(unittest.TestCase):
    def test_required_scalar_metadata_rejects_non_strings_and_blank_values(self) -> None:
        registry = json.loads(
            (REPO_ROOT / "data" / "source_registry.json").read_text(encoding="utf-8")
        )
        cases = {
            "title": None,
            "publisher": {"unexpected": "object"},
            "url": [],
            "file_type": "   ",
        }

        for field, value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                candidate = copy.deepcopy(registry)
                candidate["sources"] = [candidate["sources"][0]]
                candidate["sources"][0][field] = value
                path = Path(tmp) / "registry.json"
                path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")

                report = validate_registry(REPO_ROOT, path)

                self.assertFalse(report.ok)
                self.assertIn(
                    f"{candidate['sources'][0]['source_id']}: {field} must be a non-empty string",
                    report.errors,
                )


if __name__ == "__main__":
    unittest.main()
