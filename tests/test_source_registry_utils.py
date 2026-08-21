from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from source_registry_utils import load_source_registry  # noqa: E402


class SourceRegistryUtilsTests(unittest.TestCase):
    def test_missing_registry_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_source_registry(Path(tmp)), {})

    def test_valid_registry_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            data_dir = repo_root / "data"
            data_dir.mkdir()
            expected = {"schema_version": "1.0", "sources": []}
            (data_dir / "source_registry.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )
            self.assertEqual(load_source_registry(repo_root), expected)

    def test_invalid_registry_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            data_dir = repo_root / "data"
            data_dir.mkdir()
            (data_dir / "source_registry.json").write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, r"data/source_registry\.json: invalid JSON:"
            ):
                load_source_registry(repo_root)


if __name__ == "__main__":
    unittest.main()
