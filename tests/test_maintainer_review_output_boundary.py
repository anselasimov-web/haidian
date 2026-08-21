from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_formal_scorecard import run_formal_scorecard  # noqa: E402
from maintainer_review import run_maintainer_review  # noqa: E402
from review_submission import ReviewOutputError, validate_output_dir  # noqa: E402


REVIEW_SCRIPT = ROOT / "scripts" / "review_submission.py"


class MaintainerReviewOutputBoundaryTests(unittest.TestCase):
    def test_in_repo_outputs_must_stay_under_maintainer_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external:
            repo_root = Path(tmp)

            validate_output_dir(repo_root, repo_root / ".maintainer-review" / "packet")
            validate_output_dir(repo_root, Path(external) / "packet")

            for out_dir in [
                repo_root,
                repo_root / "docs" / "review",
                repo_root / "submissions" / "alice" / "plan",
            ]:
                with self.subTest(out_dir=out_dir), self.assertRaisesRegex(
                    ReviewOutputError, "must stay under `.maintainer-review/`"
                ):
                    validate_output_dir(repo_root, out_dir)

    def test_symlink_resolving_into_tracked_repo_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external:
            repo_root = Path(tmp)
            tracked = repo_root / "docs"
            tracked.mkdir()
            alias = Path(external) / "review-output"
            try:
                alias.symlink_to(tracked, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaisesRegex(ReviewOutputError, "must stay under `.maintainer-review/`"):
                validate_output_dir(repo_root, alias)

    def test_review_submission_cli_rejects_tracked_output_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            out_dir = repo_root / "docs" / "review"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REVIEW_SCRIPT),
                    "submissions/alice/plan",
                    "--repo-root",
                    str(repo_root),
                    "--out",
                    str(out_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("must stay under `.maintainer-review/`", completed.stderr)
            self.assertFalse(out_dir.exists())

    def test_maintainer_bundle_rejects_tracked_output_before_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            submission_dir = repo_root / "submissions" / "alice" / "plan"
            out_dir = repo_root / "submissions" / "alice" / "plan" / "review"

            with self.assertRaisesRegex(ReviewOutputError, "must stay under `.maintainer-review/`"):
                run_maintainer_review(repo_root, submission_dir, "alice", out_dir)

            self.assertFalse(out_dir.exists())

    def test_formal_scorecard_inherits_maintainer_output_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            submission_dir = repo_root / "submissions" / "alice" / "plan"
            out_dir = repo_root / "data" / "formal-scorecard"

            with self.assertRaisesRegex(ReviewOutputError, "must stay under `.maintainer-review/`"):
                run_formal_scorecard(repo_root, submission_dir, "alice", out_dir)

            self.assertFalse(out_dir.exists())


if __name__ == "__main__":
    unittest.main()
