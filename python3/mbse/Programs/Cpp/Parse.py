"""Parse: C++ source text as the transaction that writes its translation unit, delegating to tree-sitter-cpp.

DOCSTRING
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

import tree_sitter_cpp
from mbse.Expressions.Cpp.Expressions.Expressions import SUFFIXES
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..C import Parse as C
from ..C.Parse import _Branch, _Invalid, _Node, _Source, _scalar, _unescape
from ..Framework.Errors import ParseError
from ..Framework.Model import WORKSPACE

__all__ = ["parse", "ParseError", "WORKSPACE"]

_PARSER = _TSParser(_Grammar(tree_sitter_cpp.language()))

_LANGUAGE = "Programs.Cpp"

_ALTERNATIVES = {"and": "&&", "or": "||", "not": "!", "compl": "~", "bitand": "&", "bitor": "|", "xor": "^",
                 "and_eq": "&=", "or_eq": "|=", "xor_eq": "^=", "not_eq": "!="}
"""C++'s alternative tokens, normalized to the tokens they spell, as 0.3 normalized them."""
_PRIMITIVES = {"void", "char", "char8_t", "char16_t", "char32_t", "wchar_t", "bool", "short", "int", "long", "signed",
               "unsigned", "float", "double", "__int128", "__float128", "_Float16", "_Float32", "_Float64",
               "_Float128"}
_CV = {"const", "volatile", "__restrict", "__restrict__", "restrict", "_Atomic"}
_CASTS = {"static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"}
_NAMES = {"identifier", "field_identifier", "type_identifier", "namespace_identifier", "statement_identifier"}
_ATTRIBUTES = {"attribute_declaration", "attribute_specifier", "ms_declspec_modifier", "alignas_qualifier"}
_DIALECTS = {"c": "cpp", "c_types": "cpp_types"}
_ACCESS = ("public", "protected", "private")


# --- The pre-pass: what tree-sitter-cpp cannot parse, or misreads ---


class _Prepared(C._Prepared):
    """What the pre-pass rewrote, by character offset: C's (`Programs.C.Parse._Prepared`: the keywords it respelled, the
    attributes it blanked, the items it blanked where they are listed and the `_Pragma`s among them), and C++'s: the
    module declarations it blanked, each made already, the declarations and blocks `export` introduced, the `extern` of
    an `extern template`, the explicit object parameters (`this`), a using-declaration's further declarators, a
    bit-field's initializer, an attribute specifier's `using` namespace, and the `;` it wrote after a label ending a
    block."""

    def __init__(self) -> None:
        super().__init__()
        self.modules: dict[int, _Node] = {}  # by its offset: the module or import declaration
        self.exported: set[int] = set()  # the offset of a declaration `export` introduced
        self.export_blocks: set[int] = set()  # the offset of a block `export` introduced
        self.extern: set[int] = set()  # the offset of the `template` of an `extern template`
        self.this: set[int] = set()  # the offset of a parameter's first specifier, after its `this`
        self.usings: dict[int, list[tuple[int, int]]] = {}  # by the `using`: the span of each further declarator
        self.bitfields: dict[int, tuple[int, int]] = {}  # by where a bit-field's width ends: its initializer's span
        self.namespaces: dict[int, str] = {}  # by the `[[`: its `using` namespace
        self.empties: set[int] = set()  # the offset of a `;` written after a label ending a block


def _masked(text: str) -> str:
    """`text` with each raw string's characters between its quotes blanked, so that `Programs.C.Parse._lex` reads it as
    one string literal."""
    out = list(text)
    for match in re.finditer(r'(?:u8|[uUL])?R"([^ ()\\\t\v\f\n]{0,16})\(', text):
        end = text.find(")" + match.group(1) + '"', match.end())
        stop = len(text) if end < 0 else end + len(match.group(1)) + 1
        for p in range(match.end() - len(match.group(1)) - 1, stop):
            out[p] = "\n" if text[p] == "\n" else "x"
    return "".join(out)


def _module(words: list[str], written: str, keyword: str, exported: bool) -> _Node:
    """The module or import declaration whose words after its keyword, before its `;`, are `words`, `written` as they
    are; `_Invalid` for one that names no module."""
    def dotted(parts: list[str]) -> str:
        if len(parts) % 2 == 0 or any(parts[i] != "." for i in range(1, len(parts), 2)) or not all(
                C._WORD.fullmatch(parts[i]) for i in range(0, len(parts), 2)):
            raise _Invalid(keyword)
        return "".join(parts)

    def named(parts: list[str]) -> tuple[str | None, str | None]:
        """`name`, `name:partition` or `:partition`."""
        at = parts.index(":") if ":" in parts else len(parts)
        return dotted(parts[:at]) if at > 0 else None, dotted(parts[at + 1:]) if at < len(parts) else None

    if keyword == "module":
        if not words and not exported:
            return _Node("globalmodulefragment")
        if words == [":", "private"] and not exported:
            return _Node("privatemodulefragment")
        name, partition = named(words)
        if name is None:
            raise _Invalid(keyword)
        return _Node("moduledeclaration", export=exported, name=name, partition=partition)
    if keyword == "import" and words and (words[0] == "<" and words[-1] == ">" or len(words) == 1 and words[0][:1] == '"'):
        return _Node("importdeclaration", export=exported, header=written[1:-1], system=words[0] == "<")
    name, partition = named(words)
    if name is None and partition is None:
        raise _Invalid(keyword)
    return _Node("importdeclaration", export=exported, name=name, partition=partition)


def _depth(tokens: list[tuple[int, int, str]], start: int, at: int) -> int:
    """How deep `tokens[at]` is within the brackets and angle brackets opened from `tokens[start]` on."""
    depth = 0
    for _, _, w in tokens[start:at]:
        depth += 1 if w in ("(", "[", "{", "<") else -1 if w in (")", "]", "}", ">") else 2 * -(w == ">>")
    return depth


def _heads(tokens: list[tuple[int, int, str]], at: int) -> set[str]:
    """The words of the member or the statement `tokens[at]` is within, before it."""
    start = at
    while start > 0 and tokens[start - 1][2] not in (";", "{", "}"):
        start -= 1
    return {w for _, _, w in tokens[start:at]}


def _prepare(text: str, root: _TS, source: _Source) -> tuple[str, _Prepared]:
    """The text with the constructs tree-sitter-cpp cannot parse, or misreads, rewritten, and what was rewritten: what
    it misreads wherever it stands, what it cannot parse only where tree-sitter found an error."""
    found = _Prepared()
    chars = list(text)
    broken = root.has_error
    tokens, directives = C._lex(_masked(text))
    tokens = [(start, end, text[start:end]) for start, end, _ in tokens]

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            chars[p] = "\n" if text[p] == "\n" else " "

    def word(k: int) -> str:
        return tokens[k][2] if 0 <= k < len(tokens) else ""

    for start, end in directives:
        line = text[start:end]
        if broken and C._directive_name(line) == "" and not line.lstrip("#%: \t").startswith(("/", "\\")):
            blank(start, start + (1 if line[0] == "#" else 2))  # the null directive, `#` alone
            found.items.append((start, start, start))
        elif broken and line.startswith("%:"):
            chars[start:start + 2] = list("# ")
    braces = C._braces(tokens)
    pragmas: set[int] = set()  # the index of a `_Pragma`'s `)`, blanked
    statement = True  # whether a declaration may begin at the token
    i = 0
    while i < len(tokens):
        start, end, w = tokens[i]
        before, after = word(i - 1), word(i + 1)
        begins, statement = statement or i - 1 in pragmas, w in (";", "{", "}")
        i += 1
        # What tree-sitter-cpp misreads, or cannot parse, wherever it stands: C++20's modules, `export`, `extern
        # template`, `if consteval`
        if begins and braces[i - 1] == "" and w in ("export", "module", "import"):
            exported = w == "export"
            k = i if exported else i - 1
            if word(k) in ("module", "import") and word(k + 1) not in ("=", "(", "::", ".", "->", "[", ";") or (
                    word(k) == "module" and word(k + 1) == ";"):
                stop = next((j for j in range(k + 1, len(tokens)) if tokens[j][2] == ";"), None)
                if stop is None:  # unclosed: tree-sitter's recovery keeps it
                    continue
                try:
                    found.modules[start] = _module([t[2] for t in tokens[k + 1:stop]], text[
                        tokens[k + 1][0]:tokens[stop - 1][1]] if stop > k + 1 else "", word(k), exported)
                except _Invalid:
                    found.modules[start] = _Node("error", text=text[start:tokens[stop][1]])
                found.items.append((start, start, start))
                blank(start, tokens[stop][1])
                i, statement = stop + 1, True
                continue
            if exported and after:
                blank(start, end)
                (found.export_blocks if after == "{" else found.exported).add(tokens[i][0])
                statement = True
                continue
        if w == "extern" and after == "template" and word(i + 1) != "<":
            blank(start, end)
            found.extern.add(tokens[i][0])
            continue
        if w == "if" and (after == "consteval" or after == "!" and word(i + 1) == "consteval"):
            last = i + (1 if after == "consteval" else 2)
            chars[tokens[i][0]:tokens[last - 1][1]] = list("(1)".ljust(tokens[last - 1][1] - tokens[i][0]))
            found.keywords[tokens[i][0]] = "consteval" if after == "consteval" else "!consteval"
            i = last
            continue
        if not broken:
            continue
        # What tree-sitter-cpp cannot parse
        if w in C._DIGRAPHS:
            chars[start:end] = list(C._DIGRAPHS[w])
        elif w == "this" and before in ("(", ",") and (C._WORD.fullmatch(after) or after == "::") and (
                after not in ("this",)):
            blank(start, end)  # an explicit object parameter (C++23), `this S &self`
            found.this.add(tokens[i][0])
        elif w == "using" and after not in ("namespace", "enum") and begins:
            stop = next((j for j in range(i, len(tokens)) if tokens[j][2] in (";", "=", "{", "}")), len(tokens))
            commas = [j for j in range(i, stop) if tokens[j][2] == "," and _depth(tokens, i, j) == 0]
            if stop < len(tokens) and tokens[stop][2] == ";" and commas:
                found.usings[start] = [(tokens[a + 1][0], tokens[b - 1][1]) for a, b in zip(commas, commas[1:] + [
                    stop])]
                blank(tokens[commas[0]][0], tokens[stop - 1][1])
                i = stop
        elif w == ":" and braces[i - 1] == "struct" and C._WORD.fullmatch(before) and before not in _ACCESS and not (
                _heads(tokens, i - 1) & {"case", "?", "enum", "class", "struct", "union", "try"}):
            depth, j = 0, i  # a bit-field's width, and the initializer after it (C++20)
            while j < len(tokens) and not (depth == 0 and tokens[j][2] in (";", ",", "=", "{")):
                depth += 1 if tokens[j][2] in ("(", "[") else -1 if tokens[j][2] in (")", "]") else 0
                j += 1
            if j < len(tokens) and tokens[j][2] in ("=", "{") and j > i:
                stop = next((k for k in range(j, len(tokens)) if tokens[k][2] in (";", ",") and _depth(
                    tokens, j, k) == 0), len(tokens))
                if stop < len(tokens):
                    found.bitfields[tokens[j - 1][1]] = (tokens[j][0], tokens[stop - 1][1])
                    blank(tokens[j][0], tokens[stop - 1][1])
                    i = stop
        elif w == "[" and after == "[" and word(i + 1) == "using" and word(i + 3) == ":":
            found.namespaces[start] = word(i + 2)  # `[[using gnu: hot]]` (C++17)
            blank(tokens[i + 1][0], tokens[i + 3][1])
            i += 4
        elif braces[i - 1] == "enum" and before in ("{", ",", "<%") and after == "[" and word(i + 1) == "[":
            close = C._closing(tokens, i)
            if close is None:  # unclosed: nothing to read back
                continue
            found.attributes.setdefault(start, []).append((tokens[i][0], tokens[close][1]))
            blank(tokens[i][0], tokens[close][1])
        elif w == ":" and after == "}" and braces[i - 1] == "block" and tokens[i][0] > end:
            chars[end] = ";"  # a label ending a block (C++23), `l: }`, with a blank after its `:`
            found.empties.add(end)
        elif w == "_Pragma" and after == "(" and braces[i - 1] != "init" and (
                before in ("", ";", "{", "}", "<%", "%>") or before == "," and braces[i - 1] == "enum" or (
                i - 2 in pragmas)):
            close = C._closing(tokens, i)  # where an item stands, without `;`
            if close is None or word(close + 1) == ";":
                continue
            pragmas.add(close)
            found.items.append((start, start, start))
            found.pragmas[start] = (tokens[i][1], tokens[close][0])
            blank(start, tokens[close][1])
    return "".join(chars), found


# --- Literals ---


_INTEGER = re.compile(r"(0[xX](?:'?[0-9a-fA-F])+|0[bB](?:'?[01])+|0(?:'?[0-7])*|[1-9](?:'?[0-9])*)([A-Za-z_]\w*)?")


def _number(text: str) -> _Node:
    """A number's literal: its value, an int or a float, its spelling, and what the spelling encodes. `_Invalid` for one
    C++ rejects: an octal one with a digit 8 or 9, or a suffix C++ has not."""
    integer = _INTEGER.fullmatch(text)
    floating = C._FLOATING.fullmatch(text)
    if integer is not None and (floating is None or not integer.group(2) or SUFFIXES[int].fullmatch(integer.group(2))):
        digits, suffix = integer.group(1).replace("'", ""), integer.group(2) or ""
        if not SUFFIXES[int].fullmatch(suffix):
            raise _Invalid(text)
        base = {"0x": 16, "0X": 16, "0b": 2, "0B": 2}.get(digits[:2], 8 if digits.startswith("0") else 10)
        value = int(digits[2:] if base in (2, 16) else digits, base)
        return _Node("literal", value=_scalar(value), text=text, base=base, separators="'" in text,
                     suffix=suffix or None)
    if floating is None or floating.group(2) and not SUFFIXES[float].fullmatch(floating.group(2)):
        raise _Invalid(text)
    digits = floating.group(1).replace("'", "")
    try:
        value = float.fromhex(digits) if digits[:2] in ("0x", "0X") else float(digits)
    except OverflowError:  # beyond the largest: read as infinity
        value = math.inf
    return _Node("literal", value=_scalar(value), text=text, separators="'" in text, suffix=floating.group(2) or None)


def _cpp(value: Any) -> Any:
    """`value`, each of its nodes of C's dialects made C++'s (`cpp`, `cpp_types`): the branch it takes where the
    framework's union of dialects holds it (a directive's condition, a term recovered within invalid syntax)."""
    if isinstance(value, list):
        return [_cpp(v) for v in value]
    if isinstance(value, _Branch):
        return _Branch(value.tag, _cpp(value.node))
    if isinstance(value, _Node):
        object.__setattr__(value, "dialect", _DIALECTS.get(value.dialect, value.dialect))
        for v in value.fields.values():
            _cpp(v)
    return value


# --- The converter ---


class _Converter(C._Converter):
    """Rewrites a tree-sitter-cpp tree into statements and terms: C's converter (`Programs.C.Parse._Converter`), where
    tree-sitter-cpp writes the node types tree-sitter-c writes, and C++'s own."""

    SPECIFIER_NODES = ("struct_specifier", "union_specifier", "enum_specifier", "class_specifier")
    GROUPS = ("cpp_group", "cpp_membergroup")

    def reparsed(self, prefix: str, start: int, end: int, suffix: str) -> tuple[_Converter, _TS]:
        source, prepared, tree = _parsed(prefix + self.source.text[start:end] + suffix)
        return _Converter(source, prepared, self.shift + start - len(prefix), self.origin), tree.root_node

    def blanked(self, start: int, end: int) -> list[_Node]:
        """The items the pre-pass blanked from `start` and before `end`: C's, and C++20's module declarations."""
        out = []
        for at, first, last in sorted(self.pre.items):
            if start <= at < end and at in self.pre.modules:
                made = self.pre.modules[at]
                made.line = self.origin.line(self.shift + at)
                out.append(made)
            elif start <= at < end:
                out += super().blanked(at, at + 1)
        return out

    def part_type(self, start: int, end: int) -> _Node:
        """The type-id the text between `start` and `end` writes, read again."""
        converter, root = self.reparsed("using _ = ", start, end, ";")
        if root.has_error:
            raise _Invalid(self.source.text[start:end])
        return converter.type_id(converter.require(converter.named(root)[0], "type"))

    # Lists of statements

    def unit(self, ts: _TS) -> list[_Node]:
        return self.listed(ts.children, self.external)

    def external(self, ts: _TS) -> _Node:
        """A declaration where a translation unit, a namespace's body, a linkage specification's or an `export`
        lists them; a statement other than a declaration is invalid syntax there, and `;` alone an empty
        declaration."""
        if ts.type == "expression_statement" and not self.named(ts) and not ts.has_error:
            return self.new(ts, "emptydeclaration")
        if ts.type == "attributed_statement" and not self.named(self.named(ts)[-1]):
            return self.statement(ts)  # an attribute declaration
        if ts.type in self.STATEMENTS and ts.type not in ("expression_statement", "compound_statement") or (
                ts.type == "expression_statement" and not self.asm_statement(ts)) or (
                ts.type == "compound_statement" and self.local(ts) not in self.pre.export_blocks):
            return self.error(ts)
        return self.statement(ts)

    def convert(self, ts: _TS) -> _Node:
        """The statement or declaration `ts`, with its line; `export`ed where `export` introduced it."""
        at = self.local(ts)
        if ts.type == "compound_statement" and at in self.pre.export_blocks:
            return self.new(ts, "exportdeclaration", braced=True, body=self.listed(
                ts.children, self.external, ts.children[0]))
        made = super().convert(ts)
        if at in self.pre.exported:
            return self.new(ts, "exportdeclaration", body=[made])
        return made

    def listed(self, nodes: list[_TS], convert: Callable[[_TS], Any], header: _TS | None = None) -> list[Any]:
        """C's lists, but for the `;` the pre-pass wrote after a label ending a block, which is no statement."""
        kept = [n for n in nodes if not (n.type == "expression_statement" and not self.named(n) and self.source.offset(
            n.start_byte) in self.pre.empties)]
        return super().listed(kept, convert, header)

    def expression_statement(self, ts: _TS) -> _Node:
        inner = self.named(ts)
        if inner and inner[0].type == "gnu_asm_expression":
            return self.asm(inner[0])
        if not inner:
            return _Node("expressionstatement")
        return _Node("expressionstatement", expression=self.expression(inner[0]))

    def asserting(self, ts: _TS) -> bool:
        return False  # tree-sitter-cpp reads `static_assert` as a declaration

    def labeled(self, ts: _TS) -> _Node:
        label = self.require(ts, "label")
        made = _Node("labeledstatement", label=self.identifier(label))
        body = [c for c in self.named(ts) if c.id != label.id]
        if body and not (body[0].type == "expression_statement" and not self.named(body[0]) and self.local(
                body[0]) in self.pre.empties):
            made.statement = self.statement(body[0])
        return made

    def attributed(self, ts: _TS) -> _Node:
        parts = self.named(ts)
        if parts[-1].type == "expression_statement" and not self.named(parts[-1]):
            return _Node("attributedeclaration", attributes=[self.attribute(a) for a in parts[:-1]])
        return _Node("attributedstatement", attributes=[self.attribute(a) for a in parts[:-1]],
                     statement=self.statement(parts[-1]))

    # Statements C++ restates or adds

    def init_statement(self, ts: _TS) -> Any:
        """An init-statement: a declaration, or a term."""
        if ts.type == "declaration":
            return self.declaration(ts)
        if ts.type == "alias_declaration":
            return self.alias(ts)
        if ts.type == "expression_statement":
            return _Branch("expression", self.expression(self.named(ts)[0]))
        return _Branch("expression", self.expression(ts))

    def conditioned(self, ts: _TS, made: _Node) -> _Node:
        """`made`, given its initializer and its condition from a condition_clause."""
        initializer = self.field(ts, "initializer")
        if initializer is not None:
            made.initializer = self.init_statement(self.named(initializer)[0] if initializer.type == "init_statement"
                                                   else initializer)
        value = self.require(ts, "value")
        made.condition = self.declaration(value) if value.type == "declaration" else _Branch(
            "expression", self.expression(value))
        return made

    def if_statement(self, ts: _TS) -> _Node:
        made = _Node("ifstatement", constexpr=self.has(ts, "constexpr"),
                     consequence=self.statement(self.require(ts, "consequence")))
        condition = self.require(ts, "condition")
        keyword = self.pre.keywords.get(self.local(condition))
        if keyword is not None:  # `if consteval`, `if !consteval`, which the pre-pass made `if (1)`
            made.consteval, made.negated = True, keyword.startswith("!")
        else:
            self.conditioned(condition, made)
        alternative = self.field(ts, "alternative")
        if alternative is not None:
            made.alternative = self.statement(self.named(alternative)[0])
        return made

    def switch_statement(self, ts: _TS) -> _Node:
        return self.conditioned(self.require(ts, "condition"), _Node(
            "switchstatement", body=self.statement(self.require(ts, "body"))))

    def while_statement(self, ts: _TS) -> _Node:
        return self.conditioned(self.require(ts, "condition"), _Node(
            "whilestatement", body=self.statement(self.require(ts, "body"))))

    def do_statement(self, ts: _TS) -> _Node:
        return _Node("dostatement", body=self.statement(self.require(ts, "body")),
                     condition=self.condition(self.require(ts, "condition")))

    def for_statement(self, ts: _TS) -> _Node:
        made = _Node("forstatement", body=self.statement(self.require(ts, "body")))
        initializer, condition, update = (self.field(ts, n) for n in ("initializer", "condition", "update"))
        if initializer is not None:
            made.initializer = self.init_statement(initializer)
        if condition is not None:
            made.condition = self.declaration(condition) if condition.type == "declaration" else _Branch(
                "expression", self.expression(condition))
        if update is not None:
            made.increment = self.expression(update)
        return made

    def range_for(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        declaration = _Node("simpledeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                            declarators=[_Node("initdeclarator", declarator=self.declarator(
                                self.require(ts, "declarator")))])
        made = _Node("rangeforstatement", declaration=declaration, body=self.statement(self.require(ts, "body")))
        right = self.require(ts, "right")
        made.range = self.expression(right)
        initializer = self.field(ts, "initializer")
        if initializer is not None:
            made.initializer = self.init_statement(self.named(initializer)[0] if initializer.type == "init_statement"
                                                   else initializer)
        return made

    def co_return(self, ts: _TS) -> _Node:
        value = self.named(ts)
        return _Node("coreturnstatement", value=self.expression(value[0]) if value else None)

    def co_yield(self, ts: _TS) -> _Node:
        return _Node("expressionstatement", expression=_Node("yieldexpression", operand=self.expression(
            self.named(ts)[0])))

    def throw(self, ts: _TS) -> _Node:
        value = self.named(ts)
        return _Node("expressionstatement", expression=_Node("throwexpression", operand=self.expression(value[0])
                                                             if value else None))

    def try_statement(self, ts: _TS) -> _Node:
        made = _Node("trystatement", body=self.block(self.require(ts, "body")), handlers=[])
        for c in self.named(ts):
            if c.type == "catch_clause":
                parameters = self.parameters(self.require(c, "parameters"))
                if len(parameters) != 1:
                    raise _Invalid(c.type)
                made.handlers.append(self.new(c, "handler", parameter=parameters[0],
                                              body=self.block(self.require(c, "body"))))
        return made

    # Declarations

    def specifiers(self, ts: _TS, attributes: list[Any] | None = None) -> list[_Node]:
        """The specifiers of a declaration-like node, in source order. Attributes before the first specifier go to
        `attributes` when given."""
        out: list[_Node] = []
        type_ = self.field(ts, "type")
        for i, c in enumerate(ts.children):
            name = ts.field_name_for_child(i)
            if type_ is not None and c.id == type_.id:
                out += self.specifier(c)
            elif c.type in _ATTRIBUTES and name is None:
                (attributes if attributes is not None and not out else out).append(self.attribute(c))
            elif c.type in ("storage_class_specifier", "type_qualifier", "virtual", "explicit_function_specifier") or (
                    not c.is_named and c.type in ("typedef", "__extension__", "friend")):
                out += self.specifier(c)
            elif c.type == "ms_call_modifier":
                raise _Invalid(c.type)
        return out

    def specifier(self, ts: _TS) -> list[_Node]:
        """The specifiers one tree-sitter node spells."""
        kind, spelling = ts.type, self.text(ts)
        if kind == "primitive_type" or kind == "type_identifier" and spelling in _PRIMITIVES:
            return [_Node("primitivetypespecifier", keyword=spelling)]
        if kind == "sized_type_specifier":
            out: list[_Node] = []
            for c in ts.children:
                out += [_Node("primitivetypespecifier", keyword=c.type)] if not c.is_named else self.specifier(c)
            return out
        if kind in ("type_identifier", "qualified_identifier", "template_type"):
            return [_Node("namedtypespecifier", name=self.name(ts))]
        if kind == "dependent_type":
            return [_Node("typenamespecifier", name=self.specifier(self.named(ts)[0])[0].name)]
        if kind == "placeholder_type_specifier":
            constraint = self.field(ts, "constraint")
            return [_Node("placeholdertypespecifier", constraint=self.name(constraint) if constraint is not None
                          else None, decltype=any(c.type == "decltype" for c in self.named(ts)))]
        if kind == "decltype":
            return [_Node("decltypespecifier", expression=self.expression(self.named(ts)[0]))]
        if kind in ("class_specifier", "struct_specifier", "union_specifier"):
            return [self.class_specifier(ts)]
        if kind == "enum_specifier":
            return [self.enum_specifier(ts)]
        if kind in ("storage_class_specifier", "virtual", "typedef", "__extension__", "friend"):
            return [_Node("declspecifier", keyword=spelling)]
        if kind == "explicit_function_specifier":
            if self.named(ts):  # `explicit(condition)` (C++20): no kind of mbse-expressions holds its condition
                raise _Invalid(kind)
            return [_Node("declspecifier", keyword="explicit")]
        inner = self.named(ts)  # a type qualifier, the last kind of specifier
        if inner:
            return [self.attribute(inner[0])]
        if spelling in _CV:
            return [_Node("cvqualifier", keyword=spelling)]
        return [_Node("declspecifier", keyword=spelling)]  # `constexpr`, `consteval`, `constinit`, `mutable`

    def class_specifier(self, ts: _TS) -> _Node:
        made = _Node("classspecifier", key=self.text(ts.children[0]), attributes=[])
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
            made.body = True
            made.members = _Node("memberlist", members=self.listed(body.children, self.member, body.children[0]))
        return made

    def bases(self, ts: _TS) -> list[_Node]:
        out: list[_Node] = []
        current: _Node | None = None
        for c in ts.children[1:]:
            if c.type == "comment":
                continue
            if current is None:
                current = _Node("basespecifier", attributes=[])
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
        if current is not None:
            out.append(current)
        return out

    def enum_specifier(self, ts: _TS) -> _Node:
        key = "enum"
        if len(ts.children) > 1 and ts.children[1].type in ("class", "struct"):
            key = f"enum {ts.children[1].type}"
        made = _Node("enumspecifier", key=key, attributes=[self.attribute(c) for c in self.named(ts)
                                                           if c.type in _ATTRIBUTES])
        name, base, body = self.field(ts, "name"), self.field(ts, "base"), self.field(ts, "body")
        if name is not None:
            made.name = self.name(name)
        if base is not None:
            made.base = _Node("typeid", specifiers=self.specifier(base))
        if body is not None:
            items = [c for c in body.children if not c.is_missing and c.type != "comment"]
            made.body = True
            made.enumerators = self.enumerators(body.children, body.children[0])
            made.trailing_comma = len(items) > 2 and items[-2].type == ","
        return made

    def attribute(self, ts: _TS) -> _Node:
        if ts.type == "alignas_qualifier":
            operand = self.named(ts)[0]
            return _Node("alignasspecifier", keyword=self.text(ts.children[0]), operand=self.type_id(
                operand) if operand.type == "type_descriptor" else self.expression(operand))
        made = super().attribute(ts)
        if ts.type == "attribute_declaration":
            made.using_namespace = self.pre.namespaces.get(self.local(ts))
        return made

    def standard_attribute(self, ts: _TS) -> _Node:
        prefix = self.field(ts, "prefix")
        arguments = next((c for c in self.named(ts) if c.type == "argument_list"), None)
        return _Node("attribute", namespace=self.text(prefix) if prefix is not None else None,
                     name=self.text(self.require(ts, "name")),
                     arguments=[self.argument(c) for c in self.named(arguments)] if arguments is not None else [])

    def arguments(self, ts: _TS) -> list[_Node]:
        return [self.argument(c) for c in self.named(ts)]

    def argument(self, ts: _TS) -> _Node:
        """An argument: an expression, or a type-id, where tree-sitter reads one (a template's, an attribute's)."""
        if ts.type == "type_descriptor":
            return self.type_id(ts)
        if ts.type == "initializer_list":
            return self.initializer_list(ts)
        return self.expression(ts)

    # Names

    def name(self, ts: _TS) -> _Node:
        kind = ts.type
        if kind in _NAMES or kind == "primitive_type":
            return self.identifier(ts)
        if kind in ("template_type", "template_function", "template_method"):
            return _Node("templateid", name=self.name(self.require(ts, "name")), arguments=[
                self.argument(c) for c in self.named(self.require(ts, "arguments"))])
        if kind == "dependent_name":
            made = self.name(self.named(ts)[0])
            made.template_keyword = True
            return made
        if kind == "qualified_identifier":
            global_scope, qualifiers, last = self.qualified_parts(ts)
            return _Node("qualifiedname", global_scope=global_scope, qualifiers=qualifiers, name=self.name(last))
        if kind == "destructor_name":
            return _Node("destructorname", type=self.name(self.named(ts)[0]))
        if kind == "decltype":
            return self.specifier(ts)[0]
        if kind == "operator_cast":
            return self.conversion_name(ts)
        if kind == "operator_name":
            parts = [self.text(c) for c in ts.children[1:] if c.type != "comment"]
            if parts and parts[0].startswith('""'):
                return _Node("literaloperatorname", suffix=parts[-1] if len(parts) > 1 else parts[0][2:])
            return _Node("operatorname", operator=_ALTERNATIVES.get("".join(parts), "".join(parts)))
        raise _Invalid(kind)

    def qualified_parts(self, ts: _TS) -> tuple[bool, list[_Node], _TS]:
        """A qualified_identifier, which tree-sitter nests: whether it starts with `::`, its qualifiers, and its last
        name's node."""
        qualifiers: list[_Node] = []
        node = ts
        while node.type == "qualified_identifier":
            scope = self.field(node, "scope")
            if scope is not None:
                qualifiers.append(self.name(scope))
            node = next(n for n in self.fields(node, "name") if n.is_named)
        return self.field(ts, "scope") is None, qualifiers, node

    # Declarators

    def declarator(self, ts: _TS) -> _Node:
        return self.inner_declarator(ts)

    def declared(self, ts: _TS) -> _Node:
        return self.inner_declarator(ts)

    def inner_declarator(self, ts: _TS) -> _Node:
        kind = ts.type
        if ts.is_missing:
            raise _Invalid(kind)
        if kind == "qualified_identifier":
            global_scope, qualifiers, last = self.qualified_parts(ts)
            if last.type == "pointer_type_declarator":  # `C::* declarator`
                made = self.declarator(last)
                scope = qualifiers.pop()
                made.scope = _Node("qualifiedname", global_scope=global_scope, qualifiers=qualifiers, name=scope) if (
                    qualifiers or global_scope) else scope
                return made
            if last.type == "operator_cast":
                return self.conversion(last, _Node("qualifiedname", global_scope=global_scope, qualifiers=qualifiers))
        if kind in _NAMES or kind in ("qualified_identifier", "template_function", "template_method", "template_type",
                                      "destructor_name", "operator_name", "primitive_type"):
            return _Node("iddeclarator", name=self.name(ts))
        inner = self.field(ts, "declarator")
        if kind in ("pointer_declarator", "abstract_pointer_declarator", "pointer_type_declarator"):
            made = _Node("pointerdeclarator", declarator=self.declarator(inner) if inner is not None else None,
                         qualifiers=[], attributes=[])
            for c in self.named(ts):
                if c.type == "type_qualifier":
                    made.qualifiers.append(_Node("cvqualifier", keyword=self.text(c)))
                elif c.type in _ATTRIBUTES:
                    made.attributes.append(self.attribute(c))
                elif inner is None or c.id != inner.id:
                    raise _Invalid(c.type)  # Microsoft's pointer modifiers
            return made
        if kind in ("reference_declarator", "abstract_reference_declarator"):
            parts = self.named(ts)
            return _Node("referencedeclarator", rvalue=self.has(ts, "&&"),
                         declarator=self.declarator(parts[0]) if parts else None)
        if kind in ("array_declarator", "abstract_array_declarator"):
            size = self.field(ts, "size")
            if self.has(ts, "static") or any(c.type == "type_qualifier" for c in self.named(ts)) or (
                    size is not None and size.type == "*"):
                raise _Invalid(kind)  # C's array declarators, which C++ has not
            return _Node("arraydeclarator", declarator=self.declarator(inner) if inner is not None else None,
                         size=self.expression(size) if size is not None else None)
        if kind in ("function_declarator", "abstract_function_declarator"):
            return self.function_declarator(ts)
        if kind in ("parenthesized_declarator", "abstract_parenthesized_declarator"):
            parts = self.named(ts)
            if len(parts) != 1:
                raise _Invalid(kind)  # a calling convention, `(__cdecl *f)`
            return _Node("parenthesizeddeclarator", declarator=self.declarator(parts[0]))
        if kind == "attributed_declarator":
            parts = self.named(ts)
            made = self.declarator(parts[0])
            made.attributes = (made.attributes or []) + [self.attribute(a) for a in parts[1:]]
            return made
        if kind == "variadic_declarator":
            parts = self.named(ts)
            return _Node("packdeclarator", declarator=self.declarator(parts[0]) if parts else None)
        if kind == "operator_cast":
            return self.conversion(ts, None)
        raise _Invalid(kind)  # a structured binding, which no kind of mbse-expressions holds

    def function_declarator(self, ts: _TS) -> _Node:
        """A function's declarator; its trailing requires-clause and virt-specifiers, the declaration's, are kept
        apart, `lifted`."""
        inner = self.field(ts, "declarator")
        made = _Node("functiondeclarator", declarator=self.declarator(inner) if inner is not None else None,
                     parameters=self.parameters(self.require(ts, "parameters")), qualifiers=[], attributes=[])
        for c in self.named(ts):
            if c.type == "parameter_list" or inner is not None and c.id == inner.id:
                continue
            if c.type == "type_qualifier":
                made.qualifiers.append(_Node("cvqualifier", keyword=self.text(c)))
            elif c.type == "ref_qualifier":
                made.ref_qualifier = self.text(c)
            elif c.type in ("noexcept", "throw_specifier"):
                made.exception = self.exception(c)
            elif c.type == "trailing_return_type":
                made.trailing_return = self.type_id(self.named(c)[0])
            elif c.type in _ATTRIBUTES:
                made.attributes.append(self.attribute(c))
            elif c.type == "requires_clause":
                self.lifted.setdefault("requires", self.requires_clause(c))
            elif c.type == "virtual_specifier":
                self.lifted.setdefault("virt_specifiers", []).append(self.text(c))
            elif c.type == "gnu_asm_expression":
                C._identifier(made.declarator).asm = self.asm_label(c)
            else:
                raise _Invalid(c.type)
        return made

    def conversion_name(self, ts: _TS) -> _Node:
        """`operator type`, a conversion function's name, of its type and the pointers and references after it."""
        wrappers: list[_TS] = []
        node = self.field(ts, "declarator")
        while node is not None and node.type in ("abstract_pointer_declarator", "abstract_reference_declarator"):
            wrappers.append(node)
            node = self.named(node)[-1] if self.named(node) else None
        declarator: _Node | None = None
        for w in reversed(wrappers):
            if w.type == "abstract_pointer_declarator":
                declarator = _Node("pointerdeclarator", declarator=declarator, qualifiers=[
                    _Node("cvqualifier", keyword=self.text(c)) for c in self.named(w) if c.type == "type_qualifier"])
            else:
                declarator = _Node("referencedeclarator", rvalue=self.has(w, "&&"), declarator=declarator)
        return _Node("conversionname", type=_Node("typeid", specifiers=self.specifiers(ts), declarator=declarator))

    def conversion(self, ts: _TS, qualified: _Node | None) -> _Node:
        """`operator type ()`, a conversion function's declarator, which tree-sitter nests within the conversion type's
        pointers: the function's declarator, its name the conversion's."""
        node = self.require(ts, "declarator")
        while node.type in ("abstract_pointer_declarator", "abstract_reference_declarator"):
            node = self.named(node)[-1]
        name = self.conversion_name(ts)
        if qualified is not None:
            qualified.name = name
            name = qualified
        made = self.function_declarator(node)
        made.declarator = _Node("iddeclarator", name=name)
        return made

    def exception(self, ts: _TS) -> _Node:
        if ts.type == "noexcept":
            condition = self.named(ts)
            return _Node("noexceptspecifier", condition=self.expression(condition[0]) if condition else None)
        return _Node("throwspecifier", types=[self.type_id(c) for c in self.named(ts)])

    def parameters(self, ts: _TS) -> list[_Node]:
        out: list[_Node] = []
        for c in ts.children:
            if c.type in ("...", "variadic_parameter"):
                out.append(_Node("ellipsisparameter"))
            elif c.type in ("parameter_declaration", "optional_parameter_declaration",
                            "variadic_parameter_declaration"):
                out.append(self.parameter(c))
            elif c.is_named and c.type != "comment":
                raise _Invalid(c.type)
        return out

    def parameter(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        made = _Node("parameterdeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     this_keyword=self.local(ts) in self.pre.this)
        declarator = self.field(ts, "declarator")
        if declarator is not None:
            made.declarator = self.declarator(declarator)
        default = self.field(ts, "default_value")
        if default is not None:
            made.default = self.argument(default)
        return made

    def template_parameters(self, ts: _TS) -> list[_Node]:
        out: list[_Node] = []
        for c in self.named(ts):
            kind = c.type
            if kind in ("type_parameter_declaration", "variadic_type_parameter_declaration",
                        "optional_type_parameter_declaration"):
                out.append(self.type_parameter(c))
            elif kind == "template_template_parameter_declaration":
                inner = self.type_parameter(self.named(c)[-1])
                made = _Node("templatetemplateparameter", parameters=self.template_parameters(
                    self.require(c, "parameters")), key=inner.key, pack=inner.pack, name=inner.name)
                if inner.default is not None:
                    made.default = inner.default.specifiers[0].name
                out.append(made)
            elif kind in ("parameter_declaration", "optional_parameter_declaration",
                          "variadic_parameter_declaration"):
                out.append(self.parameter(c))
            else:
                raise _Invalid(kind)
        return out

    def type_parameter(self, ts: _TS) -> _Node:
        first = ts.children[0]
        made = _Node("typeparameter", pack=self.has(ts, "..."))
        if first.type in ("class", "typename"):
            made.key = first.type
        else:  # a constrained parameter, `Number T`
            made.constraint = self.name(first)
        name = self.field(ts, "name") or next((c for c in self.named(ts) if c.type == "type_identifier" and (
            c.id != first.id)), None)
        if name is not None:
            made.name = self.identifier(name)
        default = self.field(ts, "default_type")
        if default is not None:
            made.default = _Node("typeid", specifiers=self.specifier(default))
        return made

    def type_id(self, ts: _TS) -> _Node:
        """A type_descriptor: specifiers in source order, and its abstract declarator, Cpp Types' `typeid`."""
        declarator = self.field(ts, "declarator")
        return _Node("typeid", specifiers=self.specifiers(ts), declarator=self.declarator(declarator)
                     if declarator is not None else None)

    # Declarations

    lifted: dict[str, Any]

    def declaration(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        made = _Node("simpledeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     declarators=[])
        for i, c in enumerate(ts.children):
            field = ts.field_name_for_child(i)
            if field == "declarator":
                made.declarators.append(self.init_declarator(c, "initdeclarator"))
            elif field == "value":  # a condition's declarator's, which tree-sitter reads as the declaration's
                made.declarators[-1].initializer = self.initializer(c, ts.children[i - 1].type == "=")
            elif c.type == "gnu_asm_expression":
                raise _Invalid(c.type)  # where tree-sitter reads one, it reads its own declarator
        return made

    def init_declarator(self, ts: _TS, kind: str) -> _Node:
        """A declarator, with what initializes it, its trailing `requires` (and, a member's, its virt-specifiers)."""
        self.lifted = {}
        if ts.type == "init_declarator":
            made = _Node(kind, declarator=self.declarator(self.require(ts, "declarator")))
            made.initializer = self.initializer(self.require(ts, "value"), self.has(ts, "="))
        else:
            made = _Node(kind, declarator=self.declarator(ts))
        made.requires = self.lifted.get("requires")
        if self.lifted.get("virt_specifiers"):
            if kind != "memberdeclarator":
                raise _Invalid("virt-specifier")
            made.virt_specifiers = self.lifted["virt_specifiers"]
        return made

    def initializer(self, ts: _TS, equals: bool) -> _Node:
        """What initializes a declarator: `= value`, `(arguments)` or `{items}`."""
        if ts.type == "argument_list":
            return _Node("parenthesizedinitializer", arguments=self.arguments(ts))
        if not equals and ts.type == "initializer_list":
            return self.initializer_list(ts)
        return _Node("equalinitializer", value=self.argument(ts))

    def function_definition(self, ts: _TS) -> _Node:
        self.lifted = {}
        attributes: list[_Node] = []
        made = _Node("functiondefinition", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     declarator=self.declarator(self.require(ts, "declarator")))
        made.virt_specifiers, made.requires = self.lifted.get("virt_specifiers"), self.lifted.get("requires")
        if C._binder(made.declarator).branch != "functiondeclarator" or C._identifier(made.declarator) is None:
            raise _Invalid(ts.type)
        clauses = {c.type: c for c in self.named(ts)}
        body = self.field(ts, "body") or clauses.get("try_statement")
        if "field_initializer_list" in clauses:
            made.initializers = self.member_initializers(clauses["field_initializer_list"])
        if body is not None and body.type == "try_statement":
            inner = next((c for c in self.named(body) if c.type == "field_initializer_list"), None)
            if inner is not None:
                made.initializers = self.member_initializers(inner)
            made.body = self.new(body, "trystatement", **self.try_statement(body).fields)
        elif body is not None:
            made.body = self.block(body)
        elif "default_method_clause" in clauses:
            made.body = _Node("defaultedbody")
        elif "delete_method_clause" in clauses:
            made.body = _Node("deletedbody")
        else:  # `= 0` with a body, which tree-sitter reads
            raise _Invalid(ts.type)
        return made

    def member_initializers(self, ts: _TS) -> list[_Node]:
        out = []
        for c in self.named(ts):
            parts = self.named(c)
            value = parts[-1]
            initializer = _Node("parenthesizedinitializer", arguments=self.arguments(value)) if (
                value.type == "argument_list") else self.initializer_list(value)
            out.append(_Node("memberinitializer", member=self.name(parts[0]), initializer=initializer,
                             pack=self.has(c, "...")))
        return out

    def template_declaration(self, ts: _TS) -> _Node:
        parameters = self.require(ts, "parameters")
        made = _Node("templatedeclaration", parameters=self.template_parameters(parameters))
        for c in self.named(ts):
            if c.id == parameters.id:
                continue
            if c.type == "requires_clause":
                made.requires = self.requires_clause(c)
            elif made.declaration is None:
                made.declaration = self.templated(c)
            else:
                raise _Invalid(c.type)
        return made

    def templated(self, ts: _TS) -> _Node:
        """What a template declares: a declaration, or, within a class, a member's declaration."""
        if ts.type == "field_declaration" or ts.type == "declaration" and self.member_context:
            return self.convert_member(ts)
        if ts.type in ("class_specifier", "struct_specifier", "union_specifier", "enum_specifier"):
            return _Node("simpledeclaration", specifiers=self.specifier(ts))
        made = self.convert(ts)
        if made.branch not in ("simpledeclaration", "functiondefinition", "aliasdeclaration", "conceptdefinition",
                               "templatedeclaration", "memberdeclaration"):
            raise _Invalid(ts.type)
        return made

    member_context = False

    def template_instantiation(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        declaration = _Node("simpledeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                            declarators=[])
        declarator = self.field(ts, "declarator")
        if declarator is not None and declarator.is_missing:  # `template class V<int>;`, read with a missing name
            self.consumed.add(declarator.id)
        elif declarator is not None:
            declaration.declarators.append(self.init_declarator(declarator, "initdeclarator"))
        return _Node("explicitinstantiation", extern=self.local(ts) in self.pre.extern, declaration=declaration)

    def friend(self, ts: _TS) -> _Node:
        inner = self.named(ts)
        if inner and inner[0].type in ("declaration", "function_definition", "field_declaration"):
            made = self.convert_member(inner[0]) if self.member_context else self.convert(inner[0])
            made.specifiers = [_Node("declspecifier", keyword="friend"), *made.specifiers]
            return made
        key = next((c.type for c in ts.children if c.type in ("class", "struct", "union")), None)
        specifier = _Node("classspecifier", key=key, name=self.name(inner[0])) if key is not None else (
            self.specifier(inner[0])[0])
        return _Node("memberdeclaration" if self.member_context else "simpledeclaration", specifiers=[
            _Node("declspecifier", keyword="friend"), specifier])

    def alias(self, ts: _TS) -> _Node:
        return _Node("aliasdeclaration", name=self.identifier(self.require(ts, "name")),
                     attributes=[self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES],
                     type=self.type_id(self.require(ts, "type")))

    def using(self, ts: _TS) -> _Node:
        target = self.name(self.named(ts)[-1])
        if self.has(ts, "namespace"):
            return _Node("usingdirective", name=target, attributes=[
                self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES])
        if self.has(ts, "enum"):
            return _Node("usingenumdeclaration", type=target)
        made = _Node("usingdeclaration", declarators=[_Node("usingdeclarator", typename_keyword=self.has(
            ts, "typename"), name=target)])
        for start, end in self.pre.usings.get(self.local(ts), []):
            converter, root = self.reparsed("using ", start, end, ";")
            if root.has_error:
                raise _Invalid("using")
            made.declarators += converter.using(converter.named(root)[0]).declarators
        return made

    def namespace(self, ts: _TS) -> _Node:
        made = _Node("namespacedefinition", inline=self.has(ts, "inline"),
                     attributes=[self.attribute(c) for c in self.named(ts) if c.type in _ATTRIBUTES])
        name = self.field(ts, "name")
        made.names = [_Node("namespacename", inline=inline, name=self.identifier(n))
                      for inline, n in self.namespace_names(name)] if name is not None else []
        body = self.require(ts, "body")
        made.body = self.listed(body.children, self.external, body.children[0])
        return made

    def namespace_names(self, ts: _TS) -> list[tuple[bool, _TS]]:
        """The names of a namespace_identifier or nested_namespace_specifier, which tree-sitter nests, each with
        whether `inline` precedes it."""
        if ts.type == "namespace_identifier":
            return [(False, ts)]
        out: list[tuple[bool, _TS]] = []
        inline = False
        for c in ts.children:
            if c.type == "inline":
                inline = True
            elif c.is_named:
                found = self.namespace_names(c)
                out.append((inline or found[0][0], found[0][1]))
                out += found[1:]
                inline = False
        return out

    def namespace_alias(self, ts: _TS) -> _Node:
        name = self.require(ts, "name")
        target = next(c for c in self.named(ts) if c.id != name.id)
        if target.type == "nested_namespace_specifier":
            parts = [self.identifier(n) for _, n in self.namespace_names(target)]
            resolved = _Node("qualifiedname", qualifiers=parts[:-1], name=parts[-1],
                             global_scope=target.children[0].type == "::")
        else:
            resolved = self.name(target)
        return _Node("namespacealiasdefinition", name=self.identifier(name), target=resolved)

    def static_assert(self, ts: _TS) -> _Node:
        message = self.field(ts, "message")
        return _Node("staticassertdeclaration", keyword=self.text(ts.children[0]),
                     condition=self.expression(self.require(ts, "condition")),
                     message=self.expression(message) if message is not None else None)

    def linkage(self, ts: _TS) -> _Node:
        body = self.require(ts, "body")
        language = self.text(self.require(ts, "value"))[1:-1]
        if body.type == "declaration_list":
            return _Node("linkagespecification", language=language, braced=True, body=self.listed(
                body.children, self.external, body.children[0]))
        return _Node("linkagespecification", language=language, body=[self.external(body)])

    def concept(self, ts: _TS) -> _Node:
        name = self.require(ts, "name")
        return _Node("conceptdefinition", name=self.identifier(name), attributes=[], constraint=self.expression(
            next(c for c in self.named(ts) if c.id != name.id)))

    # Members

    def convert_member(self, ts: _TS) -> _Node:
        outer, self.member_context = self.member_context, True
        try:
            made = self.member_kind(ts)
        finally:
            self.member_context = outer
        made.line = self.line(ts)
        return made

    def member_kind(self, ts: _TS) -> _Node:
        kind = ts.type
        if kind.startswith("preproc_"):
            return self.directive(ts, "member")
        if kind == "access_specifier":
            return _Node("accessspecifier", access=self.text(ts))
        if kind in ("field_declaration", "declaration", "type_definition"):
            attributes: list[_Node] = []
            made = _Node("memberdeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                         declarators=[])
            kids = ts.children
            for i, c in enumerate(kids):
                field = ts.field_name_for_child(i)
                if field == "declarator":
                    if c.is_missing:  # an unnamed bit-field, which tree-sitter reads with a missing name
                        self.consumed.add(c.id)
                        made.declarators.append(_Node("memberdeclarator"))
                    elif c.type == "init_declarator":
                        made.declarators.append(self.init_declarator(c, "memberdeclarator"))
                    else:
                        made.declarators.append(self.init_declarator(c, "memberdeclarator"))
                elif field == "default_value":
                    equals = kids[i - 1].type == "="
                    value = self.initializer(c, equals)
                    if equals and c.type == "number_literal" and self.text(c) == "0" and (
                            C._binder(made.declarators[-1].declarator).branch == "functiondeclarator"):
                        made.declarators[-1].pure = True  # `= 0`, the pure-specifier
                    else:
                        made.declarators[-1].initializer = value
                elif c.type == "bitfield_clause":
                    made.declarators[-1].bitfield = self.expression(self.named(c)[0])
                    span = self.pre.bitfields.get(self.source.offset(c.end_byte))
                    if span is not None:  # its initializer (C++20), which the pre-pass blanked
                        converter, root = self.reparsed("int _ ", *span, ";")
                        declarator = converter.named(root)[0]
                        if root.has_error:
                            raise _Invalid("bitfield")
                        value = converter.require(converter.require(declarator, "declarator"), "value")
                        made.declarators[-1].initializer = converter.initializer(
                            value, converter.has(converter.require(declarator, "declarator"), "="))
                elif c.type == "pure_virtual_clause":
                    made.declarators[-1].pure = True
            return made
        if kind in self.SPECIFIER_NODES:
            return _Node("memberdeclaration", specifiers=self.specifier(ts))
        made = self.convert(ts)
        if made.branch not in ("functiondefinition", "usingdeclaration", "usingenumdeclaration", "aliasdeclaration",
                               "staticassertdeclaration", "templatedeclaration", "emptydeclaration",
                               "memberdeclaration", "comment"):
            raise _Invalid(kind)
        return made

    # Expressions

    def identifier_expression(self, ts: _TS) -> _Node:
        return _Node("idexpression", name=self.name(ts))

    def null(self, ts: _TS) -> _Node:
        text = self.text(ts)
        if text == "nullptr":
            return _Node("constant", singleton="nullptr", text=text)
        return _Node("idexpression", name=self.identifier(ts))  # `NULL`, a macro's name

    def number(self, ts: _TS) -> _Node:
        return _number(self.text(ts))

    def quoted(self, ts: _TS) -> _Node:
        if ts.type == "raw_string_literal":
            text = self.text(ts)
            quote = text.index('"')
            opening = text.index("(", quote)
            delimiter = text[quote + 1:opening]
            return _Node("literal", value=_scalar(text[opening + 1:len(text) - len(delimiter) - 2]), text=text,
                         prefix=text[:quote - 1] or None, quote='"', raw=True, delimiter=delimiter or None)
        return super().quoted(ts)

    def user_defined(self, ts: _TS) -> _Node:
        literal, suffix = self.named(ts)
        text = self.text(literal)
        made = _number(text) if literal.type == "number_literal" else self.expression(literal)
        if made.branch != "literal":
            raise _Invalid(ts.type)
        return _Node("userdefinedliteral", literal=made, suffix=self.text(suffix))

    def binary(self, ts: _TS) -> _Node:
        operator = self.text(self.require(ts, "operator"))
        return _Node("binaryexpression", left=self.expression(self.require(ts, "left")),
                     operator=_ALTERNATIVES.get(operator, operator), right=self.expression(self.require(ts, "right")))

    def assignment(self, ts: _TS) -> _Node:
        operator = self.text(self.require(ts, "operator"))
        return _Node("assignmentexpression", left=self.expression(self.require(ts, "left")),
                     operator=_ALTERNATIVES.get(operator, operator), right=self.argument(self.require(ts, "right")))

    def unary(self, ts: _TS) -> _Node:
        made = super().unary(ts)
        if made.branch == "unaryexpression":
            made.operator = _ALTERNATIVES.get(made.operator, made.operator)
        return made

    def call(self, ts: _TS) -> _Node:
        function, arguments = self.require(ts, "function"), self.require(ts, "arguments")
        if function.type == "primitive_type":  # `int(x)`
            return _Node("functionalcastexpression", type=self.specifier(function)[0],
                         initializer=_Node("parenthesizedinitializer", arguments=self.arguments(arguments)))
        if function.type == "identifier" and self.text(function) in ("typeid", "noexcept", "_Pragma"):
            return self.operator_call(self.text(function), arguments)
        if function.type == "template_function":
            name = self.text(self.require(function, "name"))
            types = self.named(self.require(function, "arguments"))
            if name in _CASTS and len(types) == 1 and types[0].type == "type_descriptor":
                operands = self.named(arguments)
                if len(operands) != 1:
                    raise _Invalid(name)
                return _Node("namedcastexpression", operator=name, type=self.type_id(types[0]),
                             operand=self.expression(operands[0]))
        return _Node("callexpression", function=self.expression(function), arguments=self.arguments(arguments))

    def operator_call(self, keyword: str, arguments: _TS) -> _Node:
        """`typeid(x)`, `noexcept(x)` and `_Pragma("...")`, which tree-sitter-cpp reads as calls: `typeid` of a
        type-id, which it cannot read there, read again as one."""
        operands = self.named(arguments)
        if keyword == "_Pragma":
            if len(operands) != 1 or operands[0].type != "string_literal":
                raise _Invalid(keyword)
            return self.pragma(self.expression(operands[0]))
        if keyword == "typeid" and arguments.has_error:
            self.consumed.update(c.id for c in arguments.children)
            operand = self.part_type(self.local(arguments) + 1, self.source.offset(arguments.end_byte) - 1)
            return _Node("typeidexpression", operand=operand)
        if len(operands) != 1:
            raise _Invalid(keyword)
        return _Node("typeidexpression" if keyword == "typeid" else "noexceptexpression",
                     operand=self.argument(operands[0]))

    def field_expression(self, ts: _TS) -> _Node:
        operator, member = self.text(self.require(ts, "operator")), self.require(ts, "field")
        if operator in (".*", "->*"):
            return _Node("binaryexpression", left=self.expression(self.require(ts, "argument")), operator=operator,
                         right=self.expression(member))
        keyword = member.type == "dependent_name"  # `object.template name<...>`: the keyword is the access's
        return _Node("memberexpression", object=self.expression(self.require(ts, "argument")), operator=operator,
                     template_keyword=keyword, member=self.name(self.named(member)[0] if keyword else member))

    def subscript(self, ts: _TS) -> _Node:
        return _Node("subscriptexpression", object=self.expression(self.require(ts, "argument")),
                     indices=self.arguments(self.require(ts, "indices")))

    def sizeof(self, ts: _TS) -> _Node:
        type_ = self.field(ts, "type")
        if type_ is not None:
            return _Node("sizeofexpression", operand=self.type_id(type_))
        value = self.require(ts, "value")
        if self.has(ts, "..."):
            return _Node("sizeofpackexpression", pack=self.identifier(value))
        return _Node("sizeofexpression", operand=self.expression(value))

    def new_expression(self, ts: _TS) -> _Node:
        type_ = self.require(ts, "type")
        declarator: _Node | None = None
        node = self.field(ts, "declarator")
        while node is not None:
            declarator = _Node("arraydeclarator", declarator=declarator, size=self.expression(
                self.require(node, "length")))
            node = next((c for c in self.named(node) if c.type == "new_declarator"), None)
        placement, arguments = self.field(ts, "placement"), self.field(ts, "arguments")
        made = _Node("newexpression", global_scope=self.has(ts, "::"),
                     placement=self.arguments(placement) if placement is not None else [],
                     type=_Node("typeid", specifiers=self.specifier(type_), declarator=declarator))
        if arguments is not None:
            made.initializer = self.initializer(arguments, False)
        return made

    def delete(self, ts: _TS) -> _Node:
        return _Node("deleteexpression", global_scope=self.has(ts, "::"), array=self.has(ts, "["),
                     operand=self.expression(self.named(ts)[0]))

    def fold(self, ts: _TS) -> _Node:
        left, right = self.require(ts, "left"), self.require(ts, "right")
        operator = self.text(self.require(ts, "operator"))
        return _Node("foldexpression", left=self.expression(left) if left.is_named else None,
                     operator=_ALTERNATIVES.get(operator, operator),
                     right=self.expression(right) if right.is_named else None)

    def pack_expansion(self, ts: _TS) -> _Node:
        return _Node("packexpansion", pattern=self.argument(self.require(ts, "pattern")))

    def initializer_list(self, ts: _TS) -> _Node:
        kids = [c for c in ts.children if not c.is_missing and c.type != "comment"]
        items = [self.designated(c) if c.type == "initializer_pair" else self.argument(c) for c in self.named(ts)]
        return _Node("initializerlist", items=items, trailing_comma=len(kids) > 2 and kids[-2].type == ",")

    def designated(self, ts: _TS) -> _Node:
        designators: list[_Node] = []
        for d in self.fields(ts, "designator"):
            if d.type not in ("field_designator", "field_identifier"):
                raise _Invalid(d.type)  # C's index designators, which C++ has not
            designators.append(_Node("fielddesignator", name=self.identifier(
                self.named(d)[0] if d.type == "field_designator" else d)))
        value = self.require(ts, "value")
        initializer = self.initializer_list(value) if value.type == "initializer_list" and not self.has(ts, "=") else (
            _Node("equalinitializer", value=self.argument(value)))
        return _Node("designatedinitializer", designators=designators, initializer=initializer)

    def compound_literal(self, ts: _TS) -> _Node:
        type_ = self.require(ts, "type")
        if type_.type == "type_descriptor":
            raise _Invalid(ts.type)  # C's compound literal, which C++ has not
        return _Node("functionalcastexpression", type=self.specifier(type_)[0],
                     initializer=self.initializer_list(self.require(ts, "value")))

    def lambda_(self, ts: _TS) -> _Node:
        made = _Node("lambdaexpression", captures=[], block=self.block(self.require(ts, "body")))
        captures = [c for c in self.require(ts, "captures").children if c.type != "comment"]
        i = 1
        while i < len(captures) - 1:
            c = captures[i]
            i += 1
            if c.type == ",":
                continue
            if c.type == "lambda_default_capture":
                made.captures.append(_Node("defaultcapture", mode=self.text(c)))
            elif c.type == "&":
                target = captures[i]
                i += 1
                pack = target.type == "parameter_pack_expansion"
                made.captures.append(_Node("simplecapture", by_reference=True, pack=pack, name=self.identifier(
                    self.require(target, "pattern") if pack else target)))
            elif c.type == "*":
                made.captures.append(_Node("thiscapture", copy=True))
                i += 1
            elif c.type == "this":
                made.captures.append(_Node("thiscapture"))
            elif c.type == "lambda_capture_initializer":
                value = self.require(c, "right")
                made.captures.append(_Node("initcapture", by_reference=self.has(c, "&"), pack=self.has(c, "..."),
                                           name=self.identifier(self.require(c, "left")),
                                           initializer=self.initializer(value, self.has(c, "="))))
            elif c.type == "parameter_pack_expansion":
                made.captures.append(_Node("simplecapture", name=self.identifier(self.require(c, "pattern")),
                                           pack=True))
            elif c.type == "identifier":
                made.captures.append(_Node("simplecapture", name=self.identifier(c)))
            else:
                raise _Invalid(c.type)
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

    def lambda_declarator(self, ts: _TS) -> _Node:
        made = _Node("lambdadeclarator", parameters=self.parameters(self.require(ts, "parameters")), specifiers=[],
                     attributes=[])
        for c in self.named(ts):
            if c.type == "parameter_list":
                continue
            if c.type in ("type_qualifier", "storage_class_specifier"):
                made.specifiers.append(_Node("declspecifier", keyword=self.text(c)))
            elif c.type in ("noexcept", "throw_specifier"):
                made.exception = self.exception(c)
            elif c.type == "trailing_return_type":
                made.trailing_return = self.type_id(self.named(c)[0])
            elif c.type == "requires_clause":
                made.requires = self.requires_clause(c)
            elif c.type in _ATTRIBUTES:
                made.attributes.append(self.attribute(c))
            else:
                raise _Invalid(c.type)
        return made

    def requires_expression(self, ts: _TS) -> _Node:
        parameters = self.field(ts, "parameters")
        made = _Node("requiresexpression", parameters=self.parameters(parameters) if parameters is not None else [],
                     requirements=[])
        for r in self.named(self.require(ts, "requirements")):
            if r.type != "simple_requirement" or self.named(r):  # tree-sitter reads `;` after some as empty ones
                made.requirements.append(self.requirement(r))
        return made

    def requirement(self, ts: _TS) -> _Node:
        if ts.type == "simple_requirement":
            inner = self.named(ts)
            if inner[0].type == "requires_clause":  # `requires constraint;`
                return _Node("nestedrequirement", constraint=self.requires_clause(inner[0]))
            return _Node("simplerequirement", expression=self.expression(inner[0]))
        if ts.type == "type_requirement":
            return _Node("typerequirement", name=self.name(self.named(ts)[0]))
        parts = self.named(ts)
        made = _Node("compoundrequirement", expression=self.expression(parts[0]), noexcept=self.has(ts, "noexcept"))
        for p in parts[1:]:
            made.return_type = self.name(self.require(self.named(p)[0], "type"))
        return made

    def requires_clause(self, ts: _TS) -> _Node:
        return self.constraint(self.fields(ts, "constraint"))

    def constraint(self, parts: list[_TS]) -> _Node:
        """A constraint expression from tree-sitter's constraint fields, which hold parentheses as tokens."""
        if parts[0].type == "(":
            return _Node("parenthesizedexpression", expression=self.constraint(parts[1:-1]))
        ts = parts[0]
        if ts.type in ("constraint_conjunction", "constraint_disjunction"):
            operator = self.text(self.require(ts, "operator"))
            return _Node("binaryexpression", left=self.constraint(self.fields(ts, "left")),
                         operator=_ALTERNATIVES.get(operator, operator),
                         right=self.constraint(self.fields(ts, "right")))
        if ts.type in ("template_type", "type_identifier"):
            return _Node("idexpression", name=self.name(ts))
        return self.expression(ts)

    EXPRESSIONS: dict[str, Callable[[Any, _TS], Any]] = {}
    STATEMENTS: dict[str, Callable[[Any, _TS], Any]] = {}
    DECLARATIONS: dict[str, Callable[[Any, _TS], Any]] = {}


_C = C._Converter


def _virtual(table: dict[str, Callable[[Any, _TS], Any]]) -> dict[str, Callable[[Any, _TS], Any]]:
    """C's converter's table, each method in it this converter's, which may override C's."""
    return {kind: method if method.__name__ == "<lambda>" else getattr(_Converter, method.__name__)
            for kind, method in table.items()}


_Converter.EXPRESSIONS.update({
    **{k: v for k, v in _virtual(_C.EXPRESSIONS).items() if k not in (
        "identifier", "generic_expression", "offsetof_expression", "compound_literal_expression")},
    **{n: _Converter.identifier_expression for n in _NAMES | {
        "qualified_identifier", "template_function", "template_method", "dependent_name", "destructor_name",
        "operator_name"}},
    "number_literal": _Converter.number, "char_literal": _Converter.quoted, "string_literal": _Converter.quoted,
    "raw_string_literal": _Converter.quoted, "user_defined_literal": _Converter.user_defined,
    "null": _Converter.null, "this": lambda self, ts: _Node("thisexpression"),
    "binary_expression": _Converter.binary, "assignment_expression": _Converter.assignment,
    "unary_expression": _Converter.unary, "pointer_expression": _Converter.unary,
    "cast_expression": lambda self, ts: _Node("castexpression", type=self.type_id(self.require(ts, "type")),
                                              operand=self.expression(self.require(ts, "value"))),
    "call_expression": _Converter.call, "field_expression": _Converter.field_expression,
    "subscript_expression": _Converter.subscript, "sizeof_expression": _Converter.sizeof,
    "alignof_expression": lambda self, ts: _Node("alignofexpression", keyword=self.text(ts.children[0]),
                                                 operand=self.type_id(self.require(ts, "type"))),
    "new_expression": _Converter.new_expression, "delete_expression": _Converter.delete, "fold_expression": _Converter.fold,
    "parameter_pack_expansion": _Converter.pack_expansion, "initializer_list": _Converter.initializer_list,
    "compound_literal_expression": _Converter.compound_literal, "lambda_expression": _Converter.lambda_,
    "requires_expression": _Converter.requires_expression, "requires_clause": _Converter.requires_clause,
    "co_await_expression": lambda self, ts: _Node("awaitexpression", operand=self.expression(
        self.require(ts, "argument"))),
    "conditional_expression": lambda self, ts: _Node(
        "conditionalexpression", condition=self.expression(self.require(ts, "condition")),
        consequence=self.expression(self.field(ts, "consequence")) if self.field(ts, "consequence") else None,
        alternative=self.argument(self.require(ts, "alternative"))),
})

_Converter.STATEMENTS.update({
    **_virtual(_C.STATEMENTS),
    "if_statement": _Converter.if_statement, "switch_statement": _Converter.switch_statement,
    "while_statement": _Converter.while_statement, "do_statement": _Converter.do_statement,
    "for_statement": _Converter.for_statement, "for_range_loop": _Converter.range_for,
    "co_return_statement": _Converter.co_return, "co_yield_statement": _Converter.co_yield,
    "throw_statement": _Converter.throw, "try_statement": _Converter.try_statement,
})

_Converter.DECLARATIONS.update({
    **_virtual(_C.DECLARATIONS),
    "type_definition": _Converter.declaration, "function_definition": _Converter.function_definition,
    "template_declaration": _Converter.template_declaration,
    "template_instantiation": _Converter.template_instantiation, "friend_declaration": _Converter.friend,
    "alias_declaration": _Converter.alias, "using_declaration": _Converter.using,
    "namespace_definition": _Converter.namespace, "namespace_alias_definition": _Converter.namespace_alias,
    "static_assert_declaration": _Converter.static_assert, "linkage_specification": _Converter.linkage,
    "concept_definition": _Converter.concept,
    **{kind: lambda self, ts: self.directive(ts, "statement") for kind in (
        "preproc_include", "preproc_def", "preproc_function_def", "preproc_call", "preproc_if", "preproc_ifdef")},
})


# --- The transaction ---


def _parsed(text: str) -> tuple[_Source, _Prepared, Any]:
    """`text` parsed, pre-passed and parsed again where the pre-pass rewrote it: its source, what the pre-pass rewrote,
    and tree-sitter's tree."""
    source = _Source(text)
    tree = _PARSER.parse(source.data, encoding="utf16le")
    cleaned, prepared = _prepare(text, tree.root_node, source)
    if cleaned != text:
        source = _Source(text, cleaned)
        tree = _PARSER.parse(source.data, encoding="utf16le")
    return source, prepared, tree


def parse(text: str, path: str, store: Any = None) -> Callable[[Any], Any]:
    """The callback of the transaction that writes `text`, C++ source, as the translation unit at `path` in the
    workspace: given to `store.transaction`, or, with `store`, to `store.Mutations.OfTransaction`. Raises `ParseError`
    only for text that is no text, a lone surrogate (which no encoding writes), now, before any transaction: invalid
    syntax is kept (`Programs.Cpp.Error`, the dialects' `error` and `missing`)."""
    try:
        text.encode("utf-16-le")
    except UnicodeEncodeError as error:  # a lone surrogate
        at = error.start
        line, column = text.count("\n", 0, at) + 1, at - (text.rfind("\n", 0, at) + 1) + 1
        raise ParseError("not text: a lone surrogate", line, column) from None
    source, prepared, tree = _parsed(text)
    body = C._write(_cpp(_Converter(source, prepared).unit(tree.root_node)))

    def transaction(txn: Any) -> Any:
        symbols = {"ws": store.registered("Programs.Framework.Workspace") if store is not None else
                   txn.Programs.Framework.Workspace,
                   "unit": store.registered(f"{_LANGUAGE}.TranslationUnit") if store is not None else
                   txn.Programs.Cpp.TranslationUnit}
        return txn.uid(path).mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
            .symbols(symbols)
            .spec([
                lambda _: _.ws.files({path: lambda e: e.file(_.unit)}),
                lambda _: _.unit.body(body),
            ])]))])

    return transaction
