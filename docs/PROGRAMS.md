<!-- nav -->
[← 8 · From rules to code (TypeScript)](../typescript5/tutorials/08_From_Rules_To_Code.ipynb) · [Home](../README.md) · [Equivalence of the implementations →](EQUIVALENCE.md)

# Programs

mbse-programs represents programs as complete abstract syntax trees: plain in-memory objects that a transpiler builds,
reads and rewrites directly, never through source text. Each language is a set of syntax node kinds that covers the
union of its most recent standards, so that every construct any of them has is a tree, and each kind and feature records
which standards have it. Standards (C++20, Python 3.14, ...) are the only place where text is involved: they parse
source text into trees, delegating to an established parser, and print trees back into source text.

The trees are mbse-schemas data: every kind has a meta-schema and a fluent builder, so trees are built, stored, sent
and read back as JSON or YAML, byte-identical between the Python and TypeScript implementations.

## Layers

| Module | Organized | Holds |
|---|---|---|
| `Framework.Syntax` | by protocol | `SyntaxNode`, kinds and their properties, `Language` (kinds, categories, validation, grammar), `Standard`, builders and meta-schemas, and the traversals every language shares: `children`, `walk`, `fold`, `same`, `copy`, `Parents`, `Visitor`, `Transformer` |
| `Framework.Definitions` | by meaning | `Entity`, `Scope` and `Program`: what a program declares, and lookup |
| `Framework.Errors` | | `ParseError` (with line and column), `PrintError` and `TranspileError` (with the syntax node's path) |
| `<Language>.Syntax` | lexically, as the standard's grammar | the language's kinds and categories, with their availability |
| `<Language>.Definitions` | semantically, as the standard's scopes | `define(unit)`, which builds a `Program` from a tree, and `referents` |
| `<Language>.<Standard>` | | `STANDARD`, `parse`, `print` and `check` for one standard |
| `Transpilers.<Source>To<Target>` | | `transpile(tree)`, which maps one language's tree to another's |
| `Bridges.<Language>` | | a language's syntax nodes and the terms of an mbse-expressions dialect, both ways |

The languages so far:

| Language | Kinds | Standards | Parser |
|---|---|---|---|
| Ccpp: C and C++ as one tree language | 171, covering C++26 and C23 | `Ccpp17`, `Ccpp20`, and `CcppStandard(year, family)` for any year of C++ or C | tree-sitter-cpp 0.23.4 |
| Python | 86, covering Python 3.0 to 3.15 | `Python312`, `Python314`, and `PythonStandard(major, minor)` for any version | tree-sitter-python 0.25.0 |
| TypeScript: TypeScript and JavaScript as one tree language, with JSX | 163, covering TypeScript 5.9 and ES2025 | `TypeScript50`, `TypeScript59`, `ECMAScript2020`, `ECMAScript2025`, each with a `JSX` variant, and `TypeScriptStandard(major, minor, jsx)` and `ECMAScriptStandard(year, jsx)` for any version or edition | tree-sitter-typescript 0.23.2 |

## Trees

- **Kinds.** A kind is a class. Its properties are declared once: in Python as typed annotations, in TypeScript as a
  `SPEC` of property constructors (`text()`, `choice(...)`, `one(() => [...])`, `many(...)`, ...). A property holding a
  native (`str`, `bool`, `int`, or a choice among strings) is an *attribute*; a property holding a syntax node, an
  optional syntax node or a list of syntax nodes is a *child*. Every child property names the categories (or kinds) it
  accepts.
- **Categories.** Each kind belongs to one category, an abstract kind such as `Expression`, `Statement` or
  `Declaration`, by subclassing it. Ccpp has 171 kinds in 17 categories.
- **Syntax nodes are plain and mutable.** They are constructed from their properties (`S.IntegerLiteral(spelling="1")`,
  `new S.IntegerLiteral({ spelling: "1" })`), unset properties take their empty value (None/`null`, `False`, `[]`), and they
  are compared by identity; `same` compares trees by structure.
- **Trees.** A syntax node has at most one parent. `Language.validate` reports what is wrong with a tree, by path:
  required properties that are unset, children of a category the property does not accept, attributes of the wrong type,
  choices out of range, a syntax node shared by two parents, cycles, and each kind's own checks (an `Identifier`'s
  spelling).
- **Serialization.** Each kind has a meta-schema: an mbse-schemas reference-object schema tagged `kind`, with one
  property per attribute. Children are entries of the adjacency `children` to the shared relation `Programs.Children`,
  which links a `parent` to a `child` with the child's `property` and, in a list, its `index`. `Language.grammar()` writes
  every kind, its category, properties and availability as data.

## Standards

Each kind records where it exists, as `SINCE`: by family (`C++`, `C`, `Python`, `ECMAScript`, `TypeScript`), the
version of the first standard that has it, or a range for a kind a later standard removed. A version is a number that
orders a family's standards: the year for C, C++ and ECMAScript, `100 * major + minor` for Python and TypeScript (3.12
is 312, 5.9 is 509), and a standard's `label(version)` names it ("C++20", "Python 3.12", "ES2025", "TypeScript 5.9").
Kinds without `SINCE` exist since the language's base (C++98, C89, Python 3.0, ES2015 and TypeScript 1.0), and kinds
marked `EXTENSION` are outside every family: GNU and Microsoft extensions that real code depends on, which every
standard accepts, and JSX, which the TypeScript language's standards accept when made with `jsx`.
Features that depend on a property's value (`<=>` in a `BinaryExpression`, several indices in a `SubscriptExpression`)
are recorded as `FEATURES`, or by a kind's own `features()` where they depend on several properties.

A `Standard` checks a tree against its availability (`check(node)` lists every problem, by path, such as
`"items[2].condition: BinaryExpression.operator '<=>' needs C++20"`), parses source text into a tree, raising
`ParseError` at the first syntax error or at the first construct the standard lacks, and prints a tree, raising
`PrintError` if the tree is invalid or uses a construct the standard lacks.

## Ccpp: C and C++

The kinds cover C++26 and C23, organized as the standard's grammar is: names, expressions, literals, lambda captures,
requirements, designators, statements, declarations, specifiers, declarators, parameters, initializers, exception
and contract specifiers, attributes, template parameters, and preprocessing directives. The tree is abstract where
the grammar only spells, and concrete where a transpiler needs to see what was written:

- Every binary operator is a `BinaryExpression`; parentheses written in the source are kept as
  `ParenthesizedExpression`, and printing adds those a hand-built tree needs.
- Names are syntax nodes wherever they occur, so one traversal finds every use and declaration of a name.
- Specifiers stay in source order, one syntax node per keyword. Declarators nest inside out, as the grammar defines
  them.
- Literals keep their spelling: digits, separators and suffixes, and the characters between the quotes, escapes
  included.
- Comments and preprocessing directives are kept where declarations, statements, members and enumerators are listed,
  with conditional branches (`#if`, `#ifdef`, ...) as trees; elsewhere comments are dropped.
- Property names avoid both languages' reserved words: an `IfStatement` has a `consequence` and an `alternative`.

### Parsing

The standards parse with [tree-sitter-cpp](https://github.com/tree-sitter/tree-sitter-cpp) 0.23.4 (through
`tree-sitter` in Python and `web-tree-sitter` in TypeScript), and convert its concrete syntax tree into Ccpp kinds. A
token-level pre-pass handles what tree-sitter-cpp cannot: module and import declarations, `export` and `extern
template` are blanked out of the text before parsing, every other character kept in place, and put back into the tree
after. Line and column are counted in characters (code points), never bytes or UTF-16 units, so both implementations
report the same position.

Parsing normalizes what has several spellings, so that printing writes one of them:

- Alternative tokens and digraphs (`and`, `bitor`, `<%`) become the primary tokens; `defined X` becomes `defined(X)`.
  Keywords with distinct spellings (`_Alignof`, `alignof`) keep them.
- A base specifier's `virtual` is printed before its access specifier.
- An empty requirement parameter list is kept (`requires () { ... }`).
- A comment between a case label and its statement is listed after the statement.
- Layout and blank lines are the printer's own.

tree-sitter-cpp 0.23 does not parse the following, although Ccpp has kinds for them, so that they can be built and
printed but not parsed. Each raises `ParseError` at a syntax error, or names the unsupported tree-sitter node:

| Construct | Example | Standard |
|---|---|---|
| Contracts | `int f(int x) pre(x > 0);` | C++26 |
| Pack indexing | `T...[0]` | C++26 |
| Explicit object parameters | `void f(this S &self);` | C++23 |
| `if consteval` | `if consteval { }` | C++23 |
| Attributes on lambdas | `[] [[nodiscard]] () { ... }` | C++23 |
| A label at the end of a block | `{ l: }` | C++23, C23 |
| Default member initializers of bit-fields | `int b : 3 = 1;` | C++20 |
| Unnamed bit-fields | `int : 3;` | all |
| Several using-declarators | `using A::a, B::b;` | C++17 |
| `using typename` | `using typename T::type;` | C++11 |
| `typeid` of a type | `typeid(int)` | all |
| Conversion function names in expressions | `a.operator int()` | all |
| A parenthesized type in `new` | `new (int)` | all |
| `alignas` after a declarator | `int y alignas(8);` | C++11 |
| The null directive | `#` | all |
| `_Thread_local`, `_BitInt` | `_BitInt(8) x;` | C11, C23 |
| Microsoft calling conventions and pointer modifiers, structured exception handling | `void __stdcall f();`, `__try` | extensions |

A constrained template parameter (`template <C T>`) parses as a constant template parameter of type `C`: without
knowing that `C` is a concept, tree-sitter-cpp cannot tell them apart.

### Printing

The printer writes one fixed layout: four spaces per level, braces on the line that opens them, one declaration or
statement per line, case labels one level inside their switch, and labels, access specifiers and directives outdented.
Parentheses are added by precedence for expressions, and by binding for declarators (`(*f)(int)`). A comment that
follows code on its line is a `Comment` with `trailing` set. Printing then parsing gives the same tree for every
tree that parses (PRS-01, CONF-03).

### Definitions

`Ccpp.Definitions.define(unit)` reads a translation unit into a `Program` of entities and scopes:

- Entity kinds: namespace, namespace alias, class (also structs and unions), enumeration, enumerator, function (one per
  signature), variable, field (a data member), parameter, template parameter, type alias, concept, label and macro.
- Scope kinds: namespace (also the global scope), class, enumeration, function, block, template, lambda and requires.
- Each entity records its declarations and its definition. Reopened namespaces are one entity; out-of-line
  definitions (`int A::f() { ... }`, `int S::count = 0;`) join the member they define, by name and signature.
- Inline and unnamed namespaces, unscoped enumerations and anonymous unions are transparent to their enclosing scope,
  using-directives and `using enum` are followed, and a class looks names up in its bases.
- `Program.lookup(name, at)` resolves a qualified or unqualified name from a syntax node, and `referents(program, name)`
  the entities a name in the tree refers to.

It does not evaluate preprocessing conditions (every branch's declarations are declared), choose among overloads,
resolve names that depend on types (members after `.` and `->` are left unresolved), tell specializations from their
primary template, or declare what a friend declaration declares.

## Python

The kinds follow Python's own abstract syntax, the `ast` module, through Python 3.15: the same kinds and property names,
capitalized where `ast`'s are lowercase (`Arg`, `Keyword`, `Alias`, `WithItem`, `MatchCase`, `Comprehension`), with
properties in source order. A Python programmer who knows `ast` knows the tree; where it departs from `ast`, it is to
keep what `ast` drops:

- Names are `Identifier` syntax nodes wherever `ast` has a string, and a module's dotted name is a `DottedName`.
- `Constant.spelling` is the literal as written (`0x_FF`, `rb'\d'`, a triple-quoted string). f-strings and t-strings
  keep their prefix and quotes, the text between replacement fields as written, and each field's own text (`{x = }`),
  which a self-documenting field writes into the string and a t-string records as the expression.
- `Parenthesized` keeps parentheses written in the source, and `ConcatenatedString` adjacent string literals.
- `Comment` statements keep comments where statements are listed, `trailing` when they end a statement's or a clause
  header's line.
- Lists hold no empty places: a dict's `**mapping` is a `DictItem` without a key, a parameter's default is on its `Arg`
  (`default_value`), a comparison is a `Compare` of `Comparison`s, and `from m import *` imports an `Alias` without a
  name.
- Not represented: the expression context (`ctx`), which follows from where an expression is, `AnnAssign.simple`,
  type comments, and Python 2's syntax.

Kinds and features record the version that introduced them, from `async` (3.5) and f-strings (3.6) to the walrus (3.8),
`match` (3.10), `except*` (3.11), type parameters (3.12) and their defaults (3.13), t-strings and unparenthesized
`except` types (3.14), and lazy imports and unpacking comprehensions (3.15).

### Parsing Python

The versions parse with [tree-sitter-python](https://github.com/tree-sitter/tree-sitter-python) 0.25.0. Its grammar
differs from Python's in places, which the converter corrects:

| tree-sitter-python reads | as | Python reads it as |
|---|---|---|
| `a ^ b & c` | `(a ^ b) & c` | `a ^ (b & c)`: `&` binds tighter than `^` |
| `await x ** 2` | `await (x ** 2)` | `(await x) ** 2` |
| `x := a if b else c` | `(x := a) if b else c` | `x := (a if b else c)` |
| `A \| B \| C` in an annotation | `A \| (B \| C)` | `(A \| B) \| C` |
| `case C(k=p as n)` | `(k=p) as n` | `k=(p as n)` |
| `f'{x:=10}'` | an assignment expression | `x` formatted with the spec `=10` |
| `type(t).name = v` | a type alias named `(t).name` | an assignment |
| `print >> f, x` | Python 2's print statement | a tuple of `print >> f` and `x`, which is Python 3 too |
| `fr'\\'` | the backslashes as part of the closing quote | text |

It cannot parse three constructs of Python 3.13 and later. When the text does not parse, a pre-pass rewrites them,
keeping every other character in place: it moves `lazy` after the `import` or `from` it qualifies, removes the `**` of a
dict comprehension that unpacks (`{**d for d in ds}`), and removes type parameters' defaults, which are parsed on their
own; the converter puts them back. What it still cannot parse raises `ParseError`:

- `*(expression)` in a subscript (`a[*(b)]`);
- a line indented less than the block it continues, inside brackets;
- Python 2's statements (`print x`, `exec code`, `<>`) and tuple parameters.

Errors are located where tree-sitter-python's error recovery starts, which is often the beginning of the statement.

Parsing normalizes what the tree does not keep: layout and blank lines, `;`-separated statements, backslash
continuations, parentheses around `with` items and imported names, group patterns (`case (a)`), the parentheses a call
shares with its only argument, a generator (`f((x for x in y))`), and comments inside expressions. Keyword arguments
before `*args` print after them, as `ast` orders them, which is the order Python evaluates them in.

Checked against CPython 3.14: of the 1,865 files of its standard library that CPython parses, 1,863 parse, print, and
read back in CPython to the same `ast` (the other two hold the first two gaps above), and so do all 1,730 files of the
packages installed with this one; printing what was printed gives the same text; and the Python and TypeScript
implementations write byte-identical snapshots and printed text for every file.

### Printing Python

The printer writes four spaces per level, one statement per line, `elif` for an `orelse` that is one `If`, and, as
PEP 8 does, two blank lines around top-level definitions and one around nested ones, keeping comments that lead a
definition with it. Parentheses are added by the precedence of Python's grammar, which also decides where an assignment
expression, a `yield`, a lambda or a tuple must be parenthesized. A replacement field prints its `text` while that
still spells its value (comparing code, without comments or whitespace outside strings), and its value otherwise, so
that a transpiler that renames a variable inside an f-string sees the new name printed.

### Python definitions

`Python.Definitions.define(module)` follows Python's execution model: scopes are 'module', 'class', 'function',
'lambda', 'comprehension' and 'type parameters' (annotation scopes); a name bound anywhere in a scope is local to it
unless `global` or `nonlocal` says otherwise; lookup goes outward past class bodies. There is one entity per name per
scope, with every binding as a declaration, in source order. Qualified names join with `.` (`Shape.area`), through a
scope's `separator`. Attributes, keyword arguments, imported modules' members and builtins are not resolved.

## TypeScript and JavaScript

TypeScript and JavaScript are one tree language, as C and C++ are: JavaScript's standards are the editions of
ECMAScript, which have none of TypeScript's own syntax. The kinds follow
[typescript-estree](https://typescript-eslint.io/packages/typescript-estree/) (TSESTree), the ESTree of TypeScript that
ESLint and its tools read: the same kinds, property names and properties, in source order. A programmer who knows
TSESTree knows the tree; where it departs from TSESTree, it is to keep a name both implementations can use or what
TSESTree drops:

- Properties whose names are keywords of Python, or clash with the framework's tag `kind`, are renamed: `kind` is
  `declarationKind`, `methodKind`, `propertyKind` or `moduleKind`, and `async`, `await`, `in` and `out` are `isAsync`,
  `isAwait`, `isIn` and `isOut`.
- `Literal.raw` is the literal as written (`0x_FF`, `1_000n`, `/a/v`), and a template's parts are their raw text.
- `ParenthesizedExpression` and `TSParenthesizedType` keep parentheses written in the source.
- `Comment` keeps comments where statements, class members, interface members, enum members and a switch's cases are
  listed, and in object types; `Program.hashbang` keeps a first line `#!...`.
- An array's hole is an `Elision`, so that lists hold no empty places.
- Not represented: what follows from the rest (`directive`, `ArrowFunctionExpression.expression`, `sourceType`,
  `TSModuleDeclaration.global`), what TSESTree keeps only for compatibility (`assertions`, `TSEnumDeclaration.members`,
  `TSMappedType.typeParameter`, `TSImportType.argument`), and the modifier keywords (`TSAbstractKeyword`, ...).

Kinds and features record where they exist in both families: the ECMAScript edition and the TypeScript version that
introduced them, from `**` (ES2016, TypeScript 1.7) to optional chaining and `??` (ES2020, TypeScript 3.7), private
names (ES2022, TypeScript 3.8) and import attributes (ES2025, TypeScript 5.3). Type syntax, enums, namespaces,
decorators, parameter properties and the modifiers are TypeScript's alone, and so are the proposals TypeScript has ahead
of an ECMAScript edition: decorators, `accessor`, `using` and `import defer`. An ECMAScript standard rejects them all.

### Parsing TypeScript

The standards parse with [tree-sitter-typescript](https://github.com/tree-sitter/tree-sitter-typescript) 0.23.2: its
`typescript` grammar, or its `tsx` grammar for a standard with JSX. In the `tsx` grammar `<T>x` is not a type assertion,
and an arrow function's lone type parameter is written `<T,>`. The editions of ECMAScript parse with the same grammars,
so that JavaScript's `a < b > (c)` reads as TypeScript reads it, a call with a type argument, as typescript-estree does.
Its grammar differs from TypeScript's in places, which the converter corrects:

| tree-sitter-typescript reads | as | TypeScript reads it as |
|---|---|---|
| `a ?? b as T` (and `\|\|`, `&&`, `\|`, `^`, `&` and equality; and `satisfies`) | `(a ?? b) as T` | `a ?? (b as T)` |
| `a \|\| b && c as T < d` | `((a \|\| b && c) as T) < d` | `a \|\| (b && ((c as T) < d))` |
| `x as A.B.C`, `x as A \| B.C.D` | `(x as A.B).C`, a member of the cast | a cast to `A.B.C`, to `A \| B.C.D` |
| `a ?? b!` | `(a ?? b)!` | `a ?? (b!)` |
| `readonly A[] \| B` | `readonly (A[] \| B)` | `(readonly A[]) \| B` |
| `global { }` in a module | an error and a block | a global augmentation |
| `declare module "m";` | a module and an empty statement | a module |
| `m() {} // c` | the comment inside the method's body | a comment after the member |
| `bigint` as a type | a type's name | the keyword type |

It cannot parse a few constructs of TypeScript 4.7 and later. When the text does not parse, a pre-pass rewrites them,
keeping every character's offset: it removes `accessor` before a member, `in` and `out` before a type parameter,
`defer` in `import defer` and `type` in `export type *`; renames a member named `abstract` or `accessor` and the name
`using` (`using + 1`); writes `for (using x of y)` as `for (const x of y)`; and replaces `import("m")` in a type, which
it cannot qualify (`import("m").A<T>`), by a name as long, whose text is parsed again. The converter puts them back.
What it still cannot parse, or reads differently without a way to tell:

- an `as` or `satisfies` type followed by `<` (`x as T < y`), which reads as type arguments, and so is a syntax error;
- `export ... from "m" with { ... }`: attributes on a re-export;
- a mapped type without a value type (`{ [K in T] }`);
- `keyof readonly T[]` in a mapped type, and an anonymous `export default function (...)` signature without a body;
- `f<T>`x``, which it reads as comparisons, and `new a!.b()` and `new new a()()`, which it reads as `(new a)!.b()` and
  `new ((new a)())`: the printer parenthesizes such callees, so that its output reads the same everywhere.

Comments inside expressions, types other than object types, and before a switch's first case are dropped, as are
comments after a block's `}` that does not end its statement (`if (a) {} // c else {}`).

Checked against typescript-estree 8.71.0, the parser of typescript-eslint, on the 997 TypeScript files and 860
JavaScript files of the packages installed with this one and its neighbors: 983 TypeScript files read as
typescript-estree reads them (8 parse in neither, 6 hold the gaps above), and so do 846 JavaScript files (the other 14
hold JSX in `.js` files, which only a JSX standard reads); printing each of them gives text that typescript-estree reads
the same, with the source's parentheses or without them, printing what was printed gives the same text, and the Python
and TypeScript implementations write byte-identical snapshots, positions, printed text and definitions for every file.
The TypeScript suite checks the conformance sources against typescript-estree itself (TSPRS-01).

### Printing TypeScript

The printer writes four spaces per level, braces on the line that opens them, one statement or member per line, a
semicolon after every statement that takes one, and object literals, object types and imports on one line. Parentheses
are added by the precedence of the grammar, and also where `??` meets `||` or `&&`, where a statement would start
with `{`, `function`, `class` or `let [`, where an arrow function's body is an object, where an `in` would end a `for`
statement's initializer, and where `new`'s callee holds a call, a `new` or a non-null assertion. A tree that would give
an `else` to the wrong `if` (`if (a) if (b) x; else y;` without braces) is invalid.

### TypeScript definitions

`TypeScript.Definitions.define(program)` follows ECMAScript's and TypeScript's scopes: `var` binds in the nearest
function, static block, namespace or module, and everything else in its block; a class's and an interface's members are
in their scope, which lookup never finds unqualified; type parameters, mapped types' keys and `infer` bindings have
scopes of their own. Declarations of one name and kind in one scope merge into one entity, as TypeScript merges
interfaces, namespaces, enums and overloads. A name has a meaning, a value, a type or a namespace, by where it is
written: `space_of` tells which, and `referents` finds only the entities that have it, so that a variable and an
interface named alike stay apart. `import a = b.c` has the entity `b.c` names as its `target`. Properties, imported
modules' members and libraries' globals are not resolved.

## Transpiling

A transpiler reads a tree with `walk` or a `Visitor`, finds where a syntax node is with `Parents` (its parent, property,
index and path), and changes the tree in place: by assigning properties, with `Parents.replace` and `Parents.remove`, or
with a `Transformer`, whose `visit_<Kind>` methods return what replaces each syntax node. `copy` duplicates a subtree,
and `check` tells which standard the result needs. Nothing in this path parses or prints a string.

Trees are built with each language's fluent builders, `LANGUAGE.Builders.<Kind>()`, which have one setter per property
and finish with `create()` (or `clone()` and `update()` from an existing syntax node). A child's setter takes a syntax
node, a builder, or a function that makes one: the function is passed the builder of the property's kind where the
property holds one kind, and the language's `Builders` otherwise, so that it names the kind. A property of one kind
whose only property is an attribute also takes that attribute's value, so an `Identifier` child takes its spelling. A
list's setter takes a list, and `add_<property>` appends to it; a setter whose name the builder already has for a method
takes a trailing `_` (TypeScript's `ForStatement.update_`). In TypeScript the builders are typed from the language's
module, so a wrong property or a wrong kind of child does not compile:

```python
from mbse.Programs.Python import Syntax as P

Py = P.LANGUAGE.Builders
call = (Py.Call().func(lambda b: b.Attribute().value(lambda b: b.Name().id("math")).attr("floor"))
        .add_args(lambda b: b.Name().id("x")).create())   # math.floor(x)
```

A transpiler between two languages builds the target's tree from the source's, and raises `TranspileError` at the first
syntax node it cannot translate, with that syntax node's path. Its programs are in
`conformance/transpilers/<transpiler>/`: for each program, the source, what it prints when it runs (`.out`), and its
translation as both implementations write it.

### TypeScript to Python

`Transpilers.TypeScriptToPython.transpile(program)` translates a TypeScript `Program` into a Python `Module`, which
`Python314` prints. It covers a subset, which the module's documentation lists: the statements, functions, classes,
enums, imports and types that ordinary code is written with. The translation follows these patterns:

| TypeScript | Python |
|---|---|
| `for (let i = a; i < b; i++)`, where the body does not assign `i` | `for i in range(a, b)`; any other `for` is a `while` |
| `do body while (test)` | `while True:` with `if not test: break` after the body, which must not `continue` |
| `switch` without fall-through | `if` and `elif` on the subject, kept in a variable unless it is a name |
| a function that assigns a name of an enclosing function or of the module | `nonlocal` or `global`, from `Definitions` |
| an arrow function with an expression for its body | a `lambda`, or a comprehension for `map` and `filter` |
| a function with a body, used as a value | a function declared before the statement |
| a class's fields and parameter properties | assigned in `__init__`, after `super().__init__` |
| getters, setters, static and abstract methods, `toString` | `@property`, `@x.setter`, `@staticmethod`, `raise NotImplementedError`, `__str__` |
| an enum of numbers or of strings | an `IntEnum` or a `StrEnum` |
| an object literal | `types.SimpleNamespace` |
| `a ?? b` | `a if a is not None else b`, through `:=` where `a` is not a name |
| `console.log`, `Math`, `JSON`, `Object.keys`, `parseInt`, `new Error` and other globals | `print`, `math`, `json`, `vars`, `int`, `Exception` |
| `push`, `includes`, `join`, `slice`, `length` and other methods, by name | `append`, `in`, `str.join`, slices, `len` |

Globals are mapped only where `Definitions` finds no declaration of the name, and methods only where no class or
interface of the program declares a member of that name; a call to a mapped global or method with arguments the
mapping does not take fails. What the two languages do differently is not emulated: `%` of a negative number, the
truthiness of empty arrays and objects, `==` between values of different types, how numbers print (`6 / 2` prints `3.0`)
and integers beyond 2 ** 53 behave as Python's do. The programs in `conformance/transpilers/typescript-to-python` print
the same in Node and, translated, in CPython.

### What transpiling showed about the framework

The first transpiler was written to test the framework, and found:

- **Definitions are enough for names.** Telling a global from a declared name, finding a `catch` parameter, and finding
  the names a function assigns in an enclosing scope all come from `define` and `referents`.
- **Paths locate errors.** `Parents.path` gives every error a place in the source tree, without positions.
- **A syntax node has one place.** A tree that holds one syntax node twice is invalid, so a translation that repeats a
  value (the subject of a `switch`, an imported module's name) copies it with `copy`.
- **Related kinds have different properties.** An arrow function has no `generator`, so code that reads functions of
  every kind checks which properties a syntax node has.
- **Building trees needs fluent builders.** A name, a call or an attribute is a syntax node and an `Identifier` within
  it; built with constructors, the first version needed a dozen helpers of its own. It now builds every syntax node with
  the language's fluent builders, which also check, in TypeScript, that each child is of a kind its property holds.
- **Without types, methods map by name.** `x.length` is `len(x)` whatever `x` is; only a member the program declares
  stops the mapping.

## Bridges

A bridge carries expressions between one of mbse-expressions' dialects and a language's syntax trees, both ways, tree
to tree, so that a rule stored as data becomes code, and code becomes a rule that can be stored, evaluated and
translated to the other dialects. mbse-expressions is a sibling of this repository, as mbse-schemas is.

### Python

`Bridges.Python` maps the Python dialect's terms to Python syntax nodes and back:

| Python dialect | Python syntax nodes |
|---|---|
| `constant` | the literal `repr` writes; a negative number is a negation, and a float that is not finite `float('nan')` or `float('inf')` |
| `name`, `attribute`, `call`, `ifexp` | `Name`, `Attribute`, `Call`, `IfExp` |
| `subscript` (a `str` key) and `index` | `Subscript`, whose slice is the key's literal or the index |
| `compare`, `binop`, `unaryop` | `Compare` of one comparison, `BinOp`, `UnaryOp` |
| `boolop` | `BoolOp`, whose operands nested to the left are one list: `a and b and c` |
| `generator` | `GeneratorExp` of one `for`, over a name |
| `let` | `(lambda name: body)(value)` |
| `import`, `importfrom` | `Import` and `ImportFrom` statements, before the expression |

- `expression(term)` gives the expression, `module(term)` the module of its imports and then the expression, and
  `function_(name, parameters, term)` the function that returns it, its imports first. Every term has a counterpart,
  and the printed Python is the dialect's own `render`, but for the parentheses the printer chooses.
- `term(expression)` and `term_of_module(module)` read the other way, as the dialect's `parse` reads source: written
  parentheses are dropped, comments skipped, `and` and `or` of more than two operands nest to the left, and a chained
  comparison is `and` of comparisons sharing their middle operands (`a < b < c` is `a < b and b < c`). Literals
  are decoded as Python decodes them (`decode`): ints, floats, strings and bytes with their prefixes, escapes and
  adjacent literals. What the dialect cannot hold raises `TranspileError` at its path: an
  operator outside the dialect's vocabulary (`is`, `@`), a keyword argument, a slice, any other lambda, a
  generator of more than one `for`, `None`, `...`, an imaginary number, a `\N{...}` escape, and any other kind.
- With the Python standards' parsers, this reads Python source into the dialect in TypeScript too, where the dialect
  alone cannot, since its `parse` uses Python's own.

```python
from mbse.Expressions.Dialects.Python import Evaluators
from mbse.Programs.Bridges import Python as B
from mbse.Programs.Python import Python314

rule = B.term_of_module(Python314.parse("age >= 18 and len(email) > 0"))   # source into a rule
Evaluators.OfAny(rule, {"age": 20, "email": "a@b"})                         # True, by the dialect
Python314.print(B.function_("is_contactable", ["age", "email"], rule))
# 'def is_contactable(age, email):\n    return age >= 18 and len(email) > 0'
```

## Open questions

- **Value objects in lists.** Children are linked through the relation `Programs.Children` rather than as nested value
  objects in an indexed list, which mbse-schemas now has (`as_indexed`). Linking keeps parity with mbse-expressions'
  arguments, and gives every syntax node an identity; nesting would make snapshots smaller and their order explicit.
- **A parser that covers C++23 and C++26.** tree-sitter-cpp 0.23 lacks the constructs listed above. A later release,
  or a second parser (Clang through libclang), would close the gap; the converter is the only part that would change.
- **Comments everywhere.** Comments inside expressions and declarators are dropped. Keeping them needs a place on every
  kind, which would weigh on every transpiler.
- **Preprocessing.** Directives are kept where items are listed, and macros are entities, but code is not expanded;
  directives elsewhere (inside an expression) are not parsed.
- **A parser that covers Python 3.13 and later.** tree-sitter-python 0.25 needs a pre-pass and nine corrections. CPython's
  own parser is exact but exists only in Python, and both implementations must read the same trees; a later
  tree-sitter-python, or a PEG grammar run in both, would close the gap.
- **Precise error positions.** tree-sitter reports where its error recovery starts, not where the text went wrong.
- **A parser that covers TypeScript 5.9.** tree-sitter-typescript 0.23 needs a pre-pass and corrections, and still
  lacks the constructs listed above. typescript-estree is exact but exists only in JavaScript; a later
  tree-sitter-typescript would close the gap, and the converter is the only part that would change.
- **Comments in types and expressions.** Comments are kept in object types, but dropped in other types and in
  expressions, as in the other languages.
- **More languages.** Verilog is planned as a further language over the same framework.
- **More bridges.** Ccpp, TypeScript and, once the language exists here, SystemVerilog have dialects in
  mbse-expressions; each would have a bridge as Python's does.
- **Types for transpilers.** Mapping methods by name is a guess where a type checker would know. Types could come from
  a checker run on the source, or from definitions that resolve members.

## Resolved

- Bridges between mbse-expressions' dialects and the languages live here, in `Bridges`, so that mbse-expressions
  depends only on mbse-schemas and keeps no parser. A bridge reads source as the dialect's own `parse` does, and
  writes what the dialect's `render` writes.
- The mbse repositories stay separate, beside each other as sibling checkouts. A dependent installs its siblings as
  they are (`../../mbse-schemas/python3`, `file:../../mbse-schemas/typescript5`), so a change in one is seen at once by
  the others, and pins the version and commit of each it was tested with in `siblings.json`: a sibling is compatible
  at the same minor version below 1.0 and no older, and `pyproject.toml` requires that range; the commit reproduces
  the checkout, since the lock files record siblings by path, without a hash, and a release is the tag `v<version>`.
  `scripts/siblings.py` checks the siblings, clones those missing at their pinned commits, and pins new ones; it runs
  the tool kept in mbse-schemas.
- The vocabulary is shared with mbse-schemas and mbse-expressions: a kind's named members are *properties* (attributes
  and children, declared in `PROPERTIES`), and a tree's elements are *syntax nodes* (`SyntaxNode`), never bare nodes.
  "Field" means only what the host language means by it: a class's field in TypeScript or C++, or an f-string's
  replacement field. Snapshots record which property a child fills as the entry's `property`.
- One repository, `mbse-programs`, holds the framework and every language, each language a package beside it
  (`mbse.Programs.Ccpp`, `@mbse/programs/Ccpp`).
- Kinds are mbse-schemas schemas: each has a registered meta-schema tagged `kind` and a builder, and children are
  entries of the relation `Programs.Children`.
- C and C++ are one language, Ccpp, whose kinds record their availability in each family; standards of either family
  check trees against it.
- Parsing delegates to tree-sitter-cpp 0.23.4, pinned in both implementations so that their trees are identical. Its
  gaps are closed by a pre-pass where the text allows it, and are listed above where it does not.
- Printing writes one fixed layout, not the source's own: trees do not record whitespace.
- Positions in errors are counted in code points.
- Definitions find entities by name: overloads are separate entities by signature, but are not chosen between.
- Python's kinds are `ast`'s, with the additions above; its versions are numbered `100 * major + minor`, and standards
  name versions through `label`.
- Python parses with tree-sitter-python 0.25.0, pinned in both implementations, whose grammar the converter corrects.
  CPython's `ast` is not used to parse, since TypeScript cannot run it; the Python suite checks the conformance source
  against it.
- web-tree-sitter is initialized once for every language: initializing it again breaks the parsers made before.
- tree-sitter reads UTF-16 in both implementations: Python passes it the text encoded as UTF-16LE, as web-tree-sitter
  does, since its error recovery depends on the encoding. Errors are then located alike in both.
- TypeScript and JavaScript are one language, whose kinds are TSESTree's with the renames and additions above, and
  whose standards are the versions of TypeScript and the editions of ECMAScript, each with JSX or without. Proposals
  TypeScript has before an ECMAScript edition does are TypeScript's.
- TypeScript parses with tree-sitter-typescript 0.23.2, pinned in both implementations, whose grammar the converter
  corrects. typescript-estree is not used to parse, since Python cannot run it; the TypeScript suite checks the
  conformance sources against it.
- TypeScript's definitions keep a name's meaning (value, type or namespace) where it is written, and look up only the
  entities with that meaning.
- Every kind's builder is fluent, in the style of mbse-schemas: one setter per property, taking a `Spec` (a syntax node,
  a builder, or a function that makes one), and `LANGUAGE.Builders.<Kind>()` beside the registered names. A function for
  a property of one kind gets that kind's builder; for a property of categories it gets the language's `Builders` and
  names the kind. Transpilers build with them, never with helpers of their own.
- Transpilers map trees to trees, in `Transpilers`, and raise `TranspileError`, a `ValueError` with the syntax node's
  path, at what they do not cover. They keep what code means where the languages agree, and do not emulate where they
  differ.
- A `break` or `continue` outside a loop, which the parser accepts, fails to transpile rather than translating into
  invalid Python.

---

<!-- nav -->
[← 8 · From rules to code (TypeScript)](../typescript5/tutorials/08_From_Rules_To_Code.ipynb) · [Home](../README.md) · [Equivalence of the implementations →](EQUIVALENCE.md)
