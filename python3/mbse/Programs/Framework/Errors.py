"""Errors: the exceptions parsing, printing and transpiling raise beyond mbse-schemas' own, named the same in every
implementation.

All are `ValueError`s. `ParseError` locates its problem in the source text, with a 1-based line and column, and
`TranspileError` in the tree, with its syntax node's place.
"""

from __future__ import annotations

__all__ = ["ParseError", "PrintError", "TranspileError"]


class ParseError(ValueError):
    """Source text that is not a program of the standard: a syntax error, or a construct the standard lacks."""

    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"line {line}, column {column}: {message}")
        self.line, self.column = line, column


class PrintError(ValueError):
    """A tree the standard cannot print: it is invalid, or uses a construct the standard lacks."""


class TranspileError(ValueError):
    """A tree a transpiler cannot translate: a construct the target has no counterpart for, or one outside the
    transpiler's subset. `path` locates its syntax node in the source tree: its anchor's text, where the tree is values
    (`body[0]:expression.right`, `TypeScript5.Definitions.Anchor`), or its path in 0.3's trees, as `Parents.path` gives
    it."""

    def __init__(self, message: str, path: str):
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path
