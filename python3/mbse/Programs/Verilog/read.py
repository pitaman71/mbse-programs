"""Reads Verilog source text for another implementation, since slang runs only here: `python -m
mbse.Programs.Verilog.read` takes a request on standard input and writes the response on standard output, both JSON.

The request is `{"text", "year", "family", "include_paths", "defines"}`, as `VerilogStandard(year, family).parse`
takes them. The response is `{"tree": snapshot}`, the tree as `JSON.ToJSON(...).Reachable` writes it, or
`{"error": message, "line": line, "column": column}` when the text does not parse, as `ParseError` locates it.
"""

from __future__ import annotations

import json
import sys

from mbse.Schemas.Framework import JSON

from ..Framework.Errors import ParseError
from . import Syntax as S
from ._Standard import VerilogStandard

__all__ = ["respond"]


def respond(request: str) -> str:
    """The response to a request."""
    fields = JSON.loads(request)
    standard = VerilogStandard(fields["year"], fields["family"])
    try:
        unit = standard.parse(fields["text"], include_paths=fields["include_paths"], defines=fields["defines"])
    except ParseError as error:
        message = str(error).removeprefix(f"line {error.line}, column {error.column}: ")
        return json.dumps({"error": message, "line": error.line, "column": error.column}, ensure_ascii=False)
    return json.dumps({"tree": JSON.ToJSON(S.LANGUAGE.Builders).Reachable(S.SourceText.Schema, unit)},
                      ensure_ascii=False)


if __name__ == "__main__":
    sys.stdout.buffer.write(respond(sys.stdin.buffer.read().decode("utf-8")).encode("utf-8"))
