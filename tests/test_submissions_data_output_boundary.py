import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_submissions_data.py"


class SubmissionsDataOutputBoundaryTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        publication = root / "gallery-publication.json"
        publication.write_text('{"version": 1, "entries": []}\n', encoding="utf-8")
        return publication

    def run_generator(
        self, root: Path, output: Path, *, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(root),
            "--out",
            str(output),
        ]
        if check:
            command.append("--check")
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_output_cannot_overwrite_gallery_publication_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publication = self.make_repo(root)
            original = publication.read_bytes()

            result = self.run_generator(root, publication)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output must not overwrite gallery publication input", result.stderr)
            self.assertEqual(publication.read_bytes(), original)

    def test_symlink_alias_to_gallery_publication_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publication = self.make_repo(root)
            alias = root / "gallery-output.js"
            try:
                alias.symlink_to(publication)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            original = publication.read_bytes()

            result = self.run_generator(root, alias)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output must not overwrite gallery publication input", result.stderr)
            self.assertEqual(publication.read_bytes(), original)

    def test_hardlink_alias_to_gallery_publication_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publication = self.make_repo(root)
            alias = root / "gallery-output.js"
            try:
                alias.hardlink_to(publication)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")
            original = publication.read_bytes()

            result = self.run_generator(root, alias)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output must not overwrite gallery publication input", result.stderr)
            self.assertEqual(publication.read_bytes(), original)

    def test_distinct_output_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_repo(root)
            output = root / "submissions-data.js"

            result = self.run_generator(root, output)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("window.HAIDIAN_SUBMISSIONS", output.read_text(encoding="utf-8"))

    def test_check_mode_does_not_rewrite_publication_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publication = self.make_repo(root)
            original = publication.read_bytes()

            result = self.run_generator(root, publication, check=True)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(publication.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
