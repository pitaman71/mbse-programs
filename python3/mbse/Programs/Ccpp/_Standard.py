"""The standards of C and C++, each parsing source text into Ccpp trees and printing them back."""

from __future__ import annotations

from typing import Any

from ..Framework.Errors import PrintError
from ..Framework.Syntax import SyntaxNode, Standard, children
from . import Syntax as S
from . import _Parser
from ._Printer import Printer

__all__ = ["CcppStandard"]


class CcppStandard(Standard):
    """A standard of C++, or with `family` 'C' of C: tree-sitter-cpp parses its source text, which must use only
    the kinds and features the standard has, and `Printer` prints its trees in one fixed layout."""

    def __init__(self, year: int, family: str = S.CPP):
        super().__init__(S.LANGUAGE, family, year)
        self._printer = Printer()

    def parse(self, text: str) -> S.TranslationUnit:
        """The tree of a source file. Raises `ParseError` at the first syntax error, or at the first construct the
        standard lacks."""
        unit, positions, source = _Parser.parse(text)
        stack: list[tuple[SyntaxNode, int]] = [(unit, 0)]
        while stack:
            node, inherited = stack.pop()
            offset = positions.get(id(node), inherited)
            problems = self.problems(node)
            if problems:
                raise source.error(f"{problems[0]}, but this is {self.name()}", offset)
            stack.extend((child, offset) for _, _, child in reversed(children(node)))
        return unit

    def print(self, node: Any) -> str:
        """The source text of a tree: a translation unit as a file, any other syntax node as the text it stands for.
        Raises `PrintError` for an invalid tree, or one with a construct the standard lacks."""
        problems = self.language.validate(node)
        if not problems:
            problems = [f"{p}, but this is {self.name()}" for p in self.check(node)]
        if problems:
            raise PrintError(problems[0])
        return self._printer.print(node)


