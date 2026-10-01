"""ES2025: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
`check` lists the constructs of a tree that ES2025 lacks. `JSX` is the same standard with JSX.

    from mbse.Programs.TypeScript import ECMAScript2025
    program = ECMAScript2025.parse("let n = 1;")
    text = ECMAScript2025.print(program)
"""

from ._Standard import ECMAScriptStandard

__all__ = ["STANDARD", "JSX", "parse", "print", "check"]

STANDARD = ECMAScriptStandard(2025)
JSX = ECMAScriptStandard(2025, jsx=True)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
