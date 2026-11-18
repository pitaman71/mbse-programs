"""Transpilers: translations between languages' trees, which never parse or print text (`TypeScriptToPython`).

A translation reads a program of one language from a store and gives the transaction that writes its translation into
the same store, which holds both languages' schemas. `INSTALLS` lists, in the order they run, the installs such a store
needs, each in a transaction of its own: TypeScript 5's, then Python 3's that TypeScript 5's do not run already (the
framework's and mbse-expressions' own, which both share); `store()` gives a new store with each run *(agent)*."""

from typing import Any

from mbse.Schemas.Framework import Builders

from .. import Python3, TypeScript5
from . import TypeScriptToPython

INSTALLS = (*TypeScript5.INSTALLS, *(each for each in Python3.INSTALLS if each not in TypeScript5.INSTALLS))


def store() -> Any:
    """A new store holding every schema TypeScript 5 and Python 3 programs need: `INSTALLS`, each run in a transaction
    of its own."""
    made = Builders.Store()
    for each in INSTALLS:
        made.transaction(each)
    return made


__all__ = ["INSTALLS", "TypeScriptToPython", "store"]
