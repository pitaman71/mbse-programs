"""Errors: the exceptions parsing and printing raise beyond mbse-schemas' own, named the same in every implementation.

Both are `ValueError`s. `ParseError` locates its problem in the source text, with a 1-based line and column.
"""

from __future__ import annotations

__all__ = ["ParseError", "PrintError"]


class ParseError(ValueError):
    """Source text that is not a program of the standard: a syntax error, or a construct the standard lacks."""

    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"line {line}, column {column}: {message}")
        self.line, self.column = line, column


class PrintError(ValueError):
    """A tree the standard cannot print: it is invalid, or uses a construct the standard lacks."""
