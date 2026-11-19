"""C++ as a language of mbse-programs, C++17 to C++23 with the GNU extensions 0.3 kept: its statements, declarations,
class members and their parts (`Statements`), as value objects refining `Programs.Framework.Statement`, C's kinds
among them, whose expressions are mbse-expressions' `Cpp` terms, its type-ids `Cpp Types`' and its directives `C
Preprocessor`'s; source read into a store (`Parse`) and printed from it (`Print`).

`INSTALLS` lists, in the order they run, the installs a store needs to hold C++ programs, each in a transaction of its
own, C's among them, as C++ reuses C's kinds and a C++ program's store may hold its C files too *(agent)*; `store()`
gives a new store with each run."""

from typing import Any

from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions
from mbse.Expressions.Cpp.Types import Expressions as CppTypes
from mbse.Schemas.Framework import Builders

from .. import C
from . import Parse, Print, Statements
from .Statements import install

INSTALLS = (*C.INSTALLS, CppExpressions.install, CppTypes.install, Statements.install)


def store() -> Any:
    """A new store holding every schema a C++ program needs: `INSTALLS`, each run in a transaction of its own."""
    made = Builders.Store()
    for each in INSTALLS:
        made.transaction(each)
    return made


__all__ = ["INSTALLS", "Parse", "Print", "Statements", "install", "store"]
