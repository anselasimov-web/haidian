from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_standard_references as fetcher  # noqa: E402


class FetchStandardReferenceSourceProvenanceTests(unittest.TestCase):
    def test_changed_source_url_does_not_preserve_old_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "standards.json").write_text(
                json.dumps(
                    {
                        "standards": [
                            {
                                "standard_id": "STD-A",
                                "title_zh": "Standard A",
                                "source_url": "https://example.com/new",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            reference = root / "references" / "std-a.md"
            reference.parent.mkdir()
            fetcher.write_reference_markdown(
                reference,
                {
                    "standard_id": "STD-A",
                    "title_zh": "Standard A",
                    "source_url": "https://example.com/old",
                    "source_status": "official",
                },
                fetcher.FetchResult(
                    True,
                    "fetched_manual_official",
                    final_url="https://example.com/old-final",
                    raw_sha256="a" * 64,
                    text="OLD SOURCE CONTENT",
                ),
                "2026-08-01",
            )

            arguments = [
                "fetch_standard_references.py",
                "--repo-root",
                str(root),
                "--standards",
                "standards.json",
                "--output-dir",
                "references",
                "--accessed-date",
                "2026-08-22",
            ]
            failed_fetch = fetcher.FetchResult(
                False,
                "timeout",
                error="temporary timeout",
                final_url="https://example.com/new",
            )
            with mock.patch.object(sys, "argv", arguments), mock.patch.object(
                fetcher, "fetch_url", return_value=failed_fetch
            ):
                return_code = fetcher.main()

            self.assertEqual(1, return_code)
            rewritten = reference.read_text(encoding="utf-8")
            self.assertNotIn("OLD SOURCE CONTENT", rewritten)
            self.assertIn('source_url: "https://example.com/new"', rewritten)
            self.assertIn("fetch_status: timeout", rewritten)

            record = json.loads((root / "references" / "index.json").read_text(encoding="utf-8"))[
                "references"
            ][0]
            self.assertEqual("https://example.com/new", record["source_url"])
            self.assertEqual("timeout", record["fetch_status"])
            self.assertEqual("https://example.com/new", record["final_url"])


if __name__ == "__main__":
    unittest.main()
