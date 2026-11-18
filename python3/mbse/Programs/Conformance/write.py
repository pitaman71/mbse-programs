"""Writes this implementation's conformance files: `python -m mbse.Programs.Conformance.write [directory]`.

For each source in `conformance/sources` of a language ported so far (`LANGUAGES`: Python 3's `.py`, TypeScript 5's
`.ts` and `.tsx`, C's `.c`), it writes the frame of the transaction its parse gives (`<source>.json`), as the user decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md),
"The corpora as frames"): a `References.OfFrame`, binding the workspace and the file and assigning the file its
tree, one nested value, as the whole tree is values ("Stage 3: the whole tree as values"), as
`Plain.ToPlain(store).Value` writes it; and the text the stored file prints to (`<source>`, its suffix kept). Every
implementation must write the same bytes. The default directory is `conformance/python3` at the repository root.

It also writes, beside each program of `conformance/transpilers/typescript-to-python`, the Python it translates to
(`<program>.py`): the program parsed into a store holding both languages (`Transpilers.store()`), transpiled into the
module at `<program>.py`, and that module printed.

The port brings the languages over one stage at a time: the other languages' sources (C++ and SystemVerilog) and
grammars are set aside until their stages, their files left as 0.3 wrote them.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mbse.Programs import C, Python3, Transpilers, TypeScript5
from mbse.Schemas.Framework import Plain, References

ROOT = Path(__file__).resolve().parents[4] / "conformance"
DEFAULT = ROOT / "python3"


LANGUAGES = {".py": Python3, ".ts": TypeScript5, ".tsx": TypeScript5, ".c": C}
"""The language each source is, by its suffix."""


def frame(store: object, parse: Callable[[Any], Any]) -> str:
    """The frame of a parse's transaction, executed in `store`, as JSON, two-space indented."""
    (given,) = store.transaction(parse)  # type: ignore[attr-defined]
    schema = store.registered("References.OfFrame")  # type: ignore[attr-defined]
    written = Plain.ToPlain(store).Value(schema, References.of(store, given))
    return json.dumps(written, indent=2, ensure_ascii=False) + "\n"


def render(sources: Path = ROOT / "sources") -> dict[str, str]:
    """File name -> text, for every file this implementation writes."""
    files = {}
    for source in sorted(path for path in sources.iterdir() if path.suffix in LANGUAGES):
        language = LANGUAGES[source.suffix]
        store = language.store()
        files[f"{source.stem}.json"] = frame(store, language.Parse.parse(source.read_text(encoding="utf-8"), source.name))
        files[source.name] = language.Print.print_module(store, source.name)
    return files


def transpiled(programs: Path = ROOT / "transpilers" / "typescript-to-python") -> dict[str, str]:
    """File name -> text, for the Python each TypeScript program translates to."""
    store = Transpilers.store()
    files = {}
    for program in sorted(programs.glob("*.ts")):
        target = f"{program.stem}.py"
        store.transaction(TypeScript5.Parse.parse(program.read_text(encoding="utf-8"), program.name))
        store.transaction(Transpilers.TypeScriptToPython.transpile(store, program.name, target))
        files[target] = Python3.Print.print_module(store, target)
    return files


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
