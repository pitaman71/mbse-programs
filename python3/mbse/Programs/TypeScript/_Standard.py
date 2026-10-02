"""The versions of TypeScript and the editions of ECMAScript, each parsing source text into TypeScript trees and
printing them back, with JSX or without."""

from __future__ import annotations

from typing import Any

from ..Framework.Errors import PrintError
from ..Framework.Syntax import SyntaxNode, Standard, children
from . import Syntax as S
from . import _Parser
from ._Printer import Printer

__all__ = ["TypeScriptStandard", "ECMAScriptStandard"]


class _Standard(Standard):
    """A standard of the TypeScript language: tree-sitter-typescript parses its source text (its `tsx` grammar with
    `jsx`), which must use only the kinds and features the standard has, and `Printer` prints its trees in one fixed
    layout. With `jsx`, source text may hold JSX but not the type assertion `<T>x`; without it, the reverse."""

    def __init__(self, family: str, version: int, jsx: bool):
        super().__init__(S.LANGUAGE, family, version)
        self.jsx = jsx
        self._printer = Printer(jsx)

    def problems(self, node: SyntaxNode) -> list[str]:
        if self.jsx and isinstance(node, S.TSTypeAssertion):
            return [f"{node.KIND} is not allowed with JSX"]
        if not self.jsx and type(node).KIND.startswith("JSX"):
            return [f"{node.KIND} needs JSX"]
        return super().problems(node)

    def parse(self, text: str) -> S.Program:
        """The tree of a source file. Raises `ParseError` at the first syntax error, or at the first construct the
        standard lacks."""
        program, positions, source = _Parser.parse(text, self.jsx)
        stack: list[SyntaxNode] = [program]
        while stack:
            node = stack.pop()
            offset = positions[id(node)]  # the parser places every syntax node
            problems = self.problems(node)
            if problems:
                raise source.error(f"{problems[0]}, but this is {self.name()}", offset)
            stack.extend(child for _, _, child in reversed(children(node)))
        return program

    def print(self, node: Any) -> str:
        """The source text of a tree: a program as a file, any other syntax node as the text it stands for. Raises
        `PrintError` for an invalid tree, or one with a construct the standard lacks."""
        problems = self.language.validate(node)
        if not problems:
            problems = [f"{p}, but this is {self.name()}" for p in self.check(node)]
        if problems:
            raise PrintError(problems[0])
        return self._printer.print(node)


class TypeScriptStandard(_Standard):
    """A version of TypeScript, such as `TypeScriptStandard(5, 9)`, or with `jsx` its TSX. Its `version` is
    `100 * major + minor`."""

    def __init__(self, major: int, minor: int, jsx: bool = False):
        super().__init__(S.TS, 100 * major + minor, jsx)

    def label(self, version: int) -> str:
        return f"TypeScript {version // 100}.{version % 100}" + (" with JSX" if self.jsx else "")


class ECMAScriptStandard(_Standard):
    """An edition of ECMAScript, such as `ECMAScriptStandard(2025)`, or with `jsx` its JSX: JavaScript, which has
    none of TypeScript's own syntax. Its `version` is the edition's year."""

    def __init__(self, year: int, jsx: bool = False):
        super().__init__(S.ES, year, jsx)

    def label(self, version: int) -> str:
        return f"ES{version}" + (" with JSX" if self.jsx else "")
