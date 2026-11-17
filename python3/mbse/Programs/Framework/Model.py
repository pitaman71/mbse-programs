"""Model: the framework's schemas, which every language's syntax nodes are built on, independent of any language.

As the user decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#decided),
2026-11-02), a syntax node is a model; files, scopes and statements are owned reference objects; expressions are
mbse-expressions' terms, value objects held by the statements' properties (stage 2's design, Decided, 1). `install`
defines, in a store:

- `Programs.Framework.Workspace`, a reference object whose singleton is `Programs.Framework.TheWorkspace`, owning its
  files by path through `Programs.Framework.Contains(workspace, path, file)` (stage 2's design, Decided, 2);
- `Programs.Framework.File`, a file or translation unit, owned by its workspace, its statements its `body`;
- `Programs.Framework.Provenance`, where a file came from (its name, path, repository and hash), owned by its file
  through `Programs.Framework.HasProvenance(file, provenance)`, one at most;
- `Programs.Framework.Statement`, a statement, which each language's statement kinds refine, owned by its parent, a
  file or a statement, through `Programs.Framework.HasParent(child, parent)`, keyed by the parent's `property` that
  holds it and its `index` there: a node's object reference is its parent's, extended by that property and index;
- `Programs.Framework.Clause`, a clause: a part of a statement that its language's grammar allows only within that
  statement and that holds statements (Python's `except` and `case`), owned by its statement through `HasParent` as a
  statement is, keyed by the statement's property that holds it (`handlers`, `cases`) and its index there; never a
  statement, as the user decided (2026-11-16): "I don't much like treating a clause as a statement when it can only
  appear in that place";
- `Programs.Framework.Scope`, a scope, owned by the file, statement or clause that opens it through
  `Programs.Framework.Opens(opener, scope)`, one at most *(agent, for review)*; a statement in it through
  `Programs.Framework.HasScope(statement, scope)`;
- `Programs.Framework.HasLocation(located, file, line)`, where a statement, a clause or a scope begins: its file and
  line.

Run it in a transaction of its own (`store.transaction(install)`); run again, it writes nothing. A language's install
runs after it. Every object of a program is a singleton or owned, never counted, so that each is found again by its
object reference (mbse-basis [CAP-315: every read within a transaction or through a follow](mbse:mbse-basis/docs/capabilities/CAP-315.md#decided)).
"""

from typing import Any

WORKSPACE = "Programs.Framework.TheWorkspace"


def install(txn: Any) -> Any:
    """The framework's schemas, upserted: run in a transaction of its own; run again, it writes nothing."""
    S = txn.Schemas
    return txn.uid("mbse.Programs.Framework/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({
            "Workspace": S.OfObject, "Contains": S.OfRelation, "File": S.OfObject, "Provenance": S.OfObject,
            "HasProvenance": S.OfRelation, "Statement": S.OfObject, "HasParent": S.OfRelation, "Clause": S.OfObject, "Scope": S.OfObject,
            "Opens": S.OfRelation, "HasScope": S.OfRelation, "HasLocation": S.OfRelation})
        .spec([
            lambda _: _.Workspace.name("Programs.Framework.Workspace").ref(True).singleton(WORKSPACE).adjacencies({
                "files": lambda a: a.relation([_.Contains]).me("workspace")}),
            lambda _: _.Contains.name("Programs.Framework.Contains").links([
                lambda t: t.name("workspace").schema([_.Workspace]), lambda t: t.name("file").schema([_.File])
            ]).properties({"path": S.OfStr}).uniques([["workspace", "path"], ["file"]]),
            lambda _: _.File.name("Programs.Framework.File").ref(True).adjacencies({
                "provenance": lambda a: a.relation([_.HasProvenance]).me("file"),
                "body": lambda a: a.relation([_.HasParent]).me("parent"),
                "scope": lambda a: a.relation([_.Opens]).me("opener")}).adjacencies([
                lambda a: a.name("workspace").relation([_.Contains]).me("file").owner(True)]),
            lambda _: _.Provenance.name("Programs.Framework.Provenance").ref(True).properties({
                "name": S.OfStr, "path": S.OfStr, "repository": S.OfStr, "hash": S.OfStr}).adjacencies([
                lambda a: a.name("file").relation([_.HasProvenance]).me("provenance").owner(True)]),
            lambda _: _.HasProvenance.name("Programs.Framework.HasProvenance").links([
                lambda t: t.name("file").schema([_.File]), lambda t: t.name("provenance").schema([_.Provenance])
            ]).uniques([["file"], ["provenance"]]),
            lambda _: _.Statement.name("Programs.Framework.Statement").ref(True).adjacencies({
                "children": lambda a: a.relation([_.HasParent]).me("parent"),
                "scope": lambda a: a.relation([_.Opens]).me("opener"),
                "within": lambda a: a.relation([_.HasScope]).me("statement"),
                "location": lambda a: a.relation([_.HasLocation]).me("located")}).adjacencies([
                lambda a: a.name("parent").relation([_.HasParent]).me("child").owner(True)]),
            lambda _: _.Clause.name("Programs.Framework.Clause").ref(True).adjacencies({
                "children": lambda a: a.relation([_.HasParent]).me("parent"),
                "scope": lambda a: a.relation([_.Opens]).me("opener"),
                "location": lambda a: a.relation([_.HasLocation]).me("located")}).adjacencies([
                lambda a: a.name("parent").relation([_.HasParent]).me("child").owner(True)]),
            lambda _: _.HasParent.name("Programs.Framework.HasParent").links([
                lambda t: t.name("child").schema([_.Statement, _.Clause]),
                lambda t: t.name("parent").schema([_.Statement, _.Clause, _.File])
            ]).properties({"property": S.OfStr, "index": S.OfInt}).uniques([["parent", "property", "index"], ["child"]]),
            lambda _: _.Scope.name("Programs.Framework.Scope").ref(True).adjacencies({
                "statements": lambda a: a.relation([_.HasScope]).me("scope"),
                "location": lambda a: a.relation([_.HasLocation]).me("located")}).adjacencies([
                lambda a: a.name("opener").relation([_.Opens]).me("scope").owner(True)]),
            lambda _: _.Opens.name("Programs.Framework.Opens").links([
                lambda t: t.name("opener").schema([_.File, _.Statement, _.Clause]), lambda t: t.name("scope").schema([_.Scope])
            ]).uniques([["opener"], ["scope"]]),
            lambda _: _.HasScope.name("Programs.Framework.HasScope").links([
                lambda t: t.name("statement").schema([_.Statement]), lambda t: t.name("scope").schema([_.Scope])
            ]).uniques([["statement"]]),
            lambda _: _.HasLocation.name("Programs.Framework.HasLocation").links([
                lambda t: t.name("located").schema([_.Statement, _.Clause, _.Scope]), lambda t: t.name("file").schema([_.File])
            ]).properties({"line": S.OfInt}).uniques([["located"]]),
        ])]))])
