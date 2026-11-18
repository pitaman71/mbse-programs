"""Parse: TypeScript 5 source text as the transaction that writes its program, delegating to tree-sitter-typescript.

`parse(text, path)` reads `text` at once, keeping what does not parse as invalid syntax, and gives the transaction's
callback, which a caller executes, `store.transaction(parse(text, path))`, or builds to write it,
`Plain.ToPlain(store).Transaction(store.Mutations.OfTransaction(parse(text, path, store)))`. Executed in a store holding
the installs (`TypeScript5.INSTALLS`: mbse-expressions' `Framework`, ISO/IEC 11404, IEEE 754, `TypeScript5`,
`TypeScript Types`, `TypeScript Patterns`, `TypeScript RegExp`, then `Programs.Framework.Model` and
`Programs.TypeScript5`), it is one upsert, `uid(path)`, whose symbols bind the workspace (`ws`, its singleton
`Programs.Framework.TheWorkspace`) and the program (`program`); its spec puts the program in the workspace's `files` by
`path` and writes its tree, the program's `body` (and its `hashbang`, where it has one), as one value: each statement a
branch of `Programs.TypeScript5.Statement`, holding its properties, its line and the statements of its blocks, its
clauses and its class members, nested (stage 3's design, "the whole tree as values"). Its frame binds the program, and
assigns it its tree.

As the port decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)),
the whole tree is values: statements are `Programs.TypeScript5`'s kinds (`Statements`), value objects nested in the
program's `body`; expressions are mbse-expressions' `TypeScript5` terms, types `TypeScript Types` terms and binding
patterns `TypeScript Patterns` terms, nested values too, written through the builders (mbse-expressions' TypeScript
family has no writers) with their concrete syntax as far as the dialects keep it: parentheses written in the source
(`parenthesizedexpression`), a literal's spelling (`text`, `quote`, `base`, `separators`), `null` and a regular
expression as `constant`s with theirs, and a template's raw text. Where a term holds statements, its property holds
them, as the user decided ("the crossover should be modeled as a property of T_A"): a function expression's, an
arrow's with a block and an object literal's or class's method's `block`, and a class expression's `classBody`.
tree-sitter-typescript builds a concrete syntax tree; `_Converter` rewrites it one node type at a time.

Reused from mbse-programs 0.3 (`TypeScript/_Parser.py`), as it was: the source and its offsets (`_Source`), counted in
characters (code points), never bytes, so that every implementation reports the same line; the pre-pass (`_prepare`)
for what tree-sitter-typescript 0.23 cannot parse (the `accessor` keyword, the variance annotations `in` and `out`, the
`defer` of `import defer`, the `type` of `export type *`, the names `accessor`, `abstract` and `using` it reads as
keywords, `using` in `for (... of ...)`, and `import(...)` as a type qualified with type arguments), which rewrites them
keeping every other character where it was, the converter putting them back; the regrouping of `as`, `satisfies`, `!`
and `readonly` where tree-sitter-typescript groups them unlike TypeScript; `x as A.B.C`'s names, the type's; and
comments' attachment, with those tree-sitter-typescript puts after a closing brace.

Decided here *(agent, for review)*:

- **The grammar by the path.** A path ending `.tsx` is read with tree-sitter-typescript's `tsx` grammar, any other with
  its `typescript` grammar, as TypeScript itself decides by the file's extension: JSX is read only in a `.tsx` file,
  and `<T>x` is a type assertion only in another.
- **Schemas, resolved through the transaction or the store**, as Python3's `Parse`: `parse(text, path, store)` for a
  bare builder.
- **What is absent is absent.** A property tree-sitter's tree gives no value, an empty list, or a flag that is false
  is not written; a kind's word (`importKind`, `exportKind`, `declarationKind`, `methodKind`, `propertyKind`) is
  always written, as typescript-estree has it.
- **A literal's value** is what JavaScript reads its spelling as: a string's, its escapes decoded, a number's (a float),
  a bigint's (an int), a boolean's. `base` is written for a number spelled as an integer and for a bigint, 10 where it
  has no prefix; `separators` where its digits are grouped by `_`. A JSX attribute's string is its text between its
  quotes, which JSX does not unescape. `null` and a regular expression are `constant`s: its `singleton`, or its
  `pattern` and `flags` as written, with its `text`; a regular expression's `regexp`, the `TypeScript RegExp` term its
  pattern encodes, is not written: mbse-expressions has no reader of it in Python, and the dialect allows it absent.
- **Positions**: each statement's, clause's, class member's (but an index signature's, which `TypeScript Types` gives
  none), enum member's and error's line is written as its `line`; an expression has none. A statement's line is where
  its node starts: a decorated class's, its first decorator's.

Invalid syntax is kept, never raised, as the user decided for every language (a statement-level
`Programs.Framework.Error`, "(a)"; "always keep, never raise", "(a)"), as far as tree-sitter-typescript's recovery
allows; what the pre-pass rewrites is no longer invalid, and what remains after it is:

- **Where a statement, a switch's case, a class member or an enum member stands**, an `Error`
  (`Programs.TypeScript5.Error`), with its line: tree-sitter skipped it (`ERROR`), or it holds invalid syntax no term
  holds (a `MISSING` token, as in `if (a {}`), or it is a construct the converter cannot hold (a mapped type as a class
  member). Its `text` is as written, before the pre-pass; its `body`, the statements tree-sitter read within it, each
  block's statements among them, flattened *(agent, as Python3's)*. A statement whose `catch` clause or interface
  member is invalid is an `Error` as a whole *(agent)*.
- **Within an expression, a type or a pattern**, its dialect's `error` term, the innermost that holds an `ERROR` or a
  construct its dialect cannot hold (a type annotation in parentheses, Flow's `?T`, an optional chain as an assignment's
  target, a hole among a call's arguments, an escape of no character): its `text` as written, its `terms` each
  `TypeScript5` expression tree-sitter read within it.
- **`MISSING`**: where an expression or a type stands, its dialect's `missing` term, its `kind` the node type
  tree-sitter expected; a token makes what holds it invalid as above.
- **`ParseError`** is raised only for text that is no text, a lone surrogate, which no encoding writes.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

import tree_sitter_typescript
from mbse.Schemas.Framework import Schemas
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from ..Framework.Model import WORKSPACE

__all__ = ["parse", "ParseError", "WORKSPACE"]

_PARSERS = {False: _TSParser(_Grammar(tree_sitter_typescript.language_typescript())),
            True: _TSParser(_Grammar(tree_sitter_typescript.language_tsx()))}

_EXTRAS = {"comment", "html_comment"}
_KEYWORD_TYPES = {
    "any": "tsanykeyword", "unknown": "tsunknownkeyword", "number": "tsnumberkeyword", "bigint": "tsbigintkeyword",
    "boolean": "tsbooleankeyword", "string": "tsstringkeyword", "symbol": "tssymbolkeyword",
    "object": "tsobjectkeyword", "never": "tsneverkeyword", "void": "tsvoidkeyword",
    "undefined": "tsundefinedkeyword", "null": "tsnullkeyword", "intrinsic": "tsintrinsickeyword",
}
# Operators that bind less than `as` and `satisfies`, which bind as the relational operators do.
_LOOSER_THAN_AS = {"==", "!=", "===", "!==", "&", "^", "|", "&&", "||", "??"}
# How tightly each binary operator binds.
_BINDS = {"??": 1, "||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "===": 6, "!==": 6, "<": 7, "<=": 7,
          ">": 7, ">=": 7, "in": 7, "instanceof": 7, "<<": 8, ">>": 8, ">>>": 8, "+": 9, "-": 9, "*": 10, "/": 10,
          "%": 10, "**": 11}
# The terms `TypeScript Patterns` lists, which an assignment's target may be.
_PATTERNS = {"arraypattern", "objectpattern", "assignmentpattern", "restelement", "identifier", "memberexpression",
             "parenthesizedexpression", "tsasexpression", "tssatisfiesexpression", "tstypeassertion",
             "tsnonnullexpression", "error", "missing"}
_LANGUAGE = "Programs.TypeScript5"
_TERM = "Expressions.Framework.Term"  # the framework's union of dialects, which an `error` term's `terms` hold


class _Invalid(Exception):
    """A construct the converter cannot hold, which it keeps as invalid syntax: an `Error` or an `error` term."""


# --- Source text ---


class _Source:
    """The text being parsed, as given and as tree-sitter parses it (`data`, which is `cleaned` in UTF-16), with
    conversions from tree-sitter's byte offsets to character offsets, and from character offsets to lines. The cleaned
    text has the same characters as the text, but for those the pre-pass rewrote."""

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

    def line(self, offset: int) -> int:
        return self.text.count("\n", 0, offset) + 1


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


# --- Literals ---


_ESCAPE = re.compile(r"\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[0-7]{1,3}|\r\n|[\s\S])")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\n": "", "\r\n": "", "\r": "",
            "\u2028": "", "\u2029": ""}  # a line terminator after `\` continues the string


def _unescape(body: str) -> str:
    """A string's value, of the text between its quotes: its escapes decoded, a surrogate pair written as two escapes
    joined."""
    def one(match: re.Match[str]) -> str:
        escape = match.group(1)
        if escape in _ESCAPES:
            return _ESCAPES[escape]
        if len(escape) > 1 and escape[0] in "ux":
            return chr(int(escape.strip("ux{}"), 16))
        if escape[0] in "01234567":  # `\0`, and a legacy octal escape
            return chr(int(escape, 8))
        return escape
    return _ESCAPE.sub(one, body).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def _number(text: str) -> _Node:
    """A number's or a bigint's literal: its value, a float or an int, its spelling, and what the spelling encodes."""
    digits = text.replace("_", "")
    bigint = digits.endswith("n")
    digits = digits.rstrip("n")
    base = {"0x": 16, "0o": 8, "0b": 2}.get(digits[:2].lower(), 10)
    integral = bigint or base != 10 or digits.isdigit()
    value: Any = int(digits[2:] if base != 10 else digits, base) if integral else float(digits)
    if not bigint:
        try:
            value = float(value)
        except OverflowError:  # beyond the largest number: JavaScript reads it as `Infinity`
            value = math.inf
    return _Node("literal", value=_scalar(value), text=text, base=base if integral else None,
                 separators="_" in text)


def _scalar(value: Any) -> Callable[[Any], Any]:
    """The writer of a literal's value, a scalar."""
    return lambda p: p.as_scalar(value)


# --- The tree, as written ---


class _Node:
    """A node of the tree, as the transaction writes it: the tag of its kind's branch (`binaryexpression`,
    `ifstatement`), and its properties, read and set as attributes, as 0.3's nodes were, absent ones read as None."""

    __slots__ = ("branch", "fields")

    def __init__(self, branch: str, /, **fields: Any):
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "fields", fields)

    def __getattr__(self, name: str) -> Any:
        return self.fields.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self.fields[name] = value


class _Branch:
    """A branch of a union that names what it holds rather than its kind: a `for`'s `init` (`expression`), a `for ...
    in`'s `left` (`pattern`), an export default's `declaration` (`statement`, `expression`)."""

    __slots__ = ("tag", "node")

    def __init__(self, tag: str, node: _Node):
        self.tag, self.node = tag, node


def _write(value: Any) -> Any:
    """The writer of what a property holds: a node, written to a union as its branch and to a value object's
    property as its properties; a list of nodes; a branch; or a scalar, or a scalar's writer, as it is."""
    if isinstance(value, list):
        return [_write(v) for v in value]
    if isinstance(value, _Branch):
        tag, inner = value.tag, _write(value.node)
        return lambda union: getattr(union, tag)(inner)
    if not isinstance(value, _Node):
        return value
    given = {name: _write(v) for name, v in value.fields.items() if v is not None and v != [] and v is not False}
    tag = value.branch

    def record(r: Any) -> Any:
        for name, v in given.items():
            getattr(r, name)(v)
        return r

    def write(visitor: Any) -> Any:
        schema = visitor.as_schema()
        if isinstance(schema, Schemas.OfProperty.Data):  # a property: its value's visitor writes it
            return visitor.as_value(write)
        if not isinstance(schema, Schemas.OfUnion.Data):
            return record(visitor)
        if schema.name == _TERM:  # a term recovered within an `error` term: TypeScript5's
            return visitor.typescript5(write)
        return getattr(visitor, tag)(record)

    return write


# --- The converter ---


class _Converter:
    """Rewrites a tree-sitter-typescript tree into statements and terms. `shift` and `origin` place a tree parsed from
    a part of the text: its offsets are `shift` past those of the part, and its text as written is `origin`'s."""

    def __init__(self, source: _Source, prepared: _Prepared, shift: int = 0, origin: _Source | None = None):
        self.source, self.pre, self.shift, self.origin = source, prepared, shift, origin or source
        self.consumed: set[int] = set()

    # Helpers

    def at(self, ts: _TS) -> int:
        return self.shift + self.source.offset(ts.start_byte)

    def text(self, ts: _TS) -> str:
        return self.source.data[ts.start_byte:ts.end_byte].decode("utf-16-le")

    def between(self, start: int, end: int) -> str:
        return self.source.data[start:end].decode("utf-16-le")

    def written(self, ts: _TS) -> str:
        """The text of `ts` as the source wrote it, before the pre-pass rewrote any of it."""
        return self.origin.text[self.at(ts):self.shift + self.source.offset(ts.end_byte)]

    def new(self, ts: _TS, branch: str, **fields: Any) -> _Node:
        """A statement, clause or member of the kind `branch`, with the line where `ts` starts."""
        return _Node(branch, line=self.origin.line(self.at(ts)), **fields)

    @staticmethod
    def kids(ts: _TS) -> list[_TS]:
        """The children of `ts`, without comments and what tree-sitter skipped (`ERROR`)."""
        return [c for c in ts.children if c.type not in _EXTRAS and c.type != "ERROR"]

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        """The named children of `ts`, without comments and what tree-sitter skipped (`ERROR`), which is never taken
        as an operand: what holds it is invalid as a whole."""
        return [c for c in ts.children if c.is_named and c.type not in _EXTRAS and c.type != "ERROR"]

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
        """A field the grammar requires, which tree-sitter always writes: it reports a missing one as an error."""
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

    def identifier(self, ts: _TS) -> _Node:
        return _Node("identifier", name=self.spelling(ts))

    def literal(self, ts: _TS) -> _Node:
        """A literal, with its spelling: a string, a number or a bigint, `true` or `false`; or a `constant`, `null` or a
        regular expression."""
        text = self.text(ts)
        if ts.type == "string":
            try:
                value = _unescape(text[1:-1])
            except (ValueError, OverflowError):  # an escape of no character, `\u{110000}`
                raise _Invalid(text) from None
            return _Node("literal", value=_scalar(value), text=text, quote=text[0])
        if ts.type == "number":
            return _number(text)
        if ts.type == "null":
            return _Node("constant", singleton="null", text=text)
        if ts.type == "regex":
            flags = self.field(ts, "flags")
            return _Node("constant", pattern=self.text(self.require(ts, "pattern")),
                         flags=None if flags is None else self.text(flags), text=text)
        return _Node("literal", value=_scalar(text == "true"), text=text)

    # Invalid syntax

    def unconsumed(self, ts: _TS) -> bool:
        """Whether `ts` holds invalid syntax (an `ERROR` or a `MISSING` node) below it that nothing made holds: no
        `error` or `missing` term, and no statement or member, which keeps its own."""
        stack = list(ts.children)
        while stack:
            node = stack.pop()
            if node.id in self.consumed:
                continue
            if node.type == "ERROR" or node.is_missing:
                return True
            stack.extend(node.children)
        return False

    def invalid(self, ts: _TS) -> _Node:
        """An expression, type or pattern that is invalid syntax as a whole: an `error` term, its text as written,
        and the terms recovered within it, each expression tree-sitter read there, in source order."""
        terms = self.recovered_terms(ts)
        self.consumed.add(ts.id)
        return _Node("error", text=self.written(ts), terms=terms)

    def recovered_terms(self, ts: _TS) -> list[_Node]:
        out: list[_Node] = []
        for c in ts.children:
            if c.is_named and c.type in self.EXPRESSIONS:
                out.append(self.expression(c))
            else:
                out += self.recovered_terms(c)
        return out

    def recovered(self, ts: _TS) -> list[_Node]:
        """The statements tree-sitter read within invalid syntax, in source order: each statement, and each block's."""
        out: list[_Node] = []
        for c in ts.children:
            if c.type == "statement_block":
                out += self.listed(c.children, self.statement, c.children[0])
            elif c.type in self.STATEMENTS:
                out.append(self.statement(c))
            else:
                out += self.recovered(c)
        return out

    def guarded(self, ts: _TS, convert: Callable[[_TS], Any]) -> Any:
        """What `convert` makes of `ts`, a statement, a switch's case or a class or enum member, or, where it is invalid
        syntax, an `Error`: tree-sitter skipped it (`ERROR`) or found it incomplete, or it holds what no `error` or
        `missing` term does, or it is a construct the converter cannot hold. The error's text is the node's, as
        written, and its body the statements recovered within it."""
        self.consumed.add(ts.id)
        try:
            made = convert(ts)
            if not (ts.has_error and self.unconsumed(ts)):
                return made
        except (Exception if ts.has_error else _Invalid):  # what tree-sitter recovered, shaped as no grammar rule is
            pass
        return self.new(ts, "error", text=self.written(ts), body=self.recovered(ts))

    def term(self, ts: _TS, methods: dict[str, Callable[[_Converter, _TS], Any]]) -> _Node:
        """The term of the expression or type `ts`, by `methods`: a `missing` term where tree-sitter expected one and
        found none, an `error` term where `ts` is invalid syntax (`invalid`), else its kind's."""
        if ts.is_missing:
            self.consumed.add(ts.id)
            return _Node("missing", kind=ts.type)
        method = methods.get(ts.type)
        if method is None:
            return self.invalid(ts)
        try:
            made = method(self, ts)
        except (Exception if ts.has_error else _Invalid):
            return self.invalid(ts)
        return self.invalid(ts) if ts.has_error and self.unconsumed(ts) else made

    # Lists of statements and members, with their comments

    def global_block(self, ts: _TS) -> bool:
        """Whether `ts` is the `global` of `global { ... }` in a module, which tree-sitter-typescript reads as an
        error followed by a block."""
        kids = [c for c in ts.children if not c.is_missing]
        following = ts.next_sibling
        return (ts.type in ("ERROR", "expression_statement") and len(kids) == 1 and kids[0].type == "identifier"
                and self.text(kids[0]) == "global" and following is not None and following.type == "statement_block"
                and ts.parent is not None and ts.parent.type == "statement_block")

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
            elif ts.type == "empty_statement" and out and out[-1].branch == "tsmoduledeclaration" and (
                    out[-1].body is None and previous is not None and previous.type != "comment"):
                pass  # the `;` that ends `declare module "a";`, which tree-sitter-typescript reads as a statement
            elif ts.type in ("ERROR", "expression_statement") and self.global_block(ts):
                block = ts.next_sibling
                self.consumed.add(ts.id)
                out.append(self.new(ts, "tsmoduledeclaration", moduleKind="global",
                                    id=_Node("identifier", name="global"), body=self.module_block(block)))
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

    def comment(self, ts: _TS, previous: _TS | None) -> _Node:
        """A comment, its text without its delimiters: trailing where nothing but blanks is between it and the end of
        `previous`, in the text as written."""
        text = self.text(ts)
        block = text.startswith("/*")
        trailing = previous is not None and "\n" not in self.origin.text[
            self.shift + self.source.offset(previous.end_byte):self.at(ts)]
        return self.new(ts, "comment", text=text[2:-2] if block else text[2:], block=block, trailing=trailing)

    @staticmethod
    def unlined(members: list[_Node]) -> list[_Node]:
        """An interface's or a type literal's members, its comments `TypeScript Types`' own, which have no line."""
        for member in members:
            if member.branch == "comment":
                del member.fields["line"]
        return members

    def program(self, ts: _TS) -> tuple[str | None, list[_Node]]:
        """A program's hashbang, without its `#!`, and its statements."""
        nodes = list(ts.children)
        hashbang = None
        if nodes and nodes[0].type == "hash_bang_line":
            hashbang = self.text(nodes[0])[2:]
            nodes = nodes[1:]
        return hashbang, self.listed(nodes, self.statement)

    def block(self, ts: _TS) -> _Node:
        return self.new(ts, "blockstatement", body=self.listed(ts.children, self.statement, ts.children[0]))

    # Statements

    def statement(self, ts: _TS) -> _Node:
        return self.guarded(ts, self.convert)

    def convert(self, ts: _TS) -> _Node:
        """The statement `ts`, with its line."""
        method = self.STATEMENTS.get(ts.type)
        if method is None:
            raise _Invalid(ts.type)
        made = method(self, ts)
        made.line = self.origin.line(self.at(ts))
        return made

    def expression_statement(self, ts: _TS) -> _Node:
        inner = self.named(ts)[0]
        if inner.type == "internal_module":  # `namespace A {}`, which tree-sitter-typescript reads as an expression
            return self.module(inner, "namespace")
        using = self.using(inner)
        if using is not None:
            return using
        return _Node("expressionstatement", expression=self.expression(inner))

    def using(self, ts: _TS) -> _Node | None:
        """`using x = f()` or `await using x = f()`, which tree-sitter-typescript reads as an assignment with a
        `using` token, perhaps awaited, and with several declarators, `using x = f(), y = g()`, as a sequence whose
        first expression is that and each other an assignment; None for any other expression. A declarator that is no
        assignment is invalid syntax: each needs its value."""
        parts = self.named(ts) if ts.type == "sequence_expression" else [ts]
        keyword, first = "using", parts[0]
        if first.type == "await_expression":
            keyword, first = "await using", self.named(first)[0]
        if first.type != "assignment_expression" or not self.has(first, "using"):
            return None
        declarators = []
        for part in (first, *parts[1:]):
            if part.type != "assignment_expression":
                raise _Invalid(part.type)
            declarators.append(_Node("variabledeclarator", id=self.binding(self.require(part, "left")),
                                     init=self.expression(self.require(part, "right"))))
        return _Node("variabledeclaration", declarationKind=keyword, declarations=declarators)

    def declarators(self, ts: _TS) -> list[_Node]:
        return [self.declarator(d) for d in self.named(ts) if d.type == "variable_declarator"]

    def declarator(self, ts: _TS) -> _Node:
        made = _Node("variabledeclarator", id=self.binding(self.require(ts, "name")), definite=self.has(ts, "!"))
        annotation = self.field(ts, "type")
        if annotation is not None:
            made.id.typeAnnotation = self.annotation(annotation)
        value = self.field(ts, "value")
        made.init = None if value is None else self.expression(value)
        return made

    def lexical_declaration(self, ts: _TS) -> _Node:
        return _Node("variabledeclaration", declarationKind=self.text(self.require(ts, "kind")),
                     declarations=self.declarators(ts))

    def variable_declaration(self, ts: _TS) -> _Node:
        return _Node("variabledeclaration", declarationKind="var", declarations=self.declarators(ts))

    def return_statement(self, ts: _TS) -> _Node:
        kids = self.named(ts)
        return _Node("returnstatement", argument=self.expression(kids[0]) if kids else None)

    def throw_statement(self, ts: _TS) -> _Node:
        return _Node("throwstatement", argument=self.expression(self.named(ts)[0]))

    def if_statement(self, ts: _TS) -> _Node:
        made = _Node("ifstatement", test=self.condition(self.require(ts, "condition")),
                     consequent=self.statement(self.require(ts, "consequence")))
        alternative = self.field(ts, "alternative")
        if alternative is not None:
            made.alternate = self.statement(self.named(alternative)[0])
        return made

    def condition(self, ts: _TS) -> _Node:
        """The expression in the parentheses a statement's syntax has: `if (test)`, `while (test)`."""
        return self.expression(self.named(ts)[0])

    def while_statement(self, ts: _TS) -> _Node:
        return _Node("whilestatement", test=self.condition(self.require(ts, "condition")),
                     body=self.statement(self.require(ts, "body")))

    def do_statement(self, ts: _TS) -> _Node:
        return _Node("dowhilestatement", body=self.statement(self.require(ts, "body")),
                     test=self.condition(self.require(ts, "condition")))

    def with_statement(self, ts: _TS) -> _Node:
        return _Node("withstatement", object=self.condition(self.require(ts, "object")),
                     body=self.statement(self.require(ts, "body")))

    def for_statement(self, ts: _TS) -> _Node:
        made = _Node("forstatement", body=self.statement(self.require(ts, "body")))
        init = self.require(ts, "initializer")
        if init.type in ("lexical_declaration", "variable_declaration"):
            made.init = self.convert(init)
        elif (using := self.using(init)) is not None:  # `for (using x = f(); ...)`
            using.line = self.origin.line(self.at(init))
            made.init = using
        elif init.type != "empty_statement":
            made.init = _Branch("expression", self.expression(init))
        conditions = [c for c in self.fields(ts, "condition") if c.type not in (";", "empty_statement")]
        made.test = self.expression(conditions[0]) if conditions else None
        increment = self.field(ts, "increment")
        made.update = None if increment is None else self.expression(increment)
        return made

    def for_in_statement(self, ts: _TS) -> _Node:
        left = self.require(ts, "left")
        kind = self.field(ts, "kind")
        if kind is not None:
            declarator = _Node("variabledeclarator", id=self.binding(left))
            value = self.field(ts, "value")
            if value is not None:
                declarator.init = self.expression(value)
            keyword = self.pre.usings.get(self.at(kind), self.text(kind))
            target: Any = self.new(kind, "variabledeclaration", declarationKind=keyword, declarations=[declarator])
        else:
            target = _Branch("pattern", self.target(left))
        right = self.expression(self.require(ts, "right"))
        body = self.statement(self.require(ts, "body"))
        if self.text(self.require(ts, "operator")) == "in":
            return _Node("forinstatement", left=target, right=right, body=body)
        return _Node("forofstatement", isAwait=self.kids(ts)[1].type == "await", left=target, right=right, body=body)

    def switch_statement(self, ts: _TS) -> _Node:
        cases: list[_Node] = []
        for case in [c for c in self.require(ts, "body").children if c.is_named]:
            if case.type == "comment":  # after a case, which tree-sitter-typescript ends where its last statement does
                if cases:
                    cases[-1].consequent = (cases[-1].consequent or []) + [self.comment(case, case.prev_sibling)]
                continue
            cases.append(self.guarded(case, self.switch_case))
        return _Node("switchstatement", discriminant=self.condition(self.require(ts, "value")), cases=cases)

    def switch_case(self, ts: _TS) -> _Node:
        value = self.field(ts, "value")
        body = [c for c in ts.children if c.start_byte > (value or ts.children[0]).end_byte]
        colon = next(c for c in ts.children if c.type == ":")
        return self.new(ts, "switchcase", test=None if value is None else self.expression(value),
                        consequent=self.listed([c for c in body if c.start_byte > colon.start_byte], self.statement,
                                               colon))

    def try_statement(self, ts: _TS) -> _Node:
        made = _Node("trystatement", block=self.block(self.require(ts, "body")))
        handler = self.field(ts, "handler")
        if handler is not None:
            clause = self.new(handler, "catchclause", body=self.block(self.require(handler, "body")))
            parameter = self.field(handler, "parameter")
            if parameter is not None:
                clause.param = self.binding(parameter)
                annotation = self.field(handler, "type")
                if annotation is not None:
                    clause.param.typeAnnotation = self.annotation(annotation)
            made.handler = clause
        finalizer = self.field(ts, "finalizer")
        if finalizer is not None:
            made.finalizer = self.block(self.require(finalizer, "body"))
        return made

    def labeled_statement(self, ts: _TS) -> _Node:
        return _Node("labeledstatement", label=self.identifier(self.require(ts, "label")),
                     body=self.statement(self.require(ts, "body")))

    def jump(branch: str) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        def convert(self: _Converter, ts: _TS) -> Any:
            label = self.field(ts, "label")
            return _Node(branch, label=None if label is None else self.identifier(label))
        return convert

    def simple(branch: str) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        return lambda self, ts: _Node(branch)

    # Functions and classes

    def function_declaration(self, ts: _TS) -> _Node:
        made = _Node("functiondeclaration", isAsync=self.has(ts, "async"), generator=self.has(ts, "*"),
                     id=self.identifier(self.require(ts, "name")), body=self.block(self.require(ts, "body")))
        self.signature(ts, made)
        return made

    def signature(self, ts: _TS, made: _Node) -> None:
        """The type parameters, parameters and return type of a function, method or signature."""
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        returns = self.field(ts, "return_type") or (
            self.field(ts, "type") if ts.type == "construct_signature" else None)
        if returns is not None:
            made.returnType = self.annotation(returns)

    def function_signature(self, ts: _TS) -> _Node:
        made = _Node("tsdeclarefunction", isAsync=self.has(ts, "async"), generator=self.has(ts, "*"),
                     id=self.identifier(self.require(ts, "name")))
        self.signature(ts, made)
        return made

    def parameters(self, ts: _TS) -> list[_Node]:
        return [self.parameter(p) for p in self.named(ts)]

    def parameter(self, ts: _TS) -> _Node:
        """A `required_parameter` or `optional_parameter`: a binding, perhaps with `?`, a type and a default, or a
        parameter property."""
        pattern = self.require(ts, "pattern")  # a parameter's, which `name` only is in a tuple type
        binding = _Node("identifier", name="this") if pattern.type == "this" else self.binding(pattern)
        annotation = self.field(ts, "type")
        if annotation is not None:
            binding.typeAnnotation = self.annotation(annotation)
        if ts.type == "optional_parameter":
            binding.optional = True
        decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        value = self.field(ts, "value")
        result = binding
        if value is not None:
            result = _Node("assignmentpattern", left=binding, right=self.expression(value))
        modifiers = self.tokens_before(ts, "pattern")
        accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        if accessibility or {"readonly", "override"} & modifiers:
            return _Node("tsparameterproperty", decorators=decorators, accessibility=accessibility,
                         override="override" in modifiers, readonly="readonly" in modifiers, parameter=result)
        result.decorators = decorators
        return result

    def class_declaration(self, ts: _TS) -> _Node:
        made = _Node("classdeclaration", abstract=ts.type == "abstract_class_declaration")
        self.class_parts(ts, made)
        return made

    def class_parts(self, ts: _TS, made: _Node) -> None:
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
                    made.implements = [_Node("tsclassimplements", **self.heritage(t)) for t in self.named(clause)]
        made.body = _Node("classbody", body=self.members(self.require(ts, "body")))

    def members(self, body: _TS) -> list[_Node]:
        """A class body's members and comments; decorators before a method, which tree-sitter-typescript lists
        beside it (and beside no other member), are its own."""
        pending: list[_Node] = []

        def member(ts: _TS) -> Any:
            if ts.type == "decorator":
                pending.append(self.decorator(ts))
                return None
            made = self.member(ts)
            if pending:
                made.decorators = pending + (made.decorators or [])
            pending.clear()
            return made

        listed = self.listed(body.children, lambda ts: self.guarded(ts, member), body.children[0])
        return [m for m in listed if m is not None]

    def heritage(self, ts: _TS) -> dict[str, Any]:
        """The expression and type arguments of a type in `implements` or `extends`."""
        if ts.type == "generic_type":
            return {"expression": self.type_name_expression(self.require(ts, "name")),
                    "typeArguments": self.type_arguments(self.require(ts, "type_arguments"))}
        return {"expression": self.type_name_expression(ts)}

    def type_name_expression(self, ts: _TS) -> _Node:
        """A type's name, as the expression `implements` and `extends` take: `a.b.C`."""
        if ts.type == "nested_type_identifier":
            return _Node("memberexpression", object=self.type_name_expression(self.require(ts, "module")),
                         property=self.identifier(self.require(ts, "name")))
        if ts.type == "nested_identifier":
            return _Node("memberexpression", object=self.type_name_expression(self.require(ts, "object")),
                         property=self.identifier(self.require(ts, "property")))
        return self.identifier(ts)

    def decorator(self, ts: _TS) -> _Node:
        return _Node("decorator", expression=self.expression(self.named(ts)[0]))

    def key(self, ts: _TS) -> tuple[_Node, bool]:
        """A member's key, and whether it is computed."""
        if ts.type == "computed_property_name":
            return self.expression(self.named(ts)[0]), True
        if ts.type == "private_property_identifier":
            return _Node("privateidentifier", name=self.text(ts)[1:]), False
        if ts.type in ("string", "number"):
            return self.literal(ts), False
        return self.identifier(ts), False

    def member(self, ts: _TS) -> _Node:
        """A class member."""
        if ts.type == "class_static_block":
            body = self.require(ts, "body")
            return self.new(ts, "staticblock", body=self.listed(body.children, self.statement, body.children[0]))
        if ts.type == "index_signature":
            return self.index_signature(ts)
        if ts.type == "public_field_definition":
            return self.field_definition(ts)
        return self.method(ts)  # a method_definition, method_signature or abstract_method_signature

    def modifiers(self, ts: _TS, made: _Node, modifiers: set[str]) -> None:
        made.decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        made.accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        made.static = "static" in modifiers
        made.override = "override" in modifiers

    def field_definition(self, ts: _TS) -> _Node:
        modifiers = self.tokens_before(ts, "name")
        accessor = "accessor" in modifiers or any(
            self.at(ts) <= o <= self.at(self.require(ts, "name")) for o in self.pre.accessors)
        abstract = "abstract" in modifiers
        branch = ("tsabstractaccessorproperty" if abstract else "accessorproperty") if accessor else (
            "tsabstractpropertydefinition" if abstract else "propertydefinition")
        made = self.new(ts, branch)
        self.modifiers(ts, made, modifiers)
        made.declare, made.readonly = "declare" in modifiers, "readonly" in modifiers
        made.key, made.computed = self.key(self.require(ts, "name"))
        made.optional, made.definite = self.has(ts, "?"), self.has(ts, "!")
        annotation = self.field(ts, "type")
        if annotation is not None:
            made.typeAnnotation = self.annotation(annotation)
        value = self.field(ts, "value")
        made.value = None if value is None else self.expression(value)
        return made

    def method(self, ts: _TS) -> _Node:
        modifiers = self.tokens_before(ts, "name")
        name = self.require(ts, "name")
        abstract = ts.type == "abstract_method_signature" or "abstract" in modifiers
        made = self.new(ts, "tsabstractmethoddefinition" if abstract else "methoddefinition")
        self.modifiers(ts, made, modifiers)
        made.key, made.computed = self.key(name)
        made.methodKind = "get" if "get" in modifiers else "set" if "set" in modifiers else "method"
        if made.methodKind == "method" and not made.static and not made.computed and self.text(name) in (
                "constructor", "'constructor'", '"constructor"'):
            made.methodKind = "constructor"
        made.optional = any(c.type == "?" and c.start_byte > name.start_byte for c in ts.children)
        body = self.field(ts, "body")
        value = _Node("functionexpression", block=self.block(body)) if body is not None else (
            _Node("tsemptybodyfunctionexpression"))
        value.isAsync, value.generator = "async" in modifiers, "*" in modifiers
        self.signature(ts, value)
        made.value = value
        return made

    def index_signature(self, ts: _TS) -> _Node:
        if any(c.type == "mapped_type_clause" for c in self.named(ts)):
            raise _Invalid(ts.type)  # a mapped type, as a member: no member holds one
        modifiers = self.tokens_before(ts, "type")
        index = self.require(ts, "index_type")
        parameter = self.identifier(self.require(ts, "name"))
        parameter.typeAnnotation = _Node("tstypeannotation", typeAnnotation=self.type(index))
        made = _Node("tsindexsignature", parameters=[parameter], readonly="readonly" in modifiers,
                     static="static" in modifiers, typeAnnotation=self.annotation(self.require(ts, "type")))
        made.accessibility = next((m for m in modifiers if m in ("public", "private", "protected")), None)
        return made

    # Modules

    def import_statement(self, ts: _TS) -> _Node:
        kind = "type" if self.kids(ts)[1].type == "type" else "value"
        require = next((c for c in self.named(ts) if c.type == "import_require_clause"), None)
        if require is not None:
            reference = _Node("tsexternalmodulereference", expression=self.literal(self.require(require, "source")))
            return _Node("tsimportequalsdeclaration", importKind=kind, id=self.identifier(self.named(require)[0]),
                         moduleReference=reference)
        made = _Node("importdeclaration", importKind=kind, specifiers=[],
                     source=self.literal(self.require(ts, "source")))
        if self.at(ts) in self.pre.deferred:
            made.phase = "defer"
        clause = next((c for c in self.named(ts) if c.type == "import_clause"), None)
        if clause is not None:
            for part in self.named(clause):
                if part.type == "identifier":
                    made.specifiers.append(_Node("importdefaultspecifier", local=self.identifier(part)))
                elif part.type == "namespace_import":
                    made.specifiers.append(_Node("importnamespacespecifier",
                                                 local=self.identifier(self.named(part)[0])))
                else:
                    made.specifiers += [self.import_specifier(s) for s in self.named(part)]
        attributes = next((c for c in self.named(ts) if c.type == "import_attribute"), None)
        if attributes is not None:
            made.attributes = self.attributes(attributes)
        return made

    def attributes(self, ts: _TS) -> list[_Node]:
        out = []
        for pair in self.named(self.named(ts)[0]):
            key = self.require(pair, "key")
            out.append(_Node("importattribute", key=self.literal(key) if key.type == "string" else self.identifier(key),
                             value=self.literal(self.require(pair, "value"))))
        return out

    def import_specifier(self, ts: _TS) -> _Node:
        name = self.require(ts, "name")
        imported = self.literal(name) if name.type == "string" else self.identifier(name)
        alias = self.field(ts, "alias")
        local = self.identifier(alias) if alias is not None else self.identifier(name)
        kind = "type" if self.kids(ts)[0].type == "type" else "value"
        return _Node("importspecifier", importKind=kind, imported=imported, local=local)

    def import_alias(self, ts: _TS) -> _Node:
        name, reference = self.named(ts)
        return _Node("tsimportequalsdeclaration", importKind="value", id=self.identifier(name),
                     moduleReference=self.entity_name(reference))

    def entity_name(self, ts: _TS) -> _Node:
        """`a.b.c` as a type's or a namespace's name: an `Identifier` or a `TSQualifiedName`."""
        if ts.type in ("nested_identifier", "member_expression"):
            return _Node("tsqualifiedname", left=self.entity_name(self.require(ts, "object")),
                         right=self.identifier(self.require(ts, "property")))
        if ts.type == "nested_type_identifier":
            return _Node("tsqualifiedname", left=self.entity_name(self.require(ts, "module")),
                         right=self.identifier(self.require(ts, "name")))
        if ts.type == "this":
            return _Node("thisexpression")
        return self.identifier(ts)

    def export_statement(self, ts: _TS) -> _Node:
        kids = self.kids(ts)
        decorators = [self.decorator(d) for d in self.fields(ts, "decorator")]
        if kids[1].type == "=":
            return _Node("tsexportassignment", expression=self.expression(self.named(ts)[-1]))
        if kids[1].type == "as":
            return _Node("tsnamespaceexportdeclaration", id=self.identifier(self.named(ts)[-1]))
        declaration = self.field(ts, "declaration")
        value = self.field(ts, "value")
        if self.has(ts, "default"):
            target = declaration or self.require(ts, "value")
            if target.type in ("function_expression", "generator_function", "class") and value is not None:
                converted: Any = _Branch("statement", self.default_declaration(target))
            elif declaration is not None:
                converted = _Branch("statement", self.statement(declaration))
            else:
                converted = _Branch("expression", self.expression(target))
            if decorators and converted.node.branch == "classdeclaration":
                converted.node.decorators = decorators + converted.node.decorators
            return _Node("exportdefaultdeclaration", declaration=converted)
        source = self.field(ts, "source")
        if self.has(ts, "*") or any(c.type == "namespace_export" for c in ts.children):
            made = _Node("exportalldeclaration", source=self.literal(source))
            made.exportKind = "type" if self.at(ts) in self.pre.type_exports or kids[1].type == "type" else "value"
            namespace = next((c for c in self.named(ts) if c.type == "namespace_export"), None)
            if namespace is not None:
                exported = self.named(namespace)[0]
                made.exported = self.literal(exported) if exported.type == "string" else self.identifier(exported)
            return made  # tree-sitter-typescript reads no attributes here
        made = _Node("exportnameddeclaration")
        if declaration is not None:
            converted = self.statement(declaration)
            if decorators and converted.branch == "classdeclaration":
                converted.decorators = decorators + converted.decorators
            made.declaration = converted
            made.exportKind = "type" if converted.branch in (
                "tsinterfacedeclaration", "tstypealiasdeclaration") or converted.declare else "value"
            return made
        made.exportKind = "type" if kids[1].type == "type" else "value"
        clause = next(c for c in self.named(ts) if c.type == "export_clause")
        made.specifiers = [self.export_specifier(s) for s in self.named(clause)]
        if source is not None:
            made.source = self.literal(source)
        return made  # tree-sitter-typescript reads no attributes here

    def default_declaration(self, ts: _TS) -> _Node:
        """`export default function ...` or `export default class ...`, which are declarations, unnamed: a named one
        is a declaration to tree-sitter-typescript too."""
        if ts.type == "class":
            made = self.new(ts, "classdeclaration")
            self.class_parts(ts, made)
            return made
        made = self.new(ts, "functiondeclaration", isAsync=self.has(ts, "async"),
                        generator=ts.type == "generator_function", body=self.block(self.require(ts, "body")))
        self.signature(ts, made)
        return made

    def export_specifier(self, ts: _TS) -> _Node:
        name = self.require(ts, "name")
        local = self.literal(name) if name.type == "string" else self.identifier(name)
        alias = self.field(ts, "alias") or name
        exported = self.literal(alias) if alias.type == "string" else self.identifier(alias)
        kind = "type" if self.kids(ts)[0].type == "type" else "value"
        return _Node("exportspecifier", exportKind=kind, local=local, exported=exported)

    def ambient_declaration(self, ts: _TS) -> _Node:
        """`declare ...`, or `declare global { ... }`."""
        inner = self.named(ts)[0]
        if inner.type == "statement_block":
            return _Node("tsmoduledeclaration", declare=True, moduleKind="global",
                         id=_Node("identifier", name="global"), body=self.module_block(inner))
        made = self.convert(inner)
        made.declare = True
        return made

    def module_block(self, ts: _TS) -> _Node:
        return _Node("tsmoduleblock", body=self.listed(ts.children, self.statement, ts.children[0]))

    def module(self, ts: _TS, kind: str | None = None) -> _Node:
        name = self.require(ts, "name")
        keyword = kind or ("namespace" if ts.type == "internal_module" else "module")
        made = _Node("tsmoduledeclaration", moduleKind=keyword,
                     id=self.literal(name) if name.type == "string" else self.entity_name(name))
        body = self.field(ts, "body")
        made.body = None if body is None else self.module_block(body)
        return made

    def module_statement(self, ts: _TS) -> _Node:
        return self.module(ts)

    def type_alias_declaration(self, ts: _TS) -> _Node:
        value = self.require(ts, "value")
        made = _Node("tstypealiasdeclaration", id=self.identifier(self.require(ts, "name")),
                     typeAnnotation=_Node("tsintrinsickeyword") if (
                         value.type == "type_identifier" and self.text(value) == "intrinsic") else self.type(value))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        return made

    def interface_declaration(self, ts: _TS) -> _Node:
        made = _Node("tsinterfacedeclaration", id=self.identifier(self.require(ts, "name")))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        clause = next((c for c in self.named(ts) if c.type == "extends_type_clause"), None)
        if clause is not None:
            made.extends = [_Node("tsinterfaceheritage", **self.heritage(t)) for t in self.named(clause)]
        body = self.require(ts, "body")
        made.body = _Node("tsinterfacebody", body=self.unlined(self.listed(body.children, self.type_member,
                                                                            body.children[0])))
        return made

    def enum_declaration(self, ts: _TS) -> _Node:
        body = self.require(ts, "body")
        made = _Node("tsenumdeclaration", const=self.has(ts, "const"), id=self.identifier(self.require(ts, "name")))
        made.body = _Node("tsenumbody", members=self.listed(body.children,
                                                            lambda m: self.guarded(m, self.enum_member),
                                                            body.children[0]))
        return made

    def enum_member(self, ts: _TS) -> _Node:
        if ts.type == "ERROR":  # what tree-sitter skipped where a member stands, which `key` would read as a name
            raise _Invalid(ts.type)
        if ts.type == "enum_assignment":
            key, computed = self.key(self.require(ts, "name"))
            return self.new(ts, "tsenummember", computed=computed, id=key,
                            initializer=self.expression(self.require(ts, "value")))
        key, computed = self.key(ts)
        return self.new(ts, "tsenummember", computed=computed, id=key)

    STATEMENTS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "expression_statement": expression_statement, "lexical_declaration": lexical_declaration,
        "variable_declaration": variable_declaration, "return_statement": return_statement,
        "throw_statement": throw_statement, "if_statement": if_statement, "while_statement": while_statement,
        "do_statement": do_statement, "with_statement": with_statement, "for_statement": for_statement,
        "for_in_statement": for_in_statement, "switch_statement": switch_statement, "try_statement": try_statement,
        "labeled_statement": labeled_statement, "break_statement": jump("breakstatement"),
        "continue_statement": jump("continuestatement"), "empty_statement": simple("emptystatement"),
        "debugger_statement": simple("debuggerstatement"), "statement_block": lambda self, ts: self.block(ts),
        "function_declaration": function_declaration, "generator_function_declaration": function_declaration,
        "function_signature": function_signature, "class_declaration": class_declaration,
        "abstract_class_declaration": class_declaration, "import_statement": import_statement,
        "import_alias": import_alias, "export_statement": export_statement,
        "ambient_declaration": ambient_declaration, "module": module_statement,
        "internal_module": module_statement, "type_alias_declaration": type_alias_declaration,
        "interface_declaration": interface_declaration, "enum_declaration": enum_declaration,
    }

    # Bindings and patterns: `TypeScript Patterns` terms

    def binding(self, ts: _TS) -> _Node:
        """What a declaration or a parameter binds: a name or a destructuring pattern."""
        if ts.type == "identifier" or ts.type == "undefined":
            return self.identifier(ts)
        return self.target(ts)

    def target(self, ts: _TS) -> _Node:
        """An assignment's or a binding's target, which tree-sitter-typescript writes as a pattern; an `error` term
        where it is an expression no pattern may be (`f() = 1`)."""
        if ts.type == "array_pattern":
            return _Node("arraypattern", elements=self.elements(ts, self.target))
        if ts.type == "object_pattern":
            return _Node("objectpattern", properties=[self.pattern_property(p) for p in self.named(ts)])
        if ts.type == "assignment_pattern":
            return _Node("assignmentpattern", left=self.target(self.require(ts, "left")),
                         right=self.expression(self.require(ts, "right")))
        if ts.type == "rest_pattern":
            return _Node("restelement", argument=self.target(self.named(ts)[0]))
        if ts.type == "identifier" or ts.type == "undefined":
            return self.identifier(ts)
        made = self.expression(ts)
        return made if made.branch in _PATTERNS else self.invalid(ts)

    def pattern_property(self, ts: _TS) -> _Node:
        if ts.type == "rest_pattern":
            return _Node("restelement", argument=self.target(self.named(ts)[0]))
        if ts.type == "shorthand_property_identifier_pattern":
            return _Node("property", propertyKind="init", key=self.identifier(ts), shorthand=True,
                         value=self.identifier(ts))
        if ts.type == "object_assignment_pattern":  # `{ a = 1 }`, whose left is always a shorthand name
            left = self.require(ts, "left")
            value = _Node("assignmentpattern", left=self.identifier(left),
                          right=self.expression(self.require(ts, "right")))
            return _Node("property", propertyKind="init", key=self.identifier(left), shorthand=True, value=value)
        key, computed = self.key(self.require(ts, "key"))
        return _Node("property", propertyKind="init", key=key, computed=computed,
                     value=self.target(self.require(ts, "value")))

    def elements(self, ts: _TS, convert: Callable[[_TS], Any]) -> list[_Node]:
        """The elements of an array or an array pattern, with an `elision` for each hole."""
        out: list[_Node] = []
        pending = True  # a comma now leaves a hole
        for c in self.kids(ts)[1:-1]:
            if c.type == ",":
                if pending:
                    out.append(_Node("elision"))
                pending = True
            else:
                out.append(convert(c))
                pending = False
        return out

    # Expressions: `TypeScript5` terms

    def expression(self, ts: _TS) -> _Node:
        return self.term(ts, self.EXPRESSIONS)

    def parenthesized(self, ts: _TS) -> _Node:
        if self.field(ts, "type") is not None:
            raise _Invalid(ts.type)  # `(a: T)`, Flow's annotation in parentheses
        return _Node("parenthesizedexpression", expression=self.expression(self.named(ts)[0]))

    def sequence(self, ts: _TS) -> _Node:
        return _Node("sequenceexpression", expressions=[self.expression(k) for k in self.named(ts)])

    def array(self, ts: _TS) -> _Node:
        return _Node("arrayexpression", elements=self.elements(ts, self.element))

    def element(self, ts: _TS) -> _Node:
        if ts.type == "spread_element":
            return _Node("spreadelement", argument=self.expression(self.named(ts)[0]))
        return self.expression(ts)

    def object(self, ts: _TS) -> _Node:
        properties: list[_Node] = []
        for p in self.named(ts):
            if p.type == "spread_element":
                properties.append(self.element(p))
            elif p.type == "shorthand_property_identifier":
                properties.append(_Node("property", propertyKind="init", key=self.identifier(p), shorthand=True,
                                        value=self.identifier(p)))
            elif p.type == "pair":
                key, computed = self.key(self.require(p, "key"))
                properties.append(_Node("property", propertyKind="init", key=key, computed=computed,
                                        value=self.expression(self.require(p, "value"))))
            else:
                properties.append(self.object_method(p))  # a method_definition
        return _Node("objectexpression", properties=properties)

    def object_method(self, ts: _TS) -> _Node:
        modifiers = self.tokens_before(ts, "name")
        key, computed = self.key(self.require(ts, "name"))
        value = _Node("functionexpression", isAsync="async" in modifiers, generator="*" in modifiers,
                      block=self.block(self.require(ts, "body")))
        self.signature(ts, value)
        kind = "get" if "get" in modifiers else "set" if "set" in modifiers else "init"
        return _Node("property", propertyKind=kind, key=key, computed=computed, method=kind == "init", value=value)

    def function_expression(self, ts: _TS) -> _Node:
        made = _Node("functionexpression", isAsync=self.has(ts, "async"),
                     generator=ts.type == "generator_function" or self.has(ts, "*"),
                     block=self.block(self.require(ts, "body")))
        name = self.field(ts, "name")
        made.id = None if name is None else self.identifier(name)
        self.signature(ts, made)
        return made

    def arrow_function(self, ts: _TS) -> _Node:
        made = _Node("arrowfunctionexpression", isAsync=self.has(ts, "async"))
        parameter = self.field(ts, "parameter")
        if parameter is not None:
            made.params = [self.identifier(parameter)]
        else:
            self.signature(ts, made)
        body = self.require(ts, "body")
        if body.type == "statement_block":
            made.block = self.block(body)
        else:
            made.body = self.expression(body)
        return made

    def class_expression(self, ts: _TS) -> _Node:
        made = _Node("classexpression")
        self.class_parts(ts, made)
        made.classBody = made.fields.pop("body")
        return made

    def template(self, ts: _TS) -> _Node:
        quasis, expressions = self.template_parts(ts, "template_substitution", self.expression)
        return _Node("templateliteral", quasis=quasis, expressions=expressions)

    def template_parts(self, ts: _TS, holder: str, convert: Callable[[_TS], Any]) -> tuple[list[_Node], list[_Node]]:
        """The texts of a template and what is substituted between them."""
        quasis: list[_Node] = []
        values: list[_Node] = []
        at = ts.start_byte + 2  # past the backtick, a UTF-16 unit
        for part in self.named(ts):
            if part.type != holder:
                continue
            quasis.append(_Node("templateelement", raw=self.between(at, part.start_byte)))
            values.append(convert(self.named(part)[0]))
            at = part.end_byte
        quasis.append(_Node("templateelement", raw=self.between(at, ts.end_byte - 2), tail=True))
        return quasis, values

    def member_expression(self, ts: _TS) -> _Node:
        typed = self.typed_member(ts)
        if typed is not None:
            return typed
        return self.link(ts)

    def typed_member(self, ts: _TS) -> _Node | None:
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
        while reference.branch in ("tsuniontype", "tsintersectiontype"):
            reference = reference.types[-1]
        name = reference.typeName
        for n in names:
            name = _Node("tsqualifiedname", left=name, right=self.identifier(n))
        reference.typeName = name
        branch = "tsasexpression" if node.type == "as_expression" else "tssatisfiesexpression"
        return _Node(branch, expression=self.expression(expression), typeAnnotation=converted)

    def chain(self, ts: _TS) -> tuple[_Node, bool]:
        """A member, a call or a non-null assertion, and whether an optional link (`?.`) is in its chain."""
        if ts.type == "member_expression":
            target, optional = self.chain(self.require(ts, "object"))
            link = self.field(ts, "optional_chain") is not None
            key, _ = self.key(self.require(ts, "property"))
            return _Node("memberexpression", object=target, optional=link, property=key), optional or link
        if ts.type == "subscript_expression":
            target, optional = self.chain(self.require(ts, "object"))
            link = self.field(ts, "optional_chain") is not None
            return _Node("memberexpression", object=target, optional=link, computed=True,
                         property=self.expression(self.require(ts, "index"))), optional or link
        if ts.type == "call_expression" and self.require(ts, "arguments").type != "template_string" and (
                self.require(ts, "function").type != "import"):
            target, optional = self.chain(self.require(ts, "function"))
            link = self.has(ts, "?.") or any(c.type == "optional_chain" for c in ts.children)
            made = _Node("callexpression", callee=target, optional=link,
                         arguments=self.arguments(self.require(ts, "arguments")))
            arguments = self.field(ts, "type_arguments")
            if arguments is not None:
                made.typeArguments = self.type_arguments(arguments)
            return made, optional or link
        if ts.type == "non_null_expression":
            inner = self.named(ts)[0]
            if inner.type == "binary_expression":
                return self.non_null_last(self.expression(inner)), False
            target, optional = self.chain(inner)
            return _Node("tsnonnullexpression", expression=target), optional
        return self.expression(ts), False

    def arguments(self, ts: _TS) -> list[_Node]:
        """A call's arguments; a hole among them, which tree-sitter-typescript reads (`f(a,,b)`), is invalid."""
        made = self.elements(ts, self.element)
        if any(a.branch == "elision" for a in made):
            raise _Invalid(ts.type)
        return made

    def non_null_last(self, node: _Node) -> _Node:
        """`node` with its last operand asserted non-null: `a ?? b!` is `a ?? (b!)`, which tree-sitter-typescript
        reads as `(a ?? b)!`."""
        if node.branch in ("binaryexpression", "logicalexpression"):
            node.right = self.non_null_last(node.right)
            return node
        return _Node("tsnonnullexpression", expression=node)

    def link(self, ts: _TS) -> _Node:
        made, optional = self.chain(ts)
        return _Node("chainexpression", expression=made) if optional else made

    def call(self, ts: _TS) -> _Node:
        function = self.require(ts, "function")
        arguments = self.require(ts, "arguments")
        if arguments.type == "template_string":
            # tree-sitter-typescript reads `f<T>`x`` as comparisons: a tagged template has no type arguments
            return _Node("taggedtemplateexpression", tag=self.expression(function), quasi=self.template(arguments))
        if function.type == "import":
            values = [self.expression(a) for a in self.named(arguments)]
            return _Node("importexpression", source=values[0], options=values[1] if len(values) > 1 else None)
        return self.link(ts)

    def new_expression(self, ts: _TS) -> _Node:
        made = _Node("newexpression", callee=self.expression(self.require(ts, "constructor")))
        arguments = self.field(ts, "arguments")
        if arguments is not None:
            made.arguments = self.arguments(arguments)
        type_arguments = self.field(ts, "type_arguments")
        if type_arguments is not None:
            made.typeArguments = self.type_arguments(type_arguments)
        return made

    def meta_property(self, ts: _TS) -> _Node:
        meta, property_ = self.text(ts).replace(" ", "").split(".")
        return _Node("metaproperty", meta=_Node("identifier", name=meta), property=_Node("identifier", name=property_))

    def update(self, ts: _TS) -> _Node:
        operator = self.require(ts, "operator")
        argument = self.require(ts, "argument")
        return _Node("updateexpression", operator=self.text(operator), prefix=operator.start_byte < argument.start_byte,
                     argument=self.expression(argument))

    def unary(self, ts: _TS) -> _Node:
        return _Node("unaryexpression", operator=self.text(self.require(ts, "operator")),
                     argument=self.expression(self.require(ts, "argument")))

    def binary(self, ts: _TS) -> _Node:
        operator = self.text(self.require(ts, "operator"))
        left = self.require(ts, "left")
        converted = _Node("privateidentifier", name=self.text(left)[1:]) if (
            left.type == "private_property_identifier") else self.expression(left)
        right = self.expression(self.require(ts, "right"))
        if left.type in ("as_expression", "satisfies_expression"):
            return self.binary_last(converted, operator, right)
        return _Node("logicalexpression" if operator in ("&&", "||", "??") else "binaryexpression", left=converted,
                     operator=operator, right=right)

    def binary_last(self, left: _Node, operator: str, right: _Node) -> _Node:
        """`left operator right`, where `left` was an `as` or `satisfies` expression that `typed_last` moved onto its
        last operand: `a || b as T && c` is `a || (b as T && c)`, which tree-sitter-typescript reads as
        `((a || b) as T) && c`. The operator applies to that last operand when it binds tighter than `left`'s."""
        if left.branch in ("binaryexpression", "logicalexpression") and _BINDS[left.operator] < _BINDS[operator]:
            left.right = self.binary_last(left.right, operator, right)
            return left
        return _Node("logicalexpression" if operator in ("&&", "||", "??") else "binaryexpression", left=left,
                     operator=operator, right=right)

    def assignment(self, ts: _TS) -> _Node:
        if self.has(ts, "using"):  # a `using` declaration where only an expression stands: invalid syntax
            raise _Invalid(ts.type)
        operator = self.field(ts, "operator")
        return _Node("assignmentexpression", left=self.target(self.require(ts, "left")),
                     operator="=" if operator is None else self.text(operator),
                     right=self.expression(self.require(ts, "right")))

    def ternary(self, ts: _TS) -> _Node:
        return _Node("conditionalexpression", test=self.expression(self.require(ts, "condition")),
                     consequent=self.expression(self.require(ts, "consequence")),
                     alternate=self.expression(self.require(ts, "alternative")))

    def yield_(self, ts: _TS) -> _Node:
        kids = self.named(ts)
        return _Node("yieldexpression", delegate=self.has(ts, "*"),
                     argument=self.expression(kids[0]) if kids else None)

    def typed_last(self, node: _Node, branch: str, type_: _Node) -> _Node:
        """`node` with `as type` (or `satisfies type`) applied to its last operand when that binds tighter than its
        operator: `a ?? b as T` is `a ?? (b as T)`, which tree-sitter-typescript reads as `(a ?? b) as T`."""
        if node.branch in ("binaryexpression", "logicalexpression") and node.operator in _LOOSER_THAN_AS:
            node.right = self.typed_last(node.right, branch, type_)
            return node
        return _Node(branch, expression=node, typeAnnotation=type_)

    def typed(branch: str) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        """`expression as type` or `expression satisfies type`."""
        def convert(self: _Converter, ts: _TS) -> Any:
            kids = self.named(ts)
            expression = kids[0]
            if len(kids) == 1 or kids[1].type == "const":  # `as const`
                converted = _Node("tstypereference", typeName=_Node("identifier", name="const"))
            else:
                converted = self.type(kids[1])
            inner = self.expression(expression)
            if expression.type == "binary_expression":
                return self.typed_last(inner, branch, converted)
            return _Node(branch, expression=inner, typeAnnotation=converted)
        return convert

    def type_assertion(self, ts: _TS) -> _Node:
        arguments, expression = self.named(ts)
        return _Node("tstypeassertion", typeAnnotation=self.type(self.named(arguments)[0]),
                     expression=self.expression(expression))

    def instantiation(self, ts: _TS) -> _Node:
        return _Node("tsinstantiationexpression", expression=self.expression(self.named(ts)[0]),
                     typeArguments=self.type_arguments(self.require(ts, "type_arguments")))

    EXPRESSIONS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "identifier": lambda self, ts: _Node("importexpression", **self.import_call(ts)) if (
            self.at(ts) in self.pre.imports) else self.identifier(ts),
        "undefined": lambda self, ts: _Node("identifier", name="undefined"),
        "number": literal, "string": literal, "true": literal, "false": literal, "null": literal, "regex": literal,
        "this": lambda self, ts: _Node("thisexpression"), "super": lambda self, ts: _Node("super"),
        "parenthesized_expression": parenthesized, "sequence_expression": sequence, "array": array, "object": object,
        "function_expression": function_expression, "generator_function": function_expression,
        "arrow_function": arrow_function, "class": class_expression, "template_string": template,
        "member_expression": member_expression, "subscript_expression": member_expression,
        "call_expression": call, "non_null_expression": link, "new_expression": new_expression,
        "meta_property": meta_property, "update_expression": update, "unary_expression": unary,
        "await_expression": lambda self, ts: _Node("awaitexpression", argument=self.expression(self.named(ts)[0])),
        "binary_expression": binary, "assignment_expression": assignment, "augmented_assignment_expression": assignment,
        "ternary_expression": ternary, "yield_expression": yield_,
        "as_expression": typed("tsasexpression"), "satisfies_expression": typed("tssatisfiesexpression"),
        "type_assertion": type_assertion, "instantiation_expression": instantiation,
        "array_pattern": lambda self, ts: self.target(ts), "object_pattern": lambda self, ts: self.target(ts),
        "jsx_element": lambda self, ts: self.jsx_element(ts),
        "jsx_self_closing_element": lambda self, ts: self.jsx_element(ts),
    }

    # Types: `TypeScript Types` terms

    def annotation(self, ts: _TS) -> _Node:
        """A `type_annotation` (`: type`), or a return type: `: x is T`, `: asserts x`."""
        if ts.type in ("type_predicate_annotation", "asserts_annotation"):
            return _Node("tstypeannotation", typeAnnotation=self.predicate(self.named(ts)[0]))
        return _Node("tstypeannotation", typeAnnotation=self.type(self.named(ts)[0]))

    def predicate(self, ts: _TS) -> _Node:
        if ts.type == "asserts":
            inner = self.named(ts)[0]
            if inner.type == "type_predicate":
                made = self.predicate(inner)
                made.asserts = True
                return made
            return _Node("tstypepredicate", asserts=True, parameterName=self.predicate_name(inner))
        type_ = self.require(ts, "type")
        return _Node("tstypepredicate", parameterName=self.predicate_name(self.require(ts, "name")),
                     typeAnnotation=_Node("tstypeannotation", typeAnnotation=self.type(type_)))

    def predicate_name(self, ts: _TS) -> _Node:
        return _Node("tsthistype") if ts.type == "this" else self.identifier(ts)

    def type(self, ts: _TS) -> _Node:
        return self.term(ts, self.TYPES)

    def predefined(self, ts: _TS) -> _Node:
        text = " ".join(self.text(ts).split())
        if text == "unique symbol":
            return _Node("tstypeoperator", operator="unique", typeAnnotation=_Node("tssymbolkeyword"))
        return _Node(_KEYWORD_TYPES[text])

    def type_reference(self, ts: _TS) -> _Node:
        keyword = _KEYWORD_TYPES.get(self.text(ts))
        if keyword is not None and self.text(ts) != "intrinsic":  # tree-sitter-typescript reads `bigint` as a name
            return _Node(keyword)
        return self.import_or_reference(ts)

    def generic(self, ts: _TS) -> _Node:
        name, arguments = self.require(ts, "name"), self.require(ts, "type_arguments")
        return self.import_type(name, arguments) or _Node(
            "tstypereference", typeName=self.entity_name(name), typeArguments=self.type_arguments(arguments))

    def type_arguments(self, ts: _TS) -> _Node:
        return _Node("tstypeparameterinstantiation", params=[self.type(t) for t in self.named(ts)])

    def type_parameters(self, ts: _TS) -> _Node:
        return _Node("tstypeparameterdeclaration", params=[self.type_parameter(p) for p in self.named(ts)])

    def type_parameter(self, ts: _TS) -> _Node:
        name = self.require(ts, "name")
        variance = self.pre.variance.get(self.at(name), set())
        made = _Node("tstypeparameter", const=self.has(ts, "const"), isIn="in" in variance or self.has(ts, "in"),
                     isOut="out" in variance or any(c.type == "out" for c in ts.children), name=self.identifier(name))
        constraint = self.field(ts, "constraint")
        if constraint is not None:
            made.constraint = self.type(self.named(constraint)[0])
        default = self.field(ts, "value")
        if default is not None:
            made.default = self.type(self.named(default)[0])
        return made

    def flat(branch: str) -> Callable[[_Converter, _TS], Any]:  # type: ignore[misc]
        """A union or an intersection, whose nested ones of the same kind flatten."""
        def convert(self: _Converter, ts: _TS) -> Any:
            types: list[_Node] = []
            for t in self.named(ts):
                if t.type == ts.type:
                    types += convert(self, t).types
                    continue
                converted = self.type(t)
                if t.type == "readonly_type" and converted.branch == branch:  # its own operand was a union
                    types += converted.types
                else:
                    types.append(converted)
            return _Node(branch, types=types)
        return convert

    def literal_type(self, ts: _TS) -> _Node:
        inner = self.named(ts)[0]
        if inner.type == "unary_expression":
            return _Node("tsliteraltype", literal=self.expression(inner))
        if inner.type == "null":
            return _Node("tsnullkeyword")
        if inner.type == "undefined":
            return _Node("tsundefinedkeyword")
        return _Node("tsliteraltype", literal=self.literal(inner))

    def function_type(self, ts: _TS) -> _Node:
        made = _Node("tsfunctiontype")
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        returns = self.require(ts, "return_type")
        made.returnType = _Node("tstypeannotation", typeAnnotation=self.predicate(returns) if returns.type in (
            "type_predicate", "asserts") else self.type(returns))
        return made

    def constructor_type(self, ts: _TS) -> _Node:
        made = _Node("tsconstructortype", abstract=self.has(ts, "abstract"))
        parameters = self.field(ts, "type_parameters")
        if parameters is not None:
            made.typeParameters = self.type_parameters(parameters)
        made.params = self.parameters(self.require(ts, "parameters"))
        made.returnType = _Node("tstypeannotation", typeAnnotation=self.type(self.require(ts, "type")))
        return made

    def tuple_type(self, ts: _TS) -> _Node:
        out: list[_Node] = []
        for element in self.named(ts):
            if element.type in ("required_parameter", "optional_parameter"):
                name = self.require(element, "name")
                annotation = self.named(self.require(element, "type"))[0]
                if name.type == "rest_pattern":
                    member = _Node("tsnamedtuplemember", label=self.identifier(self.named(name)[0]),
                                   elementType=self.type(annotation))
                    out.append(_Node("tsresttype", typeAnnotation=member))
                    continue
                out.append(_Node("tsnamedtuplemember", label=self.identifier(name),
                                 optional=element.type == "optional_parameter", elementType=self.type(annotation)))
            else:
                out.append(self.type(element))
        return _Node("tstupletype", elementTypes=out)

    def object_type(self, ts: _TS) -> _Node:
        members = self.named(ts)
        if len(members) == 1 and members[0].type == "index_signature" and any(
                c.type == "mapped_type_clause" for c in self.named(members[0])):
            return self.mapped(members[0])
        return _Node("tstypeliteral", members=self.unlined(self.listed(ts.children, self.type_member,
                                                                       ts.children[0])))

    def mapped(self, ts: _TS) -> _Node:
        """A mapped type: its constraint its `value` and its type its `body`, as `TypeScript Types` has them."""
        clause = next(c for c in self.named(ts) if c.type == "mapped_type_clause")
        made = _Node("tsmappedtype", key=self.identifier(self.require(clause, "name")),
                     value=self.type(self.require(clause, "type")))
        alias = self.field(clause, "alias")
        if alias is not None:
            made.nameType = self.type(alias)
        sign = self.field(ts, "sign")
        if any(c.type == "readonly" for c in self.kids(ts)):
            made.readonly = (self.text(sign) if sign is not None and sign.start_byte < clause.start_byte else "") + (
                "readonly")
        annotation = self.require(ts, "type")
        made.optional = {"adding_type_annotation": "+?", "omitting_type_annotation": "-?",
                         "opting_type_annotation": "?"}.get(annotation.type)
        made.body = self.type(self.named(annotation)[0])  # tree-sitter-typescript reads none without one
        return made

    def type_member(self, ts: _TS) -> _Node:
        if ts.type == "property_signature":
            modifiers = self.tokens_before(ts, "name")
            key, computed = self.key(self.require(ts, "name"))
            made = _Node("tspropertysignature", readonly="readonly" in modifiers, static="static" in modifiers, key=key,
                         computed=computed, optional=self.has(ts, "?"))
            annotation = self.field(ts, "type")
            if annotation is not None:
                made.typeAnnotation = self.annotation(annotation)
            return made
        if ts.type == "method_signature":
            modifiers = self.tokens_before(ts, "name")
            key, computed = self.key(self.require(ts, "name"))
            made = _Node("tsmethodsignature",
                         methodKind="get" if "get" in modifiers else "set" if "set" in modifiers else "method",
                         key=key, computed=computed, optional=self.has(ts, "?"))
            self.signature(ts, made)
            return made
        if ts.type in ("call_signature", "construct_signature"):
            made = _Node("tscallsignaturedeclaration" if ts.type == "call_signature" else
                         "tsconstructsignaturedeclaration")
            self.signature(ts, made)
            return made
        return self.index_signature(ts)

    def type_query(self, ts: _TS) -> _Node:
        inner = self.named(ts)[0]
        if inner.type == "instantiation_expression":
            name = self.named(inner)[0]
            return _Node("tstypequery", exprName=self.import_type(name) or self.entity_name(name),
                         typeArguments=self.type_arguments(self.require(inner, "type_arguments")))
        return _Node("tstypequery", exprName=self.import_type(inner) or self.entity_name(inner))

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

    def import_type(self, ts: _TS, arguments: _TS | None = None) -> _Node | None:
        """`import('m').a.b<arguments>` as a type; None if `ts` is not rooted at an import."""
        root = self.import_root(ts)
        if root is None:
            return None
        call, names = root
        made = _Node("tsimporttype", **self.import_call(call))
        qualifier: _Node | None = None
        for name in names:
            right = self.identifier(name)
            qualifier = right if qualifier is None else _Node("tsqualifiedname", left=qualifier, right=right)
        made.qualifier = qualifier
        if arguments is not None:
            made.typeArguments = self.type_arguments(arguments)
        return made

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
        call = converter.named(converter.named(tree.root_node)[0])[0]
        return converter.import_call(call)

    def import_or_reference(self, ts: _TS) -> _Node:
        """A type that is `import('m').a.b`, or a type reference."""
        return self.import_type(ts) or _Node("tstypereference", typeName=self.entity_name(ts))

    def template_type(self, ts: _TS) -> _Node:
        quasis, types = self.template_parts(ts, "template_type", self.type)
        return _Node("tstemplateliteraltype", quasis=quasis, types=types)

    def infer(self, ts: _TS) -> _Node:
        kids = self.named(ts)
        parameter = _Node("tstypeparameter", name=self.identifier(kids[0]))
        if len(kids) > 1:
            parameter.constraint = self.type(kids[1])
        return _Node("tsinfertype", typeParameter=parameter)

    def lookup(self, ts: _TS) -> _Node:
        object_type, index_type = self.named(ts)
        return _Node("tsindexedaccesstype", objectType=self.type(object_type), indexType=self.type(index_type))

    def readonly(self, ts: _TS) -> _Node:
        """`readonly T`, which binds tighter than `|` and `&`: tree-sitter-typescript reads `readonly A[] | B` as
        `readonly (A[] | B)`."""
        inner = self.named(ts)[0]
        if inner.type in ("union_type", "intersection_type"):
            return self.readonly_first(inner)
        return _Node("tstypeoperator", operator="readonly", typeAnnotation=self.type(inner))

    def readonly_first(self, ts: _TS) -> _Node:
        """The union or intersection `ts`, with its first member made readonly."""
        members = self.named(ts)
        branch = "tsuniontype" if ts.type == "union_type" else "tsintersectiontype"
        if members[0].type == ts.type:
            types = self.readonly_first(members[0]).types
        else:
            types = [_Node("tstypeoperator", operator="readonly", typeAnnotation=self.type(members[0]))]
        types += [self.type(m) for m in members[1:]]  # a union groups to the left: only its first may be one
        return _Node(branch, types=types)

    TYPES: dict[str, Callable[[_Converter, _TS], Any]] = {
        "predefined_type": predefined, "type_identifier": type_reference, "identifier": type_reference,
        "nested_type_identifier": lambda self, ts: self.import_or_reference(ts), "generic_type": generic,
        "member_expression": lambda self, ts: self.import_or_reference(ts),
        "this_type": lambda self, ts: _Node("tsthistype"),
        "parenthesized_type": lambda self, ts: _Node("tsparenthesizedtype", typeAnnotation=self.type(
            self.named(ts)[0])),
        "literal_type": literal_type,
        "array_type": lambda self, ts: _Node("tsarraytype", elementType=self.type(self.named(ts)[0])),
        "tuple_type": tuple_type, "union_type": flat("tsuniontype"), "intersection_type": flat("tsintersectiontype"),
        "function_type": function_type, "constructor_type": constructor_type, "object_type": object_type,
        "index_type_query": lambda self, ts: _Node("tstypeoperator", operator="keyof", typeAnnotation=self.type(
            self.named(ts)[0])),
        "readonly_type": lambda self, ts: self.readonly(ts),
        "lookup_type": lookup, "type_query": type_query, "template_literal_type": template_type,
        "conditional_type": lambda self, ts: _Node(
            "tsconditionaltype", checkType=self.type(self.require(ts, "left")),
            extendsType=self.type(self.require(ts, "right")), trueType=self.type(self.require(ts, "consequence")),
            falseType=self.type(self.require(ts, "alternative"))),
        "infer_type": infer,
        "optional_type": lambda self, ts: _Node("tsoptionaltype", typeAnnotation=self.type(self.named(ts)[0])),
        "rest_type": lambda self, ts: _Node("tsresttype", typeAnnotation=self.type(self.named(ts)[0])),
        "type_predicate": lambda self, ts: self.predicate(ts), "asserts": lambda self, ts: self.predicate(ts),
        "call_expression": lambda self, ts: self.import_or_reference(ts),
        "const": lambda self, ts: _Node("tstypereference", typeName=_Node("identifier", name="const")),
        "template_type": lambda self, ts: self.type(self.named(ts)[0]),
    }

    # JSX: `TypeScript5`'s JSX kinds and their helpers

    def jsx_element(self, ts: _TS) -> _Node:
        if ts.type == "jsx_self_closing_element":
            opening = _Node("jsxopeningelement", selfClosing=True)
            self.jsx_tag(ts, opening)
            return _Node("jsxelement", openingElement=opening)
        open_tag = self.require(ts, "open_tag")
        close_tag = self.require(ts, "close_tag")
        children = self.jsx_children(open_tag, close_tag, [c for c in self.named(ts) if c.id not in (
            open_tag.id, close_tag.id) and c.type not in ("jsx_text", "html_character_reference")])
        if self.field(open_tag, "name") is None:
            return _Node("jsxfragment", openingFragment=_Node("jsxopeningfragment"), children=children,
                         closingFragment=_Node("jsxclosingfragment"))
        opening = _Node("jsxopeningelement")
        self.jsx_tag(open_tag, opening)
        closing = _Node("jsxclosingelement", name=self.jsx_name(self.require(close_tag, "name")))
        return _Node("jsxelement", openingElement=opening, children=children, closingElement=closing)

    def jsx_tag(self, ts: _TS, made: _Node) -> None:
        made.name = self.jsx_name(self.require(ts, "name"))
        arguments = self.field(ts, "type_arguments")
        if arguments is not None:
            made.typeArguments = self.type_arguments(arguments)
        made.attributes = []
        for attribute in self.fields(ts, "attribute"):
            if attribute.type == "jsx_expression":
                made.attributes.append(_Node("jsxspreadattribute",
                                             argument=self.expression(self.named(self.named(attribute)[0])[0])))
                continue
            name, *value = self.named(attribute)
            converted = _Node("jsxattribute", name=self.jsx_name(name))
            if value:
                inner = value[0]
                converted.value = self.jsx_string(inner) if inner.type == "string" else self.jsx_child(inner)
            made.attributes.append(converted)

    def jsx_string(self, ts: _TS) -> _Node:
        """An attribute's string, whose value is its text between its quotes: JSX does not unescape it."""
        text = self.text(ts)
        return _Node("literal", value=_scalar(text[1:-1]), text=text, quote=text[0])

    def jsx_name(self, ts: _TS) -> _Node:
        if ts.type == "member_expression":
            return _Node("jsxmemberexpression", object=self.jsx_name(self.require(ts, "object")),
                         property=self.jsx_name(self.require(ts, "property")))
        if ts.type == "jsx_namespace_name":
            namespace, name = self.named(ts)
            return _Node("jsxnamespacedname", namespace=self.jsx_name(namespace), name=self.jsx_name(name))
        return _Node("jsxidentifier", name=self.text(ts))

    def jsx_children(self, open_tag: _TS, close_tag: _TS, nodes: list[_TS]) -> list[_Node]:
        """An element's children: its elements and expressions, and the text between them, as written. Text is
        whatever lies between the others: tree-sitter-typescript leaves out the text that is only whitespace, and
        splits the rest at character references (`&amp;`)."""
        out: list[_Node] = []
        at = open_tag.end_byte
        for ts in nodes + [close_tag]:
            if ts.start_byte > at:
                out.append(_Node("jsxtext", raw=self.between(at, ts.start_byte)))
            if ts is not close_tag:
                out.append(self.jsx_child(ts))
            at = ts.end_byte
        return out

    def jsx_child(self, ts: _TS) -> _Node:
        """An element's child or an attribute's value, but text, which `jsx_children` reads."""
        if ts.type == "jsx_expression":
            inner = self.named(ts)
            if not inner:
                return _Node("jsxexpressioncontainer", expression=_Node("jsxemptyexpression"))
            if inner[0].type == "spread_element":
                return _Node("jsxspreadchild", expression=self.expression(self.named(inner[0])[0]))
            return _Node("jsxexpressioncontainer", expression=self.expression(inner[0]))
        return self.expression(ts)


# --- The transaction ---


def parse(text: str, path: str, store: Any = None) -> Callable[[Any], Any]:
    """The callback of the transaction that writes `text`, TypeScript 5 source, as the program at `path` in the
    workspace, read with the `tsx` grammar where `path` ends `.tsx`: given to `store.transaction`, or, with `store`, to
    `store.Mutations.OfTransaction`. Raises `ParseError` only for text that is no text, a lone surrogate (which no
    encoding writes), now, before any transaction: invalid syntax is kept (`Programs.TypeScript5.Error`, the dialects'
    `error` and `missing`)."""
    try:
        source = _Source(text)
    except UnicodeEncodeError as error:  # a lone surrogate
        at = error.start
        line, column = text.count("\n", 0, at) + 1, at - (text.rfind("\n", 0, at) + 1) + 1
        raise ParseError("not text: a lone surrogate", line, column) from None
    parser = _PARSERS[path.endswith(".tsx")]
    tree = parser.parse(source.data, encoding="utf16le")
    prepared = _Prepared()
    if tree.root_node.has_error:
        cleaned, prepared = _prepare(text, tree.root_node, source)
        source = _Source(text, cleaned)
        tree = parser.parse(source.data, encoding="utf16le")
    hashbang, statements = _Converter(source, prepared).program(tree.root_node)
    body = _write(statements)

    def transaction(txn: Any) -> Any:
        symbols = {"ws": store.registered("Programs.Framework.Workspace") if store is not None else
                   txn.Programs.Framework.Workspace,
                   "program": store.registered(f"{_LANGUAGE}.Program") if store is not None else
                   txn.Programs.TypeScript5.Program}
        return txn.uid(path).mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
            .symbols(symbols)
            .spec([
                lambda _: _.ws.files({path: lambda e: e.file(_.program)}),
                lambda _: _.program.body(body).hashbang(hashbang) if hashbang is not None else _.program.body(body),
            ])]))])

    return transaction
