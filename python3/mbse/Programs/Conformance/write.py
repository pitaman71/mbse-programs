"""Writes this implementation's conformance files: `python -m mbse.Programs.Conformance.write [directory]`.

For each source in `conformance/sources`, it writes the tree the source parses to, as a JSON snapshot
(`<source>.json`), and the text that tree prints to (`<source>.cpp`, `<source>.py`, `<source>.ts`, `<source>.tsx`);
and it writes each language's grammar (`<language>.grammar.json`). Every implementation must write the same bytes.
The default directory is `conformance/python3` at the repository root.

It also writes, beside each program of `conformance/transpilers/typescript-to-python`, the Python it translates to
(`<program>.py`), which every implementation must write alike too.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mbse.Programs.Ccpp import Ccpp20
from mbse.Programs.Ccpp import Syntax as CcppSyntax
from mbse.Programs.Python import Python314
from mbse.Programs.Python import Syntax as PythonSyntax
from mbse.Programs.Transpilers import TypeScriptToPython
from mbse.Programs.TypeScript import Syntax as TypeScriptSyntax
from mbse.Programs.TypeScript import TypeScript59
from mbse.Schemas.Framework import JSON

ROOT = Path(__file__).resolve().parents[4] / "conformance"
DEFAULT = ROOT / "python3"
# By a source's suffix: the standard that parses and prints it, and the kind of its tree.
STANDARDS = {".cpp": (Ccpp20, CcppSyntax.TranslationUnit), ".py": (Python314, PythonSyntax.Module),
             ".ts": (TypeScript59.STANDARD, TypeScriptSyntax.Program),
             ".tsx": (TypeScript59.JSX, TypeScriptSyntax.Program)}
LANGUAGES = [CcppSyntax.LANGUAGE, PythonSyntax.LANGUAGE, TypeScriptSyntax.LANGUAGE]


def render(sources: Path = ROOT / "sources") -> dict[str, str]:
    """File name -> text, for every file this implementation writes."""
    files = {f"{language.name()}.grammar.json": json.dumps(language.grammar(), indent=1, ensure_ascii=False) + "\n"
             for language in LANGUAGES}
    for source in sorted(sources.iterdir()):
        standard, root = STANDARDS[source.suffix]
        unit = standard.parse(source.read_text(encoding="utf-8"))
        files[f"{source.stem}.json"] = JSON.ToJSON(root.LANGUAGE.Builders).Reachable(root.Schema, unit, indent=2) + "\n"
        files[f"{source.stem}{source.suffix}"] = standard.print(unit)
    return files


def transpiled(programs: Path = ROOT / "transpilers" / "typescript-to-python") -> dict[str, str]:
    """File name -> text, for the Python each TypeScript program translates to."""
    return {f"{program.stem}.py": Python314.print(TypeScriptToPython.transpile(TypeScript59.parse(
        program.read_text(encoding="utf-8")))) for program in sorted(programs.glob("*.ts"))}


def main(directory: Path = DEFAULT) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in render().items():
        (directory / name).write_text(text, encoding="utf-8")
        print("wrote", directory / name)
    programs = ROOT / "transpilers" / "typescript-to-python"
    for name, text in transpiled(programs).items():
        (programs / name).write_text(text, encoding="utf-8")
        print("wrote", programs / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
