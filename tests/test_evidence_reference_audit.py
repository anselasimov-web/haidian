from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_evidence_references.py"
SPEC = importlib.util.spec_from_file_location("audit_evidence_references", SCRIPT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class EvidenceReferenceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.package = self.repo / "submissions" / "alice" / "sample"
        self.package.mkdir(parents=True)
        (self.repo / "data").mkdir()
        (self.repo / "sources").mkdir()
        (self.repo / "brief" / "site-package" / "standards").mkdir(parents=True)
        (self.package / "geometry").mkdir()
        (self.repo / "brief" / "site-package" / "ranges").mkdir(parents=True)

        self.write_json(
            self.package / "sources.json",
            {"sources": [{"source_id": "SRC-LOCAL"}]},
        )
        self.write_json(
            self.repo / "data" / "source_registry.json",
            {"sources": [{"source_id": "SRC-CENTRAL"}]},
        )
        self.write_json(
            self.repo / "sources" / "public-sources.json",
            {"sources": [{"id": "SRC-PUBLIC"}]},
        )
        self.write_json(
            self.package / "standard_matrix.json",
            {"standards": [{"standard_id": "STD-PACKAGE"}]},
        )
        self.write_json(
            self.repo / "brief" / "site-package" / "standards" / "standards.json",
            {"standards": [{"standard_id": "STD-CENTRAL"}]},
        )
        self.write_json(
            self.package / "design_depth_matrix.json",
            {"items": [{"item_id": "depth_item"}]},
        )
        self.write_json(
            self.package / "metrics.json",
            {"metrics": {"green_ratio": {"status": "known", "value": 0.2}}},
        )
        self.write_json(
            self.package / "geometry" / "land_use.geojson",
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "id": "LU-001", "properties": {"id": "LU-001"}, "geometry": None},
                    {"type": "Feature", "id": "LU-002", "properties": {"id": "LU-002"}, "geometry": None},
                ],
            },
        )
        self.write_json(
            self.repo / "brief" / "site-package" / "ranges" / "planning_limits.json",
            {"status": "missing"},
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def write_proposal(self, body: str, name: str = "proposal.md") -> Path:
        path = self.package / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_all_five_reference_kinds_resolve(self) -> None:
        proposal = self.write_proposal(
            "\n".join(
                [
                    "[source:SRC-LOCAL] [source:SRC-CENTRAL] [source:SRC-PUBLIC]",
                    "[standard:STD-PACKAGE] [standard:STD-CENTRAL]",
                    "[depth:depth_item] [metric:green_ratio]",
                    "[data:geometry/land_use.geojson#LU-001]",
                    "[data:geometry/land_use.geojson#LU-001~LU-002]",
                    "[data:brief/site-package/ranges/planning_limits.json]",
                ]
            )
        )
        self.assertEqual(AUDIT.audit_proposal(self.repo, proposal), [])

    def test_reports_dangling_ids_and_feature_fragment(self) -> None:
        proposal = self.write_proposal(
            " ".join(
                [
                    "[source:SRC-MISSING]",
                    "[standard:STD-MISSING]",
                    "[depth:depth_missing]",
                    "[metric:metric_missing]",
                    "[data:geometry/land_use.geojson#LU-999]",
                ]
            )
        )
        findings = AUDIT.audit_proposal(self.repo, proposal)
        self.assertEqual(len(findings), 5)
        self.assertEqual({item.kind for item in findings}, {"source", "standard", "depth", "metric", "data"})
        data_finding = next(item for item in findings if item.kind == "data")
        self.assertIn("feature ID does not resolve", data_finding.reason)

    def test_missing_data_file_and_escaping_path_are_reported(self) -> None:
        proposal = self.write_proposal(
            "[data:geometry/missing.geojson#X] [data:../../outside.geojson#X]"
        )
        findings = AUDIT.audit_proposal(self.repo, proposal)
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("does not exist" in item.reason for item in findings))
        self.assertTrue(any("escapes the repository" in item.reason for item in findings))

    def test_fragment_on_non_feature_json_is_reported_but_file_only_reference_is_valid(self) -> None:
        proposal = self.write_proposal(
            "[data:brief/site-package/ranges/planning_limits.json] "
            "[data:brief/site-package/ranges/planning_limits.json#LIMIT-1]"
        )
        findings = AUDIT.audit_proposal(self.repo, proposal)
        self.assertEqual(len(findings), 1)
        self.assertIn("no feature IDs", findings[0].reason)

    def test_translation_files_are_discovered_for_package_target(self) -> None:
        primary = self.write_proposal("[metric:green_ratio]")
        translation = self.write_proposal("[metric:green_ratio]", "proposal.en.md")
        paths = AUDIT.proposal_paths(self.repo, str(self.package), False)
        self.assertEqual(paths, [primary, translation])

    def test_duplicate_dangling_marker_is_reported_once(self) -> None:
        proposal = self.write_proposal("[metric:nope] again [metric:nope]")
        findings = AUDIT.audit_proposal(self.repo, proposal)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].value, "nope")


if __name__ == "__main__":
    unittest.main()
