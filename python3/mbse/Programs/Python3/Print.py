"""Print: a Python 3 module, as the store holds it, printed as Python source text in one fixed layout.

A module is a `Programs.Python3.Module` that `Programs.Framework.TheWorkspace` owns by its path; it holds its tree as
one value, its `body`, each statement holding the statements of its blocks and its clauses as its properties (`body`,
`orelse`, `finalbody`, `handlers`, `cases`), printed in their order (`Statements`). The printer reads the tree and
writes nothing:

- `print_module(store, path)`: the text of the module at `path`, read within the transaction open on `store`, or,
  where none is, within one of its own; LookupError where the workspace holds no file at `path`.
- `print_file(module)`: the text of a module, given its visitor, within the transaction that made it.
- `print_statement(statement)`: the lines of one statement, its blocks' among them, joined by newlines without a
  final one, given its record (`Terms.kind_of`'s, of the union that holds it), within the transaction that read it.

The layout is the 0.3 printer's (`Python/_Printer.py`): four spaces a level, one statement a line; `elif` for an
`orelse` that is one `If`; as PEP 8 has it, two blank lines around top-level function and class definitions and one
around nested ones; comments directly before a definition kept with it, the blank lines going before them; a trailing
comment (`Comment.trailing`) on the line of what it follows, the first of a body on its header's line; decorators each
on a line of their own before the definition.

A statement's expressions are mbse-expressions' terms, written by the family's printer, `Python3.Text.ToText`, which
writes a `Python3`, a `Python Types` or a `Python Patterns` term, parenthesized only where precedence requires and a
parenthesis written in the tree (`parenthesized`) as written, a `case`'s open sequence bare. Where it stands as an
expression, `ToText` parenthesizes a named expression and a `yield`, and writes every tuple in parentheses; a
statement's place may take more, and there this printer writes it bare *(agent)*, as the 0.3 printer did:

- a tuple, unparenthesized: an expression statement's value, an assignment's targets and value (`=`, augmented and
  annotated), a `return`'s value, a `for`'s target and iterable and a `match`'s subject (`a, b = b, a`);
- a `yield` or a `yield from`: an expression statement's value and an assignment's value (`x = yield`);
- a named expression: the test of an `if`, an `elif` and a `while`, a `case`'s guard, a decorator and a `match`'s
  subject (`if (n := len(a)) > 10:` keeps its own, `if n := f():` needs none).

Decided by the agent where the port left it open, each *(agent)*:

- **A transaction the caller's or its own**, as the user decided that whether one is open is no flag on the store, a
  visitor's life being lexically scoped (mbse-basis CAP-315): `print_file` and `print_statement` read the visitors
  they are given, within the caller's transaction; `print_module`, given the store and a path, reads within one of its
  own, so it is called with none open, as transactions do not nest.
- **An `except` clause's tuple is parenthesized** (`except (A, B):`), which every Python 3 parses; Python 3.14's bare
  form is not written, since the tree, as `ast` has it, does not record which was written.
- **A clause's kind is its parent's**: an `except` clause is `except*` where its `try` is a `TryStar`; printed alone,
  a value that knows no parent, it is `except`.
- **A parameter's default** is written `x=1`, or `x: int = 1` where it has an annotation, as PEP 8 has it; a class
  without bases or keywords is written without parentheses (`class C:`); an alias is written as its name is stored,
  `*` among them.
- **A comment's `text`** is what follows its `#`, which the printer writes before it.
- **Every kind prints** (`KINDS`, each of `Statements.KINDS`: its statements and clauses, and the framework's `Error`);
  a statement of a kind not listed is refused, TypeError, rather than printed wrong.
- **Invalid syntax prints as written**, as the user decided that a parse keeps it (2026-11-17): an `Error`'s text, its
  first line at its level and the others as the source indented them *(agent)*, and nothing for its children, which
  its text holds already; an `error` or a `missing` term as `ToText` writes it, its text, and nothing. So a parsed
  invalid file prints back as tree-sitter's recovery allows: each `Error` and `error` exactly, the rest in this layout.
- **No validation**: the 0.3 printer validated a tree and checked it against a version before printing; this one
  prints what the store holds, validation being a check of its own, not yet ported.
- **Within an expression, `ToText`'s choices stand**: a `yield`'s tuple is parenthesized (`yield (1, 2)`, where 0.3
  wrote `yield 1, 2`), as `ToText` writes it; both parse to the same `ast`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.Framework import Objects, Terms
from mbse.Expressions.Python.Python3.Text import ToText

from ..Framework.Model import WORKSPACE
from .Statements import LANGUAGE

__all__ = ["print_module", "print_file", "print_statement", "KINDS"]

_INDENT = "    "
_DEFINITIONS = ("FunctionDef", "AsyncFunctionDef", "ClassDef")


# --- Reading ---

def _held(prop: Any) -> Any:
    """What a property holds, as `Objects.held` reads it (a scalar, a value object's or a term's visitor, or a
    container `Listed`); None where it is not set."""
    found: list[Any] = []
    prop.as_value(lambda a: found.append(Objects.held(a)) or a)
    return found[0] if found else None


def _many(prop: Any) -> list[Any]:
    """A container property's elements, in its order, as `Objects.held` reads it; none where it is not set."""
    held = _held(prop)
    return [] if held is None else list(held.values)


def _kind(node: Any) -> str:
    """A statement's kind: its schema's name, without its language's (`If`)."""
    return node.as_schema().name.rsplit(".", 1)[-1]


def _statements(node: Any, name: str) -> list[Any]:
    """The statements, clauses or errors a node's property holds (a module's or a statement's `body`, an `if`'s
    `orelse`, a `try`'s `handlers`), in order, each the record of its kind, as its union tags it."""
    return [Terms.kind_of(element)[1] for element in _many(getattr(node, name))]


# --- Expressions ---

def _text(term: Any) -> str:
    """A term as an expression writes it, `ToText`'s."""
    return ToText(term)


def _tag(term: Any) -> str:
    return Terms.kind_of(term)[0]


def _bare(term: Any, tuples: bool = False, yields: bool = False, named: bool = False) -> str:
    """A term where a statement's place takes, as well as an expression: a tuple without its parentheses, a `yield`
    or a named expression without its own, as `tuples`, `yields` and `named` allow."""
    tag = _tag(term)
    if tuples and tag == "tuple":
        elements = [_text(element) for element in Terms.arguments_of(Terms.kind_of(term)[1])]
        if elements:
            return f"{elements[0]}," if len(elements) == 1 else ", ".join(elements)
    if (yields and tag in ("yield", "yieldfrom")) or (named and tag == "namedexpr"):
        text = _text(term)
        return text[1:-1] if text.startswith("(") and text.endswith(")") else text  # ToText parenthesized it alone
    return _text(term)


def _value(node: Any, name: str = "value") -> str:
    """An assignment's or an expression statement's value: a tuple or a `yield` bare."""
    return _bare(_held(getattr(node, name)), tuples=True, yields=True)


def _optional(node: Any, name: str, before: str) -> str:
    """`before` and the term a property holds, or nothing where it holds none."""
    held = _held(getattr(node, name))
    return "" if held is None else f"{before}{_text(held)}"


def _parameter(arg: Any, prefix: str = "") -> str:
    """A parameter: `x`, `x=1`, `x: int` or `x: int = 1`, after its stars."""
    text = prefix + str(arg.arg.get())
    annotation, default = _held(arg.annotation), _held(arg.default_value)
    if annotation is not None:
        text += f": {_text(annotation)}"
    if default is not None:
        text += f" = {_text(default)}" if annotation is not None else f"={_text(default)}"
    return text


def _arguments(node: Any) -> str:
    """A function's parameters, `a, /, b, *c, d, **e`."""
    held = _held(node.args)
    if held is None:
        return ""
    posonly = [_parameter(arg) for arg in _many(held.posonlyargs)]
    parts = [*posonly, *(["/"] if posonly else []), *(_parameter(arg) for arg in _many(held.args))]
    vararg, kwonly = _held(held.vararg), _many(held.kwonlyargs)
    if vararg is not None:
        parts.append(_parameter(vararg, "*"))
    elif kwonly:
        parts.append("*")
    parts += [_parameter(arg) for arg in kwonly]
    kwarg = _held(held.kwarg)
    if kwarg is not None:
        parts.append(_parameter(kwarg, "**"))
    return ", ".join(parts)


def _type_params(node: Any) -> str:
    params = _many(node.type_params)
    return f"[{', '.join(_text(param) for param in params)}]" if params else ""


def _alias(alias: Any) -> str:
    asname = alias.asname.get()
    return str(alias.name.get()) + ("" if asname is None else f" as {asname}")


def _keyword(keyword: Any) -> str:
    arg = keyword.arg.get()
    value = _text(_held(keyword.value))
    return f"**{value}" if arg is None else f"{arg}={value}"


def _with_item(item: Any) -> str:
    return _text(_held(item.context_expr)) + _optional(item, "optional_vars", " as ")


# --- Statements ---

def _definition(node: Any) -> bool:
    return _kind(node) in _DEFINITIONS


def _comment(node: Any) -> bool:
    return _kind(node) == "Comment"


def _trailing(node: Any) -> bool:
    return _comment(node) and bool(node.trailing.get())


def _leads(statements: list[Any], i: int) -> bool:
    """Whether the comment `statements[i]` starts the comments directly before a definition."""
    j = i
    while j < len(statements) and _comment(statements[j]):
        j += 1
    return j < len(statements) and _definition(statements[j]) and (
        i == 0 or not _comment(statements[i - 1]) or _trailing(statements[i - 1]))


def _led(statements: list[Any], i: int) -> bool:
    """Whether `statements[i]` follows a comment that leads it: blank lines go before that comment."""
    return i > 0 and _comment(statements[i - 1]) and not _trailing(statements[i - 1])


def _block(statements: list[Any], level: int, top: bool = False) -> list[str]:
    """The lines of a list of statements at `level`, with blank lines around definitions: two at the top level, one
    elsewhere. Comments directly before a definition stay with it."""
    lines: list[str] = []
    blank = 2 if top else 1
    after_definition = False
    for i, statement in enumerate(statements):
        if _trailing(statement) and lines:
            lines[-1] += f"  #{statement.text.get()}"
            continue
        starts = (_definition(statement) and not _led(statements, i)) or (
            _comment(statement) and _leads(statements, i))
        if lines and (after_definition or starts):
            lines.extend([""] * blank)
        lines.extend(_statement(statement, level))
        after_definition = _definition(statement)
    return lines


def _suite(header: str, body: list[Any], level: int) -> list[str]:
    """`header:` and the indented body, a trailing comment first in it on the header's line."""
    lines = [_INDENT * level + header + ":"]
    if body and _trailing(body[0]):
        lines[0] += f"  #{body[0].text.get()}"
        body = body[1:]
    return lines + _block(body, level + 1)


def _error(node: Any, level: int) -> list[str]:
    """Invalid syntax where a statement stands, `Programs.Framework.Error`: its text as written, its first line at
    `level` and the others as the source indented them; nothing where it has none. Its `body`, recovered within it,
    are within its text, and are not printed again."""
    text = node.text.get() or ""
    return [_INDENT * level + line if i == 0 else line for i, line in enumerate(text.split("\n"))] if text else []


def _statement(node: Any, level: int) -> list[str]:
    kind = _kind(node)
    compound = _COMPOUND.get(kind)
    if compound is not None:
        return compound(node, level)
    simple = _SIMPLE.get(kind)
    if simple is None:
        raise TypeError(f"no printer for the statement kind {node.as_schema().name!r}")
    return [_INDENT * level + simple(node)]


def _assign(node: Any) -> str:
    targets = [_bare(target, tuples=True) for target in _many(node.targets)]
    return " = ".join([*targets, _value(node)])


def _ann_assign(node: Any) -> str:
    value = "" if _held(node.value) is None else f" = {_value(node)}"
    return f"{_text(_held(node.target))}: {_text(_held(node.annotation))}{value}"


def _return(node: Any) -> str:
    value = _held(node.value)
    return "return" if value is None else f"return {_bare(value, tuples=True)}"


def _import(node: Any) -> str:
    return ("lazy " if node.is_lazy.get() else "") + "import " + ", ".join(_alias(a) for a in _many(node.names))


def _import_from(node: Any) -> str:
    module = "." * (node.level.get() or 0) + (node.module.get() or "")
    names = ", ".join(_alias(a) for a in _many(node.names))
    return f"{'lazy ' if node.is_lazy.get() else ''}from {module} import {names}"


_SIMPLE: dict[str, Callable[[Any], str]] = {
    "Comment": lambda node: f"#{node.text.get()}",
    "Expr": _value,
    "Assign": _assign,
    "AugAssign": lambda node: f"{_bare(_held(node.target), tuples=True)} {node.op.get()}= {_value(node)}",
    "AnnAssign": _ann_assign,
    "Assert": lambda node: f"assert {_text(_held(node.test))}{_optional(node, 'msg', ', ')}",
    "Pass": lambda node: "pass",
    "Break": lambda node: "break",
    "Continue": lambda node: "continue",
    "Delete": lambda node: "del " + ", ".join(_text(target) for target in _many(node.targets)),
    "Return": _return,
    "Raise": lambda node: f"raise{_optional(node, 'exc', ' ')}{_optional(node, 'cause', ' from ')}",
    "Import": _import,
    "ImportFrom": _import_from,
    "Global": lambda node: "global " + ", ".join(_many(node.names)),
    "Nonlocal": lambda node: "nonlocal " + ", ".join(_many(node.names)),
    "TypeAlias": lambda node: f"type {_text(_held(node.name))}{_type_params(node)} = {_text(_held(node.value))}",
}


def _else(node: Any, level: int) -> list[str]:
    orelse = _statements(node, "orelse")
    return _suite("else", orelse, level) if orelse else []


def _orelse(orelse: list[Any], level: int) -> list[str]:
    """An `if`'s `else`: `elif` where it is one `If`."""
    if not orelse:
        return []
    if len(orelse) == 1 and _kind(orelse[0]) == "If":
        elif_ = orelse[0]
        return [*_suite(f"elif {_bare(_held(elif_.test), named=True)}", _statements(elif_, "body"), level),
                *_orelse(_statements(elif_, "orelse"), level)]
    return _suite("else", orelse, level)


def _if(node: Any, level: int) -> list[str]:
    return [*_suite(f"if {_bare(_held(node.test), named=True)}", _statements(node, "body"), level),
            *_orelse(_statements(node, "orelse"), level)]


def _while(node: Any, level: int) -> list[str]:
    return [*_suite(f"while {_bare(_held(node.test), named=True)}", _statements(node, "body"), level),
            *_else(node, level)]


def _for(node: Any, level: int) -> list[str]:
    keyword = "async for" if _kind(node) == "AsyncFor" else "for"
    target, iterable = _bare(_held(node.target), tuples=True), _bare(_held(node.iter), tuples=True)
    header = " ".join(part for part in (keyword, target, "in", iterable) if part)  # a missing target prints nothing
    return [*_suite(header, _statements(node, "body"), level), *_else(node, level)]


def _try(node: Any, level: int) -> list[str]:
    lines = _suite("try", _statements(node, "body"), level)
    for handler in _statements(node, "handlers"):
        lines += _handler(handler, level, star=_kind(node) == "TryStar") if _kind(handler) != "Error" else \
            _error(handler, level)
    lines += _else(node, level)
    finalbody = _statements(node, "finalbody")
    if finalbody:
        lines += _suite("finally", finalbody, level)
    return lines


def _handler(node: Any, level: int, star: bool) -> list[str]:
    """An `except` clause, `except*` where its `try` is a `TryStar`."""
    header = ("except*" if star else "except") + _optional(node, "type", " ")
    name = node.name.get()
    if name is not None:
        header += f" as {name}"
    return _suite(header, _statements(node, "body"), level)


def _with(node: Any, level: int) -> list[str]:
    keyword = "async with" if _kind(node) == "AsyncWith" else "with"
    items = ", ".join(_with_item(item) for item in _many(node.items))
    return _suite(f"{keyword} {items}", _statements(node, "body"), level)


def _match(node: Any, level: int) -> list[str]:
    lines = [f"{_INDENT * level}match {_bare(_held(node.subject), tuples=True, named=True)}:"]
    for case in _statements(node, "cases"):
        lines += _statement(case, level + 1)
    return lines


def _case(node: Any, level: int) -> list[str]:
    guard = _held(node.guard)
    header = f"case {_text(_held(node.pattern))}" + ("" if guard is None else f" if {_bare(guard, named=True)}")
    return _suite(header, _statements(node, "body"), level)


def _decorators(node: Any, level: int) -> list[str]:
    return [f"{_INDENT * level}@{_bare(d, named=True)}" for d in _many(node.decorator_list)]


def _function(node: Any, level: int) -> list[str]:
    keyword = "async def" if _kind(node) == "AsyncFunctionDef" else "def"
    header = f"{keyword} {node.name.get()}{_type_params(node)}({_arguments(node)}){_optional(node, 'returns', ' -> ')}"
    return [*_decorators(node, level), *_suite(header, _statements(node, "body"), level)]


def _class(node: Any, level: int) -> list[str]:
    arguments = [*(_text(base) for base in _many(node.bases)), *(_keyword(k) for k in _many(node.keywords))]
    header = f"class {node.name.get()}{_type_params(node)}" + (f"({', '.join(arguments)})" if arguments else "")
    return [*_decorators(node, level), *_suite(header, _statements(node, "body"), level)]


_COMPOUND: dict[str, Callable[[Any, int], list[str]]] = {
    "If": _if, "While": _while, "For": _for, "AsyncFor": _for, "Try": _try, "TryStar": _try,
    "ExceptHandler": lambda node, level: _handler(node, level, False), "With": _with, "AsyncWith": _with, "Match": _match, "MatchCase": _case,
    "FunctionDef": _function, "AsyncFunctionDef": _function, "ClassDef": _class, "Error": _error,
}

KINDS: tuple[str, ...] = (*_SIMPLE, *_COMPOUND)
"""The statement kinds the printer prints, by their names below `Programs.Python3`: every one of
`Statements.KINDS`, and the framework's `Error`."""


# --- Entry points ---

def print_statement(statement: Any) -> str:
    """A statement's lines, its blocks' among them, joined by newlines, without a final one: its record, read within
    the transaction that read it."""
    return "\n".join(_statement(statement, 0))


def print_file(module: Any) -> str:
    """A module's text, each line ending with a newline (none for an empty module): its visitor, a
    `Programs.Python3.Module`, read within the transaction that made it."""
    if module.as_schema().name != f"{LANGUAGE}.Module":
        raise TypeError(f"not a {LANGUAGE}.Module: {module.as_schema().name!r}")
    return "".join(line + "\n" for line in _block(_statements(module, "body"), 0, top=True))


def print_module(store: Any, path: str) -> str:
    """The text of the module the workspace holds at `path` (`print_file`), read within a transaction of its own, so
    called with none open on `store`; LookupError where it holds no file there."""
    with store.transaction():
        return print_file(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none
