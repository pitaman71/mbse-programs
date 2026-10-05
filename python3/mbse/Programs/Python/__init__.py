"""Python as a tree language: the abstract syntax (`Syntax`), the names a module binds (`Definitions`), and the
versions that parse and print source text (`Python312`, `Python314`, and `PythonStandard(major, minor)` for any
other)."""

from . import Definitions, Python312, Python314, Syntax
from ._Standard import PythonStandard

__all__ = ["Syntax", "Definitions", "Python312", "Python314", "PythonStandard"]
