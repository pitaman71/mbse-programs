"""TypeScriptToPython: translates a TypeScript 5 program the store holds into the transaction that writes a Python 3
module, without parsing or printing text.

- `transpile(store, path, target)`: the callback of the transaction that writes, as the module at `target` in the
  workspace, what the TypeScript program the workspace holds at `path` translates to. It reads the program within a
  transaction of its own, so it is called with none open on `store`; LookupError where the workspace holds no file at
  `path`. The caller executes what it gives, `store.transaction(transpile(store, path, target))`, or builds it,
  `store.Mutations.OfTransaction(...)`.
- `transpile_file(store, program, target)`: the same, given the program's visitor, read within the caller's
  transaction. What either gives holds no visitor, so it outlives the transaction that read the program.

The transaction is one upsert, `uid(target)`, as `Python3.Parse.parse` writes one: it puts the module in the workspace's
`files` by `target` and writes its tree, the module's `body`, as one value, through the builders: each statement a
branch of `Programs.Python3.Statement`, its expressions `Python3` terms written by the dialect's own writers, its
annotations `Python Types` terms. The store holds both languages' schemas: `Transpilers.store()` makes one. The
statements it builds have no `line`, as built rather than parsed.

It covers a subset of TypeScript, and raises `TranspileError` at the first syntax node outside it, located by its
anchor's text (`TypeScript5.Definitions.Anchor`: `body[0]:expression.right`):

- Statements: variable declarations (names and array patterns), expressions, `if`, `while`, `do ... while`, `for`
  (as `for ... in range(...)` where it counts, as `while` otherwise), `for ... of`, `for ... in`, `switch` without
  fall-through, `break`, `continue`, `return`, `throw`, `try`, and blocks.
- Declarations: functions (async and generators too), classes (fields, parameter properties, constructors, methods,
  accessors, static members and `extends`), enums (of numbers or of strings), imports and exports of names, and type
  aliases; interfaces and other type-only declarations are dropped.
- Expressions: literals, templates (as f-strings), arrays, object literals (as `SimpleNamespace`), arrow functions
  and function expressions (as lambdas, or as functions declared before the statement), calls, `new`, members, every
  operator with a Python counterpart, and type assertions, which are dropped.
- Types, as annotations: keywords, references, arrays, tuples, unions, literals and records.

What JavaScript's globals do is mapped where Python has a counterpart (`console.log` is `print`, `Math.floor` is
`math.floor`, `JSON.parse` is `json.loads`, `parseInt` is `int`), but only where the name is the global:
`TypeScript5.Definitions` tells a global from a name the program declares. A few methods of arrays and strings are
mapped by name (`push` is `append`, `length` is `len`, `map` and `filter` are comprehensions), unless a class or
interface of the program declares a member of that name. A call to a mapped global or method with arguments its mapping
does not take fails.

The translation keeps what code means where the two languages agree, and does not emulate where they differ: `%` of a
negative number, the truthiness of empty arrays and objects, `==` between values of different types, `+` between a
string and a number, and integers beyond 2 ** 53 behave as Python's do.

Its rules are mbse-programs 0.3's (`Transpilers/TypeScriptToPython.py`); what changed is how trees are read and built.
Decided by the agent where the port left it open, each *(agent)*:

- **The program is read record by record** (`Objects.properties`, `Terms.kind_of`), as `TypeScript5.Definitions` reads
  it, never through mbse-expressions' generic term readers, which stop at a function's `block` and a class expression's
  `classBody`. Each node read knows its anchor, the place `Definitions` gives it, and the node that holds it, so that a
  name is looked up where it is written, a `break` finds its loop, and an error is located.
- **What the translation decides, it decides from the source**: 0.3 looked at the Python it had built (whether a
  translated operand is a name or a constant, a string, a negation); a term written through the writers is a spec, not
  a node to look at, so the same questions are asked of the TypeScript that translates to it, with the same answers.
- **A statement is built as a record of its kind and properties** (`_Statement`) and written as a value once the module
  is translated (`_value`), as `Python3.Parse` builds its statements, so that a class's constructor can be found and
  spliced, and a body told empty, before it is written.
- **A legacy octal literal (`017`) is invalid syntax** in TypeScript 5, which its parser keeps as an `error` term; like
  every `error` and `missing` term and every `Programs.TypeScript5.Error`, it fails as invalid syntax, where 0.3 wrote
  `0o17`.
"""

from __future__ import annotations

import ast
import keyword
import re
import warnings
from collections.abc import Callable, Iterator
from typing import Any

from mbse.Expressions.Framework import Objects, Terms
from mbse.Expressions.Python.Python3 import Expressions as P
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework.Definitions import Entity
from ..Framework.Errors import TranspileError
from ..Framework.Model import WORKSPACE
from ..TypeScript5 import Definitions as D
from ..TypeScript5 import Statements as TS

__all__ = ["transpile", "transpile_file", "TranspileError"]

# Names the translation writes, which a name of the program must not take: Python's keywords and builtins it uses.
RESERVED = frozenset(keyword.kwlist) | {
    "self", "print", "len", "str", "int", "float", "bool", "isinstance", "list", "dict", "set", "range", "map",
    "filter", "vars", "super", "property", "staticmethod", "object", "Exception", "NotImplementedError", "math",
    "json", "random", "sys", "functools", "SimpleNamespace", "IntEnum", "StrEnum", "Any", "Literal"}
# Comparisons: TypeScript's operators, and Python's.
COMPARISONS = {"==": "==", "===": "==", "!=": "!=", "!==": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
               "in": "in"}
BINARY = {"+", "-", "*", "/", "%", "**", "<<", ">>", "&", "|", "^"}

_PLACES = frozenset(f"{TS.LANGUAGE}.{kind}" for kind in (*TS.KINDS, "Error", "Program", "ClassBody", "TSModuleBlock"))
"""The schemas that have a statement's place, as `TypeScript5.Definitions` anchors them: statements, clauses, class
members, invalid syntax, and the program, class bodies and namespace blocks that hold them."""
_FUNCTIONS = ("functiondeclaration", "functionexpression", "arrowfunctionexpression")
_LOOPS = ("whilestatement", "dowhilestatement", "forstatement", "forinstatement", "forofstatement")
_ASSERTIONS = ("parenthesizedexpression", "tsasexpression", "tssatisfiesexpression", "tsnonnullexpression",
               "tstypeassertion")
"""What translates to what it holds: parentheses, which Python's printer adds where needed, and type assertions."""


# --- Reading the TypeScript program ---

def _branch(value: Any) -> tuple[str, Any]:
    """A term's kind and record, through unions of unions (a `for`'s `init`, an export's `declaration`), the branch
    any other union holds; or a record and its kind's name in lower case (`variabledeclarator`)."""
    if Terms.is_term(value):
        return Terms.kind_of(value)
    if isinstance(value.as_schema(), SchemaKinds.OfUnion.Data):
        ((_, held),) = Objects.properties(value).items()
        return _branch(held)
    return value.as_schema().name.rsplit(".", 1)[-1].lower(), value


class _Node:
    """A node of the TypeScript program, read within the transaction: its kind's tag (`tag`, in lower case), its
    record's properties, its anchor (`at`), and the node that holds it (`parent`). A property's value is a scalar, a
    node, or a list of them; None where it is not set."""

    __slots__ = ("tag", "record", "props", "at", "parent", "place")

    def __init__(self, value: Any, at: D.Anchor, parent: _Node | None):
        self.tag, self.record = _branch(value)
        self.props = Objects.properties(self.record)
        self.at, self.parent = at, parent
        self.place = self.record.as_schema().name in _PLACES

    @property
    def kind(self) -> str:
        """Its kind's name, as typescript-estree has it (`IfStatement`)."""
        return self.record.as_schema().name.rsplit(".", 1)[-1]

    def __getitem__(self, name: str) -> Any:
        value = self.props.get(name)
        if isinstance(value, Objects.Listed):
            return [self.child(name, i, element) for i, element in enumerate(value.values)]
        return None if value is None else self.child(name, None, value)

    def items(self, name: str) -> list[Any]:
        """A list property's elements; none where it is not set."""
        return self[name] or []

    def child(self, name: str, index: int | None, value: Any) -> Any:
        """The node `value` holds, at its place as `Definitions` anchors it; a scalar as it is."""
        if not hasattr(value, "as_schema"):
            return value
        place = _branch(value)[1].as_schema().name in _PLACES
        if self.place and (place or self.kind == "ClassBody"):  # a statement within a statement
            return _Node(value, self.at.child(name, index, 0), self)
        at = self.at.at(name, 0)
        at = at if index is None else at.at(index, 0)
        return _Node(value, at.opened() if place else at, self)  # within a term, a statement opens a place

    def same(self, other: _Node | None) -> bool:
        return other is not None and self.at == other.at

    def walk(self) -> Iterator[_Node]:
        """This node and every node within it, in order."""
        yield self
        for name in self.props:
            held = self[name]
            for node in held if isinstance(held, list) else [held]:
                if isinstance(node, _Node):
                    yield from node.walk()

    def ancestors(self) -> Iterator[_Node]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent


def _bare(node: _Node) -> _Node:
    """What an expression translates as: within its parentheses and type assertions."""
    while node.tag in _ASSERTIONS:
        node = node["expression"]
    return node


def _string(node: _Node) -> bool:
    return node.tag == "literal" and node["quote"] is not None


# --- Building the Python module ---

class _Statement:
    """A Python statement, as the transaction writes it: its kind (`If`), and its properties that are given, a block's
    statements among them. `init` marks an expression statement that calls `__init__`."""

    __slots__ = ("kind", "properties", "init")

    def __init__(self, kind: str, **properties: Any):
        self.kind, self.init = kind, False
        self.properties = {name: value for name, value in properties.items()
                           if value is not None and value != [] and value is not False}


def _value(statement: _Statement) -> Callable[[Any], Any]:
    """The writer of a statement as a branch of the union that holds it, tagged by its kind in lower case: its
    properties, each block's statements written so in turn."""
    fields = {name: [_value(s) for s in value] if isinstance(value, list) and isinstance(value[0], _Statement)
              else value for name, value in statement.properties.items()}

    def write(r: Any) -> Any:
        for name, value in fields.items():
            getattr(r, name)(value)
        return r

    return lambda union: getattr(union, statement.kind.lower())(write)


def _record(fields: dict[str, Any]) -> Callable[[Any], Any]:
    """The writer of a value object's fields that are given: None and an empty list are absent."""
    given = {name: value for name, value in fields.items() if value is not None and value != []}

    def write(r: Any) -> Any:
        for name, value in given.items():
            getattr(r, name)(value)
        return r

    return write


def _constant(text: str) -> P.Writer:
    """A literal as Python reads `text`, its spelling."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)  # an escape Python does not know, which it keeps as written
        return P.constant(ast.literal_eval(text), text)


def _alias(name: str, asname: str | None = None) -> P.Helper:
    return P.Helper("alias", _record({"name": name, "asname": asname}))


def _empty(statements: list[_Statement]) -> bool:
    """Whether a body holds nothing but comments."""
    return all(s.kind == "Comment" for s in statements)


class _Translator:
    """Translates one program. Statements become lists of statements: an arrow function with a body, used as a value,
    becomes a function declared before the statement that uses it."""

    def __init__(self, store: Any, program: Any):
        self.root = _Node(program, D.Anchor(""), None)
        self.definitions = D.define_file(store, program)
        self.imports: set[str] = set()  # the modules the translation needs
        self.from_imports: dict[str, set[str]] = {}  # names to import from a module
        self.pending: list[_Statement] = []  # statements that must come before the current one
        self.lambdas = 0  # how deep in a lambda the translation is, where nothing can be declared
        self.methods: list[bool] = []  # for each enclosing function, whether `self` is its `this`
        self.catches: list[Entity] = []  # the entities a `catch` clause binds
        self.members = {e.name for e in self.definitions.entities() if e.kind in ("method", "property", "accessor")}
        self.taken = {n["name"] for n in self.root.walk() if n.tag == "identifier"}
        self.counter = 0

    # Helpers

    def error(self, node: _Node, message: str | None = None) -> TranspileError:
        what = "invalid syntax" if node.tag == "error" else node.kind
        return TranspileError(message or f"{what} is not supported", str(node.at))

    def fresh(self, stem: str) -> str:
        """A name no name of the program takes, for a value the translation keeps."""
        while True:
            self.counter += 1
            name = f"_{stem}{self.counter}"
            if name not in self.taken:
                self.taken.add(name)
                return name

    def module(self, name: str) -> P.Writer:
        """The module `name`, imported."""
        self.imports.add(name)
        return P.name(name)

    def imported(self, module: str, name: str) -> P.Writer:
        """`name` from `module`, imported."""
        self.from_imports.setdefault(module, set()).add(name)
        return P.name(name)

    @staticmethod
    def python(name: str) -> str:
        """The Python spelling of a TypeScript name: one the translation writes, or a keyword, takes a `_`."""
        return name + "_" if name in RESERVED else name

    def is_global(self, identifier: _Node) -> bool:
        """Whether `identifier` names a global: one the program does not declare."""
        return not D.referents(self.definitions, identifier.at)

    def simple(self, node: _Node) -> bool:
        """Whether `node` translates to a name or a constant, which can be written twice."""
        node = _bare(node)
        if node.tag == "identifier":
            return not (self.is_global(node) and node["name"] in ("NaN", "Infinity"))
        return node.tag in ("literal", "constant", "thisexpression")

    def none(self, node: _Node) -> bool:
        """Whether `node` translates to `None`."""
        node = _bare(node)
        return (node.tag == "constant" and node["singleton"] is not None) or (
            node.tag == "identifier" and node["name"] == "undefined" and self.is_global(node))

    @staticmethod
    def textual(node: _Node) -> bool:
        """Whether `node` is a string literal, a template or a sum that makes a string, which `+` makes a string of
        the other operand."""
        node = _bare(node)
        if node.tag == "binaryexpression" and node["operator"] == "+":
            return _Translator.textual(node["left"]) or _Translator.textual(node["right"])
        return node.tag == "templateliteral" or _string(node)

    # The program

    def program(self) -> list[_Statement]:
        body = self.statements(self.root.items("body"))
        head = [_Statement("Import", names=[_alias(m)]) for m in sorted(self.imports)]
        for module in sorted(self.from_imports):
            names = [_alias(n) for n in sorted(self.from_imports[module])]
            head.append(_Statement("ImportFrom", module=module, names=names))
        return head + body

    # Statements

    def statements(self, statements: list[_Node]) -> list[_Statement]:
        out: list[_Statement] = []
        for statement in statements:
            outer, self.pending = self.pending, []
            translated = self.statement(statement)
            out += self.pending + translated
            self.pending = outer
        return out

    def body(self, statements: list[_Node]) -> list[_Statement]:
        """Statements as a block's body, which is never empty."""
        body = self.statements(statements)
        return body + [_Statement("Pass")] if _empty(body) else body

    def block(self, statement: _Node) -> list[_Statement]:
        """A statement as a block's body: a block's statements, or the statement alone."""
        return self.body(statement.items("body") if statement.tag == "blockstatement" else [statement])

    def statement(self, node: _Node) -> list[_Statement]:
        method = self.STATEMENTS.get(node.tag)
        if method is None:
            raise self.error(node)
        return method(self, node)

    def comment(self, node: _Node) -> list[_Statement]:
        block = bool(node["block"])
        lines = node["text"].split("\n") if block else [node["text"]]
        return [_Statement("Comment", text=" " + line.strip(" *") if block else line,
                           trailing=bool(node["trailing"]) and i == 0)
                for i, line in enumerate(lines) if not block or line.strip(" *")]

    def expression_statement(self, node: _Node) -> list[_Statement]:
        return self.effect(node["expression"])

    def effect(self, expression: _Node) -> list[_Statement]:
        """An expression evaluated for what it does, as statements."""
        if expression.tag == "assignmentexpression":
            return self.assignment(expression)
        if expression.tag == "updateexpression":
            return [_Statement("AugAssign", target=self.target(expression["argument"]),
                               op="+" if expression["operator"] == "++" else "-", value=P.constant(1))]
        if expression.tag == "unaryexpression" and expression["operator"] == "delete":
            return [_Statement("Delete", targets=[self.target(expression["argument"])])]
        if expression.tag == "callexpression":
            each = self.for_each(expression)
            if each is not None:
                return each
            mapped = self.set_call(expression)
            if mapped is not None:
                return mapped
        made = _Statement("Expr", value=self.expression(expression))
        made.init = expression.tag == "callexpression" and self.calls_init(expression)
        return [made]

    def calls_init(self, call: _Node) -> bool:
        """Whether a call translates to a call of a method `__init__`: `super(...)` or `x.__init__(...)`."""
        callee = call["callee"]
        return callee.tag == "super" or (callee.tag == "memberexpression" and not callee["computed"] and (
            callee["property"].tag in ("identifier", "privateidentifier"))
            and self.property_name(callee["property"]) == "__init__")

    def assignment(self, node: _Node) -> list[_Statement]:
        operator = node["operator"]
        if operator in ("&&=", "||=", "??="):  # `a ||= b` assigns only where `a` is falsy
            target = self.target(node["left"])
            current = self.expression(node["left"])
            test = {"&&=": lambda: current, "||=": lambda: P.unaryop("not", current),
                    "??=": lambda: P.compare("is", current, P.constant(None))}[operator]()
            assign = _Statement("Assign", targets=[target], value=self.expression(node["right"]))
            return [_Statement("If", test=test, body=[assign])]
        if operator != "=":
            op = operator[:-1]
            if op not in BINARY:
                raise self.error(node, f"the operator {operator} is not supported")
            return [_Statement("AugAssign", target=self.target(node["left"]), op=op,
                               value=self.expression(node["right"]))]
        targets = [self.target(node["left"])]
        value = node["right"]
        while value.tag == "assignmentexpression" and value["operator"] == "=":  # `a = b = c`
            targets.append(self.target(value["left"]))
            value = value["right"]
        return [_Statement("Assign", targets=targets, value=self.expression(value))]

    def assignable(self, node: _Node) -> bool:
        """Whether a name or a member translates to a name, an attribute or a subscript, which can be assigned."""
        if node.tag == "identifier":
            return not (self.is_global(node) and node["name"] in ("undefined", "NaN", "Infinity"))
        return node["computed"] or self.mapped_member(node) is None

    def target(self, node: _Node) -> Any:
        """What an assignment assigns to."""
        if node.tag in ("identifier", "memberexpression") and self.assignable(node):
            return self.expression(node)
        if node.tag == "arraypattern":
            return P.tuple_(*(self.pattern_element(e) for e in node.items("elements")))
        if node.tag == "parenthesizedexpression":
            return self.target(node["expression"])
        raise self.error(node, f"{node.kind} as a target is not supported")

    def pattern_element(self, node: _Node) -> Any:
        if node.tag == "elision":
            return P.name("_")
        if node.tag == "restelement":
            return P.starred(self.target(node["argument"]))
        return self.target(node)

    def variables(self, node: _Node) -> list[_Statement]:
        if node["declarationKind"] in ("using", "await using"):
            raise self.error(node, f"{node['declarationKind']} is not supported")
        if node["declare"]:
            return []
        out: list[_Statement] = []
        for declarator in node.items("declarations"):
            id_, init = declarator["id"], declarator["init"]
            if init is not None and id_.tag == "identifier" and init.tag in (
                    "arrowfunctionexpression", "functionexpression") and init["block"] is not None:
                out.append(self.function(init, self.python(id_["name"])))  # `const f = () => {}`
                continue
            target = self.binding(id_)
            value = P.constant(None) if init is None else self.expression(init)
            annotation = self.annotation(id_) if id_.tag == "identifier" else None
            if annotation is not None and init is not None:
                out.append(_Statement("AnnAssign", target=target, annotation=annotation, value=value))
            else:
                out.append(_Statement("Assign", targets=[target], value=value))
        return out

    def binding(self, node: _Node) -> Any:
        if node.tag == "identifier":
            return P.name(self.python(node["name"]))
        if node.tag == "arraypattern":
            return P.tuple_(*(P.name("_") if e.tag == "elision" else P.starred(self.binding(e["argument"]))
                              if e.tag == "restelement" else self.binding(e) for e in node.items("elements")))
        raise self.error(node, f"{node.kind} as a binding is not supported")

    def if_statement(self, node: _Node) -> list[_Statement]:
        alternate = node["alternate"]
        orelse: list[_Statement] = []
        if alternate is not None:
            orelse = self.statements([alternate]) if alternate.tag == "ifstatement" else self.block(alternate)
        return [_Statement("If", test=self.expression(node["test"]), body=self.block(node["consequent"]),
                           orelse=orelse)]

    def while_statement(self, node: _Node) -> list[_Statement]:
        return [_Statement("While", test=self.expression(node["test"]), body=self.block(node["body"]))]

    def do_while(self, node: _Node) -> list[_Statement]:
        """`do body while (test)`: a `while True` that breaks after the body, which must not `continue`."""
        self.no_continue(node["body"], node)
        stop = _Statement("If", test=self.negate(node["test"]), body=[_Statement("Break")])
        return [_Statement("While", test=P.constant(True), body=self.block(node["body"]) + [stop])]

    def negate(self, test: _Node) -> Any:
        bare = _bare(test)
        if bare.tag == "unaryexpression" and bare["operator"] == "!":
            return self.expression(bare["argument"])
        return P.unaryop("not", self.expression(test))

    def no_continue(self, body: _Node, loop: _Node) -> None:
        """Raises if `body` continues the loop it is the body of: its translation would skip what follows the body."""
        for node in body.walk():
            if node.tag == "continuestatement" and loop.same(self.loop_of(node)):
                raise self.error(node, "continue in this loop is not supported")

    @staticmethod
    def loop_of(node: _Node) -> _Node | None:
        """The loop a `break` or `continue` leaves, or for a `break` the `switch`; None outside of them."""
        for ancestor in node.ancestors():
            if ancestor.tag in _LOOPS or (ancestor.tag == "switchstatement" and node.tag == "breakstatement"):
                return ancestor
            if ancestor.tag in _FUNCTIONS:
                break
        return None

    def for_statement(self, node: _Node) -> list[_Statement]:
        counted = self.counted(node)
        if counted is not None:
            return counted
        self.no_continue(node["body"], node)
        init, update = node["init"], node["update"]
        out: list[_Statement] = []
        if init is not None:
            out += self.variables(init) if init.tag == "variabledeclaration" else self.update(init)
        body = self.block(node["body"])
        if update is not None:
            body = [s for s in body if s.kind != "Pass"] + self.update(update)
        test = P.constant(True) if node["test"] is None else self.expression(node["test"])
        return out + [_Statement("While", test=test, body=body)]

    def update(self, node: _Node) -> list[_Statement]:
        if node.tag == "sequenceexpression":
            return [s for e in node.items("expressions") for s in self.update(e)]
        return self.effect(node)

    def counted(self, node: _Node) -> list[_Statement] | None:
        """`for (let i = a; i < b; i++)` as `for i in range(a, b)`, where the body does not assign `i`; None for
        any other `for`."""
        init, test, update = node["init"], node["test"], node["update"]
        if not (init is not None and init.tag == "variabledeclaration" and len(init.items("declarations")) == 1):
            return None
        (declarator,) = init.items("declarations")
        if not (declarator["id"].tag == "identifier" and declarator["init"] is not None):
            return None
        name = declarator["id"]["name"]
        if not (test is not None and test.tag == "binaryexpression" and test["left"].tag == "identifier" and (
                test["left"]["name"] == name) and test["operator"] in ("<", "<=", ">", ">=")):
            return None
        step: int | None = None
        if update is None:
            return None
        if update.tag == "updateexpression" and update["argument"].tag == "identifier" and (
                update["argument"]["name"] == name):
            step = 1 if update["operator"] == "++" else -1
        elif update.tag == "assignmentexpression" and update["operator"] in ("+=", "-=") and (
                update["left"].tag == "identifier") and update["left"]["name"] == name and (
                update["right"].tag == "literal") and re.fullmatch("[0-9]+", update["right"]["text"]):
            step = int(update["right"]["text"]) * (1 if update["operator"] == "+=" else -1)
        if step is None or (step > 0) != (test["operator"] in ("<", "<=")):
            return None
        for n in node["body"].walk():  # the body must not change the counter
            assigned = n["left"] if n.tag == "assignmentexpression" else n["argument"] if (
                n.tag == "updateexpression") else None
            if assigned is not None and assigned.tag == "identifier" and assigned["name"] == name:
                return None
        stop = self.expression(test["right"])
        if test["operator"] in ("<=", ">="):  # one past the bound, folded where the bound is a number
            past = 1 if step > 0 else -1
            bound = _bare(test["right"])
            digits = self.number(bound) if bound.tag == "literal" and not _string(bound) else None
            if digits is not None and re.fullmatch("[0-9]+", digits):
                stop = P.constant(int(digits) + past)
            else:
                stop = P.binop("+" if past > 0 else "-", stop, P.constant(1))
        bounds = [self.expression(declarator["init"]), stop]
        if step != 1:
            bounds.append(P.constant(step))
        iterable = P.call(P.name("range"), *bounds)
        return [_Statement("For", target=P.name(self.python(name)), iter=iterable, body=self.block(node["body"]))]

    def for_of(self, node: _Node) -> list[_Statement]:
        left = node["left"]
        target = self.binding(left.items("declarations")[0]["id"]) if left.tag == "variabledeclaration" else (
            self.target(left))
        iterable = self.expression(node["right"])
        if node.tag == "forinstatement":  # the keys of an object
            iterable = P.call(P.name("vars"), iterable)
        elif node["isAwait"]:
            raise self.error(node, "for await is not supported")
        return [_Statement("For", target=target, iter=iterable, body=self.block(node["body"]))]

    def switch(self, node: _Node) -> list[_Statement]:
        """`switch` as `if ... elif ... else`: each case must end its body, with `break`, `return`, `throw` or
        `continue`, but for cases that only share the next one's body."""
        out: list[_Statement] = []
        subject = self.expression(node["discriminant"])
        if not self.simple(node["discriminant"]):
            name = self.fresh("subject")
            out.append(_Statement("Assign", targets=[P.name(name)], value=subject))
            subject = P.name(name)
        branches: list[tuple[list[Any], list[_Statement]]] = []  # each branch's tests (none for default) and body
        tests: list[Any] = []
        default = False
        cases = node.items("cases")
        for i, case in enumerate(cases):
            consequent = case.items("consequent")
            body = [s for s in consequent if s.tag != "comment"]
            if case["test"] is None:
                default = True
            else:
                tests.append(P.compare("==", subject, self.expression(case["test"])))
            if not body and i + 1 < len(cases):
                continue  # shares the next case's body
            if body and body[-1].tag not in ("breakstatement", "returnstatement", "throwstatement",
                                             "continuestatement") and i + 1 < len(cases):
                raise self.error(case, "a case that falls through is not supported")
            final = body[-1] if body and body[-1].tag == "breakstatement" else None  # which `if` makes
            kept = [s for s in consequent if not s.same(final)]
            for n in (n for s in kept for n in s.walk()):
                if n.tag == "breakstatement" and n["label"] is None and node.same(self.loop_of(n)):
                    raise self.error(n, "break within a case is not supported")
            branches.append(([] if default else tests, self.body(kept)))
            tests, default = [], False
        chain: list[_Statement] = []
        for tests_, body_ in reversed(branches):
            if not tests_:
                chain = body_
            else:
                test = tests_[0] if len(tests_) == 1 else P.boolop("or", *tests_)
                chain = [_Statement("If", test=test, body=body_, orelse=chain)]
        return out + chain

    def jump(self, node: _Node) -> list[_Statement]:
        if self.loop_of(node) is None:
            raise self.error(node, f"{node.kind} outside of a loop is not supported")
        return [_Statement("Break" if node.tag == "breakstatement" else "Continue")]

    def return_statement(self, node: _Node) -> list[_Statement]:
        argument = node["argument"]
        return [_Statement("Return", value=None if argument is None else self.expression(argument))]

    def throw(self, node: _Node) -> list[_Statement]:
        return [_Statement("Raise", exc=self.expression(node["argument"]))]

    def try_statement(self, node: _Node) -> list[_Statement]:
        handlers: list[_Statement] = []
        handler = node["handler"]
        if handler is not None:
            param = handler["param"]
            if param is not None and param.tag != "identifier":
                raise self.error(param, "a pattern in catch is not supported")
            if param is not None:
                self.catches.append(self.definitions.entity_of(param.at))  # type: ignore[arg-type]
            handlers.append(_Statement("ExceptHandler", type=P.name("Exception"),
                                       name=None if param is None else self.python(param["name"]),
                                       body=self.block(handler["body"])))
        finalizer = node["finalizer"]
        return [_Statement("Try", body=self.block(node["block"]), handlers=handlers,
                           finalbody=[] if finalizer is None else self.block(finalizer))]

    # Declarations

    def function_declaration(self, node: _Node) -> list[_Statement]:
        if node.tag == "tsdeclarefunction":
            return []  # an overload's signature
        return [self.function(node, self.python(node["id"]["name"]))]

    @staticmethod
    def block_of(node: _Node) -> _Node | None:
        """A function's body, its block of statements: a declaration's `body`, an expression's `block`; None for an
        arrow whose body is an expression, and a signature."""
        return node["body"] if node.tag == "functiondeclaration" else node["block"]

    def function(self, node: _Node, name: str, method: bool = False, decorators: list[Any] | None = None,
                 prefix: list[_Statement] | None = None) -> _Statement:
        """A function, an arrow function or a method as a `def`; `prefix` are statements its body starts with. An
        arrow function's `this` is the enclosing function's."""
        if node["generator"] and node["isAsync"]:
            raise self.error(node, "an async generator is not supported")
        arrow = node.tag == "arrowfunctionexpression"
        self.methods.append(method or (arrow and bool(self.methods) and self.methods[-1]))
        args = self.parameters(node.items("params"), method)
        block = self.block_of(node)
        if block is not None:
            body = self.statements(block.items("body"))
        elif arrow:
            outer, self.pending = self.pending, []
            value = self.expression(node["body"])
            body = self.pending + [_Statement("Return", value=value)]
            self.pending = outer
        else:  # an abstract method's signature
            body = []
        body = self.outer_names(block) + (prefix or []) + body
        if _empty(body):
            body.append(_Statement("Pass"))
        self.methods.pop()
        returns = node["returnType"]
        return _Statement("AsyncFunctionDef" if node["isAsync"] else "FunctionDef", decorator_list=decorators,
                          name=name, args=args, body=body,
                          returns=None if returns is None else self.type(returns["typeAnnotation"]))

    def outer_names(self, block: _Node | None) -> list[_Statement]:
        """`global` and `nonlocal` for the names a function assigns but does not declare: in TypeScript, assigning
        a name of an enclosing scope assigns it there, where Python would make it the function's own."""
        if block is None:
            return []
        own = self.definitions.scope_of(block.at)
        found: dict[str, list[str]] = {"global": [], "nonlocal": []}
        for target in self.assigned(block):
            entities = D.referents(self.definitions, target.at)
            if not entities:
                continue
            scope = entities[0].parent
            while scope.kind not in ("function", "module", "static block"):  # type: ignore[union-attr]
                scope = scope.parent  # type: ignore[union-attr]
            if scope is not own:
                which = found["global" if scope.parent is None else "nonlocal"]  # type: ignore[union-attr]
                name = self.python(target["name"])
                if name not in which:
                    which.append(name)
        out: list[_Statement] = []
        if found["global"]:
            out.append(_Statement("Global", names=found["global"]))
        if found["nonlocal"]:
            out.append(_Statement("Nonlocal", names=found["nonlocal"]))
        return out

    @staticmethod
    def assigned(node: _Node) -> list[_Node]:
        """The names `node` assigns, outside the functions and classes within it, in source order."""
        if node.tag in (*_FUNCTIONS, "classdeclaration", "classexpression"):
            return []
        target = node["left"] if node.tag == "assignmentexpression" else node["argument"] if (
            node.tag == "updateexpression") else None
        out = [target] if target is not None and target.tag == "identifier" else []
        for name in node.props:
            held = node[name]
            for child in held if isinstance(held, list) else [held]:
                if isinstance(child, _Node):
                    out += _Translator.assigned(child)
        return out

    def parameters(self, params: list[_Node], method: bool) -> P.Helper:
        args: list[Any] = [P.arg("self")] if method else []
        vararg = None
        for param in params:
            if param.tag == "tsparameterproperty":
                param = param["parameter"]
            default = None
            if param.tag == "assignmentpattern":
                param, default = param["left"], self.expression(param["right"])
            if param.tag == "restelement" and param["argument"].tag == "identifier":
                vararg = P.arg(self.python(param["argument"]["name"]))
                continue
            if param.tag != "identifier":
                raise self.error(param, f"{param.kind} as a parameter is not supported")
            if param["name"] == "this":
                continue
            if param["optional"] and default is None:
                default = P.constant(None)
            args.append(P.arg(self.python(param["name"]), default, self.annotation(param)))
        return P.Helper("arguments", _record({"args": args, "vararg": vararg}))

    def annotation(self, node: _Node) -> Any:
        annotation = node["typeAnnotation"]
        return None if annotation is None else self.type(annotation["typeAnnotation"])

    def class_declaration(self, node: _Node) -> list[_Statement]:
        if node["declare"]:
            return []
        if node["decorators"]:
            raise self.error(node["decorators"][0], "a decorator is not supported")
        bases: list[Any] = []
        base = node["superClass"]
        if base is not None:
            error = base.tag == "identifier" and base["name"] == "Error" and self.is_global(base)
            bases.append(P.name("Exception") if error else self.expression(base))
        body: list[_Statement] = []
        fields: list[_Statement] = []  # instance fields, which the constructor assigns
        constructor = None
        for member in node["body"].items("body"):
            if member.tag == "comment":
                body += self.comment(member)
            elif member.tag in ("propertydefinition", "tsabstractpropertydefinition"):
                body += self.field(member, fields)
            elif member.tag in ("methoddefinition", "tsabstractmethoddefinition"):
                if member["methodKind"] == "constructor":
                    constructor = member
                elif member["value"].tag != "tsemptybodyfunctionexpression" or (
                        member.tag == "tsabstractmethoddefinition"):
                    body.append(self.method(member))
            elif member.tag != "tsindexsignature":  # a type
                raise self.error(member)
        if constructor is not None or fields:  # after the class's own attributes, before its methods
            index = next((i for i, s in enumerate(body) if s.kind in ("FunctionDef", "AsyncFunctionDef")), len(body))
            body.insert(index, self.constructor(constructor, fields, base is not None))
        if _empty(body):
            body.append(_Statement("Pass"))
        return [_Statement("ClassDef", name=self.python(node["id"]["name"]), bases=bases, body=body)]

    def member_name(self, member: _Node) -> str:
        if member["computed"]:
            raise self.error(member, "a computed member name is not supported")
        if member["key"].tag not in ("identifier", "privateidentifier"):
            raise self.error(member, "a member named by a literal is not supported")
        return self.property_name(member["key"])

    def field(self, member: _Node, fields: list[_Statement]) -> list[_Statement]:
        name = self.member_name(member)
        annotation = self.annotation(member)
        value = member["value"]
        if member["static"]:
            written = P.constant(None) if value is None else self.expression(value)
            if annotation is not None:
                return [_Statement("AnnAssign", target=P.name(name), annotation=annotation, value=written)]
            return [_Statement("Assign", targets=[P.name(name)], value=written)]
        if value is not None:
            self.methods.append(True)
            target = P.attribute(P.name("self"), name)
            fields.append(_Statement("Assign", targets=[target], value=self.expression(value)))
            self.methods.pop()
        if annotation is not None:
            return [_Statement("AnnAssign", target=P.name(name), annotation=annotation)]
        return []

    def constructor(self, member: _Node | None, fields: list[_Statement], derived: bool) -> _Statement:
        """`__init__`: the constructor's body, with the parameter properties and the fields assigned after `super`
        is called, or first; or, without a constructor, one that passes its arguments to `super`."""
        if member is None:
            prefix: list[_Statement] = []
            if derived:
                init = P.attribute(P.call(P.name("super")), "__init__")
                prefix.append(_Statement("Expr", value=P.call(init, P.starred(P.name("args")))))
            arguments = _record({"args": [P.arg("self")], "vararg": P.arg("args") if derived else None})
            return _Statement("FunctionDef", name="__init__", args=P.Helper("arguments", arguments),
                              body=prefix + fields or [_Statement("Pass")])
        value = member["value"]
        properties: list[_Statement] = []  # `constructor(private x)` assigns `self.x = x`
        for param in value.items("params"):
            if param.tag == "tsparameterproperty":
                bound = param["parameter"]
                bound = bound["left"] if bound.tag == "assignmentpattern" else bound
                name = self.python(bound["name"])
                properties.append(_Statement("Assign", targets=[P.attribute(P.name("self"), name)],
                                             value=P.name(name)))
        made = self.function(value, "__init__", method=True)
        statements = made.properties["body"]
        index = next((i + 1 for i, s in enumerate(statements) if s.init), 0)
        statements[index:index] = properties + fields
        made.properties["body"] = [s for s in statements if s.kind != "Pass"] or [_Statement("Pass")]
        return made

    def method(self, member: _Node) -> _Statement:
        name = self.member_name(member)
        value = member["value"]
        if name == "toString" and not member["static"] and not value["params"]:
            name = "__str__"  # what `String(x)` and templates call, as `str(x)` and f-strings do
        if member.tag == "tsabstractmethoddefinition":
            raise_ = _Statement("Raise", exc=P.name("NotImplementedError"))
            return self.function(value, name, method=not member["static"], prefix=[raise_])
        decorators: list[Any] = []
        if member["static"]:
            decorators.append(P.name("staticmethod"))
        if member["methodKind"] == "get":
            decorators.append(P.name("property"))
        elif member["methodKind"] == "set":
            decorators.append(P.attribute(P.name(name), "setter"))
        return self.function(value, name, method=not member["static"], decorators=decorators)

    def enum(self, node: _Node) -> list[_Statement]:
        """An enum of numbers, as an `IntEnum`, or of strings, as a `StrEnum`."""
        if node["declare"]:
            return []
        members = [m for m in node["body"].items("members") if m.tag != "comment"]
        strings = any(m["initializer"] is not None and _string(m["initializer"]) for m in members)
        body: list[_Statement] = []
        following = 0
        for member in members:
            initializer = member["initializer"]
            if member["computed"] or member["id"].tag != "identifier":
                raise self.error(member, "an enum member must be named by a name")
            name = self.property_name(member["id"])
            value: Any
            if initializer is None:
                if strings:
                    raise self.error(member, "a member of a string enum needs a value")
                value = P.constant(following)
                following += 1
            elif initializer.tag == "literal" and (strings or re.fullmatch("[0-9]+", initializer["text"])):
                value = self.expression(initializer)
                if not strings:
                    following = int(initializer["text"]) + 1
            else:
                raise self.error(initializer, "an enum member's value must be a literal")
            body.append(_Statement("Assign", targets=[P.name(name)], value=value))
        base = self.imported("enum", "StrEnum" if strings else "IntEnum")
        return [_Statement("ClassDef", name=self.python(node["id"]["name"]), bases=[base],
                           body=body or [_Statement("Pass")])]

    def type_alias(self, node: _Node) -> list[_Statement]:
        value = self.type(node["typeAnnotation"])
        if value is None or node["typeParameters"] is not None:
            return []
        return [_Statement("TypeAlias", name=P.name(self.python(node["id"]["name"])), value=value)]

    def import_declaration(self, node: _Node) -> list[_Statement]:
        if node["importKind"] == "type":
            return []
        level, names = self.module_path(node["source"])
        out: list[_Statement] = []
        named: list[Any] = []
        parent = ".".join(names[:-1]) or None
        for specifier in node.items("specifiers"):
            if specifier.tag == "importnamespacespecifier":
                local = self.python(specifier["local"]["name"])
                if level:
                    out.append(_Statement("ImportFrom", level=level, module=parent,
                                          names=[_alias(names[-1], local)]))
                else:
                    out.append(_Statement("Import", names=[_alias(".".join(names), local)]))
            elif specifier.tag == "importspecifier":
                if specifier["importKind"] == "type":
                    continue
                imported = specifier["imported"]
                if imported.tag != "identifier":
                    raise self.error(specifier, "importing a name that is a string is not supported")
                local, name = self.python(specifier["local"]["name"]), self.python(imported["name"])
                named.append(_alias(name, None if local == name else local))
            else:
                raise self.error(specifier, "a default import is not supported")
        if named:
            out.insert(0, _Statement("ImportFrom", level=level or None, module=".".join(names), names=named))
        if not node["specifiers"]:
            if not level:
                out.append(_Statement("Import", names=[_alias(".".join(names))]))
            else:
                out.append(_Statement("ImportFrom", level=level, module=parent, names=[_alias(names[-1])]))
        return out

    def module_path(self, source: _Node) -> tuple[int, list[str]]:
        """A module's level (how many packages up, for a relative path) and its dotted name's parts: `./a/b` is
        `.a.b`."""
        written = source["text"]
        path = written[1:-1]
        level = 0
        if path.startswith("."):
            level = 1
            path = path[2:] if path.startswith("./") else path
            while path.startswith("../"):
                level += 1
                path = path[3:]
        path = re.sub(r"\.(ts|js|mjs|cjs)$", "", path)
        parts = [p for p in path.split("/") if p]
        if not parts or any(not re.fullmatch("[A-Za-z_$][A-Za-z0-9_$-]*", p) for p in parts):
            raise self.error(source, f"the module {written} has no Python name")
        return level, [self.python(p.replace("-", "_").replace("$", "_")) for p in parts]

    def export_named(self, node: _Node) -> list[_Statement]:
        if node["declaration"] is not None:
            return self.statement(node["declaration"])
        if node["source"] is not None:
            raise self.error(node, "a re-export is not supported")
        return []  # Python exports every name a module binds

    def export_default(self, node: _Node) -> list[_Statement]:
        declaration = node["declaration"]
        if declaration.tag in ("functiondeclaration", "classdeclaration") and declaration["id"] is not None:
            return self.statement(declaration)
        raise self.error(node, "a default export of a value is not supported")

    def skip(self, node: _Node) -> list[_Statement]:
        return []  # type-only

    STATEMENTS: dict[str, Callable[[_Translator, _Node], list[_Statement]]] = {
        "comment": comment, "expressionstatement": expression_statement, "variabledeclaration": variables,
        "ifstatement": if_statement, "whilestatement": while_statement, "dowhilestatement": do_while,
        "forstatement": for_statement, "forofstatement": for_of, "forinstatement": for_of, "switchstatement": switch,
        "breakstatement": jump, "continuestatement": jump, "returnstatement": return_statement,
        "throwstatement": throw, "trystatement": try_statement,
        "blockstatement": lambda self, node: self.statements(node.items("body")),
        "emptystatement": lambda self, node: [],
        "functiondeclaration": function_declaration, "tsdeclarefunction": function_declaration,
        "classdeclaration": class_declaration, "tsenumdeclaration": enum, "tstypealiasdeclaration": type_alias,
        "tsinterfacedeclaration": skip, "importdeclaration": import_declaration,
        "exportnameddeclaration": export_named, "exportdefaultdeclaration": export_default,
    }

    # Expressions

    def expression(self, node: _Node) -> Any:
        method = self.EXPRESSIONS.get(node.tag)
        if method is None:
            raise self.error(node)
        return method(self, node)

    def identifier(self, node: _Node) -> Any:
        name = node["name"]
        if self.is_global(node):
            if name == "undefined":
                return P.constant(None)
            if name in ("NaN", "Infinity"):
                return P.attribute(self.module("math"), "nan" if name == "NaN" else "inf")
            if name in GLOBALS or name in OBJECTS:
                raise self.error(node, f"the global {name} is not supported here")
        return P.name(self.python(name))

    def number(self, node: _Node) -> str:
        """A number's Python spelling: a bigint's, without its `n`, as Python's integers have no bounds."""
        text = node["text"]
        return text[:-1] if text.endswith("n") else text

    def literal(self, node: _Node) -> Any:
        text = node["text"]
        if text in ("true", "false"):
            return P.constant(text == "true")
        if _string(node):
            return _constant(self.string(text))
        return _constant(self.number(node))

    def constant(self, node: _Node) -> Any:
        if node["singleton"] is not None:  # `null`
            return P.constant(None)
        raise self.error(node, "a regular expression is not supported")

    @staticmethod
    def string(text: str) -> str:
        """A Python string literal's spelling of a TypeScript one: escapes Python lacks rewritten."""
        return re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: "\\U" + m.group(1).rjust(8, "0"), text)

    def template(self, node: _Node) -> Any:
        values: list[Any] = []
        expressions = node.items("expressions")
        for i, quasi in enumerate(node.items("quasis")):
            text = self.string(quasi["raw"]).replace("{", "{{").replace("}", "}}").replace("\\`", "`").replace(
                '"', '\\"').replace("\n", "\\n")
            if text:
                values.append(text)
            if i < len(expressions):
                values.append(P.formattedvalue(self.expression(expressions[i])))
        return P.joinedstr(values, "f", '"')

    def this(self, node: _Node) -> Any:
        if not self.methods or not self.methods[-1]:
            raise self.error(node, "this outside a method is not supported")
        return P.name("self")

    def array(self, node: _Node) -> Any:
        elements: list[Any] = []
        for element in node.items("elements"):
            if element.tag == "elision":
                raise self.error(element, "a hole in an array is not supported")
            elements.append(P.starred(self.expression(element["argument"])) if element.tag == "spreadelement"
                            else self.expression(element))
        return P.list_(*elements)

    def object(self, node: _Node) -> Any:
        keywords: list[Any] = []
        for item in node.items("properties"):
            spread = item.tag == "spreadelement"
            if spread or item["method"] or item["propertyKind"] != "init" or item["computed"]:
                raise self.error(item, f"{'a spread' if spread else 'this property'} in an object literal is not "
                                       "supported")
            key = item["key"]
            name = key["name"] if key.tag == "identifier" else key["text"][1:-1] if _string(key) else None
            if name is None or not name.isidentifier():
                raise self.error(item, "a key that is not a name is not supported")
            keywords.append(P.keyword(name + "_" if keyword.iskeyword(name) else name,
                                      self.expression(item["value"])))
        return P.call(self.imported("types", "SimpleNamespace"), *keywords)

    def unary(self, node: _Node) -> Any:
        operator = node["operator"]
        if operator in ("typeof", "void", "delete"):
            raise self.error(node, f"the operator {operator} is not supported")
        return P.unaryop("not" if operator == "!" else operator, self.expression(node["argument"]))

    def binary(self, node: _Node) -> Any:
        operator = node["operator"]
        if node["left"].tag == "privateidentifier":
            raise self.error(node, "#name in is not supported")
        left, right = self.expression(node["left"]), self.expression(node["right"])
        if operator in ("&&", "||"):
            return P.boolop("and" if operator == "&&" else "or", left, right)
        if operator == "??":  # `a ?? b`: `a` is evaluated once, kept in a name unless it is one or a constant
            value = left
            if not self.simple(node["left"]):
                value = P.name(self.fresh("value"))
                left = P.namedexpr(value, left)
            return P.ifexp(P.compare("is not", left, P.constant(None)), value, right)
        if operator == "instanceof":
            return P.call(P.name("isinstance"), left, right)
        if operator in COMPARISONS:
            op = COMPARISONS[operator]
            if self.none(node["right"]) and op in ("==", "!="):
                op = "is" if op == "==" else "is not"  # `x === null`
            return P.compare(op, left, right)
        if operator not in BINARY:
            raise self.error(node, f"the operator {operator} is not supported")
        if operator == "+" and self.textual(node["left"]) != self.textual(node["right"]):
            # `"n" + 1` makes a string of the number
            left, right = (left, P.call(P.name("str"), right)) if self.textual(node["left"]) else (
                P.call(P.name("str"), left), right)
        return P.binop(operator, left, right)

    def conditional(self, node: _Node) -> Any:
        return P.ifexp(self.expression(node["test"]), self.expression(node["consequent"]),
                       self.expression(node["alternate"]))

    def assignment_expression(self, node: _Node) -> Any:
        if node["operator"] == "=" and node["left"].tag == "identifier" and not self.lambdas:  # a lambda's own
            return P.namedexpr(self.python(node["left"]["name"]), self.expression(node["right"]))
        raise self.error(node, "an assignment within an expression is not supported")

    def mapped_member(self, node: _Node) -> str | None:
        """The function a member that is no global's translates to a call of (`len` for `length` and `size`, `str` for
        a caught exception's `message`), where it does; None for an attribute."""
        name = self.property_name(node["property"])
        target = node["object"]
        if target.tag == "identifier" and self.is_global(target) and target["name"] in OBJECTS:
            return None
        if name in ("length", "size") and name not in self.members:
            return "len"
        if name == "message" and target.tag == "identifier" and self.caught(target):
            return "str"  # an exception's message
        return None

    def member(self, node: _Node) -> Any:
        target = node["object"]
        if node["computed"]:
            return P.subscript(self.expression(target), self.expression(node["property"]))
        name = self.property_name(node["property"])
        if target.tag == "identifier" and self.is_global(target) and target["name"] in OBJECTS:
            mapped = OBJECTS[target["name"]].get(name)
            if not isinstance(mapped, str):  # a function, which only a call maps
                raise self.error(node, f"{target['name']}.{name} is not supported")
            return self.global_value(mapped)
        function = self.mapped_member(node)
        if function is not None:
            return P.call(P.name(function), self.expression(target))
        return P.attribute(self.expression(target), name)

    @staticmethod
    def property_name(key: _Node) -> str:
        """A property's Python name: `#x` is `_x`, and a keyword takes a `_`."""
        if key.tag == "privateidentifier":
            return "_" + key["name"]
        return key["name"] + "_" if keyword.iskeyword(key["name"]) else key["name"]

    def global_value(self, path: str) -> Any:
        """`module.name` (or a builtin) for a global's member, its module imported."""
        module, _, name = path.rpartition(".")
        return P.attribute(self.module(module), name) if module else P.name(name)

    def caught(self, identifier: _Node) -> bool:
        found = D.referents(self.definitions, identifier.at)
        return bool(found) and any(found[0] is entity for entity in self.catches)

    def call(self, node: _Node) -> Any:
        callee = node["callee"]
        if callee.tag == "super":
            init = P.attribute(P.call(P.name("super")), "__init__")
            return P.call(init, *self.arguments(node))
        if callee.tag == "memberexpression" and callee["object"].tag == "super":
            method = P.attribute(P.call(P.name("super")), self.property_name(callee["property"]))
            return P.call(method, *self.arguments(node))
        if callee.tag == "identifier" and self.is_global(callee) and callee["name"] in GLOBALS:
            return GLOBALS[callee["name"]](self, node)
        if callee.tag == "memberexpression" and not callee["computed"]:
            target, name = callee["object"], callee["property"]["name"]
            if target.tag == "identifier" and self.is_global(target) and target["name"] in OBJECTS:
                mapped = OBJECTS[target["name"]].get(name)
                if not callable(mapped):
                    raise self.error(node, f"{target['name']}.{name}() is not supported")
                return mapped(self, node)
            if callee["property"].tag == "identifier" and name in METHODS and name not in self.members:
                return METHODS[name](self, self.expression(target), node)
        return P.call(self.expression(callee), *self.arguments(node))

    def arguments(self, node: _Node) -> list[Any]:
        return [P.starred(self.expression(a["argument"])) if a.tag == "spreadelement" else self.expression(a)
                for a in node.items("arguments")]

    def arguments_of(self, node: _Node, *counts: int) -> list[Any]:
        """The arguments of a call that a mapping translates, which must be as many as one of `counts`."""
        given = node.items("arguments")
        if len(given) not in counts or any(a.tag == "spreadelement" for a in given):
            raise self.error(node, "this call's arguments are not supported")
        return self.arguments(node)

    def new(self, node: _Node) -> Any:
        callee = node["callee"]
        if callee.tag == "identifier" and self.is_global(callee):
            mapped = {"Error": "Exception", "TypeError": "TypeError", "RangeError": "ValueError",
                      "Set": "set", "Map": "dict"}.get(callee["name"])
            if mapped is None:
                raise self.error(node, f"new {callee['name']} is not supported")
            return P.call(P.name(mapped), *self.arguments(node))
        return P.call(self.expression(callee), *self.arguments(node))

    def function_value(self, node: _Node) -> Any:
        """An arrow function or a function expression used as a value: a lambda where its body is an expression,
        and a function declared before the statement otherwise."""
        if node.tag == "arrowfunctionexpression" and node["block"] is None and not node["isAsync"]:
            names: list[str] = []
            for param in node.items("params"):
                if param.tag != "identifier":
                    raise self.error(param, "a lambda's parameters must be names")
                names.append(self.python(param["name"]))
            self.lambdas += 1
            self.methods.append(bool(self.methods) and self.methods[-1])
            body = self.expression(node["body"])
            self.methods.pop()
            self.lambdas -= 1
            return P.lambda_(body, names)
        if self.lambdas:
            raise self.error(node, "a function with a body within a lambda is not supported")
        name = self.python(node["id"]["name"]) if node["id"] is not None else self.fresh("function")
        self.pending.append(self.function(node, name))
        return P.name(name)

    def await_(self, node: _Node) -> Any:
        return P.await_(self.expression(node["argument"]))

    def yield_(self, node: _Node) -> Any:
        argument = node["argument"]
        value = None if argument is None else self.expression(argument)
        return P.yieldfrom(value) if node["delegate"] else P.yield_(value)

    def callback(self, node: _Node) -> tuple[str, Any] | None:
        """The parameter and body of the callback `node` passes, if it is an arrow function of one name with an
        expression for its body."""
        arguments = node.items("arguments")
        if len(arguments) != 1:
            return None
        f = arguments[0]
        if f.tag == "arrowfunctionexpression" and len(f.items("params")) == 1 and (
                f["params"][0].tag == "identifier") and f["block"] is None:
            self.lambdas += 1
            body = self.expression(f["body"])
            self.lambdas -= 1
            return self.python(f["params"][0]["name"]), body
        return None

    def for_each(self, node: _Node) -> list[_Statement] | None:
        """`items.forEach(x => ...)` as a statement: a `for` loop."""
        callee = node["callee"]
        if not (callee.tag == "memberexpression" and not callee["computed"] and (
                callee["property"].tag == "identifier") and callee["property"]["name"] == "forEach" and (
                "forEach" not in self.members) and len(node.items("arguments")) == 1):
            return None
        f = node["arguments"][0]
        if not (f.tag == "arrowfunctionexpression" and len(f.items("params")) == 1 and (
                f["params"][0].tag == "identifier")):
            raise self.error(f, "forEach takes an arrow function of one parameter here")
        block = f["block"]
        body = self.block(block) if block is not None else [_Statement("Expr", value=self.expression(f["body"]))]
        return [_Statement("For", target=P.name(self.python(f["params"][0]["name"])),
                           iter=self.expression(callee["object"]), body=body)]

    def set_call(self, node: _Node) -> list[_Statement] | None:
        """`map.set(k, v)` as a statement: an assignment to `map[k]`."""
        callee = node["callee"]
        if callee.tag == "memberexpression" and not callee["computed"] and callee["property"].tag == "identifier" \
                and callee["property"]["name"] == "set" and "set" not in self.members and (
                len(node.items("arguments")) == 2):
            key, value = self.arguments(node)
            return [_Statement("Assign", targets=[P.subscript(self.expression(callee["object"]), key)], value=value)]
        return None

    def stripped(self, node: _Node) -> Any:
        return self.expression(node["expression"])  # parentheses, or a type assertion, which Python does not check

    EXPRESSIONS: dict[str, Callable[[_Translator, _Node], Any]] = {
        "identifier": identifier, "literal": literal, "constant": constant, "templateliteral": template,
        "thisexpression": this, "arrayexpression": array, "objectexpression": object, "unaryexpression": unary,
        "binaryexpression": binary, "logicalexpression": binary, "conditionalexpression": conditional,
        "assignmentexpression": assignment_expression, "memberexpression": member, "callexpression": call,
        "newexpression": new, "arrowfunctionexpression": function_value, "functionexpression": function_value,
        "awaitexpression": await_, "yieldexpression": yield_, "parenthesizedexpression": stripped,
        "tsasexpression": stripped, "tssatisfiesexpression": stripped, "tsnonnullexpression": stripped,
        "tstypeassertion": stripped,
    }

    # Types

    KEYWORDS = {"tsnumberkeyword": "float", "tsstringkeyword": "str", "tsbooleankeyword": "bool",
                "tsbigintkeyword": "int", "tsobjectkeyword": "object", "tsunknownkeyword": "object",
                "tsvoidkeyword": None, "tsundefinedkeyword": None, "tsnullkeyword": None}
    """TypeScript's type keywords, by the name of the Python type, None for `None`."""

    def type(self, node: _Node) -> Any:
        """A type as an annotation; None where Python has no counterpart, which leaves the annotation out."""
        if node.tag in self.KEYWORDS:
            name = self.KEYWORDS[node.tag]
            return P.constant(None) if name is None else P.name(name)
        if node.tag == "tsanykeyword":
            return self.imported("typing", "Any")
        if node.tag == "tsarraytype":
            element = self.type(node["elementType"])
            return None if element is None else P.subscript(P.name("list"), element)
        if node.tag == "tstypeoperator" and node["operator"] == "readonly" and node["typeAnnotation"] is not None:
            return self.type(node["typeAnnotation"])
        if node.tag == "tstupletype":
            elements = [self.type(t) for t in node.items("elementTypes")]
            if None in elements or not elements:
                return None
            return P.subscript(P.name("tuple"), P.tuple_(*elements))
        if node.tag == "tsuniontype":
            types = [self.type(t) for t in node.items("types")]
            if None in types:
                return None
            union = types[0]
            for t in types[1:]:
                union = P.binop("|", union, t)
            return union
        if node.tag == "tsparenthesizedtype":
            return self.type(node["typeAnnotation"])
        if node.tag == "tsliteraltype" and node["literal"].tag == "literal":
            return P.subscript(self.imported("typing", "Literal"), self.literal(node["literal"]))
        if node.tag == "tstypereference" and node["typeName"].tag == "identifier":
            name = node["typeName"]["name"]
            arguments = node["typeArguments"]
            args = [] if arguments is None else [self.type(t) for t in arguments.items("params")]
            if None in args:
                return None
            generic = {"Array": "list", "ReadonlyArray": "list", "Set": "set", "Map": "dict", "Record": "dict"}.get(
                name)
            if generic is not None and args:
                return P.subscript(P.name(generic), args[0] if len(args) == 1 else P.tuple_(*args))
            if name in ("Promise", "Array", "Set", "Map", "Record", "Partial", "Readonly"):
                return None
            if args:
                return P.subscript(P.name(self.python(name)), args[0] if len(args) == 1 else P.tuple_(*args))
            return P.name(self.python(name))
        return None


def _console(stream: str | None) -> Callable[[_Translator, _Node], Any]:
    def call(self: _Translator, node: _Node) -> Any:
        keywords = [] if stream is None else [P.keyword("file", P.attribute(self.module("sys"), stream))]
        return P.call(P.name("print"), *self.arguments(node), *keywords)
    return call


def _function(path: str) -> Callable[[_Translator, _Node], Any]:
    """A global function that is a Python function of the same arguments."""
    return lambda self, node: P.call(self.global_value(path), *self.arguments(node))


def _stringify(self: _Translator, node: _Node) -> Any:
    """`JSON.stringify(x)`, which writes no spaces, as `json.dumps` does with these separators."""
    separators = P.tuple_(P.constant(","), P.constant(":"))
    return P.call(P.attribute(self.module("json"), "dumps"), *self.arguments(node),
                  P.keyword("separators", separators))


def _power(self: _Translator, node: _Node) -> Any:
    base, exponent = self.arguments_of(node, 2)
    return P.binop("**", base, exponent)


def _object_view(view: str) -> Callable[[_Translator, _Node], Any]:
    """`Object.keys(o)` and the like, of an object, which is a `SimpleNamespace`."""
    def call(self: _Translator, node: _Node) -> Any:
        (value,) = self.arguments_of(node, 1)
        names = P.call(P.name("vars"), value)
        listed = names if view == "keys" else P.call(P.attribute(names, view))
        return P.call(P.name("list"), listed)
    return call


def _is_array(self: _Translator, node: _Node) -> Any:
    (value,) = self.arguments_of(node, 1)
    return P.call(P.name("isinstance"), value, P.name("list"))


# Global functions, by name, and the members of global objects, by object and name: a Python path for a value, or a
# function that translates a call.
GLOBALS: dict[str, Callable[[_Translator, _Node], Any]] = {
    "String": _function("str"), "Number": _function("float"), "Boolean": _function("bool"),
    "parseInt": _function("int"), "parseFloat": _function("float"),
}
OBJECTS: dict[str, dict[str, Any]] = {
    "console": {"log": _console(None), "error": _console("stderr"), "warn": _console("stderr")},
    "Math": {"floor": _function("math.floor"), "ceil": _function("math.ceil"), "sqrt": _function("math.sqrt"),
             "trunc": _function("math.trunc"), "abs": _function("abs"), "max": _function("max"),
             "min": _function("min"), "random": _function("random.random"), "pow": _power,
             "log": _function("math.log"), "exp": _function("math.exp"), "PI": "math.pi", "E": "math.e"},
    "JSON": {"stringify": _stringify, "parse": _function("json.loads")},
    "Object": {"keys": _object_view("keys"), "values": _object_view("values"), "entries": _object_view("items")},
    "Array": {"isArray": _is_array},
}


def _rename(name: str) -> Callable[[_Translator, Any, _Node], Any]:
    """A method that is Python's method of another name."""
    return lambda self, target, node: P.call(P.attribute(target, name), *self.arguments(node))


def _push(self: _Translator, target: Any, node: _Node) -> Any:
    given = node.items("arguments")
    args = self.arguments(node)
    if len(given) == 1 and given[0].tag != "spreadelement":
        return P.call(P.attribute(target, "append"), args[0])
    return P.call(P.attribute(target, "extend"), P.list_(*args))


def _includes(self: _Translator, target: Any, node: _Node) -> Any:
    """`includes` and `has`: `in`."""
    (value,) = self.arguments_of(node, 1)
    return P.compare("in", value, target)


def _join(self: _Translator, target: Any, node: _Node) -> Any:
    args = self.arguments_of(node, 0, 1)
    separator = args[0] if args else P.constant(",")
    strings = P.call(P.name("map"), P.name("str"), target)
    return P.call(P.attribute(separator, "join"), strings)


def _slice(self: _Translator, target: Any, node: _Node) -> Any:
    args = self.arguments_of(node, 0, 1, 2)
    bounds = P.slice_(args[0] if args else None, args[1] if len(args) > 1 else None)
    return P.subscript(target, bounds)


def _comprehension(kind: str) -> Callable[[_Translator, Any, _Node], Any]:
    """`map` and `filter` of a callback: a list comprehension where the callback is a lambda of one name, and
    Python's `map` or `filter` otherwise."""
    def call(self: _Translator, target: Any, node: _Node) -> Any:
        found = self.callback(node)
        if found is not None:
            name, body = found
            if kind == "map":
                return P.listcomp(body, P.comprehension(name, target))
            return P.listcomp(P.name(name), P.comprehension(name, target, [body]))
        (f,) = self.arguments_of(node, 1)
        return P.call(P.name("list"), P.call(P.name(kind), f, target))
    return call


def _reduce(self: _Translator, target: Any, node: _Node) -> Any:
    args = self.arguments_of(node, 1, 2)
    return P.call(P.attribute(self.module("functools"), "reduce"), args[0], target, *args[1:])


def _to_string(self: _Translator, target: Any, node: _Node) -> Any:
    self.arguments_of(node, 0)
    return P.call(P.name("str"), target)


# Methods of arrays, strings, maps and sets, by name.
METHODS: dict[str, Callable[[_Translator, Any, _Node], Any]] = {
    "push": _push, "includes": _includes, "join": _join, "slice": _slice, "map": _comprehension("map"),
    "filter": _comprehension("filter"), "reduce": _reduce, "toString": _to_string, "has": _includes,
    "toUpperCase": _rename("upper"), "toLowerCase": _rename("lower"), "trim": _rename("strip"),
    "startsWith": _rename("startswith"), "endsWith": _rename("endswith"), "entries": _rename("items"),
}


# --- The transaction ---

def transpile(store: Any, path: str, target: str) -> Callable[[Any], Any]:
    """The callback of the transaction that writes, as the module at `target`, the Python module that does what the
    TypeScript program the workspace holds at `path` does (`transpile_file`), read within a transaction of its own, so
    called with none open on `store`; LookupError where the workspace holds no file at `path`."""
    with store.transaction():
        return transpile_file(store, store.singleton(WORKSPACE).files({"path": path}), target)


def transpile_file(store: Any, program: Any, target: str) -> Callable[[Any], Any]:
    """The callback of the transaction that writes, as the module at `target`, the Python module that does what
    `program` does: its visitor, a `Programs.TypeScript5.Program` of `store`, read within the caller's transaction.
    Raises `TranspileError` at the first syntax node it cannot translate. What it gives holds no visitor."""
    body = [_value(statement) for statement in _Translator(store, program).program()]

    def transaction(txn: Any) -> Any:
        symbols = {"ws": store.registered("Programs.Framework.Workspace"),
                   "module": store.registered("Programs.Python3.Module")}
        return txn.uid(target).mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
            .symbols(symbols)
            .spec([
                lambda _: _.ws.files({target: lambda e: e.file(_.module)}),
                lambda _: _.module.body(body),
            ])]))])

    return transaction
