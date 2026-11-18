"""Print: a TypeScript 5 program, as the store holds it, printed as TypeScript source text in one fixed layout.

A program is a `Programs.TypeScript5.Program` that `Programs.Framework.TheWorkspace` owns by its path; it holds its tree
as one value, its `body`, each statement holding the statements of its blocks, its clauses, its class members and its
parts as its properties, printed in their order (`Statements`). Where a term holds statements, a function's or an
arrow's `block` or a class expression's `classBody`, they print within the term, at the level of the statement that
holds it, nested to any depth. The printer reads the tree and writes nothing:

- `print_module(store, path)`: the text of the program at `path`, read within a transaction of its own, so called with
  none open on `store`; LookupError where the workspace holds no file at `path`.
- `print_file(program)`: the text of a program, given its visitor, within the transaction that made it.
- `print_statement(statement)`: the lines of one statement, clause or class member, its blocks' among them, joined by
  newlines without a final one, given its record (`Terms.kind_of`'s, of the union that holds it), within the
  transaction that read it.

The layout is the 0.3 printer's (`TypeScript/_Printer.py`): four spaces a level, braces on the line that opens them, an
empty block `{}`, one statement or member a line, and a semicolon after every statement that takes one; `} else {`,
`} catch (e) {`, `} finally {` and `} while (a);` on the line that closes the block before them, and `else if` for an
`else` that is one `if`; a statement that is no block, the body of an `if`, a loop or a `with`, on the next line one
level in; decorators each on a line of their own before what they decorate, `export` after them; an enum's members one
a line, each with its comma; a comment `//` or `/* */` as written (`Comment.block`), a trailing one (`trailing`) at the
end of the line of what it follows, the first of a block on the line that opens it.

A statement's expressions are mbse-expressions' TypeScript family's terms, written by its printer
(`TypeScript5.Text.Printer`), which this module's `Printer` extends with the statements: parenthesized only where
precedence requires, as 0.3 did, and also where an expression statement would start with `{`, `function`, `class` or
`let [`, a default export with `function` or `class`, and where a `for`'s initializer holds `in` outside parentheses,
which would read as a `for ... in`. Where `Text.Printer` writes a function's, an arrow's, a class expression's or an
object method's statements `{}`, this one writes the block or the class body the term's `block` or `classBody` holds:
its statements one level in from the statement that holds the term, its closing brace at that statement's level. An
object type with comments is written on its members' lines at the same levels; without, on one line, as `Text.Printer`
writes it.

Decided by the agent where the port left it open, each *(agent)*:

- **A transaction the caller's or its own**, as for Python 3 (`Python3.Print`): `print_file` and `print_statement` read
  the visitors they are given, within the caller's transaction; `print_module`, given the store and a path, reads
  within one of its own, so it is called with none open, as transactions do not nest.
- **Statements within a term** are read from the term's own record: `Text.Printer` reads a term as its `Terms.Node`,
  which keeps no record, so this printer keeps the record of each function, arrow and class expression it reads, and
  writes its block from it.
- **A clause or a member prints alone** (`print_statement`): a `catch` clause as `catch (e) { ... }`, a `switch`'s case
  as `case a:` and its statements one level in, a static block as `static { ... }`, a class member as in its class.
- **Every kind prints** (`KINDS`): each of `Statements.KINDS`, its statements, clauses and class members; the
  language's `Error`; and the members of a class body or an interface that are `TypeScript Types`' (an index
  signature, a property, method, call or construct signature). A statement of a kind not listed is refused, TypeError,
  rather than printed wrong.
- **Invalid syntax prints as written**, as for Python 3: an `Error` where a statement, a clause or a member stands, its
  text, its first line at its level and the others as the source indented them, and nothing for the statements
  recovered within it, which its text holds already; an `Error` with no text, nothing. Where a part stands (a `for`'s
  initializer or left side, a default export's declaration, an import's specifier, a module's name or reference, an
  enum's member), its text in the part's place; a `catch` clause's on the line that closes the `try`'s block, as a
  clause's would be. An `error` or a `missing` term, as `Text.Printer` writes it.
- **No validation**: the 0.3 printer validated a tree and checked it against a standard before printing; this one
  prints what the store holds, validation being a check of its own, not yet ported.
- **Within an expression, `Text.Printer`'s choices stand**: a literal in its spelling, else its value's default one (a
  string in double quotes); an arrow's lone type parameter without a constraint `<T,>` in every file, where 0.3 wrote it
  so only for JSX.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from mbse.Expressions.Framework import Objects, Terms
from mbse.Expressions.TypeScript.TypeScript5 import Text
from mbse.Expressions.TypeScript.TypeScript5.Text import ASSIGN, MEMBER, SEQUENCE, UNARY

from ..Framework.Model import WORKSPACE
from .Statements import LANGUAGE

__all__ = ["print_module", "print_file", "print_statement", "Printer", "KINDS"]

_INDENT = "    "
_HOLDERS = ("functionexpression", "arrowfunctionexpression", "classexpression")
"""The terms whose statements this printer writes: a function's and an arrow's `block`, a class's `classBody`."""

_SIGNATURES = ("TSIndexSignature", "TSPropertySignature", "TSMethodSignature", "TSCallSignatureDeclaration",
               "TSConstructSignatureDeclaration")
"""`TypeScript Types`' members of a class body (an index signature) or an interface (each), each written with its
`;`."""


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
    """A statement's, a clause's, a member's or a part's kind: its schema's name, without its language's
    (`IfStatement`)."""
    return node.as_schema().name.rsplit(".", 1)[-1]


def _branch(prop: Any) -> tuple[str, Any] | None:
    """The branch a union property holds, its tag and its record (or term), as `Terms.kind_of` reads it; None where it
    is not set."""
    held = _held(prop)
    return None if held is None else Terms.kind_of(held)


def _one(prop: Any) -> Any:
    """The record of the statement a property of the union `Statement` holds (an `if`'s `consequent`); None where it
    holds none."""
    branch = _branch(prop)
    return None if branch is None else branch[1]


def _statements(node: Any, name: str) -> list[Any]:
    """The statements, clauses, members or errors a node's container holds (a program's or a block's `body`, a
    `switch`'s `cases`, a class body's `body`), in order, each the record of its kind, as its union tags it."""
    return [Terms.kind_of(element)[1] for element in _many(getattr(node, name))]


def _body(block: Any) -> list[Any]:
    """The statements of a block (a `BlockStatement`, a `ClassBody`, a `TSModuleBlock`), or none where there is none."""
    return [] if block is None else _statements(block, "body")


def _comment(node: Any) -> bool:
    return _kind(node) == "Comment"


def _trailing(node: Any) -> bool:
    return _comment(node) and bool(node.trailing.get())


def _error_text(node: Any) -> str:
    """Invalid syntax where a part stands: its text as written, or nothing."""
    return node.text.get() or ""


def _joined(lines: list[str], tail: list[str]) -> list[str]:
    """`lines`, the first of `tail` on the last of them (`} else {`), and the rest of `tail` after them."""
    if tail:
        lines[-1] += " " + tail[0].lstrip()
    return lines + tail[1:]


class Printer(Text.Printer):
    """Writes statements, clauses and class members as their lines, and their terms as `Text.Printer` writes them, but
    for a function's, an arrow's, a class expression's and an object method's statements, which it writes as their
    blocks' lines, at the level of the statement being printed (`level`)."""

    def __init__(self) -> None:
        super().__init__()
        self.level = 0  # the level of the statement being printed, where a block within a term indents from
        self.records: dict[int, tuple[Any, Any]] = {}  # each function, arrow and class term read, and its record
        self.texts = {**self.texts, "tstypeliteral": Printer.type_literal}

    def node(self, value: Any) -> Any:
        """A term's `Node` (`Text.Printer.node`); the record of a function, an arrow or a class kept, whose block or
        class body it writes."""
        node = super().node(value)
        if node is not value and node.kind in _HOLDERS:
            self.records[id(node)] = (node, Terms.kind_of(value)[1])
        return node

    def part(self, value: Any) -> Any:
        """A part's `Node`, a value object a statement holds that `Text.Printer` writes (an `Identifier`, a `Literal`,
        a `TSTypeParameterDeclaration`), its kind its schema's name in lower case."""
        return Terms.node(_kind(value).lower(), value)

    def written(self, value: Any) -> str:
        """A part, written: an identifier, a literal, a type parameters' declaration or instantiation."""
        return self.text(self.part(value))

    def name(self, prop: Any) -> str:
        """The part a property holds, written."""
        return self.written(_held(prop))

    def optional(self, prop: Any, before: str, write: Callable[[Any], str]) -> str:
        """`before` and what a property holds, written by `write`, or nothing where it holds nothing."""
        held = _held(prop)
        return "" if held is None else before + write(held)

    def annotation_of(self, prop: Any) -> str:
        """A `TSTypeAnnotation` a property holds, `: T`, or nothing."""
        return self.optional(prop, ": ", lambda held: self.t(self.part(held).subterms["typeAnnotation"],
                                                             self.types.FUNCTION))

    def type_parameters(self, node: Any) -> str:
        return self.optional(node.typeParameters, "", self.written)

    # Blocks

    def block(self, statements: list[Any], level: int) -> list[str]:
        """The lines of a list of statements or members, a trailing comment on the line before it."""
        lines: list[str] = []
        for statement in statements:
            if _trailing(statement) and lines:
                lines[-1] += " " + self.comment(statement)
                continue
            lines += self.lines(statement, level)
        return lines

    def braced(self, head: str, body: list[Any], level: int) -> list[str]:
        """`head {`, the body one level in, and `}`; a trailing comment first in the body goes on the head's line."""
        lines = [f"{_INDENT * level}{head}{' ' if head else ''}{{"]
        if body and _trailing(body[0]):
            lines[0] += " " + self.comment(body[0])
            body = body[1:]
        if not body and lines[0].endswith("{"):
            return [lines[0] + "}"]
        return [*lines, *self.block(body, level + 1), f"{_INDENT * level}}}"]

    def inline(self, body: list[Any]) -> str:
        """A block within a term: its lines joined, its body one level in from the statement's."""
        return "\n".join(self.braced("", body, self.level)).lstrip()

    def comment(self, node: Any) -> str:
        return f"/*{node.text.get()}*/" if node.block.get() else f"//{node.text.get()}"

    def lines(self, node: Any, level: int) -> list[str]:
        outer, self.level = self.level, level
        kind = _kind(node)
        compound = self.STATEMENTS.get(kind)
        if compound is not None:
            lines = compound(self, node, level)
        elif kind in self.SIMPLE:
            lines = [_INDENT * level + self.SIMPLE[kind](self, node)]
        else:
            raise TypeError(f"no printer for the statement kind {node.as_schema().name!r}")
        self.level = outer
        return lines

    def body(self, head: str, body: Any, level: int) -> list[str]:
        """`head` and a statement it governs: a block on the same line, another statement on the next."""
        if _kind(body) == "BlockStatement":
            return self.braced(head, _body(body), level)
        return [_INDENT * level + head, *self.lines(body, level + 1)]

    def error(self, node: Any, level: int) -> list[str]:
        """Invalid syntax where a statement, a clause or a member stands, `Programs.TypeScript5.Error`: its text as
        written, its first line at `level` and the others as the source indented them; nothing where it has none. Its
        `body`, recovered within it, are within its text, and are not printed again."""
        text = _error_text(node)
        return [_INDENT * level + line if i == 0 else line for i, line in enumerate(text.split("\n"))] if text else []

    # Terms within statements: a block or a class body where `Text.Printer` writes `{}`

    def held_block(self, node: Any, name: str) -> list[Any]:
        """The statements or members a function's, an arrow's or a class's `block` or `classBody` holds."""
        branch = _branch(getattr(self.records[id(node)][1], name))
        return [] if branch is None else _body(branch[1])

    def _functionexpression(self, node: Any) -> str:
        return super()._functionexpression(node)[:-2] + self.inline(self.held_block(node, "block"))

    def _arrowfunctionexpression(self, node: Any) -> str:
        text = super()._arrowfunctionexpression(node)
        if node.subterms["body"] is not None:
            return text
        return text[:-2] + self.inline(self.held_block(node, "block"))

    def _classexpression(self, node: Any) -> str:
        return super()._classexpression(node)[:-2] + self.inline(self.held_block(node, "classBody"))

    def _property(self, node: Any) -> str:
        """An object's property; a method's or an accessor's statements, its value's block."""
        text = super()._property(node)
        value = self.node(node.subterms["value"])
        attributes = node.attributes
        if value.kind != "functionexpression" or attributes.get("shorthand") or not (
                attributes.get("method") or attributes.get("propertyKind") in ("get", "set")):
            return text
        return text[:-2] + self.inline(self.held_block(value, "block"))

    def type_literal(self, node: Any) -> str:
        """An object type: on one line, as `Text.Printer` writes it, or with comments on its members' lines, one level
        in from the statement's, a trailing comment on the line before it."""
        members = node.helpers.get("members", ())
        if all(member.kind != "comment" for member in members):
            return self.types.TEXTS["tstypeliteral"](self, node)
        lines = ["{"]
        for member in members:
            attributes = member.attributes
            if member.kind == "comment":
                text = f"/*{attributes['text']}*/" if attributes.get("block") else f"//{attributes['text']}"
                if attributes.get("trailing"):
                    lines[-1] += " " + text
                    continue
            else:
                text = self.text(member) + ";"
            lines.append(_INDENT * (self.level + 1) + text)
        return "\n".join([*lines, _INDENT * self.level + "}"])

    def has_in(self, value: Any) -> bool:
        """Whether an expression holds an `in` operator outside parentheses."""
        node = self.node(value)
        subterms = node.subterms
        if node.kind == "binaryexpression" and node.attributes["operator"] == "in":
            return True
        if node.kind in ("binaryexpression", "logicalexpression", "assignmentexpression"):
            return self.has_in(subterms["left"]) or self.has_in(subterms["right"])
        if node.kind == "conditionalexpression":
            return any(self.has_in(subterms[name]) for name in ("test", "consequent", "alternate"))
        if node.kind == "sequenceexpression":
            return any(self.has_in(expression) for expression in node.many)
        if node.kind in ("tsasexpression", "tssatisfiesexpression"):
            return self.has_in(subterms["expression"])
        if node.kind == "arrowfunctionexpression":
            return subterms["body"] is not None and self.has_in(subterms["body"])
        return False

    def initializer(self, value: Any, needed: int) -> str:
        """An expression in a `for`'s initializer: parenthesized where it binds less than its place needs, or holds
        `in` outside parentheses, which would read as a `for ... in`."""
        node = self.node(value)
        text = self.text(node)
        return f"({text})" if self.precedence(node) < needed or self.has_in(node) else text

    def opening(self, value: Any, needed: int, kinds: tuple[str, ...]) -> str:
        """An expression where a statement starts, written for a place that needs `needed`, parenthesized where it
        would start with one of `kinds`, or with `let [`."""
        text = self.e(value, needed)
        start = self.leftmost(value)
        if start.kind in kinds or (start.kind == "identifier" and start.attributes.get("name") == "let"
                                   and text.startswith("let[")):
            return f"({text})"
        return text

    # Statements

    def expression_statement(self, node: Any) -> str:
        kinds = ("objectexpression", "functionexpression", "classexpression", "objectpattern")
        return self.opening(_held(node.expression), SEQUENCE, kinds) + ";"

    def declaration(self, node: Any, expression: Callable[[Any, int], str]) -> str:
        """A variable declaration without its `;`, its initializers written by `expression` (`e`, or `initializer`
        in a `for`)."""
        declarators = ", ".join(self.declarator(d, expression) for d in _many(node.declarations))
        return f"{'declare ' if node.declare.get() else ''}{node.declarationKind.get()} {declarators}"

    def declarator(self, node: Any, expression: Callable[[Any, int], str]) -> str:
        target = _held(node.id)
        text = self.text(target)
        if node.definite.get():  # `id!: type`, where `id` is a name
            name = self.node(target)
            text = name.attributes["name"] + ("?" if name.attributes.get("optional") else "") + "!" + self.annotation(
                name)
        return text + self.optional(node.init, " = ", lambda held: expression(held, ASSIGN))

    def if_statement(self, node: Any, level: int) -> list[str]:
        consequent = _one(node.consequent)
        lines = self.body(f"if ({self.e(_held(node.test), SEQUENCE)})", consequent, level)
        alternate = _one(node.alternate)
        if alternate is None:
            return lines
        if _kind(alternate) == "IfStatement":
            tail = self.if_statement(alternate, level)
            tail[0] = f"{_INDENT * level}else {tail[0].lstrip()}"
        else:
            tail = self.body("else", alternate, level)
        if _kind(consequent) == "BlockStatement":  # `} else {`
            return _joined(lines, tail)
        return lines + tail

    def while_statement(self, node: Any, level: int) -> list[str]:
        return self.body(f"while ({self.e(_held(node.test), SEQUENCE)})", _one(node.body), level)

    def do_while(self, node: Any, level: int) -> list[str]:
        body = _one(node.body)
        lines = self.body("do", body, level)
        tail = f"while ({self.e(_held(node.test), SEQUENCE)});"
        if _kind(body) == "BlockStatement":
            return _joined(lines, [tail])
        return [*lines, _INDENT * level + tail]

    def for_part(self, branch: tuple[str, Any], expression: Callable[[Any, int], str], needed: int) -> str:
        """A `for`'s initializer or left side, a union's branch: a declaration, a term or a pattern, its expressions
        written by `expression` (`e`, or `initializer`), the term or pattern for a place that needs `needed`; or
        invalid syntax as written."""
        tag, held = branch
        if tag == "variabledeclaration":
            return self.declaration(held, expression)
        if tag == "error":
            return _error_text(held)
        return expression(held, needed)

    def for_statement(self, node: Any, level: int) -> list[str]:
        init = _branch(node.init)
        written = "" if init is None else self.for_part(init, self.initializer, SEQUENCE)
        test = self.optional(node.test, " ", lambda held: self.e(held, SEQUENCE))
        update = self.optional(node.update, " ", lambda held: self.e(held, SEQUENCE))
        return self.body(f"for ({written};{test};{update})", _one(node.body), level)

    def for_in(self, node: Any, level: int) -> list[str]:
        left = self.for_part(_branch(node.left), self.e, UNARY)
        return self.body(f"for ({left} in {self.e(_held(node.right), SEQUENCE)})", _one(node.body), level)

    def for_of(self, node: Any, level: int) -> list[str]:
        branch = _branch(node.left)
        left = self.for_part(branch, self.e, MEMBER)
        awaits = bool(node.isAwait.get())
        if not awaits and branch[0] == "pattern" and left == "async":
            left = f"({left})"  # `for (async of ...)` would start an arrow
        keyword = "for await" if awaits else "for"
        return self.body(f"{keyword} ({left} of {self.e(_held(node.right), ASSIGN)})", _one(node.body), level)

    def switch(self, node: Any, level: int) -> list[str]:
        lines = [f"{_INDENT * level}switch ({self.e(_held(node.discriminant), SEQUENCE)}) {{"]
        for case in _statements(node, "cases"):
            lines += self.lines(case, level + 1)
        return [*lines, f"{_INDENT * level}}}"]

    def case(self, node: Any, level: int) -> list[str]:
        test = _held(node.test)
        lines = [_INDENT * level + ("default:" if test is None else f"case {self.e(test, SEQUENCE)}:")]
        body = _statements(node, "consequent")
        if body and _trailing(body[0]):
            lines[0] += " " + self.comment(body[0])
            body = body[1:]
        return lines + self.block(body, level + 1)

    def try_statement(self, node: Any, level: int) -> list[str]:
        lines = self.braced("try", _body(_held(node.block)), level)
        handler = _one(node.handler)
        if handler is not None:
            lines = _joined(lines, self.lines(handler, level))
        finalizer = _held(node.finalizer)
        if finalizer is not None:
            lines = _joined(lines, self.braced("finally", _body(finalizer), level))
        return lines

    def catch(self, node: Any, level: int) -> list[str]:
        head = "catch" + self.optional(node.param, " ", lambda held: f"({self.text(held)})")
        return self.braced(head, _body(_held(node.body)), level)

    def labeled(self, node: Any, level: int) -> list[str]:
        inner = self.lines(_one(node.body), level)
        inner[0] = f"{_INDENT * level}{self.name(node.label)}: {inner[0].lstrip()}"
        return inner

    def signature_of(self, node: Any) -> str:
        """A function declaration's `<typeParameters>(params): returnType`."""
        params = ", ".join(self.text(parameter) for parameter in _many(node.params))
        return f"{self.type_parameters(node)}({params}){self.annotation_of(node.returnType)}"

    def function(self, node: Any, level: int) -> list[str]:
        keyword = ("async " if node.isAsync.get() else "") + "function" + ("*" if node.generator.get() else "")
        head = keyword + self.optional(node.id, " ", self.written) + self.signature_of(node)
        if _kind(node) == "TSDeclareFunction":
            return [f"{_INDENT * level}{'declare ' if node.declare.get() else ''}{head};"]
        return self.braced(head, _body(_held(node.body)), level)

    def decorators_of(self, node: Any, level: int) -> list[str]:
        return [f"{_INDENT * level}@{self.e(_held(d.expression), MEMBER)}" for d in _many(node.decorators)]

    def class_declaration(self, node: Any, level: int) -> list[str]:
        head = ("declare " if node.declare.get() else "") + ("abstract " if node.abstract.get() else "") + "class"
        head += self.optional(node.id, " ", self.written) + self.type_parameters(node)
        superclass = _held(node.superClass)
        if superclass is not None:
            head += f" extends {self.e(superclass, MEMBER)}" + self.optional(node.superTypeArguments, "", self.written)
        implements = _many(node.implements)
        if implements:
            head += " implements " + ", ".join(self.heritage(self.part(i)) for i in implements)
        return [*self.decorators_of(node, level), *self.braced(head, _body(_held(node.body)), level)]

    def member_modifiers(self, node: Any) -> str:
        """A class member's modifiers, in the order TypeScript requires."""
        abstract = _kind(node).startswith("TSAbstract")
        words = [node.accessibility.get()] if node.accessibility.get() else []
        flags = (("declare", "declare" in node.as_schema().properties and node.declare.get()),
                 ("static", node.static.get()), ("abstract", abstract), ("override", node.override.get()),
                 ("readonly", "readonly" in node.as_schema().properties and node.readonly.get()))
        return "".join(w + " " for w in words + [word for word, flag in flags if flag])

    def member_key(self, node: Any) -> str:
        return self.key(_held(node.key), bool(node.computed.get())) + ("?" if node.optional.get() else "")

    def method(self, node: Any, level: int) -> list[str]:
        value = self.node(_held(node.value))
        attributes = value.attributes
        head = self.member_modifiers(node) + ("async " if attributes.get("isAsync") else "") + (
            "*" if attributes.get("generator") else "")
        if node.methodKind.get() in ("get", "set"):
            head += node.methodKind.get() + " "
        head += self.member_key(node) + self.signature(value)
        decorators = self.decorators_of(node, level)
        if value.kind == "tsemptybodyfunctionexpression":
            return decorators + [f"{_INDENT * level}{head};"]
        return decorators + self.braced(head, self.held_block(value, "block"), level)

    def property_definition(self, node: Any, level: int) -> list[str]:
        head = self.member_modifiers(node) + ("accessor " if _kind(node).endswith("AccessorProperty") else "")
        head += self.member_key(node) + ("!" if node.definite.get() else "") + self.annotation_of(node.typeAnnotation)
        head += self.optional(node.value, " = ", lambda held: self.e(held, ASSIGN))
        return [*self.decorators_of(node, level), f"{_INDENT * level}{head};"]

    def interface(self, node: Any, level: int) -> list[str]:
        head = f"{'declare ' if node.declare.get() else ''}interface {self.name(node.id)}{self.type_parameters(node)}"
        heritages = _many(node.extends)
        if heritages:
            head += " extends " + ", ".join(self.heritage(self.part(h)) for h in heritages)
        return self.braced(head, _body(_held(node.body)), level)

    def enum(self, node: Any, level: int) -> list[str]:
        head = ("declare " if node.declare.get() else "") + ("const " if node.const.get() else "")
        head += f"enum {self.name(node.id)}"
        lines = [f"{_INDENT * level}{head} {{"]
        body = _held(node.body)
        members = [] if body is None else _statements(body, "members")
        for member in members:  # each on its line, with a comma; a trailing comment on the line before it
            kind = _kind(member)
            if kind == "Comment" and member.trailing.get():
                lines[-1] += " " + self.comment(member)
            elif kind == "Comment":
                lines.append(_INDENT * (level + 1) + self.comment(member))
            elif kind == "Error":
                lines += self.error(member, level + 1)
            else:
                initializer = self.optional(member.initializer, " = ", lambda held: self.e(held, ASSIGN))
                lines.append(f"{_INDENT * (level + 1)}{self.key(_held(member.id), bool(member.computed.get()))}"
                             f"{initializer},")
        if len(lines) == 1:
            return [lines[0] + "}"]
        return [*lines, f"{_INDENT * level}}}"]

    def module_name(self, prop: Any) -> str:
        """A module's name or an import-equals' reference, a union's branch: a part, a module reference, or invalid
        syntax as written."""
        tag, held = _branch(prop)
        if tag == "error":
            return _error_text(held)
        if tag == "tsexternalmodulereference":
            return f"require({self.name(held.expression)})"
        return self.text(Terms.node(tag, held))

    def module(self, node: Any, level: int) -> list[str]:
        head = "declare " if node.declare.get() else ""
        kind = node.moduleKind.get()
        head += "global" if kind == "global" else f"{kind} {self.module_name(node.id)}"
        body = _held(node.body)
        if body is None:
            return [f"{_INDENT * level}{head};"]
        return self.braced(head, _body(body), level)

    def exported(self, inner: list[str], keyword: str, level: int) -> list[str]:
        """A declaration's lines, `keyword` before it after its decorators (`export`, `export default`)."""
        index = next(i for i, line in enumerate(inner) if not line.lstrip().startswith("@"))
        inner[index] = f"{_INDENT * level}{keyword} {inner[index].lstrip()}"
        return inner

    def export_named(self, node: Any, level: int) -> list[str]:
        declaration = _one(node.declaration)
        if declaration is not None:
            return self.exported(self.lines(declaration, level), "export", level)
        kind = "type " if node.exportKind.get() == "type" else ""
        text = f"export {kind}{{{', '.join(self.specifier(s) for s in _many(node.specifiers))}}}"
        text += self.optional(node.source, " from ", self.written)
        return [_INDENT * level + text + self.with_attributes(node.attributes) + ";"]

    def export_default(self, node: Any, level: int) -> list[str]:
        tag, held = _branch(node.declaration)
        if tag == "statement":
            return self.exported(self.lines(Terms.kind_of(held)[1], level), "export default", level)
        if tag == "error":
            return [f"{_INDENT * level}export default {_error_text(held)}"]
        text = self.opening(held, ASSIGN, ("functionexpression", "classexpression"))
        return [f"{_INDENT * level}export default {text};"]

    def specifier(self, node: Any) -> str:
        """An export's specifier, `a`, `a as b`, `type a`."""
        local, exported = self.text(_held(node.local)), self.text(_held(node.exported))
        return ("type " if node.exportKind.get() == "type" else "") + (
            local if local == exported else f"{local} as {exported}")

    def with_attributes(self, prop: Any) -> str:
        attributes = _many(prop)
        if not attributes:
            return ""
        return " with { " + ", ".join(f"{self.text(_held(a.key))}: {self.name(a.value)}" for a in attributes) + " }"

    STATEMENTS: ClassVar[dict[str, Callable[[Printer, Any, int], list[str]]]] = {
        "BlockStatement": lambda self, node, level: self.braced("", _body(node), level),
        "IfStatement": if_statement, "WhileStatement": while_statement, "DoWhileStatement": do_while,
        "ForStatement": for_statement, "ForInStatement": for_in, "ForOfStatement": for_of,
        "SwitchStatement": switch, "SwitchCase": case, "TryStatement": try_statement, "CatchClause": catch,
        "LabeledStatement": labeled,
        "WithStatement": lambda self, node, level: self.body(f"with ({self.e(_held(node.object), SEQUENCE)})",
                                                             _one(node.body), level),
        "FunctionDeclaration": function, "TSDeclareFunction": function, "ClassDeclaration": class_declaration,
        "MethodDefinition": method, "TSAbstractMethodDefinition": method,
        "PropertyDefinition": property_definition, "TSAbstractPropertyDefinition": property_definition,
        "AccessorProperty": property_definition, "TSAbstractAccessorProperty": property_definition,
        "StaticBlock": lambda self, node, level: self.braced("static", _statements(node, "body"), level),
        "TSInterfaceDeclaration": interface, "TSEnumDeclaration": enum, "TSModuleDeclaration": module,
        "ExportNamedDeclaration": export_named, "ExportDefaultDeclaration": export_default, "Error": error,
    }

    def import_specifier(self, tag: str, node: Any) -> str:
        """An import's specifier, a union's branch: `a`, `a as b`, `type a`, `* as a`, or invalid syntax as
        written."""
        if tag == "error":
            return _error_text(node)
        local = self.name(node.local)
        if tag == "importdefaultspecifier":
            return local
        if tag == "importnamespacespecifier":
            return f"* as {local}"
        imported = self.text(_held(node.imported))
        return ("type " if node.importKind.get() == "type" else "") + (
            imported if imported == local else f"{imported} as {local}")

    def import_declaration(self, node: Any) -> str:
        head = "import " + ("type " if node.importKind.get() == "type" else "") + (
            "defer " if node.phase.get() == "defer" else "")
        tail = f"{self.name(node.source)}{self.with_attributes(node.attributes)};"
        specifiers = [Terms.kind_of(s) for s in _many(node.specifiers)]
        if not specifiers:
            return head + tail
        parts = [self.import_specifier(tag, s) for tag, s in specifiers if tag != "importspecifier"]
        named = [self.import_specifier(tag, s) for tag, s in specifiers if tag == "importspecifier"]
        if named:
            parts.append("{" + ", ".join(named) + "}")
        return f"{head}{', '.join(parts)} from {tail}"

    def export_all(self, node: Any) -> str:
        text = "export " + ("type " if node.exportKind.get() == "type" else "") + "*"
        text += self.optional(node.exported, " as ", self.text)
        return f"{text} from {self.name(node.source)}{self.with_attributes(node.attributes)};"

    def import_equals(self, node: Any) -> str:
        kind = "type " if node.importKind.get() == "type" else ""
        return f"import {kind}{self.name(node.id)} = {self.module_name(node.moduleReference)};"

    def type_alias(self, node: Any) -> str:
        return (f"{'declare ' if node.declare.get() else ''}type {self.name(node.id)}{self.type_parameters(node)} = "
                f"{self.t(_held(node.typeAnnotation), self.types.FUNCTION)};")

    def jump(self, keyword: str, node: Any) -> str:
        return keyword + self.optional(node.label, " ", self.written) + ";"

    SIMPLE: ClassVar[dict[str, Callable[[Printer, Any], str]]] = {
        "Comment": comment, "ExpressionStatement": expression_statement,
        "VariableDeclaration": lambda self, node: self.declaration(node, self.e) + ";",
        "EmptyStatement": lambda self, node: ";", "DebuggerStatement": lambda self, node: "debugger;",
        "ReturnStatement": lambda self, node: "return" + self.optional(
            node.argument, " ", lambda held: self.e(held, SEQUENCE)) + ";",
        "ThrowStatement": lambda self, node: f"throw {self.e(_held(node.argument), SEQUENCE)};",
        "BreakStatement": lambda self, node: self.jump("break", node),
        "ContinueStatement": lambda self, node: self.jump("continue", node),
        "ImportDeclaration": import_declaration, "ExportAllDeclaration": export_all,
        "TSImportEqualsDeclaration": import_equals,
        "TSExportAssignment": lambda self, node: f"export = {self.e(_held(node.expression), ASSIGN)};",
        "TSNamespaceExportDeclaration": lambda self, node: f"export as namespace {self.name(node.id)};",
        "TSTypeAliasDeclaration": type_alias,
        **{kind: lambda self, node: self.text(self.part(node)) + ";" for kind in _SIGNATURES},
    }


KINDS: tuple[str, ...] = (*Printer.SIMPLE, *Printer.STATEMENTS)
"""The kinds the printer prints, by their names below `Programs.TypeScript5` (and `TypeScript Types`' signatures, below
`Expressions.TypeScript.Types`): every one of `Statements.KINDS`, the language's `Error`, and the members of a class
body or an interface that are `TypeScript Types`'."""


# --- Entry points ---

def print_statement(statement: Any) -> str:
    """A statement's, a clause's or a member's lines, its blocks' among them, joined by newlines, without a final one:
    its record, read within the transaction that read it."""
    return "\n".join(Printer().lines(statement, 0))


def print_file(program: Any) -> str:
    """A program's text, its hashbang first, each line ending with a newline (none for an empty program): its visitor,
    a `Programs.TypeScript5.Program`, read within the transaction that made it."""
    if program.as_schema().name != f"{LANGUAGE}.Program":
        raise TypeError(f"not a {LANGUAGE}.Program: {program.as_schema().name!r}")
    head = "" if program.hashbang.get() is None else f"#!{program.hashbang.get()}\n"
    return head + "".join(line + "\n" for line in Printer().block(_statements(program, "body"), 0))


def print_module(store: Any, path: str) -> str:
    """The text of the program the workspace holds at `path` (`print_file`), read within a transaction of its own, so
    called with none open on `store`; LookupError where it holds no file there."""
    with store.transaction():
        return print_file(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none
