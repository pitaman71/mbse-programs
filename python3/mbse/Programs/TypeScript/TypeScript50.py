"""TypeScript 5.0: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
`check` lists the constructs of a tree that TypeScript 5.0 lacks. `JSX` is the same standard with JSX.

    from mbse.Programs.TypeScript import TypeScript50
    program = TypeScript50.parse("let n: number = 1;")
    text = TypeScript50.print(program)
"""

from ._Standard import TypeScriptStandard

__all__ = ["STANDARD", "JSX", "parse", "print", "check"]

STANDARD = TypeScriptStandard(5, 0)
JSX = TypeScriptStandard(5, 0, jsx=True)
parse = STANDARD.parse
print = STANDARD.print
check = STANDARD.check
