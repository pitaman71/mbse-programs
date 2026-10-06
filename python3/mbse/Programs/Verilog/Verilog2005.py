"""Verilog (IEEE 1364-2005): `parse` reads its source text into a Verilog tree, `print` writes a tree as its
source text, and `check` lists the constructs of a tree that it lacks.

    from mbse.Programs.Verilog import Verilog2005
    unit = Verilog2005.parse("module m; endmodule")
    text = Verilog2005.print(unit)
"""

from ._Standard import VerilogStandard

__all__ = ["STANDARD", "parse", "print", "check"]

STANDARD = VerilogStandard(2005, "Verilog")
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
