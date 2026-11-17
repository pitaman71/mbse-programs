"""Writes this implementation's conformance files: `python -m mbse.Programs.Conformance.write [directory]`.

For each Python source in `conformance/sources`, it writes the frame of the transaction its parse gives
(`<source>.json`), as the user decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md),
"The corpora as frames"): a `References.OfFrame`, each statement's reference and the values the transaction assigned
it, as `Plain.ToPlain(store).Value` writes it; and the text the stored module prints to (`<source>.py`). Every
implementation must write the same bytes. The default directory is `conformance/python3` at the repository root.

The port brings the languages over one stage at a time: the other languages' sources, grammars and transpiled programs
are set aside until their stages, their files left as 0.3 wrote them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mbse.Programs import Python3
from mbse.Schemas.Framework import Plain, References

ROOT = Path(__file__).resolve().parents[4] / "conformance"
DEFAULT = ROOT / "python3"


def frame(store: object, text: str, path: str) -> str:
    """The frame of the transaction that parses `text` into `store` at `path`, as JSON, two-space indented."""
    (given,) = store.transaction(Python3.Parse.parse(text, path))  # type: ignore[attr-defined]
    schema = store.registered("References.OfFrame")  # type: ignore[attr-defined]
    written = Plain.ToPlain(store).Value(schema, References.of(store, given))
    return json.dumps(written, indent=2, ensure_ascii=False) + "\n"


def render(sources: Path = ROOT / "sources") -> dict[str, str]:
    """File name -> text, for every file this implementation writes."""
    files = {}
    for source in sorted(sources.glob("*.py")):
        store = Python3.store()
        files[f"{source.stem}.json"] = frame(store, source.read_text(encoding="utf-8"), source.name)
        files[source.name] = Python3.Print.print_module(store, source.name)
    return files


def main(directory: Path = DEFAULT) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in render().items():
        (directory / name).write_text(text, encoding="utf-8")
        print("wrote", directory / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
