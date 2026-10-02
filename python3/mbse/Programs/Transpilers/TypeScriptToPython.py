"""TypeScriptToPython: translates TypeScript trees into Python trees, without parsing or printing text.

`transpile(program)` reads a `TypeScript.Syntax.Program` and returns a `Python.Syntax.Module`, which `Python314` prints.
It covers a subset of TypeScript, and raises `TranspileError` at the first node outside it, with the node's path:

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
`Definitions` tells a global from a name the program declares. A few methods of arrays and strings are mapped by name
(`push` is `append`, `length` is `len`, `map` and `filter` are comprehensions), unless a class or interface of the
program declares a member of that name. A call to a mapped global or method with arguments its mapping does not take
fails.

The translation keeps what code means where the two languages agree, and does not emulate where they differ: `%` of a
negative number, the truthiness of empty arrays and objects, `==` between values of different types, `+` between a
string and a number, and integers beyond 2 ** 53 behave as Python's do.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Callable
from typing import Any

from ..Framework.Errors import TranspileError
from ..Framework.Syntax import Parents, children, copy, walk
from ..Python import Syntax as P
from ..TypeScript import Definitions as D
from ..TypeScript import Syntax as S

__all__ = ["transpile"]

# Names the translation writes, which a name of the program must not take: Python's keywords and builtins it uses.
RESERVED = frozenset(keyword.kwlist) | {
    "self", "print", "len", "str", "int", "float", "bool", "isinstance", "list", "dict", "set", "range", "map",
    "filter", "vars", "super", "property", "staticmethod", "object", "Exception", "NotImplementedError", "math",
    "json", "random", "sys", "functools", "SimpleNamespace", "IntEnum", "StrEnum", "Any", "Literal"}
# Comparisons: TypeScript's operators, and Python's.
COMPARISONS = {"==": "==", "===": "==", "!=": "!=", "!==": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
               "in": "in"}
BINARY = {"+", "-", "*", "/", "%", "**", "<<", ">>", "&", "|", "^"}
# The modules a mapped global needs, by the name the translation writes.
MODULES = {"math": "math", "json": "json", "random": "random", "sys": "sys", "functools": "functools"}


def _name(name: str) -> P.Name:
    return P.Name(id=P.Identifier(spelling=name))


def _constant(spelling: str) -> P.Constant:
    return P.Constant(spelling=spelling)


def _call(function: Any, *args: Any, keywords: list[Any] | None = None) -> P.Call:
    if isinstance(function, str):
        function = _name(function)
    return P.Call(func=function, args=list(args), keywords=keywords or [])


def _attribute(value: Any, attr: str) -> P.Attribute:
    return P.Attribute(value=value, attr=P.Identifier(spelling=attr))


def _arguments(names: list[str]) -> P.Arguments:
    return P.Arguments(args=[P.Arg(arg=P.Identifier(spelling=n)) for n in names])


class _Translator:
    """Translates one program. Statements become lists of statements: an arrow function with a body, used as a value,
    becomes a function declared before the statement that uses it."""

    def __init__(self, program: S.Program):
        self.parents = Parents(program)
        self.definitions = D.define(program)
        self.imports: set[str] = set()  # the modules the translation needs
        self.from_imports: dict[str, set[str]] = {}  # names to import from a module
        self.pending: list[Any] = []  # statements that must come before the current one
        self.lambdas = 0  # how deep in a lambda the translation is, where nothing can be declared
        self.methods: list[bool] = []  # for each enclosing function, whether `self` is its `this`
        self.catches: set[int] = set()  # the entities a `catch` clause binds, by `id`
        self.members = {e.name for e in self.definitions.entities() if e.kind in ("method", "property", "accessor")}
        self.taken = {n.name for n in walk(program) if isinstance(n, S.Identifier)}
        self.counter = 0

    # Helpers

    def error(self, node: Any, message: str | None = None) -> TranspileError:
        return TranspileError(message or f"{node.KIND} is not supported", self.parents.path(node))

    def fresh(self, stem: str) -> str:
        """A name no name of the program takes, for a value the translation keeps."""
        while True:
            self.counter += 1
            name = f"_{stem}{self.counter}"
            if name not in self.taken:
                self.taken.add(name)
                return name

    def module(self, name: str) -> P.Name:
        """The module `name`, imported."""
        self.imports.add(name)
        return _name(name)

    def imported(self, module: str, name: str) -> P.Name:
        """`name` from `module`, imported."""
        self.from_imports.setdefault(module, set()).add(name)
        return _name(name)

    @staticmethod
    def python(name: str) -> str:
        """The Python spelling of a TypeScript name: one the translation writes, or a keyword, takes a `_`."""
        return name + "_" if name in RESERVED else name

    def is_global(self, identifier: S.Identifier) -> bool:
        """Whether `identifier` names a global: one the program does not declare."""
        return not D.referents(self.definitions, identifier)

    # The program

    def program(self, program: S.Program) -> P.Module:
        body = self.statements(program.body)
        head: list[Any] = [P.Import(names=[P.Alias(name=P.DottedName(names=[P.Identifier(spelling=m)]))])
                           for m in sorted(self.imports)]
        for module in sorted(self.from_imports):
            names = [P.Alias(name=P.DottedName(names=[P.Identifier(spelling=n)])) for n in sorted(
                self.from_imports[module])]
            head.append(P.ImportFrom(module=P.DottedName(names=[P.Identifier(spelling=module)]), names=names))
        return P.Module(body=head + body)

    # Statements

    def statements(self, statements: list[Any]) -> list[Any]:
        out: list[Any] = []
        for statement in statements:
            outer, self.pending = self.pending, []
            translated = self.statement(statement)
            out += self.pending + translated
            self.pending = outer
        return out

    def block(self, statement: Any) -> list[Any]:
        """A statement as a block's body, which is never empty."""
        body = self.statements(statement.body if isinstance(statement, S.BlockStatement) else [statement])
        return body if any(not isinstance(s, P.Comment) for s in body) else body + [P.Pass()]

    def statement(self, node: Any) -> list[Any]:
        method = self.STATEMENTS.get(type(node))
        if method is None:
            raise self.error(node)
        return method(self, node)

    def comment(self, node: S.Comment) -> list[Any]:
        lines = node.text.split("\n") if node.block else [node.text]
        return [P.Comment(text=" " + line.strip(" *") if node.block else line, trailing=node.trailing and i == 0)
                for i, line in enumerate(lines) if not node.block or line.strip(" *")]

    def expression_statement(self, node: S.ExpressionStatement) -> list[Any]:
        expression = node.expression
        if isinstance(expression, S.AssignmentExpression):
            return self.assignment(expression)
        if isinstance(expression, S.UpdateExpression):
            return [P.AugAssign(target=self.target(expression.argument), op="+" if expression.operator == "++" else "-",
                                value=_constant("1"))]
        if isinstance(expression, S.UnaryExpression) and expression.operator == "delete":
            return [P.Delete(targets=[self.target(expression.argument)])]
        if isinstance(expression, S.CallExpression):
            each = self.for_each(expression)
            if each is not None:
                return each
            mapped = self.set_call(expression)
            if mapped is not None:
                return mapped
        return [P.Expr(value=self.expression(expression))]

    def assignment(self, node: S.AssignmentExpression) -> list[Any]:
        operator = node.operator
        if operator in ("&&=", "||=", "??="):  # `a ||= b` assigns only where `a` is falsy
            target = self.target(node.left)
            current = self.expression(node.left)
            test: Any = {"&&=": current, "||=": P.UnaryOp(op="not", operand=current),
                         "??=": P.Compare(left=current, comparisons=[P.Comparison(op="is", comparator=_constant(
                             "None"))])}[operator]
            return [P.If(test=test, body=[P.Assign(targets=[target], value=self.expression(node.right))])]
        if operator != "=":
            op = operator[:-1]
            if op not in BINARY:
                raise self.error(node, f"the operator {operator} is not supported")
            return [P.AugAssign(target=self.target(node.left), op=op, value=self.expression(node.right))]
        targets = [self.target(node.left)]
        value = node.right
        while isinstance(value, S.AssignmentExpression) and value.operator == "=":  # `a = b = c`
            targets.append(self.target(value.left))
            value = value.right
        return [P.Assign(targets=targets, value=self.expression(value))]

    def target(self, node: Any) -> Any:
        """What an assignment assigns to."""
        if isinstance(node, (S.Identifier, S.MemberExpression)):
            translated = self.expression(node)
            if isinstance(translated, (P.Name, P.Attribute, P.Subscript)):
                return translated
        if isinstance(node, S.ArrayPattern):
            return P.Tuple(elts=[self.pattern_element(e) for e in node.elements])
        if isinstance(node, S.ParenthesizedExpression):
            return self.target(node.expression)
        raise self.error(node, f"{node.KIND} as a target is not supported")

    def pattern_element(self, node: Any) -> Any:
        if isinstance(node, S.Elision):
            return _name("_")
        if isinstance(node, S.RestElement):
            return P.Starred(value=self.target(node.argument))
        return self.target(node)

    def variables(self, node: S.VariableDeclaration) -> list[Any]:
        if node.declarationKind in ("using", "await using"):
            raise self.error(node, f"{node.declarationKind} is not supported")
        if node.declare:
            return []
        out: list[Any] = []
        for declarator in node.declarations:
            if declarator.init is not None and isinstance(declarator.id, S.Identifier) and isinstance(
                    declarator.init, (S.ArrowFunctionExpression, S.FunctionExpression)) and isinstance(
                    declarator.init.body, S.BlockStatement):
                out.append(self.function(declarator.init, self.python(declarator.id.name)))  # `const f = () => {}`
                continue
            target = self.binding(declarator.id)
            value = _constant("None") if declarator.init is None else self.expression(declarator.init)
            annotation = self.annotation(declarator.id) if isinstance(declarator.id, S.Identifier) else None
            if annotation is not None and declarator.init is not None:
                out.append(P.AnnAssign(target=target, annotation=annotation, value=value))
            else:
                out.append(P.Assign(targets=[target], value=value))
        return out

    def binding(self, node: Any) -> Any:
        if isinstance(node, S.Identifier):
            return _name(self.python(node.name))
        if isinstance(node, S.ArrayPattern):
            return P.Tuple(elts=[_name("_") if isinstance(e, S.Elision) else P.Starred(value=self.binding(e.argument))
                                 if isinstance(e, S.RestElement) else self.binding(e) for e in node.elements])
        raise self.error(node, f"{node.KIND} as a binding is not supported")

    def if_statement(self, node: S.IfStatement) -> list[Any]:
        orelse: list[Any] = []
        if node.alternate is not None:
            orelse = self.statements([node.alternate]) if isinstance(node.alternate, S.IfStatement) else self.block(
                node.alternate)
        return [P.If(test=self.expression(node.test), body=self.block(node.consequent), orelse=orelse)]

    def while_statement(self, node: S.WhileStatement) -> list[Any]:
        return [P.While(test=self.expression(node.test), body=self.block(node.body))]

    def do_while(self, node: S.DoWhileStatement) -> list[Any]:
        """`do body while (test)`: a `while True` that breaks after the body, which must not `continue`."""
        self.no_continue(node.body, node)
        stop = P.If(test=self.negate(self.expression(node.test)), body=[P.Break()])
        return [P.While(test=_constant("True"), body=self.block(node.body) + [stop])]

    def negate(self, test: Any) -> Any:
        if isinstance(test, P.UnaryOp) and test.op == "not":
            return test.operand
        return P.UnaryOp(op="not", operand=test)

    def no_continue(self, body: Any, loop: Any) -> None:
        """Raises if `body` continues the loop it is the body of: its translation would skip what follows the body."""
        for node in walk(body):
            if isinstance(node, S.ContinueStatement) and self.loop_of(node) is loop:
                raise self.error(node, "continue in this loop is not supported")

    def loop_of(self, node: Any) -> Any:
        """The loop a `break` or `continue` leaves, or for a `break` the `switch`; None outside of them."""
        for ancestor in self.parents.ancestors(node):
            if isinstance(ancestor, (S.WhileStatement, S.DoWhileStatement, S.ForStatement, S.ForInStatement,
                                     S.ForOfStatement)) or (isinstance(ancestor, S.SwitchStatement) and isinstance(
                                         node, S.BreakStatement)):
                return ancestor
            if isinstance(ancestor, (S.FunctionDeclaration, S.FunctionExpression, S.ArrowFunctionExpression)):
                break
        return None

    def for_statement(self, node: S.ForStatement) -> list[Any]:
        counted = self.counted(node)
        if counted is not None:
            return counted
        self.no_continue(node.body, node)
        out: list[Any] = []
        if isinstance(node.init, S.VariableDeclaration):
            out += self.variables(node.init)
        elif node.init is not None:
            out += self.update(node.init)
        body = self.block(node.body)
        if node.update is not None:
            body = [s for s in body if not isinstance(s, P.Pass)] + self.update(node.update)
        test = _constant("True") if node.test is None else self.expression(node.test)
        return out + [P.While(test=test, body=body)]

    def update(self, node: Any) -> list[Any]:
        if isinstance(node, S.SequenceExpression):
            return [s for e in node.expressions for s in self.update(e)]
        return self.expression_statement(S.ExpressionStatement(expression=node))

    def counted(self, node: S.ForStatement) -> list[Any] | None:
        """`for (let i = a; i < b; i++)` as `for i in range(a, b)`, where the body does not assign `i`; None for
        any other `for`."""
        init, test, update = node.init, node.test, node.update
        if not (isinstance(init, S.VariableDeclaration) and len(init.declarations) == 1 and isinstance(
                init.declarations[0].id, S.Identifier) and init.declarations[0].init is not None):
            return None
        name = init.declarations[0].id.name
        if not (isinstance(test, S.BinaryExpression) and isinstance(test.left, S.Identifier) and test.left.name == name
                and test.operator in ("<", "<=", ">", ">=")):
            return None
        step: int | None = None
        if isinstance(update, S.UpdateExpression) and isinstance(update.argument, S.Identifier) and (
                update.argument.name == name):
            step = 1 if update.operator == "++" else -1
        elif isinstance(update, S.AssignmentExpression) and update.operator in ("+=", "-=") and isinstance(
                update.left, S.Identifier) and update.left.name == name and isinstance(update.right, S.Literal) and (
                re.fullmatch("[0-9]+", update.right.raw)):
            step = int(update.right.raw) * (1 if update.operator == "+=" else -1)
        if step is None or (step > 0) != (test.operator in ("<", "<=")):
            return None
        for n in walk(node.body):  # the body must not change the counter
            assigned = n.left if isinstance(n, S.AssignmentExpression) else n.argument if isinstance(
                n, S.UpdateExpression) else None
            if isinstance(assigned, S.Identifier) and assigned.name == name:
                return None
        stop = self.expression(test.right)
        if test.operator in ("<=", ">="):  # one past the bound, folded where the bound is a number
            past = 1 if step > 0 else -1
            stop = _constant(str(int(stop.spelling) + past)) if isinstance(stop, P.Constant) and re.fullmatch(
                "[0-9]+", stop.spelling) else P.BinOp(left=stop, op="+" if past > 0 else "-", right=_constant("1"))
        bounds = [self.expression(init.declarations[0].init), stop] + ([] if step == 1 else [_constant(str(step))])
        return [P.For(target=_name(self.python(name)), iter=_call("range", *bounds), body=self.block(node.body))]

    def for_of(self, node: Any) -> list[Any]:
        left = node.left
        target = self.binding(left.declarations[0].id) if isinstance(left, S.VariableDeclaration) else self.target(left)
        iterable = self.expression(node.right)
        if isinstance(node, S.ForInStatement):  # the keys of an object
            iterable = _call("vars", iterable)
        elif node.isAwait:
            raise self.error(node, "for await is not supported")
        return [P.For(target=target, iter=iterable, body=self.block(node.body))]

    def switch(self, node: S.SwitchStatement) -> list[Any]:
        """`switch` as `if ... elif ... else`: each case must end its body, with `break`, `return`, `throw` or
        `continue`, but for cases that only share the next one's body."""
        out: list[Any] = []
        subject: Any = self.expression(node.discriminant)
        if not isinstance(subject, (P.Name, P.Constant)):
            name = self.fresh("subject")
            out.append(P.Assign(targets=[_name(name)], value=subject))
            subject = _name(name)
        branches: list[tuple[list[Any], list[Any]]] = []  # each branch's tests (none for default) and body
        tests: list[Any] = []
        default = False
        for i, case in enumerate(node.cases):
            body = [s for s in case.consequent if not isinstance(s, S.Comment)]
            if case.test is None:
                default = True
            else:
                test = P.Comparison(op="==", comparator=self.expression(case.test))
                tests.append(P.Compare(left=copy(subject), comparisons=[test]))
            if not body and i + 1 < len(node.cases):
                continue  # shares the next case's body
            if body and not isinstance(body[-1], (S.BreakStatement, S.ReturnStatement, S.ThrowStatement,
                                                   S.ContinueStatement)) and i + 1 < len(node.cases):
                raise self.error(case, "a case that falls through is not supported")
            final = body[-1] if body and isinstance(body[-1], S.BreakStatement) else None  # which `if` makes
            kept = [s for s in case.consequent if s is not final]
            for n in (n for s in kept for n in walk(s)):
                if isinstance(n, S.BreakStatement) and n.label is None and self.loop_of(n) is node:
                    raise self.error(n, "break within a case is not supported")
            branches.append(([] if default else tests, self.block(S.BlockStatement(body=kept))))
            tests, default = [], False
        chain: list[Any] = []
        for tests_, body in reversed(branches):
            if not tests_:
                chain = body
            else:
                test = tests_[0] if len(tests_) == 1 else P.BoolOp(op="or", values=tests_)
                chain = [P.If(test=test, body=body, orelse=chain)]
        return out + chain

    def jump(self, node: Any) -> list[Any]:
        if self.loop_of(node) is None:
            raise self.error(node, f"{node.KIND} outside of a loop is not supported")
        return [P.Break() if isinstance(node, S.BreakStatement) else P.Continue()]

    def return_statement(self, node: S.ReturnStatement) -> list[Any]:
        return [P.Return(value=None if node.argument is None else self.expression(node.argument))]

    def throw(self, node: S.ThrowStatement) -> list[Any]:
        return [P.Raise(exc=self.expression(node.argument))]

    def try_statement(self, node: S.TryStatement) -> list[Any]:
        handlers: list[Any] = []
        if node.handler is not None:
            param = node.handler.param
            if param is not None and not isinstance(param, S.Identifier):
                raise self.error(param, "a pattern in catch is not supported")
            if param is not None:
                entity = self.definitions.entity_of(param)
                self.catches.add(id(entity))
            handlers.append(P.ExceptHandler(type=_name("Exception"), name=None if param is None else P.Identifier(
                spelling=self.python(param.name)), body=self.block(node.handler.body)))
        return [P.Try(body=self.block(node.block), handlers=handlers,
                      finalbody=[] if node.finalizer is None else self.block(node.finalizer))]

    # Declarations

    def function_declaration(self, node: Any) -> list[Any]:
        if isinstance(node, S.TSDeclareFunction):
            return []  # an overload's signature
        return [self.function(node, self.python(node.id.name))]

    def function(self, node: Any, name: str, method: bool = False, decorators: list[Any] | None = None,
                 prefix: list[Any] | None = None) -> Any:
        """A function, an arrow function or a method as a `def`; `prefix` are statements its body starts with. An
        arrow function's `this` is the enclosing function's."""
        if getattr(node, "generator", False) and node.isAsync:  # an arrow function has no `generator`
            raise self.error(node, "an async generator is not supported")
        arrow = isinstance(node, S.ArrowFunctionExpression)
        self.methods.append(method or (arrow and bool(self.methods) and self.methods[-1]))
        args = self.parameters(node.params, method)
        if isinstance(node.body, S.BlockStatement):
            body = self.statements(node.body.body)
        else:
            outer, self.pending = self.pending, []
            value = self.expression(node.body)
            body = self.pending + [P.Return(value=value)]
            self.pending = outer
        body = self.outer_names(node) + (prefix or []) + body
        if not any(not isinstance(s, P.Comment) for s in body):
            body.append(P.Pass())
        self.methods.pop()
        kind = P.AsyncFunctionDef if node.isAsync else P.FunctionDef
        return kind(decorator_list=decorators or [], name=P.Identifier(spelling=name), args=args,
                    returns=self.type(node.returnType.typeAnnotation) if node.returnType is not None else None,
                    body=body)

    def outer_names(self, node: Any) -> list[Any]:
        """`global` and `nonlocal` for the names a function assigns but does not declare: in TypeScript, assigning
        a name of an enclosing scope assigns it there, where Python would make it the function's own."""
        if not isinstance(node.body, S.BlockStatement):
            return []
        own = self.definitions.scope_of(node.body)
        found: dict[str, list[str]] = {"global": [], "nonlocal": []}
        for target in self.assigned(node.body):
            entities = D.referents(self.definitions, target)
            if not entities:
                continue
            scope = entities[0].parent
            while scope.kind not in ("function", "module", "static block"):
                scope = scope.parent
            if scope is not own:
                which = found["global" if scope.parent is None else "nonlocal"]
                name = self.python(target.name)
                if name not in which:
                    which.append(name)
        out: list[Any] = []
        if found["global"]:
            out.append(P.Global(names=[P.Identifier(spelling=n) for n in found["global"]]))
        if found["nonlocal"]:
            out.append(P.Nonlocal(names=[P.Identifier(spelling=n) for n in found["nonlocal"]]))
        return out

    def assigned(self, node: Any) -> list[S.Identifier]:
        """The names `node` assigns, outside the functions within it, in source order."""
        out: list[S.Identifier] = []
        stack = [node]
        while stack:
            item = stack.pop()
            if isinstance(item, (S.FunctionDeclaration, S.FunctionExpression, S.ArrowFunctionExpression,
                                 S.ClassDeclaration, S.ClassExpression)):
                continue
            target = item.left if isinstance(item, S.AssignmentExpression) else item.argument if isinstance(
                item, S.UpdateExpression) else None
            if isinstance(target, S.Identifier):
                out.append(target)
            stack.extend(child for _, _, child in reversed(children(item)))
        return out

    def parameters(self, params: list[Any], method: bool) -> P.Arguments:
        args: list[Any] = [P.Arg(arg=P.Identifier(spelling="self"))] if method else []
        vararg = None
        for param in params:
            if isinstance(param, S.TSParameterProperty):
                param = param.parameter
            default = None
            if isinstance(param, S.AssignmentPattern):
                param, default = param.left, self.expression(param.right)
            if isinstance(param, S.RestElement) and isinstance(param.argument, S.Identifier):
                vararg = P.Arg(arg=P.Identifier(spelling=self.python(param.argument.name)),
                               annotation=None)
                continue
            if not isinstance(param, S.Identifier):
                raise self.error(param, f"{param.KIND} as a parameter is not supported")
            if param.name == "this":
                continue
            if param.optional and default is None:
                default = _constant("None")
            args.append(P.Arg(arg=P.Identifier(spelling=self.python(param.name)), annotation=self.annotation(param),
                              default_value=default))
        return P.Arguments(args=args, vararg=vararg)

    def annotation(self, node: Any) -> Any:
        return None if node.typeAnnotation is None else self.type(node.typeAnnotation.typeAnnotation)

    def class_declaration(self, node: Any) -> list[Any]:
        if node.declare:
            return []
        if node.decorators:
            raise self.error(node.decorators[0], "a decorator is not supported")
        bases: list[Any] = []
        if node.superClass is not None:
            base = node.superClass
            bases.append(_name("Exception") if isinstance(base, S.Identifier) and base.name == "Error" and (
                self.is_global(base)) else self.expression(base))
        body: list[Any] = []
        fields: list[Any] = []  # instance fields, which the constructor assigns
        constructor = None
        for member in node.body.body:
            if isinstance(member, S.Comment):
                body += self.comment(member)
            elif isinstance(member, (S.PropertyDefinition, S.TSAbstractPropertyDefinition)):
                body += self.field(member, fields)
            elif isinstance(member, (S.MethodDefinition, S.TSAbstractMethodDefinition)):
                if member.methodKind == "constructor":
                    constructor = member
                elif not isinstance(member.value, S.TSEmptyBodyFunctionExpression) or isinstance(
                        member, S.TSAbstractMethodDefinition):
                    body.append(self.method(member))
            elif isinstance(member, S.TSIndexSignature):
                continue  # a type
            else:
                raise self.error(member)
        if constructor is not None or fields:  # after the class's own attributes, before its methods
            index = next((i for i, s in enumerate(body) if isinstance(s, (P.FunctionDef, P.AsyncFunctionDef))),
                         len(body))
            body.insert(index, self.constructor(constructor, fields, node.superClass is not None))
        if not any(not isinstance(s, P.Comment) for s in body):
            body.append(P.Pass())
        return [P.ClassDef(name=P.Identifier(spelling=self.python(node.id.name)), bases=bases, body=body)]

    def member_name(self, member: Any) -> str:
        if member.computed:
            raise self.error(member, "a computed member name is not supported")
        if not isinstance(member.key, (S.Identifier, S.PrivateIdentifier)):
            raise self.error(member, "a member named by a literal is not supported")
        return self.property_name(member.key)

    def field(self, member: Any, fields: list[Any]) -> list[Any]:
        name = self.member_name(member)
        annotation = None if member.typeAnnotation is None else self.type(member.typeAnnotation.typeAnnotation)
        if member.static:
            value = _constant("None") if member.value is None else self.expression(member.value)
            if annotation is not None:
                return [P.AnnAssign(target=_name(name), annotation=annotation, value=value)]
            return [P.Assign(targets=[_name(name)], value=value)]
        if member.value is not None:
            self.methods.append(True)
            fields.append(P.Assign(targets=[_attribute(_name("self"), name)], value=self.expression(member.value)))
            self.methods.pop()
        if annotation is not None:
            return [P.AnnAssign(target=_name(name), annotation=annotation)]
        return []

    def constructor(self, member: Any, fields: list[Any], derived: bool) -> Any:
        """`__init__`: the constructor's body, with the parameter properties and the fields assigned after `super`
        is called, or first; or, without a constructor, one that passes its arguments to `super`."""
        if member is None:
            node = S.FunctionExpression(params=[S.RestElement(argument=S.Identifier(name="args"))] if derived else [],
                                        body=S.BlockStatement())
            prefix: list[Any] = []
            if derived:
                arguments = P.Starred(value=_name("args"))
                prefix.append(P.Expr(value=_call(_attribute(_call("super"), "__init__"), arguments)))
            return self.function(node, "__init__", method=True, prefix=prefix + fields)
        value = member.value
        properties: list[Any] = []  # `constructor(private x)` assigns `self.x = x`
        for param in value.params:
            if isinstance(param, S.TSParameterProperty):
                bound = param.parameter.left if isinstance(param.parameter, S.AssignmentPattern) else param.parameter
                name = self.python(bound.name)
                properties.append(P.Assign(targets=[_attribute(_name("self"), name)], value=_name(name)))
        made = self.function(value, "__init__", method=True)
        statements = made.body
        index = next((i + 1 for i, s in enumerate(statements) if isinstance(s, P.Expr) and isinstance(
            s.value, P.Call) and isinstance(s.value.func, P.Attribute) and s.value.func.attr.spelling == "__init__"),
                     0)
        statements[index:index] = properties + fields
        made.body = [s for s in statements if not isinstance(s, P.Pass)] or [P.Pass()]
        return made

    def method(self, member: Any) -> Any:
        name = self.member_name(member)
        if name == "toString" and not member.static and not member.value.params:
            name = "__str__"  # what `String(x)` and templates call, as `str(x)` and f-strings do
        if isinstance(member, S.TSAbstractMethodDefinition):
            raise_ = P.Raise(exc=_name("NotImplementedError"))
            node = S.FunctionExpression(params=member.value.params, returnType=member.value.returnType,
                                        body=S.BlockStatement())
            return self.function(node, name, method=not member.static, prefix=[raise_])
        decorators: list[Any] = []
        if member.static:
            decorators.append(_name("staticmethod"))
        if member.methodKind == "get":
            decorators.append(_name("property"))
        elif member.methodKind == "set":
            decorators.append(_attribute(_name(name), "setter"))
        return self.function(member.value, name, method=not member.static, decorators=decorators)

    def enum(self, node: S.TSEnumDeclaration) -> list[Any]:
        """An enum of numbers, as an `IntEnum`, or of strings, as a `StrEnum`."""
        if node.declare:
            return []
        members = [m for m in node.body.members if not isinstance(m, S.Comment)]
        strings = any(isinstance(m.initializer, S.Literal) and m.initializer.raw.startswith(("'", '"'))
                      for m in members)
        body: list[Any] = []
        following = 0
        for member in members:
            if member.computed or not isinstance(member.id, S.Identifier):
                raise self.error(member, "an enum member must be named by a name")
            name = self.property_name(member.id)
            value: Any
            if member.initializer is None:
                if strings:
                    raise self.error(member, "a member of a string enum needs a value")
                value = _constant(str(following))
                following += 1
            elif isinstance(member.initializer, S.Literal) and (
                    strings or re.fullmatch("[0-9]+", member.initializer.raw)):
                value = self.expression(member.initializer)
                if not strings:
                    following = int(member.initializer.raw) + 1
            else:
                raise self.error(member.initializer, "an enum member's value must be a literal")
            body.append(P.Assign(targets=[_name(name)], value=value))
        base = self.imported("enum", "StrEnum" if strings else "IntEnum")
        return [P.ClassDef(name=P.Identifier(spelling=self.python(node.id.name)), bases=[base],
                           body=body or [P.Pass()])]

    def type_alias(self, node: S.TSTypeAliasDeclaration) -> list[Any]:
        value = self.type(node.typeAnnotation)
        if value is None or node.typeParameters is not None:
            return []
        return [P.TypeAlias(name=_name(self.python(node.id.name)), value=value)]

    def import_declaration(self, node: S.ImportDeclaration) -> list[Any]:
        if node.importKind == "type":
            return []
        level, names = self.module_path(node.source)
        out: list[Any] = []
        named: list[Any] = []
        def parent() -> P.DottedName | None:
            return P.DottedName(names=names[:-1]) if len(names) > 1 else None

        for specifier in node.specifiers:
            if isinstance(specifier, S.ImportNamespaceSpecifier):
                local = self.python(specifier.local.name)
                if level:
                    out.append(P.ImportFrom(level=level, module=parent(), names=[P.Alias(
                        name=P.DottedName(names=[copy(n) for n in names[-1:]]), asname=P.Identifier(spelling=local))]))
                else:
                    out.append(P.Import(names=[P.Alias(name=P.DottedName(names=[copy(n) for n in names]),
                                                       asname=P.Identifier(spelling=local))]))
            elif isinstance(specifier, S.ImportSpecifier):
                if specifier.importKind == "type":
                    continue
                imported = specifier.imported.name if isinstance(specifier.imported, S.Identifier) else None
                if imported is None:
                    raise self.error(specifier, "importing a name that is a string is not supported")
                local = self.python(specifier.local.name)
                named.append(P.Alias(name=P.DottedName(names=[P.Identifier(spelling=self.python(imported))]),
                                     asname=None if local == self.python(imported) else P.Identifier(spelling=local)))
            else:
                raise self.error(specifier, "a default import is not supported")
        if named:
            out.insert(0, P.ImportFrom(level=level or None, module=P.DottedName(names=[copy(n) for n in names]),
                                       names=named))
        if not node.specifiers:
            out.append(P.Import(names=[P.Alias(name=P.DottedName(names=names))]) if not level else P.ImportFrom(
                level=level, module=parent(), names=[P.Alias(name=P.DottedName(names=names[-1:]))]))
        return out

    def module_path(self, source: S.Literal) -> tuple[int, list[P.Identifier]]:
        """A module's level (how many packages up, for a relative path) and its dotted name: `./a/b` is `.a.b`."""
        path = source.raw[1:-1]
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
            raise self.error(source, f"the module {source.raw} has no Python name")
        return level, [P.Identifier(spelling=self.python(p.replace("-", "_").replace("$", "_"))) for p in parts]

    def export_named(self, node: S.ExportNamedDeclaration) -> list[Any]:
        if node.declaration is not None:
            return self.statement(node.declaration)
        if node.source is not None:
            raise self.error(node, "a re-export is not supported")
        return []  # Python exports every name a module binds

    def export_default(self, node: S.ExportDefaultDeclaration) -> list[Any]:
        declaration = node.declaration
        if isinstance(declaration, (S.FunctionDeclaration, S.ClassDeclaration)) and declaration.id is not None:
            return self.statement(declaration)
        raise self.error(node, "a default export of a value is not supported")

    def skip(self, node: Any) -> list[Any]:
        return []  # type-only

    STATEMENTS: dict[type, Callable[[_Translator, Any], list[Any]]] = {
        S.Comment: comment, S.ExpressionStatement: expression_statement, S.VariableDeclaration: variables,
        S.IfStatement: if_statement, S.WhileStatement: while_statement, S.DoWhileStatement: do_while,
        S.ForStatement: for_statement, S.ForOfStatement: for_of, S.ForInStatement: for_of, S.SwitchStatement: switch,
        S.BreakStatement: jump, S.ContinueStatement: jump, S.ReturnStatement: return_statement,
        S.ThrowStatement: throw, S.TryStatement: try_statement,
        S.BlockStatement: lambda self, node: self.statements(node.body), S.EmptyStatement: lambda self, node: [],
        S.FunctionDeclaration: function_declaration, S.TSDeclareFunction: function_declaration,
        S.ClassDeclaration: class_declaration, S.TSEnumDeclaration: enum, S.TSTypeAliasDeclaration: type_alias,
        S.TSInterfaceDeclaration: skip, S.ImportDeclaration: import_declaration,
        S.ExportNamedDeclaration: export_named, S.ExportDefaultDeclaration: export_default,
    }

    # Expressions

    def expression(self, node: Any) -> Any:
        method = self.EXPRESSIONS.get(type(node))
        if method is None:
            raise self.error(node)
        return method(self, node)

    def identifier(self, node: S.Identifier) -> Any:
        if self.is_global(node):
            if node.name == "undefined":
                return _constant("None")
            if node.name in ("NaN", "Infinity"):
                return _attribute(self.module("math"), "nan" if node.name == "NaN" else "inf")
            if node.name in GLOBALS or node.name in OBJECTS:
                raise self.error(node, f"the global {node.name} is not supported here")
        return _name(self.python(node.name))

    def literal(self, node: S.Literal) -> Any:
        raw = node.raw
        if raw in ("true", "false"):
            return _constant(raw.capitalize())
        if raw == "null":
            return _constant("None")
        if raw[:1] in ("'", '"'):
            return _constant(self.string(raw))
        if raw.startswith("/"):
            raise self.error(node, "a regular expression is not supported")
        if raw.endswith("n"):
            raw = raw[:-1]  # a bigint: Python's integers have no bounds
        if re.fullmatch(r"0[0-7]+", raw):
            raw = "0o" + raw[1:]  # a legacy octal
        return _constant(raw)

    def string(self, raw: str) -> str:
        """A Python string literal's spelling of a TypeScript one: escapes Python lacks rewritten."""
        return re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: "\\U" + m.group(1).rjust(8, "0"), raw)

    def template(self, node: S.TemplateLiteral) -> Any:
        values: list[Any] = []
        for i, quasi in enumerate(node.quasis):
            text = self.string(quasi.raw).replace("{", "{{").replace("}", "}}").replace("\\`", "`").replace(
                '"', '\\"').replace("\n", "\\n")
            if text:
                values.append(P.StringText(spelling=text))
            if i < len(node.expressions):
                values.append(P.FormattedValue(value=self.expression(node.expressions[i])))
        return P.JoinedStr(prefix="f", quote='"', values=values)

    def this(self, node: S.ThisExpression) -> Any:
        if not self.methods or not self.methods[-1]:
            raise self.error(node, "this outside a method is not supported")
        return _name("self")

    def array(self, node: S.ArrayExpression) -> Any:
        elements: list[Any] = []
        for element in node.elements:
            if isinstance(element, S.Elision):
                raise self.error(element, "a hole in an array is not supported")
            elements.append(P.Starred(value=self.expression(element.argument)) if isinstance(
                element, S.SpreadElement) else self.expression(element))
        return P.List(elts=elements)

    def object(self, node: S.ObjectExpression) -> Any:
        keywords: list[Any] = []
        for item in node.properties:
            if isinstance(item, S.SpreadElement) or item.method or item.propertyKind != "init" or item.computed:
                raise self.error(item, f"{'a spread' if isinstance(item, S.SpreadElement) else 'this property'} "
                                       "in an object literal is not supported")
            key = item.key.name if isinstance(item.key, S.Identifier) else item.key.raw[1:-1] if isinstance(
                item.key, S.Literal) and item.key.raw.startswith(("'", '"')) else None
            if key is None or not key.isidentifier():
                raise self.error(item, "a key that is not a name is not supported")
            keywords.append(P.Keyword(arg=P.Identifier(spelling=key + "_" if keyword.iskeyword(key) else key),
                                      value=self.expression(item.value)))
        return _call(self.imported("types", "SimpleNamespace"), keywords=keywords)

    def unary(self, node: S.UnaryExpression) -> Any:
        if node.operator in ("typeof", "void", "delete"):
            raise self.error(node, f"the operator {node.operator} is not supported")
        return P.UnaryOp(op="not" if node.operator == "!" else node.operator, operand=self.expression(node.argument))

    def binary(self, node: Any) -> Any:
        operator = node.operator
        if isinstance(node.left, S.PrivateIdentifier):
            raise self.error(node, "#name in is not supported")
        left, right = self.expression(node.left), self.expression(node.right)
        if operator in ("&&", "||"):
            return P.BoolOp(op="and" if operator == "&&" else "or", values=[left, right])
        if operator == "??":  # `a ?? b`: `a` is evaluated once, kept in a name unless it is one or a constant
            value = left
            if not isinstance(left, (P.Name, P.Constant)):
                value = _name(self.fresh("value"))
                left = P.NamedExpr(target=value, value=left)
            test = P.Compare(left=left, comparisons=[P.Comparison(op="is not", comparator=_constant("None"))])
            return P.IfExp(test=test, body=copy(value), orelse=right)
        if operator == "instanceof":
            return _call("isinstance", left, right)
        if operator in COMPARISONS:
            op = COMPARISONS[operator]
            if isinstance(right, P.Constant) and right.spelling == "None" and op in ("==", "!="):
                op = "is" if op == "==" else "is not"  # `x === null`
            return P.Compare(left=left, comparisons=[P.Comparison(op=op, comparator=right)])
        if operator not in BINARY:
            raise self.error(node, f"the operator {operator} is not supported")
        if operator == "+" and self.textual(left) != self.textual(right):  # `"n" + 1` makes a string of the number
            left, right = (left, _call("str", right)) if self.textual(left) else (_call("str", left), right)
        return P.BinOp(left=left, op=operator, right=right)

    @staticmethod
    def textual(node: Any) -> bool:
        """Whether `node` is a string literal, an f-string or a sum that makes a string, which `+` makes a string
        of the other operand."""
        if isinstance(node, P.BinOp) and node.op == "+":
            return _Translator.textual(node.left) or _Translator.textual(node.right)
        return isinstance(node, P.JoinedStr) or (isinstance(node, P.Constant) and node.spelling.startswith(("'", '"')))

    def conditional(self, node: S.ConditionalExpression) -> Any:
        return P.IfExp(test=self.expression(node.test), body=self.expression(node.consequent),
                       orelse=self.expression(node.alternate))

    def assignment_expression(self, node: S.AssignmentExpression) -> Any:
        if node.operator == "=" and isinstance(node.left, S.Identifier) and not self.lambdas:  # a lambda's own
            return P.NamedExpr(target=_name(self.python(node.left.name)), value=self.expression(node.right))
        raise self.error(node, "an assignment within an expression is not supported")

    def member(self, node: S.MemberExpression) -> Any:
        target = node.object
        if node.computed:
            return P.Subscript(value=self.expression(target), slice=self.expression(node.property))
        name = self.property_name(node.property)
        if isinstance(target, S.Identifier) and self.is_global(target) and target.name in OBJECTS:
            mapped = OBJECTS[target.name].get(name)
            if not isinstance(mapped, str):  # a function, which only a call maps
                raise self.error(node, f"{target.name}.{name} is not supported")
            return self.global_value(mapped)
        if name == "length" and name not in self.members:
            return _call("len", self.expression(target))
        if name == "size" and name not in self.members:
            return _call("len", self.expression(target))
        if name == "message" and isinstance(target, S.Identifier) and self.caught(target):
            return _call("str", self.expression(target))  # an exception's message
        return _attribute(self.expression(target), name)

    @staticmethod
    def property_name(key: Any) -> str:
        """A property's Python name: `#x` is `_x`, and a keyword takes a `_`."""
        if isinstance(key, S.PrivateIdentifier):
            return "_" + key.name
        return key.name + "_" if keyword.iskeyword(key.name) else key.name

    def global_value(self, path: str) -> Any:
        """`module.name` (or a builtin) for a global's member, its module imported."""
        module, _, name = path.rpartition(".")
        return _attribute(self.module(module), name) if module else _name(name)

    def caught(self, identifier: S.Identifier) -> bool:
        found = D.referents(self.definitions, identifier)
        return bool(found) and id(found[0]) in self.catches

    def call(self, node: S.CallExpression) -> Any:
        callee = node.callee
        if isinstance(callee, S.Super):
            return _call(_attribute(_call("super"), "__init__"), *self.arguments(node.arguments))
        if isinstance(callee, S.MemberExpression) and isinstance(callee.object, S.Super):
            return _call(_attribute(_call("super"), self.property_name(callee.property)),
                         *self.arguments(node.arguments))
        if isinstance(callee, S.Identifier) and self.is_global(callee) and callee.name in GLOBALS:
            return GLOBALS[callee.name](self, node)
        if isinstance(callee, S.MemberExpression) and not callee.computed and isinstance(callee.object, S.Identifier) \
                and self.is_global(callee.object) and callee.object.name in OBJECTS:
            mapped = OBJECTS[callee.object.name].get(callee.property.name)
            if not callable(mapped):
                raise self.error(node, f"{callee.object.name}.{callee.property.name}() is not supported")
            return mapped(self, node)
        if isinstance(callee, S.MemberExpression) and not callee.computed and isinstance(
                callee.property, S.Identifier) and callee.property.name in METHODS and (
                callee.property.name not in self.members):
            return METHODS[callee.property.name](self, self.expression(callee.object), node)
        return _call(self.expression(callee), *self.arguments(node.arguments))

    def arguments(self, args: list[Any]) -> list[Any]:
        return [P.Starred(value=self.expression(a.argument)) if isinstance(a, S.SpreadElement) else self.expression(a)
                for a in args]

    def arguments_of(self, node: S.CallExpression, *counts: int) -> list[Any]:
        """The arguments of a call that a mapping translates, which must be as many as one of `counts`."""
        args = self.arguments(node.arguments)
        if len(args) not in counts or any(isinstance(a, P.Starred) for a in args):
            raise self.error(node, "this call's arguments are not supported")
        return args

    def new(self, node: S.NewExpression) -> Any:
        callee = node.callee
        if isinstance(callee, S.Identifier) and self.is_global(callee):
            mapped = {"Error": "Exception", "TypeError": "TypeError", "RangeError": "ValueError",
                      "Set": "set", "Map": "dict"}.get(callee.name)
            if mapped is None:
                raise self.error(node, f"new {callee.name} is not supported")
            return _call(mapped, *self.arguments(node.arguments))
        return _call(self.expression(callee), *self.arguments(node.arguments))

    def function_value(self, node: Any) -> Any:
        """An arrow function or a function expression used as a value: a lambda where its body is an expression,
        and a function declared before the statement otherwise."""
        if isinstance(node, S.ArrowFunctionExpression) and not isinstance(node.body, S.BlockStatement) and (
                not node.isAsync):
            names: list[str] = []
            for param in node.params:
                if not isinstance(param, S.Identifier):
                    raise self.error(param, "a lambda's parameters must be names")
                names.append(self.python(param.name))
            self.lambdas += 1
            self.methods.append(bool(self.methods) and self.methods[-1])
            body = self.expression(node.body)
            self.methods.pop()
            self.lambdas -= 1
            return P.Lambda(args=_arguments(names), body=body)
        if self.lambdas:
            raise self.error(node, "a function with a body within a lambda is not supported")
        name = self.python(node.id.name) if getattr(node, "id", None) is not None else self.fresh("function")
        self.pending.append(self.function(node, name))
        return _name(name)

    def await_(self, node: S.AwaitExpression) -> Any:
        return P.Await(value=self.expression(node.argument))

    def yield_(self, node: S.YieldExpression) -> Any:
        value = None if node.argument is None else self.expression(node.argument)
        return P.YieldFrom(value=value) if node.delegate else P.Yield(value=value)

    def callback(self, node: S.CallExpression) -> tuple[Any, Any] | None:
        """The parameter and body of the callback `node` passes, if it is an arrow function of one name with an
        expression for its body."""
        if len(node.arguments) != 1:
            return None
        f = node.arguments[0]
        if isinstance(f, S.ArrowFunctionExpression) and len(f.params) == 1 and isinstance(
                f.params[0], S.Identifier) and not isinstance(f.body, S.BlockStatement):
            self.lambdas += 1
            body = self.expression(f.body)
            self.lambdas -= 1
            return _name(self.python(f.params[0].name)), body
        return None

    def for_each(self, node: S.CallExpression) -> list[Any] | None:
        """`items.forEach(x => ...)` as a statement: a `for` loop."""
        callee = node.callee
        if not (isinstance(callee, S.MemberExpression) and not callee.computed and isinstance(
                callee.property, S.Identifier) and callee.property.name == "forEach" and (
                "forEach" not in self.members) and len(node.arguments) == 1):
            return None
        f = node.arguments[0]
        if not (isinstance(f, S.ArrowFunctionExpression) and len(f.params) == 1 and isinstance(
                f.params[0], S.Identifier)):
            raise self.error(f, "forEach takes an arrow function of one parameter here")
        body = self.block(f.body) if isinstance(f.body, S.BlockStatement) else [P.Expr(value=self.expression(f.body))]
        return [P.For(target=_name(self.python(f.params[0].name)), iter=self.expression(callee.object), body=body)]

    def set_call(self, node: S.CallExpression) -> list[Any] | None:
        """`map.set(k, v)` as a statement: an assignment to `map[k]`."""
        callee = node.callee
        if isinstance(callee, S.MemberExpression) and not callee.computed and isinstance(
                callee.property, S.Identifier) and callee.property.name == "set" and "set" not in self.members and (
                len(node.arguments) == 2):
            key, value = self.arguments(node.arguments)
            return [P.Assign(targets=[P.Subscript(value=self.expression(callee.object), slice=key)], value=value)]
        return None

    def stripped(self, node: Any) -> Any:
        return self.expression(node.expression)  # a type assertion, which Python does not check

    EXPRESSIONS: dict[type, Callable[[_Translator, Any], Any]] = {
        S.Identifier: identifier, S.Literal: literal, S.TemplateLiteral: template, S.ThisExpression: this,
        S.ArrayExpression: array, S.ObjectExpression: object, S.UnaryExpression: unary, S.BinaryExpression: binary,
        S.LogicalExpression: binary, S.ConditionalExpression: conditional,
        S.AssignmentExpression: assignment_expression, S.MemberExpression: member, S.CallExpression: call,
        S.NewExpression: new, S.ArrowFunctionExpression: function_value, S.FunctionExpression: function_value,
        S.AwaitExpression: await_, S.YieldExpression: yield_,
        S.ParenthesizedExpression: lambda self, node: self.expression(node.expression),
        S.TSAsExpression: stripped, S.TSSatisfiesExpression: stripped, S.TSNonNullExpression: stripped,
        S.TSTypeAssertion: stripped,
    }

    # Types

    def type(self, node: Any) -> Any:
        """A type as an annotation; None where Python has no counterpart, which leaves the annotation out."""
        keyword_ = {S.TSNumberKeyword: "float", S.TSStringKeyword: "str", S.TSBooleanKeyword: "bool",
                    S.TSBigIntKeyword: "int", S.TSObjectKeyword: "object", S.TSUnknownKeyword: "object",
                    S.TSVoidKeyword: "None", S.TSUndefinedKeyword: "None", S.TSNullKeyword: "None"}.get(type(node))
        if keyword_ is not None:
            return _constant("None") if keyword_ == "None" else _name(keyword_)
        if isinstance(node, S.TSAnyKeyword):
            return self.imported("typing", "Any")
        if isinstance(node, S.TSArrayType):
            element = self.type(node.elementType)
            return None if element is None else P.Subscript(value=_name("list"), slice=element)
        if isinstance(node, S.TSTypeOperator) and node.operator == "readonly" and node.typeAnnotation is not None:
            return self.type(node.typeAnnotation)
        if isinstance(node, S.TSTupleType):
            elements = [self.type(t) for t in node.elementTypes]
            return None if None in elements or not elements else P.Subscript(value=_name("tuple"), slice=P.Tuple(
                elts=elements))
        if isinstance(node, S.TSUnionType):
            types = [self.type(t) for t in node.types]
            if None in types:
                return None
            union = types[0]
            for t in types[1:]:
                union = P.BinOp(left=union, op="|", right=t)
            return union
        if isinstance(node, S.TSParenthesizedType):
            return self.type(node.typeAnnotation)
        if isinstance(node, S.TSLiteralType) and isinstance(node.literal, S.Literal):
            return P.Subscript(value=self.imported("typing", "Literal"), slice=self.literal(node.literal))
        if isinstance(node, S.TSTypeReference) and isinstance(node.typeName, S.Identifier):
            name = node.typeName.name
            args = [] if node.typeArguments is None else [self.type(t) for t in node.typeArguments.params]
            if None in args:
                return None
            generic = {"Array": "list", "ReadonlyArray": "list", "Set": "set", "Map": "dict", "Record": "dict"}.get(
                name)
            if generic is not None and args:
                return P.Subscript(value=_name(generic), slice=args[0] if len(args) == 1 else P.Tuple(elts=args))
            if name in ("Promise", "Array", "Set", "Map", "Record", "Partial", "Readonly"):
                return None
            if args:
                return P.Subscript(value=_name(self.python(name)), slice=args[0] if len(args) == 1 else P.Tuple(
                    elts=args))
            return _name(self.python(name))
        return None


def _console(stream: str | None) -> Callable[[_Translator, S.CallExpression], Any]:
    def call(self: _Translator, node: S.CallExpression) -> Any:
        keywords = [] if stream is None else [P.Keyword(arg=P.Identifier(spelling="file"), value=_attribute(
            self.module("sys"), stream))]
        return _call("print", *self.arguments(node.arguments), keywords=keywords)
    return call


def _function(path: str) -> Callable[[_Translator, S.CallExpression], Any]:
    """A global function that is a Python function of the same arguments."""
    return lambda self, node: _call(self.global_value(path), *self.arguments(node.arguments))


def _stringify(self: _Translator, node: S.CallExpression) -> Any:
    """`JSON.stringify(x)`, which writes no spaces, as `json.dumps` does with these separators."""
    separators = P.Tuple(elts=[_constant("','"), _constant("':'")])
    return _call(_attribute(self.module("json"), "dumps"), *self.arguments(node.arguments),
                 keywords=[P.Keyword(arg=P.Identifier(spelling="separators"), value=separators)])


def _power(self: _Translator, node: S.CallExpression) -> Any:
    base, exponent = self.arguments_of(node, 2)
    return P.BinOp(left=base, op="**", right=exponent)


def _object_view(view: str) -> Callable[[_Translator, S.CallExpression], Any]:
    """`Object.keys(o)` and the like, of an object, which is a `SimpleNamespace`."""
    def call(self: _Translator, node: S.CallExpression) -> Any:
        (value,) = self.arguments_of(node, 1)
        names = _call("vars", value)
        return _call("list", names if view == "keys" else _call(_attribute(names, view)))
    return call


def _is_array(self: _Translator, node: S.CallExpression) -> Any:
    (value,) = self.arguments_of(node, 1)
    return _call("isinstance", value, _name("list"))


# Global functions, by name, and the members of global objects, by object and name: a Python path for a value, or a
# function that translates a call.
GLOBALS: dict[str, Callable[[_Translator, S.CallExpression], Any]] = {
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


def _rename(name: str) -> Callable[[_Translator, Any, S.CallExpression], Any]:
    """A method that is Python's method of another name."""
    return lambda self, target, node: _call(_attribute(target, name), *self.arguments(node.arguments))


def _push(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    args = self.arguments(node.arguments)
    if len(args) == 1 and not isinstance(args[0], P.Starred):
        return _call(_attribute(target, "append"), args[0])
    return _call(_attribute(target, "extend"), P.List(elts=args))


def _includes(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    """`includes` and `has`: `in`."""
    (value,) = self.arguments_of(node, 1)
    return P.Compare(left=value, comparisons=[P.Comparison(op="in", comparator=target)])


def _join(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    args = self.arguments_of(node, 0, 1)
    separator = args[0] if args else _constant("','")
    return _call(_attribute(separator, "join"), _call("map", _name("str"), target))


def _slice(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    args = self.arguments_of(node, 0, 1, 2)
    return P.Subscript(value=target, slice=P.Slice(lower=args[0] if args else None,
                                                   upper=args[1] if len(args) > 1 else None))


def _comprehension(kind: str) -> Callable[[_Translator, Any, S.CallExpression], Any]:
    """`map` and `filter` of a callback: a list comprehension where the callback is a lambda of one name, and
    Python's `map` or `filter` otherwise."""
    def call(self: _Translator, target: Any, node: S.CallExpression) -> Any:
        found = self.callback(node)
        if found is not None:
            name, body = found
            if kind == "map":
                return P.ListComp(elt=body, generators=[P.Comprehension(target=name, iter=target)])
            return P.ListComp(elt=_name(name.id.spelling), generators=[P.Comprehension(target=name, iter=target,
                                                                                         ifs=[body])])
        (f,) = self.arguments_of(node, 1)
        return _call("list", _call(kind, f, target))
    return call


def _reduce(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    args = self.arguments_of(node, 1, 2)
    return _call(_attribute(self.module("functools"), "reduce"), args[0], target, *args[1:])


def _to_string(self: _Translator, target: Any, node: S.CallExpression) -> Any:
    self.arguments_of(node, 0)
    return _call("str", target)


# Methods of arrays, strings, maps and sets, by name.
METHODS: dict[str, Callable[[_Translator, Any, S.CallExpression], Any]] = {
    "push": _push, "includes": _includes, "join": _join, "slice": _slice, "map": _comprehension("map"),
    "filter": _comprehension("filter"), "reduce": _reduce, "toString": _to_string, "has": _includes,
    "toUpperCase": _rename("upper"), "toLowerCase": _rename("lower"), "trim": _rename("strip"),
    "startsWith": _rename("startswith"), "endsWith": _rename("endswith"), "entries": _rename("items"),
}


def transpile(program: S.Program) -> P.Module:
    """The Python module that does what `program` does. Raises `TranspileError` at the first node it cannot
    translate."""
    return _Translator(program).program(program)
