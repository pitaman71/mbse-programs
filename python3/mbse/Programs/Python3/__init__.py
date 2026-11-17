"""Python 3 as a language of mbse-programs: its statement kinds (`Statements`), refining `Programs.Framework.Statement`,
whose expressions are mbse-expressions' `Python3` terms; source read into a store (`Parse`), printed from it
(`Print`), and the names it defines resolved (`Definitions`).

`INSTALLS` lists, in the order they run, the installs a store needs to hold Python 3 programs, each in a transaction
of its own; `store()` gives a new store with each run."""

from typing import Any

from mbse.Expressions import Framework as Expressions
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404
from mbse.Expressions.Python import Patterns as PythonPatterns
from mbse.Expressions.Python import Python3 as PythonExpressions
from mbse.Expressions.Python import Types as PythonTypes
from mbse.Schemas.Framework import Builders

from ..Framework import Model
from . import Definitions, Parse, Print, Statements
from .Statements import install

INSTALLS = (Expressions.install, ISOIEC11404.install, IEEE754.install, PythonExpressions.install, PythonTypes.install,
            PythonPatterns.install, Model.install, Statements.install)


def store() -> Any:
    """A new store holding every schema a Python 3 program needs: `INSTALLS`, each run in a transaction of its own."""
    made = Builders.Store()
    for each in INSTALLS:
        made.transaction(each)
    return made


__all__ = ["INSTALLS", "Definitions", "Parse", "Print", "Statements", "install", "store"]
