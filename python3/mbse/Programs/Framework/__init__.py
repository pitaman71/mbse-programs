"""The framework every language implements: its schemas (`Model`), the entities a tree declares (`Definitions`), and
its errors. `Syntax`, the 0.3 node machinery, is set aside while the port replaces it, and is imported by name only.
See mbse-basis [CAP-084: program trees as data](../../../../../mbse-basis/docs/capabilities/CAP-084.md)."""

from . import Definitions, Errors, Model

__all__ = ["Definitions", "Errors", "Model"]
