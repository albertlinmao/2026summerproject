"""Validate the feature 002 API contracts as two separate documents.

Constitution principle 12 ("no API spec -> no merge", P12) needs a runnable
check. The two contracts are deliberately NOT merged: openapi.yaml (user
service, /api/v1) and dashboard-bff.yaml (dashboard BFF, /api) have different
base paths and trust models, and a merged document silently collapses duplicate
path keys. Each file is therefore parsed and validated on its own.

Checks per document:
  1. Strict YAML parse - duplicate mapping keys are an error (the failure mode
     merging would create is the failure mode this catches).
  2. Required OpenAPI 3 structure: openapi, info, non-empty paths.
  3. Every operation declares at least one response.
  4. Every $ref is local ('#/...') and resolves inside the same document -
     a contract must not reach into the other one.
  5. If openapi-spec-validator is installed, full JSON-Schema validation.

Usage:
    python scripts/validate_contracts.py                 # both contracts
    python scripts/validate_contracts.py path/to/one.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable, List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACTS = [
    REPO_ROOT / "specs" / "002-club-user-integration" / "contracts" / "openapi.yaml",
    REPO_ROOT / "specs" / "002-club-user-integration" / "contracts" / "dashboard-bff.yaml",
]

OPERATION_KEYS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


class ContractError(Exception):
    pass


class _StrictLoader(yaml.SafeLoader):
    pass


def _construct_no_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise ContractError(
                f"duplicate key {key!r} at line {key_node.start_mark.line + 1} "
                "- a merged document collapses duplicate paths silently"
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_no_duplicates
)


def load_strict(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    doc = yaml.load(text, Loader=_StrictLoader)
    if not isinstance(doc, dict):
        raise ContractError("document root is not a mapping")
    return doc


def _walk(node: Any) -> Iterable[Any]:
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _resolve_pointer(root: Any, pointer: str) -> Any:
    current = root
    for raw_part in pointer.lstrip("#").split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ContractError(f"unresolvable $ref fragment '#/{part}'")
    return current


def structural_checks(doc: dict) -> List[str]:
    problems: List[str] = []

    version = doc.get("openapi")
    if not isinstance(version, str) or not version.startswith("3."):
        problems.append(f"missing or non-3.x 'openapi' version: {version!r}")

    info = doc.get("info")
    if not isinstance(info, dict) or not info.get("title") or not info.get("version"):
        problems.append("'info.title' and 'info.version' are required")

    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        problems.append("'paths' must be a non-empty mapping")
        return problems

    operations = 0
    for path, item in paths.items():
        if not isinstance(item, dict):
            problems.append(f"path {path}: path item is not a mapping")
            continue
        op_keys = [k for k in OPERATION_KEYS if k in item]
        if not op_keys and "$ref" not in item:
            problems.append(f"path {path}: no operation defined")
        for op_key in op_keys:
            operations += 1
            op = item[op_key]
            if not isinstance(op, dict):
                problems.append(f"{op_key.upper()} {path}: operation is not a mapping")
                continue
            responses = op.get("responses")
            if not isinstance(responses, dict) or not responses:
                problems.append(f"{op_key.upper()} {path}: declares no responses")

    for node in _walk(doc):
        if isinstance(node, dict) and "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str):
                problems.append(f"$ref is not a string: {ref!r}")
                continue
            if not ref.startswith("#"):
                problems.append(
                    f"external $ref {ref!r}: contracts are validated as independent "
                    "documents and must not reference each other"
                )
                continue
            try:
                _resolve_pointer(doc, ref)
            except ContractError as exc:
                problems.append(f"$ref {ref!r}: {exc}")

    print(f"  paths: {len(paths)}, operations: {operations}")
    return problems


def spec_validator_check(path: Path) -> List[str]:
    try:
        from openapi_spec_validator import validate
        from openapi_spec_validator.readers import read_from_filename
    except ImportError:
        print("  openapi-spec-validator not installed - skipping JSON-Schema pass")
        return []

    try:
        document, _ = read_from_filename(str(path))
        validate(document)
    except Exception as exc:  # validator raises its own exception hierarchy
        return [f"openapi-spec-validator: {exc}"]
    print("  openapi-spec-validator: OK")
    return []


def validate_file(path: Path) -> List[str]:
    try:
        shown = path.relative_to(REPO_ROOT)
    except ValueError:
        shown = path
    print(f"Validating {shown}")
    if not path.is_file():
        return [f"file not found: {path}"]
    try:
        doc = load_strict(path)
    except ContractError as exc:
        return [str(exc)]
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]
    return structural_checks(doc) + spec_validator_check(path)


def main(argv: List[str]) -> int:
    paths = [Path(a).resolve() for a in argv] if argv else DEFAULT_CONTRACTS

    failures = 0
    for path in paths:
        problems = validate_file(path)
        if problems:
            failures += len(problems)
            for problem in problems:
                print(f"  FAIL: {problem}")
        else:
            print("  OK")
        print()

    if failures:
        print(f"{failures} problem(s) in {len(paths)} contract(s)")
        return 1
    print(f"All {len(paths)} contract(s) valid, each as its own document.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
