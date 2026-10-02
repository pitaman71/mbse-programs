"""Parses TypeScript and JavaScript source text into TypeScript trees, delegating to tree-sitter-typescript.

tree-sitter-typescript builds a concrete syntax tree, with its `typescript` grammar or, for JSX, its `tsx` grammar;
`_Converter` rewrites it into TypeScript kinds, one tree-sitter node type at a time. tree-sitter-typescript 0.23
cannot parse a few constructs of TypeScript 4.7 and later. When the text does not parse, a pre-pass (`_prepare`)
removes them, keeping every other character where it was: the `accessor` keyword, the variance annotations `in` and
`out` of type parameters, the `defer` of `import defer`, and the `type` of `export type *`. The converter puts them
back where they were.

Positions are counted in characters (code points), never bytes, so that every implementation reports the same line and
column.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tree_sitter_typescript
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from . import Syntax as S

__all__ = ["parse"]

_PARSERS = {False: _TSParser(_Grammar(tree_sitter_typescript.language_typescript())),
            True: _TSParser(_Grammar(tree_sitter_typescript.language_tsx()))}

_EXTRAS = {"comment", "html_comment"}
_KEYWORD_TYPES = {
    "any": S.TSAnyKeyword, "unknown": S.TSUnknownKeyword, "number": S.TSNumberKeyword, "bigint": S.TSBigIntKeyword,
    "boolean": S.TSBooleanKeyword, "string": S.TSStringKeyword, "symbol": S.TSSymbolKeyword,
    "object": S.TSObjectKeyword, "never": S.TSNeverKeyword, "void": S.TSVoidKeyword,
    "undefined": S.TSUndefinedKeyword, "null": S.TSNullKeyword, "intrinsic": S.TSIntrinsicKeyword,
}
# Operators that bind less than `as` and `satisfies`, which bind as the relational operators do.
_LOOSER_THAN_AS = {"==", "!=", "===", "!==", "&", "^", "|", "&&", "||", "??"}
# How tightly each binary operator binds.
_BINDS = {"??": 1, "||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "===": 6, "!==": 6, "<": 7, "<=": 7,
          ">": 7, ">=": 7, "in": 7, "instanceof": 7, "<<": 8, ">>": 8, ">>>": 8, "+": 9, "-": 9, "*": 10, "/": 10,
          "%": 10, "**": 11}
_MODIFIERS = {"static", "readonly", "declare", "abstract", "override", "accessor", "async", "get", "set", "*", "?",
              "!", "public", "private", "protected"}


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


# --- The pre-pass: what tree-sitter-typescript cannot parse ---


class _Prepared:
    """What the pre-pass rewrote, by character offset: `accessor`s (by the offset of what follows), `in` and `out`
    annotations (by the type parameter's name), `import defer` and `export type *` (by the statement), names
    tree-sitter-typescript reads as keywords, `using` in `for (... of ...)`, and `import(...)` in types."""

    def __init__(self) -> None:
        self.accessors: set[int] = set()
        self.variance: dict[int, set[str]] = {}
        self.deferred: set[int] = set()
        self.type_exports: set[int] = set()
        self.imports: dict[int, int] = {}  # a placeholder's offset -> the offset of its `(`
        self.names: dict[int, str] = {}  # names tree-sitter-typescript reads as keywords, by offset
        self.usings: dict[int, str] = {}  # `using` or `await using` in a `for (... of ...)`, by the offset of `const`


def _tokens(source: _Source, root: _TS) -> list[tuple[int, int, str]]:
    """The tokens of a tree, as character spans and their text: each leaf, but each string whole, without comments."""
    out: list[tuple[int, int, str]] = []
    stack = [root]
    while stack:
        ts = stack.pop()
        if ts.type in _EXTRAS or ts.is_missing:  # what error recovery put in is not in the text
            continue
        if ts.child_count == 0 or ts.type in ("string", "template_string", "regex"):
            start, end = source.offset(ts.start_byte), source.offset(ts.end_byte)
            out.append((start, end, source.text[start:end]))
            continue
        stack.extend(reversed(ts.children))
    return out


def _starts_name(word: str) -> bool:
    """Whether a token starts as a name does: with a letter, `_` or `$`."""
    return word != "" and (word[0].isalpha() or word[0] in ("_", "$"))


def _prepare(text: str, root: _TS, source: _Source) -> tuple[str, _Prepared]:
    """The text with the constructs tree-sitter-typescript cannot parse removed, and what was removed."""
    found = _Prepared()
    chars = list(text)

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            chars[p] = " "

    tokens = _tokens(source, root)
    for i, (start, end, word) in enumerate(tokens):
        before = tokens[i - 1][2] if i > 0 else ""
        after = tokens[i + 1][2] if i + 1 < len(tokens) else ""
        if word == "accessor" and after not in ("", "(", ":", "=", ";", "?", "!", "<", ",", ")", "}"):
            blank(start, end)
            found.accessors.add(tokens[i + 1][0])  # where the member starts once `accessor` is gone, or its name
        elif word == "accessor" and before in ("{", ";", "}"):
            chars[start] = "_"  # a member named `accessor`
            found.names[start] = word
        elif word in ("in", "out") and before in ("<", ",", "in", "const") and _starts_name(after) and (
                after not in ("in", "of")):
            name = next(t for t in tokens[i + 1:] if t[2] not in ("in", "out"))
            blank(start, end)
            found.variance.setdefault(name[0], set()).add(word)
        elif word == "defer" and before == "import" and after in ("*", "{"):
            blank(start, end)
            found.deferred.add(tokens[i - 1][0])
        elif word == "type" and before == "export" and after == "*":
            blank(start, end)
            found.type_exports.add(tokens[i - 1][0])
        elif word == "abstract" and after in (":", "?", "(") and before in (";", "{", "}", ",", "readonly"):
            chars[start] = "_"  # a member named `abstract`
            found.names[start] = word
        elif word == "using" and before in ("(", "await") and i + 2 < len(tokens) and tokens[i + 2][2] == "of" and (
                before == "(" or tokens[i - 2][2] == "("):
            # `for (using x of y)` becomes `for (const x of y)`, as long
            chars[start:end] = list("const")
            keyword = "using"
            if before == "await":
                blank(tokens[i - 1][0], tokens[i - 1][1])
                keyword = "await using"
            found.usings[start] = keyword
        elif word == "using" and (not _starts_name(after) or after in ("in", "of", "instanceof", "as", "satisfies")):
            chars[start] = "_"  # a name `using`: the keyword is followed by the name it binds
            found.names[start] = word
        elif word == "import" and after == "(" and before not in (".", ""):
            # `import("m")`, which tree-sitter-typescript cannot qualify with type arguments as a type, becomes a
            # name as long, `_______m_`... the converter reads the call back from the text
            close = next((j for j in range(i + 1, len(tokens)) if tokens[j][2] == ")"), None)
            if close is not None:
                for p in range(start, tokens[close][1]):
                    chars[p] = "_"  # one name, though the call spans lines: positions are offsets, which stay
                found.imports[start] = tokens[i + 1][0]
    return "".join(chars), found


# --- The converter ---


class _Converter:
    """Rewrites a tree-sitter-typescript tree into TypeScript nodes, recording where each node starts in `positions`.
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
        return [c for c in ts.children if c.type not in _EXTRAS]

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        return [c for c in ts.children if c.is_named and c.type not in _EXTRAS]

    @staticmethod
    def field(ts: _TS, name: str) -> _TS | None:
        """The child in the field `name`, found among the children: tree-sitter's own lookup can return a nested
        node's (`typeof a.b.c`)."""
        return next((c for i, c in enumerate(ts.children) if ts.field_name_for_child(i) == name), None)

    @staticmethod
    def fields(ts: _TS, name: str) -> list[_TS]:
        return [c for i, c in enumerate(ts.children) if ts.field_name_for_child(i) == name]

    @staticmethod
    def has(ts: _TS, token: str) -> bool:
        return any(not c.is_named and c.type == token for c in ts.children)

    @staticmethod
    def require(ts: _TS, name: str) -> _TS:
        """A field the grammar requires, which tree-sitter always writes."""
        return _Converter.field(ts, name)  # type: ignore[return-value]

    def tokens_before(self, ts: _TS, field: str) -> set[str]:
        """The modifier keywords and marks among `ts`'s children before its field `field`."""
        stop = self.require(ts, field).start_byte
        return {c.type if not c.is_named else self.text(c) for c in ts.children
                if c.start_byte < stop and (
                    not c.is_named or c.type in ("accessibility_modifier", "override_modifier"))}

    def spelling(self, ts: _TS) -> str:
        """A name's spelling, which the pre-pass may have changed: a name tree-sitter-typescript reads as a keyword."""
        return self.pre.names.get(self.at(ts), self.text(ts))

    def identifier(self, ts: _TS) -> S.Identifier:
        return self.made(ts, S.Identifier(name=self.spelling(ts)))

    def literal(self, ts: _TS) -> S.Literal:
        return self.made(ts, S.Literal(raw=self.text(ts)))

    # Errors

    def check(self, ts: _TS) -> None:
        """Raises for the first syntax error in `ts`, in source order."""
        stack = [ts]
        while stack:
            node = stack.pop()
            if node.type == "ERROR" and not self.global_block(node):
                raise self.error(node, "syntax error")
            if node.is_missing and not (node.parent is not None and self.global_block(node.parent)):
                raise self.error(node, f"expected {node.type}")
            stack.extend(reversed(node.children))

    def global_block(self, ts: _TS) -> bool:
        """Whether `ts` is the `global` of `global { ... }` in a module, which tree-sitter-typescript reads as an
        error followed by a block."""
        kids = [c for c in ts.children if not c.is_missing]
        following = ts.next_sibling
        return (ts.type in ("ERROR", "expression_statement") and len(kids) == 1 and kids[0].type == "identifier"
                and self.text(kids[0]) == "global" and following is not None and following.type == "statement_block"
                and ts.parent is not None and ts.parent.type == "statement_block")

    # Lists of statements and members, with their comments

    def listed(self, nodes: list[_TS], convert: Callable[[_TS], Any], header: _TS | None = None) -> list[Any]:
        """The items among `nodes`, up to a closing brace, converted, and the comments between them: a comment is
        trailing on the line where the item before it ends, or `header` for the first."""
        out: list[Any] = []
        previous = header
        skip = None
        for ts in nodes:
            if skip is not None and ts.id == skip:
                previous = ts
                continue
            if ts.type == "comment":
                out.append(self.comment(ts, previous))
            elif ts.type == "empty_statement" and out and isinstance(out[-1], S.TSModuleDeclaration) and (
                    out[-1].body is None and previous is not None and previous.type != "comment"):
                pass  # the `;` that ends `declare module "a";`, which tree-sitter-typescript reads as a statement
            elif ts.type in ("ERROR", "expression_statement") and self.global_block(ts):
                block = ts.next_sibling
                made = S.TSModuleDeclaration(moduleKind="global", id=self.made(ts, S.Identifier(name="global")),
                                             body=self.module_block(block))
                out.append(self.made(ts, made))
                skip = block.id
            elif ts.is_named and ts.type != "html_comment":
                out.append(convert(ts))
                for comment in self.strays(ts):
                    out.append(self.comment(comment, comment.prev_sibling))
                    ts = comment
            elif ts.type == "}":
                break
            else:
                continue
            previous = ts
        return out

    @staticmethod
    def strays(ts: _TS) -> list[_TS]:
        """The comments after `ts` that tree-sitter-typescript puts after the closing brace of the block that ends it:
        `m() {} // c`."""
        out: list[_TS] = []
        node = ts
        while node.child_count > 0:
            kids = node.children
            i = len(kids)
            while kids[i - 1].type == "comment":  # a node holds more than comments
                i -= 1
            if i < len(kids) and kids[i - 1].type == "}":
                out = kids[i:] + out  # those of an inner block come first
            node = kids[i - 1]
        return out

    def comment(self, ts: _TS, previous: _TS | None) -> S.Comment:
        text = self.text(ts)
        made = S.Comment(block=text.startswith("/*"), text=text[2:-2] if text.startswith("/*") else text[2:])
        made.trailing = previous is not None and "\n" not in self.source.text[  # in the text as written
            self.source.offset(previous.end_byte):self.source.offset(ts.start_byte)]
        return self.made(ts, made)

    def program(self, ts: _TS) -> S.Program:
        self.check(ts)
        made = S.Program()
        nodes = list(ts.children)
        if nodes and nodes[0].type == "hash_bang_line":
            made.hashbang = self.text(nodes[0])[2:]
            nodes = nodes[1:]
        made.body = self.listed(nodes, self.statement)
        return self.made(ts, made)

    def block(self, ts: _TS) -> S.BlockStatement:
        return self.made(ts, S.BlockStatement(body=self.listed(ts.children, self.statement, ts.children[0])))

    # Statements

    def statement(self, ts: _TS) -> S.Statement:
        return self.made(ts, self.STATEMENTS[ts.type](self, ts))  # the grammar has no other statement

    def expression_statement(self, ts: _TS) -> S.Statement:
        inner = self.named(ts)[0]
        if inner.type == "internal_module":  # `namespace A {}`, which tree-sitter-typescript reads as an expression
            return self.module(inner, "namespace")
        using = self.using(inner)
        if using is not None:
            return using
        return S.ExpressionStatement(expression=self.expression(inner))

    def using(self, ts: _TS) -> S.VariableDeclaration | None:
        """`using x = f()` or `await using x = f()`, which tree-sitter-typescript reads as an assignment with a
        `using` token, perhaps awaited; None for any other expression."""
        keyword = "using"
        if ts.type == "await_expression":
            keyword, ts = "await using", self.named(ts)[0]
        if ts.type != "assignment_expression" or not self.has(ts, "using"):
            return None
        left = self.require(ts, "left")
        declarator = self.made(left, S.VariableDeclarator(id=self.binding(left),
                                                          init=self.expression(self.require(ts, "right"))))
        return S.VariableDeclaration(declarationKind=keyword, declarations=[declarator])

    def declarators(self, ts: _TS) -> list[S.VariableDeclarator]:
        return [self.declarator(d) for d in self.named(ts) if d.type == "variable_declarator"]

    def declarator(self, ts: _TS) -> S.VariableDeclarator:
        made = S.VariableDeclarator(id=self.binding(self.require(ts, "name")))
        made.definite = self.has(ts, "!")
        annotation = self.field(ts, "type")
        if annotation is not None:
            made.id.typeAnnotation = self.annotation(annotation)
        value = self.field(ts, "value")
        made.init = None if value is None else self.expression(value)
        return self.made(ts, made)

    def lexical_declaration(self, ts: _TS) -> S.VariableDeclaration:
        return S.VariableDeclaration(declarationKind=self.text(self.require(ts, "kind")),
                                     declarations=self.declarators(ts))

    def variable_declaration(self, ts: _TS) -> S.VariableDeclaration:
        return S.VariableDeclaration(declarationKind="var", declarations=self.declarators(ts))

    def return_statement(self, ts: _TS) -> S.ReturnStatement:
        kids = self.named(ts)
        return S.ReturnStatement(argument=self.expression(kids[0]) if kids else None)

    def throw_statement(self, ts: _TS) -> S.ThrowStatement:
        return S.ThrowStatement(argument=self.expression(self.named(ts)[0]))

    def if_statement(self, ts: _TS) -> S.IfStatement:
        made = S.IfStatement(test=self.condition(self.require(ts, "condition")),
                             consequent=self.statement(self.require(ts, "consequence")))
        alternative = self.field(ts, "alternative")
        if alternative is not None:
            made.alternate = self.statement(self.named(alternative)[0])
        return made

    def condition(self, ts: _TS) -> S.Expression:
        """The expression in the parentheses a statement's syntax has: `if (test)`, `while (test)`."""
        return self.expression(self.named(ts)[0])

    def while_statement(self, ts: _TS) -> S.WhileStatement:
        return S.WhileStatement(test=self.condition(self.require(ts, "condition")),
                                body=self.statement(self.require(ts, "body")))

    def do_statement(self, ts: _TS) -> S.DoWhileStatement:
        return S.DoWhileStatement(body=self.statement(self.require(ts, "body")),
                                  test=self.condition(self.require(ts, "condition")))

    def with_statement(self, ts: _TS) -> S.WithStatement:
        return S.WithStatement(object=self.condition(self.require(ts, "object")),
                               body=self.statement(self.require(ts, "body")))

    def for_statement(self, ts: _TS) -> S.ForStatement:
        made = S.ForStatement(body=self.statement(self.require(ts, "body")))
        init = self.require(ts, "initializer")
        if init.type in ("lexical_declaration", "variable_declaration"):
            made.init = self.made(init, self.STATEMENTS[init.type](self, init))
        elif init.type != "empty_statement":
            made.init = self.expression(init)
        conditions = [c for c in self.fields(ts, "condition") if c.type not in (";", "empty_statement")]
        made.test = self.expression(conditions[0]) if conditions else None
        increment = self.field(ts, "increment")
        made.update = None if increment is None else self.expression(increment)
        return made

    def for_in_statement(self, ts: _TS) -> S.Statement:
        left = self.require(ts, "left")
        kind = self.field(ts, "kind")
        if kind is not None:
            declarator = self.made(left, S.VariableDeclarator(id=self.binding(left)))
            value = self.field(ts, "value")
            if value is not None:
                declarator.init = self.expression(value)
            keyword = self.pre.usings.get(self.at(kind), self.text(kind))
            target: Any = self.made(kind, S.VariableDeclaration(declarationKind=keyword, declarations=[declarator]))
        else:
            target = self.target(left)
        right = self.expression(self.require(ts, "right"))
        body = self.statement(self.require(ts, "body"))
        if self.text(self.require(ts, "operator")) == "in":
            return S.ForInStatement(left=target, right=right, body=body)
        kids = self.kids(ts)
        return S.ForOfStatement(isAwait=kids[1].type == "await", left=target, right=right, body=body)

    def switch_statement(self, ts: _TS) -> S.SwitchStatement:
        cases = []
        for case in [c for c in self.require(ts, "body").children if c.is_named]:
            if case.type == "comment":  # after a case, which tree-sitter-typescript ends where its last statement does
                if cases:
                    cases[-1].consequent.append(self.comment(case, case.prev_sibling))
                continue
            value = self.field(case, "value")
            body = [c for c in case.children if c.start_byte > (value or case.children[0]).end_byte]
            made = S.SwitchCase(test=None if value is None else self.expression(value))
            colon = next(c for c in case.children if c.type == ":")
            made.consequent = self.listed([c for c in body if c.start_byte > colon.start_byte], self.statement, colon)
            cases.append(self.made(case, made))
        return S.SwitchStatement(discriminant=self.condition(self.require(ts, "value")), cases=cases)

    def try_statement(self, ts: _TS) -> S.TryStatement:
        made = S.TryStatement(block=self.block(self.require(ts, "body")))
        handler = self.field(ts, "handler")
        if handler is not None:
            clause = S.CatchClause(body=self.block(self.require(handler, "body")))
            parameter = self.field(handler, "parameter")
            if parameter is not None:
                clause.param = self.binding(parameter)
                annotation = self.field(handler, "type")
                if annotation is not None:
                    clause.param.typeAnnotation = self.annotation(annotation)
            made.handler = self.made(handler, clause)
        finalizer = self.field(ts, "finalizer")
        if finalizer is not None:
            made.finalizer = self.block(self.require(finalizer, "body"))
        return made

    def labeled_statement(self, ts: _TS) -> S.LabeledStatement:
        return S.LabeledStatement(label=self.identifier(self.require(ts, "label")),
                                  body=self.statement(self.require(ts, "body")))

    def jump(kind: type) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        def convert(self: _Converter, ts: _TS) -> Any:
            label = self.field(ts, "label")
            return kind(label=None if label is None else self.identifier(label))
        return convert

    def simple(kind: type) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        return lambda self, ts: kind()

    # Functions and classes

    def function_declaration(self, ts: _TS) -> S.FunctionDeclaration:
        made = S.FunctionDeclaration(isAsync=self.has(ts, "async"), generator=self.has(ts, "*"),
                                     id=self.identifier(self.require(ts, "name")),
                                     body=self.block(self.require(ts, "body")))
        self.signature(ts, made)
        return made

    def signature(self, ts: _TS, made: Any) -> None:
        """The type parameters, parameters and return type of a function, method or signature."""
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        returns = self.field(ts, "return_type") or (
            self.field(ts, "type") if ts.type == "construct_signature" else None)
        if returns is not None:
            made.returnType = self.annotation(returns)

    def function_signature(self, ts: _TS) -> S.TSDeclareFunction:
        made = S.TSDeclareFunction(isAsync=self.has(ts, "async"), generator=self.has(ts, "*"),
                                   id=self.identifier(self.require(ts, "name")))
        self.signature(ts, made)
        return made

    def parameters(self, ts: _TS) -> list[Any]:
        return [self.parameter(p) for p in self.named(ts)]

    def parameter(self, ts: _TS) -> Any:
        """A `required_parameter` or `optional_parameter`: a binding, perhaps with `?`, a type and a default, or a
        parameter property."""
        pattern = self.require(ts, "pattern")  # a parameter's, which `name` only is in a tuple type
        if pattern.type == "this":
            binding: Any = self.made(pattern, S.Identifier(name="this"))
        else:
            binding = self.binding(pattern)
        annotation = self.field(ts, "type")
        if annotation is not None:
            binding.typeAnnotation = self.annotation(annotation)
        if ts.type == "optional_parameter":
            binding.optional = True
        decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        value = self.field(ts, "value")
        result: Any = binding
        if value is not None:
            result = self.made(ts, S.AssignmentPattern(left=binding, right=self.expression(value)))
        modifiers = self.tokens_before(ts, "pattern")
        accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        if accessibility or {"readonly", "override"} & modifiers:
            return self.made(ts, S.TSParameterProperty(
                decorators=decorators, accessibility=accessibility, override="override" in modifiers,
                readonly="readonly" in modifiers, parameter=result))
        result.decorators = decorators
        return result

    def class_declaration(self, ts: _TS) -> S.ClassDeclaration:
        made = S.ClassDeclaration(abstract=ts.type == "abstract_class_declaration")
        self.class_parts(ts, made)
        return made

    def class_parts(self, ts: _TS, made: Any) -> None:
        made.decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        name = self.field(ts, "name")
        made.id = None if name is None else self.identifier(name)
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        heritage = next((c for c in self.named(ts) if c.type == "class_heritage"), None)
        if heritage is not None:
            for clause in self.named(heritage):
                if clause.type == "extends_clause":
                    made.superClass = self.expression(self.require(clause, "value"))
                    arguments = self.field(clause, "type_arguments")
                    if arguments is not None:
                        made.superTypeArguments = self.type_arguments(arguments)
                else:
                    made.implements = [self.made(t, S.TSClassImplements(**self.heritage(t)))
                                       for t in self.named(clause)]
        body = self.require(ts, "body")
        made.body = self.made(body, S.ClassBody(body=self.members(body)))

    def members(self, body: _TS) -> list[Any]:
        """A class body's members and comments; decorators before a member, which tree-sitter-typescript lists
        beside it, are its own."""
        pending: list[S.Decorator] = []

        def member(ts: _TS) -> Any:
            if ts.type == "decorator":
                pending.append(self.decorator(ts))
                return None
            made = self.member(ts)
            if pending and hasattr(made, "decorators"):
                made.decorators = pending + made.decorators
            pending.clear()
            return made

        return [m for m in self.listed(body.children, member, body.children[0]) if m is not None]

    def heritage(self, ts: _TS) -> dict[str, Any]:
        """The expression and type arguments of a type in `implements` or `extends`."""
        if ts.type == "generic_type":
            return {"expression": self.type_name_expression(self.require(ts, "name")),
                    "typeArguments": self.type_arguments(self.require(ts, "type_arguments"))}
        return {"expression": self.type_name_expression(ts)}

    def type_name_expression(self, ts: _TS) -> S.Expression:
        """A type's name, as the expression `implements` and `extends` take: `a.b.C`."""
        if ts.type == "nested_type_identifier":
            return self.made(ts, S.MemberExpression(object=self.type_name_expression(self.require(ts, "module")),
                                                    property=self.identifier(self.require(ts, "name"))))
        if ts.type == "nested_identifier":
            return self.made(ts, S.MemberExpression(object=self.type_name_expression(self.require(ts, "object")),
                                                    property=self.identifier(self.require(ts, "property"))))
        return self.identifier(ts)

    def decorator(self, ts: _TS) -> S.Decorator:
        return self.made(ts, S.Decorator(expression=self.expression(self.named(ts)[0])))

    def key(self, ts: _TS) -> tuple[S.Expression, bool]:
        """A member's key, and whether it is computed."""
        if ts.type == "computed_property_name":
            return self.expression(self.named(ts)[0]), True
        if ts.type == "private_property_identifier":
            return self.made(ts, S.PrivateIdentifier(name=self.text(ts)[1:])), False
        if ts.type in ("string", "number"):
            return self.literal(ts), False
        return self.identifier(ts), False

    def member(self, ts: _TS) -> Any:
        """A class member."""
        if ts.type == "class_static_block":
            body = self.require(ts, "body")
            return self.made(ts, S.StaticBlock(body=self.listed(body.children, self.statement, body.children[0])))
        if ts.type == "index_signature":
            return self.index_signature(ts)
        if ts.type == "public_field_definition":
            return self.field_definition(ts)
        return self.method(ts)  # a method_definition, method_signature or abstract_method_signature

    def modifiers(self, ts: _TS, made: Any, modifiers: set[str]) -> None:
        made.decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        made.accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        made.static = "static" in modifiers
        made.override = "override" in modifiers

    def field_definition(self, ts: _TS) -> Any:
        modifiers = self.tokens_before(ts, "name")
        accessor = "accessor" in modifiers or any(
            self.at(ts) <= o <= self.at(self.require(ts, "name")) for o in self.pre.accessors)
        abstract = "abstract" in modifiers
        kind = (S.TSAbstractAccessorProperty if abstract else S.AccessorProperty) if accessor else (
            S.TSAbstractPropertyDefinition if abstract else S.PropertyDefinition)
        made = kind()
        self.modifiers(ts, made, modifiers)
        made.declare, made.readonly = "declare" in modifiers, "readonly" in modifiers
        made.key, made.computed = self.key(self.require(ts, "name"))
        made.optional, made.definite = self.has(ts, "?"), self.has(ts, "!")
        annotation = self.field(ts, "type")
        if annotation is not None:
            made.typeAnnotation = self.annotation(annotation)
        value = self.field(ts, "value")
        made.value = None if value is None else self.expression(value)
        return self.made(ts, made)

    def method(self, ts: _TS) -> Any:
        modifiers = self.tokens_before(ts, "name")
        name = self.require(ts, "name")
        abstract = ts.type == "abstract_method_signature" or "abstract" in modifiers
        made = (S.TSAbstractMethodDefinition if abstract else S.MethodDefinition)()
        self.modifiers(ts, made, modifiers)
        made.key, made.computed = self.key(name)
        made.methodKind = "get" if "get" in modifiers else "set" if "set" in modifiers else "method"
        if made.methodKind == "method" and not made.static and not made.computed and self.text(name) in (
                "constructor", "'constructor'", '"constructor"'):
            made.methodKind = "constructor"
        made.optional = any(c.type == "?" and c.start_byte > name.start_byte for c in ts.children)
        body = self.field(ts, "body")
        value: Any = S.FunctionExpression(body=self.block(body)) if body is not None else (
            S.TSEmptyBodyFunctionExpression())
        value.isAsync, value.generator = "async" in modifiers, "*" in modifiers
        self.signature(ts, value)
        made.value = self.made(self.require(ts, "parameters"), value)
        return self.made(ts, made)

    def index_signature(self, ts: _TS) -> Any:
        mapped = next((c for c in self.named(ts) if c.type == "mapped_type_clause"), None)
        if mapped is not None:
            raise self.unsupported(ts)
        modifiers = self.tokens_before(ts, "type")
        name = self.require(ts, "name")
        parameter = self.identifier(name)
        parameter.typeAnnotation = self.made(self.require(ts, "index_type"), S.TSTypeAnnotation(
            typeAnnotation=self.type(self.require(ts, "index_type"))))
        made = S.TSIndexSignature(parameters=[parameter], readonly="readonly" in modifiers,
                                  static="static" in modifiers,
                                  typeAnnotation=self.annotation(self.require(ts, "type")))
        made.accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        return self.made(ts, made)

    # Modules

    def import_statement(self, ts: _TS) -> S.Statement:
        require = next((c for c in self.named(ts) if c.type == "import_require_clause"), None)
        if require is not None:
            reference = self.made(require, S.TSExternalModuleReference(
                expression=self.literal(self.require(require, "source"))))
            return S.TSImportEqualsDeclaration(importKind="type" if self.kids(ts)[1].type == "type" else "value",
                                               id=self.identifier(self.named(require)[0]), moduleReference=reference)
        made = S.ImportDeclaration(source=self.literal(self.require(ts, "source")))
        made.importKind = "type" if self.kids(ts)[1].type == "type" else "value"
        if self.at(ts) in self.pre.deferred:
            made.phase = "defer"
        clause = next((c for c in self.named(ts) if c.type == "import_clause"), None)
        if clause is not None:
            for part in self.named(clause):
                if part.type == "identifier":
                    made.specifiers.append(self.made(part, S.ImportDefaultSpecifier(local=self.identifier(part))))
                elif part.type == "namespace_import":
                    made.specifiers.append(self.made(part, S.ImportNamespaceSpecifier(
                        local=self.identifier(self.named(part)[0]))))
                else:
                    made.specifiers += [self.import_specifier(s) for s in self.named(part)]
        attributes = next((c for c in self.named(ts) if c.type == "import_attribute"), None)
        if attributes is not None:
            made.attributes = self.attributes(attributes)
        return made

    def attributes(self, ts: _TS) -> list[S.ImportAttribute]:
        out = []
        for pair in self.named(self.named(ts)[0]):
            key = self.require(pair, "key")
            out.append(self.made(pair, S.ImportAttribute(
                key=self.literal(key) if key.type == "string" else self.identifier(key),
                value=self.literal(self.require(pair, "value")))))
        return out

    def import_specifier(self, ts: _TS) -> S.ImportSpecifier:
        name = self.require(ts, "name")
        imported = self.literal(name) if name.type == "string" else self.identifier(name)
        alias = self.field(ts, "alias")
        local = self.identifier(alias) if alias is not None else self.made(name, S.Identifier(name=self.spelling(name)))
        kind = "type" if self.kids(ts)[0].type == "type" else "value"
        return self.made(ts, S.ImportSpecifier(importKind=kind, imported=imported, local=local))

    def import_alias(self, ts: _TS) -> S.TSImportEqualsDeclaration:
        name, reference = self.named(ts)
        return S.TSImportEqualsDeclaration(importKind="value", id=self.identifier(name),
                                           moduleReference=self.entity_name(reference))

    def entity_name(self, ts: _TS) -> Any:
        """`a.b.c` as a type's or a namespace's name: an `Identifier` or a `TSQualifiedName`."""
        if ts.type in ("nested_identifier", "member_expression"):
            return self.made(ts, S.TSQualifiedName(left=self.entity_name(self.require(ts, "object")),
                                                   right=self.identifier(self.require(ts, "property"))))
        if ts.type == "nested_type_identifier":
            return self.made(ts, S.TSQualifiedName(left=self.entity_name(self.require(ts, "module")),
                                                   right=self.identifier(self.require(ts, "name"))))
        if ts.type == "this":
            return self.made(ts, S.ThisExpression())
        return self.identifier(ts)

    def export_statement(self, ts: _TS) -> S.Statement:
        kids = self.kids(ts)
        decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        if kids[1].type == "=":
            return S.TSExportAssignment(expression=self.expression(self.named(ts)[-1]))
        if kids[1].type == "as":
            return S.TSNamespaceExportDeclaration(id=self.identifier(self.named(ts)[-1]))
        declaration = self.field(ts, "declaration")
        value = self.field(ts, "value")
        if self.has(ts, "default"):
            target = declaration or self.require(ts, "value")
            if target.type in ("function_expression", "generator_function", "class") and value is not None:
                converted: Any = self.default_declaration(target)
            elif declaration is not None:
                converted = self.statement(declaration)
            else:
                converted = self.expression(target)
            if decorators and isinstance(converted, S.ClassDeclaration):
                converted.decorators = decorators + converted.decorators
            return S.ExportDefaultDeclaration(declaration=converted)
        source = self.field(ts, "source")
        if self.has(ts, "*") or any(c.type == "namespace_export" for c in ts.children):
            made: Any = S.ExportAllDeclaration(source=self.literal(source))
            made.exportKind = "type" if self.at(ts) in self.pre.type_exports or kids[1].type == "type" else "value"
            namespace = next((c for c in self.named(ts) if c.type == "namespace_export"), None)
            if namespace is not None:
                exported = self.named(namespace)[0]
                made.exported = self.literal(exported) if exported.type == "string" else self.identifier(exported)
            return made  # tree-sitter-typescript reads no attributes here
        made = S.ExportNamedDeclaration()
        if declaration is not None:
            converted = self.statement(declaration)
            if decorators and isinstance(converted, S.ClassDeclaration):
                converted.decorators = decorators + converted.decorators
            made.declaration = converted
            made.exportKind = "type" if isinstance(converted, (
                S.TSInterfaceDeclaration, S.TSTypeAliasDeclaration)) or getattr(converted, "declare", False) else (
                "value")
            return made
        made.exportKind = "type" if kids[1].type == "type" else "value"
        clause = next(c for c in self.named(ts) if c.type == "export_clause")
        made.specifiers = [self.export_specifier(s) for s in self.named(clause)]
        if source is not None:
            made.source = self.literal(source)
        return made  # tree-sitter-typescript reads no attributes here

    def default_declaration(self, ts: _TS) -> S.Statement:
        """`export default function ...` or `export default class ...`, which are declarations, unnamed: a named one
        is a declaration to tree-sitter-typescript too."""
        if ts.type == "class":
            made: Any = S.ClassDeclaration()
            self.class_parts(ts, made)
            return self.made(ts, made)
        made = S.FunctionDeclaration(isAsync=self.has(ts, "async"), generator=ts.type == "generator_function",
                                     body=self.block(self.require(ts, "body")))
        self.signature(ts, made)
        return self.made(ts, made)

    def export_specifier(self, ts: _TS) -> S.ExportSpecifier:
        name = self.require(ts, "name")
        local = self.literal(name) if name.type == "string" else self.identifier(name)
        alias = self.field(ts, "alias")
        if alias is None:
            exported: Any = self.made(name, (S.Literal(raw=self.text(name)) if name.type == "string"
                                             else S.Identifier(name=self.spelling(name))))
        else:
            exported = self.literal(alias) if alias.type == "string" else self.identifier(alias)
        kind = "type" if self.kids(ts)[0].type == "type" else "value"
        return self.made(ts, S.ExportSpecifier(exportKind=kind, local=local, exported=exported))

    def ambient_declaration(self, ts: _TS) -> S.Statement:
        """`declare ...`, or `declare global { ... }`."""
        inner = self.named(ts)[0]
        if inner.type == "statement_block":
            made: Any = S.TSModuleDeclaration(declare=True, moduleKind="global",
                                              id=self.made(ts.children[1], S.Identifier(name="global")))
            made.body = self.module_block(inner)
            return made
        made = self.statement(inner)
        made.declare = True
        return made

    def module_block(self, ts: _TS) -> S.TSModuleBlock:
        return self.made(ts, S.TSModuleBlock(body=self.listed(ts.children, self.statement, ts.children[0])))

    def module(self, ts: _TS, kind: str | None = None) -> S.TSModuleDeclaration:
        name = self.require(ts, "name")
        keyword = kind or ("namespace" if ts.type == "internal_module" else "module")
        made = S.TSModuleDeclaration(moduleKind=keyword,
                                     id=self.literal(name) if name.type == "string" else self.entity_name(name))
        body = self.field(ts, "body")
        made.body = None if body is None else self.module_block(body)
        return self.made(ts, made)

    def module_statement(self, ts: _TS) -> S.TSModuleDeclaration:
        return self.module(ts)

    def type_alias_declaration(self, ts: _TS) -> S.TSTypeAliasDeclaration:
        value = self.require(ts, "value")
        made = S.TSTypeAliasDeclaration(id=self.identifier(self.require(ts, "name")),
                                        typeAnnotation=self.made(value, S.TSIntrinsicKeyword()) if (
                                            value.type == "type_identifier" and self.text(value) == "intrinsic")
                                        else self.type(value))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        return made

    def interface_declaration(self, ts: _TS) -> S.TSInterfaceDeclaration:
        made = S.TSInterfaceDeclaration(id=self.identifier(self.require(ts, "name")))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        clause = next((c for c in self.named(ts) if c.type == "extends_type_clause"), None)
        if clause is not None:
            made.extends = [self.made(t, S.TSInterfaceHeritage(**self.heritage(t))) for t in self.named(clause)]
        body = self.require(ts, "body")
        made.body = self.made(body, S.TSInterfaceBody(
            body=self.listed(body.children, self.type_member, body.children[0])))
        return made

    def enum_declaration(self, ts: _TS) -> S.TSEnumDeclaration:
        body = self.require(ts, "body")
        made = S.TSEnumDeclaration(const=self.has(ts, "const"), id=self.identifier(self.require(ts, "name")))
        made.body = self.made(body, S.TSEnumBody(members=self.listed(body.children, self.enum_member,
                                                                     body.children[0])))
        return made

    def enum_member(self, ts: _TS) -> S.TSEnumMember:
        if ts.type == "enum_assignment":
            key, computed = self.key(self.require(ts, "name"))
            return self.made(ts, S.TSEnumMember(computed=computed, id=key,
                                                initializer=self.expression(self.require(ts, "value"))))
        key, computed = self.key(ts)
        return self.made(ts, S.TSEnumMember(computed=computed, id=key))

    STATEMENTS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "expression_statement": expression_statement, "lexical_declaration": lexical_declaration,
        "variable_declaration": variable_declaration, "return_statement": return_statement,
        "throw_statement": throw_statement, "if_statement": if_statement, "while_statement": while_statement,
        "do_statement": do_statement, "with_statement": with_statement, "for_statement": for_statement,
        "for_in_statement": for_in_statement, "switch_statement": switch_statement, "try_statement": try_statement,
        "labeled_statement": labeled_statement, "break_statement": jump(S.BreakStatement),
        "continue_statement": jump(S.ContinueStatement), "empty_statement": simple(S.EmptyStatement),
        "debugger_statement": simple(S.DebuggerStatement), "statement_block": lambda self, ts: self.block(ts),
        "function_declaration": function_declaration, "generator_function_declaration": function_declaration,
        "function_signature": function_signature, "class_declaration": class_declaration,
        "abstract_class_declaration": class_declaration, "import_statement": import_statement,
        "import_alias": import_alias, "export_statement": export_statement,
        "ambient_declaration": ambient_declaration, "module": module_statement,
        "internal_module": module_statement, "type_alias_declaration": type_alias_declaration,
        "interface_declaration": interface_declaration, "enum_declaration": enum_declaration,
    }

    # Bindings and patterns

    def binding(self, ts: _TS) -> Any:
        """What a declaration or a parameter binds: a name or a destructuring pattern."""
        if ts.type == "identifier" or ts.type == "undefined":
            return self.identifier(ts)
        return self.target(ts)

    def target(self, ts: _TS) -> Any:
        """An assignment's or a binding's target, which tree-sitter-typescript writes as a pattern."""
        if ts.type == "array_pattern":
            return self.made(ts, S.ArrayPattern(elements=self.elements(ts, self.target)))
        if ts.type == "object_pattern":
            return self.made(ts, S.ObjectPattern(properties=[self.pattern_property(p) for p in self.named(ts)]))
        if ts.type == "assignment_pattern":
            return self.made(ts, S.AssignmentPattern(left=self.target(self.require(ts, "left")),
                                                     right=self.expression(self.require(ts, "right"))))
        if ts.type == "rest_pattern":
            return self.made(ts, S.RestElement(argument=self.target(self.named(ts)[0])))
        if ts.type == "identifier" or ts.type == "undefined":
            return self.identifier(ts)
        return self.expression(ts)

    def pattern_property(self, ts: _TS) -> Any:
        if ts.type == "rest_pattern":
            return self.made(ts, S.RestElement(argument=self.target(self.named(ts)[0])))
        if ts.type == "shorthand_property_identifier_pattern":
            return self.made(ts, S.Property(propertyKind="init", key=self.identifier(ts), shorthand=True,
                                            value=self.made(ts, S.Identifier(name=self.spelling(ts)))))
        if ts.type == "object_assignment_pattern":  # `{ a = 1 }`, whose left is always a shorthand name
            left = self.require(ts, "left")
            value = self.made(ts, S.AssignmentPattern(left=self.identifier(left),
                                                      right=self.expression(self.require(ts, "right"))))
            return self.made(ts, S.Property(propertyKind="init", key=self.made(left, S.Identifier(
                name=self.text(left))), shorthand=True, value=value))
        key, computed = self.key(self.require(ts, "key"))
        return self.made(ts, S.Property(propertyKind="init", key=key, computed=computed,
                                        value=self.target(self.require(ts, "value"))))

    def elements(self, ts: _TS, convert: Callable[[_TS], Any]) -> list[Any]:
        """The elements of an array or an array pattern, with an `Elision` for each hole."""
        out: list[Any] = []
        pending = True  # a comma now leaves a hole
        for c in self.kids(ts)[1:-1]:
            if c.type == ",":
                if pending:
                    out.append(self.made(c, S.Elision()))
                pending = True
            else:
                out.append(convert(c))
                pending = False
        return out

    # Expressions

    def expression(self, ts: _TS) -> Any:
        return self.made(ts, self.EXPRESSIONS[ts.type](self, ts))  # the grammar has no other expression

    def parenthesized(self, ts: _TS) -> Any:
        inner = self.named(ts)[0]
        annotation = self.field(ts, "type")
        if annotation is not None:
            raise self.unsupported(ts)
        return S.ParenthesizedExpression(expression=self.expression(inner))

    def sequence(self, ts: _TS) -> S.SequenceExpression:
        return S.SequenceExpression(expressions=[self.expression(k) for k in self.named(ts)])

    def array(self, ts: _TS) -> S.ArrayExpression:
        return S.ArrayExpression(elements=self.elements(ts, self.element))

    def element(self, ts: _TS) -> Any:
        if ts.type == "spread_element":
            return self.made(ts, S.SpreadElement(argument=self.expression(self.named(ts)[0])))
        return self.expression(ts)

    def object(self, ts: _TS) -> S.ObjectExpression:
        properties: list[Any] = []
        for p in self.named(ts):
            if p.type == "spread_element":
                properties.append(self.element(p))
            elif p.type == "shorthand_property_identifier":
                properties.append(self.made(p, S.Property(propertyKind="init", key=self.identifier(p), shorthand=True,
                                                          value=self.made(p, S.Identifier(name=self.spelling(p))))))
            elif p.type == "pair":
                key, computed = self.key(self.require(p, "key"))
                properties.append(self.made(p, S.Property(propertyKind="init", key=key, computed=computed,
                                                          value=self.expression(self.require(p, "value")))))
            else:
                properties.append(self.object_method(p))  # a method_definition
        return S.ObjectExpression(properties=properties)

    def object_method(self, ts: _TS) -> S.Property:
        modifiers = self.tokens_before(ts, "name")
        key, computed = self.key(self.require(ts, "name"))
        value = S.FunctionExpression(isAsync="async" in modifiers, generator="*" in modifiers,
                                     body=self.block(self.require(ts, "body")))
        self.signature(ts, value)
        kind = "get" if "get" in modifiers else "set" if "set" in modifiers else "init"
        return self.made(ts, S.Property(propertyKind=kind, key=key, computed=computed, method=kind == "init",
                                        value=self.made(self.require(ts, "parameters"), value)))

    def function_expression(self, ts: _TS) -> S.FunctionExpression:
        made = S.FunctionExpression(isAsync=self.has(ts, "async"), generator=ts.type == "generator_function" or
                                    self.has(ts, "*"), body=self.block(self.require(ts, "body")))
        name = self.field(ts, "name")
        made.id = None if name is None else self.identifier(name)
        self.signature(ts, made)
        return made

    def arrow_function(self, ts: _TS) -> S.ArrowFunctionExpression:
        made = S.ArrowFunctionExpression(isAsync=self.has(ts, "async"))
        parameter = self.field(ts, "parameter")
        if parameter is not None:
            made.params = [self.identifier(parameter)]
        else:
            self.signature(ts, made)
        body = self.require(ts, "body")
        made.body = self.block(body) if body.type == "statement_block" else self.expression(body)
        return made

    def class_expression(self, ts: _TS) -> S.ClassExpression:
        made = S.ClassExpression()
        self.class_parts(ts, made)
        return made

    def template(self, ts: _TS) -> S.TemplateLiteral:
        quasis, expressions = self.template_parts(ts, "template_substitution", self.expression)
        return S.TemplateLiteral(quasis=quasis, expressions=expressions)

    def template_parts(self, ts: _TS, holder: str, convert: Callable[[_TS], Any]) -> tuple[list[Any], list[Any]]:
        """The texts of a template and what is substituted between them."""
        quasis: list[Any] = []
        values: list[Any] = []
        at = ts.start_byte + 2  # past the backtick, a UTF-16 unit
        for part in self.named(ts):
            if part.type != holder:
                continue
            quasis.append(self.made_at(at, S.TemplateElement(raw=self.between(at, part.start_byte))))
            values.append(convert(self.named(part)[0]))
            at = part.end_byte
        last = S.TemplateElement(raw=self.between(at, ts.end_byte - 2), tail=True)
        quasis.append(self.made_at(at, last))
        return quasis, values

    def made_at(self, byte: int, node: Any) -> Any:
        """A new node, placed at `byte`."""
        self.positions[id(node)] = self.shift + self.source.offset(byte)
        self.placed.append(node)
        return node

    def member_expression(self, ts: _TS) -> Any:
        typed = self.typed_member(ts)
        if typed is not None:
            return typed
        made, optional = self.chain(ts)
        return S.ChainExpression(expression=self.made(ts, made)) if optional else made

    def typed_member(self, ts: _TS) -> Any:
        """`x as A.B.C`, which tree-sitter-typescript reads as `(x as A.B).C`: a member of an `as` or `satisfies`
        expression without parentheses, whose names belong to its type. None for any other member."""
        names: list[_TS] = []
        node = ts
        while node.type == "member_expression" and self.field(node, "optional_chain") is None:
            names.insert(0, self.require(node, "property"))
            node = self.require(node, "object")
        if node.type not in ("as_expression", "satisfies_expression") or len(self.named(node)) != 2:
            return None
        expression, type_ = self.named(node)
        last = type_  # in `x as A | B.C.D`, the names continue the last type of the union
        while last.type in ("union_type", "intersection_type"):
            last = self.named(last)[-1]
        if last.type not in ("type_identifier", "nested_type_identifier"):
            return None
        converted = self.type(type_)
        reference = converted
        while isinstance(reference, (S.TSUnionType, S.TSIntersectionType)):
            reference = reference.types[-1]
        name = reference.typeName
        for n in names:
            name = self.made(last, S.TSQualifiedName(left=name, right=self.identifier(n)))
        reference.typeName = name
        kind = S.TSAsExpression if node.type == "as_expression" else S.TSSatisfiesExpression
        return kind(expression=self.expression(expression), typeAnnotation=converted)

    def chain(self, ts: _TS) -> tuple[Any, bool]:
        """A member, a call or a non-null assertion, and whether an optional link (`?.`) is in its chain."""
        if ts.type == "member_expression":
            target, optional = self.chain(self.require(ts, "object"))
            link = self.field(ts, "optional_chain") is not None
            key, _ = self.key(self.require(ts, "property"))
            return self.made(ts, S.MemberExpression(object=target, optional=link, property=key)), optional or link
        if ts.type == "subscript_expression":
            target, optional = self.chain(self.require(ts, "object"))
            link = self.field(ts, "optional_chain") is not None
            index = self.require(ts, "index")
            return self.made(ts, S.MemberExpression(object=target, optional=link, computed=True,
                                                    property=self.expression(index))), optional or link
        if ts.type == "call_expression" and self.require(ts, "arguments").type != "template_string" and (
                self.require(ts, "function").type != "import"):
            target, optional = self.chain(self.require(ts, "function"))
            link = self.has(ts, "?.") or any(c.type == "optional_chain" for c in ts.children)
            made = S.CallExpression(callee=target, optional=link,
                                    arguments=[self.element(a) for a in self.named(self.require(ts, "arguments"))])
            arguments = self.field(ts, "type_arguments")
            if arguments is not None:
                made.typeArguments = self.type_arguments(arguments)
            return self.made(ts, made), optional or link
        if ts.type == "non_null_expression":
            inner = self.named(ts)[0]
            if inner.type == "binary_expression":
                return self.non_null_last(self.expression(inner)), False
            target, optional = self.chain(inner)
            return self.made(ts, S.TSNonNullExpression(expression=target)), optional
        return self.expression(ts), False

    def non_null_last(self, node: Any) -> Any:
        """`node` with its last operand asserted non-null: `a ?? b!` is `a ?? (b!)`, which tree-sitter-typescript
        reads as `(a ?? b)!`."""
        if isinstance(node, (S.BinaryExpression, S.LogicalExpression)):
            node.right = self.non_null_last(node.right)
            return node
        made = S.TSNonNullExpression(expression=node)
        self.positions[id(made)] = self.positions[id(node)]
        self.placed.append(made)
        return made

    def link(self, ts: _TS) -> Any:
        made, optional = self.chain(ts)
        made = self.made(ts, made)
        return S.ChainExpression(expression=made) if optional else made

    def call(self, ts: _TS) -> Any:
        function = self.require(ts, "function")
        arguments = self.require(ts, "arguments")
        if arguments.type == "template_string":
            # tree-sitter-typescript reads `f<T>`x`` as comparisons: a tagged template has no type arguments
            return S.TaggedTemplateExpression(tag=self.expression(function), quasi=self.expression(arguments))
        if function.type == "import":
            values = [self.expression(a) for a in self.named(arguments)]
            return S.ImportExpression(source=values[0], options=values[1] if len(values) > 1 else None)
        made, optional = self.chain(ts)
        return S.ChainExpression(expression=self.made(ts, made)) if optional else made

    def new_expression(self, ts: _TS) -> S.NewExpression:
        made = S.NewExpression(callee=self.expression(self.require(ts, "constructor")))
        arguments = self.field(ts, "arguments")
        if arguments is not None:
            made.arguments = [self.element(a) for a in self.named(arguments)]
        type_arguments = self.field(ts, "type_arguments")
        if type_arguments is not None:
            made.typeArguments = self.type_arguments(type_arguments)
        return made

    def meta_property(self, ts: _TS) -> S.MetaProperty:
        meta, property_ = self.text(ts).replace(" ", "").split(".")
        kids = self.kids(ts)
        return S.MetaProperty(meta=self.made(kids[0], S.Identifier(name=meta)),
                              property=self.made(kids[-1], S.Identifier(name=property_)))

    def update(self, ts: _TS) -> S.UpdateExpression:
        operator = self.require(ts, "operator")
        argument = self.require(ts, "argument")
        return S.UpdateExpression(operator=self.text(operator), prefix=operator.start_byte < argument.start_byte,
                                  argument=self.expression(argument))

    def unary(self, ts: _TS) -> S.UnaryExpression:
        return S.UnaryExpression(operator=self.text(self.require(ts, "operator")),
                                 argument=self.expression(self.require(ts, "argument")))

    def binary(self, ts: _TS) -> Any:
        operator = self.text(self.require(ts, "operator"))
        left = self.require(ts, "left")
        converted = self.made(left, S.PrivateIdentifier(name=self.text(left)[1:])) if (
            left.type == "private_property_identifier") else self.expression(left)
        right = self.expression(self.require(ts, "right"))
        if left.type in ("as_expression", "satisfies_expression"):
            return self.binary_last(converted, operator, right)
        if operator in ("&&", "||", "??"):
            return S.LogicalExpression(left=converted, operator=operator, right=right)
        return S.BinaryExpression(left=converted, operator=operator, right=right)

    def binary_last(self, left: Any, operator: str, right: Any) -> Any:
        """`left operator right`, where `left` was an `as` or `satisfies` expression that `typed_last` moved onto its
        last operand: `a || b as T && c` is `a || (b as T && c)`, which tree-sitter-typescript reads as
        `((a || b) as T) && c`. The operator applies to that last operand when it binds tighter than `left`'s."""
        if isinstance(left, (S.BinaryExpression, S.LogicalExpression)) and _BINDS[left.operator] < _BINDS[operator]:
            left.right = self.binary_last(left.right, operator, right)
            return left
        kind = S.LogicalExpression if operator in ("&&", "||", "??") else S.BinaryExpression
        made = kind(left=left, operator=operator, right=right)
        self.positions[id(made)] = self.positions[id(left)]  # where its left operand starts
        self.placed.append(made)
        return made

    def assignment(self, ts: _TS) -> S.AssignmentExpression:
        operator = self.field(ts, "operator")
        return S.AssignmentExpression(left=self.target(self.require(ts, "left")),
                                      operator="=" if operator is None else self.text(operator),
                                      right=self.expression(self.require(ts, "right")))

    def ternary(self, ts: _TS) -> S.ConditionalExpression:
        return S.ConditionalExpression(test=self.expression(self.require(ts, "condition")),
                                       consequent=self.expression(self.require(ts, "consequence")),
                                       alternate=self.expression(self.require(ts, "alternative")))

    def yield_(self, ts: _TS) -> S.YieldExpression:
        kids = self.named(ts)
        return S.YieldExpression(delegate=self.has(ts, "*"), argument=self.expression(kids[0]) if kids else None)

    def typed_last(self, node: Any, kind: type, type_: Any) -> Any:
        """`node` with `as type` (or `satisfies type`) applied to its last operand when that binds tighter than its
        operator: `a ?? b as T` is `a ?? (b as T)`, which tree-sitter-typescript reads as `(a ?? b) as T`."""
        if isinstance(node, (S.BinaryExpression, S.LogicalExpression)) and node.operator in _LOOSER_THAN_AS:
            node.right = self.typed_last(node.right, kind, type_)
            return node
        made = kind(expression=node, typeAnnotation=type_)
        self.positions[id(made)] = self.positions[id(node)]
        self.placed.append(made)
        return made

    def typed(kind: type) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        """`expression as type` or `expression satisfies type`."""
        def convert(self: _Converter, ts: _TS) -> Any:
            kids = self.named(ts)
            expression = kids[0]
            if len(kids) == 1 or kids[1].type == "const":  # `as const`
                const = next(c for c in ts.children if c.type == "const")
                converted: Any = self.made(const, S.TSTypeReference(typeName=self.made(const, S.Identifier(
                    name="const"))))
            else:
                converted = self.type(kids[1])
            inner = self.expression(expression)
            if expression.type == "binary_expression":
                return self.typed_last(inner, kind, converted)
            return kind(expression=inner, typeAnnotation=converted)
        return convert

    def type_assertion(self, ts: _TS) -> S.TSTypeAssertion:
        arguments, expression = self.named(ts)
        return S.TSTypeAssertion(typeAnnotation=self.type(self.named(arguments)[0]),
                                 expression=self.expression(expression))

    def instantiation(self, ts: _TS) -> S.TSInstantiationExpression:
        return S.TSInstantiationExpression(expression=self.expression(self.named(ts)[0]),
                                           typeArguments=self.type_arguments(self.require(ts, "type_arguments")))

    def regex(self, ts: _TS) -> S.Literal:
        return S.Literal(raw=self.text(ts))

    EXPRESSIONS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "identifier": lambda self, ts: S.ImportExpression(**self.import_call(ts)) if (
            self.at(ts) in self.pre.imports) else S.Identifier(name=self.spelling(ts)),
        "undefined": lambda self, ts: S.Identifier(name="undefined"),
        "number": lambda self, ts: S.Literal(raw=self.text(ts)),
        "string": lambda self, ts: S.Literal(raw=self.text(ts)),
        "true": lambda self, ts: S.Literal(raw="true"), "false": lambda self, ts: S.Literal(raw="false"),
        "null": lambda self, ts: S.Literal(raw="null"), "regex": regex,
        "this": lambda self, ts: S.ThisExpression(), "super": lambda self, ts: S.Super(),
        "parenthesized_expression": parenthesized, "sequence_expression": sequence, "array": array, "object": object,
        "function_expression": function_expression, "generator_function": function_expression,
        "arrow_function": arrow_function, "class": class_expression, "template_string": template,
        "member_expression": member_expression, "subscript_expression": member_expression,
        "call_expression": call, "non_null_expression": link, "new_expression": new_expression,
        "meta_property": meta_property, "update_expression": update, "unary_expression": unary,
        "await_expression": lambda self, ts: S.AwaitExpression(argument=self.expression(self.named(ts)[0])),
        "binary_expression": binary, "assignment_expression": assignment, "augmented_assignment_expression": assignment,
        "ternary_expression": ternary, "yield_expression": yield_,
        "as_expression": typed(S.TSAsExpression), "satisfies_expression": typed(S.TSSatisfiesExpression),
        "type_assertion": type_assertion, "instantiation_expression": instantiation,
        "array_pattern": lambda self, ts: S.ArrayPattern(elements=self.elements(ts, self.target)),
        "object_pattern": lambda self, ts: S.ObjectPattern(properties=[self.pattern_property(p)
                                                                       for p in self.named(ts)]),
        "jsx_element": lambda self, ts: self.jsx_element(ts),
        "jsx_self_closing_element": lambda self, ts: self.jsx_element(ts),
        "internal_module": lambda self, ts: self.module(ts, "namespace"),
    }

    # Types

    def annotation(self, ts: _TS) -> S.TSTypeAnnotation:
        """A `type_annotation` (`: type`), or a return type: `: x is T`, `: asserts x`."""
        if ts.type in ("type_predicate_annotation", "asserts_annotation"):
            return self.made(ts, S.TSTypeAnnotation(typeAnnotation=self.predicate(self.named(ts)[0])))
        return self.made(ts, S.TSTypeAnnotation(typeAnnotation=self.type(self.named(ts)[0])))

    def predicate(self, ts: _TS) -> S.TSTypePredicate:
        if ts.type == "asserts":
            inner = self.named(ts)[0]
            if inner.type == "type_predicate":
                made = self.predicate(inner)
                made.asserts = True
                return self.made(ts, made)
            return self.made(ts, S.TSTypePredicate(asserts=True, parameterName=self.predicate_name(inner)))
        name = self.require(ts, "name")
        type_ = self.require(ts, "type")
        return self.made(ts, S.TSTypePredicate(parameterName=self.predicate_name(name), typeAnnotation=self.made(
            type_, S.TSTypeAnnotation(typeAnnotation=self.type(type_)))))

    def predicate_name(self, ts: _TS) -> Any:
        return self.made(ts, S.TSThisType()) if ts.type == "this" else self.identifier(ts)

    def type(self, ts: _TS) -> Any:
        method = self.TYPES.get(ts.type)
        if method is None:
            raise self.unsupported(ts)
        return self.made(ts, method(self, ts))

    def predefined(self, ts: _TS) -> Any:
        text = " ".join(self.text(ts).split())
        if text == "unique symbol":
            return S.TSTypeOperator(operator="unique", typeAnnotation=self.made(ts.children[-1], S.TSSymbolKeyword()))
        return _KEYWORD_TYPES[text]()

    def type_reference(self, ts: _TS) -> Any:
        keyword = _KEYWORD_TYPES.get(self.text(ts))
        if keyword is not None and self.text(ts) != "intrinsic":  # tree-sitter-typescript reads `bigint` as a name
            return keyword()
        return self.import_or_reference(ts)

    def generic(self, ts: _TS) -> Any:
        name, arguments = self.require(ts, "name"), self.require(ts, "type_arguments")
        return self.import_type(name, arguments) or S.TSTypeReference(
            typeName=self.entity_name(name), typeArguments=self.type_arguments(arguments))

    def type_arguments(self, ts: _TS) -> S.TSTypeParameterInstantiation:
        return self.made(ts, S.TSTypeParameterInstantiation(params=[self.type(t) for t in self.named(ts)]))

    def type_parameters(self, ts: _TS) -> S.TSTypeParameterDeclaration:
        return self.made(ts, S.TSTypeParameterDeclaration(params=[self.type_parameter(p) for p in self.named(ts)]))

    def type_parameter(self, ts: _TS) -> S.TSTypeParameter:
        name = self.require(ts, "name")
        variance = self.pre.variance.get(self.at(name), set())
        made = S.TSTypeParameter(const=self.has(ts, "const"), isIn="in" in variance or self.has(ts, "in"),
                                 isOut="out" in variance or any(c.type == "out" for c in ts.children),
                                 name=self.identifier(name))
        constraint = self.field(ts, "constraint")
        if constraint is not None:
            made.constraint = self.type(self.named(constraint)[0])
        default = self.field(ts, "value")
        if default is not None:
            made.default = self.type(self.named(default)[0])
        return self.made(ts, made)

    def flat(kind: type) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        """A union or an intersection, whose nested ones of the same kind flatten."""
        def convert(self: _Converter, ts: _TS) -> Any:
            types: list[Any] = []
            for t in self.named(ts):
                if t.type == ts.type:
                    types += self.made(t, convert(self, t)).types
                    continue
                converted = self.type(t)
                if t.type == "readonly_type" and type(converted) is kind:  # its own operand was a union
                    types += converted.types
                else:
                    types.append(converted)
            return kind(types=types)
        return convert

    def literal_type(self, ts: _TS) -> S.TSLiteralType:
        inner = self.named(ts)[0]
        if inner.type == "unary_expression":
            return S.TSLiteralType(literal=self.expression(inner))
        if inner.type == "null":
            return S.TSNullKeyword()
        if inner.type == "undefined":
            return S.TSUndefinedKeyword()
        return S.TSLiteralType(literal=self.literal(inner))

    def function_type(self, ts: _TS) -> S.TSFunctionType:
        made = S.TSFunctionType()
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        returns = self.require(ts, "return_type")
        made.returnType = self.made(returns, S.TSTypeAnnotation(
            typeAnnotation=self.predicate(returns) if returns.type in ("type_predicate", "asserts")
            else self.type(returns)))
        return made

    def constructor_type(self, ts: _TS) -> S.TSConstructorType:
        made = S.TSConstructorType(abstract=self.has(ts, "abstract"))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        returns = self.require(ts, "type")
        made.returnType = self.made(returns, S.TSTypeAnnotation(typeAnnotation=self.type(returns)))
        return made

    def tuple_type(self, ts: _TS) -> S.TSTupleType:
        out: list[Any] = []
        for element in self.named(ts):
            if element.type in ("required_parameter", "optional_parameter"):
                name = self.require(element, "name")
                annotation = self.named(self.require(element, "type"))[0]
                if name.type == "rest_pattern":
                    member = S.TSNamedTupleMember(label=self.identifier(self.named(name)[0]),
                                                  elementType=self.type(annotation))
                    out.append(self.made(element, S.TSRestType(typeAnnotation=self.made(element, member))))
                    continue
                out.append(self.made(element, S.TSNamedTupleMember(
                    label=self.identifier(name), optional=element.type == "optional_parameter",
                    elementType=self.type(annotation))))
            else:
                out.append(self.type(element))
        return S.TSTupleType(elementTypes=out)

    def object_type(self, ts: _TS) -> Any:
        members = [m for m in self.named(ts)]
        if len(members) == 1 and members[0].type == "index_signature" and any(
                c.type == "mapped_type_clause" for c in self.named(members[0])):
            return self.mapped(members[0])
        return S.TSTypeLiteral(members=self.listed(ts.children, self.type_member, ts.children[0]))

    def mapped(self, ts: _TS) -> S.TSMappedType:
        clause = next(c for c in self.named(ts) if c.type == "mapped_type_clause")
        made = S.TSMappedType(key=self.identifier(self.require(clause, "name")),
                              constraint=self.type(self.require(clause, "type")))
        alias = self.field(clause, "alias")
        if alias is not None:
            made.nameType = self.type(alias)
        kids = self.kids(ts)
        sign = self.field(ts, "sign")
        if any(c.type == "readonly" for c in kids):
            made.readonly = (self.text(sign) if sign is not None and sign.start_byte < clause.start_byte else "") + (
                "readonly")
        annotation = self.require(ts, "type")
        if annotation.type == "adding_type_annotation":
            made.optional = "+?"
        elif annotation.type == "omitting_type_annotation":
            made.optional = "-?"
        elif annotation.type == "opting_type_annotation":
            made.optional = "?"
        made.typeAnnotation = self.type(self.named(annotation)[0])  # tree-sitter-typescript reads none without one
        return made

    def type_member(self, ts: _TS) -> Any:
        if ts.type == "property_signature":
            modifiers = self.tokens_before(ts, "name")
            key, computed = self.key(self.require(ts, "name"))
            made = S.TSPropertySignature(readonly="readonly" in modifiers, static="static" in modifiers, key=key,
                                         computed=computed, optional=self.has(ts, "?"))
            annotation = self.field(ts, "type")
            if annotation is not None:
                made.typeAnnotation = self.annotation(annotation)
            return self.made(ts, made)
        if ts.type == "method_signature":
            modifiers = self.tokens_before(ts, "name")
            key, computed = self.key(self.require(ts, "name"))
            made_method = S.TSMethodSignature(
                methodKind="get" if "get" in modifiers else "set" if "set" in modifiers else "method", key=key,
                computed=computed, optional=self.has(ts, "?"))
            self.signature(ts, made_method)
            return self.made(ts, made_method)
        if ts.type == "call_signature":
            made_call = S.TSCallSignatureDeclaration()
            self.signature(ts, made_call)
            return self.made(ts, made_call)
        if ts.type == "construct_signature":
            made_new = S.TSConstructSignatureDeclaration()
            self.signature(ts, made_new)
            return self.made(ts, made_new)
        return self.index_signature(ts)

    def type_query(self, ts: _TS) -> S.TSTypeQuery:
        inner = self.named(ts)[0]
        if inner.type == "instantiation_expression":
            name = self.named(inner)[0]
            return S.TSTypeQuery(exprName=self.import_type(name) or self.entity_name(name),
                                 typeArguments=self.type_arguments(self.require(inner, "type_arguments")))
        return S.TSTypeQuery(exprName=self.import_type(inner) or self.entity_name(inner))

    def import_root(self, ts: _TS) -> tuple[_TS, list[_TS]] | None:
        """The import at the root of the dotted name `ts`, `import('m').a.b`, and the names after it; None if it has
        none. The import is a call, or the name the pre-pass put in its place."""
        names: list[_TS] = []
        node = ts
        while node.type in ("member_expression", "nested_identifier", "nested_type_identifier"):
            if node.type == "nested_type_identifier":
                names.insert(0, self.require(node, "name"))
                node = self.require(node, "module")
            else:
                names.insert(0, self.require(node, "property"))
                node = self.require(node, "object")
        if node.type == "call_expression" and self.require(node, "function").type == "import":
            return node, names
        if node.type in ("identifier", "type_identifier") and self.at(node) in self.pre.imports:
            return node, names
        return None

    def import_type(self, ts: _TS, arguments: _TS | None = None) -> S.TSImportType | None:
        """`import('m').a.b<arguments>` as a type; None if `ts` is not rooted at an import."""
        root = self.import_root(ts)
        if root is None:
            return None
        call, names = root
        made = S.TSImportType(**self.import_call(call))
        qualifier: Any = None
        for name in names:
            right = self.identifier(name)
            qualifier = right if qualifier is None else self.made(name, S.TSQualifiedName(left=qualifier, right=right))
        made.qualifier = qualifier
        if arguments is not None:
            made.typeArguments = self.type_arguments(arguments)
        return self.made(ts, made)

    def import_call(self, ts: _TS) -> dict[str, Any]:
        """The source and options of `import(source, options)`: a call, or the name the pre-pass put in its place,
        whose text is parsed again."""
        if ts.type == "call_expression":
            arguments = self.named(self.require(ts, "arguments"))
            return {"source": self.expression(arguments[0]),
                    "options": self.expression(arguments[1]) if len(arguments) > 1 else None}
        start = self.at(ts)
        source = _Source(self.origin.text[start:self.shift + self.source.offset(ts.end_byte)])
        tree = _PARSERS[False].parse(source.data, encoding="utf16le")
        converter = _Converter(source, _Prepared(), start, self.origin)
        converter.check(tree.root_node)
        call = converter.named(converter.named(tree.root_node)[0])[0]
        parts = converter.import_call(call)
        self.positions.update(converter.positions)
        self.placed += converter.placed
        return parts

    def import_or_reference(self, ts: _TS) -> Any:
        """A type that is `import('m').a.b`, or a type reference."""
        return self.import_type(ts) or S.TSTypeReference(typeName=self.entity_name(ts))

    def template_type(self, ts: _TS) -> S.TSTemplateLiteralType:
        quasis, types = self.template_parts(ts, "template_type", self.type)
        return S.TSTemplateLiteralType(quasis=quasis, types=types)

    def infer(self, ts: _TS) -> S.TSInferType:
        kids = self.named(ts)
        parameter = S.TSTypeParameter(name=self.identifier(kids[0]))
        if len(kids) > 1:
            parameter.constraint = self.type(kids[1])
        return S.TSInferType(typeParameter=self.made(kids[0], parameter))

    def lookup(self, ts: _TS) -> S.TSIndexedAccessType:
        object_type, index_type = self.named(ts)
        return S.TSIndexedAccessType(objectType=self.type(object_type), indexType=self.type(index_type))

    def readonly(self, ts: _TS) -> Any:
        """`readonly T`, which binds tighter than `|` and `&`: tree-sitter-typescript reads `readonly A[] | B` as
        `readonly (A[] | B)`."""
        inner = self.named(ts)[0]
        if inner.type in ("union_type", "intersection_type"):
            return self.readonly_first(inner, ts)
        return S.TSTypeOperator(operator="readonly", typeAnnotation=self.type(inner))

    def readonly_first(self, ts: _TS, at: _TS) -> Any:
        """The union or intersection `ts`, with its first member made readonly."""
        members = self.named(ts)
        kind = S.TSUnionType if ts.type == "union_type" else S.TSIntersectionType
        if members[0].type == ts.type:
            head: Any = self.readonly_first(members[0], at)
            types = head.types
        else:
            types = [self.made(at, S.TSTypeOperator(operator="readonly", typeAnnotation=self.type(members[0])))]
        types += [self.type(m) for m in members[1:]]  # a union groups to the left: only its first may be one
        return self.made(at, kind(types=types))

    TYPES: dict[str, Callable[[_Converter, _TS], Any]] = {
        "predefined_type": predefined, "type_identifier": type_reference, "identifier": type_reference,
        "nested_type_identifier": lambda self, ts: self.import_or_reference(ts), "generic_type": generic,
        "member_expression": lambda self, ts: self.import_or_reference(ts),
        "this_type": lambda self, ts: S.TSThisType(),
        "parenthesized_type": lambda self, ts: S.TSParenthesizedType(typeAnnotation=self.type(self.named(ts)[0])),
        "literal_type": literal_type, "array_type": lambda self, ts: S.TSArrayType(
            elementType=self.type(self.named(ts)[0])),
        "tuple_type": tuple_type, "union_type": flat(S.TSUnionType), "intersection_type": flat(S.TSIntersectionType),
        "function_type": function_type, "constructor_type": constructor_type, "object_type": object_type,
        "index_type_query": lambda self, ts: S.TSTypeOperator(operator="keyof", typeAnnotation=self.type(
            self.named(ts)[0])),
        "readonly_type": lambda self, ts: self.readonly(ts),
        "lookup_type": lookup, "type_query": type_query, "template_literal_type": template_type,
        "conditional_type": lambda self, ts: S.TSConditionalType(
            checkType=self.type(self.require(ts, "left")), extendsType=self.type(self.require(ts, "right")),
            trueType=self.type(self.require(ts, "consequence")), falseType=self.type(self.require(ts, "alternative"))),
        "infer_type": infer, "optional_type": lambda self, ts: S.TSOptionalType(
            typeAnnotation=self.type(self.named(ts)[0])),
        "rest_type": lambda self, ts: S.TSRestType(typeAnnotation=self.type(self.named(ts)[0])),
        "type_predicate": lambda self, ts: self.predicate(ts), "asserts": lambda self, ts: self.predicate(ts),
        "call_expression": lambda self, ts: self.import_or_reference(ts),
        "const": lambda self, ts: S.TSTypeReference(typeName=self.made(ts, S.Identifier(name="const"))),
        "template_type": lambda self, ts: self.type(self.named(ts)[0]),
    }

    # JSX

    def jsx_element(self, ts: _TS) -> Any:
        if ts.type == "jsx_self_closing_element":
            opening = self.made(ts, S.JSXOpeningElement(selfClosing=True))
            self.jsx_tag(ts, opening)
            return S.JSXElement(openingElement=opening)
        open_tag = self.require(ts, "open_tag")
        close_tag = self.require(ts, "close_tag")
        children = self.jsx_children(open_tag, close_tag, [c for c in self.named(ts) if c.id not in (
            open_tag.id, close_tag.id) and c.type not in ("jsx_text", "html_character_reference")])
        if self.field(open_tag, "name") is None:
            return S.JSXFragment(openingFragment=self.made(open_tag, S.JSXOpeningFragment()), children=children,
                                 closingFragment=self.made(close_tag, S.JSXClosingFragment()))
        opening = self.made(open_tag, S.JSXOpeningElement())
        self.jsx_tag(open_tag, opening)
        closing = self.made(close_tag, S.JSXClosingElement(name=self.jsx_name(self.require(close_tag, "name"))))
        return S.JSXElement(openingElement=opening, children=children, closingElement=closing)

    def jsx_tag(self, ts: _TS, made: S.JSXOpeningElement) -> None:
        made.name = self.jsx_name(self.require(ts, "name"))
        arguments = self.field(ts, "type_arguments")
        if arguments is not None:
            made.typeArguments = self.type_arguments(arguments)
        for attribute in self.fields(ts, "attribute"):
            if attribute.type == "jsx_expression":
                made.attributes.append(self.made(attribute, S.JSXSpreadAttribute(
                    argument=self.expression(self.named(self.named(attribute)[0])[0]))))
                continue
            name, *value = self.named(attribute)
            converted = S.JSXAttribute(name=self.jsx_name(name))
            if value:
                inner = value[0]
                converted.value = self.literal(inner) if inner.type == "string" else self.jsx_child(inner)
            made.attributes.append(self.made(attribute, converted))

    def jsx_name(self, ts: _TS) -> Any:
        if ts.type == "member_expression":
            return self.made(ts, S.JSXMemberExpression(object=self.jsx_name(self.require(ts, "object")),
                                                       property=self.jsx_name(self.require(ts, "property"))))
        if ts.type == "jsx_namespace_name":
            namespace, name = self.named(ts)
            return self.made(ts, S.JSXNamespacedName(namespace=self.jsx_name(namespace), name=self.jsx_name(name)))
        return self.made(ts, S.JSXIdentifier(name=self.text(ts)))

    def jsx_children(self, open_tag: _TS, close_tag: _TS, nodes: list[_TS]) -> list[Any]:
        """An element's children: its elements and expressions, and the text between them, as written. Text is
        whatever lies between the others: tree-sitter-typescript leaves out the text that is only whitespace, and
        splits the rest at character references (`&amp;`)."""
        out: list[Any] = []
        at = open_tag.end_byte
        for ts in nodes + [close_tag]:
            if ts.start_byte > at:
                out.append(self.made_at(at, S.JSXText(raw=self.between(at, ts.start_byte))))
            if ts is not close_tag:
                out.append(self.jsx_child(ts))
            at = ts.end_byte
        return out

    def jsx_child(self, ts: _TS) -> Any:
        """An element's child or an attribute's value, but text, which `jsx_children` reads."""
        if ts.type == "jsx_expression":
            inner = self.named(ts)
            if not inner:
                return self.made(ts, S.JSXExpressionContainer(expression=self.made(ts, S.JSXEmptyExpression())))
            if inner[0].type == "spread_element":
                return self.made(ts, S.JSXSpreadChild(expression=self.expression(self.named(inner[0])[0])))
            return self.made(ts, S.JSXExpressionContainer(expression=self.expression(inner[0])))
        return self.expression(ts)


def parse(text: str, jsx: bool = False) -> tuple[S.Program, dict[int, int], _Source]:
    """The tree of `text`, with the `tsx` grammar if `jsx`, the offset where each of its nodes starts (by `id`), and
    the source, for locating problems. Raises `ParseError` for text tree-sitter-typescript cannot parse."""
    parser = _PARSERS[jsx]
    source = _Source(text)
    tree = parser.parse(source.data, encoding="utf16le")
    prepared = _Prepared()
    if tree.root_node.has_error:
        cleaned, prepared = _prepare(text, tree.root_node, source)
        source = _Source(text, cleaned)
        tree = parser.parse(source.data, encoding="utf16le")
    converter = _Converter(source, prepared)
    program = converter.program(tree.root_node)
    return program, converter.positions, source
