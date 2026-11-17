"""Python 3 as a language of mbse-programs: its statement kinds (`Statements`), refining `Programs.Framework.Statement`,
whose expressions are mbse-expressions' `Python3` terms."""

from . import Statements
from .Statements import install

__all__ = ["Statements", "install"]
