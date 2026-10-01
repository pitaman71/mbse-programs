"""C++17 (ISO/IEC 14882:2017): `parse` reads its source text into a Ccpp tree, `print` writes a tree as its source
text, and `check` lists the constructs of a tree that C++17 lacks.

    from mbse.Programs.Ccpp import Ccpp17
    unit = Ccpp17.parse("int main() { return 0; }")
    text = Ccpp17.print(unit)
"""

from ._Standard import CcppStandard

__all__ = ["STANDARD", "parse", "print", "check"]

STANDARD = CcppStandard(2017)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
