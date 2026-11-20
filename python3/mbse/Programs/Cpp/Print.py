"""Print: a C++ translation unit, as the store holds it, printed as C++ source text in one fixed layout.

A translation unit is a `Programs.Cpp.TranslationUnit` that `Programs.Framework.TheWorkspace` owns by its path; it holds
its tree as one value, its `body`. Where a term holds statements or declarations, a lambda's and a statement
expression's `block`, a class's `members` and a conditional directive's `group`, they print within the term, at the
level of the statement that holds it. The printer reads the tree and writes nothing:

- `print_module(store, path)`: the text of the translation unit at `path`, read within a transaction of its own, so
  called with none open on `store`; LookupError where the workspace holds no file at `path`.
- `print_file(unit)`: the text of a translation unit, given its visitor, within the transaction that made it.
- `print_statement(statement)`: the lines of one statement, declaration or member, joined by newlines without a final
  one, given its record, within the transaction that read it.

The layout is C's (`Programs.C.Print`), whose printer this module's `Printer` extends, and 0.3's for what C++ adds
(`Ccpp/_Printer.py`): a namespace's, a linkage specification's and an `export`'s braced declarations one level in, an
unbraced one after its head on its line; a template's head (`template <...>`, and its `requires`) on a line of its own,
what it declares on the next at its level; an access specifier one level out from the members after it, as a label is;
`} catch (...) {` on the line that closes the block before it, and a function-try-block's `try` after its declarator;
a constructor's member initializers after its declarator, ` : a(1), b{2}`; `= default;` and `= delete;`; a declarator's
virt-specifiers, `= 0` and trailing `requires` after it; a module's and an import's declaration as written, but
spaced as the printer spaces. C++'s terms are mbse-expressions' `Cpp` terms, written by the C family's printer
(`C.Expressions.Text.Printer`), with C++'s precedence.

Decided by the agent, each *(agent)*:

- **Every kind prints** (`KINDS`): each of `Statements.KINDS`, and the language's `Error`; a statement of a kind not
  listed is refused, TypeError, as C's are.
- **An `if consteval`**, which has no condition, prints `if consteval` (`if !consteval` where `negated`), and an `if`
  that is `constexpr` `if constexpr (...)`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from mbse.Expressions.C.Expressions import Text
from mbse.Expressions.C.Expressions.Text import ASSIGNMENT, COMMA, CONDITIONAL
from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions

from ..C import Print as C
from ..C.Print import _INDENT, _branch, _declared, _held, _joined, _kind, _many, _one, _statements
from ..Framework.Model import WORKSPACE
from .Statements import LANGUAGE

__all__ = ["print_module", "print_file", "print_statement", "Printer", "KINDS"]


def _prefixed(prefix: str, lines: list[str], level: int) -> list[str]:
    """`lines`, the first at `level` after `prefix` (`export `, `extern "C" `)."""
    return [_INDENT * level + prefix + lines[0].lstrip(), *lines[1:]]


class Printer(C.Printer):
    """C's printer (`Programs.C.Print.Printer`) over C++'s terms, and C++'s statements, declarations and members."""

    HOLDERS = (*C.Printer.HOLDERS, "lambdaexpression")

    def __init__(self) -> None:
        Text.Printer.__init__(self, CppExpressions.DIALECT)
        self.level = 0
        self.records: dict[int, tuple[Any, Any]] = {}

    def group(self, node: Any) -> str:
        branch = _branch(self.records[id(node)][1].group)
        if branch is None:
            return ""
        tag, group = branch
        return "\n".join(self.block(_statements(group, "body" if tag == "cpp_group" else "members"), self.level))

    def condition(self, prop: Any) -> str:
        """A condition: a term, or a declaration (`int x = f()`)."""
        tag, record = _branch(prop)
        if tag == "simpledeclaration":
            return self.declaration(record)
        if tag == "error":
            return record.text.get() or ""
        return self.e(record, COMMA)

    def init_statement(self, prop: Any) -> str:
        """An init-statement with its `;`, and a space; nothing where there is none."""
        branch = _branch(prop)
        if branch is None:
            return ""
        tag, record = branch
        if tag == "aliasdeclaration":
            return self.alias(record) + " "
        if tag == "error":
            return (record.text.get() or "") + " "
        return (self.declaration(record) if tag == "simpledeclaration" else self.e(record, COMMA)) + "; "

    def requires(self, prop: Any) -> str:
        return self.optional(prop, " requires ", self.constraint)

    def initialized(self, prop: Any) -> str:
        """What initializes a declarator: ` = x`, `(x)` or `{x}`; nothing where nothing does."""
        return self.optional(prop, "", lambda held: self.initializer(self.part(held)))

    def declaration(self, node: Any) -> str:
        """A declaration without its `;`: its attributes, specifiers and declarators, each with what initializes it."""
        declarators = ", ".join(self.declarator_of(d.declarator) + self.initialized(d.initializer) + self.requires(
            d.requires) for d in _many(node.declarators))
        return self.attributes_of(node) + _declared(self.specifiers_of(node), declarators)

    def member_declaration(self, node: Any) -> str:
        declarators = []
        for d in _many(node.declarators):
            written = self.declarator_of(d.declarator) + self.requires(d.requires) + "".join(
                " " + v for v in _many(d.virt_specifiers)) + (" = 0" if d.pure.get() else "")
            written += self.optional(d.bitfield, " : " if written else ": ", lambda held: self.e(held, CONDITIONAL))
            initializer = self.initialized(d.initializer)  # after a bit-field's width, `{3}` spaced from it
            declarators.append(written + (" " if _held(d.bitfield) is not None and initializer[:1] == "{" else "")
                               + initializer)
        return self.attributes_of(node) + _declared(self.specifiers_of(node), ", ".join(declarators)) + ";"

    def function(self, node: Any, level: int) -> list[str]:
        head = self.attributes_of(node) + _declared(self.specifiers_of(node), self.declarator_of(node.declarator))
        head += "".join(" " + v for v in _many(node.virt_specifiers)) + self.requires(node.requires)
        initializers = [self.written(_held(i.member)) + self.initializer(self.part(_held(i.initializer))) + (
            "..." if i.pack.get() else "") for i in _many(node.initializers)]
        written = " : " + ", ".join(initializers) if initializers else ""
        tag, body = _branch(node.body)
        if tag == "trystatement":
            return self.try_lines(body, head + " try" + written, level)
        if tag in ("defaultedbody", "deletedbody"):
            return [_INDENT * level + head + written + (" = default;" if tag == "defaultedbody" else " = delete;")]
        return self.braced(head + written, _statements(body, "body"), level)

    def try_lines(self, node: Any, head: str, level: int) -> list[str]:
        """`head {`, a `try`'s block, and each handler, `} catch (parameter) {`."""
        lines = self.braced(head, _statements(_held(node.body), "body"), level)
        for handler in _many(node.handlers):
            lines = _joined(lines, self.STATEMENTS["Handler"](self, handler, level))
        return lines

    # Statements

    def if_statement(self, node: Any, level: int) -> list[str]:
        if node.consteval.get():
            head = "if !consteval" if node.negated.get() else "if consteval"
        else:
            head = f"if{' constexpr' if node.constexpr.get() else ''} ({self.init_statement(node.initializer)}" \
                   f"{self.condition(node.condition)})"
        consequence = _one(node.consequence)
        lines = self.body(head, consequence, level)
        alternative = _one(node.alternative)
        if alternative is None:
            return lines
        if _kind(alternative) == "IfStatement":
            tail = self.if_statement(alternative, level)
            tail[0] = f"{_INDENT * level}else {tail[0].lstrip()}"
        else:
            tail = self.body("else", alternative, level)
        return _joined(lines, tail) if _kind(consequence) == "CompoundStatement" else lines + tail

    def loop(self, keyword: str) -> Callable[[Any, Any, int], list[str]]:
        return lambda node, level: self.body(f"{keyword} ({self.init_statement(node.initializer) if keyword == 'switch' else ''}"
                                             f"{self.condition(node.condition)})", _one(node.body), level)

    def for_statement(self, node: Any, level: int) -> list[str]:
        initializer = self.init_statement(node.initializer).rstrip() or ";"
        condition = self.optional(node.condition, " ", lambda held: self.condition(node.condition))
        increment = self.optional(node.increment, " ", lambda held: self.e(held, COMMA))
        return self.body(f"for ({initializer}{condition};{increment})", _one(node.body), level)

    def range_for(self, node: Any, level: int) -> list[str]:
        head = f"for ({self.init_statement(node.initializer)}{self.declaration(_held(node.declaration))} : " \
               f"{self.e(_held(node.range), ASSIGNMENT)})"
        return self.body(head, _one(node.body), level)

    def namespace(self, node: Any, level: int) -> list[str]:
        head = ("inline " if node.inline.get() else "") + "namespace" + "".join(
            " " + self.written(a) for a in _many(node.attributes))
        names = "::".join(("inline " if n.inline.get() else "") + self.written(_held(n.name)) for n in _many(node.names))
        return self.braced(head + (" " + names if names else ""), _statements(node, "body"), level)

    def wrapping(self, head: str, node: Any, level: int) -> list[str]:
        """A linkage specification's or an `export`'s declarations: braced, or the one after its head."""
        if node.braced.get():
            return self.braced(head, _statements(node, "body"), level)
        return _prefixed(head + " ", self.block(_statements(node, "body"), level), level)

    def template(self, node: Any, level: int) -> list[str]:
        parameters = ", ".join(self.written(p) for p in _many(node.parameters))
        head = f"template <{parameters}>" + self.requires(node.requires)
        return [_INDENT * level + head, *self.statement_lines(_one(node.declaration), level)]

    def instantiation(self, node: Any, level: int) -> list[str]:
        prefix = ("extern " if node.extern.get() else "") + "template "
        return [_INDENT * level + prefix + self.declaration(_held(node.declaration)) + ";"]

    def access(self, node: Any, level: int) -> list[str]:
        """An access specifier, one level out from the members after it."""
        return [f"{_INDENT * max(level - 1, 0)}{node.access.get()}:"]

    # Declarations C++ adds

    def alias(self, node: Any) -> str:
        attributes = "".join(" " + self.written(a) for a in _many(node.attributes))
        return f"using {self.written(_held(node.name))}{attributes} = {self.term(_held(node.type))};"

    def using(self, node: Any) -> str:
        declarators = ", ".join(("typename " if d.typename_keyword.get() else "") + self.written(_held(d.name)) + (
            "..." if d.pack.get() else "") for d in _many(node.declarators))
        return f"using {declarators};"

    def module(self, node: Any) -> str:
        kind = _kind(node)
        if kind == "GlobalModuleFragment":
            return "module;"
        if kind == "PrivateModuleFragment":
            return "module :private;"
        text = "export " if node.export.get() else ""
        partition = f":{node.partition.get()}" if node.partition.get() is not None else ""
        if kind == "ModuleDeclaration":
            text += f"module {node.name.get()}{partition}"
        elif node.header.get() is not None:
            text += "import " + (f"<{node.header.get()}>" if node.system.get() else f'"{node.header.get()}"')
        else:
            text += f"import {node.name.get() or ''}{partition}"
        return text + "".join(" " + self.written(a) for a in _many(node.attributes)) + ";"

    STATEMENTS: ClassVar[dict[str, Callable[[Printer, Any, int], list[str]]]] = {
        **C.Printer.STATEMENTS,
        "IfStatement": if_statement, "WhileStatement": lambda self, node, level: self.loop("while")(node, level),
        "SwitchStatement": lambda self, node, level: self.loop("switch")(node, level),
        "ForStatement": for_statement, "RangeForStatement": range_for, "FunctionDefinition": function,
        "TryStatement": lambda self, node, level: self.try_lines(node, "try", level),
        "NamespaceDefinition": namespace,
        "LinkageSpecification": lambda self, node, level: self.wrapping(f'extern "{node.language.get()}"', node,
                                                                        level),
        "ExportDeclaration": lambda self, node, level: self.wrapping("export", node, level),
        "TemplateDeclaration": template, "ExplicitInstantiation": instantiation, "AccessSpecifier": access,
        "Handler": lambda self, node, level: self.braced(f"catch ({self.written(_held(node.parameter))})", _statements(
            _held(node.body), "body"), level),
    }

    SIMPLE: ClassVar[dict[str, Callable[[Printer, Any], str]]] = {
        **C.Printer.SIMPLE,
        "SimpleDeclaration": lambda self, node: self.declaration(node) + ";",
        "MemberDeclaration": member_declaration,
        "CoReturnStatement": lambda self, node: "co_return" + self.optional(
            node.value, " ", lambda held: self.e(held, COMMA)) + ";",
        "EmptyDeclaration": lambda self, node: ";",
        "NamespaceAliasDefinition": lambda self, node: f"namespace {self.written(_held(node.name))} = "
                                                       f"{self.written(_held(node.target))};",
        "UsingDirective": lambda self, node: self.attributes_of(node) + f"using namespace "
                                                                        f"{self.written(_held(node.name))};",
        "UsingDeclaration": using,
        "UsingEnumDeclaration": lambda self, node: f"using enum {self.written(_held(node.type))};",
        "AliasDeclaration": alias,
        "ConceptDefinition": lambda self, node: f"concept {self.written(_held(node.name))}" + "".join(
            " " + self.written(a) for a in _many(node.attributes)) + f" = {self.e(_held(node.constraint), CONDITIONAL)};",
        "ModuleDeclaration": module, "GlobalModuleFragment": module, "PrivateModuleFragment": module,
        "ImportDeclaration": module,
    }


KINDS: tuple[str, ...] = (*Printer.SIMPLE, *Printer.STATEMENTS)
"""The kinds the printer prints, by their names below `Programs.Cpp`: every one of `Statements.KINDS`, and the
language's `Error`."""


# --- Entry points ---

def print_statement(statement: Any) -> str:
    """A statement's, a declaration's or a member's lines, joined by newlines, without a final one: its record, read
    within the transaction that read it."""
    return "\n".join(Printer().statement_lines(statement, 0))


def print_file(unit: Any) -> str:
    """A translation unit's text, each line ending with a newline (none for an empty unit): its visitor, a
    `Programs.Cpp.TranslationUnit`, read within the transaction that made it."""
    if unit.as_schema().name != f"{LANGUAGE}.TranslationUnit":
        raise TypeError(f"not a {LANGUAGE}.TranslationUnit: {unit.as_schema().name!r}")
    return "".join(line + "\n" for line in Printer().block(_statements(unit, "body"), 0))


def print_module(store: Any, path: str) -> str:
    """The text of the translation unit the workspace holds at `path` (`print_file`), read within a transaction of its
    own, so called with none open on `store`; LookupError where it holds no file there."""
    with store.transaction():
        return print_file(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none
