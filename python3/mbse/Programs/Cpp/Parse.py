"""Parse: C++ source text as the transaction that writes its translation unit, delegating to tree-sitter-cpp.

`parse(text, path)` reads `text` at once, keeping what does not parse as invalid syntax, and gives the transaction's
callback, which a caller executes, `store.transaction(parse(text, path))`, or builds to write it,
`Plain.ToPlain(store).Transaction(store.Mutations.OfTransaction(parse(text, path, store)))`. Executed in a store holding
the installs (`Cpp.INSTALLS`: C's, then mbse-expressions' `Cpp` and `Cpp Types` and `Programs.Cpp`), it is one upsert,
`uid(path)`, whose symbols bind the workspace (`ws`) and the translation unit (`unit`); its spec puts the unit in the
workspace's `files` by `path` and writes its tree, the unit's `body`, as one value, each declaration and statement a
branch of `Programs.Cpp.Statement` (stage 3's design, "the whole tree as values").

Expressions are mbse-expressions' `Cpp` terms, a declaration's specifiers, declarators and attributes its helpers, type
subterms `Cpp Types`' `typeid`, and directives `C Preprocessor` terms, nested values written through the builders with
their concrete syntax as far as the dialects keep it. Where a term holds statements or declarations, its property holds
them, as the user decided ("the crossover should be modeled as a property of T_A"): a lambda's and a statement
expression's `block`, a class's `members`, and a conditional directive's `group`.

tree-sitter-cpp builds a concrete syntax tree, tree-sitter-c's extended, so `_Converter` is C's
(`Programs.C.Parse._Converter`), where tree-sitter-cpp writes the node types tree-sitter-c writes, and C++'s own, ported
from mbse-programs 0.3's Ccpp parser (`Ccpp/_Parser.py`), which read C++ with tree-sitter-cpp: names, declarators,
lambdas, requires-expressions, templates, classes, namespaces, modules. C's source and its offsets (`_Source`), its
literals, comments, labels, directives, invalid syntax and its rules for what is absent are C++'s too.

**Where tree-sitter-cpp 0.23.4 departs from C++.** As the user decided, "Parser discrepancies from the language spec
should be clearly enumerated and have preprocessing passes as has been done elsewhere": each place where
tree-sitter-cpp 0.23.4, the version pinned, reads C++ (ISO/IEC 14882:2017, 2020 and 2024, C++17, C++20 and C++23, with
the GNU extensions 0.3 kept) otherwise than C++ does is listed here, with the edition that brought the construct where
it is recent, and how `parse` handles it, as C's `Parse` lists tree-sitter-c's. Where tree-sitter cannot parse a
construct, the pre-pass rewrites the text so that it can, keeping every other character where it was, records what it
rewrote (`_Prepared`), and the converter puts the construct back as the model holds it; where tree-sitter parses it
wrongly, the converter corrects it; where tree-sitter reads what C++ rejects, the converter keeps it invalid syntax.

What tree-sitter-cpp cannot parse, or misreads wherever it stands, which the pre-pass rewrites:

1. **Module declarations** (C++20), `module;`, `export module m.n:p;`, `module :private;`, `import std;`,
   `export import :p;`, `import <h>;`, `import "h";`, which it reads as an expression statement, a declaration, a
   label or a template's name, or cannot read: blanked, each made as it stood (`GlobalModuleFragment`,
   `ModuleDeclaration`, `PrivateModuleFragment`, `ImportDeclaration`), listed again where it stood; one that names
   no module, an `Error`.
2. **`export`** (C++20) before a declaration or a block: blanked, the converter making an `ExportDeclaration` of what
   follows it, `braced` for a block.
3. **`extern template`** (C++11), the explicit instantiation declaration: `extern` blanked, the converter making the
   `ExplicitInstantiation` `extern`.
4. **`if consteval` and `if !consteval`** (C++23): rewritten `if (1)`, as long, the converter making the `if`
   `consteval` (and `negated`), with no condition.

What tree-sitter-cpp cannot parse, which the pre-pass rewrites where it found an error:

5. **An explicit object parameter** (C++23), `void f(this S &self)`: `this` blanked, the converter making the
   parameter's `this_keyword`.
6. **A using-declaration of several declarators** (C++17), `using std::a, std::b;`, **or a declarator `typename`
   introduces**, `using typename T::b;`: the declarators after the first, and `typename`, blanked, the converter
   reading each back, `typename_keyword` where it was written.
7. **A bit-field's default member initializer** (C++20), `int x : 4 = 1;`, `int y : 2 {3};`: blanked, the converter
   reading it back into the member's declarator's `initializer`.
8. **An attribute-using-prefix** (C++17), `[[using gnu: hot, cold]]`: `using gnu:` blanked, the converter giving the
   attribute specifier its `using_namespace`.
9. **Attributes after an enumerator's name** (C++17), `A [[deprecated]] = 1`, **or after a pointer's `*`**, `int *
   [[a]] p`: blanked, the converter reading them back into the enumerator's or the pointer declarator's `attributes`.
10. **A label ending a block** (C++23), `l: }` and `case 1: }`: a `;` written in the blank after its `:`, which the
    converter drops: a label without a statement. Without a blank between, `l:}`, kept as tree-sitter's recovery
    leaves it, invalid syntax.
11. **`_Pragma("...")` where a declaration, a statement, a member or an enumerator stands** (C++11), without a `;`
    after it: blanked, the converter listing a `Directive` holding C Preprocessor's `pragmaexpression` where it stood,
    as C's `Parse` does (its 15).
12. **The null directive**, `#` alone on its line: blanked, the converter listing an `otherdirective` with no name
    where it stood, as C's does (its 12).
13. **Digraphs**, `<: :> <% %> %: %:%:`: rewritten as the tokens they spell, as the model holds them; and **`->*`**,
    which it reads as `->` and an error: rewritten `.*`, the converter making it `->*` again.
14. **An alias declaration as a `for` statement's init-statement** (C++23), `for (using T = int; ;)`: blanked but its
    `;`, the converter reading it back, an `AliasDeclaration`, as the statement's `initializer`; an `if`'s, a
    `switch`'s and a range-based `for`'s it parses.
15. **A static lambda** (C++23), `[]() static {}`: `static` blanked, the converter giving the lambda's declarator the
    specifier `static` where it stood; without parameters, `[] static {}`, `static` rewritten `()`, as long, so that it
    prints `[]() static {}`, which C++23 reads the same *(agent: the model holds no lambda's specifiers without its
    declarator)*; **and a lambda's attributes** (C++23), `[] [[nodiscard]] () {}`: blanked, the converter reading them
    back into the lambda's `attributes`.
16. **A conversion function's name within an expression**, `x.operator int()`, `p->operator T *()`, and, within a
    function's body or an initializer, `operator bool()`: made a name as long, the converter reading its type back, a
    `conversionname`. Qualified, `&S::operator int`, it parses as it is.
17. **GNU's extensions**, as C's `Parse` rewrites them for tree-sitter-c (its 6, 9, 11 and 14, the same pre-pass,
    `Programs.C.Parse._gnu`): GNU attributes after a declarator, `int x __attribute__((aligned(16))) = 0;`, read back
    into its `attributes`; a case range, `case 1 ... 3:`, its end read back into the label's `last`; a computed `goto`,
    `goto *p;`, a `GotoStatement` whose `target` is `p`; and an asm label before what initializes a declarator, or
    before GNU attributes, `register int r asm("r1") = 3;`, read back into its identifier's `asm`.

What tree-sitter-cpp misreads, which the converter corrects:

18. **An explicit instantiation definition**, `template class V<int>;`, which it reads with a missing declarator: an
    `ExplicitInstantiation` of the class.
19. **`typeid` of a type-id**, `typeid(int)`, which it reads as a call holding an error: a `typeidexpression` whose
    operand is the type-id, read again; and `typeid(x)`, `noexcept(x)` and `_Pragma("...")`, which it reads as calls:
    a `typeidexpression`, a `noexceptexpression` and C Preprocessor's `pragmaexpression`.
20. **A function deleted or defaulted outside a class**, `int f() = delete;`, `S::S() = default;`, which it reads as
    a declarator initialized by a `delete` expression missing its operand, or by a variable named `default`: a
    `FunctionDefinition` whose body is a `DeletedBody` or a `DefaultedBody`.
21. **An unnamed bit-field**, `int : 3;`, which it reads with a missing name: a `MemberDeclarator` without a
    declarator.
22. **Alternative tokens**, `and`, `or`, `not`, `bitand`, `not_eq` and their like, which it keeps as spelled: the
    tokens they spell, `&&`, `||`, `!`, `&`, `!=`, as 0.3 normalized them.
23. **Casts it reads as calls**: `int(x)`, a call of a type's keyword, a `functionalcastexpression`;
    `static_cast<T>(x)` and its siblings, a call of a template, a `namedcastexpression`; and `T{x}`, which it reads as
    a compound literal, a `functionalcastexpression`.
24. **`.*` and `->*`**, which it reads as a member access: a `binaryexpression`.
25. **`NULL`**, which it reads as a null constant like `nullptr`: the macro's name, an `idexpression`; `nullptr` a
    `constant`.
26. **A conversion function's declarator**, `operator T *()`, which it nests within the conversion type's pointers:
    a function's declarator whose name is a `conversionname` of the type and its pointers.
27. **A declarator's trailing requires-clause and virt-specifiers**, which it reads as its function declarator's:
    the `requires` and `virt_specifiers` of the declarator or the function's definition that holds it.
28. **The pure-specifier**, `= 0`, which it reads as initializing a member function with `0`: the member
    declarator's `pure`.
29. **An attribute declaration**, `[[fallthrough]];`, which it reads as an attributed empty statement: an
    `AttributeDeclaration`; and GNU's attributes on a null statement, `__attribute__((fallthrough));`, which it reads as
    an error and `;`, an `AttributedStatement`, as C's does (its 22).
30. **A condition's declaration**, `if (int x = f())`, whose initializer it reads as the declaration's: its
    declarator's.
31. **GNU's asm label**, `int f(void) asm("g");`, which it reads as a declarator of its own: the `asm` of the
    identifier's declarator it follows; and GNU's `__restrict`, which it reads as Microsoft's pointer modifier, a
    cv-qualifier.
32. **A pointer to member's declarator**, `int C::*p`, which it reads as a qualified name ending in a pointer's
    declarator: a `pointerdeclarator` whose `scope` is the class.
33. **A constraint**, the parenthesized conjunctions and disjunctions it reads as tokens within a requires-clause: a
    term, `&&` and `||` binary expressions of primary expressions.
34. **`defined X`**, without parentheses, read as `defined(X)`, its one form in the model, and GNU's labels as values,
    `&&l`, as C's `Parse` reads them (its 25 and 28).
35. **A type's keyword as a macro's argument**, `va_arg(ap, int)`, which it reads as an error: a `typeid`, as C's
    `Parse` reads it (its 24).
36. **`auto(x)` and `auto{x}`** (C++23), which it reads as a call of a function named `auto` and a cast to a type named
    `auto`: a `functionalcastexpression` whose type is a `placeholdertypespecifier`.

What tree-sitter-cpp reads but C++ rejects, which the converter keeps invalid syntax (an `Error`, or an `error` term):

37. **Statements at namespace scope**, `x = 1;`, `{}`: a translation unit, a namespace, a linkage specification and an
    `export` hold declarations alone (`;` alone is an `EmptyDeclaration`).
38. **C's constructs**: `_Generic`, a compound literal of a type-id, `(struct p){1}`, C's index designators, `[0] = 1`,
    an array declarator's `static`, qualifiers and `[*]`, K&R definitions, and the keywords `restrict`, `_Atomic`,
    `_Noreturn`, `_Thread_local` and `_Alignas`.
39. **Literals C++ rejects**: an escape of no character (`'\\x'`), and an octal one with a digit 8 or 9 (`08`), which
    it reads as two; a suffix C++'s literals have not, `1uu`, `1e`, `0x`, it reads as a user-defined literal's,
    kept as it reads them.
40. **A conditional directive's closing or continuing line where none is open**, `#endif` alone.
41. **Virt-specifiers where no member is declared**, `int f() override;` at namespace scope, and a function's
    definition whose declarator declares no function.
42. **Microsoft's extensions** 0.3 did not keep: calling conventions (`__cdecl`), pointer modifiers (`__ptr32`).
43. **`_Pragma` of what is no one string literal**, `_Pragma(x)`.

What mbse-expressions' C++ dialect cannot hold, which the converter keeps invalid syntax, each a gap reported to it:

44. **Structured bindings** (C++17), `auto [a, b] = p;`, `for (auto &[k, v] : m)`: no declarator of the dialect binds
    several names.
45. **A conditional `explicit`** (C++20), `explicit(N > 1)`: no specifier of the dialect holds its condition (`explicit`
    alone is a `declspecifier`).
46. **`__has_include`** (C++17), `#if __has_include(<h>)`, which tree-sitter cannot parse either: no term of the
    dialects holds a header's name.
47. **A user-defined literal of adjacent strings**, `"a" "b"_s`: the dialect's `userdefinedliteral` holds one
    literal; an `error` term.

What stays as tree-sitter-cpp reads it, each left with its reason:

48. **Typedef names and other names**, `T * x;`, `T(x);`, `(T)*x`, **template names and other names**, `a<b>(c)`, and
    **concepts and types**, `template <Number T>`, read as a constant parameter of the type `Number`: which a text is
    depends on what `T`, `a` and `Number` name, which the declarations before it decide, outside the grammar. Read as
    tree-sitter decides.
49. **A conditional directive that splits a construct**, `#ifdef A` opening a block that `#endif` closes after it: no
    tree of either, the preprocessor not run. Kept as tree-sitter's recovery leaves it, invalid syntax.

Decided here *(agent, for review)*, as C's `Parse` decides: schemas resolved through the transaction or the store;
what is absent is absent; a literal's value what C++ reads its spelling as, a raw string's its characters between its
delimiter's parentheses, a user-defined literal's its literal's; each statement's, declaration's, member's, clause's,
directive's, comment's and error's line its `line`. Invalid syntax is kept, never raised, as the user decided for every
language: an `Error` where a statement, a declaration or a member stands, an `error` or a `missing` term within an
expression; `ParseError` only for text that is no text, a lone surrogate.
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
_CV = {"const", "volatile", "__restrict", "__restrict__"}
_C_ONLY = {"restrict", "_Atomic", "_Noreturn", "_Thread_local", "_Alignas"}
"""C's keywords tree-sitter-cpp reads as qualifiers and specifiers, which C++ has not."""
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
    bit-field's initializer, an attribute specifier's `using` namespace, the `;` it wrote after a label ending a block,
    an alias declaration where an init-statement stands, a lambda's `static` and attributes, and a conversion
    function's name made a name."""

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
        self.typenames: set[int] = set()  # the offset of a using-declarator's name, after its `typename`
        self.aliases: dict[int, tuple[int, int]] = {}  # by the `(` before it: an alias declaration's span, before its
        # `;`, blanked where an init-statement stands
        self.statics: dict[int, int] = {}  # by its lambda's `(`: the offset of a lambda's `static`
        self.lambdas: dict[int, list[tuple[int, int]]] = {}  # by its lambda's `[`: the span of each of its attributes
        self.conversions: dict[int, tuple[int, int]] = {}  # by its offset: a conversion function's name made a name,
        # and the span of its type


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
    labels: dict[int, int] = {}  # the index of an asm label's `)`, blanked: where the declarator before it ends
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
        elif w == "->" and after == "*" and tokens[i][0] == end:
            chars[start:end + 1] = list(".* ")  # `->*`, which it reads as `->` and an error
            found.keywords[start] = "->*"
        elif w == "this" and before in ("(", ",") and (C._WORD.fullmatch(after) or after == "::") and (
                after not in ("this",)):
            blank(start, end)  # an explicit object parameter (C++23), `this S &self`
            found.this.add(tokens[i][0])
        elif w == "typename" and before in ("using", ",") and "using" in _heads(tokens, i - 1) and "=" not in (
                _heads(tokens, i - 1)):
            blank(start, end)  # a using-declarator's `typename`, `using typename T::b;`
            found.typenames.add(tokens[i][0])
        elif w == "using" and before == "(" and word(i - 3) == "for":
            stop = next((j for j in range(i, len(tokens)) if tokens[j][2] == ";" and _depth(tokens, i, j) == 0),
                        len(tokens))  # an alias declaration as an init-statement (C++23), `for (using T = int; ;)`
            if stop < len(tokens) and "=" in (t[2] for t in tokens[i:stop]):
                found.aliases[tokens[i - 2][0]] = (start, tokens[stop - 1][1])
                blank(start, tokens[stop - 1][1])
                i = stop
        elif w == "[" and after == "[" and before == "]" and _introducer(tokens, i - 2):
            opening, j = C._opening(tokens, i - 2), i - 1  # a lambda's attributes (C++23), `[] [[nodiscard]] ()`
            while word(j) == "[" and word(j + 1) == "[" and (close := C._closing(tokens, j)) is not None:
                found.lambdas.setdefault(tokens[opening][0], []).append((tokens[j][0], tokens[close][1]))
                blank(tokens[j][0], tokens[close][1])
                j = close + 1
            i = max(i, j)  # unclosed: nothing to read back
        elif w == "static" and _lambda_static(tokens, i - 1):
            opening = C._opening(tokens, i - 2)  # a static lambda (C++23), `[]() static {}`; `[] static {}` given
            if before == "]":  # its `()`
                chars[start:end] = list("()".ljust(end - start))
                opening = i - 1
            else:
                blank(start, end)
            found.statics[tokens[opening][0]] = start
        elif w == "operator" and (before in (".", "->") or braces[i - 1] in ("block", "init") and before != "::") and (
                C._WORD.fullmatch(after) and after not in ("new", "delete", "co_await")):
            stop = _conversion_type(tokens, i)  # a conversion function's name in an expression, `x.operator int()`
            found.conversions[start] = (tokens[i][0], tokens[stop - 1][1])
            chars[start:tokens[stop - 1][1]] = list("_" * (tokens[stop - 1][1] - start))  # a line's end within it
            i = stop  # too, as the source's lines are counted in the text as written
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
        elif w == "*" and after == "[" and word(i + 1) == "[":
            close = C._closing(tokens, i)  # a pointer's attributes, `* [[a]]`
            if close is None:  # unclosed: nothing to read back
                continue
            found.attributes.setdefault(start, []).append((tokens[i][0], tokens[close][1]))
            blank(tokens[i][0], tokens[close][1])
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
        else:
            C._gnu(tokens, braces, i - 1, found, labels, chars)  # GNU's extensions, as C's pre-pass rewrites them
    return "".join(chars), found


def _lambda_static(tokens: list[tuple[int, int, str]], at: int) -> bool:
    """Whether the `static` at `tokens[at]` is a lambda's (C++23): after its parameters, whose `(` follows its captures'
    `]` or its template parameters' `>`, or after its captures, `[] static`, which no attribute's `]]` and no
    subscript's `]` is."""
    before = tokens[at - 1][2] if at > 0 else ""
    if before == ")":
        opening = C._opening(tokens, at - 1)
        return opening > 0 and tokens[opening - 1][2] in ("]", ">")
    return before == "]" and _introducer(tokens, at - 1)


def _introducer(tokens: list[tuple[int, int, str]], close: int) -> bool:
    """Whether the `]` at `tokens[close]` closes a lambda's captures: its `[` follows no name, `)` or `]` (a
    subscript's), but `return` and its like, and opens no attribute's `[[`."""
    opening = C._opening(tokens, close)
    previous = tokens[opening - 1][2] if opening > 0 else ""
    following = tokens[opening + 1][2] if opening + 1 < len(tokens) else ""
    return following != "[" and previous not in (")", "]", "[") and not (
        C._WORD.fullmatch(previous) and previous not in ("return", "co_return", "co_yield", "throw"))


def _conversion_type(tokens: list[tuple[int, int, str]], first: int) -> int:
    """The index of the token after the conversion type that begins at `tokens[first]`: its words, its qualifiers' `:`s,
    its pointers' and references' operators, and its template arguments in angle brackets."""
    depth, j = 0, first
    while j < len(tokens):
        w = tokens[j][2]
        if w == "<":
            depth += 1
        elif w in (">", ">>") and depth > 0:
            depth = max(0, depth - len(w))
        elif depth == 0 and not (C._WORD.fullmatch(w) or w in (":", "*", "&", "&&")):
            break
        j += 1
    return j


# --- Literals ---


_INTEGER = re.compile(r"(0[xX](?:'?[0-9a-fA-F])+|0[bB](?:'?[01])+|0(?:'?[0-7])*|[1-9](?:'?[0-9])*)([A-Za-z_]\w*)?")


def _number(text: str) -> _Node:
    """A number's literal: its value, an int or a float, its spelling, and what the spelling encodes."""
    integer = _INTEGER.fullmatch(text)
    floating = C._FLOATING.fullmatch(text)
    if integer is not None and SUFFIXES[int].fullmatch(integer.group(2) or ""):
        digits, suffix = integer.group(1).replace("'", ""), integer.group(2) or ""
        base = {"0x": 16, "0X": 16, "0b": 2, "0B": 2}.get(digits[:2], 8 if digits.startswith("0") else 10)
        value = int(digits[2:] if base in (2, 16) else digits, base)
        return _Node("literal", value=_scalar(value), text=text, base=base, separators="'" in text,
                     suffix=suffix or None)
    digits = floating.group(1).replace("'", "")  # tree-sitter reads no other number, nor a suffix but C++'s
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
        if self.local(inner[0]) in self.pre.gotos:  # `goto *p;`, which the pre-pass made `+p;`
            return _Node("gotostatement", target=self.expression(self.require(inner[0], "argument")))
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
        """An init-statement: a declaration, an alias declaration (C++23), or a term."""
        if ts.type == "declaration":
            return self.declaration(ts)
        if ts.type == "alias_declaration":
            return self.alias(ts)
        if ts.type == "expression_statement":
            return _Branch("expression", self.expression(self.named(ts)[0]))
        return _Branch("expression", self.expression(ts))

    def aliased(self, opening: _TS) -> _Node | None:
        """The alias declaration the pre-pass blanked where an init-statement stands after `opening`, a `(`, read
        again (C++23); None where it blanked none."""
        span = self.pre.aliases.get(self.local(opening))
        if span is None:
            return None
        converter, root = self.reparsed("", *span, ";")
        if root.has_error:
            raise _Invalid("using")
        return converter.alias(converter.named(root)[0])

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
        made.initializer = self.aliased(ts.children[1])
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
        made.initializer = self.aliased(ts.children[1])
        if made.initializer is None and initializer is not None:
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
        return out

    def specifier(self, ts: _TS) -> list[_Node]:
        """The specifiers one tree-sitter node spells."""
        kind, spelling = ts.type, self.text(ts)
        if kind in ("identifier", "type_identifier") and spelling == "auto":  # `auto(x)`, `auto{x}` (C++23)
            return [_Node("placeholdertypespecifier", decltype=False)]
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
        if spelling in _C_ONLY:
            raise _Invalid(spelling)
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
        return out + [current]

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
        """A call's arguments; a type's keyword among them, `va_arg(ap, int)`, which tree-sitter-cpp reads as an
        error, a type-id, as C's `Parse` reads it."""
        out = []
        for c in ts.children:
            kept = self.named(c)
            if c.type == "ERROR" and len(kept) == 1 and kept[0].type == "primitive_type":
                self.consumed.update(n.id for n in (c, *c.children))
                out.append(_Node("typeid", specifiers=self.specifier(kept[0])))
            elif c.is_named and c.type not in ("comment", "ERROR"):
                out.append(self.argument(c))
        return out

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
        span = self.pre.conversions.get(self.local(ts))
        if span is not None:  # `x.operator int`, which the pre-pass made a name
            return _Node("conversionname", type=self.part_type(*span))
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
        parts = [self.text(c) for c in ts.children[1:] if c.type != "comment"]  # operator_name, the last kind of name
        if parts and parts[0].startswith('""'):
            return _Node("literaloperatorname", suffix=parts[-1] if len(parts) > 1 else parts[0][2:])
        return _Node("operatorname", operator=_ALTERNATIVES.get("".join(parts), "".join(parts)))

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

    def inner_declarator(self, ts: _TS) -> _Node:
        kind = ts.type
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
                         qualifiers=[], attributes=self.blanked_attributes(self.local(ts)))
            for c in self.named(ts):
                if c.type == "type_qualifier" and self.text(c) not in _C_ONLY or (
                        c.type == "ms_pointer_modifier" and self.text(c) in _CV):  # GNU's `__restrict`, which
                    made.qualifiers.append(_Node("cvqualifier", keyword=self.text(c)))  # it reads as Microsoft's
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
            return _Node("parenthesizeddeclarator", declarator=self.declarator(self.named(ts)[-1]))  # after a
            # calling convention, `(__cdecl *f)`, which tree-sitter reads as an error
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
            else:  # a virt-specifier, the last kind of part
                self.lifted.setdefault("virt_specifiers", []).append(self.text(c))
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
            else:  # a constant's parameter, the last kind
                out.append(self.parameter(c))
        return out

    def type_parameter(self, ts: _TS) -> _Node:
        first = ts.children[0]
        made = _Node("typeparameter", key=first.type, pack=self.has(ts, "..."))
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
        defined = self.defined(ts)
        if defined is not None:
            return defined
        for i, c in enumerate(ts.children):
            field = ts.field_name_for_child(i)
            if field == "declarator" and c.type == "gnu_asm_expression":  # GNU's asm label, which tree-sitter-cpp
                C._identifier(made.declarators[-1].declarator).asm = self.asm_label(c)  # reads as a declarator
            elif field == "declarator":
                made.declarators.append(self.init_declarator(c, "initdeclarator"))
            elif field == "value":  # a condition's declarator's, which tree-sitter reads as the declaration's
                made.declarators[-1].initializer = self.initializer(c, ts.children[i - 1].type == "=")
        return made

    def defined(self, ts: _TS) -> _Node | None:
        """A function's declaration `= delete` or `= default` outside a class, which tree-sitter-cpp reads as a
        declarator initialized by a `delete` expression missing its operand, or by a variable named `default`: a
        function's definition; None for any other declaration."""
        declarators = self.fields(ts, "declarator")
        if len(declarators) != 1 or declarators[0].type != "init_declarator":
            return None
        value = self.require(declarators[0], "value")
        named = self.named(value)
        deleted = value.type == "delete_expression" and len(named) == 1 and named[0].is_missing
        if not (deleted or value.type == "identifier" and self.text(value) == "default"):
            return None
        self.lifted = {}
        attributes: list[_Node] = []
        made = _Node("functiondefinition", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                     declarator=self.declarator(self.require(declarators[0], "declarator")),
                     body=_Node("deletedbody" if deleted else "defaultedbody"))
        made.virt_specifiers, made.requires = self.lifted.get("virt_specifiers"), self.lifted.get("requires")
        if C._binder(made.declarator).branch != "functiondeclarator":
            raise _Invalid(ts.type)
        self.consumed.update(n.id for n in named)
        return made

    def init_declarator(self, ts: _TS, kind: str) -> _Node:
        """A declarator, with what initializes it, its trailing `requires` (and, a member's, its virt-specifiers)."""
        self.lifted = {}
        if ts.type == "init_declarator":
            made = _Node(kind, declarator=self.declared(self.require(ts, "declarator")))
            made.initializer = self.initializer(self.require(ts, "value"), self.has(ts, "="))
        else:
            made = _Node(kind, declarator=self.declared(ts))
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
        else:  # `= delete`: tree-sitter requires a body or one of these clauses
            made.body = _Node("deletedbody")
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
            else:  # what it declares, its one other part
                made.declaration = self.templated(c)
        return made

    def templated(self, ts: _TS) -> _Node:
        """What a template declares: a declaration, or, within a class, a member's declaration."""
        if ts.type == "field_declaration" or ts.type == "declaration" and self.member_context:
            return self.convert_member(ts)
        if ts.type in ("class_specifier", "struct_specifier", "union_specifier", "enum_specifier"):
            return _Node("simpledeclaration", specifiers=self.specifier(ts))
        return self.convert(ts)  # tree-sitter-cpp's grammar templates declarations, aliases, concepts and templates

    member_context = False

    def template_instantiation(self, ts: _TS) -> _Node:
        attributes: list[_Node] = []
        declaration = _Node("simpledeclaration", specifiers=self.specifiers(ts, attributes), attributes=attributes,
                            declarators=[])
        declarator = self.require(ts, "declarator")
        if declarator.is_missing:  # `template class V<int>;`, read with a missing name
            self.consumed.add(declarator.id)
        else:
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
            ts, "typename") or self.local(self.named(ts)[-1]) in self.pre.typenames, name=target)])
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
            return made
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
        if made.branch != "literal":  # of adjacent strings, `"a" "b"_s`, which the dialect's literal is not (41)
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
        if function.type == "primitive_type" or function.type == "identifier" and self.text(function) == "auto":
            return _Node("functionalcastexpression", type=self.specifier(function)[0],  # `int(x)`, `auto(x)`
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
        operator = self.pre.keywords.get(self.local(self.require(ts, "operator")), operator)  # `->*`, made `.*`
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
        made.attributes = []
        for start, end in self.pre.lambdas.get(self.local(ts), []):  # which the pre-pass blanked (C++23)
            converter, root = self.reparsed("", start, end, " int _;")
            made.attributes.append(converter.attribute(converter.named(converter.named(root)[0])[0]))
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
            else:  # a name, the last kind of capture
                made.captures.append(_Node("simplecapture", name=self.identifier(c)))
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
        parameters = self.require(ts, "parameters")
        made = _Node("lambdadeclarator", parameters=self.parameters(parameters), specifiers=[], attributes=[])
        static = self.pre.statics.get(self.local(parameters))  # `static` (C++23), which the pre-pass blanked
        for c in self.named(ts):
            if static is not None and self.local(c) > static:
                made.specifiers.append(_Node("declspecifier", keyword="static"))
                static = None
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
            else:  # an attribute specifier, the last kind of part
                made.attributes.append(self.attribute(c))
        if static is not None:
            made.specifiers.append(_Node("declspecifier", keyword="static"))
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
