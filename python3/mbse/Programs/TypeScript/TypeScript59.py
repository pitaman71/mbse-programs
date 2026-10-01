"""TypeScript 5.9: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
`check` lists the constructs of a tree that TypeScript 5.9 lacks. `JSX` is the same standard with JSX.

    from mbse.Programs.TypeScript import TypeScript59
    program = TypeScript59.parse("let n: number = 1;")
    text = TypeScript59.print(program)
"""

from ._Standard import TypeScriptStandard

__all__ = ["STANDARD", "JSX", "parse", "print", "check"]

STANDARD = TypeScriptStandard(5, 9)
JSX = TypeScriptStandard(5, 9, jsx=True)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
