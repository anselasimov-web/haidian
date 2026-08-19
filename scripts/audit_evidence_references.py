#!/usr/bin/env python3
"""Audit proposal evidence markers against the files they claim to reference.

This is a read-only diagnostic.  It does not change formal submission readiness
or any existing validation gate.  It resolves the five proposal-v2 evidence
marker kinds documented in ``templates/proposal.md``:

- ``[source:ID]`` against package/local and repository source registries;
- ``[standard:ID]`` against the package standard matrix and central standards;
- ``[depth:ID]`` against the package design-depth matrix;
- ``[metric:KEY]`` against package ``metrics.json``;
- ``[data:path[#feature-id]]`` against an existing JSON/GeoJSON file and,
  when a feature fragment is supplied, the feature IDs inside it.

The command exits 0 when every marker resolves and 1 when any dangling marker
is found.  Use ``--json`` for machine-readable output.  Because this audit can
surface legacy inconsistencies, it is intentionally separate from the formal
validator until corpus impact and compatibility have been reviewed.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

REFERENCE_RE = re.compile(r"\[(source|standard|depth|data|metric):([^\]\s]+)\]")


@dataclass(frozen=True)
class Finding:
    proposal: str
    kind: str
    value: str
    reason: str


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def collect_ids(raw: Any, list_keys: Iterable[str], id_keys: Iterable[str]) -> set[str]:
    if not isinstance(raw, dict):
        return set()
    values: list[Any] = []
    for key in list_keys:
        candidate = raw.get(key)
        if isinstance(candidate, list):
            values.extend(candidate)
    result: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        for key in id_keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                result.add(value.strip())
    return result


def source_ids(repo_root: Path, package: Path) -> set[str]:
    result: set[str] = set()
    for path in (
        package / "sources.json",
        repo_root / "data" / "source_registry.json",
        repo_root / "sources" / "public-sources.json",
    ):
        raw = load_json(path)
        result.update(
            collect_ids(
                raw,
                ("sources", "items", "records"),
                ("id", "source_id", "registry_source_id"),
            )
        )
    return result


def standard_ids(repo_root: Path, package: Path) -> set[str]:
    result = collect_ids(
        load_json(package / "standard_matrix.json"),
        ("standards", "items"),
        ("standard_id", "id"),
    )
    result.update(
        collect_ids(
            load_json(repo_root / "brief" / "site-package" / "standards" / "standards.json"),
            ("standards", "items"),
            ("standard_id", "id"),
        )
    )
    return result


def depth_ids(package: Path) -> set[str]:
    return collect_ids(
        load_json(package / "design_depth_matrix.json"),
        ("items", "depth_items"),
        ("item_id", "depth_id", "id"),
    )


def metric_ids(package: Path) -> set[str]:
    raw = load_json(package / "metrics.json")
    if not isinstance(raw, dict):
        return set()
    metrics = raw.get("metrics")
    if isinstance(metrics, dict):
        return {str(key) for key in metrics}
    if isinstance(metrics, list):
        result: set[str] = set()
        for item in metrics:
            if isinstance(item, dict):
                for key in ("metric_id", "id", "key", "name"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        result.add(value.strip())
                        break
        return result
    return set()


def feature_ids(raw: Any) -> set[str]:
    if not isinstance(raw, dict):
        return set()
    features = raw.get("features")
    if not isinstance(features, list):
        return set()
    result: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict):
            continue
        value = feature.get("id")
        if isinstance(value, (str, int)):
            result.add(str(value))
        properties = feature.get("properties")
        if isinstance(properties, dict):
            value = properties.get("id")
            if isinstance(value, (str, int)):
                result.add(str(value))
    return result


def safe_data_path(repo_root: Path, package: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    # Proposal-local artifacts use paths such as geometry/land_use.geojson;
    # central evidence uses paths such as brief/site-package/ranges/....
    package_path = package / candidate
    if package_path.exists():
        resolved = package_path.resolve()
    else:
        resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return resolved


def data_reference_reason(repo_root: Path, package: Path, value: str) -> str | None:
    raw_path, separator, fragment = value.partition("#")
    path = safe_data_path(repo_root, package, raw_path)
    if path is None:
        return "path escapes the repository or is not a permitted relative path"
    if not path.is_file():
        return f"referenced data file does not exist: {raw_path}"
    if not separator or not fragment:
        return None
    raw = load_json(path)
    ids = feature_ids(raw)
    if not ids:
        return f"fragment `{fragment}` cannot resolve because the file has no feature IDs"
    if "~" in fragment:
        start, end = fragment.split("~", 1)
        if start in ids and end in ids:
            return None
        return f"feature range endpoints do not resolve: {fragment}"
    if fragment not in ids:
        return f"feature ID does not resolve: {fragment}"
    return None


def audit_proposal(repo_root: Path, proposal: Path) -> list[Finding]:
    package = proposal.parent
    try:
        text = proposal.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [Finding(str(proposal), "proposal", str(proposal), f"cannot read proposal: {exc}")]

    registries = {
        "source": source_ids(repo_root, package),
        "standard": standard_ids(repo_root, package),
        "depth": depth_ids(package),
        "metric": metric_ids(package),
    }
    findings: list[Finding] = []
    for kind, value in REFERENCE_RE.findall(text):
        reason: str | None = None
        if kind == "data":
            reason = data_reference_reason(repo_root, package, value)
        elif value not in registries[kind]:
            reason = f"{kind} ID does not resolve in the corresponding registry"
        if reason:
            display = str(proposal.relative_to(repo_root)) if proposal.is_relative_to(repo_root) else str(proposal)
            findings.append(Finding(display, kind, value, reason))
    return list(dict.fromkeys(findings))


def proposal_paths(repo_root: Path, target: str | None, audit_all: bool) -> list[Path]:
    if audit_all:
        return sorted((repo_root / "submissions").glob("*/*/proposal*.md"))
    if target is None:
        raise SystemExit("provide a submission directory/proposal path or use --all")
    path = Path(target)
    if not path.is_absolute():
        path = repo_root / path
    if path.is_dir():
        candidates = [path / "proposal.md"]
        candidates.extend(sorted(path.glob("proposal.*.md")))
        return [candidate for candidate in candidates if candidate.is_file()]
    return [path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="submission directory or proposal Markdown path")
    parser.add_argument("--repo-root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--all", action="store_true", help="audit all proposal*.md files under submissions/")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    proposals = proposal_paths(repo_root, args.target, args.all)
    findings: list[Finding] = []
    for proposal in proposals:
        findings.extend(audit_proposal(repo_root, proposal.resolve()))

    if args.json:
        print(
            json.dumps(
                {
                    "proposal_count": len(proposals),
                    "finding_count": len(findings),
                    "findings": [asdict(item) for item in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print("# Evidence reference audit")
        print(f"Proposals: {len(proposals)}")
        print(f"Dangling references: {len(findings)}")
        for item in findings:
            print(f"- {item.proposal}: [{item.kind}:{item.value}] — {item.reason}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
