"""The framework every language implements: protocols for syntax trees (`Syntax`) and the entities they declare
(`Definitions`), and the machinery that implements them. See docs/PROGRAMS.md."""

from . import Definitions, Errors, Syntax

__all__ = ["Definitions", "Errors", "Syntax"]
