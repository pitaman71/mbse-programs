#!/usr/bin/env python3
"""The mbse repositories this one depends on, which live beside it as sibling checkouts.

`siblings.json`, at the repository's root, names each sibling with the version this repository was tested with:

    {"mbse-schemas": {"repository": "git@github.com:pitaman71/mbse-schemas.git", "version": "0.1.0"}}

Development uses the siblings as they are, so that a change in one is seen at once by the others: Python installs
`../../<sibling>/python3` (`tool.uv.sources`) and TypeScript `file:../../<sibling>/typescript5`. The version is the
contract: a sibling is compatible when it has the same major version (the same minor below 1.0) and is no older, and
`python3/pyproject.toml` requires exactly that range, so uv refuses an incompatible sibling too. A release of a sibling
is the tag `v<version>`.

    python3 scripts/siblings.py check [--strict]   siblings present, compatible, and required alike by pyproject.toml;
                                                   --strict also requires each at its pinned tag, clean (for releases)
    python3 scripts/siblings.py clone              clones each missing sibling at its pinned tag (fresh clones, CI)
    python3 scripts/siblings.py pin                records each sibling's current version, here and in pyproject.toml

Standard library only, so that it runs before anything is installed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "siblings.json"
PYPROJECT = ROOT / "python3" / "pyproject.toml"


def parse(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        raise SystemExit(f"not a version: {version!r}")
    major, minor, patch = (int(g) for g in match.groups())
    return major, minor, patch


def bound(version: str) -> str:
    """The first version that is no longer compatible with `version`."""
    major, minor, _ = parse(version)
    return f"{major + 1}.0" if major > 0 else f"0.{minor + 1}"


def requirement(version: str) -> str:
    return f">={version},<{bound(version)}"


def compatible(pinned: str, actual: str) -> bool:
    p, a = parse(pinned), parse(actual)
    same = p[0] == a[0] and (p[0] > 0 or p[1] == a[1])
    return same and a >= p


def version_of(sibling: Path) -> str:
    """The sibling's version, which its Python and TypeScript packages must agree on."""
    python = re.search(r'^version = "([^"]+)"', (sibling / "python3" / "pyproject.toml").read_text(), re.M)
    typescript = json.loads((sibling / "typescript5" / "package.json").read_text())["version"]
    if python is None or python.group(1) != typescript:
        raise SystemExit(f"{sibling.name}: python3 and typescript5 disagree on the version")
    return typescript


def git(sibling: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(sibling), *args], capture_output=True, text=True).stdout.strip()


def required(name: str) -> list[str]:
    """The version ranges pyproject.toml requires of `name`, with or without extras."""
    return re.findall(rf'"{re.escape(name)}(?:\[[^\]]*\])?([^"]*)"', PYPROJECT.read_text())


def check(strict: bool) -> int:
    failures = 0
    for name, entry in json.loads(CONFIG.read_text()).items():
        sibling, pinned = ROOT.parent / name, entry["version"]
        if not sibling.is_dir():
            print(f"{name}: missing at {sibling}; run python3 scripts/siblings.py clone")
            failures += 1
            continue
        actual = version_of(sibling)
        ranges = required(name)
        if not compatible(pinned, actual):
            print(f"{name}: {actual} is not compatible with the pinned {pinned}")
            failures += 1
        if not ranges or any(r != requirement(pinned) for r in ranges):
            print(f"{name}: pyproject.toml must require {name}{requirement(pinned)}, not {ranges}; run pin")
            failures += 1
        at_tag = git(sibling, "rev-parse", "HEAD") == git(sibling, "rev-parse", f"v{pinned}^{{commit}}")
        clean = not git(sibling, "status", "--porcelain")
        if not (at_tag and clean):
            where = "has changes" if at_tag else f"is not at v{pinned}"
            if strict:
                print(f"{name}: {where}; a release is tested with its siblings at their pinned tags")
                failures += 1
            else:
                print(f"{name}: {actual}, {where} (developing against the sibling as it is)")
        else:
            print(f"{name}: {actual}, at v{pinned}")
    return 1 if failures else 0


def clone() -> int:
    for name, entry in json.loads(CONFIG.read_text()).items():
        sibling = ROOT.parent / name
        if sibling.is_dir():
            print(f"{name}: present")
            continue
        tag = f"v{entry['version']}"
        subprocess.run(["git", "clone", "--branch", tag, entry["repository"], str(sibling)], check=True)
    return 0


def pin() -> int:
    config = json.loads(CONFIG.read_text())
    text = PYPROJECT.read_text()
    for name, entry in config.items():
        entry["version"] = version_of(ROOT.parent / name)
        text = re.sub(rf'"({re.escape(name)}(?:\[[^\]]*\])?)[^"]*"', rf'"\g<1>{requirement(entry["version"])}"', text)
        print(f"{name}: pinned {entry['version']}")
    CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    PYPROJECT.write_text(text)
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "check":
        sys.exit(check("--strict" in sys.argv[2:]))
    if command in ("clone", "pin"):
        sys.exit(clone() if command == "clone" else pin())
    raise SystemExit(__doc__)
