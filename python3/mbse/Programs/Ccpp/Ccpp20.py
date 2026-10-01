"""C++20 (ISO/IEC 14882:2020): `parse` reads its source text into a Ccpp tree, `print` writes a tree as its source
text, and `check` lists the constructs of a tree that C++20 lacks.

    from mbse.Programs.Ccpp import Ccpp20
    unit = Ccpp20.parse("int main() { return 0; }")
    text = Ccpp20.print(unit)
"""

from ._Standard import CcppStandard

__all__ = ["STANDARD", "parse", "print", "check"]

STANDARD = CcppStandard(2020)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
