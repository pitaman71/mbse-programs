# Programs

mbse-programs represents programs as complete abstract syntax trees: plain in-memory objects that a transpiler builds,
reads and rewrites directly, never through source text. Each language is a set of node kinds that covers the union of
its most recent standards, so that every construct any of them has is a tree, and each kind and feature records which
standards have it. Standards (C++20, Python 3.14, ...) are the only place where text is involved: they parse source text
into trees, delegating to an established parser, and print trees back into source text.

The trees are mbse-schemas data: every kind has a meta-schema and a builder, so trees are stored, sent and read back
as JSON or YAML, byte-identical between the Python and TypeScript implementations.

## Layers

| Module | Organized | Holds |
|---|---|---|
| `Framework.Syntax` | by protocol | `Node`, kinds and their fields, `Language` (kinds, categories, validation, grammar), `Standard`, builders and meta-schemas, and the traversals every language shares: `children`, `walk`, `fold`, `same`, `copy`, `Parents`, `Visitor`, `Transformer` |
| `Framework.Definitions` | by meaning | `Entity`, `Scope` and `Program`: what a program declares, and lookup |
| `Framework.Errors` | | `ParseError` (with line and column) and `PrintError` |
| `<Language>.Syntax` | lexically, as the standard's grammar | the language's kinds and categories, with their availability |
| `<Language>.Definitions` | semantically, as the standard's scopes | `define(unit)`, which builds a `Program` from a tree, and `referents` |
| `<Language>.<Standard>` | | `STANDARD`, `parse`, `print` and `check` for one standard |

The languages so far:

| Language | Kinds | Standards | Parser |
|---|---|---|---|
| Ccpp: C and C++ as one tree language | 171, covering C++26 and C23 | `Ccpp17`, `Ccpp20`, and `CcppStandard(year, family)` for any year of C++ or C | tree-sitter-cpp 0.23.4 |
| Python | 86, covering Python 3.0 to 3.15 | `Python312`, `Python314`, and `PythonStandard(major, minor)` for any version | tree-sitter-python 0.25.0 |

## Trees

- **Kinds.** A kind is a class. Its fields are declared once: in Python as typed annotations, in TypeScript as a
  `SPEC` of field constructors (`text()`, `choice(...)`, `one(() => [...])`, `many(...)`, ...). A field holding a
  native (`str`, `bool`, `int`, or a choice among strings) is an *attribute*; a field holding a node, an optional
  node or a list of nodes is a *child*. Every child field names the categories (or kinds) it accepts.
- **Categories.** Each kind belongs to one category, an abstract kind such as `Expression`, `Statement` or
  `Declaration`, by subclassing it. Ccpp has 171 kinds in 17 categories.
- **Nodes are plain and mutable.** They are constructed from their fields (`S.IntegerLiteral(spelling="1")`, `new
  S.IntegerLiteral({ spelling: "1" })`), unset fields take their empty value (None/`null`, `False`, `[]`), and they are
  compared by identity; `same` compares trees by structure.
- **Trees.** A node has at most one parent. `Language.validate` reports what is wrong with a tree, by path: required
  fields that are unset, children of a category the field does not accept, attributes of the wrong type, choices out
  of range, a node shared by two parents, cycles, and each kind's own checks (an `Identifier`'s spelling).
- **Serialization.** Each kind has a meta-schema: an mbse-schemas reference-object schema tagged `kind`, with one
  property per attribute. Children are entries of the adjacency `children` to the shared relation `Programs.Children`,
  which links a `parent` to a `child` with the child's `field` and, in a list, its `index`. `Language.grammar()` writes
  every kind, its category, fields and availability as data.

## Standards

Each kind records where it exists, as `SINCE`: by family (`C++`, `C`, `Python`), the version of the first standard that
has it, or a range for a kind a later standard removed. A version is a number that orders a family's standards: the
year for C and C++, `100 * major + minor` for Python (3.12 is 312), and a standard's `label(version)` names it ("C++20",
"Python 3.12"). Kinds without `SINCE` exist since the language's base (C++98, C89, Python 3.0), and
kinds marked `EXTENSION` (GNU and Microsoft extensions that real code depends on) are accepted by every standard.
Features that depend on a field's value (`<=>` in a `BinaryExpression`, several indices in a `SubscriptExpression`)
are recorded as `FEATURES`, or by a kind's own `features()` where they depend on several fields.

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
- Names are nodes wherever they occur, so one traversal finds every use and declaration of a name.
- Specifiers stay in source order, one node per keyword. Declarators nest inside out, as the grammar defines them.
- Literals keep their spelling: digits, separators and suffixes, and the characters between the quotes, escapes
  included.
- Comments and preprocessing directives are kept where declarations, statements, members and enumerators are listed,
  with conditional branches (`#if`, `#ifdef`, ...) as trees; elsewhere comments are dropped.
- Field names avoid both languages' reserved words: an `IfStatement` has a `consequence` and an `alternative`.

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
  signature), variable, field, parameter, template parameter, type alias, concept, label and macro.
- Scope kinds: namespace (also the global scope), class, enumeration, function, block, template, lambda and requires.
- Each entity records its declarations and its definition. Reopened namespaces are one entity; out-of-line
  definitions (`int A::f() { ... }`, `int S::count = 0;`) join the member they define, by name and signature.
- Inline and unnamed namespaces, unscoped enumerations and anonymous unions are transparent to their enclosing scope,
  using-directives and `using enum` are followed, and a class looks names up in its bases.
- `Program.lookup(name, at)` resolves a qualified or unqualified name from a node, and `referents(program, name)` the
  entities a name in the tree refers to.

It does not evaluate preprocessing conditions (every branch's declarations are declared), choose among overloads,
resolve names that depend on types (members after `.` and `->` are left unresolved), tell specializations from their
primary template, or declare what a friend declaration declares.

## Python

The kinds follow Python's own abstract syntax, the `ast` module, through Python 3.15: the same kinds and field names,
capitalized where `ast`'s are lowercase (`Arg`, `Keyword`, `Alias`, `WithItem`, `MatchCase`, `Comprehension`), with
fields in source order. A Python programmer who knows `ast` knows the tree; where it departs from `ast`, it is to keep
what `ast` drops:

- Names are `Identifier` nodes wherever `ast` has a string, and a module's dotted name is a `DottedName`.
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

## Transpiling

A transpiler reads a tree with `walk` or a `Visitor`, finds where a node is with `Parents` (its parent, field, index
and path), and changes the tree in place: by assigning fields, with `Parents.replace` and `Parents.remove`, or with a
`Transformer`, whose `visit_<Kind>` methods return what replaces each node. `copy` duplicates a subtree, and `check`
tells which standard the result needs. Nothing in this path parses or prints a string.

## Open questions

- **Value objects in lists.** Children are linked through the relation `Programs.Children` rather than as nested value
  objects in an indexed list, which mbse-schemas now has (`as_indexed`). Linking keeps parity with mbse-expressions'
  arguments, and gives every node an identity; nesting would make snapshots smaller and their order explicit.
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
- **More languages.** Verilog and TypeScript are planned as further languages over the same framework.

## Resolved

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
