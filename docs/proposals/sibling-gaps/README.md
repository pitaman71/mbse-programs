<!-- nav -->
[← Porting to the stabilized mbse-schemas and mbse-expressions](../port/README.md) · [Home](../../../README.md)

# What the port needs of mbse-expressions and mbse-schemas (a proposal, parked)

**Parked**, as the user decided: "rather than send it now, let's write a proposal and park it. I want a clean break when
mbse-schemas and mbse-expressions are stable enough for mbse-programs port to proceed." Nothing here is asked of either
repository until the user unparks it, after the port's freeze point (mbse-schemas with CAP-312 and CAP-314, and
mbse-expressions on it).

The Python port ([stage 2](../port/README.md#stage-2-python3-the-design-for-review-2026-11-16)) found these gaps
while building on mbse-schemas 0.27 and mbse-expressions 0.10 and 0.11. Each is reported, not worked around by schema
extension: "if there are any gaps in the dialect as modeled in `mbse-expressions.Dialects.<lang_ver>`, they should be
added into `mbse-expressions`" ([Decided](../port/README.md#decided), 3), and
[PRI-032: a sibling's gap is reported, not worked around](../../../../mbse-basis/docs/PRINCIPLES.md#PRI-032). Each fix
proposed is additive. None changes what a program means: the conformance source parses, prints and parses to the same
CPython `ast` without them.

## mbse-expressions

1. **A tuple does not record its parentheses** (priority). `Expressions.Python.Python3`'s `tuple` holds its elements
   alone, so `a, b` and `(a, b)` are one term, and wrapping a tuple in `parenthesized` prints `((a, b))`.
   - What it costs the port: printing loses every parenthesized tuple of the source (`ONE = (1,)` prints `ONE = 1,`;
     `TEXTS = ('a', 'b')` prints `TEXTS = 'a', 'b'`), where 0.3 kept them; and a bare `except A, B:`, which Python 3.14
     added, cannot be told from `except (A, B):`, so `Check` cannot flag it against 3.13 (P3CHK-02).
   - Proposed: either a flag on `tuple` that records written parentheses, or `parenthesized` around a `tuple` printed
     with one pair, as a tuple display's own parentheses.
2. **`ToText` prints a term only at the top level.** It parenthesizes a tuple, a named expression and a `yield` as an
   expression's root needs, so the printer strips the one pair it adds where a statement takes them bare (an expression
   statement, an assignment's value, a test).
   - Proposed: `ToText(term, level)`, a term printed at a precedence level of `Text.py`'s scale, or an entry point for a
     term in a statement's position.
3. **Python Patterns has no parenthesized pattern.** `case (1 | 2) as s:` reads back as `case 1 | 2 as s:` (0.3 lost
   it too).
   - Proposed: a `group` kind, as `ast` has none but the grammar does (`group_pattern`).
4. **A slice does not record a second colon.** `a[::]` prints as `a[:]`.
   - Proposed: a flag on `slice`, as spelling a literal keeps its text.
5. **The names a binder binds come without where each is written.** `Python3.target_names` and `Patterns.bound_names`
   give sets, so `Definitions` walks each target again to anchor each name, its tests checking the walk against them.
   - Proposed: a variant that gives each name with its path within the term.
6. **No public walk of a term by property names.** `Terms._labelled` is private and drops indices; `Definitions` walks
   through `Objects.properties`.
   - Proposed: a public walk giving each subterm with its path of property names and indices.
7. **A standard tags a kind, not a property or a value.** Met by mbse-expressions 0.15.0's grammar clauses (mbse-basis
   [grammar clauses by version](../../../../mbse-basis/proposals/GRAMMAR-CLAUSES.md), stage 1): Python3's and
   TypeScript5's `Check` read them, their terms' from mbse-expressions' dialects and their statements' from each
   language's own (`Standards.GRAMMAR_CLAUSES`), and their code tables, `FEATURES` and `STATEMENT_FEATURES`, are gone.
8. **No writers for invalid syntax.** `Expressions.Python.Python3` writes each of its kinds (`name`, `call`, ...) but
   not the framework's `error` and `missing`, which every dialect's `Term` holds, so `Parse`, the first parser to keep
   them, writes them on the union's branch itself (`P.Writer(lambda u: u.error(...))`), and `Python Types` and
   `Python Patterns` terms through its `_term`.
   - Proposed: `error(text, *terms)` and `missing(kind)` writers in the framework, which every dialect's writers reuse.

13. **`takes` does not say which element of a list takes a grammar clause.** Met by mbse-expressions 0.16.0 (mbse-basis
    [grammar clauses by version](../../../../mbse-basis/proposals/GRAMMAR-CLAUSES.md), "Decided in stage 3", 4):
    `takes` gives each grammar clause taken with the indices of the elements that took it, which Python3's `Check`
    locates it at (`body[2].decorator_list[0]`, `body[1].names[0]`), finding nothing again itself.
14. **`grammar_clauses_spec` writes on the frame symbol `dialect`.** Met by mbse-expressions 0.16.0: the writer takes the
    owner's symbol, which each language's `define` passes.
15. **A version the data does not represent cannot be guessed without being stored.** Met by mbse-expressions 0.16.0
    (stage 3, 1): `edition_allows` and `edition_has` answer for an edition given by its designation and its revision,
    stored or not, from its neighbours' flagged entries, each language's oldest and newest editions flagged
    (`editions_spec`); the suites ask them of Python 3.16, TypeScript 5.10, C2y and C++26 (P3CHK-10, TS5CHK-11,
    CCHK-11, XCHK-11), and each `Check` asks a dialect that does not represent its target so. `check` still takes the
    editions its language covers.
16. **Python3 records the names `async` and `await` only where a variable refers to one.**
    `Expressions.Python.Python3`'s `variable.name 'async' or 'await'` (allowed by Python 3.0 to 3.6) is the one record
    of what Python 3.7 reserved among its terms, so a parameter, a keyword argument or an attribute named `async`
    (`def f(async)`, `f(async=1)`, `x.async`), which 3.7 refuses too, is not found; the language records the names its
    statements declare (`Programs.Python3.Standards`).
    - Proposed: grammar clauses of the same names on the helpers and kinds that hold a name (a parameter's, a keyword
      argument's, an attribute's).

## mbse-schemas

9. **Whether a transaction is open is no flag on the store**, as the user decided, a visitor's life being lexically
   scoped (mbse-basis [CAP-315](../../../../mbse-basis/docs/capabilities/CAP-315.md)): code is called within a
   transaction and reads the visitors it is given, or is given references or plain data and opens its own. So `Print`,
   `Definitions` and `Check` take a module's visitor within the caller's transaction (`print_file`, `define_file`,
   `check_file`, `validate_file`), or the store and a path and open their own, called with none open. Nothing is asked of
   mbse-schemas.
10. **No public way to extend an object reference by an owned entry.** No longer met here: as the whole tree is values
   ([Stage 3: the whole tree as values](../port/README.md#stage-3-the-whole-tree-as-values)), a statement has no object
   reference, and an anchor is its place in its module's value alone, which `Definitions` makes without mbse-schemas.
   As it stood: `Definitions` built a statement's reference
   from its module's and each parent entry's keys by writing the plain form by hand, guarded by P3DEF-07, which
   compared it with `References.of` for every statement of the conformance source.
   - Proposed: a reference of an entry's owned object given its owner's reference and its keys.
   - Since then, the user decided that a path is internal to an object reference and that no API takes or returns a
     bare path (mbse-basis [CAP-132](../../../../mbse-basis/docs/capabilities/CAP-132.md)), so the plain form
     `Definitions` writes is mbse-schemas' internal, and breaks if it changes: this is a dependency on internals until
     the proposed API exists.
11. **Executing a parse's transaction costs about 4.6 ms a statement** (the Python conformance source, 151 statements,
    about 0.7 s, written as one nested value; 6.5 ms as owned statements), nearly all of it in the transaction's
    execution, against 15 ms to read the source: fine for a file, slow for a suite that parses hundreds. Reported to the
    session that owns the store; no fix proposed here.

12. **A query's frame stream cannot be consumed within the transaction that makes it**, found by mbse-transforms
    ([its first-release proposal](https://github.com/pitaman71/mbse-transforms/blob/main/docs/proposals/first-release/README.md#gaps-found),
    Gaps found, 1). A query's result is a frame stream, and `Visitors.OfPattern` is a frame's own protocol, its symbols
    members, each the visitor of the object it binds; but `store.transaction` gives the stream back after its
    transaction ends, each frame holding object references, so a caller that needs the frames' objects resolves the
    references itself, through what CAP-132 makes internal (10, above, has the same root).
    - Proposed: a frame stream consumed within its transaction, each frame given as a `Visitors.OfPattern`; nothing then
      resolves a reference.

## When unparked

The user decides which to take, and in which order. Each lands in its own repository, additively, and the port picks it
up as a release; the printer, `Check` and `Definitions` then drop their workarounds, and the corpus regenerates where
printing changes (1 to 4).

---

<!-- nav -->
[← Porting to the stabilized mbse-schemas and mbse-expressions](../port/README.md) · [Home](../../../README.md)
