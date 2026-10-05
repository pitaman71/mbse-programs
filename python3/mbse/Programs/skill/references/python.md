# mbse-programs in Python

Install `mbse-programs` (it brings mbse-schemas, mbse-expressions and the tree-sitter grammars), then import each
language from `mbse.Programs.<Language>` (`Ccpp`, `Python`, `TypeScript`): its `Syntax`, its `Definitions` and its
standards. The traversals are `mbse.Programs.Framework.Syntax`'s, the errors `mbse.Programs.Framework.Errors`, the
transpilers `mbse.Programs.Transpilers` and the bridges `mbse.Programs.Bridges`.

## A complete program

Parse, rename by meaning, rewrite by kind, build, check standards, snapshot, transpile and bridge.

```python
from mbse.Expressions import Expressions as E, Translators
from mbse.Expressions.Dialects.Python import Expressions as PythonDialect
from mbse.Programs.Bridges import Python as Bridge
from mbse.Programs.Framework import Errors
from mbse.Programs.Framework.Syntax import Parents, Transformer, copy, same, walk
from mbse.Programs.Python import Definitions, Python312, Python314, PythonStandard, Syntax as P
from mbse.Programs.Transpilers.TypeScriptToPython import transpile
from mbse.Programs.TypeScript import TypeScript59
from mbse.Schemas.Framework import JSON

Py = P.LANGUAGE.Builders  # a fluent builder per kind: one setter per property, then create()

# Parse source into a tree of the language's own abstract syntax (Python's follows `ast`), and print it back.
module = Python314.parse("def area(w, h):\n    x = w * h\n    return x\n\n\ndef perimeter(w, h):\n    x = 2 * (w + h)\n    return x\n")
assert Python314.print(module).startswith("def area(w, h):\n    x = w * h\n")

# Rename one variable by what names refer to, never by spelling: perimeter's x is another entity.
program = Definitions.define(module)
[x] = program.lookup("x", module.body[0].body[0])
for node in walk(module):
    if isinstance(node, P.Name) and x in Definitions.referents(program, node):
        node.id.spelling = "result"
assert "result = w * h" in Python314.print(module) and "x = 2 * (w + h)" in Python314.print(module)


# Rewrite by kind: a Transformer's visit_<Kind> returns what replaces each syntax node (a list splices statements).
class LogReturns(Transformer):
    def visit_Return(self, node):
        log = Py.Expr().value(lambda b: b.Call().func(lambda b: b.Name().id("log")).add_args(copy(node.value))).create()
        return [log, node]  # copy: a syntax node has one parent


LogReturns().visit(module)
assert P.LANGUAGE.validate(module) == [] and "log(result)" in Python314.print(module)
parents = Parents(module)
assert parents.path(module.body[0].body[1]) == "body[0].body[1]"

# Build a tree: the printer adds the parentheses precedence needs.
twice = Py.BinOp().left(Python314.parse("a + b\n").body[0].value).op("*").right(lambda b: b.Constant().spelling("2")).create()
assert Python314.print(twice).strip() == "(a + b) * 2"

# Standards check, parse and print only what their version has.
modern = Python314.parse('greeting = t"hello {name}"\n')
assert Python312.check(modern) == ["body[0].value: TemplateStr needs Python 3.14",
                                  "body[0].value.values[1]: Interpolation needs Python 3.14"]
try:
    Python312.parse('greeting = t"hello {name}"\n')
except Errors.ParseError as error:
    assert str(error).startswith("line 1, column 12")
assert PythonStandard(3, 15).check(modern) == []

# Trees are mbse-schemas data: a JSON snapshot, byte-identical in both implementations, reads back the same.
text = JSON.ToJSON(P.LANGUAGE.Builders).Reachable(P.Module.Schema, module)
assert same(JSON.FromJSON(P.LANGUAGE.Builders).Reachable(P.Module.Schema, text), module)

# Transpile TypeScript to Python, tree to tree.
ts = TypeScript59.parse("for (let i = 0; i < 3; i++) {\n    console.log(i * 2);\n}\n")
assert Python314.print(transpile(ts)) == "for i in range(0, 3):\n    print(i * 2)\n"

# Bridge a rule kept as data (mbse-expressions) into a Python function, and code back into a rule.
this = E.variable("this")
rule = E.literal(2.0).le(this.celsius).and_(this.celsius.le(8.0)).data
term = Translators.between(E.DIALECT, PythonDialect.DIALECT).forward(rule)
assert Python314.print(Bridge.function_("in_range", ["this"], term)).strip() == (
    "def in_range(this):\n    return 2.0 <= this.celsius and this.celsius <= 8.0")
back = Bridge.term(Python314.parse("this.hours <= 48\n").body[0].value)
assert Translators.between(PythonDialect.DIALECT, E.DIALECT).forward(back).name == "le"
```

## Cheat sheet

```python fragment
from mbse.Programs.Framework.Syntax import Parents, Transformer, Visitor, children, copy, fold, same, walk
from mbse.Programs.Ccpp import Ccpp17, Ccpp20, CcppStandard, Definitions as CD, Syntax as S
from mbse.Programs.Python import Python312, Python314, PythonStandard, Definitions as PD, Syntax as P
from mbse.Programs.TypeScript import TypeScript50, TypeScript59, ECMAScript2020, ECMAScript2025, TypeScriptStandard, ECMAScriptStandard

tree = Python314.parse(text); Python314.print(tree); Python314.check(tree)    # ParseError, PrintError; check -> [problems]
PythonStandard(3, 15); CcppStandard(2011, "C"); TypeScriptStandard(5, 9, jsx=True); ECMAScriptStandard(2025, jsx=False)
ECMAScript2025.JSX                                       # each TypeScript standard has a JSX variant
P.LANGUAGE.validate(tree)                                # problems by path; [] when valid
P.LANGUAGE.kinds(); P.LANGUAGE.grammar()                 # every kind, its category, properties and availability, as data

walk(tree); children(node)                               # every syntax node; (property, index, child) of one
Parents(tree).parent(n) / .path(n) / .replace(n, new) / .remove(n)
class Rename(Transformer):                               # visit_<Kind> returns a replacement, a list to splice, or None
    def visit_Name(self, node): ...
copy(node); same(a, b); fold(tree, lambda node, results: ...)

Py = P.LANGUAGE.Builders                                 # Py.Call().func(lambda b: b.Name().id("f")).add_args(...).create()
Py.FunctionDef().name("f").args(lambda a: a.add_args(lambda b: b.arg("x"))).add_body(...).create()

program = PD.define(module); program.entities(); program.lookup("x", at_node)
PD.referents(program, name_node); entity.kind, entity.qualified_name(), entity.declarations, entity.definition

from mbse.Programs.Transpilers.TypeScriptToPython import transpile          # TypeScript Program -> Python Module
from mbse.Programs.Bridges import Python as Bridge                          # Python-dialect terms <-> Python trees
Bridge.expression(term); Bridge.module(term); Bridge.function_("f", ["x"], term); Bridge.term(expr); Bridge.term_of_module(m)
JSON.ToJSON(P.LANGUAGE.Builders).Reachable(P.Module.Schema, tree)           # from mbse.Schemas.Framework import JSON
```

## Traps

- Syntax nodes compare by identity: use `same(a, b)` to compare trees.
- Python's names are `Identifier` nodes inside `Name` (`name.id.spelling`), and parameters inside `Arg` (`arg.arg`);
  TypeScript's `Identifier` has `name`, not `spelling`.
- Parentheses written in the source are kept (`Parenthesized`, `ParenthesizedExpression`); a hand-built tree gets the
  ones precedence needs when printed.
- `define` doesn't resolve attributes, keyword arguments, imported modules' members or builtins: they refer to nothing.
- A transpiled program keeps what code means where the languages agree; it does not emulate where they differ.
- The bridge holds only what mbse-expressions' Python dialect can: no `is`, no keyword arguments, no slices.

## Go deeper

| Topic | Read |
|---|---|
| Learning it by example: trees, rewriting, standards, names, languages, snapshots, transpiling, bridges | [the tutorial, eight case studies](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/README.md) |
| The design: trees, standards, each language, parsing gaps, printing, definitions, transpiling, bridges | [PROGRAMS.md](https://github.com/pitaman71/mbse-programs/blob/main/docs/PROGRAMS.md) |
| Every behavior, as test cases | [the test plan](https://github.com/pitaman71/mbse-programs/blob/main/python3/tests/TestPlan.md) |
