from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_data_registry import validate_registry  # noqa: E402


class DataRegistryCalendarDateTests(unittest.TestCase):
    def valid_registry(self) -> dict:
        return {
            "schema_version": "0.1.0",
            "updated_date": "2024-02-29",
            "sources": [
                {
                    "source_id": "CALENDAR-DATE-SOURCE",
                    "title": "Calendar date fixture",
                    "publisher": "Fixture publisher",
                    "source_kind": "official_open_data",
                    "url": "https://example.com/source",
                    "published_date": "2024-02-29",
                    "accessed_date": "2026-08-21",
                    "file_type": "webpage",
                    "authority_level": "A0",
                    "timeliness_level": "T0",
                    "public_access_status": "public_url",
                    "license_summary": "Fixture license summary.",
                    "review_status": "approved",
                    "usable_for_formal": "yes",
                    "allowed_uses": ["fixture validation"],
                    "prohibited_uses": ["none"],
                    "topics": ["test"],
                }
            ],
        }

    def validate(self, registry: dict):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            return validate_registry(root, path)

    def test_valid_leap_day_passes(self) -> None:
        report = self.validate(self.valid_registry())
        self.assertTrue(report.ok, report.errors)

    def test_impossible_calendar_dates_fail(self) -> None:
        cases = [
            ("updated_date", None, "2026-02-30", "updated_date"),
            ("accessed_date", "accessed_date", "2026-13-01", "accessed_date"),
            ("published_date", "published_date", "2026-02-29", "published_date"),
        ]
        for _name, source_key, invalid_date, expected_error in cases:
            with self.subTest(field=expected_error, value=invalid_date):
                registry = deepcopy(self.valid_registry())
                if source_key is None:
                    registry["updated_date"] = invalid_date
                else:
                    registry["sources"][0][source_key] = invalid_date

                report = self.validate(registry)

                self.assertFalse(report.ok)
                self.assertTrue(
                    any(expected_error in error and "valid YYYY-MM-DD calendar date" in error for error in report.errors),
                    report.errors,
                )


if __name__ == "__main__":
    unittest.main()
