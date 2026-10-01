"""ES2020: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
`check` lists the constructs of a tree that ES2020 lacks. `JSX` is the same standard with JSX.

    from mbse.Programs.TypeScript import ECMAScript2020
    program = ECMAScript2020.parse("let n = 1;")
    text = ECMAScript2020.print(program)
"""

from ._Standard import ECMAScriptStandard

__all__ = ["STANDARD", "JSX", "parse", "print", "check"]

STANDARD = ECMAScriptStandard(2020)
JSX = ECMAScriptStandard(2020, jsx=True)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
