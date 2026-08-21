from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "prepare_source_registry_draft.py"


def write_seed(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "title", "url", "topic"])
        writer.writeheader()
        writer.writerow(
            {
                "id": "policy_001",
                "title": "Valid source",
                "url": "https://example.com/source",
                "topic": "test",
            }
        )


def write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "updated_date": "2026-08-22",
                "sources": [],
            }
        ),
        encoding="utf-8",
    )


def run_generator(root: Path, seed: Path, registry: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(root),
            "--input",
            str(seed),
            "--existing-registry",
            str(registry),
            "--out",
            str(output),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class SourceRegistryDraftOutputBoundaryTests(unittest.TestCase):
    def test_output_cannot_overwrite_input_sources(self) -> None:
        for target_name in ("seed", "registry"):
            with self.subTest(target=target_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                seed = root / "seed.csv"
                registry = root / "data" / "source_registry.json"
                write_seed(seed)
                write_registry(registry)
                target = seed if target_name == "seed" else registry
                original = target.read_bytes()

                completed = run_generator(root, seed, registry, target)

                self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
                self.assertIn("--out must not overwrite", completed.stderr)
                self.assertEqual(target.read_bytes(), original)

    def test_hardlink_alias_to_existing_registry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.csv"
            registry = root / "data" / "source_registry.json"
            alias = root / "draft.json"
            write_seed(seed)
            write_registry(registry)
            try:
                alias.hardlink_to(registry)
            except OSError as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")
            original = registry.read_bytes()

            completed = run_generator(root, seed, registry, alias)

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertIn("--out must not overwrite the existing registry", completed.stderr)
            self.assertEqual(registry.read_bytes(), original)
            self.assertTrue(alias.samefile(registry))

    def test_symlink_alias_to_input_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.csv"
            registry = root / "data" / "source_registry.json"
            alias = root / "draft.json"
            write_seed(seed)
            write_registry(registry)
            try:
                alias.symlink_to(seed)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            original = seed.read_bytes()

            completed = run_generator(root, seed, registry, alias)

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertIn("--out must not overwrite the input source", completed.stderr)
            self.assertEqual(seed.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
