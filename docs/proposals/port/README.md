<!-- nav -->
[← FEA-008: expressive program models](../../../../mbse-basis/docs/features/FEA-008.md) · [Home](../../../README.md)

# Porting to the stabilized mbse-schemas and mbse-expressions (a proposal, for review)

mbse-programs no longer imports against its siblings as they stand. mbse-schemas' store overhaul is done, and its step 5
ports the dependents: "If we do not have a step 5 defined yet, it should be focused on porting all of the `mbse-*`
dependencies over to the stabilized `mbse-schemas`" (mbse-schemas, [Store overhaul](../../../../mbse-schemas/docs/proposals/store-overhaul/README.md),
Decided, 26). Step 5 names this repository: "mbse-programs' corpora become Reachable transactions", and orders the
work: "mbse-expressions first, which the others depend on; then mbse-patterns and mbse-programs; mbse-codegen-python
last". mbse-expressions is ported and released (0.7.0). This proposes how mbse-programs follows, onto mbse-schemas
0.26.5 and mbse-expressions 0.7.0, and asks what only the user can decide. No code is written until it is decided.

## Where it stands

mbse-programs 0.3.28 pins mbse-schemas 0.10.0 and mbse-expressions 0.5.4. Against today's siblings (mbse-schemas
0.26.5 at `bf7c675`, mbse-expressions 0.7.0 at `ce3a3cc`), checked in a throwaway environment:

- **Python fails at import, in every module**: `Framework/Syntax.py` imports `Visitors.Native`, which is gone. Past
  that, it fails at module scope building `Programs.Children` outside a store
  (`Schemas.OfRelation.Builder()...links("parent", "child")`: a `TypeError` from `_AdjacencyMember.__call__`).
- **TypeScript fails to type-check**: 38 errors, 35 in `Framework/Syntax.ts`, 2 in `Conformance/write.ts`, 1 in
  `Verilog/_Reader.ts`. The bridges type-check only because they read terms as `any`; they fail when run.

What it uses that is gone or changed, by module (Python / TypeScript):

| Module | Lines | What fails |
|---|---|---|
| `Framework.Syntax` | 1,074 / 1,276 | Schemas built outside a store, at import: one meta-schema per kind (701 kinds), `Programs.Children`, one union per language (3 sites / 3). `OfStore` subclasses `Stores.Catalog` and calls `register`, which is gone (2 / 2). The reverse protocol: `accept`, `identify`, `Visitable` (6 / 8), superseded by [PRI-004: one visitor protocol per kind](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-004). Its builders, entries and links implement the 0.10 visitor types, `Visitors.OfNative`, `OfLink`, `OfIndexed`, `Visitable`, `Callback` (27 / 34 references), and attributes are declared `as_native` (9 / 13), now `Schemas.OfScalar` and its five basic scalars |
| `Conformance.write`, `Verilog.read` / `Verilog._Reader` | 111 / 79 + reader | `JSON.ToJSON(LANGUAGE.Builders).Reachable(Kind.Schema, tree)`: the old Reachable format, over a catalog and a plain object, where 0.26.5 takes a store and a `Readers.OfObject` and writes one transaction (3 / 2). The Verilog reader sends trees from Python to TypeScript this way |
| `Bridges.Python`, `Bridges.Verilog` | 667 / 736 | Read terms as 0.5.4's objects: `term.KIND`, `term.left`, ..., under 0.5.4's kind names (`constant`, `name`, `identifier`). In 0.7.0 a term is a nested value read through `Terms.kind_of` and `Terms.form`, and a dialect reuses the framework's `literal`, `variable` and `let`. Writers stay (38 calls / 38), but give specs written in a transaction, not terms. The vocabularies they check (`Domains.COMPARE`, `BINOP`, `UNARY`, `BINARY`) and `Text.ToText` stay. The Python dialect gained `list` and `mapping`, which have no counterpart in the bridge |
| Parsers, printers, `Definitions`, `Transpilers.TypeScriptToPython` | about 21,000 / 21,000 | Nothing from the siblings directly: they fail through `Framework.Syntax`. But they are written against today's plain, mutable syntax nodes: about 880 direct constructions in the parsers (Ccpp 206, Python 124, TypeScript 208, Verilog 343), about 430 `isinstance` dispatches in the printers, about 100 in definitions, and 122 with 188 builder calls in the transpiler; definitions, `Parents`, validation and `fold` key by a node's identity (`id(node)`) |

Not used, so not affected: `Bindings`, `Schemas.Form`, `properties_of`, `ListRecord`, `entries_of`,
`Comparison.OfNative`, `FromFunction`, terms' `domain`s and `Domains.register`. `Repr` and `Errors` (TypeScript) still
exist.

**How syntax nodes are modeled today.** Every language alike: a kind is a hand-written class (Python: typed
annotations; TypeScript: a `SPEC` of property constructors), plain and mutable, compared by identity, in categories
by subclassing. Each kind gets a meta-schema, a reference object schema `Programs.<Language>.<Kind>` tagged `kind`, one
property per attribute; children are entries of the relation `Programs.Children` (`parent`, `child`, `property`,
`index`). Builders (`LANGUAGE.Builders.<Kind>()`, `create`/`clone`/`update`) are mbse-programs' own, implementing the
0.10 visitor protocol. Ccpp has 171 kinds in 17 categories, Python 86 in 4, TypeScript 163 in 6, Verilog 281 in 18:
1,741 properties in all. `Definitions` (`Entity`, `Scope`, `Program`) are plain classes too, keyed by node identity.
[PRI-018: no model needs code to read or write](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-018) forbids both, and the open item on
[PRI-004: one visitor protocol per kind](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-004) beyond mbse-schemas (Principles, Open items) names
`LANGUAGE.Builders.<Kind>()` as still to move.

**What depends on mbse-expressions.** Only `Bridges` ([CAP-089: Python expressions bridged to Python source](../../../../mbse-basis/docs/capabilities/CAP-089.md),
[CAP-090: SystemVerilog expressions bridged to Verilog source](../../../../mbse-basis/docs/capabilities/CAP-090.md)), their
suites BRG and BRV, tutorials 8 and 9 and the skill. Tutorials 8 and 9 also build a `Shipment` schema outside a store
(`Proxies.OfStore().register`), read `.data` off writers, take a translator's result as a term, and make `this` the
constraint's subject (`E.variable("this")`), as do BRG-01, BRG-03, BRG-07, the BRV cases and the skill.

**Tests, tutorials, corpora, skill.**

- Tests: 22 suites, 224 cases a language. On removed API directly: SYN (11; SYN-03, SYN-05 and SYN-06 are about
  meta-schemas, the visitor protocol and snapshots), CONF (3), VLGRD (31, through the reader's exchange), BRG (7) and
  BRV (7), with 156 writer calls a language, SKL (3). The rest (PRS, PRT, DEF, PY*, TS*, TRN, VLG, VLGPRT, VLGDEF) use
  mbse-programs' own API, and change only as the node API does.
- Tutorials: 9 a language. 6 writes trees on the wire (Reachable); 8 and 9 are the bridges'; 1 to 5 and 7 use
  mbse-programs' API only.
- Corpora: in each of `conformance/python3` and `conformance/typescript5`, 4 grammars (plain data from `grammar()`,
  not the wire), 5 printed sources, and 5 snapshots in the old Reachable format, every one to regenerate: `cpp20`
  1,824 nodes, `python314` 1,181, `typescript59` 1,223, `typescript59-jsx` 118, `systemverilog2023` 3,321. The 8
  transpiled programs (24 files) do not touch the wire.
- Skill: `SKILL.md` and 4 references, copied into both packages (SKL-01); its 2 complete programs (SKL-02) write
  Reachable and use `this`.
- Dependents: mbse-codegen-python pins mbse-programs 0.3.28, and builds through `Framework.Syntax` and Python's syntax
  nodes ([CAP-027: Python3 source generated from schemas](../../../../mbse-basis/docs/capabilities/CAP-027.md)).

**Cost, measured.** In 0.26.5 (Python), a tree of nested value objects, built through the builders in one transaction:
2,044 nodes in 0.11 s, written as a Reachable transaction in 0.15 s and read back in 0.16 s; 6,138 nodes in 0.50,
0.40 and 0.46 s. A store takes about 25 ms to make. The largest corpus tree is 3,321 nodes.

**Unmerged branches.** None holds unmerged work: `batch4/conventions`, `priorities-drain` and `no-prepass` are merged
into `origin/main`, and `overhauls/meta-schemas` has no commit beyond it, so this repository's half of mbse-schemas'
meta-schemas overhaul was never made. No earlier port or overhaul work exists.

## Decided elsewhere, that applies

- **Schemas are defined in installs, in transactions.** "Every schema is defined in a module-scope `install(txn)`, a
  transaction that upserts it" ([CAP-115: schemas defined by idempotent installs](../../../../mbse-basis/docs/capabilities/CAP-115.md#decided));
  the dependents move to installs in their port ("install D7", there). An install and what uses it are separate
  transactions ([CAP-124: writes all-or-nothing in transactions](../../../../mbse-basis/docs/capabilities/CAP-124.md#decided)).
- **The corpora become Reachable transactions** (Store overhaul, step 5, above), one-transaction documents
  ([CAP-128: graphs sent as one-transaction documents](../../../../mbse-basis/docs/capabilities/CAP-128.md)), which
  names this repository's corpora and its Verilog reader among their uses.
- **Model first**, for mbse-expressions: "yes" to "the framework and each dialect defined by installs, terms stored in
  the store, the cases rewritten to it" ([its port](../../../../mbse-expressions/docs/proposals/port/README.md#decided),
  Decided, 1). Backed by [PRI-018: no model needs code to read or write](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-018):
  "No model should need code to read or write. Ever."
- **Terms are nested value objects of a union**: "there was some back and forth but I have landed on terms as value
  objects" (there, Decided, 2026-10-29), held by a reference object, their root (Decided, 2). Dialects extend the union
  by schema extension: "refinement has been superseded by schema extension", and "ah, schema *extension* is the
  preferred form" ([its API](../../../../mbse-expressions/docs/proposals/port/API.md), Settled in stage 3).
- **No domain on terms; type inference deferred**: "Terms do not designate their schema. Whatever reference object owns
  the root term must specify its schema", and evaluation does without, "as that involves building a type inference
  system which should be a follow-up capability" (its port, Stage 3, Decided, 1 and 2).
- **Each dialect a singleton by name, owning its vocabulary**: "yes, each dialect has a singleton by name" (its API,
  Settled in stage 3, 16), owning its domains through `Expressions.Framework.Defines` (Decided, 4). Other dialects'
  vocabularies as data are a follow-up (its API, 28).
- **`FromFunction` and free references removed; no `this`**: "Honestly FromExpression is not that important. Let's
  just remove that capability entirely"; "I had not envisioned that Expressions.FromFunction would support free
  references at all"; "There is no 'this' convention", and "I don't even want the tutorials introducing 'this' as a
  convention" (its port, Decided, 2026-10-30).
- **Writers stay until mbse-codegen-python moves off them**, then go (its port, Decided, 10 and 2026-10-29).
- **"Never guess the schema"**: what a value is, is never inferred from the shape of its data ([PRI-025: never guess the schema](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-025)).
- **"Never use wire format in examples"** (Store overhaul, 4f, "A transaction on the wire is its expression, nested").
- **"Do not invent another DSL by wrapping builder syntax"**: models are written in the builders' fluent syntax
  itself ([PRI-019: fluent builder syntax](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-019)).

## Decided

As the user decided (2026-11-02), on questions 1 to 3 (each answer quoted as written):

1. **A syntax node is a model.** "A syntax node is a model. This means there the mbse-schema definitions cover every
   kind of node of any possible AST in the standards."
2. **Files, scopes and statements are reference objects; expression terms are value objects.** "Files, scopes, and
   statements should be reference objects. When parsed from "native" AST (such as Python `ast`), the parser should
   generate an identity so path references are not necessary." "Expression terms are value objects. An instance of
   OfSchemas.Expression holds the expression root."
3. **Expressions are mbse-expressions' dialects, complete.** "Expression terms are value objects. `mbse-schemas` should
   make use of `mbse-expressions.Dialects.<lang_ver>.Expression`. Yes, this means the expression dialect must
   completely cover the AST. Rather than using schema-extension, if there are any gaps in the dialect as modeled in
   `mbse-expressions.Dialects.<lang_ver>`, they should be added into `mbse-expressions`. There is no reason for an
   expression dialect to exist that is ia subset of the corresponding node of AST in the real langauge." On the
   question of kind grouping, the user asked "To what end are you inquiring about kind grouping?"; answered (each slot
   names the schema of what it accepts: a union of kinds), not yet decided.

4. **Dialects by major version, over a native parser** (asked whether dialects go by language version, "yes that's
   my answer to 2"): "`mbse-programs` creates language dialects each of which supports a major version of the target
   language and all of the minor versions in it, such as Python3 or Typescript5. This means each language dialect must
   correctly handle the closure of syntaxes across minor versions such as 3.11 - 3.14. `mbse-programs` typically uses
   a "native parser" or "tree walker" that conforms to and tracks evolution of publish standards. To the degree that
   the chosen "native parser" supports parsing and preserving invalid syntax, `mbse-programs` should also." And (b)
   below: "`mbse-schemas` should make use of" means mbse-programs ("yes").

Asked in turn, "do counted objects roundtrip through `Visitors` in general and serialization in particular?": their
contents do (a document or snapshot writes the counted objects reachable from its root, numbered, and reading it
recreates them with their properties and links), their identity does not ("A counted object read from a document is
always a new one", CAP-127; a document cannot refer to one it does not hold, CAP-128; no durable references to them,
CAP-133; nothing is owned by one, CAP-118).

Open on these, asked of the user: (a) what a parser-generated identity is in mbse-schemas' identity modes (a singleton,
an owned object by path, a counted object with none): an owned object keyed by the generated id, or a new mode; (c) a
TypeScript dialect, which mbse-expressions does not have, and mbse-expressions' dialects renamed by major version; (d)
`Dialects.<lang_ver>.Expression`, each dialect's own expression holder, where mbse-expressions has one,
`Expressions.Framework.Expression`, whose root is any dialect's term. Questions 1 and 2 below are superseded; 3 is
answered in part.

## Questions for the user

1. **What a syntax node is.** (a) Model first: kinds defined by installs, trees store data built through mbse-schemas'
   builders and read through `Readers`, and every module rewritten to them; the kind classes, `Builder` and `OfStore`
   go. (b) Boundary first: the kind classes kept as the in-memory form, their schemas installed, trees written into
   and read from a store only to serialize;
   [PRI-018: no model needs code to read or write](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-018) forbids the
   classes it keeps, and (a) would follow it, building twice. (c) Kind classes generated from the installed schemas,
   as that principle allows ("proxies in mbse-schemas or generated dataclasses"); not available now:
   mbse-codegen-python depends on this repository and generates no TypeScript.
   *Recommended: (a), as decided for mbse-expressions. It rewrites about 21,000 lines a language; (b) mainly
   `Framework.Syntax` (about 1,100), the corpus writer, the Verilog reader and the bridges (Risks).*
2. **How a tree is stored.** (a) One nested value: each syntax node a value object, its children its properties,
   lists containers by int index, the root held by a reference object (as `Expressions.Framework.Expression` holds a
   term). (b) Owned reference objects linked by `Programs.Children`, a node's owner its parent, keyed by property and
   index, keeping identity and giving each node a path. (c) Today's: counted reference objects linked by
   `Programs.Children`. *Recommended: (a), as decided for terms, and the open question [CAP-084: program trees as data](../../../../mbse-basis/docs/capabilities/CAP-084.md#open-questions)
   already raises ("Value objects in lists"). Identity goes: definitions key a node by its path, and validation's
   sharing and cycle checks go, as mbse-expressions' did (its API, Settled while building, 6).*
3. **How a language's kinds are grouped.** Proposed: each category a union of its kinds, in the language's module
   (`Programs.Python.Expression`), a child property's schema the union of the categories it accepts, tagged by kind
   name, so that the wire names each node's kind and a reader never guesses it
   ([PRI-025: never guess the schema](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-025)); a framework union that each
   language extends by schema extension where a tree of any language is held (the root object). The alternative, one
   union of every language's kinds, needs tags qualified by language (`python_<kind>`, as mbse-expressions' dialects
   have them). *Confirm or correct.*
4. **What a language is.** Proposed, as for dialects: each language a singleton by name (`Programs.Python`), its kinds
   the schemas its module defines; its standards, availability (`SINCE`, `FEATURES`) and grammar stay code, as other
   dialects' vocabularies do, as data a follow-up. *Confirm or correct.*
5. **The API that builds and rewrites trees.** (a) mbse-schemas' builders only, in the caller's transaction:
   `parse`, `transpile` and a bridge's `expression` each give a spec that the caller writes, as a translation in
   mbse-expressions is "a writer of the target dialect's term, which its caller writes in a transaction" (its API,
   Settled in stage 2b, 12); a rewrite is a new spec, or an update in a transaction, not an assignment; `Parents`,
   `Visitor` and `Transformer` read through `Readers`. (b) Keep `LANGUAGE.Builders.<Kind>()` over mbse-schemas'
   builders: a DSL wrapping builder syntax, which
   [PRI-019: fluent builder syntax](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-019) forbids. *Recommended: (a).
   mbse-codegen-python, which builds through these builders, ports after this, as the order has it.*
6. **Definitions.** `Entity`, `Scope` and `Program` are derived from a tree, not stored. (a) They stay code for the
   port, keyed by a node's path. (b) They become a model of their own, schemas and installs. *Recommended: (a), (b) a
   follow-up capability of [CAP-087: definitions resolve names](../../../../mbse-basis/docs/capabilities/CAP-087.md);
   the principle, above, may be read to require (b) now.*
7. **The bridges.** Ported to 0.7.0: terms read through `Terms.kind_of` and `Terms.form` under its kind names, written
   through the writers while they stay. The Python dialect's new `list` and `mapping` either (a) bridge to Python's
   list and dict displays (`List`, `Dict`), keeping "every term has a counterpart" (BRG-01), or (b) are refused by
   name. *Recommended: (a).*
8. **`this`.** The tutorials, BRG, BRV and the skill make `this` a constraint's subject. Proposed: name each variable
   for what it holds (`shipment`, or the fields themselves, as a `constraint` block refers to a class's members), as
   decided. The Verilog bridge maps the variable `this` to SystemVerilog's keyword `this` (`ThisExpression`) and back: (a) keep
   it, as the language's spelling of a name the dialect can hold, asserted by one case; (b) refuse
   `ThisExpression` by name. *Recommended: (a).*
9. **Scope now.** All four languages, the transpiler, both bridges and the Verilog reader's exchange, ported with the
   model. Not now: the Ccpp bridge
   ([CAP-091: Ccpp expressions bridged to C and C++ source](../../../../mbse-basis/docs/capabilities/CAP-091.md)), reference front
   ends, transpilers and bridges rebuilt on mbse-patterns' transforms ([CAP-074: transforms applied step by step](../../../../mbse-basis/docs/capabilities/CAP-074.md)),
   and the skill split by language
   ([PRI-016: guidance written once](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-016), its open item).
   *Recommended as stated.*
10. **How to stage it.** Every module fails at import, so the first stage whose gates pass must bring a language over
    whole. (a) One stage for everything. (b) Language by language: the framework and Python first, the other languages'
    packages, cases, tutorials and corpus files set aside and restored one stage each, as mbse-expressions' stage 2a set
    aside the dialects 2b restored (its API, What stage 2b needed). *Recommended: (b).*

## Stages (proposed, once decided)

Each on the branch `port-schemas`, with both gates at 100% and the corpora regenerated in both languages; a stage
touching a sibling is made in a workspace (`polyrepo.py workspace <dir> --edit <sibling>`), since a gap found there
is reported, not worked around ([PRI-032: a sibling's gap is reported, not worked around](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-032)).

1. **The decisions**: this proposal decided; the decisions recorded in mbse-basis, in the detail files of the
   capabilities they settle (program trees as data, definitions, the two bridges), in a pull request there.
2. **The framework and Python** (question 10's (b)): pins mbse-schemas 0.26.5 and mbse-expressions 0.7.0
   (`siblings.json`, `pyproject.toml`, `package.json`); the framework's install, traversals, validation and standards'
   checks; Python's install, parser, printer and definitions; `Bridges.Python`; SYN, PY, PYPRS, PYPRT, PYDEF, BRG,
   CONF and SKL; Python's corpus as a Reachable transaction; the tutorials as far as they are the framework's and Python's.
3. **TypeScript and the transpiler**: TS, TSPRS, TSPRT, TSDEF, TRN; tutorial 7; its corpora.
4. **Ccpp**: CPP, PRS, PRT, DEF; its corpus; the README's example.
5. **Verilog**: its install, reader (the exchange from Python to TypeScript as a Reachable transaction), printer and
   definitions; `Bridges.Verilog`; VLG, VLGRD, VLGPRT, VLGDEF, BRV; tutorial 9; its corpus.
6. **Tutorials, skill, README, EQUIVALENCE, AGENTS; release** 0.4.0, a minor bump since dependents must adapt
   ([PRI-031: the version is the contract](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-031)). Then mbse-codegen-python.

## Risks

- **Size**: question 1's (a) rewrites about 21,000 lines a language, every test case's and tutorial's construction of
  a tree, and every example; the largest of the dependents' ports.
- **Cost**: building through the builders, in transactions, is about 0.05 to 0.08 ms a node (measured above), and
  grows faster than the tree; parsing a large source, and suites that parse hundreds, will slow.
- **Ergonomics and typing**: mbse-schemas' builders are more verbose than `LANGUAGE.Builders.<Kind>()`, which are
  typed in TypeScript so that a wrong kind of child does not compile (SYN-04, a listed deliberate difference). Whether
  mbse-schemas' TypeScript builders type a union's branches as precisely is to check.
- **Identity**: definitions, `Parents`, validation's sharing checks and `fold`'s memo rely on a node's identity
  (`id(node)`), which a nested value lacks (question 2).
- **The commit-time rule**: an install and the trees built with it are separate transactions.
- **No reference between stores**: a constraint and the data it is evaluated over share a store (tutorials 8 and 9).
- **Extension limits**: an extension's adjacency is to a relation of two links and no properties; data owned by a
  schema object fails to write (mbse-expressions' API, Settled in stage 3, 26).
- **Equivalence**: byte-identical JSON in both languages, the Verilog reader's exchange included.
- **mbse-codegen-python breaks** when this releases, until its own port.

---

<!-- nav -->
[← FEA-008: expressive program models](../../../../mbse-basis/docs/features/FEA-008.md) · [Home](../../../README.md)
