"""Print: a C translation unit, as the store holds it, printed as C source text in one fixed layout.

A translation unit is a `Programs.C.TranslationUnit` that `Programs.Framework.TheWorkspace` owns by its path; it holds
its tree as one value, its `body`, each declaration and statement holding the statements of its blocks and its parts as
its properties, printed in their order (`Statements`). Where a term holds statements or declarations, a statement
expression's `block`, a struct's or a union's `members` and a conditional directive's `group`, they print within the
term, at the level of the statement that holds it, nested to any depth. The printer reads the tree and writes nothing:

- `print_module(store, path)`: the text of the translation unit at `path`, read within a transaction of its own, so
  called with none open on `store`; LookupError where the workspace holds no file at `path`.
- `print_file(unit)`: the text of a translation unit, given its visitor, within the transaction that made it.
- `print_statement(statement)`: the lines of one statement, declaration or member declaration, its blocks' among them,
  joined by newlines without a final one, given its record (`Terms.kind_of`'s, of the union that holds it), within the
  transaction that read it.

The layout is the 0.3 printer's (`Ccpp/_Printer.py`): four spaces a level, braces on the line that opens them, an empty
block `{}`, one declaration or statement a line; `} else {` and `} while (a);` on the line that closes the block before
them, and `else if` for an `else` that is one `if`; a statement that is no block, the body of an `if`, a loop or a
`switch`, on the next line one level in; `case` and `default` labels one level in from the `switch`, the statements
after them one further, and other labels one level out from their statement; a struct's or a union's members one
level in, a member a line, an enumeration's enumerators so too, each but the last with its comma; directives at the
start of their lines, a conditional's group at its level between them, and a `_Pragma` where a statement stands at
its level *(agent: an operator, written where the source may write it)*; a comment `//` or `/* */` as written
(`Comment.block`), a trailing one (`trailing`) at the end of the line of what it follows.

A statement's expressions are mbse-expressions' C family's terms, written by its printer (`C.Expressions.Text.Printer`,
the family's one printer), which this module's `Printer` extends with the statements and declarations: parenthesized
only where precedence requires, as 0.3 did. `Text.Printer` writes a statement expression's block through `statements`,
a struct's or a union's members through `members`, and a conditional directive's group through `group`, which this
printer overrides to write what the term's property holds, at the level of the statement being printed (`level`).

Decided by the agent where the port left it open, each *(agent)*:

- **A transaction the caller's or its own**, as for TypeScript 5: `print_file` and `print_statement` read the visitors
  they are given, within the caller's transaction; `print_module`, given the store and a path, reads within one of its
  own, so it is called with none open, as transactions do not nest.
- **Statements within a term** are read from the term's own record: `Text.Printer` reads a term as its `Terms.Node`,
  which keeps no record, so this printer keeps the record of each statement expression, struct or union specifier
  and conditional directive it reads, its helpers' among them, and writes its block, members or group from it.
- **A K&R definition's declarations** each on a line of its own, one level in, between its declarator and its body.
- **Every kind prints** (`KINDS`): each of `Statements.KINDS`, and the language's `Error`. A statement of a kind not
  listed is refused, TypeError, rather than printed wrong.
- **Invalid syntax prints as written**, as for TypeScript 5: an `Error` where a statement or a member stands, its text,
  its first line at its level and the others as the source indented them, and nothing for the statements recovered
  within it, which its text holds already; where a `for`'s initializer stands, its text in its place. An `error` or a
  `missing` term, as `Text.Printer` writes it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from mbse.Expressions.C.Expressions import Expressions as CExpressions
from mbse.Expressions.C.Expressions import Text
from mbse.Expressions.C.Expressions.Text import ASSIGNMENT, COMMA, CONDITIONAL
from mbse.Expressions.Framework import Objects, Terms

from ..Framework.Model import WORKSPACE
from .Statements import LANGUAGE

__all__ = ["print_module", "print_file", "print_statement", "Printer", "KINDS"]

_INDENT = "    "
_HOLDERS = ("statementexpression", "classspecifier", "ifdirective", "ifdefdirective", "elifdirective",
            "elifdefdirective", "elsedirective")
"""The terms and helpers whose statements, members or group this printer writes: a statement expression's `block`, a
struct's or a union's `members`, and a conditional directive's `group`."""
_LABELS = ("LabeledStatement", "CaseStatement", "DefaultStatement")


# --- Reading ---

def _held(prop: Any) -> Any:
    """What a property holds, as `Objects.held` reads it (a scalar, a value object's or a union's visitor, or a
    container `Listed`); None where it is not set."""
    found: list[Any] = []
    prop.as_value(lambda a: found.append(Objects.held(a)) or a)
    return found[0] if found else None


def _many(prop: Any) -> list[Any]:
    """A container property's elements, in its order, as `Objects.held` reads it; none where it is not set."""
    held = _held(prop)
    return [] if held is None else list(held.values)


def _kind(node: Any) -> str:
    """A statement's, a member's or a part's kind: its schema's name, without its language's (`IfStatement`)."""
    return node.as_schema().name.rsplit(".", 1)[-1]


def _branch(prop: Any) -> tuple[str, Any] | None:
    """The branch a union property holds, its tag and its record (or term), as `Terms.kind_of` reads it; None where it
    is not set."""
    held = _held(prop)
    return None if held is None else Terms.kind_of(held)


def _one(prop: Any) -> Any:
    """The record of the statement a property of the union `Statement` holds (an `if`'s `consequence`); None where it
    holds none."""
    branch = _branch(prop)
    return None if branch is None else branch[1]


def _statements(node: Any, name: str) -> list[Any]:
    """The statements, members or errors a node's container holds (a unit's or a block's `body`, a member list's
    `members`), in order, each the record of its kind, as its union tags it."""
    return [Terms.kind_of(element)[1] for element in _many(getattr(node, name))]


def _trailing(node: Any) -> bool:
    return _kind(node) == "Comment" and bool(node.trailing.get())


def _declared(specifiers: str, declarator: str) -> str:
    """Specifiers and a declarator, separated by a space where both are written."""
    return f"{specifiers} {declarator}" if specifiers and declarator else specifiers + declarator


def _joined(lines: list[str], tail: list[str]) -> list[str]:
    """`lines`, the first of `tail` on the last of them (`} else {`), and the rest of `tail` after them."""
    lines[-1] += " " + tail[0].lstrip()
    return lines + tail[1:]


def _loop(keyword: str) -> Callable[[Any, Any, int], list[str]]:
    """A `while`'s or a `switch`'s lines: its keyword, its condition, and its body."""
    return lambda self, node, level: self.body(f"{keyword} ({self.e(_held(node.condition), COMMA)})",
                                               _one(node.body), level)


class Printer(Text.Printer):
    """Writes statements, declarations and member declarations as their lines, and their terms and their parts as
    `Text.Printer` writes them, but for a statement expression's block, a struct's or a union's members and a
    conditional directive's group, which it writes as their lines, at the level of the statement being printed
    (`level`)."""

    def __init__(self) -> None:
        super().__init__(CExpressions.DIALECT)
        self.level = 0  # the level of the statement being printed, where a block within a term indents from
        self.records: dict[int, tuple[Any, Any]] = {}  # each holder read, and its record

    def node(self, value: Any) -> Any:
        """A term's `Node` (`Text.Printer.node`), the records of the holders among it and its helpers kept."""
        node = super().node(value)
        if node is not value:
            self.keep(node, Terms.kind_of(value)[1])
        return node

    def keep(self, node: Any, record: Any) -> Any:
        """`node`, a term's or a helper's, its record and its helpers' records kept where they hold what this printer
        writes."""
        if node.kind in _HOLDERS:
            self.records[id(node)] = (node, record)
        held = Objects.properties(record)
        for name, helpers in node.helpers.items():
            values = held[name].values if isinstance(held[name], Objects.Listed) else [held[name]]
            for inner, value in zip(helpers if isinstance(helpers, tuple) else (helpers,), values):
                self.keep(inner, Terms.kind_of(value)[1] if Terms.is_term(value) or _is_union(value) else value)
        return node

    def part(self, value: Any) -> Any:
        """The `Node` of a helper a declaration holds (a specifier, a declarator, an attribute specifier), its holders'
        records kept, a union's branch by its tag, a value object by its schema's name in lower case."""
        if _is_union(value):
            tag, record = Terms.kind_of(value)
        else:
            tag, record = _kind(value).lower(), value
        return self.keep(Terms.node(tag, record), record)

    def written(self, value: Any) -> str:
        """A helper, written: a specifier, a declarator, an attribute specifier, an identifier."""
        return self.text(self.part(value))

    def e(self, value: Any, needed: int) -> str:
        """An expression where one of at least `needed` precedence is needed."""
        return self.expression(value, needed)

    def optional(self, prop: Any, before: str, write: Callable[[Any], str]) -> str:
        """`before` and what a property holds, written by `write`, or nothing where it holds nothing."""
        held = _held(prop)
        return "" if held is None else before + write(held)

    # Blocks

    def block(self, statements: list[Any], level: int) -> list[str]:
        """The lines of a list of statements or members at `level`, a trailing comment on the line before it; after a
        `case` or `default` label, the statements one level further in."""
        lines: list[str] = []
        labelled = False
        for statement in statements:
            if _trailing(statement) and lines:
                lines[-1] += " " + self.remark(statement)
                continue
            if _kind(statement) in ("CaseStatement", "DefaultStatement"):
                labelled = True
                lines += self.statement_lines(statement, level + 1)
            else:
                lines += self.statement_lines(statement, level + 1 if labelled else level)
        return lines

    def braced(self, head: str, body: list[Any], level: int) -> list[str]:
        """`head {`, the body one level in, and `}`; an empty body `{}`."""
        opening = f"{_INDENT * level}{head}{' ' if head else ''}{{"
        if not body:
            return [opening + "}"]
        return [opening, *self.block(body, level + 1), f"{_INDENT * level}}}"]

    def remark(self, node: Any) -> str:
        """A comment, `Programs.C.Comment`, with its delimiters."""
        return f"/*{node.text.get()}*/" if node.block.get() else f"//{node.text.get()}"

    def statement_lines(self, node: Any, level: int) -> list[str]:
        outer, self.level = (self.level, self.depth), level
        self.depth = level
        kind = _kind(node)
        compound = self.STATEMENTS.get(kind)
        if compound is not None:
            lines = compound(self, node, level)
        elif kind in self.SIMPLE:
            lines = [_INDENT * level + self.SIMPLE[kind](self, node)]
        else:
            raise TypeError(f"no printer for the statement kind {node.as_schema().name!r}")
        self.level, self.depth = outer
        return lines

    def body(self, head: str, body: Any, level: int) -> list[str]:
        """`head` and a statement it governs: a block on the same line, another statement on the next."""
        if _kind(body) == "CompoundStatement":
            return self.braced(head, _statements(body, "body"), level)
        inner = level + 2 if _kind(body) in ("CaseStatement", "DefaultStatement") else level + 1  # a label, out
        return [_INDENT * level + head, *self.statement_lines(body, inner)]

    def error(self, node: Any, level: int) -> list[str]:
        """Invalid syntax where a statement or a member stands, `Programs.C.Error`: its text as written, its first line
        at `level` and the others as the source indented them; nothing where it has none. Its `body`, recovered within
        it, is within its text, and is not printed again."""
        text = node.text.get() or ""
        return [_INDENT * level + line if i == 0 else line for i, line in enumerate(text.split("\n"))] if text else []

    # Terms holding this grammar's statements, members or groups, which `Text.Printer` writes through these

    def statements(self, node: Any) -> str:
        """A statement expression's compound statement, its `block`: its lines, one level in from the statement's."""
        branch = _branch(self.records[id(node)][1].block)
        body = [] if branch is None else _statements(branch[1], "body")
        return "\n".join(self.braced("", body, self.level)).lstrip()

    def members(self, node: Any) -> str:
        """A struct's or a union's member declarations, its `members`: one level in from the statement's."""
        branch = _branch(self.records[id(node)][1].members)
        members = [] if branch is None else _statements(branch[1], "members")
        return "\n".join(self.braced("", members, self.level)).lstrip()

    def group(self, node: Any) -> str:
        """A conditional directive's group, the statements or members it governs, at the statement's level."""
        branch = _branch(self.records[id(node)][1].group)
        if branch is None:
            return ""
        tag, group = branch
        return "\n".join(self.block(_statements(group, "body" if tag == "group" else "members"), self.level))

    # Declarations

    def attributes_of(self, node: Any) -> str:
        """A declaration's attribute specifiers, before it, and a space; or nothing."""
        attributes = [self.written(a) for a in _many(node.attributes)]
        return " ".join(attributes) + " " if attributes else ""

    def specifiers_of(self, node: Any) -> str:
        return " ".join(self.written(s) for s in _many(node.specifiers))

    def declarator_of(self, prop: Any) -> str:
        return self.optional(prop, "", self.written)

    def declaration(self, node: Any) -> str:
        """A declaration without its `;`: its attributes, its specifiers and its declarators, each with what initializes
        it."""
        declarators = ", ".join(self.declarator_of(d.declarator) + self.optional(
            d.initializer, " = ", lambda held: self.e(held, ASSIGNMENT)) for d in _many(node.declarators))
        return self.attributes_of(node) + _declared(self.specifiers_of(node), declarators)

    def member_declaration(self, node: Any) -> str:
        """A member declaration: its declarators each with its bit-field's width, `x : 3`, or one alone, `: 0`."""
        declarators = []
        for d in _many(node.declarators):
            written = self.declarator_of(d.declarator)
            declarators.append(written + self.optional(d.bitfield, " : " if written else ": ",
                                                       lambda held: self.e(held, CONDITIONAL)))
        return self.attributes_of(node) + _declared(self.specifiers_of(node), ", ".join(declarators)) + ";"

    def function(self, node: Any, level: int) -> list[str]:
        head = self.attributes_of(node) + _declared(self.specifiers_of(node), self.declarator_of(node.declarator))
        declarations = _many(node.declarations)
        if not declarations:
            return self.braced(head, _statements(_held(node.body), "body"), level)
        return [_INDENT * level + head,
                *(_INDENT * (level + 1) + self.declaration(d) + ";" for d in declarations),
                *self.braced("", _statements(_held(node.body), "body"), level)]

    # Statements

    def if_statement(self, node: Any, level: int) -> list[str]:
        consequence = _one(node.consequence)
        lines = self.body(f"if ({self.e(_held(node.condition), COMMA)})", consequence, level)
        alternative = _one(node.alternative)
        if alternative is None:
            return lines
        if _kind(alternative) == "IfStatement":
            tail = self.if_statement(alternative, level)
            tail[0] = f"{_INDENT * level}else {tail[0].lstrip()}"
        else:
            tail = self.body("else", alternative, level)
        if _kind(consequence) == "CompoundStatement":  # `} else {`
            return _joined(lines, tail)
        return lines + tail

    def do_statement(self, node: Any, level: int) -> list[str]:
        body = _one(node.body)
        lines = self.body("do", body, level)
        tail = f"while ({self.e(_held(node.condition), COMMA)});"
        if _kind(body) == "CompoundStatement":
            return _joined(lines, [tail])
        return [*lines, _INDENT * level + tail]

    def for_statement(self, node: Any, level: int) -> list[str]:
        init = _branch(node.initializer)
        if init is None:
            written = ";"
        elif init[0] == "simpledeclaration":
            written = self.declaration(init[1]) + ";"
        elif init[0] == "error":
            written = init[1].text.get() or ""
        else:
            written = self.e(init[1], COMMA) + ";"
        condition = self.optional(node.condition, " ", lambda held: self.e(held, COMMA))
        increment = self.optional(node.increment, " ", lambda held: self.e(held, COMMA))
        return self.body(f"for ({written}{condition};{increment})", _one(node.body), level)

    def label(self, node: Any, level: int) -> list[str]:
        """A label, one level out from its statement (`case` and `default` one level in from their `switch`, by
        `block`), and its statement: on the label's line where it is a block, on the next line else."""
        kind = _kind(node)
        if kind == "CaseStatement":
            head = "case " + self.e(_held(node.value), CONDITIONAL) + self.optional(
                node.last, " ... ", lambda held: self.e(held, CONDITIONAL))
        else:
            head = "default" if kind == "DefaultStatement" else self.written(_held(node.label))
        outer = max(level - 1, 0)
        statement = _one(node.statement)
        if statement is None:
            return [f"{_INDENT * outer}{head}:"]
        if _kind(statement) == "CompoundStatement":
            return self.braced(head + ":", _statements(statement, "body"), outer)
        return [f"{_INDENT * outer}{head}:", *self.statement_lines(statement, level)]

    def attributed(self, node: Any, level: int) -> list[str]:
        inner = self.statement_lines(_one(node.statement), level)
        head = " ".join(self.written(a) for a in _many(node.attributes))
        rest = inner[0].lstrip()
        inner[0] = f"{_INDENT * level}{head}{'' if rest == ';' else ' '}{rest}"
        return inner

    def directive_lines(self, node: Any, level: int) -> list[str]:
        """A directive, at the start of its line; a conditional's group between its lines, at `level`; a `_Pragma`,
        an operator rather than a line of its own, at `level`, as a statement."""
        written = self.text(self.node(_held(node.directive))).split("\n")
        return [_INDENT * level + written[0]] if _branch(node.directive)[0] == "pragmaexpression" else written

    def asm(self, node: Any) -> str:
        text = node.keyword.get() + "".join(f" {q}" for q in ("volatile", "inline", "goto") if getattr(node, q).get())

        def operand(o: Any) -> str:
            name = self.optional(o.name, "", lambda held: f"[{self.written(held)}] ")
            return f"{name}{self.e(_held(o.constraint), ASSIGNMENT)} ({self.e(_held(o.value), COMMA)})"

        sections = [", ".join(operand(o) for o in _many(node.outputs)),
                    ", ".join(operand(o) for o in _many(node.inputs)),
                    ", ".join(self.e(c, ASSIGNMENT) for c in _many(node.clobbers)),
                    ", ".join(self.written(label) for label in _many(node.labels))]
        while sections and not sections[-1]:
            sections.pop()
        inner = self.e(_held(node.template), ASSIGNMENT) + "".join(" :" + (f" {s}" if s else "") for s in sections)
        return f"{text}({inner});"

    def goto(self, node: Any) -> str:
        target = _held(node.target)
        if target is not None:
            return f"goto *{self.e(target, Text.UNARY)};"
        return f"goto {self.written(_held(node.label))};"

    def static_assert(self, node: Any) -> str:
        message = self.optional(node.message, ", ", lambda held: self.e(held, ASSIGNMENT))
        return f"{node.keyword.get()}({self.e(_held(node.condition), ASSIGNMENT)}{message});"

    STATEMENTS: ClassVar[dict[str, Callable[[Printer, Any, int], list[str]]]] = {
        "CompoundStatement": lambda self, node, level: self.braced("", _statements(node, "body"), level),
        "IfStatement": if_statement, "WhileStatement": _loop("while"), "SwitchStatement": _loop("switch"),
        "DoStatement": do_statement,
        "ForStatement": for_statement, "LabeledStatement": label, "CaseStatement": label, "DefaultStatement": label,
        "AttributedStatement": attributed, "FunctionDefinition": function, "Directive": directive_lines, "Error": error,
    }

    SIMPLE: ClassVar[dict[str, Callable[[Printer, Any], str]]] = {
        "Comment": remark,
        "ExpressionStatement": lambda self, node: self.optional(node.expression, "", lambda held: self.e(
            held, COMMA)) + ";",
        "BreakStatement": lambda self, node: "break;", "ContinueStatement": lambda self, node: "continue;",
        "ReturnStatement": lambda self, node: "return" + self.optional(
            node.value, " ", lambda held: self.e(held, COMMA)) + ";",
        "GotoStatement": goto, "AsmDeclaration": asm,
        "SimpleDeclaration": lambda self, node: self.declaration(node) + ";",
        "StaticAssertDeclaration": static_assert,
        "AttributeDeclaration": lambda self, node: self.attributes_of(node).rstrip() + ";",
        "MemberDeclaration": member_declaration,
    }


def _is_union(value: Any) -> bool:
    """Whether `value` is the visitor of a union's value, whose branch `Terms.kind_of` reads."""
    from mbse.Schemas.Framework import Schemas
    return isinstance(value.as_schema(), Schemas.OfUnion.Data)


KINDS: tuple[str, ...] = (*Printer.SIMPLE, *Printer.STATEMENTS)
"""The kinds the printer prints, by their names below `Programs.C`: every one of `Statements.KINDS`, and the
language's `Error`."""


# --- Entry points ---

def print_statement(statement: Any) -> str:
    """A statement's, a declaration's or a member's lines, its blocks' among them, joined by newlines, without a final
    one: its record, read within the transaction that read it."""
    return "\n".join(Printer().statement_lines(statement, 0))


def print_file(unit: Any) -> str:
    """A translation unit's text, each line ending with a newline (none for an empty unit): its visitor, a
    `Programs.C.TranslationUnit`, read within the transaction that made it."""
    if unit.as_schema().name != f"{LANGUAGE}.TranslationUnit":
        raise TypeError(f"not a {LANGUAGE}.TranslationUnit: {unit.as_schema().name!r}")
    return "".join(line + "\n" for line in Printer().block(_statements(unit, "body"), 0))


def print_module(store: Any, path: str) -> str:
    """The text of the translation unit the workspace holds at `path` (`print_file`), read within a transaction of its
    own, so called with none open on `store`; LookupError where it holds no file there."""
    with store.transaction():
        return print_file(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none
