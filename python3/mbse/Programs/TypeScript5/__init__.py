"""TypeScript 5 as a language of mbse-programs: its statements, declarations and their parts (`Statements`), as value
objects refining `Programs.Framework.Statement`, whose expressions are mbse-expressions' `TypeScript5` terms; source
read into a store (`Parse`).

`INSTALLS` lists, in the order they run, the installs a store needs to hold TypeScript 5 programs, each in a
transaction of its own; `store()` gives a new store with each run."""

from typing import Any

from mbse.Expressions import Framework as Expressions
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404
from mbse.Expressions.TypeScript import Patterns as TypeScriptPatterns
from mbse.Expressions.TypeScript import RegExp as TypeScriptRegExp
from mbse.Expressions.TypeScript import TypeScript5 as TypeScriptExpressions
from mbse.Expressions.TypeScript import Types as TypeScriptTypes
from mbse.Schemas.Framework import Builders

from ..Framework import Model
from . import Parse, Statements
from .Statements import install

INSTALLS = (Expressions.install, ISOIEC11404.install, IEEE754.install, TypeScriptExpressions.install,
            TypeScriptTypes.install, TypeScriptPatterns.install, TypeScriptRegExp.install, Model.install,
            Statements.install)


def store() -> Any:
    """A new store holding every schema a TypeScript 5 program needs: `INSTALLS`, each run in a transaction of its own."""
    made = Builders.Store()
    for each in INSTALLS:
        made.transaction(each)
    return made


__all__ = ["INSTALLS", "Parse", "Statements", "install", "store"]
