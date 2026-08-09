from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
HAS_REVIEW_DEPS = all(
    importlib.util.find_spec(name) is not None for name in ["shapely", "pyproj", "jsonschema"]
)

if HAS_REVIEW_DEPS:
    from test_agent_scaffold_and_self_check import (  # noqa: E402
        complete_scaffold,
        run_scaffold,
        write_official_site_package,
    )


def run_finalize(submission_dir: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "finalize_submission.py"),
            str(submission_dir),
            *flags,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def run_self_check(repo_root: Path, submission_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "self_check_submission.py"),
            str(submission_dir),
            "--repo-root",
            str(repo_root),
            "--pr-author",
            "alice",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def read_manifest(submission_dir: Path) -> dict:
    return json.loads((submission_dir / "manifest.json").read_text(encoding="utf-8"))


def stale_hashes(submission_dir: Path) -> list[str]:
    """Manifest entries whose recorded sha256 no longer matches the file on disk."""
    stale: list[str] = []
    for item in read_manifest(submission_dir).get("files", []):
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        recorded = item.get("sha256")
        if not rel or not recorded or rel == "manifest.json":
            continue
        path = submission_dir / str(rel)
        if not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
            stale.append(str(rel))
    return stale


def make_ready_for_review_package(root: Path, slug: str) -> Path:
    write_official_site_package(root)
    submission_dir = root / "submissions" / "alice" / slug
    scaffold = run_scaffold(submission_dir, cwd=root)
    if scaffold.returncode != 0:
        raise AssertionError(scaffold.stdout + scaffold.stderr)
    finalized = complete_scaffold(submission_dir)
    if finalized.returncode != 0:
        raise AssertionError(finalized.stdout + finalized.stderr)
    return submission_dir


@unittest.skipUnless(HAS_REVIEW_DEPS, "Install requirements-review.txt to run finalize tests")
class FinalizeRefinalizeTests(unittest.TestCase):
    def test_refinalize_refreshes_hashes_for_a_later_editing_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            submission_dir = make_ready_for_review_package(root, "refinalize-pass")
            self.assertEqual("ready_for_review", read_manifest(submission_dir)["package_state"])

            # A deterministic rebuild reproduces identical bytes, so an equal hash must
            # not be read back as "still an untouched scaffold artifact".
            rebuilt = run_finalize(submission_dir, "--refinalize")
            self.assertEqual(0, rebuilt.returncode, rebuilt.stdout + rebuilt.stderr)
            self.assertEqual(
                f"Refinalized review-ready package: {submission_dir}",
                rebuilt.stdout.splitlines()[0],
            )

            for rel in ["proposal.md", "proposal.en.md"]:
                path = submission_dir / rel
                path.write_text(
                    path.read_text(encoding="utf-8") + "\nSecond editing round.\n", encoding="utf-8"
                )
            for rel in ["report/proposal.html", "report/proposal.en.html"]:
                path = submission_dir / rel
                path.write_text(
                    path.read_text(encoding="utf-8") + "\n<!-- second editing round -->\n",
                    encoding="utf-8",
                )
            self.assertNotEqual([], stale_hashes(submission_dir))

            refinalized = run_finalize(submission_dir, "--refinalize")
            self.assertEqual(0, refinalized.returncode, refinalized.stdout + refinalized.stderr)
            manifest = read_manifest(submission_dir)
            self.assertEqual("ready_for_review", manifest["package_state"])
            self.assertEqual([], stale_hashes(submission_dir))
            self.assertFalse(manifest["validation_claim"]["self_checked"])

            completed = run_self_check(root, submission_dir)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["can_enter_formal_review"])

    def test_refinalize_is_rejected_for_a_scaffold_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_official_site_package(root)
            submission_dir = root / "submissions" / "alice" / "scaffold-guard"
            scaffold = run_scaffold(submission_dir, cwd=root)
            self.assertEqual(0, scaffold.returncode, scaffold.stdout + scaffold.stderr)
            manifest_path = submission_dir / "manifest.json"
            before = manifest_path.read_bytes()

            rejected = run_finalize(submission_dir, "--refinalize")
            self.assertEqual(2, rejected.returncode, rejected.stdout + rejected.stderr)
            self.assertIn(
                "--refinalize only applies to a package that is already ready_for_review",
                rejected.stderr,
            )
            # The flag must never become a shortcut around the first-time baseline gate.
            self.assertEqual(before, manifest_path.read_bytes())
            self.assertEqual("scaffold", read_manifest(submission_dir)["package_state"])

            finalized = complete_scaffold(submission_dir)
            self.assertEqual(0, finalized.returncode, finalized.stdout + finalized.stderr)
            self.assertEqual("ready_for_review", read_manifest(submission_dir)["package_state"])

    def test_default_finalization_path_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_official_site_package(root)
            submission_dir = root / "submissions" / "alice" / "default-path"
            scaffold = run_scaffold(submission_dir, cwd=root)
            self.assertEqual(0, scaffold.returncode, scaffold.stdout + scaffold.stderr)

            blocked = run_finalize(submission_dir)
            self.assertEqual(1, blocked.returncode, blocked.stdout + blocked.stderr)
            self.assertIn("Submission is still a scaffold:", blocked.stdout)
            self.assertIn("proposal.md still contains the SCAFFOLD-DRAFT marker", blocked.stdout)
            self.assertIn("proposal.md is unchanged from the generated scaffold", blocked.stdout)
            self.assertIn(
                "drawings/a0-boards.pdf is unchanged from the placeholder drawing", blocked.stdout
            )

            finalized = complete_scaffold(submission_dir)
            self.assertEqual(0, finalized.returncode, finalized.stdout + finalized.stderr)
            self.assertEqual(
                f"Review-ready package: {submission_dir}", finalized.stdout.splitlines()[0]
            )
            self.assertEqual([], stale_hashes(submission_dir))

            repeated = run_finalize(submission_dir)
            self.assertEqual(2, repeated.returncode, repeated.stdout + repeated.stderr)
            self.assertIn("package_state must be scaffold before finalization", repeated.stderr)
            self.assertIn("--refinalize", repeated.stderr)

    def test_refinalize_still_rejects_markers_zero_page_drawings_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            submission_dir = make_ready_for_review_package(root, "refinalize-guard")

            proposal = submission_dir / "proposal.md"
            proposal.write_text(
                proposal.read_text(encoding="utf-8") + "\nSCAFFOLD-DRAFT\n", encoding="utf-8"
            )
            (submission_dir / "drawings" / "a0-boards.pdf").write_bytes(b"%PDF-1.4\n/Count 0\n")
            (submission_dir / "visual" / "index.html").unlink()

            rejected = run_finalize(submission_dir, "--refinalize")
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            self.assertIn("proposal.md still contains the SCAFFOLD-DRAFT marker", rejected.stdout)
            self.assertIn("drawings/a0-boards.pdf has no pages", rejected.stdout)
            self.assertIn("visual/index.html is missing", rejected.stdout)
            self.assertEqual("ready_for_review", read_manifest(submission_dir)["package_state"])


if __name__ == "__main__":
    unittest.main()
