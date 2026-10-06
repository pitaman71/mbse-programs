"""The standards of Verilog (IEEE 1364) and SystemVerilog (IEEE 1800), each reading source text into Verilog trees and
printing them back."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..Framework.Errors import PrintError
from ..Framework.Syntax import Standard, SyntaxNode, children
from . import Syntax as S
from . import _Reader
from ._Printer import Printer

__all__ = ["VerilogStandard"]


class VerilogStandard(Standard):
    """A standard of SystemVerilog, such as `VerilogStandard(2023)`, or with `family` 'Verilog' of Verilog, such as
    `VerilogStandard(2005, "Verilog")`: slang reads its source text, which must use only the kinds and features the
    standard has, and `Printer` prints its trees in one fixed layout. Its `version` is the standard's year."""

    def __init__(self, year: int, family: str = S.SV):
        super().__init__(S.LANGUAGE, family, year)
        self._printer = Printer()

    def label(self, version: int) -> str:
        return f"{self.family}-{version}"

    def parse(self, text: str, include_paths: Sequence[str] = (), defines: Sequence[str] = ()) -> S.SourceText:
        """The tree of a source file. `include_paths` are searched for `` `include `` files, and `defines` (`NAME` or
        `NAME=value`) are predefined macros. Raises `ParseError` at the first error slang reports, at what the reader
        does not support, or at the first construct the standard lacks."""
        unit, positions, source = _Reader.parse(text, include_paths, defines)
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
        """The source text of a tree: source text as a file, any other syntax node as the text it stands for. Raises
        `PrintError` for an invalid tree, or one with a construct the standard lacks."""
        problems = self.language.validate(node)
        if not problems:
            problems = [f"{p}, but this is {self.name()}" for p in self.check(node)]
        if problems:
            raise PrintError(problems[0])
        return self._printer.print(node)
