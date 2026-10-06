# Languages

Each language is a set of kinds covering the union of its recent standards, each kind and feature recording which
standards have it (`SINCE`, by family: a year for C, C++ and ECMAScript, `100 * major + minor` for Python and
TypeScript). Standards parse with tree-sitter, or for Verilog with slang, and print one fixed layout. `LANGUAGE.grammar()` describes every kind,
category, property and availability as data: read it rather than guessing a property's name.

| Language | Kinds | Standards | Tree follows |
|---|---|---|---|
| Ccpp: C and C++ | 171, through C++26 and C23 | `Ccpp17`, `Ccpp20`, `CcppStandard(year, "C++" or "C")` | the C++ grammar: specifiers, declarators, statements |
| Python | 86, Python 3.0 to 3.15 | `Python312`, `Python314`, `PythonStandard(major, minor)` | Python's `ast`, names as `Identifier`s |
| TypeScript: TypeScript and JavaScript | 163, through TypeScript 5.9 and ES2025, with JSX | `TypeScript50`, `TypeScript59`, `ECMAScript2020`, `ECMAScript2025`, each with `.JSX`; `TypeScriptStandard(major, minor, jsx)`, `ECMAScriptStandard(year, jsx)` | typescript-estree (TSESTree) |
| Verilog: Verilog and SystemVerilog | 280, SystemVerilog 2023's design subset and verification constructs | `Verilog2005`, `SystemVerilog2017`, `SystemVerilog2023`, `VerilogStandard(year, "SystemVerilog" or "Verilog")` | IEEE 1800's grammar: design units, items, statements, expressions |

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

## Verilog and SystemVerilog

```python fragment
from mbse.Programs.Verilog import SystemVerilog2023, Verilog2005, VerilogStandard, Definitions, Syntax as V
unit = SystemVerilog2023.parse(text, include_paths=["rtl/include"], defines=["SIM"])   # V.SourceText; unit.items
module = unit.items[0]; module.ports; module.items              # AnsiPort/InterfacePort/PortReference; items
Verilog2005.check(unit)                       # ['items[0]: PackageDeclaration is not Verilog', ...]
Definitions.define(unit).lookup("logger_pkg::FIELDS")           # packages qualify with ::, design units with .
```

- Read by slang 12.0.0 (`pyslang`), preprocessing included: `include_paths` and `defines` are slang's. TypeScript's
  `parse(text, includePaths, defines)` runs the Python implementation's reader, so it needs `python3/`'s environment
  (or `MBSE_PROGRAMS_PYTHON`); printing, checking and definitions don't.
- Kept as written: parentheses, literals' spelling, comments and directives where items and statements are listed,
  `` `ifdef `` as a tree whose untaken branches keep their text (`DisabledText`), with a macro's `name` or a 2023
  `condition` (`` `ifdef (A && !B) ``, no directive inside its branches), a macro use that is a whole expression
  (`MacroUsage`). An included file's items are not spliced in: the `IncludeDirective` stays.
- Classes: `ClassDeclaration` (`virtual`, `interface`, `final`, `parameters`, `base` and its `arguments` or
  `defaulted`, `interfaces`), properties as `VariableDeclaration`s with `visibility` and `random`, methods as
  `FunctionDeclaration`/`TaskDeclaration` with `extern`, `pure`, `virtual`, `visibility`, `static`, `specifier`
  (`:initial`, `:extends`) and `final` (a constructor is named `new`), `local typedef`, `EmptyItem` (`;`), `NewExpression`, `this`,
  `super`, `null`, and class scopes as `ScopedName`s whose scope may be a `ParameterizedName` (`c #(8)::x`).
- Randomization: `ConstraintDeclaration` and `ConstraintPrototype`, whose items are `Constraint`s (expression, `soft`,
  implication, `if`, `foreach`, `solve before`, `disable soft`, `unique`, blocks); `DistExpression`;
  `RandomizeWithExpression` (inline constraints, `local::x` as `LocalName`); `ArrayMethodWithExpression`
  (`q.find(x) with (x > 0)`); `RandCaseStatement`. `void'(f());` is an `ExpressionStatement` of a cast to `void`.
- Assertions: `Sequence` and `Property` are categories (a sequence is a property; an expression stands for either):
  `DelaySequence` (`a ##1 b ##[1:3] c`, flat), `RepetitionSequence` (`[*n]`, `[->n]`, `[=n]`; `[*]` is `[*0:$]`),
  `BinarySequence`, `ImplicationProperty`, `BinaryProperty`, `UnaryProperty` (`not`, `always [1:3]`, ...), and more;
  `PropertySpec` (clock, `disable iff`, property); `ConcurrentAssertion` and `ExpectStatement` are statements, and
  `AssertionItem` puts an assertion among items with its label; `LabeledStatement`; `PropertyDeclaration`,
  `SequenceDeclaration`, `LetDeclaration`; `ClockingDeclaration`; `CycleDelay` (`##2`).
- Coverage: `CovergroupDeclaration` (clocked, or `with function sample`), `CoverageOption`, `Coverpoint` and its
  `CoverageBins`, whose `initializer` is `BinsValues`, `BinsTransitions`, `BinsDefault` or `BinsExpression`;
  `CoverCross` and its `BinsSelection`s, whose select is a `BinsSelect` (`BinsOf`, `&&`/`||`, `!`, `with`).
- Attributes `(* ... *)`: `AttributedItem`, `AttributedStatement` and `AttributedPort` wrap what they annotate; an
  operator's or a call's are its `attributes`. Elsewhere (struct members, function ports, connections) they're refused.
- Expressions beyond Verilog's: `StreamingConcatenation` (`{<< byte {a with [0 +: 2]}}`, of `StreamItem`s),
  `MinTypMaxExpression`, `EmptyArgument` (`f(a, , b)`, `u i(a, , b)`), `RootExpression` (`$root`), `EmptyQueue`
  (`{}`), `UnitName` (`$unit::x`), `TypeReference` (`type(a)`); a repeated pattern is an `AssignmentPattern` with a
  `count`, a tolerance range a `ValueRange` with an `operator`, and `#(rise, fall, turnoff)` a `DelayControl` with a
  `fall` and a `turnoff`.
- Ports: non-ANSI `PortReference` (with a select: `w[1:0]`), `PortConcatenation`, `ExplicitPort` (`.p(x)`),
  `EmptyPort`; ANSI `ExplicitAnsiPort` (`input .p(x + 1)`). Modports: `ModportPort` (`explicit`: `input .a(b)`),
  `ModportSubroutine` (`import f`, or a prototype), `ModportClocking`.
- Testbench: `DpiImport` (a prototype, `context` or `pure`, a C name), `DpiExport`, `BindDirective` (`bind m: u1
  mon i (...)`); `extern` modules, interfaces and programs, defined with `.*` ports (`WildcardPort`).
- Procedures: `ForceStatement` (`force`, procedural `assign`), `ReleaseStatement` (`release`, `deassign`),
  `WaitForkStatement`, `WaitOrderStatement`, `EventTrigger`'s `timing` (`->> #1 e`), `RepeatEventControl` (`a <= repeat
  (2) @(e) b`); `ElaborationTask` (`$error(...)` among items).
- Declarations: a `NetDeclaration` has a `strength` (`DriveStrength`, or a trireg's `ChargeStrength`) and an
  `expansion` (`vectored`, `scalared`), and a `ContinuousAssign` a `strength`; `NetTypeDeclaration`, `NetAlias`,
  `DefParam`, `TimeUnitsDeclaration`; `EnumMember`'s `left` and `right` (`A[2]`, `A[1:3]`); `StructMember`'s `random`;
  `TfPort`'s `const` and `static`; `TypeParameterDeclaration`'s `restriction`.
- `randsequence`: `RandSequenceStatement`, `Production`, `ProductionRule` (`weight`, `code`, `rand_join`, `bias`), and
  the `ProductionItem` category: `ProductionCall`, `ProductionCode`, `ProductionIf`, `ProductionRepeat`, `ProductionCase`.
- Checkers: `CheckerDeclaration` (property ports, `rand` variables), instantiated as a module is, or in a procedure
  (`CheckerStatement`); `ExportDeclaration` (`export p::x;`, `export *::*;`); a user-defined net type's net is a
  `NetDeclaration` without a `net_type` (`nt #1 w;`).
- Tagged unions: `StructType`'s `qualifier` (`tagged`, `soft`), `TaggedExpression`; patterns (`Pattern`:
  `VariablePattern`, `WildcardPattern`, `TaggedPattern`, `StructurePattern`; an expression is a constant pattern),
  `MatchesExpression` and `PredicateExpression` (`&&&`) in conditions, `CaseStatement`'s `matches` with
  `PatternCaseItem`s; a pattern's variables are seen by its guard and body.
- Gates and primitives: `GateInstantiation` (a gate's `keyword`, or a `primitive`'s name for an unnamed instance;
  `DriveStrength` or `PullStrength`; `GateInstance`s), `UdpDeclaration` (`UdpPort`s, `UdpInitial`, `UdpEntry` rows kept
  as written: `inputs`, `current`, `output`).
- Specify blocks: `SpecifyBlock`, `SpecparamDeclaration` (`SpecparamAssignment`'s `limit` for `PATHPULSE$`),
  `PathDeclaration` (`condition` or `ifnone`, `edge`, `polarity`, `operator`, `data_polarity` and `data`), `TimingCheck`
  (`TimingCheckEvent` arguments), `PulseStyleDeclaration`.
- Also: `CovergroupDeclaration`'s `extends`, `BlockEventControl` (`@@(begin f)`), `MatchesBinsSelect`, `NewExpression`'s
  `defaulted` (`super.new(default)`), `InterfacePortDeclaration` (`bus_if.mp a;`; without a modport, a variable),
  attributes on structure members, function ports (`attributes`), connections (`AttributedConnection`) and coverage and
  clocking items (`AttributedItem`); a sequence as a property's or a sequence's argument (`p(a ##1 b)`).
- Configurations: `ConfigDeclaration` (localparams, `design` cells, rules), `ConfigCell`, `ConfigRule` (`default`,
  `instance` and its `path`, `cell`), `ConfigLiblist`, `ConfigUse` (`cell`, `parameters`, `config`).
- Refused, by slang's kind name at its line and column (`unsupported syntax: ExternUdpDecl`): attributes on modport
  ports, `extern` primitives, a primitive's `.*` ports, and a macro used where a whole expression isn't.
- Definitions: packages, design units, classes, functions and tasks, and blocks as scopes; a class's lookup goes on to
  its base; a method or constraint defined outside its class (`c::f`) is its prototype's entity; an array method's
  iterator (`item`, or its argument's name) is a variable of its `with`; `import p::x` aliases, `import
  p::*` is found where nothing nearer is; `$unit::x` in the compilation unit; `.*` takes an `extern` unit's ports; `bind`'s connections are found in its
  target; `A[1:3]` declares `A1` to `A3`; members after `.` and instances'
  contents unresolved.

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
