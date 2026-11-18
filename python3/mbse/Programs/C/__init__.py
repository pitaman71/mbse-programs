"""C as a language of mbse-programs, C11 to C23 with the GNU extensions 0.3 kept: its statements, declarations and their
parts (`Statements`), as value objects refining `Programs.Framework.Statement`, whose expressions are mbse-expressions'
`C` terms, its type names' parts `C Types`' and its directives `C Preprocessor`'s; source read into a store (`Parse`)
and printed from it (`Print`).

`INSTALLS` lists, in the order they run, the installs a store needs to hold C programs, each in a transaction of its
own; `store()` gives a new store with each run."""

from typing import Any

from mbse.Expressions import Framework as Expressions
from mbse.Expressions.C.Expressions import Expressions as CExpressions
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.C.Types import Expressions as CTypes
from mbse.Schemas.Framework import Builders

from ..Framework import Model
from . import Parse, Print, Statements
from .Statements import install

INSTALLS = (Expressions.install, CExpressions.install, CTypes.install, CPreprocessor.install, Model.install,
            Statements.install)


def store() -> Any:
    """A new store holding every schema a C program needs: `INSTALLS`, each run in a transaction of its own."""
    made = Builders.Store()
    for each in INSTALLS:
        made.transaction(each)
    return made


__all__ = ["INSTALLS", "Parse", "Print", "Statements", "install", "store"]
