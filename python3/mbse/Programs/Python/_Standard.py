"""The versions of Python, each parsing source text into Python trees and printing them back."""

from __future__ import annotations

from typing import Any

from ..Framework.Errors import PrintError
from ..Framework.Syntax import SyntaxNode, Standard, children
from . import Syntax as S
from . import _Parser
from ._Printer import Printer

__all__ = ["PythonStandard"]


class PythonStandard(Standard):
    """A version of Python, such as `PythonStandard(3, 14)`: tree-sitter-python parses its source text, which must use
    only the kinds and features the version has, and `Printer` prints its trees in one fixed layout. Its `version`
    is `100 * major + minor`."""

    def __init__(self, major: int, minor: int):
        super().__init__(S.LANGUAGE, S.PY, 100 * major + minor)
        self._printer = Printer()

    def label(self, version: int) -> str:
        return f"Python {version // 100}.{version % 100}"

    def parse(self, text: str) -> S.Module:
        """The tree of a source file. Raises `ParseError` at the first syntax error, or at the first construct the
        version lacks."""
        module, positions, source = _Parser.parse(text)
        stack: list[SyntaxNode] = [module]
        while stack:
            node = stack.pop()
            offset = positions[id(node)]  # the parser places every syntax node
            problems = self.problems(node)
            if problems:
                raise source.error(f"{problems[0]}, but this is {self.name()}", offset)
            stack.extend(child for _, _, child in reversed(children(node)))
        return module

    def print(self, node: Any) -> str:
        """The source text of a tree: a module as a file, any other syntax node as the text it stands for. Raises
        `PrintError` for an invalid tree, or one with a construct the version lacks."""
        problems = self.language.validate(node)
        if not problems:
            problems = [f"{p}, but this is {self.name()}" for p in self.check(node)]
        if problems:
            raise PrintError(problems[0])
        return self._printer.print(node)
