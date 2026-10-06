"""SystemVerilog (IEEE 1800-2023): `parse` reads its source text into a Verilog tree, `print` writes a tree as its
source text, and `check` lists the constructs of a tree that it lacks.

    from mbse.Programs.Verilog import SystemVerilog2023
    unit = SystemVerilog2023.parse("module m; endmodule")
    text = SystemVerilog2023.print(unit)
"""

from ._Standard import VerilogStandard

__all__ = ["STANDARD", "parse", "print", "check"]

STANDARD = VerilogStandard(2023)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
