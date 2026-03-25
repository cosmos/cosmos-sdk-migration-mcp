#!/usr/bin/env python3
"""Validate package version metadata before building or publishing."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
PACKAGE_INIT_FILE = REPO_ROOT / "src" / "cosmos_migration_mcp" / "__init__.py"
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def read_package_version() -> str | None:
    match = VERSION_PATTERN.search(PACKAGE_INIT_FILE.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group(1)


def normalize_tag(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag",
        help="Git tag to compare against the project version. Accepts 'v0.1.1' or '0.1.1'.",
    )
    args = parser.parse_args()

    pyproject_version = read_pyproject_version()
    package_version = read_package_version()

    errors: list[str] = []
    if package_version is None:
        errors.append(f"missing __version__ assignment in {PACKAGE_INIT_FILE}")
    elif package_version != pyproject_version:
        errors.append(
            "package version mismatch: "
            f"pyproject.toml has {pyproject_version}, "
            f"but src/cosmos_migration_mcp/__init__.py has {package_version}"
        )

    if args.tag:
        tag_version = normalize_tag(args.tag)
        if tag_version != pyproject_version:
            errors.append(
                "release tag mismatch: "
                f"git tag {args.tag} does not match pyproject.toml version {pyproject_version}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Version metadata OK: {pyproject_version}")
    if args.tag:
        print(f"Release tag OK: {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
