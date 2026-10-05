# Rewriting, transpiling and bridging

Everything here works on trees: nothing parses or prints a string between the source standard's `parse` and the
target standard's `print`.

## Rewriting within a language

```python fragment
for node in walk(tree): ...                       # find; assign properties to change in place
class Fix(Transformer):                           # visit_<Kind>(node) returns the replacement:
    def visit_Call(self, node):                   #   the node itself, another node, None to remove,
        self.generic_visit(node)                  #   or a list to splice into a list property
        return node
Fix().visit(tree)
parents = Parents(tree); parents.path(node); parents.replace(node, new); parents.remove(node)
copy(node)                                        # a syntax node has one parent: copy to use it twice
P.LANGUAGE.validate(tree)                         # [] when valid; problems by path otherwise
```

Rename by meaning: `Definitions.define(tree)`, then `referents(program, name)` for each name, as in
[the tutorial's case study 4](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/04_What_Names_Refer_To.ipynb).

## Transpiling TypeScript to Python

```python fragment
from mbse.Programs.Transpilers.TypeScriptToPython import transpile
Python314.print(transpile(TypeScript59.parse(text)))   # raises TranspileError(path) at what it doesn't cover
```

| TypeScript | Python |
|---|---|
| `for (let i = a; i < b; i++)` whose body doesn't assign `i` | `for i in range(a, b)`; any other `for` is a `while` |
| `do ... while`, `switch` without fall-through | `while True` with a `break`; `if`/`elif` on the subject |
| an assignment to an enclosing function's or the module's name | `nonlocal` or `global`, from `Definitions` |
| an expression-bodied arrow function | a `lambda`, or a comprehension for `map` and `filter` |
| class fields, parameter properties, getters, setters, static and abstract members | `__init__` assignments, `@property`, `@x.setter`, `@staticmethod`, `raise NotImplementedError` |
| enums of numbers or strings; object literals | `IntEnum` or `StrEnum`; `types.SimpleNamespace` |
| `a ?? b`, `===`, `console.log`, `Math`, `JSON`, `String(n)`, `x.length`, `push`, `includes` | `a if a is not None else b`, `==`, `print`, `math`, `json`, `str(n)`, `len(x)`, `append`, `in` |

Globals map only where `Definitions` finds no declaration, and methods only where no class or interface of the program
declares that member. Not emulated: `%` of negative numbers, truthiness of empty arrays and objects, `==` across types,
number printing (`6 / 2` prints `3.0`), integers beyond 2 ** 53. Labels, and anything else outside the subset, raise
`TranspileError` with the syntax node's path.

## Bridging rules and Python code

A bridge maps mbse-expressions' Python dialect to Python's trees and back. From a Basic rule, translate to the Python
dialect first (`mbse.Expressions.Translators.between(E.DIALECT, PythonDialect.DIALECT)`).

```python fragment
from mbse.Programs.Bridges import Python as Bridge
Bridge.expression(term)                       # a Python expression syntax node
Bridge.module(term)                           # the term's imports, then the expression
Bridge.function_("in_range", ["this"], term)  # def in_range(this): return ...
Bridge.term(expression_node)                  # Python syntax node -> dialect term; Bridge.term_of_module(module)
```

A chained comparison reads as `and` of comparisons sharing their middle operands, as the dialect's own `FromText`
reads it. What the dialect can't hold raises `TranspileError` at its path: `is`, `@`, keyword arguments, slices, other lambdas, generators of more than one `for`, `None`, `...`, imaginary numbers.
In TypeScript the bridge reads Python source into rules too, through the Python standards' parsers.

## Writing a transpiler

Build the target's tree with its `LANGUAGE.Builders`, never with helpers of your own; read the source with `walk`, a
`Visitor` or `Definitions`; locate errors with `Parents.path`; raise `TranspileError` rather than approximate. Its
programs belong in `conformance/transpilers/<transpiler>/`: the source, what it prints (`.out`), and its translation.

## Go deeper

| Topic | Read |
|---|---|
| Transpiling and bridges, in the design | [PROGRAMS.md, Transpiling](https://github.com/pitaman71/mbse-programs/blob/main/docs/PROGRAMS.md#transpiling) |
| Changing code, by example | [the tutorial's case study 2](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/02_Changing_Code_Safely.ipynb) |
| Transpiling and bridges, by example | [case study 7](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/07_From_One_Language_To_Another.ipynb) and [case study 8](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/08_From_Rules_To_Code.ipynb) |
