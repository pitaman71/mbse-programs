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
7. **A standard tags a kind, not a property or a value.** `HasStandard` links an object schema alone, so availability
   that depends on a property's value stays code in `Check` (`binop.op '@'` 3.5, `comprehension.is_async` 3.6,
   `formattedvalue.debug` and `arguments.posonlyargs` 3.8, an unpacked subscript index 3.11, a type parameter's default
   3.13, unpacked comprehensions 3.15; and, of mbse-programs' own, `Import.is_lazy` 3.15 and `type_params` 3.12).
   - Proposed: a way to tag a property, or a value of one, with the standards that have it
     ([CAP-268: standards as tagged data](../../../../mbse-basis/docs/capabilities/CAP-268.md)).

## mbse-schemas

8. **Whether a transaction is open is no flag on the store**, as the user decided, a visitor's life being lexically
   scoped (mbse-basis [CAP-315](../../../../mbse-basis/docs/capabilities/CAP-315.md)): code is called within a
   transaction and reads the visitors it is given, or is given references or plain data and opens its own. So `Print`,
   `Definitions` and `Check` take a module's visitor within the caller's transaction (`print_file`, `define_file`,
   `check_file`, `validate_file`), or the store and a path and open their own, called with none open. Nothing is asked of
   mbse-schemas.
9. **No public way to extend an object reference by an owned entry.** `Definitions` builds a statement's reference
   from its module's and each parent entry's keys by writing the plain form by hand, guarded by P3DEF-07, which
   compares it with `References.of` for every statement of the conformance source.
   - Proposed: a reference of an entry's owned object given its owner's reference and its keys.
   - Since then, the user decided that a path is internal to an object reference and that no API takes or returns a
     bare path (mbse-basis [CAP-132](../../../../mbse-basis/docs/capabilities/CAP-132.md)), so the plain form
     `Definitions` writes is mbse-schemas' internal, and breaks if it changes: this is a dependency on internals until
     the proposed API exists.
10. **Executing a parse's transaction costs about 6.5 ms a statement** (the Python conformance source, 151 statements,
    about 1.0 s), nearly all of it in the transaction's execution: fine for a file, slow for a suite that parses
    hundreds. Reported to the session that owns the store (2026-11-16); no fix proposed here.

## When unparked

The user decides which to take, and in which order. Each lands in its own repository, additively, and the port picks it
up as a release; the printer, `Check` and `Definitions` then drop their workarounds, and the corpus regenerates where
printing changes (1 to 4).

---

<!-- nav -->
[← Porting to the stabilized mbse-schemas and mbse-expressions](../port/README.md) · [Home](../../../README.md)
