"""Parses Python source text into Python trees, delegating to tree-sitter-python.

tree-sitter-python builds a concrete syntax tree; `_Converter` rewrites it into Python kinds, one tree-sitter node
type at a time. tree-sitter-python 0.25 cannot parse three constructs of Python 3.13 and later. When the text does not
parse, a pre-pass (`_prepare`) rewrites them, keeping every other character where it was: it moves `lazy` after the
`import` or `from` it qualifies, and removes the `**` of a dict comprehension that unpacks and the defaults of type
parameters. The converter puts them back where they were.

Positions are counted in characters (code points), never bytes, so that every implementation reports the same line and
column.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tree_sitter_python
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from ..Framework.Syntax import walk
from . import Syntax as S

__all__ = ["parse"]

_PARSER = _TSParser(_Grammar(tree_sitter_python.language()))

_EXTRAS = {"comment", "line_continuation"}
_PYTHON2 = {"exec_statement"}
_CLAUSES = {"elif_clause", "else_clause", "except_clause", "finally_clause", "case_clause"}
# Python's binary operators, by precedence, the loosest first. tree-sitter-python 0.25 groups `^` and `&` as one level,
# so the converter regroups chains of binary operators by these.
_LEVELS = [("|",), ("^",), ("&",), ("<<", ">>"), ("+", "-"), ("*", "@", "/", "//", "%"), ("**",)]


# --- Source text ---


class _Source:
    """The text being parsed, as given and as tree-sitter parses it (`data`, which is `cleaned` in UTF-16), with
    conversions from tree-sitter's byte offsets to character offsets, and from character offsets to lines and
    columns. The cleaned text has the same characters as the text, but for those the pre-pass rewrote."""

    def __init__(self, text: str, cleaned: str | None = None):
        self.text = text
        self.data = (text if cleaned is None else cleaned).encode("utf-16-le")
        self._chars: list[int] | None = None
        if len(self.data) != 2 * len(text):  # a character beyond the Basic Multilingual Plane takes two units
            self._chars = [0] * (len(self.data) // 2 + 1)
            at = 0
            for i, ch in enumerate(text if cleaned is None else cleaned):
                for _ in range(len(ch.encode("utf-16-le")) // 2):
                    self._chars[at] = i
                    at += 1
            self._chars[at] = len(text)

    def offset(self, byte: int) -> int:
        return byte // 2 if self._chars is None else self._chars[byte // 2]

    def error(self, message: str, offset: int) -> ParseError:
        line = self.text.count("\n", 0, offset) + 1
        column = offset - (self.text.rfind("\n", 0, offset) + 1) + 1
        return ParseError(message, line, column)


# --- The pre-pass: what tree-sitter-python cannot parse ---


class _Prepared:
    """What the pre-pass rewrote, by the character offset where the construct starts: lazy imports, set
    comprehensions that are dict comprehensions that unpack, and type parameters' defaults (the offset and text of
    each default)."""

    def __init__(self) -> None:
        self.lazy: set[int] = set()
        self.unpacking: set[int] = set()
        self.defaults: dict[int, tuple[int, str]] = {}


def _tokens(source: _Source, root: _TS) -> list[tuple[int, int, str]]:
    """The tokens of a tree, as character spans and their text: each leaf, but each string whole, without comments."""
    out: list[tuple[int, int, str]] = []
    stack = [root]
    while stack:
        ts = stack.pop()
        if ts.type in _EXTRAS:
            continue
        if ts.child_count == 0 or ts.type == "string":
            start, end = source.offset(ts.start_byte), source.offset(ts.end_byte)
            out.append((start, end, source.text[start:end]))
            continue
        stack.extend(reversed(ts.children))
    return out


def _closing(tokens: list[tuple[int, int, str]], i: int) -> int:
    """The index of the bracket that closes the one at `tokens[i]`, or of the last token if none does."""
    depth = 0
    for j in range(i, len(tokens)):
        if tokens[j][2] in ("(", "[", "{"):
            depth += 1
        elif tokens[j][2] in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _prepare(text: str, root: _TS, source: _Source) -> tuple[str, _Prepared]:
    """The text with the constructs tree-sitter-python cannot parse rewritten, and what was rewritten."""
    found = _Prepared()
    chars = list(text)
    tokens = _tokens(source, root)

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            if chars[p] != "\n":
                chars[p] = " "

    for i, (start, end, word) in enumerate(tokens):
        following = tokens[i + 1][2] if i + 1 < len(tokens) else ""
        line_start = text.rfind("\n", 0, start) + 1
        if word == "lazy" and following in ("import", "from") and not text[line_start:start].strip():
            # `lazy import` becomes `import    `, which keeps the statement where it starts
            after = tokens[i + 1]
            chars[start:after[1]] = list(following.ljust(after[1] - start))
            found.lazy.add(start)
        elif word == "{" and following == "**":
            close = _closing(tokens, i)
            depth, comprehension = 0, False
            for _, _, inner in tokens[i + 1:close]:
                depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(inner, 0)
                if depth == 0 and inner == ":":
                    break
                comprehension = comprehension or (depth == 0 and inner == "for")
            else:
                if comprehension:
                    blank(tokens[i + 1][0], tokens[i + 1][1])
                    found.unpacking.add(start)
        elif word == "[" and i >= 2 and tokens[i - 2][2] in ("def", "class", "type"):
            close = _closing(tokens, i)
            depth, parameter, equals = 0, None, None
            for j in range(i + 1, close + 1):
                s, e, inner = tokens[j]
                if depth == 0 and inner in (",", "]") and j <= close:
                    if equals is not None and equals + 1 < j:
                        found.defaults[parameter] = (tokens[equals + 1][0], text[tokens[equals + 1][0]:s])
                        blank(tokens[equals][0], s)
                    parameter, equals = None, None
                    continue
                if parameter is None:
                    parameter = s
                if depth == 0 and inner == "=":
                    equals = j
                depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(inner, 0)
    return "".join(chars), found


# --- The converter ---


class _Converter:
    """Rewrites a tree-sitter-python tree into Python nodes, recording where each node starts in `positions`.
    `shift` and `origin` place a tree parsed from a part of the text: its offsets are `shift` past those of the part,
    and its errors are located in `origin`."""

    def __init__(self, source: _Source, prepared: _Prepared, shift: int = 0, origin: _Source | None = None):
        self.source, self.pre, self.shift, self.origin = source, prepared, shift, origin or source
        self.positions: dict[int, int] = {}
        self.placed: list[Any] = []  # the nodes placed, kept alive so that no other node takes their `id`

    # Helpers

    def at(self, ts: _TS) -> int:
        return self.shift + self.source.offset(ts.start_byte)

    def text(self, ts: _TS) -> str:
        return self.source.data[ts.start_byte:ts.end_byte].decode("utf-16-le")

    def between(self, start: int, end: int) -> str:
        """The text between two byte offsets."""
        return self.source.data[start:end].decode("utf-16-le")

    def error(self, ts: _TS, message: str) -> ParseError:
        return self.origin.error(message, self.at(ts))

    def unsupported(self, ts: _TS) -> ParseError:
        return self.error(ts, f"unsupported syntax: {ts.type}")

    def made(self, ts: _TS, node: Any) -> Any:
        if id(node) not in self.positions:
            self.positions[id(node)] = self.at(ts)
            self.placed.append(node)
        return node

    @staticmethod
    def kids(ts: _TS) -> list[_TS]:
        """The children of `ts`, without comments and line continuations."""
        return [c for c in ts.children if c.type not in _EXTRAS]

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        return [c for c in ts.children if c.is_named and c.type not in _EXTRAS]

    @staticmethod
    def field(ts: _TS, name: str) -> _TS | None:
        return ts.child_by_field_name(name)

    @staticmethod
    def fields(ts: _TS, name: str) -> list[_TS]:
        return [c for i, c in enumerate(ts.children) if ts.field_name_for_child(i) == name]

    @staticmethod
    def has(ts: _TS, token: str) -> bool:
        return any(not c.is_named and c.type == token for c in ts.children)

    @staticmethod
    def require(ts: _TS, name: str) -> _TS:
        """A field the grammar requires, which tree-sitter always writes: it reports a missing one as an error."""
        return ts.child_by_field_name(name)  # type: ignore[return-value]

    def identifier(self, ts: _TS) -> S.Identifier:
        return self.made(ts, S.Identifier(spelling=self.text(ts)))

    def name(self, ts: _TS) -> S.Name:
        return self.made(ts, S.Name(id=self.identifier(ts)))

    # Errors

    def check(self, ts: _TS) -> None:
        """Raises for the first syntax error in `ts`, in source order, and for Python 2's statements."""
        stack = [ts]
        while stack:
            node = stack.pop()
            if node.type == "ERROR":
                raise self.error(node, "syntax error")
            if node.is_missing:
                raise self.error(node, f"expected {node.type}")
            if node.type in _PYTHON2:
                raise self.error(node, f"unsupported syntax: {node.type}, which is Python 2")
            stack.extend(reversed(node.children))

    # Statements

    def module(self, ts: _TS) -> S.Module:
        self.check(ts)
        return self.made(ts, S.Module(body=self.statements(ts.children)))

    def statements(self, nodes: list[_TS], header: _TS | None = None) -> list[S.Statement]:
        """The statements and comments among `nodes`. A comment is trailing on the line where the node before it
        ends; for the first, that is `header`, the clause whose block the statements are."""
        out: list[S.Statement] = []
        previous = header
        for ts in nodes:
            if ts.type == "comment":
                comment = self.made(ts, S.Comment(text=self.text(ts)[1:].rstrip("\r")))
                comment.trailing = previous is not None and previous.end_point[0] == ts.start_point[0]
                out.append(comment)
            elif ts.is_named and ts.type != "line_continuation":
                out.append(self.statement(ts))
            else:
                continue
            previous = ts
        return out

    def block(self, ts: _TS, clause: _TS) -> list[S.Statement]:
        """The statements of the block `ts` of `clause`, with the comments tree-sitter lists beside the block: in the
        clause between its header and the block, and after the block until the next clause."""
        header = max((c for c in clause.children if c.type == ":" and c.start_byte < ts.start_byte),
                     key=lambda c: c.start_byte)
        before = [c for c in clause.children
                  if c.type == "comment" and header.start_byte < c.start_byte < ts.start_byte]
        after = self.after(ts)
        if clause.type in _CLAUSES:
            after += self.after(clause)
        return self.statements([*before, *ts.children, *after], header)

    @staticmethod
    def after(ts: _TS) -> list[_TS]:
        """The comments that follow `ts` among its siblings, up to the next sibling that is not one."""
        out: list[_TS] = []
        sibling = ts.next_sibling
        while sibling is not None and sibling.type == "comment":
            out.append(sibling)
            sibling = sibling.next_sibling
        return out

    def statement(self, ts: _TS) -> S.Statement:
        return self.made(ts, self.STATEMENTS[ts.type](self, ts))  # check() has raised for any other

    def expression_statement(self, ts: _TS) -> S.Statement:
        kids = self.named(ts)
        if len(kids) > 1 or self.has(ts, ","):
            return S.Expr(value=self.made(ts, S.Tuple(elts=[self.expression(k) for k in kids])))
        ts = kids[0]
        if ts.type == "assignment":
            annotation = self.field(ts, "type")
            right = self.field(ts, "right")
            if annotation is not None:
                return S.AnnAssign(target=self.target(self.require(ts, "left")), annotation=self.type(annotation),
                                   value=None if right is None else self.expression(right))
            targets = [self.target(self.require(ts, "left"))]
            while right.type == "assignment":  # type: ignore[union-attr]
                targets.append(self.target(self.require(right, "left")))  # type: ignore[arg-type]
                right = self.require(right, "right")  # type: ignore[arg-type]
            return S.Assign(targets=targets, value=self.expression(right))  # type: ignore[arg-type]
        if ts.type == "augmented_assignment":
            return S.AugAssign(target=self.target(self.require(ts, "left")),
                               op=self.text(self.require(ts, "operator"))[:-1],
                               value=self.expression(self.require(ts, "right")))
        return S.Expr(value=self.expression(ts))

    def return_statement(self, ts: _TS) -> S.Return:
        kids = self.named(ts)
        return S.Return(value=self.expression(kids[0]) if kids else None)

    def delete_statement(self, ts: _TS) -> S.Delete:
        target = self.named(ts)[0]
        targets = self.named(target) if target.type == "expression_list" else [target]
        return S.Delete(targets=[self.target(t) for t in targets])

    def raise_statement(self, ts: _TS) -> S.Raise:
        cause = self.field(ts, "cause")
        kids = [k for k in self.named(ts) if cause is None or k.id != cause.id]
        return S.Raise(exc=self.expression(kids[0]) if kids else None,
                       cause=None if cause is None else self.expression(cause))

    def assert_statement(self, ts: _TS) -> S.Assert:
        kids = self.named(ts)
        return S.Assert(test=self.expression(kids[0]), msg=self.expression(kids[1]) if len(kids) > 1 else None)

    def global_statement(self, ts: _TS) -> S.Global:
        return S.Global(names=[self.identifier(k) for k in self.named(ts)])

    def nonlocal_statement(self, ts: _TS) -> S.Nonlocal:
        return S.Nonlocal(names=[self.identifier(k) for k in self.named(ts)])

    def dotted(self, ts: _TS) -> S.DottedName:
        return self.made(ts, S.DottedName(names=[self.identifier(k) for k in self.named(ts)]))

    def alias(self, ts: _TS) -> S.Alias:
        if ts.type == "aliased_import":
            return self.made(ts, S.Alias(name=self.dotted(self.require(ts, "name")),
                                         asname=self.identifier(self.require(ts, "alias"))))
        return self.made(ts, S.Alias(name=self.dotted(ts)))

    def import_statement(self, ts: _TS) -> S.Import:
        return S.Import(is_lazy=self.at(ts) in self.pre.lazy, names=[self.alias(n) for n in self.fields(ts, "name")])

    def import_from_statement(self, ts: _TS) -> S.ImportFrom:
        made = S.ImportFrom(is_lazy=self.at(ts) in self.pre.lazy)
        module = self.require(ts, "module_name")
        if module.type == "relative_import":
            made.level = self.text(self.named(module)[0]).count(".")
            names = self.named(module)[1:]
            made.module = self.dotted(names[0]) if names else None
        else:
            made.module = self.dotted(module)
        wildcard = [c for c in ts.children if c.type == "wildcard_import"]
        made.names = [self.made(wildcard[0], S.Alias())] if wildcard else [
            self.alias(n) for n in self.fields(ts, "name")]
        return made

    def future_import_statement(self, ts: _TS) -> S.ImportFrom:
        future = next(c for c in ts.children if c.type == "__future__")
        module = self.made(future, S.DottedName(names=[self.made(future, S.Identifier(spelling="__future__"))]))
        return S.ImportFrom(module=module, names=[self.alias(n) for n in self.fields(ts, "name")])

    def type_alias_statement(self, ts: _TS) -> S.Statement:
        left = self.named(self.require(ts, "left"))[0]
        if left.type not in ("identifier", "generic_type"):
            return self.reread(ts)
        made = S.TypeAlias(value=self.type(self.require(ts, "right")))
        if left.type == "generic_type":
            name, parameters = self.named(left)
            made.name, made.type_params = self.name(name), self.type_parameters(parameters)
        else:
            made.name = self.name(left)
        return made

    def reread(self, ts: _TS) -> S.Statement:
        """An assignment to an expression that starts with the name `type`, as `type(t).name = value`, which
        tree-sitter-python reads as a type alias: it is parsed again with `Type` for `type`, which is then put back."""
        source = _Source("Type" + self.text(ts)[4:])
        tree = _PARSER.parse(source.data, encoding="utf16le")
        converter = _Converter(source, _Prepared(), self.at(ts), self.origin)
        converter.check(tree.root_node)
        statement = converter.statement(converter.named(tree.root_node)[0])
        next(n for n in walk(statement) if isinstance(n, S.Identifier)).spelling = "type"
        self.positions.update(converter.positions)
        self.placed += converter.placed
        return statement

    def print_statement(self, ts: _TS) -> S.Expr:
        """`print >> file, value`, which is Python 3 too: a tuple of a shift and the values. tree-sitter-python
        reads it as Python 2's print statement, which without `>>` is not Python 3."""
        chevron = next((c for c in ts.children if c.type == "chevron"), None)
        if chevron is None:
            raise self.error(ts, "unsupported syntax: print_statement, which is Python 2")
        keyword = ts.children[0]
        shift = self.made(keyword, S.BinOp(left=self.made(keyword, S.Name(id=self.made(keyword, S.Identifier(
            spelling="print")))), op=">>", right=self.expression(self.named(chevron)[0])))
        values = [self.expression(a) for a in self.fields(ts, "argument")]
        return S.Expr(value=self.made(ts, S.Tuple(elts=[shift, *values])) if values else shift)

    def simple(kind: type) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        return lambda self, ts: kind()

    # Compound statements

    def if_statement(self, ts: _TS) -> S.If:
        made = S.If(test=self.expression(self.require(ts, "condition")),
                    body=self.block(self.require(ts, "consequence"), ts))
        last = made
        for clause in self.fields(ts, "alternative"):
            if clause.type == "elif_clause":
                elif_ = self.made(clause, S.If(test=self.expression(self.require(clause, "condition")),
                                               body=self.block(self.require(clause, "consequence"), clause)))
                last.orelse = [elif_]
                last = elif_
            else:
                last.orelse = self.block(self.require(clause, "body"), clause)
        return made

    def orelse(self, ts: _TS) -> list[S.Statement]:
        clause = self.field(ts, "alternative")
        return [] if clause is None else self.block(self.require(clause, "body"), clause)

    def while_statement(self, ts: _TS) -> S.While:
        return S.While(test=self.expression(self.require(ts, "condition")),
                       body=self.block(self.require(ts, "body"), ts), orelse=self.orelse(ts))

    def for_statement(self, ts: _TS) -> S.For | S.AsyncFor:
        kind = S.AsyncFor if self.has(ts, "async") else S.For
        return kind(target=self.target(self.require(ts, "left")), iter=self.expression(self.require(ts, "right")),
                    body=self.block(self.require(ts, "body"), ts), orelse=self.orelse(ts))

    def try_statement(self, ts: _TS) -> S.Try | S.TryStar:
        handlers, orelse, finalbody, star = [], [], [], False
        for clause in self.named(ts)[1:]:
            if clause.type == "except_clause":
                star = star or self.has(clause, "*")
                handlers.append(self.handler(clause))
            elif clause.type == "else_clause":
                orelse = self.block(self.require(clause, "body"), clause)
            else:
                finalbody = self.block(self.named(clause)[0], clause)
        kind = S.TryStar if star else S.Try
        return kind(body=self.block(self.require(ts, "body"), ts), handlers=handlers, orelse=orelse,
                    finalbody=finalbody)

    def handler(self, ts: _TS) -> S.ExceptHandler:
        made = self.made(ts, S.ExceptHandler(body=self.block(self.named(ts)[-1], ts)))
        values = self.fields(ts, "value")
        if len(values) == 1 and values[0].type == "as_pattern":
            made.name = self.identifier(self.named(self.require(values[0], "alias"))[0])
            values = [self.named(values[0])[0]]
        if len(values) > 1:
            made.type = self.made(values[0], S.Tuple(elts=[self.expression(v) for v in values]))
        elif values:
            made.type = self.expression(values[0])
        return made

    def with_statement(self, ts: _TS) -> S.With | S.AsyncWith:
        items = []
        for item in self.named(self.named(ts)[0]):
            value = self.require(item, "value")
            if value.type == "parenthesized_expression" and self.named(value)[0].type == "as_pattern":
                value = self.named(value)[0]  # `with (manager() as target):`, one item in parentheses
            if value.type == "as_pattern":
                target = self.named(self.require(value, "alias"))[0]
                made = S.WithItem(context_expr=self.expression(self.named(value)[0]), optional_vars=self.target(target))
            else:
                made = S.WithItem(context_expr=self.expression(value))
            items.append(self.made(item, made))
        kind = S.AsyncWith if self.has(ts, "async") else S.With
        return kind(items=items, body=self.block(self.require(ts, "body"), ts))

    def match_statement(self, ts: _TS) -> S.Match:
        subjects = self.fields(ts, "subject")
        subject = self.made(subjects[0], S.Tuple(elts=[self.expression(s) for s in subjects])) \
            if len(subjects) > 1 or self.has(ts, ",") else self.expression(subjects[0])
        body = self.require(ts, "body")
        cases = []
        for clause in self.fields(body, "alternative"):
            patterns = [c for c in self.named(clause) if c.type == "case_pattern"]
            pattern = self.made(clause, S.MatchSequence(patterns=[self.pattern(p) for p in patterns])) \
                if len(patterns) > 1 or self.has(clause, ",") else self.pattern(patterns[0])
            guard = self.field(clause, "guard")
            cases.append(self.made(clause, S.MatchCase(
                pattern=pattern, guard=None if guard is None else self.expression(self.named(guard)[0]),
                body=self.block(self.require(clause, "consequence"), clause))))
        return S.Match(subject=subject, cases=cases)

    def function_definition(self, ts: _TS) -> S.FunctionDef | S.AsyncFunctionDef:
        kind = S.AsyncFunctionDef if self.has(ts, "async") else S.FunctionDef
        parameters = self.field(ts, "type_parameters")
        returns = self.field(ts, "return_type")
        return kind(name=self.identifier(self.require(ts, "name")),
                    type_params=[] if parameters is None else self.type_parameters(parameters),
                    args=self.arguments(self.require(ts, "parameters")),
                    returns=None if returns is None else self.type(returns),
                    body=self.block(self.require(ts, "body"), ts))

    def class_definition(self, ts: _TS) -> S.ClassDef:
        parameters = self.field(ts, "type_parameters")
        made = S.ClassDef(name=self.identifier(self.require(ts, "name")),
                          type_params=[] if parameters is None else self.type_parameters(parameters),
                          body=self.block(self.require(ts, "body"), ts))
        superclasses = self.field(ts, "superclasses")
        if superclasses is not None:
            made.bases, made.keywords = self.call_arguments(superclasses)
        return made

    def decorated_definition(self, ts: _TS) -> S.Statement:
        made = self.statement(self.require(ts, "definition"))
        made.decorator_list = [self.expression(self.named(d)[0]) for d in self.named(ts) if d.type == "decorator"]
        return made

    STATEMENTS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "expression_statement": expression_statement, "return_statement": return_statement,
        "delete_statement": delete_statement, "raise_statement": raise_statement,
        "assert_statement": assert_statement, "pass_statement": simple(S.Pass),
        "break_statement": simple(S.Break), "continue_statement": simple(S.Continue),
        "global_statement": global_statement, "nonlocal_statement": nonlocal_statement,
        "import_statement": import_statement, "import_from_statement": import_from_statement,
        "future_import_statement": future_import_statement, "type_alias_statement": type_alias_statement,
        "print_statement": print_statement,
        "if_statement": if_statement, "while_statement": while_statement, "for_statement": for_statement,
        "try_statement": try_statement, "with_statement": with_statement, "match_statement": match_statement,
        "function_definition": function_definition, "class_definition": class_definition,
        "decorated_definition": decorated_definition,
    }

    # Parameters

    def arguments(self, ts: _TS) -> S.Arguments:
        """A function's or lambda's parameter list."""
        made = self.made(ts, S.Arguments())
        keyword_only = False
        for p in self.named(ts):
            if p.type == "positional_separator":
                made.posonlyargs, made.args = made.args, []
            elif p.type == "keyword_separator":
                keyword_only = True
            elif p.type in ("list_splat_pattern", "dictionary_splat_pattern") or (
                    p.type == "typed_parameter" and self.named(p)[0].type != "identifier"):
                splat = p if p.type != "typed_parameter" else self.named(p)[0]
                annotation = self.field(p, "type")
                arg = self.made(p, S.Arg(arg=self.identifier(self.named(splat)[0]),
                                         annotation=None if annotation is None else self.type(annotation)))
                if splat.type == "list_splat_pattern":
                    made.vararg, keyword_only = arg, True
                else:
                    made.kwarg = arg
            else:
                (made.kwonlyargs if keyword_only else made.args).append(self.parameter(p))
        return made

    def parameter(self, ts: _TS) -> S.Arg:
        if ts.type == "identifier":
            return self.made(ts, S.Arg(arg=self.identifier(ts)))
        if ts.type == "typed_parameter":
            return self.made(ts, S.Arg(arg=self.identifier(self.named(ts)[0]),
                                       annotation=self.type(self.require(ts, "type"))))
        if ts.type not in ("default_parameter", "typed_default_parameter"):
            raise self.unsupported(ts)
        name = self.require(ts, "name")
        if name.type != "identifier":
            raise self.unsupported(name)
        annotation = self.field(ts, "type")
        return self.made(ts, S.Arg(arg=self.identifier(name),
                                   annotation=None if annotation is None else self.type(annotation),
                                   default_value=self.expression(self.require(ts, "value"))))

    def type_parameters(self, ts: _TS) -> list[S.TypeParameter]:
        out: list[S.TypeParameter] = []
        for t in self.named(ts):
            inner = self.named(t)[0]
            if inner.type == "constrained_type":
                name, bound = self.named(inner)
                made: Any = S.TypeVar(name=self.identifier(self.named(name)[0]), bound=self.type(bound))
            elif inner.type == "splat_type":
                kind = S.ParamSpec if self.has(inner, "**") else S.TypeVarTuple
                made = kind(name=self.identifier(self.named(inner)[0]))
            elif inner.type == "identifier":
                made = S.TypeVar(name=self.identifier(inner))
            else:
                raise self.unsupported(inner)
            default = self.pre.defaults.get(self.at(t))
            if default is not None:
                made.default_value = self.part(*default)
            out.append(self.made(t, made))
        return out

    def part(self, offset: int, text: str) -> S.Expression:
        """The expression `text`, at `offset` of the text, which the pre-pass removed."""
        source = _Source(f"({text})")
        tree = _PARSER.parse(source.data, encoding="utf16le")
        converter = _Converter(source, _Prepared(), offset - 1, self.origin)
        converter.check(tree.root_node)
        statement = converter.named(tree.root_node)[0]
        value = converter.expression(converter.named(converter.named(statement)[0])[0])
        self.positions.update(converter.positions)
        self.placed += converter.placed
        return value

    # Annotations: tree-sitter-python's type grammar

    def type(self, ts: _TS) -> S.Expression:
        """An annotation, or the value of a type alias: tree-sitter's `type`, which holds an expression or a
        construct of its type grammar."""
        inner = self.named(ts)[0] if ts.type == "type" else ts
        if inner.type == "generic_type":
            name, parameters = self.named(inner)
            elts = [self.type(t) for t in self.named(parameters)]
            index = elts[0] if len(elts) == 1 else self.made(parameters, S.Tuple(elts=elts))
            return self.made(inner, S.Subscript(value=self.expression(name), slice=index))
        if inner.type == "union_type":
            # `a | b | c` groups to the left, which tree-sitter-python's type grammar writes to the right
            members: list[_TS] = []

            def flatten(node: _TS) -> None:
                node = self.named(node)[0] if node.type == "type" else node
                if node.type == "union_type" or (
                        node.type == "binary_operator" and self.text(self.require(node, "operator")) == "|"):
                    for member in self.named(node) if node.type == "union_type" else (
                            self.require(node, "left"), self.require(node, "right")):
                        flatten(member)
                else:
                    members.append(node)

            flatten(inner)
            union = self.type(members[0])
            for member in members[1:]:
                union = self.made(members[0], S.BinOp(left=union, op="|", right=self.type(member)))
            return union
        if inner.type == "splat_type":
            return self.made(inner, S.Starred(value=self.name(self.named(inner)[0])))
        return self.expression(inner)

    # Assignment targets: tree-sitter-python's patterns

    def target(self, ts: _TS) -> S.Expression:
        if ts.type == "pattern_list":
            return self.made(ts, S.Tuple(elts=[self.target(k) for k in self.named(ts)]))
        if ts.type == "tuple_pattern":
            elts = [self.target(k) for k in self.named(ts)]
            if not elts:
                return self.made(ts, S.Tuple())
            if self.has(ts, ","):
                return self.made(ts, S.Parenthesized(value=self.made(ts, S.Tuple(elts=elts))))
            return self.made(ts, S.Parenthesized(value=elts[0]))
        if ts.type == "list_pattern":
            return self.made(ts, S.List(elts=[self.target(k) for k in self.named(ts)]))
        if ts.type == "list_splat_pattern":
            return self.made(ts, S.Starred(value=self.target(self.named(ts)[0])))
        return self.expression(ts)

    # Expressions

    def expression(self, ts: _TS) -> S.Expression:
        method = self.EXPRESSIONS.get(ts.type)
        if method is None:
            raise self.unsupported(ts)
        return self.made(ts, method(self, ts))

    def constant(self, ts: _TS) -> S.Constant:
        return S.Constant(spelling=self.text(ts))

    def string(self, ts: _TS) -> S.Expression:
        start = self.named(ts)[0]
        quote_at = next(i for i, ch in enumerate(self.text(start)) if ch in "'\"")
        prefix, quote = self.text(start)[:quote_at], self.text(start)[quote_at:]
        if not any(ch in prefix for ch in "fFtT"):
            return S.Constant(spelling=self.text(ts))
        kind = S.TemplateStr if any(ch in prefix for ch in "tT") else S.JoinedStr
        fields = [c for c in self.named(ts) if c.type == "interpolation"]
        # the text ends at the closing quote: tree-sitter-python counts the backslashes before it in a raw string as
        # part of its end, as in `fr'\\'`
        end = ts.end_byte - 2 * len(quote)
        return kind(prefix=prefix, quote=quote, values=self.pieces(start.end_byte, end, fields, kind))

    def pieces(self, start: int, end: int, fields: list[_TS], kind: type) -> list[Any]:
        """The text and replacement fields between two byte offsets of an f-string, t-string or format spec."""
        out: list[Any] = []
        at = start
        for field in fields:
            if field.start_byte > at:
                out.append(self.made_at(at, S.StringText(spelling=self.between(at, field.start_byte))))
            out.append(self.replacement(field, kind))
            at = field.end_byte
        if end > at:
            out.append(self.made_at(at, S.StringText(spelling=self.between(at, end))))
        return out

    def made_at(self, byte: int, node: Any) -> Any:
        """A new node, placed at `byte`."""
        self.positions[id(node)] = self.shift + self.source.offset(byte)
        self.placed.append(node)
        return node

    def replacement(self, ts: _TS, kind: type) -> S.FormattedValue | S.Interpolation:
        """A replacement field: an interpolation of a t-string, or else a formatted value."""
        made = (S.Interpolation if kind is S.TemplateStr else S.FormattedValue)()
        expression = self.require(ts, "expression")
        conversion = self.field(ts, "type_conversion")
        spec = self.field(ts, "format_specifier")
        closing = ts.children[-1]
        end = (conversion or spec or closing).start_byte
        made.debug = self.has(ts, "=")
        if expression.type == "named_expression" and spec is None:
            # `{x:=10}` formats `x` with the spec `=10`, which tree-sitter-python reads as an assignment expression
            name = self.require(expression, "name")
            made.text = self.between(ts.children[0].end_byte, name.end_byte)
            made.value = self.name(name)
            colon = next(c for c in expression.children if c.type == ":=")
            made.format_spec = self.made(colon, S.FormatSpec(values=[self.made_at(colon.start_byte + 2, S.StringText(
                spelling=self.between(colon.start_byte + 2, closing.start_byte)))]))
            return self.made(ts, made)
        made.text = self.between(ts.children[0].end_byte, end)
        made.value = self.expression(expression)
        if conversion is not None:
            made.conversion = self.text(conversion)[1:]
        if spec is not None:
            fields = [c for c in self.named(spec) if c.type == "format_expression"]
            colon = spec.children[0]
            made.format_spec = self.made(spec, S.FormatSpec(values=self.pieces(colon.end_byte, spec.end_byte, fields,
                                                                                S.JoinedStr)))
        return self.made(ts, made)

    def concatenated_string(self, ts: _TS) -> S.ConcatenatedString:
        return S.ConcatenatedString(values=[self.expression(k) for k in self.named(ts)])

    def parenthesized_expression(self, ts: _TS) -> S.Parenthesized:
        return S.Parenthesized(value=self.expression(self.named(ts)[0]))

    def tuple(self, ts: _TS) -> S.Expression:
        elts = [self.expression(k) for k in self.named(ts)]
        if not elts:
            return S.Tuple()
        return S.Parenthesized(value=self.made(ts, S.Tuple(elts=elts)))

    def expression_list(self, ts: _TS) -> S.Tuple:
        return S.Tuple(elts=[self.expression(k) for k in self.named(ts)])

    def list_(self, ts: _TS) -> S.List:
        return S.List(elts=[self.expression(k) for k in self.named(ts)])

    def set_(self, ts: _TS) -> S.Set:
        return S.Set(elts=[self.expression(k) for k in self.named(ts)])

    def dictionary(self, ts: _TS) -> S.Dict:
        items = []
        for k in self.named(ts):
            if k.type == "pair":
                items.append(self.made(k, S.DictItem(key=self.expression(self.require(k, "key")),
                                                     value=self.expression(self.require(k, "value")))))
            else:
                items.append(self.made(k, S.DictItem(value=self.expression(self.named(k)[0]))))
        return S.Dict(items=items)

    def generators(self, ts: _TS) -> list[S.Comprehension]:
        out: list[S.Comprehension] = []
        for clause in self.named(ts)[1:]:
            if clause.type == "for_in_clause":
                right = [k for k in self.fields(clause, "right") if k.is_named]
                iter_ = self.expression(right[0]) if len(right) == 1 else self.made(
                    right[0], S.Tuple(elts=[self.expression(r) for r in right]))
                out.append(self.made(clause, S.Comprehension(
                    is_async=self.has(clause, "async"), target=self.target(self.require(clause, "left")), iter=iter_)))
            else:
                out[-1].ifs.append(self.expression(self.named(clause)[0]))
        return out

    def list_comprehension(self, ts: _TS) -> S.ListComp:
        return S.ListComp(elt=self.expression(self.require(ts, "body")), generators=self.generators(ts))

    def set_comprehension(self, ts: _TS) -> S.SetComp | S.DictComp:
        if self.at(ts) in self.pre.unpacking:
            return S.DictComp(key=self.expression(self.require(ts, "body")), generators=self.generators(ts))
        return S.SetComp(elt=self.expression(self.require(ts, "body")), generators=self.generators(ts))

    def dictionary_comprehension(self, ts: _TS) -> S.DictComp:
        pair = self.require(ts, "body")
        return S.DictComp(key=self.expression(self.require(pair, "key")),
                          value=self.expression(self.require(pair, "value")), generators=self.generators(ts))

    def generator_expression(self, ts: _TS) -> S.GeneratorExp:
        return S.GeneratorExp(elt=self.expression(self.require(ts, "body")), generators=self.generators(ts))

    def yield_(self, ts: _TS) -> S.Yield | S.YieldFrom:
        kids = self.named(ts)
        if self.has(ts, "from"):
            return S.YieldFrom(value=self.expression(kids[0]))
        return S.Yield(value=self.expression(kids[0]) if kids else None)

    def attribute(self, ts: _TS) -> S.Attribute:
        return S.Attribute(value=self.expression(self.require(ts, "object")),
                           attr=self.identifier(self.require(ts, "attribute")))

    def subscript(self, ts: _TS) -> S.Subscript:
        indices = self.fields(ts, "subscript")
        elts = [self.expression(i) for i in indices]
        index = elts[0] if len(elts) == 1 and not self.has(ts, ",") else self.made(indices[0], S.Tuple(elts=elts))
        return S.Subscript(value=self.expression(self.require(ts, "value")), slice=index)

    def slice_(self, ts: _TS) -> S.Slice:
        parts: list[S.Expression | None] = [None, None, None]
        colons = 0
        for c in self.kids(ts):
            if c.type == ":":
                colons += 1
            else:
                parts[colons] = self.expression(c)
        return S.Slice(lower=parts[0], upper=parts[1], step=parts[2])

    def call_arguments(self, ts: _TS) -> tuple[list[S.Expression], list[S.Keyword]]:
        args: list[S.Expression] = []
        keywords: list[S.Keyword] = []
        for k in self.named(ts):
            if k.type == "keyword_argument":
                keywords.append(self.made(k, S.Keyword(arg=self.identifier(self.require(k, "name")),
                                                       value=self.expression(self.require(k, "value")))))
            elif k.type == "dictionary_splat":
                keywords.append(self.made(k, S.Keyword(value=self.expression(self.named(k)[0]))))
            else:
                args.append(self.expression(k))
        return args, keywords

    def call(self, ts: _TS) -> S.Call:
        arguments = self.require(ts, "arguments")
        made = S.Call(func=self.expression(self.require(ts, "function")))
        if arguments.type == "generator_expression":
            made.args = [self.expression(arguments)]
        else:
            made.args, made.keywords = self.call_arguments(arguments)
        return made

    def splat(self, ts: _TS) -> S.Starred:
        return S.Starred(value=self.expression(self.named(ts)[0]))

    def await_(self, ts: _TS) -> S.Expression:
        value = self.named(ts)[0]
        if value.type == "binary_operator" and self.text(self.require(value, "operator")) == "**":
            # `await x ** y` is `(await x) ** y`, which tree-sitter-python reads as `await (x ** y)`
            left = self.made(ts, S.Await(value=self.expression(self.require(value, "left"))))
            return S.BinOp(left=left, op="**", right=self.expression(self.require(value, "right")))
        return S.Await(value=self.expression(value))

    def unary_operator(self, ts: _TS) -> S.UnaryOp:
        return S.UnaryOp(op=self.text(self.require(ts, "operator")),
                         operand=self.expression(self.require(ts, "argument")))

    def not_operator(self, ts: _TS) -> S.UnaryOp:
        return S.UnaryOp(op="not", operand=self.expression(self.require(ts, "argument")))

    def binary_operator(self, ts: _TS) -> S.Expression:
        """A chain of binary operators, regrouped by Python's precedence."""
        operands: list[_TS] = []
        operators: list[str] = []

        def flatten(node: _TS) -> None:
            if node.type == "binary_operator":
                flatten(self.require(node, "left"))
                operators.append(self.text(self.require(node, "operator")))
                flatten(self.require(node, "right"))
            else:
                operands.append(node)

        flatten(ts)
        values = [self.expression(o) for o in operands]

        def build(low: int, high: int, level: int) -> S.Expression:
            """The operands `low` to `high`, with the operators between them, at precedence `level` or above."""
            if low == high:
                return values[low]
            group = _LEVELS[level]
            splits = [k for k in range(low, high) if operators[k] in group]
            if not splits:
                return build(low, high, level + 1)
            k = splits[0] if group == ("**",) else splits[-1]  # `**` groups to the right, the others to the left
            right_level = level if group == ("**",) else level + 1
            left_level = level + 1 if group == ("**",) else level
            made = S.BinOp(left=build(low, k, left_level), op=operators[k], right=build(k + 1, high, right_level))
            return self.made(operands[low], made)

        return build(0, len(values) - 1, 0)

    def boolean_operator(self, ts: _TS) -> S.BoolOp:
        op = self.text(self.require(ts, "operator"))
        values: list[S.Expression] = []
        for side in (self.require(ts, "left"), self.require(ts, "right")):
            if side.type == "boolean_operator" and self.text(self.require(side, "operator")) == op:
                values.extend(self.made(side, self.boolean_operator(side)).values)
            else:
                values.append(self.expression(side))
        return S.BoolOp(op=op, values=values)

    def comparison_operator(self, ts: _TS) -> S.Compare:
        operands = [c for c in self.named(ts) if ts.field_name_for_child(ts.children.index(c)) != "operators"]
        operators = self.fields(ts, "operators")
        comparisons = []
        for op, operand in zip(operators, operands[1:]):
            spelling = " ".join(self.text(op).split())
            if spelling == "<>":
                raise self.error(op, "unsupported syntax: <>, which is Python 2")
            comparisons.append(self.made(op, S.Comparison(op=spelling, comparator=self.expression(operand))))
        return S.Compare(left=self.expression(operands[0]), comparisons=comparisons)

    def conditional_expression(self, ts: _TS) -> S.Expression:
        body, test, orelse = self.named(ts)
        if body.type == "named_expression":
            # `x := a if b else c` is `x := (a if b else c)`, which tree-sitter-python reads as `(x := a) if b else c`
            value = self.made(ts, S.IfExp(body=self.expression(self.require(body, "value")), test=self.expression(test),
                                          orelse=self.expression(orelse)))
            return S.NamedExpr(target=self.name(self.require(body, "name")), value=value)
        return S.IfExp(body=self.expression(body), test=self.expression(test), orelse=self.expression(orelse))

    def named_expression(self, ts: _TS) -> S.NamedExpr:
        return S.NamedExpr(target=self.name(self.require(ts, "name")),
                           value=self.expression(self.require(ts, "value")))

    def lambda_(self, ts: _TS) -> S.Lambda:
        parameters = self.field(ts, "parameters")
        return S.Lambda(args=self.arguments(parameters) if parameters is not None else self.made(ts, S.Arguments()),
                        body=self.expression(self.require(ts, "body")))

    def identifier_expression(self, ts: _TS) -> S.Name:
        return S.Name(id=self.identifier(ts))

    EXPRESSIONS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "identifier": identifier_expression, "integer": constant, "float": constant, "true": constant,
        "false": constant, "none": constant, "ellipsis": constant, "string": string,
        "concatenated_string": concatenated_string, "parenthesized_expression": parenthesized_expression,
        "tuple": tuple, "expression_list": expression_list, "pattern_list": expression_list, "list": list_,
        "set": set_, "dictionary": dictionary, "list_comprehension": list_comprehension,
        "set_comprehension": set_comprehension, "dictionary_comprehension": dictionary_comprehension,
        "generator_expression": generator_expression, "yield": yield_, "attribute": attribute,
        "subscript": subscript, "slice": slice_, "call": call, "list_splat": splat, "list_splat_pattern": splat,
        "await": await_, "unary_operator": unary_operator,
        "not_operator": not_operator, "binary_operator": binary_operator, "boolean_operator": boolean_operator,
        "comparison_operator": comparison_operator, "conditional_expression": conditional_expression,
        "named_expression": named_expression, "lambda": lambda_,
    }

    # Patterns

    def pattern(self, ts: _TS) -> S.Pattern:
        """A pattern: a `case_pattern`, or what one holds."""
        if ts.type == "_":
            return self.made(ts, S.MatchAs())
        if ts.type == "case_pattern":
            kids = self.kids(ts)
            if kids[0].type == "-":
                return self.made(ts, S.MatchValue(value=self.signed(kids)))
            return self.pattern(kids[0])
        method = self.PATTERNS.get(ts.type)
        if method is not None:
            return self.made(ts, method(self, ts))
        if ts.type in ("none", "true", "false"):
            return self.made(ts, S.MatchSingleton(value=self.text(ts)))
        return self.made(ts, S.MatchValue(value=self.expression(ts)))

    def signed(self, kids: list[_TS]) -> S.Expression:
        """A negative number, `-1`, which tree-sitter-python writes as two tokens."""
        return self.made(kids[0], S.UnaryOp(op="-", operand=self.expression(kids[1])))

    def as_pattern(self, ts: _TS) -> S.MatchAs:
        pattern, name = self.named(ts)
        return S.MatchAs(pattern=self.pattern(pattern), name=self.identifier(name))

    def union_pattern(self, ts: _TS) -> S.MatchOr:
        patterns: list[S.Pattern] = []
        kids = [k for k in self.kids(ts) if k.type != "|"]
        i = 0
        while i < len(kids):
            k = kids[i]
            if k.type == "-":  # tree-sitter lists `-1` as two alternatives' worth of children
                patterns.append(self.made(k, S.MatchValue(value=self.signed(kids[i:i + 2]))))
                i += 1
            else:
                patterns.append(self.pattern(k))
            i += 1
        return S.MatchOr(patterns=patterns)

    def list_pattern(self, ts: _TS) -> S.MatchSequence:
        return S.MatchSequence(delimiters="[]", patterns=[self.pattern(k) for k in self.named(ts)])

    def tuple_pattern(self, ts: _TS) -> S.Pattern:
        patterns = [self.pattern(k) for k in self.named(ts)]
        if len(patterns) == 1 and not self.has(ts, ","):
            return patterns[0]  # a group: `(pattern)`
        return S.MatchSequence(delimiters="()", patterns=patterns)

    def splat_pattern(self, ts: _TS) -> S.MatchStar:
        names = self.named(ts)
        return S.MatchStar(name=self.identifier(names[0]) if names else None)

    def dotted_pattern(self, ts: _TS) -> S.Pattern:
        names = self.named(ts)
        if len(names) == 1:
            return S.MatchAs(name=self.identifier(names[0]))
        return S.MatchValue(value=self.dotted_expression(ts))

    def dotted_expression(self, ts: _TS) -> S.Expression:
        names = self.named(ts)
        value: S.Expression = self.name(names[0])
        for name in names[1:]:
            value = self.made(ts, S.Attribute(value=value, attr=self.identifier(name)))
        return value

    def dict_pattern(self, ts: _TS) -> S.MatchMapping:
        made = S.MatchMapping()
        kids = self.kids(ts)
        i = 0
        while i < len(kids):
            k = kids[i]
            if k.type == "splat_pattern":
                made.rest = self.identifier(self.named(k)[0])
            elif ts.field_name_for_child(ts.children.index(k)) == "key":
                key = [k]
                if k.type == "-":
                    i += 1
                    key.append(kids[i])
                made.keys.append(self.signed(key) if k.type == "-" else self.pattern_value(k))
            elif k.type == "case_pattern":
                made.patterns.append(self.pattern(k))
            i += 1
        return made

    def pattern_value(self, ts: _TS) -> S.Expression:
        """A literal or dotted name in a pattern, as an expression."""
        if ts.type == "dotted_name":
            return self.dotted_expression(ts)
        if ts.type == "complex_pattern":
            return self.complex(ts)
        return self.expression(ts)

    def complex(self, ts: _TS) -> S.Expression:
        kids = self.kids(ts)
        if kids[0].type == "-":
            left: S.Expression = self.made(kids[0], S.UnaryOp(op="-", operand=self.expression(kids[1])))
            kids = kids[2:]
        else:
            left, kids = self.expression(kids[0]), kids[1:]
        return self.made(ts, S.BinOp(left=left, op=kids[0].type, right=self.expression(kids[1])))

    def complex_pattern(self, ts: _TS) -> S.MatchValue:
        return S.MatchValue(value=self.complex(ts))

    def class_pattern(self, ts: _TS) -> S.MatchClass:
        names = self.named(ts)
        made = S.MatchClass(cls=self.dotted_expression(names[0]))
        for k in names[1:]:
            inner = self.kids(k)[0]
            if inner.type == "as_pattern" and self.kids(self.named(inner)[0])[0].type == "keyword_pattern":
                # `name=pattern as alias`, which tree-sitter-python reads as `(name=pattern) as alias`
                keyword, alias = self.kids(self.named(inner)[0])[0], self.named(inner)[-1]
                name, *value = self.kids(keyword)
                made.kwd_attrs.append(self.identifier(name))
                made.kwd_patterns.append(self.made(keyword, S.MatchAs(pattern=self.keyword_value(value[1:]),
                                                                      name=self.identifier(alias))))
            elif inner.type == "keyword_pattern":
                name, *value = self.kids(inner)
                made.kwd_attrs.append(self.identifier(name))
                made.kwd_patterns.append(self.made(inner, self.keyword_value(value[1:])))
            else:
                made.patterns.append(self.pattern(k))
        return made

    def keyword_value(self, kids: list[_TS]) -> S.Pattern:
        """The pattern of a keyword pattern, which tree-sitter does not wrap in a `case_pattern`."""
        if kids[0].type == "-":
            return self.made(kids[0], S.MatchValue(value=self.signed(kids)))
        return self.pattern(kids[0])

    PATTERNS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "as_pattern": as_pattern, "union_pattern": union_pattern, "list_pattern": list_pattern,
        "tuple_pattern": tuple_pattern, "splat_pattern": splat_pattern, "dotted_name": dotted_pattern,
        "dict_pattern": dict_pattern, "class_pattern": class_pattern, "complex_pattern": complex_pattern,
    }


def parse(text: str) -> tuple[S.Module, dict[int, int], _Source]:
    """The tree of `text`, the offset where each of its nodes starts (by `id`), and the source, for locating
    problems. Raises `ParseError` for text tree-sitter-python cannot parse."""
    source = _Source(text)
    tree = _PARSER.parse(source.data, encoding="utf16le")
    prepared = _Prepared()
    if tree.root_node.has_error:
        cleaned, prepared = _prepare(text, tree.root_node, source)
        source = _Source(text, cleaned)
        tree = _PARSER.parse(source.data, encoding="utf16le")
    converter = _Converter(source, prepared)
    module = converter.module(tree.root_node)
    return module, converter.positions, source
