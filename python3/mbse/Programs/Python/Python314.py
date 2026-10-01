"""Python 3.14: `parse` reads its source text into a Python tree, `print` writes a tree as its source text, and
`check` lists the constructs of a tree that Python 3.14 lacks.

    from mbse.Programs.Python import Python314
    module = Python314.parse("print('hello')")
    text = Python314.print(module)
"""

from ._Standard import PythonStandard

__all__ = ["STANDARD", "parse", "print", "check"]

STANDARD = PythonStandard(3, 14)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
