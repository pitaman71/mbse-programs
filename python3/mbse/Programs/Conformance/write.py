"""Writes this implementation's conformance files: `python -m mbse.Programs.Conformance.write [directory]`.

For each source in `conformance/sources`, it writes the tree the source parses to, as a JSON snapshot
(`<source>.json`), and the text that tree prints to (`<source>.cpp`); and it writes each language's grammar
(`<language>.grammar.json`). Every implementation must write the same bytes. The default directory is
`conformance/python3` at the repository root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mbse.Programs.Ccpp import Ccpp20, Syntax
from mbse.Schemas.Framework import JSON

ROOT = Path(__file__).resolve().parents[4] / "conformance"
DEFAULT = ROOT / "python3"
STANDARDS = {".cpp": Ccpp20}


def render(sources: Path = ROOT / "sources") -> dict[str, str]:
    """File name -> text, for every file this implementation writes."""
    files = {"Ccpp.grammar.json": json.dumps(Syntax.LANGUAGE.grammar(), indent=1, ensure_ascii=False) + "\n"}
    for source in sorted(sources.iterdir()):
        standard = STANDARDS[source.suffix]
        unit = standard.parse(source.read_text(encoding="utf-8"))
        files[f"{source.stem}.json"] = JSON.ToJSON.Reachable(Syntax.TranslationUnit.Schema, unit, indent=2) + "\n"
        files[f"{source.stem}{source.suffix}"] = standard.print(unit)
    return files


def main(directory: Path = DEFAULT) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in render().items():
        (directory / name).write_text(text, encoding="utf-8")
        print("wrote", directory / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
