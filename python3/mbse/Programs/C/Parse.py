"""Parse: C source text as the transaction that writes its translation unit, delegating to tree-sitter-c.

`parse(text, path)` reads `text` at once, keeping what does not parse as invalid syntax, and gives the transaction's
callback, which a caller executes, `store.transaction(parse(text, path))`, or builds to write it,
`Plain.ToPlain(store).Transaction(store.Mutations.OfTransaction(parse(text, path, store)))`. Executed in a store holding
the installs (`C.INSTALLS`: mbse-expressions' `Framework`, `C`, `C Types` and `C Preprocessor`, then
`Programs.Framework.Model` and `Programs.C`), it is one upsert, `uid(path)`, whose symbols bind the workspace (`ws`, its
singleton `Programs.Framework.TheWorkspace`) and the translation unit (`unit`); its spec puts the unit in the
workspace's `files` by `path` and writes its tree, the unit's `body`, as one value: each declaration and statement a
branch of `Programs.C.Statement`, holding its properties, its line and the statements of its blocks, nested (stage 3's
design, "the whole tree as values"). Its frame binds the unit, and assigns it its tree.

As the port decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#stage-4-c-and-cpp)),
the whole tree is values: statements and declarations are `Programs.C`'s kinds (`Statements`), value objects nested in
the unit's `body`; expressions are mbse-expressions' `C` terms, a declaration's specifiers, declarators and attributes
`C Types`' helpers, and directives `C Preprocessor` terms, nested values too, written through the builders with their
concrete syntax as far as the dialects keep it: parentheses written in the source (`parenthesizedexpression`), and a
literal's spelling (`text`, `prefix`, `quote`, `base`, `separators`, `suffix`). Where a term holds statements or
declarations, its property holds them, as the user decided ("the crossover should be modeled as a property of T_A"): a
statement expression's `block`, a struct's or a union's `members`, and a conditional directive's `group`.
tree-sitter-c builds a concrete syntax tree; `_Converter` rewrites it one node type at a time.

Reused from mbse-programs 0.3 (`Ccpp/_Parser.py`), as it was but for tree-sitter-c's node types, which 0.3 read with
tree-sitter-cpp: the source and its offsets (`_Source`), counted in characters (code points), never bytes, so that every
implementation reports the same line; a `case` or `default` label labeling the first statement tree-sitter lists after
it, the others following it; comments' attachment; and specifiers in source order, declarators inside out. Its rules,
the user's, apply as TypeScript5's `Parse` applies them: the pre-pass (`_prepare`) and the converter's corrections,
extended to each place listed below.

**Where tree-sitter-c 0.24.2 departs from C.** As the user decided, "Parser discrepancies from the language spec should
be clearly enumerated and have preprocessing passes as has been done elsewhere": each place where tree-sitter-c 0.24.2,
its latest release, reads C (ISO/IEC 9899:2011, 2018 and 2024, C11, C17 and C23, with the GNU extensions 0.3 kept)
otherwise than C does is listed here, with the edition that brought the construct where it is recent, and how `parse`
handles it. Where tree-sitter cannot parse a construct, the pre-pass rewrites the text so that it can, keeping every
other character where it was, records what it rewrote (`_Prepared`), and the converter puts the construct back as the
model holds it, reading the part it rewrote from the text as written where it is an expression, a type name or an
attribute. Where tree-sitter parses it wrongly, the converter corrects it, or the pre-pass rewrites it, in every text.
The pre-pass rewrites what tree-sitter cannot parse only where it found an error, and the text is parsed again where it
rewrote any. Where tree-sitter reads what C rejects, the converter keeps it invalid syntax.

What tree-sitter-c cannot parse, which the pre-pass rewrites:

1. **`_BitInt(N)`** (C23), `unsigned _BitInt(8) x`: made a name as long, the converter making it a `bitintspecifier`
   whose `width` it reads back from the text.
2. **`typeof` of an expression** (C23; GNU's `__typeof__` and `__typeof`), `typeof(a + 1) x`, `typeof_unqual(f())`,
   which tree-sitter takes only of a type name: the operand made a name as long, the converter reading it back as an
   expression.
3. **`_Atomic(T)`** (C11), the atomic type specifier, which tree-sitter takes for the qualifier `_Atomic` and a cast:
   made a name as long, the converter making it an `atomictypespecifier` whose type it reads back.
4. **Type inference** (C23), `auto x = 1;`, `static auto y = 2;`, which tree-sitter reads with `x` a type and no
   declarator: `auto` rewritten `int`, as long, the converter making it `auto` again.
5. **Standard attributes after `struct`, `union` or `enum`** (C23), `struct [[deprecated]] s {}`, **and after an
   enumerator's name**, `A [[deprecated]] = 1`: blanked, the converter reading them back into the specifier's or the
   enumerator's `attributes`.
6. **GNU attributes after a declarator** but a function's, `int x __attribute__((aligned(16))) = 0;`: blanked, the
   converter reading them back into the `attributes` of the declarator they follow (the innermost but its pointers and
   parentheses, whose attributes print where the source wrote these).
7. **`static_assert` among a struct's or a union's members** (C11): blanked, the converter listing the declaration
   again among the members.
8. **An enumeration's underlying type of several specifiers** (C23), `enum e : unsigned char {`: made a name as long,
   the converter reading the type name back into the specifier's `base`.
9. **GNU's case ranges**, `case 1 ... 3:`: `... 3` blanked, the converter reading the range's end back into the
   label's `last`.
10. **A `switch` whose body is no compound statement**, `switch (x) case 1: f();`, which C allows: `switch` rewritten
    `while`, as long, the converter making it a `switch` again.
11. **GNU's computed `goto`**, `goto *p;`: `goto` blanked and `*` rewritten `+`, the converter making the expression
    statement it parses a `GotoStatement` whose `target` is `p`.
12. **The null directive**, `#` alone on its line: blanked, the converter listing an `otherdirective` with no name
    again where it stood.
13. **Digraphs** (C95), `<: :> <% %> %: %:%:`: rewritten as the tokens they spell, `[ ] { } # ##`, as the model holds
    them, as 0.3 normalized them.

What tree-sitter-c misreads, which the pre-pass rewrites:

14. **`_Thread_local`** (C11), which it reads as a type's name: rewritten `thread_local`, as long, the converter
    spelling it as written.
15. **`_Complex` and `_Imaginary`** (C99, kept by C11 to C23), which it reads as types' names or declarators:
    rewritten `const`, as long, the converter making each a `primitivetypespecifier` as written.

What tree-sitter-c misreads, which the converter corrects:

16. **`typeof` of a type name** (C23), `typeof(int *) x`, which it reads as a macro's type specifier: a
    `typeofspecifier` holding a `typeid`.
17. **Keywords and type names**: `_Bool`, `_Float16` to `_Float128x`, `_Decimal32` to `_Decimal128`, `__int128`,
    `__float128`, `__auto_type` and `_Noreturn`'s companions it reads as types' names, and the library's typedefs
    `size_t`, `int32_t`, `char16_t` and their like, which it reads as keywords: a `primitivetypespecifier` for a
    keyword, a `namedtypespecifier` for a name, as 0.3 had them.
18. **An unnamed bit-field**, `int : 3;`, which it reads with a missing name: a `MemberDeclarator` without a
    declarator.
19. **A label ending a block** (C23), `l: }`, `case 1: }`, which it reads with a missing `;`: a label without a
    statement.
20. **GNU attributes on a null statement**, `__attribute__((fallthrough));`, which it reads as an error and `;`: an
    `AttributedStatement`.
21. **`NULL`**, which it reads as a null constant like `nullptr`: the macro's name, a `variable`; `nullptr` (C23) a
    `constant`.
22. **A type name as a macro's argument**, `va_arg(ap, int)`, which it reads as a variable named `int`: a `typeid`,
    where the argument is a type's keyword.
23. **`defined X`**, without parentheses, read as `defined(X)`, its one form in the model (0.3's normalization); and
    GNU's obsolete designator `x: 1`, read as `.x = 1`.

What tree-sitter-c reads but C rejects, which the converter keeps invalid syntax (an `Error`, or an `error` term):

24. **Statements at file scope**, `x = 1;`, `;`, `{}`: C's translation unit holds declarations alone.
25. **C++'s linkage specification**, `extern "C" { ... }`, and **Microsoft's extensions** 0.3 did not keep: calling
    conventions (`__cdecl`), pointer modifiers (`__ptr32`, `__based`) and structured exceptions (`__try`).
26. **Literals C rejects**: an octal one with a digit 8 or 9 (`08`), a suffix C has not (`1x`, GNU's imaginary `i` once
    tree-sitter reads one), and an escape of no character (`\\x` without digits).
27. **A conditional directive's closing or continuing line where none is open**, `#endif` alone, which it reads as an
    other directive.
28. **A macro's use that is no C syntax**, `FOO(T) x;` (a macro's type specifier other than `typeof`), and a type
    specifier tree-sitter reads but C has not.

What stays as tree-sitter-c reads it:

29. **Typedef names and other names**, `T * x;` (a declaration or a product), `(T)*x` (a cast or a product),
    `typeof(x)` and `_Alignof(x)` (of a type or of an expression): which a text is depends on whether `T` names a
    type, which the declarations before it decide, outside the grammar. Read as tree-sitter decides.
30. **A conditional directive that splits a construct**, `#ifdef A` opening a block that `#endif` closes after it:
    no tree of either the directives or the statements, the preprocessor not run. Kept as tree-sitter's recovery
    leaves it: invalid syntax, as written.
31. **Trigraphs** (`??=`), which C11 and C17 replace before all else, within strings too, and C23 removed: which a
    text means depends on its edition. Kept as tree-sitter reads them, invalid syntax where they spell punctuation.
32. **What the model cannot hold** (mbse-expressions' gaps, reported to it): GNU's labels as values, `&&l`, which
    tree-sitter reads as `&(&l)`, an `error` term as written; an `asm` label on a declarator, `int x asm("r1");`, and
    `_Pragma("...")`, an `Error` as written.

Decided here *(agent, for review)*:

- **Schemas, resolved through the transaction or the store**, as TypeScript5's `Parse`: `parse(text, path, store)` for
  a bare builder.
- **What is absent is absent.** A property tree-sitter's tree gives no value, an empty list, or a flag that is false is
  not written.
- **A literal's value** is what C reads its spelling as: an integer's (an int, `0` octal, as C's grammar spells it), a
  floating literal's (a float; beyond the largest, infinity), a character's code (an int; of several characters, each
  shifted in after the one before it, as GCC reads them), a string's characters, its escapes decoded, and C23's `true`
  and `false`, with its spelling, `text`, and what the spelling encodes: `prefix`, `quote`, `base`, `separators`,
  `suffix`.
- **Positions**: each statement's, declaration's, member declaration's, directive's, comment's and error's line is
  written as its `line`; an expression has none.

Invalid syntax is kept, never raised, as the user decided for every language, as far as tree-sitter-c's recovery
allows; what the pre-pass rewrites is no longer invalid, and what remains after it is:

- **Where a statement, a declaration or a member declaration stands**, an `Error` (`Programs.C.Error`), with its line:
  tree-sitter skipped it (`ERROR`), or it holds invalid syntax no term holds (a `MISSING` token, as in `if (a {}`), or
  it is a construct the converter cannot hold. Its `text` is as written, before the pre-pass; its `body`, the
  statements tree-sitter read within it, each block's statements among them, flattened.
- **Within an expression**, the dialect's `error` term, the innermost that holds an `ERROR` or a construct the dialect
  cannot hold: its `text` as written, its `terms` each `C` expression tree-sitter read within it.
- **`MISSING`**: where an expression stands, the dialect's `missing` term, its `kind` the node type tree-sitter
  expected; a token makes what holds it invalid as above.
- **`ParseError`** is raised only for text that is no text, a lone surrogate, which no encoding writes.
"""

from __future__ import annotations

import bisect
import math
import re
from collections.abc import Callable
from typing import Any

import tree_sitter_c
from mbse.Expressions.C.Expressions.Expressions import SUFFIXES
from mbse.Schemas.Framework import Schemas
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from ..Framework.Model import WORKSPACE

__all__ = ["parse", "ParseError", "WORKSPACE"]

_PARSER = _TSParser(_Grammar(tree_sitter_c.language()))

_LANGUAGE = "Programs.C"
_TERM = "Expressions.Framework.Term"  # the framework's union of dialects: a condition's, an item's, a recovered term's

# C's keywords that name types, as 0.3's `PrimitiveKeyword` lists them, and GNU's `__auto_type`
_PRIMITIVES = {
    "void", "char", "bool", "_Bool", "short", "int", "long", "signed", "unsigned", "float", "double", "_Complex",
    "_Imaginary", "_Decimal32", "_Decimal64", "_Decimal128", "_Float16", "_Float32", "_Float64", "_Float128",
    "_Float32x", "_Float64x", "_Float128x", "__int128", "__float128", "__auto_type"}
_CV = {"const", "volatile", "restrict", "_Atomic", "__restrict", "__restrict__", "_Nonnull", "_Nullable", "__const",
       "__volatile__"}
_TYPEOFS = ("typeof", "typeof_unqual", "__typeof__", "__typeof")
_ATTRIBUTES = ("__attribute__", "__attribute")
_DIGRAPHS = {"<:": "[ ", ":>": "] ", "<%": "{ ", "%>": "} ", "%:": "# ", "%:%:": "## "}
_SPECIFIER_NODES = ("struct_specifier", "union_specifier", "enum_specifier")
_ALTERNATIVE_DIRECTIVES = ("#else", "#elif", "#endif", "#elifdef", "#elifndef")


class _Invalid(Exception):
    """A construct the converter cannot hold, which it keeps as invalid syntax: an `Error` or an `error` term."""


# --- Source text ---


class _Source:
    """The text being parsed, as given and as tree-sitter parses it (`data`, which is `cleaned` in UTF-16), with
    conversions from tree-sitter's byte offsets to character offsets and back, and from character offsets to lines. The
    cleaned text has the same characters as the text, but for those the pre-pass rewrote."""

    def __init__(self, text: str, cleaned: str | None = None):
        self.text = text
        self.data = (text if cleaned is None else cleaned).encode("utf-16-le")
        self._chars: list[int] | None = None
        self._bytes: list[int] | None = None
        if len(self.data) != 2 * len(text):  # a character beyond the Basic Multilingual Plane takes two units
            self._chars, self._bytes = [0] * (len(self.data) // 2 + 1), []
            at = 0
            for i, ch in enumerate(text if cleaned is None else cleaned):
                self._bytes.append(2 * at)
                for _ in range(len(ch.encode("utf-16-le")) // 2):
                    self._chars[at] = i
                    at += 1
            self._chars[at] = len(text)
            self._bytes.append(2 * at)

    def offset(self, byte: int) -> int:
        return byte // 2 if self._chars is None else self._chars[byte // 2]

    def byte(self, offset: int) -> int:
        return 2 * offset if self._bytes is None else self._bytes[offset]

    def line(self, offset: int) -> int:
        return self.text.count("\n", 0, offset) + 1


# --- The pre-pass: what tree-sitter-c cannot parse, or misreads ---


class _Prepared:
    """What the pre-pass rewrote, by character offset: keywords it respelled (`_Thread_local`, `_Complex`, an inferred
    declaration's `auto`, a `switch`), constructs it made names (`_BitInt(N)`, `typeof`'s operand, `_Atomic(T)`, an
    enumeration's underlying type), attributes it blanked, by what they follow, the ends of case ranges, computed
    `goto`s, and the items it blanked where they are listed (null directives, a struct's `static_assert`s)."""

    def __init__(self) -> None:
        self.keywords: dict[int, str] = {}  # by its offset: the keyword as written
        self.names: dict[int, tuple[str, int, int]] = {}  # by the name's offset: what it stands for, and the span of
        # the text to read back (`bitint`, its width; `typeof`, its operand; `atomic` and `base`, a type name)
        self.attributes: dict[int, list[tuple[int, int]]] = {}  # by the offset of the keyword or the enumerator's name
        self.after: dict[int, list[tuple[int, int]]] = {}  # GNU attributes, by where the declarator before them ends
        self.ranges: dict[int, tuple[int, int]] = {}  # by the `case`: the span of its range's end
        self.gotos: dict[int, int] = {}  # by the `+` that was `*`: the `goto`'s offset
        self.items: list[tuple[int, int, int]] = []  # an item blanked: its offset, and the span to read back (a null
        # directive's is empty)


_PUNCTUATORS = sorted(["%:%:", "...", "<<=", ">>=", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
                       "*=", "/=", "%=", "+=", "-=", "&=", "^=", "|=", "##", "<:", ":>", "<%", "%>", "%:"],
                      key=len, reverse=True)
_NUMBER = re.compile(r"\.?[0-9](?:[eEpP][+-]|'[0-9A-Za-z_]|[0-9A-Za-z_.])*")
_WORD = re.compile(r"[^\W\d]\w*|\$[\w$]*")
_QUOTED = re.compile(r"""(?:u8|[uUL])?(?:'(?:\\[\s\S]|[^'\\\n])*'?|"(?:\\[\s\S]|[^"\\\n])*"?)""")


def _lex(text: str) -> tuple[list[tuple[int, int, str]], list[tuple[int, int]]]:
    """The tokens of `text`, as character spans and their text, without comments and directives, and the spans of its
    directives, each from its `#` (or `%:`) to its line's end, lines continued with `\\` among it."""
    tokens: list[tuple[int, int, str]] = []
    directives: list[tuple[int, int]] = []
    i, n, line_start = 0, len(text), True
    while i < n:
        ch = text[i]
        if ch == "\n":
            line_start, i = True, i + 1
        elif ch in " \t\r\f\v" or text.startswith("\\\n", i) or text.startswith("\\\r\n", i):
            i += 1 if ch != "\\" else 2
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 2 if text.startswith("\\\n", i) else 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif line_start and (ch == "#" or text.startswith("%:", i)):
            start = i
            while i < n and text[i] != "\n":
                if text.startswith("/*", i):  # a comment within a directive may span lines
                    end = text.find("*/", i + 2)
                    i = n if end < 0 else end + 2
                else:
                    i += 2 if text[i] == "\\" and i + 1 < n else 1
            directives.append((start, i))
        else:
            line_start = False
            match = _QUOTED.match(text, i) if ch in "'\"uUL" else None
            if match is not None and match.group():
                tokens.append((i, match.end(), match.group()))
                i = match.end()
                continue
            match = _NUMBER.match(text, i) or _WORD.match(text, i)
            if match is not None:
                tokens.append((i, match.end(), match.group()))
                i = match.end()
                continue
            word = next((p for p in _PUNCTUATORS if text.startswith(p, i)), ch)
            tokens.append((i, i + len(word), word))
            i += len(word)
    return tokens, directives


def _closing(tokens: list[tuple[int, int, str]], i: int) -> int:
    """The index of the bracket that closes the one at `tokens[i]`, or of the last token if none does."""
    depth = 0
    for j in range(i, len(tokens)):
        if tokens[j][2] in ("(", "[", "{", "<:", "<%"):
            depth += 1
        elif tokens[j][2] in (")", "]", "}", ":>", "%>"):
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _braces(tokens: list[tuple[int, int, str]]) -> list[str]:
    """Each token's innermost brace: `enum` within an enumeration's body, `struct` within a struct's or a union's,
    `block` within any other braces, `` outside them."""
    out, stack = [], []
    for i, (_, _, word) in enumerate(tokens):
        out.append(stack[-1] if stack else "")
        if word in ("{", "<%"):
            kind, j = "block", i - 1
            while j >= 0 and tokens[j][2] not in (";", "{", "}", "=", ")", "<%", "%>"):
                if tokens[j][2] in ("struct", "union", "enum"):
                    kind = "enum" if tokens[j][2] == "enum" else "struct"
                    break
                j -= 1
            stack.append(kind)
        elif word in ("}", "%>") and stack:
            stack.pop()
    return out


def _parsed_type(root: _TS, source: _Source, offset: int) -> bool:
    """Whether tree-sitter read the `typeof` at `offset` as a macro's type specifier, of a type name, without error."""
    node = root.descendant_for_byte_range(source.byte(offset), source.byte(offset))
    while node is not None and node.type not in ("macro_type_specifier", "ERROR", "translation_unit"):
        node = node.parent
    return node is not None and node.type == "macro_type_specifier" and not node.has_error


def _inferred(tokens: list[tuple[int, int, str]], i: int) -> bool:
    """Whether the `auto` at `tokens[i]` begins a declaration whose type is inferred (C23): no type's keyword follows it,
    but qualifiers and storage classes, before a name and its `=`."""
    j = i + 1
    while j < len(tokens) and tokens[j][2] in (_CV | {"static", "constexpr", "register", "thread_local",
                                                      "_Thread_local", "extern"}):
        j += 1
    return (j + 1 < len(tokens) and _WORD.fullmatch(tokens[j][2]) is not None and tokens[j][2] not in _PRIMITIVES
            and tokens[j][2] not in ("struct", "union", "enum") and tokens[j + 1][2] == "=")


def _prepare(text: str, root: _TS, source: _Source) -> tuple[str, _Prepared]:
    """The text with the constructs tree-sitter-c cannot parse, or misreads, rewritten, and what was rewritten. What it
    misreads is rewritten wherever it stands; what it cannot parse only where tree-sitter found an error."""
    found = _Prepared()
    chars = list(text)
    broken = root.has_error
    tokens, directives = _lex(text)

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            chars[p] = "\n" if text[p] == "\n" else " "

    def named(start: int, end: int) -> None:
        for p in range(start, end):
            chars[p] = "\n" if text[p] == "\n" else "_"

    def respell(start: int, word: str, spelled: str) -> None:
        chars[start:start + len(word)] = list(spelled.ljust(len(word)))
        found.keywords[start] = word

    for start, end in directives:
        line = text[start:end]
        if broken and _directive_name(line) == "" and not line.lstrip("#%: \t").startswith(("/", "\\")):
            blank(start, start + (1 if line[0] == "#" else 2))  # the null directive, `#` alone
            found.items.append((start, start, start))
        elif line.startswith("%:"):
            chars[start:start + 2] = list("# ")
    braces = _braces(tokens)
    for i, (start, end, word) in enumerate(tokens):
        after = tokens[i + 1][2] if i + 1 < len(tokens) else ""
        before = tokens[i - 1][2] if i > 0 else ""
        # What tree-sitter-c misreads
        if word == "_Thread_local":
            respell(start, word, "thread_local")
        elif word in ("_Complex", "_Imaginary"):
            respell(start, word, "const")
        if not broken:
            continue
        # What tree-sitter-c cannot parse
        if word in _DIGRAPHS:
            chars[start:end] = list(_DIGRAPHS[word])
        elif word in ("_BitInt", "_Atomic") and after == "(":
            close = _closing(tokens, i + 1)
            named(start, tokens[close][1])
            found.names[start] = ("bitint" if word == "_BitInt" else "atomic", tokens[i + 1][1], tokens[close][0])
        elif word in _TYPEOFS and after == "(" and not _parsed_type(root, source, start):
            close = _closing(tokens, i + 1)
            if close > i + 2:
                named(tokens[i + 2][0], tokens[close][0])
                found.names[tokens[i + 2][0]] = ("typeof", tokens[i + 2][0], tokens[close][0])
        elif word == "auto" and _inferred(tokens, i):
            respell(start, word, "int")
        elif word in ("struct", "union", "enum") and after == "[" and i + 2 < len(tokens) and tokens[i + 2][2] == "[":
            j = i + 1
            while j < len(tokens) and tokens[j][2] == "[" and j + 1 < len(tokens) and tokens[j + 1][2] == "[":
                close = _closing(tokens, j)
                found.attributes.setdefault(start, []).append((tokens[j][0], tokens[close][1]))
                blank(tokens[j][0], tokens[close][1])
                j = close + 1
        elif braces[i] == "enum" and before in ("{", ",", "<%") and after == "[" and i + 2 < len(tokens) and (
                tokens[i + 2][2] == "["):
            close = _closing(tokens, i + 1)
            found.attributes.setdefault(start, []).append((tokens[i + 1][0], tokens[close][1]))
            blank(tokens[i + 1][0], tokens[close][1])
        elif word in _ATTRIBUTES and after == "(" and (_WORD.fullmatch(before) or before == "]") and (
                before not in _PRIMITIVES | _CV | {"struct", "union", "enum"}):
            close = _closing(tokens, i + 1)
            following = tokens[close + 1][2] if close + 1 < len(tokens) else ""
            if following in ("=", ",", ";", ":"):
                found.after.setdefault(tokens[i - 1][1], []).append((start, tokens[close][1]))
                blank(start, tokens[close][1])
        elif word in ("static_assert", "_Static_assert") and braces[i] == "struct":
            stop = next((j for j in range(i, len(tokens)) if tokens[j][2] == ";"), len(tokens) - 1)
            found.items.append((start, start, tokens[stop][1]))
            blank(start, tokens[stop][1])
        elif word == "enum":
            j = i + 1
            if j < len(tokens) and _WORD.fullmatch(tokens[j][2]):
                j += 1
            if j < len(tokens) and tokens[j][2] == ":":
                stop = next((k for k in range(j + 1, len(tokens)) if tokens[k][2] in ("{", ";", "<%")), len(tokens))
                if stop > j + 2 or stop == j + 2 and tokens[j + 1][2] not in _PRIMITIVES:
                    first, last = tokens[j + 1][0], tokens[stop - 1][1]  # made `int`, as long: tree-sitter-c takes
                    blank(first, last)  # a keyword alone there
                    chars[first:first + 3] = list("int")
                    found.names[first] = ("base", first, last)
        elif word == "case":
            depth, j, last = 0, i + 1, None
            while j < len(tokens):
                inner = tokens[j][2]
                depth += 1 if inner in ("(", "[", "?") else -1 if inner in (")", "]") else 0
                if inner == ":" and depth == 0 or inner in (";", "{", "}"):
                    break
                if inner == ":":
                    depth -= 1  # a conditional's `:`
                if inner == "..." and depth == 0:
                    last = j
                j += 1
            if last is not None and j < len(tokens) and tokens[j][2] == ":":
                found.ranges[start] = (tokens[last + 1][0], tokens[j - 1][1])
                blank(tokens[last][0], tokens[j - 1][1])
        elif word == "switch" and after == "(":
            close = _closing(tokens, i + 1)
            if close + 1 < len(tokens) and tokens[close + 1][2] not in ("{", "<%"):
                respell(start, word, "while")
        elif word == "goto" and after == "*":
            blank(start, end)
            chars[tokens[i + 1][0]] = "+"
            found.gotos[tokens[i + 1][0]] = start
    return "".join(chars), found


def _directive_name(line: str) -> str:
    """A directive's name, the word after its `#`: `` for the null directive."""
    match = re.match(r"(?:#|%:)[ \t]*(\w*)", line)
    return match.group(1) if match is not None else ""


# --- Literals ---


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "a": "\a", "e": "\x1b", "\\": "\\",
            "'": "'", '"': '"', "?": "?"}
_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]*|[0-7]{1,3}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[\s\S])")
_INTEGER = re.compile(r"(0[xX](?:'?[0-9a-fA-F])+|0[bB](?:'?[01])+|0(?:'?[0-7])*|[1-9](?:'?[0-9])*)"
                      r"([A-Za-z]*)")
_FLOATING = re.compile(r"((?:[0-9](?:'?[0-9])*)?\.(?:[0-9](?:'?[0-9])*)?(?:[eE][+-]?[0-9]+)?|[0-9](?:'?[0-9])*[eE][+-]?"
                       r"[0-9]+|0[xX](?:[0-9a-fA-F](?:'?[0-9a-fA-F])*)?\.?(?:[0-9a-fA-F](?:'?[0-9a-fA-F])*)?[pP][+-]?"
                       r"[0-9]+)([A-Za-z0-9]*)")


def _unescape(body: str) -> str:
    """A character's or a string's characters, of the text between its quotes: its escapes decoded. ValueError for an
    escape of no character, `\\x` without digits."""
    def one(match: re.Match[str]) -> str:
        escape = match.group(1)
        if escape[0] == "x":
            if len(escape) == 1:
                raise ValueError(escape)
            return chr(int(escape[1:], 16) % 0x110000)
        if escape[0] in "01234567":
            return chr(int(escape, 8))
        if escape[0] in "uU" and len(escape) > 1:
            return chr(int(escape[1:], 16))
        if escape in ("\n", "\r"):  # a line continued
            return ""
        return _ESCAPES.get(escape, escape)
    return _ESCAPE.sub(one, body.replace("\\\r\n", ""))


def _number(text: str) -> _Node:
    """A number's literal: its value, an int or a float, its spelling, and what the spelling encodes. `_Invalid` for one
    C rejects: an octal one with a digit 8 or 9, or a suffix C has not."""
    floating = _FLOATING.fullmatch(text)
    integer = _INTEGER.fullmatch(text)
    if integer is not None and (floating is None or not integer.group(2) or SUFFIXES[int].fullmatch(integer.group(2))):
        digits, suffix = integer.group(1).replace("'", ""), integer.group(2)
        base = {"0x": 16, "0X": 16, "0b": 2, "0B": 2}.get(digits[:2], 8 if digits.startswith("0") else 10)
        if not SUFFIXES[int].fullmatch(suffix):
            raise _Invalid(text)
        value = int(digits[2:] if base in (2, 16) else digits, base)
        return _Node("literal", value=_scalar(value), text=text, base=base, separators="'" in text,
                     suffix=suffix or None)
    if floating is None or floating.group(2) and not SUFFIXES[float].fullmatch(floating.group(2)):
        raise _Invalid(text)
    digits = floating.group(1).replace("'", "")
    try:
        value = float.fromhex(digits) if digits[:2] in ("0x", "0X") else float(digits)
    except OverflowError:  # beyond the largest: C reads it as infinity
        value = math.inf
    return _Node("literal", value=_scalar(value), text=text, separators="'" in text, suffix=floating.group(2) or None)


def _scalar(value: Any) -> Callable[[Any], Any]:
    """The writer of a literal's value, a scalar."""
    return lambda p: p.as_scalar(value)


# --- The tree, as written ---


class _Node:
    """A node of the tree, as the transaction writes it: the tag of its kind's branch (`binaryexpression`,
    `ifstatement`), its properties, read and set as attributes, absent ones read as None, and, where it stands for the
    framework's union of dialects, the dialect's branch (`c`, `c_types`, `c_preprocessor`)."""

    __slots__ = ("branch", "fields", "dialect")

    def __init__(self, branch: str, /, **fields: Any):
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "dialect", "c")

    def __getattr__(self, name: str) -> Any:
        return self.fields.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self.fields[name] = value

    def of(self, dialect: str) -> _Node:
        object.__setattr__(self, "dialect", dialect)
        return self


class _Branch:
    """A branch of a union that names what it holds rather than its kind: a `for`'s `initializer` (`expression`)."""

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
    tag, dialect = value.branch, value.dialect

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
        if schema.name == _TERM:  # the framework's union of dialects: the node's dialect's branch
            return getattr(visitor, dialect)(write)
        return getattr(visitor, tag)(record)

    return write


# --- The converter ---


class _Converter:
    """Rewrites a tree-sitter-c tree into statements and terms. `shift` and `origin` place a tree parsed from a part of
    the text: its offsets are `shift` past those of the part, and its text as written is `origin`'s."""

    def __init__(self, source: _Source, prepared: _Prepared, shift: int = 0, origin: _Source | None = None):
        self.source, self.pre, self.shift, self.origin = source, prepared, shift, origin or source
        self.consumed: set[int] = set()
        self.hoisted: list[_Node] = []  # what a label that is a statement's body took beyond its statement

    # Helpers

    def local(self, ts: _TS) -> int:
        """Where `ts` starts in the text this converter parsed, as the pre-pass records it."""
        return self.source.offset(ts.start_byte)

    def at(self, ts: _TS) -> int:
        return self.shift + self.local(ts)

    def text(self, ts: _TS) -> str:
        return self.source.data[ts.start_byte:ts.end_byte].decode("utf-16-le")

    def written(self, ts: _TS) -> str:
        """The text of `ts` as the source wrote it, before the pre-pass rewrote any of it."""
        return self.origin.text[self.at(ts):self.shift + self.source.offset(ts.end_byte)]

    def line(self, ts: _TS) -> int:
        return self.origin.line(self.at(ts))

    def new(self, ts: _TS, branch: str, **fields: Any) -> _Node:
        """A statement, declaration or member of the kind `branch`, with the line where `ts` starts."""
        return _Node(branch, line=self.line(ts), **fields)

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        """The named children of `ts`, without comments and what tree-sitter skipped (`ERROR`), which is never taken
        as an operand: what holds it is invalid as a whole."""
        return [c for c in ts.children if c.is_named and c.type not in ("comment", "ERROR")]

    @staticmethod
    def field(ts: _TS, name: str) -> _TS | None:
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

    def identifier(self, ts: _TS) -> _Node:
        return _Node("identifier", spelling=self.text(ts))

    def reparsed(self, prefix: str, start: int, end: int, suffix: str) -> tuple[_Converter, _TS]:
        """The text written between `start` and `end`, offsets in the text this converter parsed, between `prefix` and
        `suffix`, parsed (and pre-passed) as a translation unit of its own: the converter that places it where the
        text was written, and the unit's tree."""
        source, prepared, tree = _parsed(prefix + self.source.text[start:end] + suffix)
        return _Converter(source, prepared, self.shift + start - len(prefix), self.origin), tree.root_node

    # Invalid syntax

    def unconsumed(self, ts: _TS) -> bool:
        """Whether `ts` holds invalid syntax (an `ERROR` or a `MISSING` node) below it that nothing made holds: no
        `error` or `missing` term, and no statement, which keeps its own."""
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
        """An expression that is invalid syntax as a whole: an `error` term, its text as written, and the terms
        recovered within it, each expression tree-sitter read there, in source order."""
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
            if c.type == "compound_statement":
                out += self.listed(c.children, self.statement, c.children[0])
            elif c.type in self.STATEMENTS or c.type in self.DECLARATIONS and c.type != "ERROR":
                out.append(self.statement(c))
            else:
                out += self.recovered(c)
        return out

    def error(self, ts: _TS) -> _Node:
        """Invalid syntax where a statement, a declaration or a member stands: an `Error`, its text as written, and the
        statements recovered within it."""
        self.consumed.add(ts.id)
        return self.new(ts, "error", text=self.written(ts), body=self.recovered(ts))

    def guarded(self, ts: _TS, convert: Callable[[_TS], Any]) -> Any:
        """What `convert` makes of `ts`, a statement, a declaration or a member, or, where it is invalid syntax, an
        `Error`: tree-sitter skipped it (`ERROR`) or found it incomplete, or it holds what no `error` or `missing` term
        does, or it is a construct the converter cannot hold."""
        self.consumed.add(ts.id)
        try:
            made = convert(ts)
            if not (ts.has_error and self.unconsumed(ts)):
                return made
        except (Exception if ts.has_error else _Invalid):  # what tree-sitter recovered, shaped as no grammar rule is
            pass
        return self.error(ts)

    def term(self, ts: _TS, methods: dict[str, Callable[[_Converter, _TS], Any]]) -> _Node:
        """The term of the expression `ts`, by `methods`: a `missing` term where tree-sitter expected one and found
        none, an `error` term where `ts` is invalid syntax (`invalid`), else its kind's."""
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

    # Lists of statements, declarations and members, with their comments

    def listed(self, nodes: list[_TS], convert: Callable[[_TS], Any], header: _TS | None = None) -> list[Any]:
        """The items among `nodes`, up to a closing brace, converted, and the comments between them: a comment is
        trailing on the line where the item before it ends, or `header` for the first. A struct's, a union's or an
        enumeration's specifier and the `;` after it are one declaration; a `case` label's statements are its first
        and those after it; GNU's attributes tree-sitter cannot read before `;` attribute it; and what the pre-pass
        blanked among them is listed again."""
        out: list[Any] = []
        previous = header
        kids = [n for n in nodes if not n.is_missing]
        whole = bool(nodes) and nodes[0].parent is not None and nodes[0].parent.type == "translation_unit"
        limit = len(self.source.text) if whole or not nodes else self.source.offset(nodes[-1].end_byte)
        i = 0
        while i < len(kids):
            ts = kids[i]
            i += 1
            out += self.blanked(previous, self.local(ts))
            if ts.type == "comment":
                out.append(self.comment(ts, previous))
            elif ts.type in _SPECIFIER_NODES and i < len(kids) and kids[i].type == ";":
                out.append(self.guarded(ts, lambda t: self.new(t, "simpledeclaration", specifiers=self.specifier(t))))
                ts = kids[i]
                i += 1
            elif ts.type == "case_statement":
                made, i = self.case(kids, i - 1, convert)
                out += made
                ts = kids[i - 1]
            elif ts.type == "ERROR" and [c.type for c in ts.children] == ["attribute_specifier"] and i < len(kids) and (
                    kids[i].type == "expression_statement"):
                self.consumed.add(ts.id)
                attributes = [self.attribute(ts.children[0])]
                out.append(self.new(ts, "attributedstatement", attributes=attributes, statement=convert(kids[i])))
                ts = kids[i]
                i += 1
            elif ts.is_named:
                outer, self.hoisted = self.hoisted, []
                out.append(convert(ts))
                out += self.hoisted
                self.hoisted = outer
            elif ts.type == "}":
                return out
            else:
                continue
            previous = ts
        return out + self.blanked(previous, limit)

    def blanked(self, previous: _TS | None, end: int) -> list[_Node]:
        """The items the pre-pass blanked after `previous` and before `end`: null directives, and the `static_assert`s
        of a struct's members, read back."""
        start = 0 if previous is None else self.source.offset(previous.end_byte)
        out = []
        for at, first, last in self.pre.items:
            if start <= at < end:
                if first == last:
                    made = _Node("otherdirective").of("c_preprocessor")
                    out.append(_Node("directive", line=self.origin.line(self.shift + at), directive=made))
                    continue
                converter, root = self.reparsed("", first, last, "")
                out += [converter.statement(c) for c in converter.named(root)]
        return out

    def comment(self, ts: _TS, previous: _TS | None) -> _Node:
        """A comment, its text without its delimiters: trailing where nothing but blanks is between it and the end of
        `previous`, in the text as written."""
        text = self.written(ts)
        block = text.startswith("/*")
        trailing = previous is not None and "\n" not in self.origin.text[
            self.shift + self.source.offset(previous.end_byte):self.at(ts)]
        return self.new(ts, "comment", text=text[2:-2] if block else text[2:].rstrip("\r"), block=block,
                        trailing=trailing)

    def case(self, nodes: list[_TS], i: int, convert: Callable[[_TS], Any]) -> tuple[list[Any], int]:
        """The case or default label `nodes[i]`, and the index of the node after what it took: tree-sitter lists the
        statements after a label as its children; here it labels the first, and the others follow it, the comments
        before the first among them. A label without statements labels the next label, or ends its block (C23)."""
        ts = nodes[i]
        i += 1
        self.consumed.add(ts.id)
        value = self.field(ts, "value")
        colon = next(c for c in ts.children if c.type == ":")
        held = self.listed(ts.children[ts.children.index(colon) + 1:], convert, colon)
        first = next((k for k, item in enumerate(held) if item.branch != "comment"), None)
        statement = None
        if first is not None:
            statement = held.pop(first)
        elif i < len(nodes) and nodes[i].type == "case_statement":
            nested, i = self.case(nodes, i, convert)
            statement, held = nested[0], held + nested[1:]
        for comment in held[:first]:
            comment.trailing = False
        try:
            if any(c.type == "ERROR" or c.is_missing for c in ts.children[:ts.children.index(colon)]):
                raise _Invalid(ts.type)
            if value is None:
                label = self.new(ts, "defaultstatement", statement=statement)
            else:
                label = self.new(ts, "casestatement", value=self.expression(value), statement=statement)
                span = self.pre.ranges.get(self.local(ts))
                if span is not None:
                    label.last = self.part_expression(*span)
        except _Invalid:
            return [self.new(ts, "error", text=self.written(ts), body=[s for s in [statement, *held] if s])], i
        return [label, *held], i

    def case_body(self, ts: _TS) -> _Node:
        """A label that is a statement's body, `switch (x) case 1: f();`: tree-sitter lists every statement after it
        in its block as its own, which follow the statement that holds it instead (`hoisted`)."""
        label, *rest = self.case([ts], 0, self.statement)[0]
        self.hoisted += rest
        return label

    # Translation units, blocks and statements

    def unit(self, ts: _TS) -> list[_Node]:
        """A translation unit's declarations; a statement other than a declaration, which C admits only within a
        function, is invalid syntax there."""
        return self.listed(ts.children, self.external)

    def external(self, ts: _TS) -> _Node:
        if ts.type == "attributed_statement" and self.named(ts)[-1].type != "expression_statement" or (
                ts.type == "attributed_statement" and self.named(self.named(ts)[-1])):
            return self.error(ts)
        if ts.type in self.STATEMENTS and ts.type not in ("expression_statement", "attributed_statement") or (
                ts.type == "expression_statement" and not self.asm_statement(ts)):
            return self.error(ts)
        return self.statement(ts)

    def asm_statement(self, ts: _TS) -> bool:
        """Whether an expression statement is a declaration: `asm(...)`, or `_Static_assert(x)` read as a call."""
        kids = self.named(ts)
        return len(kids) == 1 and (kids[0].type == "gnu_asm_expression" or self.asserting(kids[0]))

    def block(self, ts: _TS) -> _Node:
        return self.new(ts, "compoundstatement", body=self.listed(ts.children, self.statement, ts.children[0]))

    def statement(self, ts: _TS) -> _Node:
        return self.guarded(ts, self.convert)

    def convert(self, ts: _TS) -> _Node:
        """The statement or declaration `ts`, with its line."""
        method = self.STATEMENTS.get(ts.type) or self.DECLARATIONS.get(ts.type)
        if method is None:
            raise _Invalid(ts.type)
        made = method(self, ts)
        made.line = self.line(ts)
        return made

    def expression_statement(self, ts: _TS) -> _Node:
        inner = self.named(ts)
        if not inner:
            return _Node("expressionstatement")
        if inner[0].type == "gnu_asm_expression":
            return self.asm(inner[0])
        if self.asserting(inner[0]):  # `_Static_assert(x);`, which tree-sitter-c reads as a call
            function, arguments = self.require(inner[0], "function"), self.named(self.require(inner[0], "arguments"))
            return _Node("staticassertdeclaration", keyword=self.text(function),
                         condition=self.expression(arguments[0]),
                         message=self.expression(arguments[1]) if len(arguments) == 2 else None)
        goto = self.pre.gotos.get(self.local(inner[0]))
        if goto is not None:  # `goto *p;`, which the pre-pass made `+p;`
            return _Node("gotostatement", target=self.expression(self.require(inner[0], "argument")))
        return _Node("expressionstatement", expression=self.expression(inner[0]))

    def asserting(self, ts: _TS) -> bool:
        """Whether `ts` is a call of `static_assert` or `_Static_assert` with one argument or two: a declaration."""
        if ts.type != "call_expression" or self.require(ts, "function").type != "identifier":
            return False
        return self.text(self.require(ts, "function")) in ("static_assert", "_Static_assert") and (
            len(self.named(self.require(ts, "arguments"))) in (1, 2))

    def asm(self, ts: _TS) -> _Node:
        made = _Node("asmdeclaration", keyword=self.text(ts.children[0]),
                     template=self.expression(self.require(ts, "assembly_code")))
        for q in self.named(ts):
            if q.type == "gnu_asm_qualifier":
                setattr(made, self.text(q).strip("_"), True)

        def operands(name: str) -> list[_Node]:
            found = self.field(ts, name)
            out = []
            for o in self.fields(found, "operand") if found is not None else []:
                symbol = self.field(o, "symbol")
                out.append(_Node("asmoperand", name=self.identifier(symbol) if symbol is not None else None,
                                 constraint=self.expression(self.require(o, "constraint")),
                                 value=self.expression(self.require(o, "value"))))
            return out

        made.outputs, made.inputs = operands("output_operands"), operands("input_operands")
        clobbers, labels = self.field(ts, "clobbers"), self.field(ts, "goto_labels")
        made.clobbers = [self.expression(c) for c in self.named(clobbers)] if clobbers is not None else []
        made.labels = [self.identifier(c) for c in self.named(labels)] if labels is not None else []
        return made

    def condition(self, ts: _TS) -> _Node:
        """A parenthesized condition's expression: the parentheses are the statement's."""
        return self.expression(self.named(ts)[0])

    def if_statement(self, ts: _TS) -> _Node:
        made = _Node("ifstatement", condition=self.condition(self.require(ts, "condition")),
                     consequence=self.statement(self.require(ts, "consequence")))
        alternative = self.field(ts, "alternative")
        if alternative is not None:
            made.alternative = self.statement(self.named(alternative)[0])
        return made

    def while_statement(self, ts: _TS) -> _Node:
        kind = "switchstatement" if self.pre.keywords.get(self.local(ts)) == "switch" else "whilestatement"
        return _Node(kind, condition=self.condition(self.require(ts, "condition")),
                     body=self.statement(self.require(ts, "body")))

    def for_statement(self, ts: _TS) -> _Node:
        made = _Node("forstatement", body=self.statement(self.require(ts, "body")))
        initializer, condition, update = (self.field(ts, n) for n in ("initializer", "condition", "update"))
        if initializer is not None:
            made.initializer = self.declaration(initializer) if initializer.type == "declaration" else _Branch(
                "expression", self.expression(initializer))
        if condition is not None:
            made.condition = self.expression(condition)
        if update is not None:
            made.increment = self.expression(update)
        return made

    def labeled(self, ts: _TS) -> _Node:
        label = self.require(ts, "label")
        body = [c for c in self.named(ts) if c.id != label.id]
        made = _Node("labeledstatement", label=self.identifier(label))
        statement = body[0]
        if statement.type == "expression_statement" and [c.is_missing for c in statement.children] == [True]:
            self.consumed.add(statement.children[0].id)  # a label that ends its block (C23), read with a missing `;`
        else:
            made.statement = self.statement(statement)
        return made

    def attributed(self, ts: _TS) -> _Node:
        parts = self.named(ts)
        if parts[-1].type == "expression_statement" and not self.named(parts[-1]):
            # `[[fallthrough]];`, which tree-sitter-c reads as an empty statement with attributes: a declaration (C23)
            return _Node("attributedeclaration", attributes=[self.attribute(a) for a in parts[:-1]])
        return _Node("attributedstatement", attributes=[self.attribute(a) for a in parts[:-1]],
                     statement=self.statement(parts[-1]))

    STATEMENTS: dict[str, Callable[[Any, _TS], Any]] = {}

    # Declarations

    def specifiers(self, ts: _TS, attributes: list[Any] | None = None) -> list[_Node]:
        """The specifiers of a declaration-like node, in source order. Attributes before the first specifier go to
        `attributes` when given."""
        out: list[_Node] = []
        type_ = self.field(ts, "type")
        for c in ts.children:
            if type_ is not None and c.id == type_.id:
                out += self.specifier(c)
            elif not c.is_named and c.type in ("typedef", "__extension__"):
                out.append(_Node("declspecifier", keyword=c.type))
            elif c.type in ("attribute_declaration", "attribute_specifier", "ms_declspec_modifier"):
                (attributes if attributes is not None and not out else out).append(self.attribute(c))
            elif c.type in ("storage_class_specifier", "type_qualifier"):
                out += self.specifier(c)
            elif c.type == "ms_call_modifier":
                raise _Invalid(c.type)
        return out

    def specifier(self, ts: _TS) -> list[_Node]:
        """The specifiers one tree-sitter node spells."""
        kind, spelling = ts.type, self.text(ts)
        if kind in ("primitive_type", "type_identifier"):
            name = self.pre.names.get(self.local(ts))
            if name is not None:
                return [self.named_specifier(ts, *name)]
            if spelling in _PRIMITIVES:
                return [_Node("primitivetypespecifier", keyword=spelling)]
            return [_Node("namedtypespecifier", name=self.identifier(ts))]
        if kind == "sized_type_specifier":
            out: list[_Node] = []
            for c in ts.children:
                out += [_Node("primitivetypespecifier", keyword=c.type)] if not c.is_named else self.specifier(c)
            return out
        if kind in ("struct_specifier", "union_specifier"):
            return [self.class_specifier(ts)]
        if kind == "enum_specifier":
            return [self.enum_specifier(ts)]
        if kind == "macro_type_specifier":
            return [self.typeof(ts)]
        if kind == "storage_class_specifier":
            keyword = self.pre.keywords.get(self.local(ts), spelling)
            return [_Node("declspecifier", keyword=keyword)]
        if kind == "type_qualifier":
            inner = self.named(ts)
            if inner:
                return [self.attribute(inner[0])]
            keyword = self.pre.keywords.get(self.local(ts), spelling)
            if keyword in ("_Complex", "_Imaginary"):
                return [_Node("primitivetypespecifier", keyword=keyword)]
            if keyword in _CV:
                return [_Node("cvqualifier", keyword=keyword)]
            return [_Node("declspecifier", keyword=keyword)]  # `_Noreturn`, `noreturn`, `inline`, `constexpr`
        raise _Invalid(kind)

    def named_specifier(self, ts: _TS, kind: str, start: int, end: int) -> _Node:
        """What the pre-pass made a name: `_BitInt(N)`, `_Atomic(T)`, an enumeration's underlying type."""
        if kind == "bitint":
            return _Node("bitintspecifier", width=self.part_expression(start, end))
        if kind == "atomic":
            return _Node("atomictypespecifier", type=self.part_type(start, end))
        return self.part_type(start, end)

    def part_expression(self, start: int, end: int) -> _Node:
        """The expression the text between `start` and `end` writes, read again."""
        converter, root = self.reparsed("int _ = (", start, end, ");")
        declaration = converter.named(root)[0]
        value = converter.require(converter.require(declaration, "declarator"), "value")
        if root.has_error:
            raise _Invalid(self.source.text[start:end])
        return converter.expression(converter.named(value)[0])

    def part_type(self, start: int, end: int) -> _Node:
        """The type name the text between `start` and `end` writes, read again."""
        converter, root = self.reparsed("typeof(", start, end, ") _;")
        if root.has_error:
            raise _Invalid(self.source.text[start:end])
        declaration = converter.named(root)[0]
        return converter.type_id(converter.require(converter.require(declaration, "type"), "type"))

    def typeof(self, ts: _TS) -> _Node:
        """`typeof(operand)`, which tree-sitter reads as a macro's type specifier of a type name, and the pre-pass made
        a name where it is an expression; another macro's type specifier is no C syntax."""
        name = self.text(self.require(ts, "name"))
        if name not in _TYPEOFS:
            raise _Invalid(name)
        operand = self.require(ts, "type")
        held = self.pre.names.get(self.local(operand))
        if held is not None:
            return _Node("typeofspecifier", keyword=name, operand=self.part_expression(held[1], held[2]))
        return _Node("typeofspecifier", keyword=name, operand=self.type_id(operand))

    def class_specifier(self, ts: _TS) -> _Node:
        made = _Node("classspecifier", key=self.text(ts.children[0]),
                     attributes=self.blanked_attributes(self.local(ts)))
        for c in self.named(ts):
            if c.type in ("attribute_declaration", "attribute_specifier", "ms_declspec_modifier"):
                made.attributes.append(self.attribute(c))
        name = self.field(ts, "name")
        if name is not None:
            made.name = self.identifier(name)
        body = self.field(ts, "body")
        if body is not None:
            made.body = True
            made.members = _Node("memberlist", members=self.listed(body.children, self.member, body.children[0]))
        return made

    def enum_specifier(self, ts: _TS) -> _Node:
        made = _Node("enumspecifier", key="enum", attributes=self.blanked_attributes(self.local(ts)))
        made.attributes += [self.attribute(c) for c in self.named(ts) if c.type == "attribute_declaration"]
        name, base, body = self.field(ts, "name"), self.field(ts, "underlying_type"), self.field(ts, "body")
        if name is not None:
            made.name = self.identifier(name)
        if base is not None:
            held = self.pre.names.get(self.local(base))
            made.base = self.part_type(held[1], held[2]) if held is not None else _Node(
                "typeid", specifiers=self.specifier(base)).of("c_types")
        if body is not None:
            items = [c for c in body.children if not c.is_missing]
            made.body = True
            made.enumerators = self.enumerators(body.children, body.children[0])
            made.trailing_comma = len(items) > 2 and items[-2].type == ","
        return made

    def enumerators(self, nodes: list[_TS], header: _TS | None) -> list[_Node]:
        """An enumeration's items: its enumerators, and the directives and comments among them, `C Types`' and
        `C Preprocessor`'s terms; a comment, without its line."""
        out = []
        for item in self.listed(nodes, self.enumerator, header):
            if item.branch == "comment":
                del item.fields["line"]
                item.of("c_preprocessor")
            elif item.branch == "directive":
                item = item.directive
            out.append(item)
        return out

    def enumerator(self, ts: _TS) -> _Node:
        if ts.type.startswith("preproc_"):
            return _Node("directive", directive=self.directive_term(ts, "enumerator"))
        if ts.type != "enumerator":
            return self.invalid(ts).of("c_types")
        value = self.field(ts, "value")
        made = _Node("enumerator", name=self.identifier(self.require(ts, "name")),
                     attributes=self.blanked_attributes(self.local(ts))).of("c_types")
        if value is not None:
            made.value = self.expression(value)
        if ts.has_error and self.unconsumed(ts):
            return self.invalid(ts).of("c_types")
        return made

    def blanked_attributes(self, at: int) -> list[_Node]:
        """The standard attributes the pre-pass blanked after the keyword or the name at `at`, read again."""
        out = []
        for start, end in self.pre.attributes.get(at, []):
            converter, root = self.reparsed("", start, end, ";")
            out += [converter.attribute(a) for a in converter.named(converter.named(root)[0])[:-1]]
        return out

    def attribute(self, ts: _TS) -> _Node:
        kind = ts.type
        if kind == "attribute_declaration":
            return _Node("standardattributespecifier", attributes=[self.standard_attribute(a) for a in self.named(ts)])
        if kind == "attribute_specifier":
            made = _Node("gnuattributespecifier", keyword=self.text(ts.children[0]), attributes=[])
            for a in self.named(self.named(ts)[0]):
                if a.type == "call_expression":
                    made.attributes.append(_Node("attribute", name=self.text(self.require(a, "function")),
                                                 arguments=self.arguments(self.require(a, "arguments"))))
                else:
                    made.attributes.append(_Node("attribute", name=self.text(a)))
            return made
        if kind == "ms_declspec_modifier":
            return _Node("declspecspecifier", attributes=[_Node("attribute", name=self.text(a))
                                                          for a in self.named(ts)])
        if kind != "alignas_qualifier":
            raise _Invalid(kind)
        operand = self.named(ts)[0]
        return _Node("alignasspecifier", keyword=self.text(ts.children[0]), operand=self.type_id(operand)
                     if operand.type == "type_descriptor" else self.expression(operand))

    def standard_attribute(self, ts: _TS) -> _Node:
        prefix = self.field(ts, "prefix")
        arguments = next((c for c in self.named(ts) if c.type == "argument_list"), None)
        return _Node("attribute", namespace=self.text(prefix) if prefix is not None else None,
                     name=self.text(self.require(ts, "name")),
                     arguments=self.arguments(arguments) if arguments is not None else [])

    # Declarators

    def declarator(self, ts: _TS) -> _Node:
        """A declarator, named or abstract."""
        return self.inner_declarator(ts)

    def declared(self, ts: _TS) -> _Node:
        """A declaration's declarator, with the GNU attributes the pre-pass blanked after it."""
        made = self.inner_declarator(ts)
        blanked = self.pre.after.get(self.source.offset(ts.end_byte))
        if blanked:
            target = made
            while target.branch in ("pointerdeclarator", "parenthesizeddeclarator") and target.declarator is not None:
                target = target.declarator
            for start, end in blanked:
                converter, root = self.reparsed("", start, end, " int _;")
                target.attributes = (target.attributes or []) + [
                    converter.attribute(converter.named(converter.named(root)[0])[0])]
        return made

    def inner_declarator(self, ts: _TS) -> _Node:
        kind = ts.type
        if kind in ("identifier", "field_identifier", "type_identifier", "primitive_type"):
            if ts.is_missing:
                raise _Invalid(kind)
            return _Node("iddeclarator", name=self.identifier(ts))
        inner = self.field(ts, "declarator")
        held = self.declarator(inner) if inner is not None else None
        if kind in ("pointer_declarator", "abstract_pointer_declarator"):
            made = _Node("pointerdeclarator", declarator=held, qualifiers=[], attributes=[])
            for c in self.named(ts):
                if c.type == "type_qualifier":
                    made.qualifiers.append(_Node("cvqualifier", keyword=self.text(c)))
                elif c.type in ("attribute_declaration",):
                    made.attributes.append(self.attribute(c))
                elif inner is None or c.id != inner.id:
                    raise _Invalid(c.type)  # Microsoft's pointer modifiers
            return made
        if kind in ("array_declarator", "abstract_array_declarator"):
            size = self.field(ts, "size")
            made = _Node("arraydeclarator", declarator=held, static=self.has(ts, "static"),
                         qualifiers=[_Node("cvqualifier", keyword=self.text(c))
                                     for c in self.named(ts) if c.type == "type_qualifier"])
            if size is not None and size.type == "*":
                made.star = True
            elif size is not None:
                made.size = self.expression(size)
            return made
        if kind in ("function_declarator", "abstract_function_declarator"):
            made = _Node("functiondeclarator", declarator=held,
                         parameters=self.parameters(self.require(ts, "parameters")), attributes=[])
            for c in self.named(ts):
                if c.type in ("attribute_specifier", "attribute_declaration"):
                    made.attributes.append(self.attribute(c))
                elif c.type != "parameter_list" and (inner is None or c.id != inner.id):
                    raise _Invalid(c.type)  # an `asm` label, which the model has no place for
            return made
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
        raise _Invalid(kind)

    def parameters(self, ts: _TS) -> list[_Node]:
        out: list[_Node] = []
        for c in ts.children:
            if c.type in ("variadic_parameter", "..."):
                out.append(_Node("ellipsisparameter"))
            elif c.type == "identifier":  # a K&R definition's parameter, named alone
                out.append(_Node("parameterdeclaration", declarator=self.declarator(c)))
            elif c.type == "parameter_declaration":
                attributes: list[_Node] = []
                made = _Node("parameterdeclaration", specifiers=self.specifiers(c, attributes), attributes=attributes)
                declarator = self.field(c, "declarator")
                if declarator is not None:
                    made.declarator = self.declarator(declarator)
                out.append(made)
            elif c.is_named and c.type != "comment":
                raise _Invalid(c.type)
        return out

    def type_id(self, ts: _TS) -> _Node:
        """A type_descriptor: specifiers in source order, and its abstract declarator, `C Types`' `typeid`."""
        declarator = self.field(ts, "declarator")
        return _Node("typeid", specifiers=self.specifiers(ts),
                     declarator=self.declarator(declarator) if declarator is not None else None).of("c_types")

    # Declarations

    def declaration(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        made = _Node("simpledeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     declarators=[])
        for c in self.fields(ts, "declarator"):
            if c.type == "init_declarator":
                made.declarators.append(_Node("initdeclarator", declarator=self.declared(
                    self.require(c, "declarator")), initializer=self.expression(self.require(c, "value"))))
            elif c.type == "gnu_asm_expression":
                raise _Invalid(c.type)  # an `asm` label, which the model has no place for
            else:
                made.declarators.append(_Node("initdeclarator", declarator=self.declared(c)))
        return made

    def function_definition(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        made = _Node("functiondefinition", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     declarator=self.declarator(self.require(ts, "declarator")))
        made.declarations = [self.declaration(c) for c in self.named(ts) if c.type == "declaration"]
        made.body = self.block(self.require(ts, "body"))
        return made

    def static_assert(self, ts: _TS) -> _Node:
        message = self.field(ts, "message")
        return _Node("staticassertdeclaration", keyword=self.text(ts.children[0]),
                     condition=self.expression(self.require(ts, "condition")),
                     message=self.expression(message) if message is not None else None)

    DECLARATIONS: dict[str, Callable[[Any, _TS], Any]] = {}

    # Members

    def member(self, ts: _TS) -> _Node:
        return self.guarded(ts, self.convert_member)

    def convert_member(self, ts: _TS) -> _Node:
        if ts.type.startswith("preproc_"):
            made = self.directive(ts, "member")
        elif ts.type != "field_declaration":
            raise _Invalid(ts.type)
        else:
            attributes: list[_Node] = []
            made = _Node("memberdeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                         declarators=[])
            for c in ts.children:
                if ts.field_name_for_child(ts.children.index(c)) == "declarator":
                    if c.is_missing:
                        self.consumed.add(c.id)  # an unnamed bit-field, which tree-sitter reads with a missing name
                        made.declarators.append(_Node("memberdeclarator"))
                    else:
                        made.declarators.append(_Node("memberdeclarator", declarator=self.declared(c)))
                elif c.type == "bitfield_clause":
                    if not made.declarators:
                        made.declarators.append(_Node("memberdeclarator"))
                    made.declarators[-1].bitfield = self.expression(self.named(c)[0])
        made.line = self.line(ts)
        return made

    # Directives

    def directive(self, ts: _TS, place: str) -> _Node:
        """A directive, as the statement `Directive` holding its `C Preprocessor` term, where a statement or a member
        declaration stands (`place`, `statement` or `member`)."""
        return _Node("directive", directive=self.directive_term(ts, place))

    def directive_term(self, ts: _TS, place: str) -> _Node:
        """A directive's `C Preprocessor` term; a conditional's lines, where `place` lists them (a statement's, a
        member's or an enumerator's), its `group` (a `Group` or a `MemberGroup`), or, among an enumeration's
        enumerators, its `items`."""
        kind = ts.type
        if kind == "preproc_include":
            directive = _directive_name(self.text(ts.children[0]))
            path = self.require(ts, "path")
            if path.type == "system_lib_string":
                made = _Node("includedirective", directive=directive, path=self.text(path)[1:-1], system=True)
            elif path.type == "string_literal":
                made = _Node("includedirective", directive=directive, path=self.text(path)[1:-1])
            else:
                made = _Node("includedirective", directive=directive, macro=self.expression(path))
            return made.of("c_preprocessor")
        if kind in ("preproc_def", "preproc_function_def"):
            value = self.field(ts, "value")
            replacement = self.written(value).strip() if value is not None else None
            made = _Node("definedirective", name=self.identifier(self.require(ts, "name")),
                         replacement=replacement or None)
            parameters = self.field(ts, "parameters")
            if parameters is not None:
                made.function_like = True
                made.parameters = [self.identifier(p) for p in self.named(parameters)]
                made.variadic = self.has(parameters, "...")
            return made.of("c_preprocessor")
        if kind == "preproc_call":
            directive = self.text(self.require(ts, "directive"))
            if directive in _ALTERNATIVE_DIRECTIVES:
                raise _Invalid(directive)  # a conditional's line where none is open
            argument = self.field(ts, "argument")
            text = self.written(argument).strip() if argument is not None else ""
            return _Node("otherdirective", directive=_directive_name(directive), text=text or None).of(
                "c_preprocessor")
        if kind not in ("preproc_if", "preproc_ifdef", "preproc_elif", "preproc_elifdef", "preproc_else"):
            raise _Invalid(kind)
        made = _Node(kind.replace("preproc_", "") + "directive").of("c_preprocessor")
        head = ts.children[0]
        if kind in ("preproc_if", "preproc_elif"):
            head = self.require(ts, "condition")
            made.condition = self.expression(head)
        elif kind in ("preproc_ifdef", "preproc_elifdef"):
            made.negated = self.text(ts.children[0]).rstrip().endswith("ndef")
            head = self.require(ts, "name")
            made.name = self.identifier(head)
        alternative = self.field(ts, "alternative")
        nodes = [c for c in ts.children[ts.children.index(head) + 1:] if alternative is None or c.id != alternative.id]
        if place == "enumerator":
            made.items = self.enumerators(nodes, head)
        elif place == "member":
            made.group = _Node("membergroup", members=self.listed(nodes, self.member, head))
        else:
            made.group = _Node("group", body=self.listed(nodes, self.statement, head))
        if alternative is not None:
            made.alternative = self.directive_term(alternative, place)
        return made

    # Expressions

    def expression(self, ts: _TS) -> _Node:
        return self.term(ts, self.EXPRESSIONS)

    def arguments(self, ts: _TS) -> list[_Node]:
        """A call's arguments; a type's keyword among them, `va_arg(ap, int)`, is a type name."""
        out = []
        for c in self.named(ts):
            if c.type == "identifier" and self.text(c) in _PRIMITIVES:
                out.append(_Node("typeid", specifiers=[_Node("primitivetypespecifier", keyword=self.text(c))]).of(
                    "c_types"))
            else:
                out.append(self.expression(c))
        return out

    def number(self, ts: _TS) -> _Node:
        return _number(self.text(ts))

    def quoted(self, ts: _TS) -> _Node:
        """A character or a string literal, with its spelling, its prefix and its quote."""
        text = self.text(ts)
        quote = "'" if ts.type == "char_literal" else '"'
        prefix = text[:text.index(quote)]
        try:
            value = _unescape(text[len(prefix) + 1:-1])
        except ValueError:
            raise _Invalid(text) from None
        if quote == "'":
            code = 0
            for ch in value:  # several characters: each shifted in after the one before it, as GCC reads them
                code = (code << 8 | ord(ch)) if len(value) > 1 else ord(ch)
            return _Node("literal", value=_scalar(code), text=text, prefix=prefix or None, quote="'")
        return _Node("literal", value=_scalar(value), text=text, prefix=prefix or None, quote='"')

    def null(self, ts: _TS) -> _Node:
        text = self.text(ts)
        if text == "nullptr":
            return _Node("constant", singleton="nullptr", text=text)
        return _Node("variable", name=text)  # `NULL`, a macro's name

    def parenthesized(self, ts: _TS) -> _Node:
        inner = self.named(ts)[0]
        if inner.type == "compound_statement":
            return _Node("statementexpression", block=self.block(inner))
        return _Node("parenthesizedexpression", expression=self.expression(inner))

    def binary(self, ts: _TS) -> _Node:
        return _Node("binaryexpression", left=self.expression(self.require(ts, "left")),
                     operator=self.text(self.require(ts, "operator")),
                     right=self.expression(self.require(ts, "right")))

    def comma(self, ts: _TS) -> _Node:
        """`a, b, c`, which tree-sitter nests to the right; the comma operator groups to the left."""
        operands = [self.require(ts, "left")]
        right = self.require(ts, "right")
        while right.type == "comma_expression":
            operands.append(self.require(right, "left"))
            right = self.require(right, "right")
        made = self.expression(operands[0])
        for operand in [*operands[1:], right]:
            made = _Node("binaryexpression", left=made, operator=",", right=self.expression(operand))
        return made

    def unary(self, ts: _TS) -> _Node:
        operator, argument = self.text(self.require(ts, "operator")), self.require(ts, "argument")
        if operator == "&" and argument.type == "pointer_expression" and self.text(
                self.require(argument, "operator")) == "&" and self.local(argument) == self.local(ts) + 1:
            raise _Invalid("&&")  # GNU's label as a value, `&&l`, which the model has no kind for
        return _Node("unaryexpression", operator=operator, operand=self.expression(argument))

    def update(self, ts: _TS) -> _Node:
        operator = self.text(self.require(ts, "operator"))
        operand = self.expression(self.require(ts, "argument"))
        if ts.children[0].type in ("++", "--"):
            return _Node("unaryexpression", operator=operator, operand=operand)
        return _Node("postfixexpression", operand=operand, operator=operator)

    def call(self, ts: _TS) -> _Node:
        return _Node("callexpression", function=self.expression(self.require(ts, "function")),
                     arguments=self.arguments(self.require(ts, "arguments")))

    def field_expression(self, ts: _TS) -> _Node:
        return _Node("memberexpression", object=self.expression(self.require(ts, "argument")),
                     operator=self.text(self.require(ts, "operator")),
                     member=self.identifier(self.require(ts, "field")))

    def sizeof(self, ts: _TS) -> _Node:
        type_ = self.field(ts, "type")
        operand = self.type_id(type_) if type_ is not None else self.expression(self.require(ts, "value"))
        return _Node("sizeofexpression", operand=operand)

    def initializer_list(self, ts: _TS) -> _Node:
        kids = [c for c in ts.children if not c.is_missing and c.type != "comment"]
        return _Node("initializerlist", items=[self.designated(c) if c.type == "initializer_pair" else self.expression(c)
                                               for c in self.named(ts)],
                     trailing_comma=len(kids) > 2 and kids[-2].type == ",")

    def designated(self, ts: _TS) -> _Node:
        designators: list[_Node] = []
        for d in self.fields(ts, "designator"):
            if d.type in ("field_designator", "field_identifier"):
                name = self.named(d)[0] if d.type == "field_designator" else d
                designators.append(_Node("fielddesignator", name=self.identifier(name)))
            elif d.type == "subscript_designator":
                designators.append(_Node("indexdesignator", index=self.expression(self.named(d)[0])))
            else:
                designators.append(_Node("indexdesignator", index=self.expression(self.require(d, "start")),
                                         last=self.expression(self.require(d, "end"))))
        value = self.require(ts, "value")
        return _Node("designatedinitializer", designators=designators,
                     initializer=_Node("equalinitializer", value=self.expression(value)))

    def generic(self, ts: _TS) -> _Node:
        parts = self.named(ts)
        made = _Node("genericselection", controlling=self.expression(parts[0]), associations=[])
        for i in range(1, len(parts) - 1, 2):  # type, value: `default` is a type named default to tree-sitter
            association = parts[i]
            made.associations.append(_Node("genericassociation", type=self.type_id(association) if self.text(
                association) != "default" else None, value=self.expression(parts[i + 1])))
        return made

    EXPRESSIONS: dict[str, Callable[[Any, _TS], Any]] = {}


_Converter.EXPRESSIONS.update({
    "identifier": lambda self, ts: _Node("variable", name=self.text(ts)),
    "number_literal": _Converter.number, "char_literal": _Converter.quoted, "string_literal": _Converter.quoted,
    "concatenated_string": lambda self, ts: _Node("concatenatedstring", parts=[
        self.expression(c) for c in self.named(ts)]),
    "true": lambda self, ts: _Node("literal", value=_scalar(True), text="true"),
    "false": lambda self, ts: _Node("literal", value=_scalar(False), text="false"),
    "null": _Converter.null, "parenthesized_expression": _Converter.parenthesized,
    "comma_expression": _Converter.comma, "binary_expression": _Converter.binary,
    "assignment_expression": lambda self, ts: _Node(
        "assignmentexpression", left=self.expression(self.require(ts, "left")),
        operator=self.text(self.require(ts, "operator")), right=self.expression(self.require(ts, "right"))),
    "conditional_expression": lambda self, ts: _Node(
        "conditionalexpression", condition=self.expression(self.require(ts, "condition")),
        consequence=self.expression(self.field(ts, "consequence")) if self.field(ts, "consequence") else None,
        alternative=self.expression(self.require(ts, "alternative"))),
    "unary_expression": _Converter.unary, "pointer_expression": _Converter.unary,
    "update_expression": _Converter.update,
    "cast_expression": lambda self, ts: _Node("castexpression", type=self.type_id(self.require(ts, "type")),
                                              operand=self.expression(self.require(ts, "value"))),
    "call_expression": _Converter.call, "field_expression": _Converter.field_expression,
    "subscript_expression": lambda self, ts: _Node(
        "subscriptexpression", object=self.expression(self.require(ts, "argument")),
        indices=[self.expression(self.require(ts, "index"))]),
    "sizeof_expression": _Converter.sizeof,
    "alignof_expression": lambda self, ts: _Node("alignofexpression", keyword=self.text(ts.children[0]),
                                                 operand=self.type_id(self.require(ts, "type"))),
    "offsetof_expression": lambda self, ts: _Node("callexpression", function=_Node("variable", name="offsetof"),
                                                  arguments=[self.type_id(self.require(ts, "type")),
                                                             _Node("variable", name=self.text(
                                                                 self.require(ts, "member")))]),
    "generic_expression": _Converter.generic, "initializer_list": _Converter.initializer_list,
    "compound_literal_expression": lambda self, ts: _Node(
        "compoundliteralexpression", type=self.type_id(self.require(ts, "type")),
        initializer=self.initializer_list(self.require(ts, "value"))),
    "extension_expression": lambda self, ts: _Node("extensionexpression", operand=self.expression(self.named(ts)[0])),
    "preproc_defined": lambda self, ts: _Node("definedexpression", name=self.identifier(self.named(ts)[0])),
})

_Converter.STATEMENTS.update({
    "compound_statement": lambda self, ts: self.block(ts), "expression_statement": _Converter.expression_statement,
    "if_statement": _Converter.if_statement,
    "switch_statement": lambda self, ts: _Node("switchstatement", condition=self.condition(
        self.require(ts, "condition")), body=self.statement(self.require(ts, "body"))),
    "while_statement": _Converter.while_statement,
    "do_statement": lambda self, ts: _Node("dostatement", body=self.statement(self.require(ts, "body")),
                                           condition=self.condition(self.require(ts, "condition"))),
    "for_statement": _Converter.for_statement,
    "return_statement": lambda self, ts: _Node("returnstatement", value=self.expression(self.named(ts)[0])
                                               if self.named(ts) else None),
    "break_statement": lambda self, ts: _Node("breakstatement"),
    "continue_statement": lambda self, ts: _Node("continuestatement"),
    "goto_statement": lambda self, ts: _Node("gotostatement", label=self.identifier(self.require(ts, "label"))),
    "labeled_statement": _Converter.labeled,
    "case_statement": _Converter.case_body, "attributed_statement": _Converter.attributed,
})

_Converter.DECLARATIONS.update({
    "declaration": _Converter.declaration, "type_definition": _Converter.declaration,
    "function_definition": _Converter.function_definition, "static_assert_declaration": _Converter.static_assert,
    **{kind: lambda self, ts: self.directive(ts, "statement") for kind in ("preproc_include", "preproc_def", "preproc_function_def", "preproc_call", "preproc_if",
                    "preproc_ifdef")},
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
    """The callback of the transaction that writes `text`, C source, as the translation unit at `path` in the
    workspace: given to `store.transaction`, or, with `store`, to `store.Mutations.OfTransaction`. Raises `ParseError`
    only for text that is no text, a lone surrogate (which no encoding writes), now, before any transaction: invalid
    syntax is kept (`Programs.C.Error`, the dialects' `error` and `missing`)."""
    try:
        text.encode("utf-16-le")
    except UnicodeEncodeError as error:  # a lone surrogate
        at = error.start
        line, column = text.count("\n", 0, at) + 1, at - (text.rfind("\n", 0, at) + 1) + 1
        raise ParseError("not text: a lone surrogate", line, column) from None
    source, prepared, tree = _parsed(text)
    body = _write(_Converter(source, prepared).unit(tree.root_node))

    def transaction(txn: Any) -> Any:
        symbols = {"ws": store.registered("Programs.Framework.Workspace") if store is not None else
                   txn.Programs.Framework.Workspace,
                   "unit": store.registered(f"{_LANGUAGE}.TranslationUnit") if store is not None else
                   txn.Programs.C.TranslationUnit}
        return txn.uid(path).mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
            .symbols(symbols)
            .spec([
                lambda _: _.ws.files({path: lambda e: e.file(_.unit)}),
                lambda _: _.unit.body(body),
            ])]))])

    return transaction
