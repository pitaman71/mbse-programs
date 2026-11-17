"""Model: the framework's schemas, which every language's syntax nodes are built on, independent of any language.

As the user decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)),
the whole tree is values: "the whole AST is value objects. It's lexically proportionate". A file is a reference object,
and holds its tree as one value, as a holder holds its root term; its statements, clauses and invalid syntax are value
objects nested within it, and expressions are mbse-expressions' terms, values too. `install` defines, in a store:

- `Programs.Framework.Workspace`, a reference object whose singleton is `Programs.Framework.TheWorkspace`, owning its
  files by path through `Programs.Framework.Contains(workspace, path, file)`;
- `Programs.Framework.File`, a file or translation unit, owned by its workspace: each language's file refines it, with
  the property that holds its tree (`body`);
- `Programs.Framework.Provenance`, where a file came from (its name, path, repository and hash), owned by its file
  through `Programs.Framework.HasProvenance(file, provenance)`, one at most;
- `Programs.Framework.Statement`, a statement, a value object which each language's statement kinds refine;
- `Programs.Framework.Clause`, a clause: a part of a statement that its language's grammar allows only within that
  statement and that holds statements (Python's `except` and `case`), a value object which each language's clause kinds
  refine; never a statement, as the user decided: "I don't much like treating a clause as a statement when it can only
  appear in that place";
- `Programs.Framework.Error`, invalid syntax where a statement or a clause stands: the statement-level counterpart of
  mbse-expressions' `error` term, as the user decided that every language's parser keeps what it cannot read, never
  raising for it. It holds the source it spans, as written (`text`); each language's error refines it, with the
  statements its parser recovered within it (`body`) *(agent: the framework cannot name a language's statements)*.

Each of `Statement`, `Clause` and `Error` has the line it begins on (`line`), 1-based, absent where it was built rather
than parsed. A node is found again by its place within its file's tree: nesting is ownership. Scopes are derived on
demand, as definitions are (`Definitions`), not stored.

Run it in a transaction of its own (`store.transaction(install)`); run again, it writes nothing. A language's install
runs after it.
"""

from typing import Any

WORKSPACE = "Programs.Framework.TheWorkspace"


def install(txn: Any) -> Any:
    """The framework's schemas, upserted: run in a transaction of its own; run again, it writes nothing."""
    S = txn.Schemas
    return txn.uid("mbse.Programs.Framework/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({
            "Workspace": S.OfObject, "Contains": S.OfRelation, "File": S.OfObject, "Provenance": S.OfObject,
            "HasProvenance": S.OfRelation, "Statement": S.OfObject, "Clause": S.OfObject, "Error": S.OfObject})
        .spec([
            lambda _: _.Workspace.name("Programs.Framework.Workspace").ref(True).singleton(WORKSPACE).adjacencies({
                "files": lambda a: a.relation([_.Contains]).me("workspace")}),
            lambda _: _.Contains.name("Programs.Framework.Contains").links([
                lambda t: t.name("workspace").schema([_.Workspace]), lambda t: t.name("file").schema([_.File])
            ]).properties({"path": S.OfStr}).uniques([["workspace", "path"], ["file"]]),
            lambda _: _.File.name("Programs.Framework.File").ref(True).adjacencies({
                "provenance": lambda a: a.relation([_.HasProvenance]).me("file")}).adjacencies([
                lambda a: a.name("workspace").relation([_.Contains]).me("file").owner(True)]),
            lambda _: _.Provenance.name("Programs.Framework.Provenance").ref(True).properties({
                "name": S.OfStr, "path": S.OfStr, "repository": S.OfStr, "hash": S.OfStr}).adjacencies([
                lambda a: a.name("file").relation([_.HasProvenance]).me("provenance").owner(True)]),
            lambda _: _.HasProvenance.name("Programs.Framework.HasProvenance").links([
                lambda t: t.name("file").schema([_.File]), lambda t: t.name("provenance").schema([_.Provenance])
            ]).uniques([["file"], ["provenance"]]),
            lambda _: _.Statement.name("Programs.Framework.Statement").properties({"line": S.OfInt}),
            lambda _: _.Clause.name("Programs.Framework.Clause").properties({"line": S.OfInt}),
            lambda _: _.Error.name("Programs.Framework.Error").properties({"line": S.OfInt, "text": S.OfStr}),
        ])]))])
