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
  Decided, 1). Backed by [CAP-282: no model needs bespoke schema-aware code to read or write](../../../../mbse-basis/docs/capabilities/README.md#CAP-282):
  "No model should need bespoke schema-aware code to read or write. Use mbse-schemas built-in serialization support."
- **Terms are nested value objects of a union**: "there was some back and forth but I have landed on terms as value
  objects" (there, Decided, 2026-10-29), held by a reference object, their root (Decided, 2). Dialects extend the union
  by schema extension: "refinement has been superseded by schema extension", and "ah, schema *extension* is the
  preferred form" ([its API](../../../../mbse-expressions/docs/proposals/port/API.md), Settled in stage 3).
- **No domain on terms; domain inference deferred**: "Terms do not designate their schema. Whatever reference object owns
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

The user's consolidated statement (2026-11-02), the decision of record; the entries after it record how it was
reached:

> `mbse-programs` creates language dialects each of which supports
> a major version of a target language and all of the minor versions
> in it, such as Python3 or Typescript5. This means each language
> dialect must correctly handle the closure of syntaxes across minor 
> versions such as 3.11 - 3.14. 
>
> The `mbse-schema` definitions must cover every kind of node 
> of any possible AST in the standards.
>
> A syntax node is a model. 
>
> Files, scopes, and statements should be owned reference objects. 
>
> Expression terms are value objects. 
>
> `mbse-programs` will have a framework of base models that are
> language/dialect independent:
>
> ```python3
> OBJECT Programs.Framework.Provenance # captures file name, path, repository link and hash, etc.
> OBJECT Programs.Framework.File # represents a file or translation unit
> RELATION Programs.Framework.HasProvenance(file, provenance)
> OBJECT Programs.Framework.Statement # represents a statement within a file
> RELATION Programs.Framework.HasLocation(statement, file, line)
> RELATION Programs.Framework.HasParent(stmt1, stmt2)
> ```
>
>
> `mbse-programs` should make
> use of `mbse-expressions.Dialects.<lang_ver>.Expression`. Yes, this
> means the expression dialect must completely cover the AST. Rather
> than using schema-extension, if there are any gaps in the dialect
> as modeled in `mbse-expressions.Dialects.<lang_ver>`, they should
> be added into `mbse-expressions`. There is no reason for an
> expression dialect to exist that is ia subset of the corresponding
> node of AST in the real langauge.
>
> Syntax tagging (for example between a file and a statement) should 
> be clear based on the relation name which may hint at or take on the
> syntax element name.
>
> Growth by extension is natural when relations are used and because
> schema extension is explicitly supported in `mbse-schemas`.
>
> `mbse-programs` typically uses a "native parser" or "tree walker"
> that conforms to and tracks evolution of publish standards. To
> the degree that the chosen "native parser" supports parsing and
> preserving invalid syntax, `mbse-programs` should also.
>
> To what end are you inquiring about kind grouping?

Revised by the user the same day (the framework's models, superseding the block above; then ownership):

> ```python3
> OBJECT Programs.Framework.Provenance # captures file name, path, repository link and hash, etc.
> OBJECT Programs.Framework.File # represents a file or translation unit
> RELATION Programs.Framework.HasProvenance(file, provenance)
> OBJECT Programs.Framework.Scope # represents a scope
> OBJECT Programs.Framework.Statement # represents a statement within a file
> RELATION Programs.Framework.HasScope(statement, scope)
> RELATION Programs.Framework.HasLocation(statement|scope, file, line)
> RELATION Programs.Framework.HasParent(child, parent)
> ```
>
> Dialects must establish complete ownership through relations that 
> represent parent-child links in the AST. A dialect may choose to reuse
> the generic `Programs.Framework.HasParent`, or it may define
> more specific relations for particular edges of the grammar.

On ownership, the user: "yes, I replaced the language to clarify we are using ownership as mbse-schemas defines it":
a node is owned through the parent-child relation that holds it, its identity its owner's and its key, up to its
file.

On question 4, shown the mechanisms mbse-schemas builds (refinement, a kind union grown by schema extension, a link
filled by any schema declaring an adjacency on its relation; intersections as subtyping, CAP-034, not built) and
refinement in an install (`Programs.Python3.If` `.refines([Statement])`), the user decided: "good. I didn't know that
was built. let's use refinement from `Statement` to dialect-specific kinds like `If`." A dialect's statement kinds
refine `Programs.Framework.Statement`: each inherits its members, `Schemas.is_a` accepts it wherever a `Statement` is
linked, a store's `Statement`s include it, and the wire tags it by its schema's name where several fill a link.

On dialect names, asked how C and C++ divide into major versions: "Maybe C11, C17, C23 Cpp17, cpp20, cpp23" (tentative;
noted to the user: C17 adds no syntax over C11, being technical corrigenda, so `C11` and `C17` would be identical). On
Verilog: "yes keep verilog as a subset of systemverilog, presuming that is how the standards are partitioned" (it is:
IEEE 1800-2009 merged IEEE 1364 Verilog into SystemVerilog, and 1364 was withdrawn).

It settles question 4 (files, scopes and statements are owned reference objects) and answers the grouping question
(tagging by relation names; growth by relations and schema extension).


As the user decided (2026-11-02), on questions 1 to 3 (each answer quoted as written):

1. **A syntax node is a model.** "A syntax node is a model. This means there the mbse-schema definitions cover every
   kind of node of any possible AST in the standards."
2. **Files, scopes and statements are reference objects; expression terms are value objects.** "Files, scopes, and
   statements should be reference objects. When parsed from "native" AST (such as Python `ast`), the parser should
   generate an identity so path references are not necessary." "Expression terms are value objects. An instance of
   OfSchemas.Expression holds the expression root."
3. **Expressions are mbse-expressions' dialects, complete.** "Expression terms are value objects. `mbse-programs` should
   make use of `mbse-expressions.Dialects.<lang_ver>.Expression`. (As first written, "`mbse-schemas` should make use
   of"; the user corrected it to mbse-programs.) Yes, this means the expression dialect must
   completely cover the AST. Rather than using schema-extension, if there are any gaps in the dialect as modeled in
   `mbse-expressions.Dialects.<lang_ver>`, they should be added into `mbse-expressions`. There is no reason for an
   expression dialect to exist that is ia subset of the corresponding node of AST in the real langauge." On the
   question of kind grouping, the user asked "To what end are you inquiring about kind grouping?"; answered (each slot
   names the schema of what it accepts: a union of kinds), not yet decided.

   Asked whether each dialect has its own expression holder or the framework's one restricted to the dialect, the
   user answered "3." with the same text, naming `mbse-expressions.Dialects.<lang_ver>.Expression`: each dialect
   defines its own `Expression`, whose root holds that dialect's terms.
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
TypeScript dialect, which mbse-expressions does not have, and mbse-expressions' dialects renamed by major version. Questions 1 and 2 below are superseded; 3 is
answered in part.

As the user decided (2026-11-02), on the questions below, once the consolidated statement above had answered or
changed most of them:

- **1, 2, 3 and 10**: answered by the decisions above (a syntax node is a model; files, scopes and statements owned
  reference objects, expressions values; the framework's models, statement kinds refining `Statement`, edges named
  relations, expressions grouped by mbse-expressions' unions; stages language by language, after mbse-expressions'
  complete dialects). Their options below are superseded.
- **4. What a language is**: "yes, you an make a singleton by name for the language": each language a singleton by
  name (`Programs.Python3`), owning its statement kinds; its standards recorded as data, as for C and C++.
- **5. The API that builds and rewrites trees**: "yes, P-019 applies": mbse-schemas' builders only, `parse` and
  `transpile` each giving a spec that the caller writes in a transaction; `LANGUAGE.Builders` goes.
- **6. Definitions**: "yes to (a)": `Entity`, name resolution and `Program` stay code over the stored tree for the
  port, computed on demand and not stored (`Scope` is a model, as the framework has it); a model of their own is a
  follow-up, which must anchor a use of a name on its statement and the term's path, since a term is a value.
- **7, 8 and 9**: "7,8,9: confirmed": the bridges go, mbse-programs using mbse-expressions' dialects directly, nothing
  left to translate; no `this` convention, SystemVerilog's own `this` a kind of its complete dialect; the scope now all
  four languages (`Python3`, `TypeScript5`, `C` and `Cpp`, `SystemVerilog`) and the transpiler, not reference front
  ends or mbse-patterns' transforms.

## Questions for the user (as posed; answered above)

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

Redrawn after the user's decisions (2026-11-02): expressions are mbse-expressions' dialects, complete, so they come
first. Each stage passes both gates at 100% with the corpora regenerated, in the repository it changes.

1. **mbse-expressions: complete dialects by major version** (its 0.8.0). Each dialect covers its language's whole
   expression syntax across its minor versions and has its own `Expression` holder (`Expressions.<Dialect>.Expression`):
   `Python3` (mbse-programs' Python expression kinds merged with mbse-expressions' Python dialect), `TypeScript5` (new),
   `C` and `Cpp`, each covering its standards (C11 to C23, C++17 to C++23; decided on mbse-expressions' proposal,
   question 3), `SystemVerilog` (Verilog its
   subset). Evaluation may stay shallow; the model and printing are complete, checked against each grammar's node list.
   Parsing stays here, in mbse-programs (stage 2 on), as the user decided on mbse-expressions' proposal ("yes fix that
   phrase"). Proposed and decided in mbse-expressions' `docs/proposals/dialects/README.md`.
2. **mbse-programs: the framework and `Python3`.** `Programs.Framework` (`Provenance`, `File`, `Scope`, `Statement`,
   `HasProvenance`, `HasScope`, `HasLocation`, `HasParent`); `Python3`'s statement kinds refining `Statement`, owned
   through the parent-child relations; the parser from the native parser's tree to owned statements and the dialect's
   expressions; printer; definitions; pins mbse-schemas 0.26.5 and mbse-expressions 0.8.0.
3. **The whole tree as values, then `TypeScript5`** and the transpiler ([Stage 3: the whole tree as
   values](#stage-3-the-whole-tree-as-values)): `Python3` reworked to values; mbse-expressions' open unions for the
   terms that hold statements; then `TypeScript5` and the transpiler.
4. **`C` and `Cpp`**, each covering its standards ([Stage 4: C and Cpp](#stage-4-c-and-cpp)).
5. **`SystemVerilog`** (Verilog its subset), and the exchange from Python to TypeScript.
6. **Tutorials, skill, README, EQUIVALENCE; release.** Then mbse-codegen-python. The version is 0.4.0 from stage 2,
   which brings the new API, as the user decided ("bump the verion and no need to add 'dev' as a suffix").

## Stage 2, Python3: the design (for review, 2026-11-16)

Redrawn for the siblings as they stand: mbse-schemas 0.27.0 (`c64cb18`, CAP-315 stage 2) and mbse-expressions 0.10.0,
which still pins mbse-schemas `<0.27`. As the user decided (2026-11-16): CAP-312 and CAP-314 land in mbse-schemas first,
as necessary to stabilize it with CAP-316; once they do and mbse-expressions is re-pinned to them, that pair of commits is
this port's freeze point, and the siblings take only additive changes until the port lands. Work that parallelizes runs
meanwhile. Python only; TypeScript and the equivalence gate follow in stage 3 (proposed).

**Written to 0.27's rules from the start** ([CAP-315](../../../../mbse-basis/docs/capabilities/CAP-315.md), mbse-schemas'
`tests/37_Lifetimes.ipynb`), so that the freeze point's bump changes no code:

- every read and write of the tree within a transaction; a visitor never kept past the transaction that made it, nor
  keyed by `id()` across transactions;
- `singleton` and `extent` only in a transaction; transactions never nested;
- between transactions, an object held as its `References.OfObject`, found again by navigation or by a symbol given
  the reference; a frame read as references and `assigns`;
- no counted objects: every object found again is a singleton or owned by key, as the stacked stores direct ("A model
  should give every object it must find again a singleton or an owner+key"); counted identity is being deprecated.

**The model** (superseded: [Stage 3: the whole tree as values](#stage-3-the-whole-tree-as-values)). As decided above: `Programs.Framework`'s models, `Programs.Python3` a singleton by name, its statement
kinds (`Expr`, `Assign`, `AugAssign`, `AnnAssign`, `Assert`, `Pass`, `Delete`, `Return`, `Raise`, `Break`, `Continue`,
`Import`, `ImportFrom`, `Global`, `Nonlocal`, `TypeAlias`, `If`, `While`, `For`, `AsyncFor`, `Try`, `TryStar`, `With`,
`AsyncWith`, `Match`, `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `Comment`) refining `Statement`, each owned by its
parent through `HasParent` (or a relation named for the edge) keyed by the property and index; `Module` a `File`. An `except`
clause and a `case` (`ExceptHandler`, `MatchCase`), which hold statements, refine a framework model of their own,
`Programs.Framework.Clause`, owned as a statement is (decided below, 4); an import's aliases and a `with` statement's
items (`Alias`, `WithItem`), which hold none, are value objects of the statement that holds them. Expressions are mbse-expressions' `Python3` terms; annotations, returns, type aliases' values and type
parameters `Python Types` terms; a case's pattern a `Python Patterns` term; a function's parameters `Python3.Arguments`,
a class's keywords `Python3.Keyword`, the dialect's own helpers. Gaps are fixed in mbse-expressions, never by extension
here (CAP-226).

**Reused from 0.3.28**, measured: about 40% of the Python language's 3,000 lines is independent of how a node is held
and moves nearly verbatim (tree-sitter's source handling and pre-pass, error positions, the precedence ladder, the
regrouping of binary operators, `SINCE` and `FEATURES`, the printer's layout, `Framework.Definitions` and Python's
scoping rules); the converter and the printer keep their dispatch tables, one function per kind, rewriting only how a
node is built and read. The expressions' printer is mbse-expressions' `Text.ToText`; its `Text.FromText` moves here
(CAP-226).

**Cost**, measured on 0.27: about 0.13 ms a node built in a transaction, about 0.1 ms written as a Reachable document;
the Python corpus' 1,181 nodes, about 0.15 s.

**The corpora as frames**, as the user decided (2026-11-16): "transaction is one representation but may be difficult
to compare. Frame I think already has equality and comparison"; then, shown the frame measured, "yes". A tree of owned
objects is not carried by a `Reachable` transaction, which writes its root and the counted objects it reaches and
refers to every other object by its object reference; a snapshot carries it with every schema of the store (274 KB for a
two-statement program). The transaction a parse gives carries it too (180 KB for the Python corpus, `Plain.ToPlain
(store).Transaction`), but compares only as text. So each corpus file is the frame that transaction gives back, as a
`References.OfFrame` (`References.of(store, frame)`) written by `Plain.ToPlain(store).Value`: each statement's
object reference, which names its place in the tree, in `binds`, and its properties, its terms among them, in `assigns`.
Measured on 0.27 for the Python corpus: 146 KB; byte-identical when parsed in two stores; equal under `Comparison`
once both are read into one store (a store's own schema objects make two stores' values incomparable); equal and
byte-identical where only the source's layout differs; incomparable, and differing, where a value does. A frame
witnesses a program and does not rebuild it: a program is rebuilt by parsing its source. `assigns` holds each value as
a value of any schema, which names its schema, so the statement kinds' lists are named containers
(`Programs.Python3.Terms`, ...).

**What the port needs of its siblings** is [a proposal of its own, parked](../sibling-gaps/README.md) until the
siblings are stable enough for the port to proceed, as the user decided: each gap the port found in mbse-expressions
and mbse-schemas, its cost to the port, and an additive fix.

**Decided** by the user (2026-11-16), on the three questions as posed:

1. **A statement's property holds the term**, a nested value (`If.test: Expressions.Python.Python3.Term`), owned with its
   statement and reached through its statement's object reference: "yes that is the obvs way". The holders (`Expressions.Python.Python3.Expression`),
   counted objects with no object reference under 0.27, stay for a constraint's root. Asked as (a) a nested value, or
   (b) a holder per expression related to its statement.
2. **A singleton `Programs.Framework.Workspace` owns the files**, keyed by path: "sure that works".
3. **mbse-expressions moves to 0.27** by the session that built CAP-315 stage 2, after the CAP-316 re-pin of
   mbse-expressions merges: "sure that works".
4. **A clause is not a statement.** Shown a module whose `except` clause and `case` refined `Statement`, the user: "I
   don't much like treating a clause as a statement when it can only appear in that place". Of the names offered for
   the framework's model of a part of a statement that only it may hold, and that holds statements (`Clause`, `Arm`,
   `Part`), the user chose `Programs.Framework.Clause`, with VOC-032 narrowed to it ("1.").
5. **Invalid syntax is kept, never raised** (2026-11-17), as far as tree-sitter-python's recovery allows ("To the degree
   that the chosen native parser supports parsing and preserving invalid syntax, mbse-programs should also"). Where a
   broken statement lands, (a): a framework kind, `Programs.Framework.Error`, the statement-level counterpart of
   mbse-expressions' `error` term, holding the skipped source (`text`) and the statements recovered within it as owned
   children through `HasParent`, every language's parser to use it. Whether to raise, (a): `parse` keeps invalid syntax
   and never raises `ParseError` for it; `Check.validate` reports each `Error` and each `error` and `missing` term, each
   located, so a caller who needs a clean tree validates it. Within an expression, the dialect's `error` (`text`,
   `terms`) and `missing` (`kind`) terms, as mbse-basis CAP-226 decided. The pre-pass stays: only what remains after
   it is invalid. Decided by the agent, in the modules' docstrings, each *(agent)*:
   - an `Error`'s recovered statements are its children by `body` and index; a compound statement whose header or
     clause is invalid is an `Error` as a whole, its blocks' statements recovered; an `Error` with no text stands for a
     newline tree-sitter found missing (two statements on a line without `;`), which its API does not show;
   - an `ERROR` is never taken as an operand: the innermost expression that holds it is an `error` term, its text as
     written and its recovered terms each expression read within it; so are constructs `Python3` cannot hold (`a <> b`,
     `10L`); a `MISSING` expression is a `missing` term of the node type expected; a `MISSING` token makes what holds it
     invalid;
   - Python 2's `print x` and `exec x`, a tuple parameter and a type parameter that is no name are `Error`s; `ParseError`
     remains only for text that is no text (a lone surrogate);
   - printing writes an `Error`'s text, its first line at its level and the others as written, and not its children,
     so a parsed invalid file prints back as written where invalid and in the printer's layout elsewhere;
   - `validate` words an `Error` as mbse-expressions words an `error` term, `body[1]: invalid syntax 'x = = 1'`; an
     `Error` may stand where a statement or a clause may; `check` skips invalid syntax, which no standard lists, and
     checks what was recovered within it;
   - definitions descend into an `Error`'s recovered statements, in the scope it stands in; its text binds nothing,
     and an `error` term's recovered terms are uses.

## Stage 3: the whole tree as values

Stage 3 met what Python3 never did: statements within an expression. mbse-expressions' TypeScript5 leaves a function
expression's, a block-bodied arrow's and a class expression's body out of the term (mbse-basis [CAP-226: complete
expression dialects](../../../../mbse-basis/docs/capabilities/CAP-226.md#decided), "Bodies within expressions are not
part of the term"), and stage 2's statements, owned reference objects, cannot be held by a term, a value: mbse-schemas
0.28 refuses a reference object in a value's property ("property 'body' takes a value object or a Spec"). Python3's
lambda has an expression for its body, and its class members are statements, so neither question arose there.

**Decided** by the user, in this order:

1. **A crossover is a property of the term**: "For any dialect A if term T_A has a clause(s) that crosses over to another
   dialect's expression language, the crossover should be modeled as a property of T_A."
2. **Which dialect defines what**: "mbse-expressions defines a dialect for expression grammar and mbse-programs defines
   a dialect for statement, definition, and file grammar".
3. **The whole tree is values.** Asked first "dialects define expressions and statements as value objects, no?", then
   "Perhaps blocks and statements should be value objects", and "Or statement may have both a reference and value
   representation. Especially if the dialect's grammar maps well onto such a dichotomy". Shown that a separation of
   files and definitions as references from statements and expressions as values ("can we cleanly separate: File
   (reference), Definitions (references), nested decls such as namespace, Statement Kinds (values), Expression Kinds
   (values)") leaves seams (a definition within a statement, a body mixing definitions and statements, `export`
   wrapping a declaration): "Because modern languages do not have a clean lexical separation between definitions and
   statements we may have to resort to "the whole AST is value objects". It's lexically proportionate, so maybe that's
   just tolerable." Asked whether to record that as decided: "yes".

This supersedes, for every language, that statements and scopes are owned reference objects (the consolidated
statement's "Files, scopes, and statements should be owned reference objects", its revised framework's relations, and
stage 2's model). What it means:

- **References**: the singleton `Programs.Framework.Workspace`, each `Programs.Framework.File` it owns by path, and the
  file's `Provenance`. A file holds its tree as one value, as a holder holds its root term.
- **Values**: everything a file holds: its statements, definitions, clauses, class members and invalid syntax
  (`Programs.Framework.Error`), and the expressions within them, which were values already. A node is found again by
  its place in its file, as stage 2's `Definitions` anchors a use within a term.
- **The crossover**: where a term holds statements, mbse-expressions' dialect gives the term a property typed by an
  open union of its own, which mbse-programs' dialect extends by schema extension with its block (shown in a scratch
  store on mbse-schemas 0.28, below). The
  dependency stays one way: mbse-expressions names nothing of mbse-programs'. For TypeScript5: its function, arrow and
  class expressions; later C's and C++'s statement expressions and lambdas.
- **What goes**: `Programs.Framework.HasParent`, `HasLocation`, `Opens`, `HasScope` and `Scope` as a stored model, which
  a value cannot fill: nesting is ownership, a line is a property, and scopes are derived on demand, as `Definitions`
  already are (Decided, 6). `Statement`, `Clause` and `Error` stay, as value kinds the languages' kinds refine.

Checked on mbse-schemas 0.28, in a scratch store with stand-ins for both dialects (a reference object holding a function
expression whose `body` is a block of statements holding terms):

- **Read back as written**: read in a later transaction, the value is the one written, every node tagged by its branch.
- **Rewritten in place**: a later upsert that writes part of a value merges into it. Setting only the function's name
  kept its body. Writing one element of a list by its index (`body({1: ...})`) added it beside the element already
  there. So a rewrite writes down to what it changes, without replacing the file's tree.
- **The corpora as frames still hold** (Decided, "The corpora as frames"): a parse's frame binds the file, and its
  `assigns` carry the file's whole tree as one nested value, each node tagged by its branch.

What it changes beyond this repository's model, for the user's attention:

- **Transforms** (mbse-transforms; mbse-codegen-python's transforms over Python trees): a pattern's symbols bind
  reference objects, so a transform's prototype can no longer bind a statement or a class member. Its candidates come
  per file, and its procedures navigate within the file's value: mbse-codegen-python's "from Python" direction, which
  matches `ClassDef` and `TypeAlias` statements, will be written that way, when its port comes.
- **Definitions' anchors** become a place within the file's value, its property and index steps then the term's path,
  in place of a statement's object reference. The parked [sibling gaps](../sibling-gaps/README.md) item 10 (anchors
  built from `HasParent`'s keys) and item 12's resolution of references may then no longer apply here; that proposal
  is updated with the rework.

The stages change with it (below): stage 3 reworks `Python3` to values, asks mbse-expressions for the open unions, then
builds `TypeScript5` and the transpiler.

## Stage 4: C and Cpp

Two languages, `Programs.C` and `Programs.Cpp`, each a singleton by name, the whole tree values, as stage 3 decided.
Their standards are mbse-expressions' C and C++ dialects': C11, C17 (C11's corrigenda, with no new syntax) and C23; and
C++17, C++20 and C++23. Where a C or C++ term holds statements or declarations, a property of the term holds them, typed
by an open union in mbse-expressions, which it declares a boundary (`Terms.boundaries`) and mbse-programs extends, as
for TypeScript5: a GNU statement expression's body and a C++ lambda's body (`block`), and a struct's, a union's or a
class's member declarations (`members`, which their `body: bool` only marked).

**Decided** by the user, on three questions as posed, and on the ABI:

1. **Each language its own native parser**: tree-sitter-c for C, tree-sitter-cpp for C++, each language's departures
   from its standards enumerated and pre-passed against its own standard
   ([CAP-026](../../../../mbse-basis/docs/capabilities/CAP-026.md#decided)). Asked as (a) that, or (b) tree-sitter-cpp
   for both, as 0.3 parsed them: "1(a)".
2. **C's statement kinds, and C++ reusing them**: `Programs.C` defines its kinds; `Programs.Cpp` defines only what C++
   adds, its union listing C's kinds and its own, as mbse-expressions' C++ writers derive from C's. Asked as (a) that,
   or (b) two independent sets of kinds: "2(a)". Shown then that C's kinds hold C's terms and C++'s terms are of a
   dialect of their own (mbse-expressions' `Cpp`, with its own copy of each kind it shares with C), so that C's
   schemas cannot hold C++'s terms and cannot be shared, and offered (a) C++ reusing C's kinds by definition, one
   table of properties (`Programs.C.Statements.properties`) generating both languages' schemas, as built; (b) one
   shared set of schemas over a union of C's and C++'s terms; or (c) mbse-expressions' `Cpp` dialect extending C's:
   "(a) is fine for now."
3. **A preprocessor directive between statements is a statement holding the directive term**, mbse-expressions'
   `C Preprocessor` term, and a conditional's statements a property of that term, typed by an open union mbse-programs
   extends: the crossover rule applied again. Asked as (a) that, or (b) directives as mbse-programs' own statement
   kinds: "3(a)". tree-sitter reads only conditionals that enclose whole statements; one that splits a construct
   (`#if` within a function's body, closed after it) is an entry in each parser's enumerated departures.
4. **The ABI is applied last**: "Of course C and C++ need a ABI, but if we can model programs in an abi-agnostic form
   and apply the ABI at the last minute, that would be advantageous". A program names no ABI: a translation unit holds
   C as written, and nothing in its tree depends on a target. `Check.validate` checks what does not depend on one; the
   checks that do are not made: a literal's type and its range, `sizeof` and `_Alignof`, and constant evaluation (an
   array's size, a `static_assert`'s condition, a bit-field's width, a `case` label's value). A later step applies an
   ABI at the call that needs one: `validate_for(store, path, abi)` is planned, with mbse-expressions reading a term's
   types under an ABI the caller gives, rather than one the term's holder names, and reporting a check that needs an
   ABI as deferred rather than as a problem. Until then, the problems mbse-expressions gives where a type needs an ABI
   ("'int' is not a type C defines, and its expression names no ABI") stand for those deferred checks, and `validate`
   leaves them out.

The stage builds, in order: mbse-expressions' open unions for the C family (both implementations, a release); then
`Programs.C` (statements, parse, print, definitions, standards, check, a C corpus source); then `Programs.Cpp` over it;
each with its suites at 100%.

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
