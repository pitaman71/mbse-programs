"""The framework every language implements: protocols for syntax trees (`Syntax`) and the entities they declare
(`Definitions`), and the machinery that implements them. See mbse-basis
[CAP-084: program trees as data](../../../../../mbse-basis/docs/capabilities/CAP-084.md)."""

from . import Definitions, Errors, Syntax

__all__ = ["Definitions", "Errors", "Syntax"]
