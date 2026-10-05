"""C and C++ as one tree language, Ccpp: the abstract syntax (`Syntax`), the entities a program declares
(`Definitions`), and the standards that parse and print source text (`Ccpp17`, `Ccpp20`, and `CcppStandard(year, family)` for any
other)."""

from . import Ccpp17, Ccpp20, Definitions, Syntax
from ._Standard import CcppStandard

__all__ = ["Syntax", "Definitions", "Ccpp17", "Ccpp20", "CcppStandard"]
