# Languages

Each language is a set of kinds covering the union of its recent standards, each kind and feature recording which
standards have it (`SINCE`, by family: a year for C, C++ and ECMAScript, `100 * major + minor` for Python and
TypeScript). Standards parse with tree-sitter and print one fixed layout. `LANGUAGE.grammar()` describes every kind,
category, property and availability as data: read it rather than guessing a property's name.

| Language | Kinds | Standards | Tree follows |
|---|---|---|---|
| Ccpp: C and C++ | 171, through C++26 and C23 | `Ccpp17`, `Ccpp20`, `CcppStandard(year, "C++" or "C")` | the C++ grammar: specifiers, declarators, statements |
| Python | 86, Python 3.0 to 3.15 | `Python312`, `Python314`, `PythonStandard(major, minor)` | Python's `ast`, names as `Identifier`s |
| TypeScript: TypeScript and JavaScript | 163, through TypeScript 5.9 and ES2025, with JSX | `TypeScript50`, `TypeScript59`, `ECMAScript2020`, `ECMAScript2025`, each with `.JSX`; `TypeScriptStandard(major, minor, jsx)`, `ECMAScriptStandard(year, jsx)` | typescript-estree (TSESTree) |

## Ccpp

```python fragment
from mbse.Programs.Ccpp import Ccpp17, Ccpp20, CcppStandard, Definitions, Syntax as S
unit = Ccpp20.parse("bool f(const R &r) { return r.x >= 2; }\n")       # S.TranslationUnit; unit.items
fn = unit.items[0]; fn.body.items[0]                                     # FunctionDefinition, CompoundStatement.items
CcppStandard(2011, "C").check(unit)    # ["...PrimitiveTypeSpecifier.keyword 'bool' needs C23", '...ReferenceDeclarator is not C']
Ccpp17.check(Ccpp20.parse("auto c = 1 <=> 2;\n"))  # ["...BinaryExpression.operator '<=>' needs C++20"]
Definitions.define(unit)               # namespaces, classes, functions (one per signature), fields, ... ; qualified with ::
```

- Every binary operator is a `BinaryExpression`; names are syntax nodes everywhere; specifiers stay in source order;
  declarators nest inside out; literals keep their spelling; comments and directives are kept where items are listed.
- Not parsed by tree-sitter-cpp 0.23.4 (built and printed, but `ParseError`): contracts, pack indexing, explicit object
  parameters, `if consteval`, attributes on lambdas, unnamed bit-fields, several using-declarators, `using typename`,
  `typeid(int)`, `a.operator int()`, `_BitInt`, Microsoft calling conventions. A constrained template parameter
  parses as a constant one.
- Definitions don't evaluate preprocessing conditions, choose among overloads, resolve members after `.` and `->`, or
  tell specializations from their primary template.

## Python

```python fragment
from mbse.Programs.Python import Python312, Python314, PythonStandard, Definitions, Syntax as P
module = Python314.parse(text)                 # P.Module; module.body
name.id.spelling; arg.arg.spelling; constant.spelling      # Identifier nodes; a literal as written ('0x_FF')
Definitions.define(module).lookup("x", at)     # Python's scopes: module, class, function, lambda, comprehension, type params
```

- Kinds are `ast`'s, capitalized where `ast`'s are lowercase (`Arg`, `Keyword`, `Alias`); kept beyond `ast`:
  `Parenthesized`, `ConcatenatedString`, `Comment`, f-string and t-string text. Not represented: `ctx`, type comments.
- Versions: `async` 3.5, f-strings 3.6, walrus 3.8, `match` 3.10, `except*` 3.11, type parameters 3.12 (defaults
  3.13), t-strings 3.14, lazy imports 3.15.
- tree-sitter-python 0.25.0 is corrected for nine precedence differences; still not parsed: `a[*(b)]`, a line indented
  less than the block it continues inside brackets, Python 2.
- Definitions: one entity per name per scope; lookup goes outward past class bodies; `global` and `nonlocal` honored;
  attributes, keyword arguments, imported members and builtins unresolved.

## TypeScript and JavaScript

```python fragment
from mbse.Programs.TypeScript import TypeScript59, ECMAScript2025, Definitions, Syntax as T
program = TypeScript59.parse(text)             # T.Program; program.body
ECMAScript2025.check(program)                  # ['body[0]: TSInterfaceDeclaration is not ECMAScript', ...]
Definitions.define(program).space_of(name)    # 'value', 'type' or 'namespace': a name's meaning where it is written
```

- Kinds are TSESTree's; renamed where a name is a keyword of Python or the framework's tag: `declarationKind`,
  `methodKind`, `isAsync`, `isAwait`, `isIn`, `isOut`. `Literal.raw` keeps the spelling; an array hole is an `Elision`.
- Type syntax, enums, namespaces, decorators, parameter properties, `accessor`, `using` and `import defer` are
  TypeScript's alone: an ECMAScript standard rejects them.
- Not parsed by tree-sitter-typescript 0.23.2: `x as T < y`, attributes on a re-export, a mapped type without a value
  type, ``f<T>`x` ``. Comments inside expressions and most types are dropped.
- Definitions keep values, types and namespaces apart, merge declarations as TypeScript does, and leave properties
  and imported members unresolved.

## Printing

Every printer writes one fixed layout (four spaces per level, the language's usual braces and blank lines) and adds
the parentheses precedence needs; parentheses written in the source are kept as syntax nodes. Printing validates the
tree and checks the standard first, raising `PrintError`. Printing then parsing gives the same tree for every tree that
parses.

## Go deeper

| Topic | Read |
|---|---|
| Every kind, standard, parsing gap and printing rule | [PROGRAMS.md](https://github.com/pitaman71/mbse-programs/blob/main/docs/PROGRAMS.md) |
| Standards, names and three languages, by example | [the tutorial](https://github.com/pitaman71/mbse-programs/blob/main/python3/tutorials/README.md), case studies 3 to 5 |
