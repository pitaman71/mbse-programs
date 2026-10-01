"""Parses C and C++ source text into Ccpp trees, delegating to tree-sitter-cpp.

tree-sitter-cpp builds a concrete syntax tree; `_Converter` rewrites it into Ccpp kinds, one tree-sitter node type at
a time. A token-level pre-pass (`_premodules`) handles what tree-sitter-cpp 0.23 cannot parse: module and import
declarations, `export` and `extern template`. It removes them from the text, keeping every other character where it
was, and the converter puts them back where they were.

Positions are counted in characters (code points), never bytes, so that every implementation reports the same line and
column.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tree_sitter_cpp
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from . import Syntax as S

__all__ = ["parse"]

_PARSER = _TSParser(_Grammar(tree_sitter_cpp.language()))

_ALTERNATIVES = {"and": "&&", "or": "||", "not": "!", "compl": "~", "bitand": "&", "bitor": "|", "xor": "^",
                 "and_eq": "&=", "or_eq": "|=", "xor_eq": "^=", "not_eq": "!="}
_PRIMITIVES = set(S.PrimitiveKeyword.__args__)  # type: ignore[attr-defined]
_CV_KEYWORDS = set(S.CvKeyword.__args__)  # type: ignore[attr-defined]
_CASTS = {"static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"}
_NAMES = {"identifier", "field_identifier", "type_identifier", "namespace_identifier", "statement_identifier"}
_ATTRIBUTES = {"attribute_declaration", "attribute_specifier", "ms_declspec_modifier", "alignas_qualifier"}
_SPECIFIERS = {"storage_class_specifier", "type_qualifier", "explicit_function_specifier", "virtual"}


def _op(token: str) -> str:
    return _ALTERNATIVES.get(token, token)


# --- Source text ---


class _Source:
    """The text being parsed, as given and as tree-sitter parses it (`data`, which is `cleaned` in UTF-16), with
    conversions from tree-sitter's byte offsets to character offsets, and from character offsets to lines and
    columns. The cleaned text has the same characters as the text, but for those the pre-pass replaced."""

    def __init__(self, text: str, cleaned: str | None = None):
        self.text = text
        self.data = (text if cleaned is None else cleaned).encode("utf-16-le")
        self._chars: list[int] | None = None
        if len(self.data) != 2 * len(text):  # a character beyond the Basic Multilingual Plane takes two units
            self._chars = [0] * (len(self.data) // 2 + 1)
            at = 0
            for i, ch in enumerate(text):
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


# --- The pre-pass: what tree-sitter-cpp cannot parse ---


class _Premodules:
    """What the pre-pass removed from the text: module and import declarations to insert among the top-level items,
    by offset; the offsets of declarations that `export` or `extern template` introduced; and the offsets of blocks
    `export` introduced."""

    def __init__(self) -> None:
        self.declarations: list[tuple[int, S.Declaration]] = []
        self.exported: set[int] = set()
        self.export_blocks: set[int] = set()
        self.extern_templates: set[int] = set()


def _tokens(text: str) -> list[tuple[int, int]]:
    """The spans of the tokens of `text` that matter to the pre-pass, skipping comments and directives: each
    identifier, number, literal, header name after `import`, and punctuation character."""
    out: list[tuple[int, int]] = []
    i, n = 0, len(text)
    line_start = True
    while i < n:
        ch = text[i]
        if ch == "\n":
            line_start, i = True, i + 1
            continue
        if ch in " \t\r\f\v":
            i += 1
            continue
        if ch == "#" and line_start:  # a directive: skip to the end of its line, following continuations
            while i < n and text[i] != "\n":
                i += 2 if text[i] == "\\" and i + 1 < n else 1
            continue
        line_start = False
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch.isalnum() or ch == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_'"):
                j += 1
            if j < n and text[j] in "'\"" and text[i:j] in ("L", "u", "U", "u8", "R", "LR", "uR", "UR", "u8R"):
                out.append((i, _literal(text, i, j)))
                i = out[-1][1]
                continue
            out.append((i, j))
            i = j
            continue
        if ch in "'\"":
            out.append((i, _literal(text, i, i)))
            i = out[-1][1]
            continue
        if ch == "<" and out and text[out[-1][0]:out[-1][1]] == "import":
            end = text.find(">", i)
            out.append((i, n if end < 0 else end + 1))
            i = out[-1][1]
            continue
        out.append((i, i + 1))
        i += 1
    return out


def _literal(text: str, start: int, quote: int) -> int:
    """The end of the character or string literal starting at `start`, whose quote is at `quote`."""
    n = len(text)
    if text[quote] == '"' and quote > start and text[quote - 1] == "R":
        open_ = text.find("(", quote)
        end = text.find(")" + text[quote + 1:open_] + '"', open_) if open_ >= 0 else -1
        return n if end < 0 else end + len(text[quote + 1:open_]) + 2
    q, i = text[quote], quote + 1
    while i < n and text[i] != q and text[i] != "\n":
        i += 2 if text[i] == "\\" else 1
    return i + 1


def _premodules(text: str) -> tuple[str, _Premodules]:
    """The text with module and import declarations, `export` and the `extern` of `extern template` replaced by
    spaces, and what was removed."""
    found = _Premodules()
    tokens = _tokens(text)
    chars = list(text)
    source = _Source(text)

    def word(k: int) -> str:
        return text[tokens[k][0]:tokens[k][1]] if k < len(tokens) else ""

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            if chars[p] != "\n":
                chars[p] = " "

    depth, k = 0, 0
    start_of_statement = True
    while k < len(tokens):
        w = word(k)
        if start_of_statement and w in ("export", "module", "import", "extern"):
            exported = w == "export"
            j = k + 1 if exported else k
            head = word(j)
            if head in ("module", "import") and depth == 0 and word(j + 1) not in ("=", "(", "::", ".", "->", "["):
                end = j
                while end < len(tokens) and word(end) != ";":
                    end += 1
                if end == len(tokens):
                    raise source.error("expected ';'", tokens[-1][1])
                found.declarations.append((tokens[k][0], _module(text, tokens, j, end, exported, source)))
                blank(tokens[k][0], tokens[end][1])
                k, start_of_statement = end + 1, True
                continue
            if exported and head:
                blank(*tokens[k])
                (found.export_blocks if head == "{" else found.exported).add(tokens[j][0])
                k += 1
                continue
            if w == "extern" and head == "extern" and word(k + 1) == "template":
                blank(*tokens[k])
                found.extern_templates.add(tokens[k + 1][0])
                k += 1
                continue
        start_of_statement = w in (";", "{", "}")
        depth += 1 if w == "{" else -1 if w == "}" else 0
        k += 1
    return "".join(chars), found


def _module(text: str, tokens: list[tuple[int, int]], k: int, end: int, exported: bool,
            source: _Source) -> S.Declaration:
    """The module or import declaration whose tokens are `tokens[k:end]`, from its keyword to before its `;`."""
    words = [text[s:e] for s, e in tokens[k + 1:end]]
    keyword = text[tokens[k][0]:tokens[k][1]]
    if "[" in words:
        raise source.error(f"attributes of {keyword} declarations are not supported", tokens[k][0])

    def fail() -> ParseError:
        return source.error(f"expected a module name after {keyword}", tokens[k][0])

    def dotted(parts: list[str]) -> str:
        """`a.b.c`: identifiers separated by dots."""
        if len(parts) % 2 == 0 or any(parts[i] != "." for i in range(1, len(parts), 2)) \
                or not all(_identifier(parts[i]) for i in range(0, len(parts), 2)):
            raise fail()
        return "".join(parts)

    def named(parts: list[str]) -> tuple[str | None, str | None]:
        """`name`, `name:partition` or `:partition`."""
        at = parts.index(":") if ":" in parts else len(parts)
        name = dotted(parts[:at]) if at > 0 else None
        return name, dotted(parts[at + 1:]) if at < len(parts) else None

    if keyword == "module":
        if not words and not exported:
            return S.GlobalModuleFragment()
        if words == [":", "private"] and not exported:
            return S.PrivateModuleFragment()
        name, partition = named(words)
        if name is None:
            raise fail()
        return S.ModuleDeclaration(export=exported, name=name, partition=partition)
    if len(words) == 1 and words[0][0] in '<"':
        return S.ImportDeclaration(export=exported, header=words[0][1:-1], system=words[0][0] == "<")
    if not words:
        raise fail()
    name, partition = named(words)
    return S.ImportDeclaration(export=exported, name=name, partition=partition)


def _identifier(word: str) -> bool:
    return word[0] not in "0123456789" and all(not ch.isascii() or ch.isalnum() or ch in "_$" for ch in word)


# --- The converter ---


class _Converter:
    """Rewrites a tree-sitter-cpp tree into Ccpp nodes, recording where each node starts in `positions`."""

    def __init__(self, source: _Source, premodules: _Premodules):
        self.source, self.pre = source, premodules
        self.positions: dict[int, int] = {}
        self.placed: list[Any] = []  # the nodes placed, kept alive so that no other node takes their `id`

    # Helpers

    def at(self, ts: _TS) -> int:
        return self.source.offset(ts.start_byte)

    def text(self, ts: _TS) -> str:
        return self.source.data[ts.start_byte:ts.end_byte].decode("utf-16-le")

    def error(self, ts: _TS, message: str) -> ParseError:
        return self.source.error(message, self.at(ts))

    def unsupported(self, ts: _TS) -> ParseError:
        return self.error(ts, f"unsupported syntax: {ts.type}")

    def made(self, ts: _TS, node: Any) -> Any:
        if id(node) not in self.positions:
            self.positions[id(node)] = self.at(ts)
            self.placed.append(node)
        return node

    @staticmethod
    def kids(ts: _TS) -> list[_TS]:
        """The children of `ts`, without comments."""
        return [c for c in ts.children if c.type != "comment"]

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        return [c for c in ts.children if c.is_named and c.type != "comment"]

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

    # Errors

    def check(self, ts: _TS) -> None:
        """Raises for the first syntax error in `ts`, in source order."""
        stack = [ts]
        while stack:
            node = stack.pop()
            if node.type == "ERROR":
                raise self.error(node, "syntax error")
            if node.is_missing and not (node.parent is not None and node.parent.type == "template_instantiation"):
                raise self.error(node, f"expected {node.type}")
            if node.has_error:
                stack.extend(reversed(node.children))

    # Lists of items

    def unit(self, ts: _TS) -> S.TranslationUnit:
        self.check(ts)
        items = self.items(ts.children, declarations=True)
        for offset, declaration in self.pre.declarations:
            self.positions[id(declaration)] = offset
            self.placed.append(declaration)
        merged = sorted([(self.positions[id(i)], i) for i in items] + self.pre.declarations, key=lambda t: t[0])
        return self.made(ts, S.TranslationUnit(items=[i for _, i in merged]))

    def items(self, nodes: list[_TS], declarations: bool, enumerators: bool = False) -> list[Any]:
        """The items of a list of declarations, statements, members or enumerators. With `declarations`, `;` alone is
        an empty declaration rather than an empty statement."""
        out: list[Any] = []
        nodes = [n for n in nodes if n.is_named]
        i = 0
        while i < len(nodes):
            ts = nodes[i]
            i += 1
            if ts.type == "comment":
                comment = self.comment(ts)
                comment.trailing = i > 1 and nodes[i - 2].end_point[0] == ts.start_point[0]
                out.append(comment)
            elif ts.type == "case_statement":
                made, i = self.case(nodes, i - 1)
                out.extend(made)
            elif ts.type == "enumerator" and enumerators:
                out.append(self.enumerator(ts))
            elif ts.type == "access_specifier":
                out.append(self.made(ts, S.AccessSpecifier(access=self.text(ts))))
            elif ts.type.startswith("preproc_"):
                out.append(self.directive(ts, declarations, enumerators))
            elif ts.type == "expression_statement" and declarations and not self.named(ts):
                out.append(self.made(ts, S.EmptyDeclaration()))
            elif ts.type == "attributed_statement" and declarations and not self.named(self.named(ts)[-1]):
                # `[[attributes]];`, which tree-sitter reads as an empty statement with attributes
                out.append(self.made(ts, S.AttributeDeclaration(
                    attributes=[self.attribute(a) for a in self.named(ts)[:-1]])))
            else:
                out.append(self.item(ts))
        return out

    def item(self, ts: _TS) -> Any:
        """A declaration or statement, exported if `export` introduced it."""
        offset = self.at(ts)
        if ts.type == "compound_statement" and offset in self.pre.export_blocks:
            made: Any = S.ExportDeclaration(braced=True, items=self.items(ts.children, declarations=True))
        else:
            made = self.declaration_or_statement(ts)
            if offset in self.pre.exported:
                made = S.ExportDeclaration(items=[made])
        return self.made(ts, made)

    def case(self, nodes: list[_TS], i: int) -> tuple[list[Any], int]:
        """The case or default label `nodes[i]`, and the index of the node after what it took: tree-sitter lists the
        statements after a label as its children; here it labels the first, and the others follow it. A label
        without statements labels the next label."""
        ts = nodes[i]
        i += 1
        value = self.field(ts, "value")
        body = [c for c in ts.children if c.is_named and c.type != "comment" and (value is None or c.id != value.id)]
        comments = [self.comment(c) for c in ts.children if c.type == "comment"]
        statement = None
        rest: list[Any] = []
        if body:
            statement = self.statement(body[0])
            rest = [self.statement(c) for c in body[1:]]
        elif i < len(nodes) and nodes[i].type == "case_statement":
            nested, i = self.case(nodes, i)
            statement, rest = nested[0], nested[1:]
        if value is None:
            label: Any = S.DefaultStatement(statement=statement)
        else:
            label = S.CaseStatement(value=self.expression(value), statement=statement)
        return [self.made(ts, label), *comments, *rest], i

    def comment(self, ts: _TS) -> S.Comment:
        spelling = self.text(ts)
        if spelling.startswith("/*"):
            return self.made(ts, S.Comment(block=True, text=spelling[2:-2]))
        return self.made(ts, S.Comment(text=spelling[2:].rstrip("\r")))

    def declaration_or_statement(self, ts: _TS) -> Any:
        method = self.DECLARATIONS.get(ts.type)
        return method(self, ts) if method is not None else self.statement(ts)

    # Directives

    def directive(self, ts: _TS, declarations: bool, enumerators: bool) -> Any:
        kind = ts.type
        if kind == "preproc_include":
            directive = self.text(self.kids(ts)[0])[1:].strip()
            path = self.require(ts, "path")
            if path.type == "system_lib_string":
                return self.made(ts, S.IncludeDirective(directive=directive, path=self.text(path)[1:-1], system=True))
            if path.type == "string_literal":
                return self.made(ts, S.IncludeDirective(directive=directive, path=self.text(path)[1:-1]))
            return self.made(ts, S.IncludeDirective(directive=directive, macro=self.expression(path)))
        if kind in ("preproc_def", "preproc_function_def"):
            value = self.field(ts, "value")
            replacement = self.text(value).strip() if value is not None else None
            made = S.DefineDirective(name=self.identifier(self.require(ts, "name")), replacement=replacement or None)
            parameters = self.field(ts, "parameters")
            if parameters is not None:
                made.function_like = True
                made.parameters = [self.identifier(p) for p in self.named(parameters)]
                made.variadic = self.has(parameters, "...")
            return self.made(ts, made)
        if kind == "preproc_call":
            directive = self.text(self.require(ts, "directive"))[1:].strip()
            argument = self.field(ts, "argument")
            text = self.text(argument).strip() if argument is not None else ""
            return self.made(ts, S.OtherDirective(directive=directive, text=text or None))
        body = [c for c in ts.children if c.is_named and c.id not in self.ids(ts, "condition", "name", "alternative")]
        items = self.items(body, declarations, enumerators)
        alternative = self.field(ts, "alternative")
        tail = self.directive(alternative, declarations, enumerators) if alternative is not None else None
        if kind == "preproc_else":
            return self.made(ts, S.ElseDirective(items=items))
        if kind in ("preproc_if", "preproc_elif"):
            condition = self.expression(self.require(ts, "condition"))
            made = (S.IfDirective if kind == "preproc_if" else S.ElifDirective)(condition=condition, items=items,
                                                                               alternative=tail)
            return self.made(ts, made)
        negated = self.text(self.kids(ts)[0]).rstrip().endswith("ndef")
        name = self.identifier(self.require(ts, "name"))
        made = (S.IfdefDirective if kind == "preproc_ifdef" else S.ElifdefDirective)(
            negated=negated, name=name, items=items, alternative=tail)
        return self.made(ts, made)

    def ids(self, ts: _TS, *names: str) -> set[int]:
        return {c.id for name in names for c in self.fields(ts, name)}

    # Names

    def identifier(self, ts: _TS) -> S.Identifier:
        return self.made(ts, S.Identifier(spelling=self.text(ts)))

    def name(self, ts: _TS) -> Any:
        kind = ts.type
        if kind in _NAMES or kind == "primitive_type":
            return self.identifier(ts)
        if kind in ("template_type", "template_function", "template_method"):
            return self.made(ts, S.TemplateId(name=self.name(self.require(ts, "name")),
                                              arguments=self.template_arguments(self.require(ts, "arguments"))))
        if kind == "dependent_name":
            made = self.name(self.named(ts)[0])
            made.template_keyword = True
            return made
        if kind == "qualified_identifier":
            return self.qualified(ts)
        if kind == "destructor_name":
            return self.made(ts, S.DestructorName(type=self.name(self.named(ts)[0])))
        return self.operator_name(ts)  # the last kind of name tree-sitter writes outside declarators

    def operator_name(self, ts: _TS) -> Any:
        parts = [self.text(c) for c in self.kids(ts)[1:]]
        if parts and parts[0] == '""':
            return self.made(ts, S.LiteralOperatorName(suffix=parts[1]))
        return self.made(ts, S.OperatorName(operator=_op("".join(parts))))

    def qualified(self, ts: _TS) -> S.QualifiedName:
        global_scope, qualifiers, last = self.qualified_parts(ts)
        return self.made(ts, S.QualifiedName(global_scope=global_scope, qualifiers=qualifiers, name=self.name(last)))

    def scope(self, ts: _TS) -> Any:
        if ts.type == "decltype":
            return self.specifiers(ts)[0]
        return self.name(ts)

    def template_arguments(self, ts: _TS) -> list[Any]:
        return [self.type_id(c) if c.type == "type_descriptor" else self.expression(c) for c in self.named(ts)]

    # Literals

    def number(self, ts: _TS) -> Any:
        spelling = self.text(ts)
        lower = spelling.lower()
        if lower.startswith("0x"):
            floating = "p" in lower or "." in lower
        else:
            floating = not lower.startswith("0b") and ("." in lower or "e" in lower)
        return self.made(ts, (S.FloatingLiteral if floating else S.IntegerLiteral)(spelling=spelling))

    def quoted(self, ts: _TS) -> Any:
        spelling = self.text(ts)
        if ts.type == "raw_string_literal":
            quote = spelling.index('"')
            open_ = spelling.index("(", quote)
            delimiter = spelling[quote + 1:open_]
            return self.made(ts, S.RawStringLiteral(prefix=spelling[:quote - 1] or None, delimiter=delimiter or None,
                                                    text=spelling[open_ + 1:len(spelling) - len(delimiter) - 2]))
        quote = spelling.index("'" if ts.type == "char_literal" else '"')
        kind = S.CharacterLiteral if ts.type == "char_literal" else S.StringLiteral
        return self.made(ts, kind(prefix=spelling[:quote] or None, text=spelling[quote + 1:-1]))

    # Expressions

    def expression(self, ts: _TS) -> Any:
        method = self.EXPRESSIONS.get(ts.type)
        if method is None:
            raise self.unsupported(ts)
        return self.made(ts, method(self, ts))

    def expressions(self, ts: _TS) -> list[Any]:
        return [self.expression(c) for c in self.named(ts)]

    def id_expression(self, ts: _TS) -> Any:
        return S.IdExpression(name=self.name(ts))

    def null(self, ts: _TS) -> Any:
        if self.text(ts) == "nullptr":
            return S.NullptrLiteral()
        return S.IdExpression(name=self.identifier(ts))

    def parenthesized(self, ts: _TS) -> Any:
        inner = self.named(ts)[0]
        if inner.type == "compound_statement":
            return S.StatementExpression(body=self.statement(inner))
        return S.ParenthesizedExpression(expression=self.expression(inner))

    def binary(self, ts: _TS) -> Any:
        return S.BinaryExpression(left=self.expression(self.require(ts, "left")),
                                  operator=_op(self.text(self.require(ts, "operator"))),
                                  right=self.expression(self.require(ts, "right")))

    def comma(self, ts: _TS) -> Any:
        """`a, b, c`, which tree-sitter nests to the right; the comma operator groups to the left."""
        operands = [self.require(ts, "left")]
        right = self.require(ts, "right")
        while right.type == "comma_expression":
            operands.append(self.require(right, "left"))
            right = self.require(right, "right")
        made = self.expression(operands[0])
        for operand in [*operands[1:], right]:
            made = self.made(operand, S.BinaryExpression(left=made, operator=",", right=self.expression(operand)))
        return made

    def assignment(self, ts: _TS) -> Any:
        return S.AssignmentExpression(left=self.expression(self.require(ts, "left")),
                                      operator=_op(self.text(self.require(ts, "operator"))),
                                      right=self.expression(self.require(ts, "right")))

    def conditional(self, ts: _TS) -> Any:
        consequence = self.field(ts, "consequence")
        return S.ConditionalExpression(
            condition=self.expression(self.require(ts, "condition")),
            consequence=self.expression(consequence) if consequence is not None else None,
            alternative=self.expression(self.require(ts, "alternative")))

    def unary(self, ts: _TS) -> Any:
        return S.UnaryExpression(operator=_op(self.text(self.require(ts, "operator"))),
                                 operand=self.expression(self.require(ts, "argument")))

    def update(self, ts: _TS) -> Any:
        operator = self.text(self.require(ts, "operator"))
        operand = self.expression(self.require(ts, "argument"))
        if self.kids(ts)[0].type in ("++", "--"):
            return S.UnaryExpression(operator=operator, operand=operand)
        return S.PostfixExpression(operand=operand, operator=operator)

    def cast(self, ts: _TS) -> Any:
        return S.CastExpression(type=self.type_id(self.require(ts, "type")),
                                operand=self.expression(self.require(ts, "value")))

    def call(self, ts: _TS) -> Any:
        function = self.require(ts, "function")
        arguments = self.require(ts, "arguments")
        if function.type == "primitive_type":
            return S.FunctionalCastExpression(
                type=self.specifiers(function)[0],
                initializer=self.made(arguments, S.ParenthesizedInitializer(arguments=self.expressions(arguments))))
        if function.type == "identifier" and self.text(function) in ("typeid", "noexcept"):
            # tree-sitter reads these operators as calls; their operand is an expression here
            operands = self.named(arguments)
            if len(operands) != 1:
                raise self.error(arguments, f"{self.text(function)} takes one operand")
            kind = S.TypeidExpression if self.text(function) == "typeid" else S.NoexceptExpression
            return kind(operand=self.expression(operands[0]))
        if function.type == "template_function":
            name = self.text(self.require(function, "name"))
            types = self.named(self.require(function, "arguments"))
            if name in _CASTS and len(types) == 1 and types[0].type == "type_descriptor":
                operands = self.named(arguments)
                if len(operands) != 1:
                    raise self.error(arguments, f"{name} takes one operand")
                return S.NamedCastExpression(operator=name, type=self.type_id(types[0]),
                                             operand=self.expression(operands[0]))
        return S.CallExpression(function=self.expression(function), arguments=self.expressions(arguments))

    def field_expression(self, ts: _TS) -> Any:
        operator = self.text(self.require(ts, "operator"))
        member = self.require(ts, "field")
        if operator == ".*":
            return S.BinaryExpression(left=self.expression(self.require(ts, "argument")), operator=".*",
                                      right=self.expression(member))
        keyword = member.type == "dependent_name"  # `object.template name<...>`: the keyword is the access's
        return S.MemberExpression(object=self.expression(self.require(ts, "argument")), operator=operator,
                                  template_keyword=keyword, member=self.name(self.named(member)[0] if keyword else member))

    def subscript(self, ts: _TS) -> Any:
        return S.SubscriptExpression(object=self.expression(self.require(ts, "argument")),
                                     indices=self.expressions(self.require(ts, "indices")))

    def sizeof(self, ts: _TS) -> Any:
        type_ = self.field(ts, "type")
        if type_ is not None:
            return S.SizeofExpression(operand=self.type_id(type_))
        value = self.require(ts, "value")
        if self.has(ts, "..."):
            return S.SizeofPackExpression(pack=self.identifier(value))
        return S.SizeofExpression(operand=self.expression(value))

    def alignof(self, ts: _TS) -> Any:
        return S.AlignofExpression(keyword=self.text(self.kids(ts)[0]), operand=self.type_id(self.require(ts, "type")))

    def new(self, ts: _TS) -> Any:
        type_ = self.require(ts, "type")
        declarator: Any = None
        node = self.field(ts, "declarator")
        while node is not None:
            declarator = self.made(node, S.ArrayDeclarator(declarator=declarator,
                                                           size=self.expression(self.require(node, "length"))))
            node = next((c for c in self.named(node) if c.type == "new_declarator"), None)
        placement = self.field(ts, "placement")
        arguments = self.field(ts, "arguments")
        initializer: Any = None
        if arguments is not None and arguments.type == "argument_list":
            initializer = self.made(arguments, S.ParenthesizedInitializer(arguments=self.expressions(arguments)))
        elif arguments is not None:
            initializer = self.expression(arguments)
        return S.NewExpression(global_scope=self.has(ts, "::"),
                               placement=self.expressions(placement) if placement is not None else [],
                               type=self.made(type_, S.TypeId(specifiers=self.specifiers(type_), declarator=declarator)),
                               initializer=initializer)

    def delete(self, ts: _TS) -> Any:
        return S.DeleteExpression(global_scope=self.has(ts, "::"), array=self.has(ts, "["),
                                  operand=self.expression(self.named(ts)[0]))

    def fold(self, ts: _TS) -> Any:
        left, right = self.require(ts, "left"), self.require(ts, "right")
        return S.FoldExpression(left=self.expression(left) if left.is_named else None,
                                operator=_op(self.text(self.require(ts, "operator"))),
                                right=self.expression(right) if right.is_named else None)

    def pack_expansion(self, ts: _TS) -> Any:
        pattern = self.require(ts, "pattern")
        return S.PackExpansion(pattern=self.type_id(pattern) if pattern.type == "type_descriptor"
                               else self.expression(pattern))

    def literal(self, ts: _TS) -> Any:
        return self.quoted(ts)

    def concatenated(self, ts: _TS) -> Any:
        return S.ConcatenatedString(parts=[self.expression(c) for c in self.named(ts)])

    def user_defined(self, ts: _TS) -> Any:
        literal, suffix = self.named(ts)
        return S.UserDefinedLiteral(literal=self.expression(literal), suffix=self.text(suffix))

    def initializer_list(self, ts: _TS) -> Any:
        kids = self.kids(ts)
        return S.InitializerList(items=[self.designated(c) if c.type == "initializer_pair" else self.expression(c)
                                        for c in self.named(ts)],
                                 trailing_comma=len(kids) > 2 and kids[-2].type == ",")

    def designated(self, ts: _TS) -> Any:
        designators: list[Any] = []
        for d in self.fields(ts, "designator"):
            if d.type in ("field_designator", "field_identifier"):
                name = self.named(d)[0] if d.type == "field_designator" else d
                designators.append(self.made(d, S.FieldDesignator(name=self.identifier(name))))
            elif d.type == "subscript_designator":
                designators.append(self.made(d, S.IndexDesignator(index=self.expression(self.named(d)[0]))))
            else:
                designators.append(self.made(d, S.IndexDesignator(index=self.expression(self.require(d, "start")),
                                                                  last=self.expression(self.require(d, "end")))))
        value = self.require(ts, "value")
        initializer = self.made(value, S.EqualInitializer(value=self.expression(value)))
        return self.made(ts, S.DesignatedInitializer(designators=designators, initializer=initializer))

    def compound_literal(self, ts: _TS) -> Any:
        type_ = self.require(ts, "type")
        value = self.expression(self.require(ts, "value"))
        if type_.type == "type_descriptor":
            return S.CompoundLiteralExpression(type=self.type_id(type_), initializer=value)
        return S.FunctionalCastExpression(type=self.specifiers(type_)[0], initializer=value)

    def generic(self, ts: _TS) -> Any:
        parts = self.named(ts)
        made = S.GenericSelection(controlling=self.expression(parts[0]))  # tree-sitter reads no type there
        for i in range(1, len(parts), 2):  # type, value: `default` is a type named default to tree-sitter
            association = parts[i]
            made.associations.append(self.made(association, S.GenericAssociation(
                type=self.type_id(association) if self.text(association) != "default" else None,
                value=self.expression(parts[i + 1]))))
        return made

    def offsetof(self, ts: _TS) -> Any:
        keyword = self.kids(ts)[0]
        return S.CallExpression(function=self.made(keyword, S.IdExpression(name=self.identifier(keyword))),
                                arguments=[self.type_id(self.require(ts, "type")),
                                           self.id_expression(self.require(ts, "member"))])

    def lambda_(self, ts: _TS) -> Any:
        made = S.LambdaExpression(body=self.statement(self.require(ts, "body")))
        captures = self.require(ts, "captures")
        kids = self.kids(captures)
        i = 1
        while i < len(kids) - 1:
            c = kids[i]
            i += 1
            if c.type == ",":
                continue
            if c.type == "lambda_default_capture":
                made.captures.append(self.made(c, S.DefaultCapture(mode=self.text(c))))
            elif c.type == "&":
                target = kids[i]
                i += 1
                if target.type == "parameter_pack_expansion":
                    made.captures.append(self.made(c, S.SimpleCapture(
                        by_reference=True, name=self.identifier(self.require(target, "pattern")), pack=True)))
                else:
                    made.captures.append(self.made(c, S.SimpleCapture(by_reference=True, name=self.identifier(target))))
            elif c.type == "*":
                made.captures.append(self.made(c, S.ThisCapture(copy=True)))
                i += 1
            elif c.type == "this":
                made.captures.append(self.made(c, S.ThisCapture()))
            elif c.type == "lambda_capture_initializer":
                made.captures.append(self.init_capture(c))
            elif c.type == "parameter_pack_expansion":
                made.captures.append(self.made(c, S.SimpleCapture(name=self.identifier(self.require(c, "pattern")),
                                                                  pack=True)))
            elif c.type == "identifier":
                made.captures.append(self.made(c, S.SimpleCapture(name=self.identifier(c))))
            else:
                raise self.unsupported(c)
        parameters = self.field(ts, "template_parameters")
        if parameters is not None:
            made.template_parameters = self.template_parameters(parameters)
        constraint = self.field(ts, "constraint")
        if constraint is not None:
            made.template_requires = self.requires_clause(constraint)
        declarator = self.field(ts, "declarator")
        if declarator is not None:
            made.declarator = self.lambda_declarator(declarator)
        return made

    def init_capture(self, ts: _TS) -> Any:
        value = self.require(ts, "right")
        initializer = self.made(value, S.EqualInitializer(value=self.expression(value)))
        return self.made(ts, S.InitCapture(by_reference=self.has(ts, "&"), pack=self.has(ts, "..."),
                                           name=self.identifier(self.require(ts, "left")), initializer=initializer))

    def lambda_declarator(self, ts: _TS) -> Any:
        made = S.LambdaDeclarator(parameters=self.parameters(self.require(ts, "parameters")))
        for c in self.named(ts):
            if c.type == "parameter_list":
                continue
            if c.type == "type_qualifier":
                made.specifiers.append(self.made(c, S.DeclSpecifier(keyword=self.text(c))))
            elif c.type in ("noexcept", "throw_specifier"):
                made.exception = self.exception(c)
            elif c.type == "trailing_return_type":
                made.trailing_return = self.type_id(self.named(c)[0])
            elif c.type == "requires_clause":
                made.requires = self.requires_clause(c)
            elif c.type in _ATTRIBUTES:
                made.attributes.append(self.attribute(c))
            else:
                raise self.unsupported(c)
        return self.made(ts, made)

    def requires_expression(self, ts: _TS) -> Any:
        parameters = self.field(ts, "parameters")
        made = S.RequiresExpression(parameters=self.parameters(parameters) if parameters is not None else [])
        for r in self.named(self.require(ts, "requirements")):
            if r.type != "simple_requirement" or self.named(r):  # tree-sitter reads `;` after some as empty ones
                made.requirements.append(self.requirement(r))
        return made

    def requirement(self, ts: _TS) -> Any:
        if ts.type == "simple_requirement":
            inner = self.named(ts)
            if inner and inner[0].type == "requires_clause":  # `requires constraint;`
                return self.made(ts, S.NestedRequirement(constraint=self.requires_clause(inner[0])))
            return self.made(ts, S.SimpleRequirement(expression=self.expression(inner[0])))
        if ts.type == "type_requirement":
            return self.made(ts, S.TypeRequirement(name=self.name(self.named(ts)[0])))
        parts = self.named(ts)
        made = S.CompoundRequirement(expression=self.expression(parts[0]), noexcept=self.has(ts, "noexcept"))
        for p in parts[1:]:
            descriptor = self.named(p)[0]
            made.return_type = self.name(self.require(descriptor, "type"))
        return self.made(ts, made)

    def requires_clause(self, ts: _TS) -> Any:
        return self.constraint(self.fields(ts, "constraint"))

    def constraint(self, parts: list[_TS]) -> Any:
        """A constraint expression from tree-sitter's constraint fields, which hold parentheses as tokens."""
        if parts[0].type == "(":
            inner = self.constraint(parts[1:-1])
            return self.made(parts[0], S.ParenthesizedExpression(expression=inner))
        ts = parts[0]
        if ts.type in ("constraint_conjunction", "constraint_disjunction"):
            return self.made(ts, S.BinaryExpression(
                left=self.constraint(self.fields(ts, "left")), operator=_op(self.text(self.require(ts, "operator"))),
                right=self.constraint(self.fields(ts, "right"))))
        if ts.type in ("template_type", "type_identifier"):
            return self.made(ts, S.IdExpression(name=self.name(ts)))
        return self.expression(ts)

    def await_(self, ts: _TS) -> Any:
        return S.AwaitExpression(operand=self.expression(self.require(ts, "argument")))

    def extension(self, ts: _TS) -> Any:
        return S.ExtensionExpression(operand=self.expression(self.named(ts)[0]))

    def defined(self, ts: _TS) -> Any:
        return S.DefinedExpression(name=self.identifier(self.named(ts)[0]))

    EXPRESSIONS: dict[str, Callable[[Any, _TS], Any]] = {}

    # Types

    def type_id(self, ts: _TS) -> S.TypeId:
        """A type_descriptor: specifiers in source order, and its abstract declarator."""
        declarator = self.field(ts, "declarator")
        return self.made(ts, S.TypeId(specifiers=self.specifiers_of(ts),
                                      declarator=self.declarator(declarator) if declarator is not None else None))

    def specifiers_of(self, ts: _TS, attributes: list[Any] | None = None) -> list[Any]:
        """The specifiers of a declaration-like node, in source order. Attributes before the first specifier go to
        `attributes` when given."""
        out: list[Any] = []
        type_ = self.field(ts, "type")
        for i, c in enumerate(ts.children):
            name = ts.field_name_for_child(i)
            if type_ is not None and c.id == type_.id:
                out.extend(self.specifiers(c))
            elif c.type in _ATTRIBUTES and name is None:
                (attributes if attributes is not None and not out else out).append(self.attribute(c))
            elif c.type in _SPECIFIERS or c.type in ("typedef", "__extension__"):
                out.extend(self.specifiers(c))
            elif c.type == "ms_call_modifier":
                raise self.unsupported(c)
        return out

    def specifiers(self, ts: _TS) -> list[Any]:
        """The specifiers one tree-sitter node spells."""
        kind, spelling = ts.type, self.text(ts)
        if kind == "primitive_type" or (kind == "type_identifier" and spelling in _PRIMITIVES):
            if spelling in _PRIMITIVES:
                return [self.made(ts, S.PrimitiveTypeSpecifier(keyword=spelling))]
            return [self.made(ts, S.NamedTypeSpecifier(name=self.identifier(ts)))]
        if kind == "sized_type_specifier":
            out: list[Any] = []
            for c in self.kids(ts):
                if not c.is_named:
                    out.append(self.made(c, S.PrimitiveTypeSpecifier(keyword=c.type)))
                else:
                    out.extend(self.specifiers(c))
            return out
        if kind in ("type_identifier", "qualified_identifier", "template_type"):
            return [self.made(ts, S.NamedTypeSpecifier(name=self.name(ts)))]
        if kind == "dependent_type":
            return [self.made(ts, S.TypenameSpecifier(name=self.specifiers(self.named(ts)[0])[0].name))]
        if kind == "placeholder_type_specifier":
            constraint = self.field(ts, "constraint")
            return [self.made(ts, S.PlaceholderTypeSpecifier(
                constraint=self.name(constraint) if constraint is not None else None,
                decltype=any(c.type == "decltype" for c in self.named(ts))))]
        if kind == "decltype":
            return [self.made(ts, S.DecltypeSpecifier(expression=self.expression(self.named(ts)[0])))]
        if kind in ("class_specifier", "struct_specifier", "union_specifier"):
            return [self.class_specifier(ts)]
        if kind == "enum_specifier":
            return [self.enum_specifier(ts)]
        if kind == "storage_class_specifier" or kind in ("virtual", "typedef", "__extension__"):
            return [self.made(ts, S.DeclSpecifier(keyword=spelling))]
        if kind == "type_qualifier":
            inner = self.named(ts)
            if inner:
                return [self.attribute(inner[0])]
            if spelling in _CV_KEYWORDS:
                return [self.made(ts, S.CvQualifier(keyword=spelling))]
            return [self.made(ts, S.DeclSpecifier(keyword=spelling))]
        condition = self.named(ts)  # explicit_function_specifier, the last kind of specifier
        return [self.made(ts, S.ExplicitSpecifier(condition=self.expression(condition[0]) if condition else None))]

    def class_specifier(self, ts: _TS) -> Any:
        made = S.ClassSpecifier(key=self.text(self.kids(ts)[0]))
        name = self.field(ts, "name")
        if name is not None:
            made.name = self.name(name)
        for c in self.named(ts):
            if c.type in _ATTRIBUTES:
                made.attributes.append(self.attribute(c))
            elif c.type == "virtual_specifier":
                made.final = True
            elif c.type == "base_class_clause":
                made.bases = self.bases(c)
        body = self.field(ts, "body")
        if body is not None:
            made.body = self.made(body, S.MemberList(items=self.items(body.children, declarations=True)))
        return self.made(ts, made)

    def bases(self, ts: _TS) -> list[Any]:
        out: list[Any] = []
        current: Any = None
        for c in self.kids(ts)[1:]:
            if current is None:
                current = self.made(c, S.BaseSpecifier())
            if c.type == ",":
                out.append(current)
                current = None
            elif c.type == "virtual":
                current.virtual = True
            elif c.type == "access_specifier":
                current.access = self.text(c)
            elif c.type == "...":
                current.pack = True
            elif c.type in _ATTRIBUTES:
                current.attributes.append(self.attribute(c))
            else:
                current.type = self.name(c)
        out.append(current)
        return out

    def enum_specifier(self, ts: _TS) -> Any:
        kids = self.kids(ts)
        key = "enum"
        if len(kids) > 1 and kids[1].type in ("class", "struct"):
            key = f"enum {kids[1].type}"
        made = S.EnumSpecifier(key=key)
        name, base, body = self.field(ts, "name"), self.field(ts, "base"), self.field(ts, "body")
        made.attributes = [self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES]
        if name is not None:
            made.name = self.name(name)
        if base is not None:
            made.base = self.made(base, S.TypeId(specifiers=self.specifiers(base)))
        if body is not None:
            items = self.kids(body)
            made.body = self.made(body, S.EnumeratorList(
                enumerators=self.items(body.children, declarations=False, enumerators=True),
                trailing_comma=len(items) > 2 and items[-2].type == ","))
        return self.made(ts, made)

    def enumerator(self, ts: _TS) -> Any:
        value = self.field(ts, "value")
        return self.made(ts, S.Enumerator(name=self.identifier(self.require(ts, "name")),
                                          value=self.expression(value) if value is not None else None))

    # Attributes

    def attribute(self, ts: _TS) -> Any:
        kind = ts.type
        if kind == "attribute_declaration":
            return self.made(ts, S.StandardAttributeSpecifier(attributes=[self.standard_attribute(a)
                                                                          for a in self.named(ts)]))
        if kind == "attribute_specifier":
            made = S.GnuAttributeSpecifier(keyword=self.text(self.kids(ts)[0]))
            for a in self.named(self.named(ts)[0]):
                if a.type == "call_expression":
                    function = self.require(a, "function")
                    made.attributes.append(self.made(a, S.Attribute(
                        name=self.text(function), arguments=self.expressions(self.require(a, "arguments")))))
                else:
                    made.attributes.append(self.made(a, S.Attribute(name=self.text(a))))
            return self.made(ts, made)
        if kind == "ms_declspec_modifier":
            return self.made(ts, S.DeclspecSpecifier(attributes=[self.made(a, S.Attribute(name=self.text(a)))
                                                                 for a in self.named(ts)]))
        operand = self.named(ts)[0]
        return self.made(ts, S.AlignasSpecifier(
            keyword=self.text(self.kids(ts)[0]),
            operand=self.type_id(operand) if operand.type == "type_descriptor" else self.expression(operand)))

    def standard_attribute(self, ts: _TS) -> Any:
        prefix = self.field(ts, "prefix")
        arguments = next((c for c in self.named(ts) if c.type == "argument_list"), None)
        return self.made(ts, S.Attribute(namespace=self.text(prefix) if prefix is not None else None,
                                         name=self.text(self.require(ts, "name")),
                                         arguments=self.expressions(arguments) if arguments is not None else []))

    # Declarators

    def declarator(self, ts: _TS, lifted: dict[str, list[Any]] | None = None) -> Any:
        """A declarator, named or abstract. A function declarator's trailing requires-clause and virt-specifiers
        belong to the declaration, so they go to `lifted`."""
        kind = ts.type
        if kind == "qualified_identifier":
            global_scope, qualifiers, last = self.qualified_parts(ts)
            if last.type == "pointer_type_declarator":
                return self.member_pointer(ts, global_scope, qualifiers, last, lifted)
            if last.type == "operator_cast":
                return self.conversion(last, lifted, ts, global_scope, qualifiers)
        if kind in _NAMES or kind in ("qualified_identifier", "template_function", "template_method",
                                      "destructor_name", "operator_name", "primitive_type"):
            return self.made(ts, S.IdDeclarator(name=self.name(ts)))
        if kind in ("pointer_declarator", "abstract_pointer_declarator", "pointer_type_declarator"):
            inner = self.field(ts, "declarator")
            made = S.PointerDeclarator(declarator=self.declarator(inner, lifted) if inner is not None else None)
            for c in self.named(ts):
                if c.type == "type_qualifier":
                    made.qualifiers.append(self.made(c, S.CvQualifier(keyword=self.text(c))))
                elif inner is None or c.id != inner.id:
                    raise self.unsupported(c)
            return self.made(ts, made)
        if kind in ("reference_declarator", "abstract_reference_declarator"):
            inner_nodes = self.named(ts)
            return self.made(ts, S.ReferenceDeclarator(
                rvalue=self.has(ts, "&&"),
                declarator=self.declarator(inner_nodes[0], lifted) if inner_nodes else None))
        if kind in ("array_declarator", "abstract_array_declarator"):
            inner = self.field(ts, "declarator")
            size = self.field(ts, "size")
            made = S.ArrayDeclarator(declarator=self.declarator(inner, lifted) if inner is not None else None,
                                     static=self.has(ts, "static"))
            if size is not None:
                if size.type == "*":
                    made.star = True
                else:
                    made.size = self.expression(size)
            made.qualifiers = [self.made(c, S.CvQualifier(keyword=self.text(c)))
                               for c in self.named(ts) if c.type == "type_qualifier"]
            return self.made(ts, made)
        if kind in ("function_declarator", "abstract_function_declarator"):
            return self.function_declarator(ts, lifted)
        if kind in ("parenthesized_declarator", "abstract_parenthesized_declarator"):
            inner_nodes = self.named(ts)
            if len(inner_nodes) != 1:  # a calling convention, as in `(__cdecl *f)`
                raise self.unsupported(inner_nodes[0])
            return self.made(ts, S.ParenthesizedDeclarator(declarator=self.declarator(inner_nodes[0], lifted)))
        if kind == "attributed_declarator":
            parts = self.named(ts)
            made = self.declarator(parts[0], lifted)
            made.attributes.extend(self.attribute(a) for a in parts[1:])
            return made
        if kind == "structured_binding_declarator":
            return self.made(ts, S.StructuredBindingDeclarator(
                bindings=[self.made(c, S.IdDeclarator(name=self.identifier(c))) for c in self.named(ts)]))
        if kind == "variadic_declarator":
            inner_nodes = self.named(ts)
            return self.made(ts, S.PackDeclarator(
                declarator=self.made(inner_nodes[0], S.IdDeclarator(name=self.identifier(inner_nodes[0])))
                if inner_nodes else None))
        return self.conversion(ts, lifted)  # operator_cast, the last kind of declarator

    def qualified_parts(self, ts: _TS) -> tuple[bool, list[Any], _TS]:
        """A qualified_identifier, which tree-sitter nests: whether it starts with `::`, its qualifiers, and its last
        name's node."""
        qualifiers: list[Any] = []
        node = ts
        while node.type == "qualified_identifier":
            scope = self.field(node, "scope")
            if scope is not None:
                qualifiers.append(self.scope(scope))
            node = next(n for n in self.fields(node, "name") if n.is_named)
        return self.field(ts, "scope") is None, qualifiers, node

    def member_pointer(self, ts: _TS, global_scope: bool, qualifiers: list[Any], last: _TS,
                       lifted: dict[str, list[Any]] | None) -> Any:
        """`C::* declarator`, which tree-sitter writes as a qualified name ending in a pointer declarator."""
        made = self.declarator(last, lifted)
        scope = qualifiers.pop()
        made.scope = self.made(ts, S.QualifiedName(global_scope=global_scope, qualifiers=qualifiers, name=scope)) \
            if qualifiers or global_scope else scope
        return made

    def function_declarator(self, ts: _TS, lifted: dict[str, list[Any]] | None) -> Any:
        inner = self.field(ts, "declarator")
        made = S.FunctionDeclarator(declarator=self.declarator(inner, lifted) if inner is not None else None,
                                    parameters=self.parameters(self.require(ts, "parameters")))
        for c in self.named(ts):
            if c.type in ("parameter_list",) or (inner is not None and c.id == inner.id):
                continue
            if c.type == "type_qualifier":
                made.qualifiers.append(self.made(c, S.CvQualifier(keyword=self.text(c))))
            elif c.type == "ref_qualifier":
                made.ref_qualifier = self.text(c)
            elif c.type in ("noexcept", "throw_specifier"):
                made.exception = self.exception(c)
            elif c.type == "trailing_return_type":
                made.trailing_return = self.type_id(self.named(c)[0])
            elif c.type in _ATTRIBUTES:
                made.attributes.append(self.attribute(c))
            elif c.type == "requires_clause" and lifted is not None:
                lifted["requires"].append(self.requires_clause(c))
            elif c.type == "virtual_specifier" and lifted is not None:
                lifted["virt_specifiers"].append(self.made(c, S.VirtSpecifier(keyword=self.text(c))))
            else:
                raise self.unsupported(c)
        return self.made(ts, made)

    def conversion(self, ts: _TS, lifted: dict[str, list[Any]] | None, qualified: _TS | None = None,
                   global_scope: bool = False, qualifiers: list[Any] | None = None) -> Any:
        """`operator type declarator`, or a qualified `A::operator type declarator`: tree-sitter nests the function
        declarator inside the conversion type's pointers; the conversion type is `type` and those pointers, and the
        function declarator declares it."""
        wrappers: list[_TS] = []
        node = self.require(ts, "declarator")
        while node.type in ("abstract_pointer_declarator", "abstract_reference_declarator"):
            wrappers.append(node)
            node = self.named(node)[-1]
        type_declarator: Any = None
        for w in reversed(wrappers):
            if w.type == "abstract_pointer_declarator":
                type_declarator = self.made(w, S.PointerDeclarator(
                    qualifiers=[self.made(c, S.CvQualifier(keyword=self.text(c)))
                                for c in self.named(w) if c.type == "type_qualifier"],
                    declarator=type_declarator))
            else:
                type_declarator = self.made(w, S.ReferenceDeclarator(rvalue=self.has(w, "&&"),
                                                                     declarator=type_declarator))
        conversion = self.made(ts, S.ConversionName(type=self.made(ts, S.TypeId(specifiers=self.specifiers_of(ts),
                                                                                declarator=type_declarator))))
        made = self.function_declarator(node, lifted)
        if qualified is not None:
            conversion = self.made(qualified, S.QualifiedName(global_scope=global_scope, qualifiers=qualifiers or [],
                                                              name=conversion))
        made.declarator = self.made(ts, S.IdDeclarator(name=conversion))
        return made

    def exception(self, ts: _TS) -> Any:
        if ts.type == "noexcept":
            condition = self.named(ts)
            return self.made(ts, S.NoexceptSpecifier(condition=self.expression(condition[0]) if condition else None))
        return self.made(ts, S.ThrowSpecifier(types=[self.type_id(c) for c in self.named(ts)]))

    # Parameters

    def parameters(self, ts: _TS) -> list[Any]:
        out: list[Any] = []
        for c in self.kids(ts):
            if c.type == "...":
                out.append(self.made(c, S.EllipsisParameter()))
            elif c.is_named:
                out.append(self.parameter(c))
        return out

    def parameter(self, ts: _TS) -> Any:
        made = S.ParameterDeclaration()
        made.specifiers = self.specifiers_of(ts, made.attributes)
        declarator = self.field(ts, "declarator")
        if declarator is not None:
            made.declarator = self.declarator(declarator)
        default = self.field(ts, "default_value")
        if default is not None:
            made.default = self.expression(default)
        return self.made(ts, made)

    def template_parameters(self, ts: _TS) -> list[Any]:
        out: list[Any] = []
        for c in self.named(ts):
            kind = c.type
            if kind in ("type_parameter_declaration", "variadic_type_parameter_declaration",
                        "optional_type_parameter_declaration"):
                out.append(self.type_parameter(c))
            elif kind == "template_template_parameter_declaration":
                inner = self.type_parameter(self.named(c)[-1])
                out.append(self.made(c, S.TemplateTemplateParameter(
                    parameters=self.template_parameters(self.require(c, "parameters")), key=inner.key,
                    pack=inner.pack, name=inner.name,
                    default=inner.default.specifiers[0].name if inner.default is not None else None)))
            else:
                out.append(self.parameter(c))
        return out

    def type_parameter(self, ts: _TS) -> Any:
        made = S.TypeParameter(key=self.text(self.kids(ts)[0]), pack=self.has(ts, "..."))
        name = self.field(ts, "name") or next((c for c in self.named(ts) if c.type == "type_identifier"), None)
        if name is not None:
            made.name = self.identifier(name)
        default = self.field(ts, "default_type")
        if default is not None:
            made.default = self.made(default, S.TypeId(specifiers=self.specifiers(default)))
        return self.made(ts, made)

    # Statements

    def statement(self, ts: _TS) -> Any:
        method = self.STATEMENTS.get(ts.type)
        if method is None:
            if ts.type in self.DECLARATIONS:
                return self.DECLARATIONS[ts.type](self, ts)
            raise self.unsupported(ts)
        return self.made(ts, method(self, ts))

    def compound(self, ts: _TS) -> Any:
        return S.CompoundStatement(items=self.items(ts.children, declarations=False))

    def expression_statement(self, ts: _TS) -> Any:
        inner = self.named(ts)
        if not inner:
            return S.ExpressionStatement()
        if inner[0].type == "gnu_asm_expression":
            return self.asm(inner[0])
        return S.ExpressionStatement(expression=self.expression(inner[0]))

    def asm(self, ts: _TS) -> Any:
        made = S.AsmDeclaration(keyword=self.text(self.kids(ts)[0]),
                                template=self.expression(self.require(ts, "assembly_code")))
        for q in self.named(ts):
            if q.type == "gnu_asm_qualifier":
                word = self.text(q).strip("_")
                setattr(made, word, True)

        def operands(name: str) -> list[Any]:
            found = self.field(ts, name)
            out = []
            for o in self.fields(found, "operand") if found is not None else []:
                symbol = self.field(o, "symbol")
                out.append(self.made(o, S.AsmOperand(
                    name=self.identifier(symbol) if symbol is not None else None,
                    constraint=self.expression(self.require(o, "constraint")),
                    value=self.expression(self.require(o, "value")))))
            return out

        made.outputs, made.inputs = operands("output_operands"), operands("input_operands")
        clobbers, labels = self.field(ts, "clobbers"), self.field(ts, "goto_labels")
        made.clobbers = [self.expression(c) for c in self.named(clobbers)] if clobbers is not None else []
        made.labels = [self.identifier(c) for c in self.named(labels)] if labels is not None else []
        return self.made(ts, made)

    def condition(self, ts: _TS, made: Any) -> Any:
        """Fills `made`'s initializer and condition from a condition_clause."""
        initializer = self.field(ts, "initializer")
        if initializer is not None:
            made.initializer = self.declaration_or_statement(self.named(initializer)[0])
        value = self.require(ts, "value")
        made.condition = self.declaration_or_statement(value) if value.type == "declaration" else \
            self.expression(value)
        return made

    def if_(self, ts: _TS) -> Any:
        made = S.IfStatement(constexpr=self.has(ts, "constexpr"),
                             consequence=self.statement(self.require(ts, "consequence")))
        self.condition(self.require(ts, "condition"), made)
        alternative = self.field(ts, "alternative")
        if alternative is not None:
            made.alternative = self.statement(self.named(alternative)[0])
        return made

    def switch(self, ts: _TS) -> Any:
        return self.condition(self.require(ts, "condition"),
                              S.SwitchStatement(body=self.statement(self.require(ts, "body"))))

    def while_(self, ts: _TS) -> Any:
        return self.condition(self.require(ts, "condition"),
                              S.WhileStatement(body=self.statement(self.require(ts, "body"))))

    def do(self, ts: _TS) -> Any:
        condition = self.require(ts, "condition")
        return S.DoStatement(body=self.statement(self.require(ts, "body")),
                             condition=self.expression(self.named(condition)[0]))

    def for_(self, ts: _TS) -> Any:
        made = S.ForStatement(body=self.statement(self.require(ts, "body")))
        initializer, condition, update = (self.field(ts, n) for n in ("initializer", "condition", "update"))
        if initializer is not None:
            if initializer.type == "declaration":
                made.initializer = self.simple_declaration(initializer)
            else:
                made.initializer = self.made(initializer, S.ExpressionStatement(
                    expression=self.expression(initializer)))
        if condition is not None:
            made.condition = self.expression(condition)
        if update is not None:
            made.increment = self.expression(update)
        return made

    def range_for(self, ts: _TS) -> Any:
        declaration = S.SimpleDeclaration()
        declaration.specifiers = self.specifiers_of(ts, declaration.attributes)
        declaration.declarators = [self.made(ts, S.InitDeclarator(
            declarator=self.declarator(self.require(ts, "declarator"))))]
        made = S.RangeForStatement(declaration=self.made(ts, declaration),
                                   range=self.expression(self.require(ts, "right")),
                                   body=self.statement(self.require(ts, "body")))
        initializer = self.field(ts, "initializer")
        if initializer is not None:
            made.initializer = self.declaration_or_statement(self.named(initializer)[0])
        return made

    def return_(self, ts: _TS) -> Any:
        value = self.named(ts)
        return S.ReturnStatement(value=self.expression(value[0]) if value else None)

    def co_return(self, ts: _TS) -> Any:
        value = self.named(ts)
        return S.CoReturnStatement(value=self.expression(value[0]) if value else None)

    def co_yield(self, ts: _TS) -> Any:
        return S.ExpressionStatement(expression=self.made(ts, S.YieldExpression(
            operand=self.expression(self.named(ts)[0]))))

    def throw(self, ts: _TS) -> Any:
        value = self.named(ts)
        return S.ExpressionStatement(expression=self.made(ts, S.ThrowExpression(
            operand=self.expression(value[0]) if value else None)))

    def goto(self, ts: _TS) -> Any:
        return S.GotoStatement(label=self.identifier(self.require(ts, "label")))

    def labeled(self, ts: _TS) -> Any:
        label = self.require(ts, "label")
        body = [c for c in self.named(ts) if c.id != label.id]
        return S.LabeledStatement(label=self.identifier(label), statement=self.statement(body[0]))  # tree-sitter
        # parses no label that ends a block

    def try_(self, ts: _TS) -> Any:
        made = S.TryStatement(body=self.statement(self.require(ts, "body")))
        for c in self.named(ts):
            if c.type == "catch_clause":
                parameters = self.parameters(self.require(c, "parameters"))
                made.handlers.append(self.made(c, S.Handler(parameter=parameters[0],
                                                            body=self.statement(self.require(c, "body")))))
        return made

    def attributed(self, ts: _TS) -> Any:
        parts = self.named(ts)
        return S.AttributedStatement(attributes=[self.attribute(a) for a in parts[:-1]],
                                     statement=self.statement(parts[-1]))

    STATEMENTS: dict[str, Callable[[Any, _TS], Any]] = {}

    # Declarations

    def simple_declaration(self, ts: _TS) -> Any:
        made = S.SimpleDeclaration()
        made.specifiers = self.specifiers_of(ts, made.attributes)
        kids = ts.children
        current: Any = None
        lifted: dict[str, list[Any]] = {"requires": [], "virt_specifiers": []}
        for i, c in enumerate(kids):
            name = ts.field_name_for_child(i)
            if name == "declarator":
                current = self.init_declarator(c, lifted)
                made.declarators.append(current)
            elif name in ("default_value", "value"):
                equals = i > 0 and kids[i - 1].type == "="
                current.initializer = self.initializer(c, equals, current)
            elif c.type == "bitfield_clause":  # tree-sitter-cpp parses no unnamed bit-field
                current.bitfield = self.expression(self.named(c)[0])
        return made

    def init_declarator(self, ts: _TS, lifted: dict[str, list[Any]]) -> Any:
        if ts.type == "gnu_asm_expression":
            raise self.unsupported(ts)
        if ts.type != "init_declarator":
            made = S.InitDeclarator(declarator=self.declarator(ts, lifted))
        else:
            made = S.InitDeclarator(declarator=self.declarator(self.require(ts, "declarator"), lifted))
            value = self.require(ts, "value")
            made.initializer = self.initializer(value, self.has(ts, "="), made)
        made.requires = lifted["requires"].pop() if lifted["requires"] else None
        made.virt_specifiers, lifted["virt_specifiers"] = lifted["virt_specifiers"], []
        return self.made(ts, made)

    def initializer(self, ts: _TS, equals: bool, declarator: Any) -> Any:
        if ts.type == "argument_list":
            return self.made(ts, S.ParenthesizedInitializer(arguments=self.expressions(ts)))
        value = self.expression(ts)
        if not equals:
            return value
        if (isinstance(value, S.IntegerLiteral) and value.spelling == "0" and declarator is not None
                and isinstance(S.binding(declarator.declarator)[1], S.FunctionDeclarator)):
            declarator.pure = True  # `= 0` after a function declarator is the pure-specifier
            return None
        return self.made(ts, S.EqualInitializer(value=value))

    def function_definition(self, ts: _TS) -> Any:
        lifted: dict[str, list[Any]] = {"requires": [], "virt_specifiers": []}
        attributes: list[Any] = []
        specifiers = self.specifiers_of(ts, attributes)
        declarator = self.declarator(self.require(ts, "declarator"), lifted)
        made: Any
        clauses = {c.type: c for c in self.named(ts)}
        # a function-try-block with member initializers is a child that is not the body
        body = self.field(ts, "body") or clauses.get("try_statement")
        if "pure_virtual_clause" in clauses:
            made = S.SimpleDeclaration(attributes=attributes, specifiers=specifiers, declarators=[self.made(
                ts, S.InitDeclarator(declarator=declarator, pure=True,
                                     virt_specifiers=lifted["virt_specifiers"],
                                     requires=lifted["requires"][0] if lifted["requires"] else None))])
            return self.made(ts, made)
        made = S.FunctionDefinition(attributes=attributes, specifiers=specifiers, declarator=declarator,
                                    virt_specifiers=lifted["virt_specifiers"],
                                    requires=lifted["requires"][0] if lifted["requires"] else None)
        if "field_initializer_list" in clauses:
            made.initializers = self.member_initializers(clauses["field_initializer_list"])
        if body is not None and body.type == "try_statement":
            made.body = self.made(body, self.try_(body))
            inner = next((c for c in self.named(body) if c.type == "field_initializer_list"), None)
            if inner is not None:
                made.initializers = self.member_initializers(inner)
        elif body is not None:
            made.body = self.statement(body)
        elif "default_method_clause" in clauses:
            made.body = self.made(clauses["default_method_clause"], S.DefaultedBody())
        else:  # tree-sitter requires a body or one of these clauses
            made.body = self.made(clauses["delete_method_clause"], S.DeletedBody())
        return self.made(ts, made)

    def member_initializers(self, ts: _TS) -> list[Any]:
        out = []
        for c in self.named(ts):
            parts = self.named(c)
            value = parts[-1]
            initializer = (self.made(value, S.ParenthesizedInitializer(arguments=self.expressions(value)))
                           if value.type == "argument_list" else self.expression(value))
            out.append(self.made(c, S.MemberInitializer(member=self.name(parts[0]), initializer=initializer,
                                                        pack=self.has(c, "..."))))
        return out

    def template_declaration(self, ts: _TS) -> Any:
        made = S.TemplateDeclaration(parameters=self.template_parameters(self.require(ts, "parameters")))
        parameters = self.require(ts, "parameters")
        for c in self.named(ts):
            if c.id == parameters.id:
                continue
            if c.type == "requires_clause":
                made.requires = self.requires_clause(c)
            else:
                made.declaration = self.declaration_or_statement(c)
        return made

    def template_instantiation(self, ts: _TS) -> Any:
        declaration = S.SimpleDeclaration()
        declaration.specifiers = self.specifiers_of(ts, declaration.attributes)
        declarator = self.require(ts, "declarator")
        if not declarator.is_missing:
            declaration.declarators = [self.init_declarator(declarator, {"requires": [], "virt_specifiers": []})]
        return S.ExplicitInstantiation(extern=self.at(ts) in self.pre.extern_templates,
                                       declaration=self.made(ts, declaration))

    def type_specifier_declaration(self, ts: _TS) -> Any:
        return S.SimpleDeclaration(specifiers=self.specifiers(ts))

    def friend(self, ts: _TS) -> Any:
        keyword = self.kids(ts)[0]
        friend = self.made(keyword, S.DeclSpecifier(keyword="friend"))
        inner = self.named(ts)
        if inner and inner[0].type in ("declaration", "function_definition"):
            made = self.declaration_or_statement(inner[0])
            made.specifiers.insert(0, friend)
            return made
        key = next((c.type for c in self.kids(ts) if c.type in ("class", "struct", "union")), None)
        type_ = inner[0]
        specifier = (self.made(type_, S.ClassSpecifier(key=key, name=self.name(type_))) if key is not None
                     else self.specifiers(type_)[0])
        return S.SimpleDeclaration(specifiers=[friend, specifier])

    def alias(self, ts: _TS) -> Any:
        return S.AliasDeclaration(name=self.identifier(self.require(ts, "name")),
                                  attributes=[self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES],
                                  type=self.type_id(self.require(ts, "type")))

    def using(self, ts: _TS) -> Any:
        target = self.name(self.named(ts)[0])
        if self.has(ts, "namespace"):
            return S.UsingDirective(name=target)
        if self.has(ts, "enum"):
            return S.UsingEnumDeclaration(type=target)
        return S.UsingDeclaration(declarators=[self.made(ts, S.UsingDeclarator(
            typename_keyword=self.has(ts, "typename"), name=target))])

    def namespace(self, ts: _TS) -> Any:
        made = S.NamespaceDefinition(inline=self.has(ts, "inline"),
                                     attributes=[self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES])
        name = self.field(ts, "name")
        made.names = [self.made(n, S.NamespaceName(inline=inline, name=self.identifier(n)))
                      for inline, n in self.namespace_names(name)] if name is not None else []
        made.items = self.items(self.require(ts, "body").children, declarations=True)
        return made

    def namespace_names(self, ts: _TS) -> list[tuple[bool, _TS]]:
        """The names of a namespace_identifier or nested_namespace_specifier, which tree-sitter nests, each with
        whether `inline` precedes it."""
        if ts.type == "namespace_identifier":
            return [(False, ts)]
        out: list[tuple[bool, _TS]] = []
        inline = False
        for c in self.kids(ts):
            if c.type == "inline":
                inline = True
            elif c.is_named:
                found = self.namespace_names(c)
                out.append((inline or found[0][0], found[0][1]))
                out.extend(found[1:])
                inline = False
        return out

    def namespace_alias(self, ts: _TS) -> Any:
        name = self.require(ts, "name")
        target = next(c for c in self.named(ts) if c.id != name.id)
        if target.type == "nested_namespace_specifier":
            parts = [self.identifier(n) for _, n in self.namespace_names(target)]
            resolved: Any = self.made(target, S.QualifiedName(qualifiers=parts[:-1], name=parts[-1],
                                                              global_scope=self.kids(target)[0].type == "::"))
        else:
            resolved = self.identifier(target)
        return S.NamespaceAliasDefinition(name=self.identifier(name), target=resolved)

    def static_assert(self, ts: _TS) -> Any:
        message = self.field(ts, "message")
        return S.StaticAssertDeclaration(keyword=self.text(self.kids(ts)[0]),
                                         condition=self.expression(self.require(ts, "condition")),
                                         message=self.expression(message) if message is not None else None)

    def linkage(self, ts: _TS) -> Any:
        body = self.require(ts, "body")
        language = self.text(self.require(ts, "value"))[1:-1]
        if body.type == "declaration_list":
            return S.LinkageSpecification(language=language, braced=True,
                                          items=self.items(body.children, declarations=True))
        return S.LinkageSpecification(language=language, items=[self.declaration_or_statement(body)])

    def concept(self, ts: _TS) -> Any:
        name = self.require(ts, "name")
        return S.ConceptDefinition(name=self.identifier(name),
                                   constraint=self.expression(next(c for c in self.named(ts) if c.id != name.id)))

    def type_definition(self, ts: _TS) -> Any:
        return self.simple_declaration(ts)

    DECLARATIONS: dict[str, Callable[[Any, _TS], Any]] = {}


_Converter.EXPRESSIONS.update({
    **{n: _Converter.id_expression for n in _NAMES | {"qualified_identifier", "template_function", "template_method",
                                                       "dependent_name", "destructor_name", "operator_name"}},
    "number_literal": _Converter.number, "char_literal": _Converter.literal, "string_literal": _Converter.literal,
    "raw_string_literal": _Converter.literal, "concatenated_string": _Converter.concatenated,
    "user_defined_literal": _Converter.user_defined,
    "true": lambda self, ts: S.BooleanLiteral(value=True), "false": lambda self, ts: S.BooleanLiteral(),
    "null": _Converter.null, "this": lambda self, ts: S.ThisExpression(),
    "parenthesized_expression": _Converter.parenthesized, "comma_expression": _Converter.comma,
    "binary_expression": _Converter.binary, "assignment_expression": _Converter.assignment,
    "conditional_expression": _Converter.conditional, "unary_expression": _Converter.unary,
    "pointer_expression": _Converter.unary, "update_expression": _Converter.update,
    "cast_expression": _Converter.cast, "call_expression": _Converter.call,
    "field_expression": _Converter.field_expression, "subscript_expression": _Converter.subscript,
    "sizeof_expression": _Converter.sizeof, "alignof_expression": _Converter.alignof, "new_expression": _Converter.new,
    "delete_expression": _Converter.delete, "fold_expression": _Converter.fold,
    "parameter_pack_expansion": _Converter.pack_expansion, "initializer_list": _Converter.initializer_list,
    "compound_literal_expression": _Converter.compound_literal, "generic_expression": _Converter.generic,
    "offsetof_expression": _Converter.offsetof, "lambda_expression": _Converter.lambda_,
    "requires_expression": _Converter.requires_expression, "requires_clause": _Converter.requires_clause,
    "co_await_expression": _Converter.await_, "extension_expression": _Converter.extension,
    "preproc_defined": _Converter.defined,
})

_Converter.STATEMENTS.update({
    "compound_statement": _Converter.compound, "expression_statement": _Converter.expression_statement,
    "if_statement": _Converter.if_, "switch_statement": _Converter.switch, "while_statement": _Converter.while_,
    "do_statement": _Converter.do, "for_statement": _Converter.for_, "for_range_loop": _Converter.range_for,
    "return_statement": _Converter.return_, "co_return_statement": _Converter.co_return,
    "co_yield_statement": _Converter.co_yield, "throw_statement": _Converter.throw,
    "break_statement": lambda self, ts: S.BreakStatement(), "continue_statement": lambda self, ts: S.ContinueStatement(),
    "goto_statement": _Converter.goto, "labeled_statement": _Converter.labeled, "try_statement": _Converter.try_,
    "attributed_statement": _Converter.attributed,
})

_Converter.DECLARATIONS.update({
    "declaration": _Converter.simple_declaration, "field_declaration": _Converter.simple_declaration,
    "type_definition": _Converter.type_definition, "function_definition": _Converter.function_definition,
    "template_declaration": _Converter.template_declaration,
    "template_instantiation": _Converter.template_instantiation, "friend_declaration": _Converter.friend,
    "alias_declaration": _Converter.alias, "using_declaration": _Converter.using,
    "namespace_definition": _Converter.namespace, "namespace_alias_definition": _Converter.namespace_alias,
    "static_assert_declaration": _Converter.static_assert, "linkage_specification": _Converter.linkage,
    "concept_definition": _Converter.concept,
    **{n: _Converter.type_specifier_declaration for n in (
        "class_specifier", "struct_specifier", "union_specifier", "enum_specifier")},
})


def parse(text: str) -> tuple[S.TranslationUnit, dict[int, int], _Source]:
    """The tree of `text`, the offset where each of its nodes starts (by `id`), and the source, for locating
    problems. Raises `ParseError` for text tree-sitter-cpp cannot parse."""
    cleaned, premodules = _premodules(text)
    source = _Source(text, cleaned)
    tree = _PARSER.parse(source.data, encoding="utf16le")
    converter = _Converter(source, premodules)
    unit = converter.unit(tree.root_node)
    return unit, converter.positions, source
