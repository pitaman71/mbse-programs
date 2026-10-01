"""C and C++ as one tree language, Ccpp: the abstract syntax (`Syntax`), the entities a program declares
(`Definitions`), and the standards that parse and print source text (`Ccpp17`, `Ccpp20`)."""

from . import Ccpp17, Ccpp20, Definitions, Syntax

__all__ = ["Syntax", "Definitions", "Ccpp17", "Ccpp20"]
