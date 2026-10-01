"""Prints TypeScript trees as TypeScript or JavaScript source text, in one fixed layout.

The layout: four spaces per level, braces on the line that opens them, one statement or member per line, and a
semicolon after every statement that takes one. Parentheses written in the tree are printed; those a tree built by
hand needs are added, by the precedence of the grammar: for expressions, also where `??` meets `||` or `&&`, where a
statement would start with `{`, `function`, `class` or `let [`, and where an arrow's body is an object; for types,
where a function, conditional or union type is an operand. The printer assumes a valid tree: standards validate before
they print.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import Syntax as S

__all__ = ["Printer"]

_INDENT = "    "

# Expressions' precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its
# place needs. `new` is printed with its arguments, so it binds as a member does.
SEQUENCE, ASSIGN, CONDITIONAL, COALESCE, OR, AND, BOR, BXOR, BAND, EQUALITY, RELATIONAL, SHIFT, ADD, MULTIPLY, POWER, \
    UNARY, POSTFIX, NEW, MEMBER, PRIMARY = range(20)
_BINARY = {"==": EQUALITY, "!=": EQUALITY, "===": EQUALITY, "!==": EQUALITY, "<": RELATIONAL, "<=": RELATIONAL,
           ">": RELATIONAL, ">=": RELATIONAL, "in": RELATIONAL, "instanceof": RELATIONAL, "<<": SHIFT, ">>": SHIFT,
           ">>>": SHIFT, "+": ADD, "-": ADD, "*": MULTIPLY, "/": MULTIPLY, "%": MULTIPLY, "**": POWER, "|": BOR,
           "^": BXOR, "&": BAND, "&&": AND, "||": OR, "??": COALESCE}
_PRECEDENCE: dict[type, int] = {
    S.SequenceExpression: SEQUENCE, S.AssignmentExpression: ASSIGN, S.ArrowFunctionExpression: ASSIGN,
    S.YieldExpression: ASSIGN, S.ConditionalExpression: CONDITIONAL, S.TSAsExpression: RELATIONAL,
    S.TSSatisfiesExpression: RELATIONAL, S.UnaryExpression: UNARY, S.AwaitExpression: UNARY,
    S.TSTypeAssertion: UNARY, S.UpdateExpression: POSTFIX, S.TSNonNullExpression: MEMBER,
    S.NewExpression: MEMBER, S.CallExpression: MEMBER, S.MemberExpression: MEMBER, S.ChainExpression: MEMBER,
    S.TaggedTemplateExpression: MEMBER, S.TSInstantiationExpression: MEMBER, S.ImportExpression: MEMBER,
}

# Types' precedence.
T_FUNCTION, T_CONDITIONAL, T_UNION, T_INTERSECTION, T_OPERATOR, T_POSTFIX, T_PRIMARY = range(7)
_TYPE_PRECEDENCE: dict[type, int] = {
    S.TSFunctionType: T_FUNCTION, S.TSConstructorType: T_FUNCTION, S.TSConditionalType: T_CONDITIONAL,
    S.TSUnionType: T_UNION, S.TSIntersectionType: T_INTERSECTION, S.TSTypeOperator: T_OPERATOR,
    S.TSInferType: T_OPERATOR, S.TSArrayType: T_POSTFIX, S.TSIndexedAccessType: T_POSTFIX,
    S.TSTypePredicate: T_FUNCTION,
}


def _precedence(node: Any) -> int:
    if isinstance(node, (S.BinaryExpression, S.LogicalExpression)):
        return _BINARY[node.operator]
    if isinstance(node, S.UpdateExpression) and node.prefix:
        return UNARY
    return _PRECEDENCE.get(type(node), PRIMARY)


def _leftmost(node: Any) -> Any:
    """The expression a statement made of `node` starts with."""
    while True:
        if isinstance(node, (S.BinaryExpression, S.LogicalExpression, S.AssignmentExpression)):
            node = node.left
        elif isinstance(node, (S.MemberExpression,)):
            node = node.object
        elif isinstance(node, (S.CallExpression, S.TaggedTemplateExpression)):
            node = node.callee if isinstance(node, S.CallExpression) else node.tag
        elif isinstance(node, S.ConditionalExpression):
            node = node.test
        elif isinstance(node, S.SequenceExpression):
            node = node.expressions[0]
        elif isinstance(node, (S.TSAsExpression, S.TSSatisfiesExpression, S.TSNonNullExpression, S.ChainExpression,
                               S.TSInstantiationExpression)):
            node = node.expression
        elif isinstance(node, S.UpdateExpression) and not node.prefix:
            node = node.argument
        else:
            return node


class Printer:
    """Prints a program as a file, and any other node as the text it stands for: a statement or a member as its
    lines, an expression, a pattern or a type as its text. With `jsx`, it prints for the JSX grammar, where an arrow
    function's lone type parameter is `<T,>`."""

    def __init__(self, jsx: bool = False):
        self.jsx = jsx

    def print(self, node: Any) -> str:
        if isinstance(node, S.Program):
            head = "" if node.hashbang is None else f"#!{node.hashbang}\n"
            return head + "".join(line + "\n" for line in self.block(node.body, 0))
        if isinstance(node, (S.Statement, S.ClassElement, S.TypeElement, S.SwitchCase)):
            return "\n".join(self.lines(node, 0))
        return self.text(node)

    # Statements

    def block(self, statements: list[Any], level: int) -> list[str]:
        """The lines of a list of statements or members, a trailing comment on the line before it."""
        lines: list[str] = []
        for statement in statements:
            if isinstance(statement, S.Comment) and statement.trailing and lines:
                lines[-1] += " " + self.comment(statement)
                continue
            lines += self.lines(statement, level)
        return lines

    def braced(self, head: str, body: list[Any], level: int) -> list[str]:
        """`head {`, the body one level in, and `}`; a trailing comment first in the body goes on the head's line."""
        lines = [f"{_INDENT * level}{head}{' ' if head else ''}{{"]
        if body and isinstance(body[0], S.Comment) and body[0].trailing:
            lines[0] += " " + self.comment(body[0])
            body = body[1:]
        if not body and lines[0].endswith("{"):
            return [lines[0] + "}"]
        return [*lines, *self.block(body, level + 1), f"{_INDENT * level}}}"]

    def comment(self, node: S.Comment) -> str:
        return f"/*{node.text}*/" if node.block else f"//{node.text}"

    level = 0  # the level of the statement being printed, where a function or class within an expression indents from

    def lines(self, node: Any, level: int) -> list[str]:
        outer, self.level = self.level, level
        method = self.STATEMENTS.get(type(node))
        lines = method(self, node, level) if method is not None else [_INDENT * level + self.simple(node)]
        self.level = outer
        return lines

    def simple(self, node: Any) -> str:
        return self.SIMPLE[type(node)](self, node)

    def body(self, head: str, body: Any, level: int) -> list[str]:
        """`head` and a statement it governs: a block on the same line, another statement on the next."""
        if isinstance(body, S.BlockStatement):
            return self.braced(head, body.body, level)
        return [_INDENT * level + head, *self.lines(body, level + 1)]

    def expression_statement(self, node: S.ExpressionStatement) -> str:
        expression = node.expression
        text = self.e(expression, SEQUENCE)
        start = _leftmost(expression)
        if isinstance(start, (S.ObjectExpression, S.FunctionExpression, S.ClassExpression, S.ObjectPattern)) or (
                isinstance(start, S.Identifier) and start.name == "let" and text.startswith("let[")):
            text = f"({text})"
        return text + ";"

    def variable_declaration(self, node: S.VariableDeclaration) -> str:
        return self.declaration(node) + ";"

    def declaration(self, node: S.VariableDeclaration, without_in: bool = False) -> str:
        declarators = ", ".join(self.declarator(d, without_in) for d in node.declarations)
        return f"{'declare ' if node.declare else ''}{node.declarationKind} {declarators}"

    def declarator(self, node: S.VariableDeclarator, without_in: bool = False) -> str:
        text = self.text(node.id)
        if node.definite:  # `id!: type`, where `id` is a name
            text = f"{self.binding_name(node.id)}!{self.annotation(node.id.typeAnnotation)}"
        if node.init is not None:
            text += f" = {self.e(node.init, ASSIGN, without_in)}"
        return text

    def if_statement(self, node: S.IfStatement, level: int) -> list[str]:
        lines = self.body(f"if ({self.e(node.test, SEQUENCE)})", node.consequent, level)
        alternate = node.alternate
        if alternate is None:
            return lines
        if isinstance(alternate, S.IfStatement):
            tail = self.if_statement(alternate, level)
            tail[0] = f"{_INDENT * level}else {tail[0].lstrip()}"
        else:
            tail = self.body("else", alternate, level)
        if isinstance(node.consequent, S.BlockStatement):  # `} else {`
            lines[-1] += " " + tail[0].lstrip()
            tail = tail[1:]
        return lines + tail

    def loop(self, node: Any, level: int) -> list[str]:
        if isinstance(node, S.WhileStatement):
            return self.body(f"while ({self.e(node.test, SEQUENCE)})", node.body, level)
        if isinstance(node, S.DoWhileStatement):
            lines = self.body("do", node.body, level)
            tail = f"while ({self.e(node.test, SEQUENCE)});"
            if isinstance(node.body, S.BlockStatement):
                lines[-1] += " " + tail
            else:
                lines.append(_INDENT * level + tail)
            return lines
        if isinstance(node, S.ForStatement):
            init = "" if node.init is None else (self.declaration(node.init, True) if isinstance(
                node.init, S.VariableDeclaration) else self.e(node.init, SEQUENCE, True))
            test = "" if node.test is None else " " + self.e(node.test, SEQUENCE)
            update = "" if node.update is None else " " + self.e(node.update, SEQUENCE)
            return self.body(f"for ({init};{test};{update})", node.body, level)
        left = self.declaration(node.left) if isinstance(node.left, S.VariableDeclaration) else self.e(
            node.left, MEMBER if isinstance(node, S.ForOfStatement) else UNARY)
        if isinstance(node, S.ForInStatement):
            return self.body(f"for ({left} in {self.e(node.right, SEQUENCE)})", node.body, level)
        keyword = "for await" if node.isAwait else "for"
        if isinstance(node.left, S.Identifier) and node.left.name == "async" and not node.isAwait:
            left = f"({left})"  # `for (async of ...)` would start an arrow
        return self.body(f"{keyword} ({left} of {self.e(node.right, ASSIGN)})", node.body, level)

    def switch(self, node: S.SwitchStatement, level: int) -> list[str]:
        lines = [f"{_INDENT * level}switch ({self.e(node.discriminant, SEQUENCE)}) {{"]
        for case in node.cases:
            lines += self.case(case, level + 1)
        return [*lines, f"{_INDENT * level}}}"]

    def case(self, node: S.SwitchCase, level: int) -> list[str]:
        head = "default:" if node.test is None else f"case {self.e(node.test, SEQUENCE)}:"
        lines = [_INDENT * level + head]
        body = node.consequent
        if body and isinstance(body[0], S.Comment) and body[0].trailing:
            lines[0] += " " + self.comment(body[0])
            body = body[1:]
        return lines + self.block(body, level + 1)

    def try_statement(self, node: S.TryStatement, level: int) -> list[str]:
        lines = self.braced("try", node.block.body, level)
        if node.handler is not None:
            handler = node.handler
            head = "catch" if handler.param is None else f"catch ({self.text(handler.param)})"
            inner = self.braced(head, handler.body.body, level)
            lines[-1] += " " + inner[0].strip()
            lines += inner[1:]
        if node.finalizer is not None:
            inner = self.braced("finally", node.finalizer.body, level)
            lines[-1] += " " + inner[0].strip()
            lines += inner[1:]
        return lines

    def labeled(self, node: S.LabeledStatement, level: int) -> list[str]:
        inner = self.lines(node.body, level)
        inner[0] = f"{_INDENT * level}{self.text(node.label)}: {inner[0].strip()}"
        return inner

    def function(self, node: Any, level: int) -> list[str]:
        head = self.function_head(node)
        if isinstance(node, S.TSDeclareFunction):
            return [f"{_INDENT * level}{'declare ' if node.declare else ''}{head};"]
        return self.braced(head, node.body.body, level)

    def function_head(self, node: Any) -> str:
        keyword = ("async " if node.isAsync else "") + "function" + ("*" if node.generator else "")
        name = "" if node.id is None else " " + self.text(node.id)
        return f"{keyword}{name}{self.signature(node)}"

    def signature(self, node: Any, arrow: bool = False) -> str:
        """`<typeParameters>(params): returnType`, or with `arrow` `... => returnType` for a function type."""
        parameters = "" if node.typeParameters is None else self.text(node.typeParameters)
        params = ", ".join(self.text(p) for p in node.params)
        returns = "" if node.returnType is None else (
            f" => {self.t(node.returnType.typeAnnotation, T_FUNCTION)}" if arrow else self.annotation(node.returnType))
        return f"{parameters}({params}){returns}"

    def class_lines(self, node: Any, level: int) -> list[str]:
        decorators = [_INDENT * level + self.text(d) for d in node.decorators]
        return decorators + self.braced(self.class_head(node), node.body.body, level)

    def class_head(self, node: Any) -> str:
        head = ("declare " if getattr(node, "declare", False) else "") + (
            "abstract " if getattr(node, "abstract", False) else "") + "class"
        if node.id is not None:
            head += " " + self.text(node.id)
        if node.typeParameters is not None:
            head += self.text(node.typeParameters)
        if node.superClass is not None:
            head += f" extends {self.e(node.superClass, MEMBER)}"
            if node.superTypeArguments is not None:
                head += self.text(node.superTypeArguments)
        if node.implements:
            head += " implements " + ", ".join(self.text(i) for i in node.implements)
        return head

    def member_modifiers(self, node: Any, abstract: bool = False) -> str:
        """A class member's modifiers, in the order TypeScript requires."""
        words = [node.accessibility] if getattr(node, "accessibility", None) else []
        if getattr(node, "declare", False):
            words.append("declare")
        if getattr(node, "static", False):
            words.append("static")
        if abstract:
            words.append("abstract")
        if getattr(node, "override", False):
            words.append("override")
        if getattr(node, "readonly", False):
            words.append("readonly")
        return "".join(w + " " for w in words)

    def method(self, node: Any, level: int) -> list[str]:
        value = node.value
        head = self.member_modifiers(node, isinstance(node, S.TSAbstractMethodDefinition))
        head += ("async " if value.isAsync else "") + ("*" if value.generator else "")
        if node.methodKind in ("get", "set"):
            head += node.methodKind + " "
        head += self.key(node.key, node.computed) + ("?" if node.optional else "") + self.signature(value)
        decorators = [_INDENT * level + self.text(d) for d in node.decorators]
        if isinstance(value, S.TSEmptyBodyFunctionExpression):
            return decorators + [f"{_INDENT * level}{head};"]
        return decorators + self.braced(head, value.body.body, level)

    def property_definition(self, node: Any, level: int) -> list[str]:
        head = self.member_modifiers(node, isinstance(node, (S.TSAbstractPropertyDefinition,
                                                              S.TSAbstractAccessorProperty)))
        if isinstance(node, (S.AccessorProperty, S.TSAbstractAccessorProperty)):
            head += "accessor "
        head += self.key(node.key, node.computed) + ("?" if node.optional else "") + ("!" if node.definite else "")
        if node.typeAnnotation is not None:
            head += self.annotation(node.typeAnnotation)
        if node.value is not None:
            head += f" = {self.e(node.value, ASSIGN)}"
        return [_INDENT * level + self.text(d) for d in node.decorators] + [f"{_INDENT * level}{head};"]

    def key(self, key: Any, computed: bool) -> str:
        return f"[{self.e(key, ASSIGN)}]" if computed else self.text(key)

    def static_block(self, node: S.StaticBlock, level: int) -> list[str]:
        return self.braced("static", node.body, level)

    def interface(self, node: S.TSInterfaceDeclaration, level: int) -> list[str]:
        head = f"{'declare ' if node.declare else ''}interface {self.text(node.id)}"
        if node.typeParameters is not None:
            head += self.text(node.typeParameters)
        if node.extends:
            head += " extends " + ", ".join(self.text(h) for h in node.extends)
        return self.braced(head, node.body.body, level)

    def enum(self, node: S.TSEnumDeclaration, level: int) -> list[str]:
        head = f"{'declare ' if node.declare else ''}{'const ' if node.const else ''}enum {self.text(node.id)}"
        lines = [f"{_INDENT * level}{head} {{"]
        for member in node.body.members:  # each on its line, with a comma; a trailing comment on the line before it
            if isinstance(member, S.Comment):
                if member.trailing:
                    lines[-1] += " " + self.comment(member)
                else:
                    lines.append(_INDENT * (level + 1) + self.comment(member))
            else:
                lines.append(f"{_INDENT * (level + 1)}{self.text(member)},")
        if len(lines) == 1 and lines[0].endswith("{"):
            return [lines[0] + "}"]
        return [*lines, f"{_INDENT * level}}}"]

    def module(self, node: S.TSModuleDeclaration, level: int) -> list[str]:
        head = "declare " if node.declare else ""
        head += "global" if node.moduleKind == "global" else f"{node.moduleKind} {self.text(node.id)}"
        if node.body is None:
            return [f"{_INDENT * level}{head};"]
        return self.braced(head, node.body.body, level)

    def export_named(self, node: S.ExportNamedDeclaration, level: int) -> list[str]:
        if node.declaration is not None:
            inner = self.lines(node.declaration, level)
            index = next(i for i, line in enumerate(inner) if not line.strip().startswith("@"))
            inner[index] = f"{_INDENT * level}export {inner[index].strip()}"
            return inner
        kind = "type " if node.exportKind == "type" else ""
        text = f"export {kind}{{{', '.join(self.text(s) for s in node.specifiers)}}}"
        if node.source is not None:
            text += f" from {self.text(node.source)}"
        return [_INDENT * level + text + self.with_attributes(node.attributes) + ";"]

    def export_default(self, node: S.ExportDefaultDeclaration, level: int) -> list[str]:
        declaration = node.declaration
        if isinstance(declaration, S.Statement):
            inner = self.lines(declaration, level)
            index = next(i for i, line in enumerate(inner) if not line.strip().startswith("@"))
            inner[index] = f"{_INDENT * level}export default {inner[index].strip()}"
            return inner
        text = self.e(declaration, ASSIGN)
        start = _leftmost(declaration)
        if isinstance(start, (S.FunctionExpression, S.ClassExpression)):
            text = f"({text})"
        return [f"{_INDENT * level}export default {text};"]

    def with_attributes(self, attributes: list[Any]) -> str:
        if not attributes:
            return ""
        return " with { " + ", ".join(self.text(a) for a in attributes) + " }"

    STATEMENTS: dict[type, Callable[[Printer, Any, int], list[str]]] = {
        S.BlockStatement: lambda self, node, level: self.braced("", node.body, level),
        S.IfStatement: if_statement, S.WhileStatement: loop, S.DoWhileStatement: loop, S.ForStatement: loop,
        S.ForInStatement: loop, S.ForOfStatement: loop, S.SwitchStatement: switch, S.SwitchCase: case,
        S.TryStatement: try_statement, S.LabeledStatement: labeled,
        S.WithStatement: lambda self, node, level: self.body(f"with ({self.e(node.object, SEQUENCE)})", node.body,
                                                             level),
        S.FunctionDeclaration: function, S.TSDeclareFunction: function, S.ClassDeclaration: class_lines,
        S.MethodDefinition: method, S.TSAbstractMethodDefinition: method,
        S.PropertyDefinition: property_definition, S.TSAbstractPropertyDefinition: property_definition,
        S.AccessorProperty: property_definition, S.TSAbstractAccessorProperty: property_definition,
        S.StaticBlock: static_block, S.TSInterfaceDeclaration: interface, S.TSEnumDeclaration: enum,
        S.TSModuleDeclaration: module, S.ExportNamedDeclaration: export_named,
        S.ExportDefaultDeclaration: export_default,
    }

    def import_declaration(self, node: S.ImportDeclaration) -> str:
        head = "import " + ("type " if node.importKind == "type" else "") + (
            "defer " if node.phase == "defer" else "")
        if not node.specifiers:
            return f"{head}{self.text(node.source)}{self.with_attributes(node.attributes)};"
        parts: list[str] = []
        named: list[str] = []
        for specifier in node.specifiers:
            if isinstance(specifier, S.ImportSpecifier):
                named.append(self.text(specifier))
            else:
                parts.append(self.text(specifier))
        if named:
            parts.append("{" + ", ".join(named) + "}")
        return f"{head}{', '.join(parts)} from {self.text(node.source)}{self.with_attributes(node.attributes)};"

    def export_all(self, node: S.ExportAllDeclaration) -> str:
        text = "export " + ("type " if node.exportKind == "type" else "") + "*"
        if node.exported is not None:
            text += f" as {self.text(node.exported)}"
        return f"{text} from {self.text(node.source)}{self.with_attributes(node.attributes)};"

    def import_equals(self, node: S.TSImportEqualsDeclaration) -> str:
        kind = "type " if node.importKind == "type" else ""
        return f"import {kind}{self.text(node.id)} = {self.text(node.moduleReference)};"

    def type_alias(self, node: S.TSTypeAliasDeclaration) -> str:
        parameters = "" if node.typeParameters is None else self.text(node.typeParameters)
        return (f"{'declare ' if node.declare else ''}type {self.text(node.id)}{parameters} = "
                f"{self.t(node.typeAnnotation, T_FUNCTION)};")

    def jump(self, keyword: str, node: Any) -> str:
        return keyword + ("" if node.label is None else " " + self.text(node.label)) + ";"

    SIMPLE: dict[type, Callable[[Printer, Any], str]] = {
        S.Comment: lambda self, node: self.comment(node), S.ExpressionStatement: expression_statement,
        S.VariableDeclaration: variable_declaration, S.EmptyStatement: lambda self, node: ";",
        S.DebuggerStatement: lambda self, node: "debugger;",
        S.ReturnStatement: lambda self, node: "return;" if node.argument is None else (
            f"return {self.e(node.argument, SEQUENCE)};"),
        S.ThrowStatement: lambda self, node: f"throw {self.e(node.argument, SEQUENCE)};",
        S.BreakStatement: lambda self, node: self.jump("break", node),
        S.ContinueStatement: lambda self, node: self.jump("continue", node),
        S.ImportDeclaration: import_declaration, S.ExportAllDeclaration: export_all,
        S.TSImportEqualsDeclaration: import_equals,
        S.TSExportAssignment: lambda self, node: f"export = {self.e(node.expression, ASSIGN)};",
        S.TSNamespaceExportDeclaration: lambda self, node: f"export as namespace {self.text(node.id)};",
        S.TSTypeAliasDeclaration: type_alias,
        S.TSIndexSignature: lambda self, node: self.index_signature(node) + ";",
        S.TSPropertySignature: lambda self, node: self.text(node) + ";",
        S.TSMethodSignature: lambda self, node: self.text(node) + ";",
        S.TSCallSignatureDeclaration: lambda self, node: self.text(node) + ";",
        S.TSConstructSignatureDeclaration: lambda self, node: self.text(node) + ";",
    }

    # Expressions

    def e(self, node: Any, needed: int, without_in: bool = False) -> str:
        """`node`'s text, parenthesized if it binds less than its place needs; with `without_in`, also if it holds an
        `in` operator outside parentheses (a `for` statement's initializer)."""
        text = self.text(node)
        if _precedence(node) < needed or (without_in and self.has_in(node)):
            return f"({text})"
        return text

    def has_in(self, node: Any) -> bool:
        if isinstance(node, S.BinaryExpression):
            return node.operator == "in" or self.has_in(node.left) or self.has_in(node.right)
        if isinstance(node, (S.LogicalExpression, S.AssignmentExpression)):
            return self.has_in(node.left) or self.has_in(node.right)
        if isinstance(node, S.ConditionalExpression):
            return self.has_in(node.test) or self.has_in(node.consequent) or self.has_in(node.alternate)
        if isinstance(node, S.SequenceExpression):
            return any(self.has_in(e) for e in node.expressions)
        if isinstance(node, (S.TSAsExpression, S.TSSatisfiesExpression)):
            return self.has_in(node.expression)
        if isinstance(node, S.ArrowFunctionExpression):
            return self.has_in(node.body)
        return False

    def text(self, node: Any) -> str:
        return self.TEXTS[type(node)](self, node)

    def binary(self, node: Any) -> str:
        level = _BINARY[node.operator]
        if node.operator == "**":
            left = self.e(node.left, POWER + 1)
            if isinstance(node.left, (S.UnaryExpression, S.AwaitExpression, S.TSTypeAssertion)):
                left = f"({self.text(node.left)})"  # `-a ** b` is not JavaScript
            return f"{left} ** {self.e(node.right, POWER)}"
        left, right = self.e(node.left, level), self.e(node.right, level + 1)
        if isinstance(node, S.LogicalExpression):  # `??` does not mix with `||` and `&&` without parentheses
            for side, operand in (("left", node.left), ("right", node.right)):
                if isinstance(operand, S.LogicalExpression) and (operand.operator == "??") != (node.operator == "??"):
                    text = f"({self.text(operand)})"
                    left, right = (text, right) if side == "left" else (left, text)
        if isinstance(node.left, S.PrivateIdentifier):
            left = self.text(node.left)
        return f"{left} {node.operator} {right}"

    def assignment(self, node: S.AssignmentExpression) -> str:
        left = self.e(node.left, MEMBER) if not isinstance(node.left, (S.ObjectPattern, S.ArrayPattern)) else (
            self.text(node.left))
        return f"{left} {node.operator} {self.e(node.right, ASSIGN)}"

    def conditional(self, node: S.ConditionalExpression) -> str:
        return (f"{self.e(node.test, COALESCE)} ? {self.e(node.consequent, ASSIGN)} : "
                f"{self.e(node.alternate, ASSIGN)}")

    def unary(self, node: S.UnaryExpression) -> str:
        argument = self.e(node.argument, UNARY)
        if node.operator in ("typeof", "void", "delete"):
            return f"{node.operator} {argument}"
        if node.operator in ("+", "-") and argument.startswith(node.operator):
            return f"{node.operator} {argument}"  # `--a` and `++a` would be updates
        return f"{node.operator}{argument}"

    def update(self, node: S.UpdateExpression) -> str:
        if node.prefix:
            return f"{node.operator}{self.e(node.argument, UNARY)}"
        return f"{self.e(node.argument, POSTFIX + 1)}{node.operator}"

    def member(self, node: S.MemberExpression) -> str:
        target = self.e(node.object, MEMBER)
        if isinstance(node.object, S.Literal) and node.object.raw.strip("0123456789_") == "":
            target = f"({target})"  # `1.toString()` would be a number
        if node.computed:
            return f"{target}{'?.' if node.optional else ''}[{self.e(node.property, SEQUENCE)}]"
        return f"{target}{'?.' if node.optional else '.'}{self.text(node.property)}"

    def call(self, node: S.CallExpression) -> str:
        callee = self.e(node.callee, MEMBER)
        arguments = "" if node.typeArguments is None else self.text(node.typeArguments)
        return f"{callee}{'?.' if node.optional else ''}{arguments}({self.arguments(node.arguments)})"

    def arguments(self, arguments: list[Any]) -> str:
        return ", ".join(self.e(a, ASSIGN) for a in arguments)

    def new(self, node: S.NewExpression) -> str:
        callee = self.e(node.callee, NEW)
        if self.calls(node.callee):
            callee = f"({callee})"  # `new f()()` would call `f`'s instance
        arguments = "" if node.typeArguments is None else self.text(node.typeArguments)
        return f"new {callee}{arguments}({self.arguments(node.arguments)})"

    def calls(self, node: Any) -> bool:
        """Whether `node`, as a `new` callee, holds a call, a `new` or a non-null assertion outside parentheses,
        which would end the callee: tree-sitter-typescript reads `new a!.b()` as `(new a)!.b()`."""
        while isinstance(node, S.MemberExpression):
            node = node.object
        return isinstance(node, (S.CallExpression, S.ChainExpression, S.ImportExpression, S.TSNonNullExpression,
                                 S.NewExpression))

    def arrow(self, node: S.ArrowFunctionExpression) -> str:
        head = ("async " if node.isAsync else "") + self.signature(node)
        parameters = node.typeParameters
        if self.jsx and parameters is not None and len(parameters.params) == 1 and (
                parameters.params[0].constraint is None):
            written = self.text(parameters)
            head = head.replace(written, written[:-1] + ",>", 1)  # `<T>(` would open an element
        if isinstance(node.body, S.BlockStatement):
            return head + " => " + self.inline_block(node.body)
        body = self.e(node.body, ASSIGN)
        if isinstance(_leftmost(node.body), (S.ObjectExpression, S.ObjectPattern)):
            body = f"({body})"
        return f"{head} => {body}"

    def inline_block(self, node: S.BlockStatement) -> str:
        """A block within an expression: its lines joined, its body one level in from the statement's."""
        return "\n".join(self.braced("", node.body, self.level)).lstrip()

    def function_expression(self, node: S.FunctionExpression) -> str:
        return self.function_head(node) + " " + self.inline_block(node.body)

    def class_expression(self, node: S.ClassExpression) -> str:
        decorators = "".join(self.text(d) + " " for d in node.decorators)
        return decorators + "\n".join(self.braced(self.class_head(node), node.body.body, self.level)).lstrip()

    def template(self, node: S.TemplateLiteral) -> str:
        parts = [node.quasis[0].raw]
        for expression, quasi in zip(node.expressions, node.quasis[1:]):
            parts.append("${" + self.e(expression, SEQUENCE) + "}" + quasi.raw)
        return "`" + "".join(parts) + "`"

    def object_expression(self, node: S.ObjectExpression) -> str:
        if not node.properties:
            return "{}"
        return "{ " + ", ".join(self.text(p) for p in node.properties) + " }"

    def property(self, node: S.Property) -> str:
        key = self.key(node.key, node.computed)
        value = node.value
        if node.shorthand:
            if isinstance(value, S.AssignmentPattern):
                return f"{self.text(value.left)} = {self.e(value.right, ASSIGN)}"
            return key
        if node.propertyKind in ("get", "set") or node.method:
            prefix = (node.propertyKind + " ") if node.propertyKind in ("get", "set") else ""
            prefix += ("async " if value.isAsync else "") + ("*" if value.generator else "")
            if isinstance(value, S.TSEmptyBodyFunctionExpression):
                return f"{prefix}{key}{self.signature(value)}"
            return f"{prefix}{key}{'?' if node.optional else ''}{self.signature(value)} {self.inline_block(value.body)}"
        return f"{key}: {self.e(value, ASSIGN)}"

    def array(self, node: Any) -> str:
        elements = [self.element(e) for e in node.elements]
        if node.elements and isinstance(node.elements[-1], S.Elision):
            elements.append("")  # `[a, ,]` keeps its last hole
        return "[" + ",".join((" " if i > 0 and e else "") + e for i, e in enumerate(elements)) + "]"

    def element(self, node: Any) -> str:
        if isinstance(node, S.Elision):
            return ""
        return self.e(node, ASSIGN)

    def jsx(self, node: Any) -> str:
        if isinstance(node, S.JSXFragment):
            return "<>" + "".join(self.text(c) for c in node.children) + "</>"
        opening = node.openingElement
        name = self.text(opening.name)
        arguments = "" if opening.typeArguments is None else self.text(opening.typeArguments)
        attributes = "".join(" " + self.text(a) for a in opening.attributes)
        if opening.selfClosing:
            return f"<{name}{arguments}{attributes} />"
        children = "".join(self.text(c) for c in node.children)
        return f"<{name}{arguments}{attributes}>{children}</{self.text(node.closingElement.name)}>"

    def jsx_attribute(self, node: S.JSXAttribute) -> str:
        return self.text(node.name) + ("" if node.value is None else "=" + self.text(node.value))

    # Patterns and parameters

    def binding_name(self, node: S.Identifier) -> str:
        return node.name + ("?" if node.optional else "")

    def identifier(self, node: S.Identifier) -> str:
        decorators = "".join(self.text(d) + " " for d in node.decorators)
        text = decorators + self.binding_name(node)
        return text + ("" if node.typeAnnotation is None else self.annotation(node.typeAnnotation))

    def pattern(self, node: Any, inner: str) -> str:
        decorators = "".join(self.text(d) + " " for d in node.decorators)
        text = decorators + inner + ("?" if node.optional else "")
        return text + ("" if node.typeAnnotation is None else self.annotation(node.typeAnnotation))

    def object_pattern(self, node: S.ObjectPattern) -> str:
        inner = "{}" if not node.properties else "{ " + ", ".join(self.text(p) for p in node.properties) + " }"
        return self.pattern(node, inner)

    def assignment_pattern(self, node: S.AssignmentPattern) -> str:
        return self.pattern(node, f"{self.text(node.left)} = {self.e(node.right, ASSIGN)}")

    def rest(self, node: S.RestElement) -> str:
        return self.pattern(node, f"...{self.text(node.argument)}")

    def parameter_property(self, node: S.TSParameterProperty) -> str:
        decorators = "".join(self.text(d) + " " for d in node.decorators)
        return decorators + self.member_modifiers(node) + self.text(node.parameter)

    # Types

    def annotation(self, node: S.TSTypeAnnotation) -> str:
        return ": " + self.t(node.typeAnnotation, T_FUNCTION)

    def t(self, node: Any, needed: int) -> str:
        """A type's text, parenthesized if it binds less than its place needs."""
        text = self.text(node)
        return f"({text})" if _TYPE_PRECEDENCE.get(type(node), T_PRIMARY) < needed else text

    def union(self, node: Any) -> str:
        operator, level = (" | ", T_INTERSECTION) if isinstance(node, S.TSUnionType) else (" & ", T_OPERATOR)
        return operator.join(self.t(t, level) for t in node.types)

    def type_operator(self, node: S.TSTypeOperator) -> str:
        if node.typeAnnotation is None:
            return node.operator
        return f"{node.operator} {self.t(node.typeAnnotation, T_OPERATOR)}"

    def conditional_type(self, node: S.TSConditionalType) -> str:
        extends = node.extendsType  # a function type needs no parentheses, unless it returns a conditional type
        if isinstance(extends, S.TSConditionalType) or (
                isinstance(extends, (S.TSFunctionType, S.TSConstructorType)) and extends.returnType is not None
                and isinstance(extends.returnType.typeAnnotation, S.TSConditionalType)):
            extended = f"({self.text(extends)})"
        else:
            extended = self.t(extends, T_FUNCTION)
        return (f"{self.t(node.checkType, T_UNION)} extends {extended} ? "
                f"{self.t(node.trueType, T_FUNCTION)} : {self.t(node.falseType, T_FUNCTION)}")

    def mapped(self, node: S.TSMappedType) -> str:
        readonly = "" if node.readonly is None else node.readonly + " "
        name = "" if node.nameType is None else f" as {self.t(node.nameType, T_FUNCTION)}"
        optional = node.optional or ""
        value = "" if node.typeAnnotation is None else f": {self.t(node.typeAnnotation, T_FUNCTION)}"
        constraint = self.t(node.constraint, T_FUNCTION)
        return f"{{ {readonly}[{self.text(node.key)} in {constraint}{name}]{optional}{value} }}"

    def type_parameter(self, node: S.TSTypeParameter) -> str:
        text = ("const " if node.const else "") + ("in " if node.isIn else "") + ("out " if node.isOut else "")
        text += self.text(node.name)
        if node.constraint is not None:
            text += f" extends {self.t(node.constraint, T_FUNCTION)}"
        if node.default is not None:
            text += f" = {self.t(node.default, T_FUNCTION)}"
        return text

    def predicate(self, node: S.TSTypePredicate) -> str:
        text = ("asserts " if node.asserts else "") + self.text(node.parameterName)
        if node.typeAnnotation is not None:
            text += f" is {self.t(node.typeAnnotation.typeAnnotation, T_FUNCTION)}"
        return text

    def type_literal(self, node: S.TSTypeLiteral) -> str:
        """`{ a: A; b(): B }` on one line, or with comments its members' lines, one level in from the statement's."""
        if any(isinstance(m, S.Comment) for m in node.members):
            return "\n".join(self.braced("", node.members, self.level)).lstrip()
        if not node.members:
            return "{}"
        return "{ " + " ".join(self.simple(m) for m in node.members) + " }"

    def index_signature(self, node: S.TSIndexSignature) -> str:
        modifiers = "".join(w + " " for w in (
            [node.accessibility] if node.accessibility else []) + (["static"] if node.static else []) + (
            ["readonly"] if node.readonly else []))
        parameters = ", ".join(self.text(p) for p in node.parameters)
        annotation = "" if node.typeAnnotation is None else self.annotation(node.typeAnnotation)
        return f"{modifiers}[{parameters}]{annotation}"

    def property_signature(self, node: S.TSPropertySignature) -> str:
        text = ("readonly " if node.readonly else "") + self.key(node.key, node.computed) + (
            "?" if node.optional else "")
        return text + ("" if node.typeAnnotation is None else self.annotation(node.typeAnnotation))

    def method_signature(self, node: S.TSMethodSignature) -> str:
        prefix = (node.methodKind + " ") if node.methodKind in ("get", "set") else ""
        return f"{prefix}{self.key(node.key, node.computed)}{'?' if node.optional else ''}{self.signature(node)}"

    def import_type(self, node: S.TSImportType) -> str:
        options = "" if node.options is None else ", " + self.text(node.options)
        text = f"import({self.text(node.source)}{options})"
        if node.qualifier is not None:
            text += "." + self.text(node.qualifier)
        return text + ("" if node.typeArguments is None else self.text(node.typeArguments))

    def heritage(self, node: Any) -> str:
        return self.e(node.expression, MEMBER) + ("" if node.typeArguments is None else self.text(
            node.typeArguments))

    TEXTS: dict[type, Callable[[Printer, Any], str]] = {
        S.Comment: lambda self, node: self.comment(node),
        S.Identifier: identifier, S.PrivateIdentifier: lambda self, node: "#" + node.name,
        S.Literal: lambda self, node: node.raw, S.TemplateElement: lambda self, node: node.raw,
        S.TemplateLiteral: template,
        S.TaggedTemplateExpression: lambda self, node: self.e(node.tag, MEMBER) + (
            "" if node.typeArguments is None else self.text(node.typeArguments)) + self.text(node.quasi),
        S.ThisExpression: lambda self, node: "this", S.Super: lambda self, node: "super",
        S.ParenthesizedExpression: lambda self, node: f"({self.e(node.expression, SEQUENCE)})",
        S.Elision: lambda self, node: "", S.SpreadElement: lambda self, node: f"...{self.e(node.argument, ASSIGN)}",
        S.ArrayExpression: array, S.Property: property, S.ObjectExpression: object_expression,
        S.FunctionExpression: function_expression, S.ArrowFunctionExpression: arrow,
        S.ClassExpression: class_expression,
        S.MetaProperty: lambda self, node: f"{self.text(node.meta)}.{self.text(node.property)}",
        S.MemberExpression: member, S.CallExpression: call, S.ChainExpression: lambda self, node: self.text(
            node.expression),
        S.NewExpression: new,
        S.ImportExpression: lambda self, node: "import" + (".defer" if node.phase == "defer" else "") + "(" + ", ".join(
            self.e(a, ASSIGN) for a in [node.source] + ([] if node.options is None else [node.options])) + ")",
        S.UpdateExpression: update, S.UnaryExpression: unary,
        S.AwaitExpression: lambda self, node: f"await {self.e(node.argument, UNARY)}",
        S.BinaryExpression: binary, S.LogicalExpression: binary, S.ConditionalExpression: conditional,
        S.AssignmentExpression: assignment,
        S.SequenceExpression: lambda self, node: ", ".join(self.e(e, ASSIGN) for e in node.expressions),
        S.YieldExpression: lambda self, node: ("yield*" if node.delegate else "yield") + (
            "" if node.argument is None else " " + self.e(node.argument, ASSIGN)),
        S.TSAsExpression: lambda self, node: (f"{self.e(node.expression, RELATIONAL)} as "
                                              f"{self.t(node.typeAnnotation, 0)}"),
        S.TSSatisfiesExpression: lambda self, node: (f"{self.e(node.expression, RELATIONAL)} satisfies "
                                                     f"{self.t(node.typeAnnotation, 0)}"),
        S.TSTypeAssertion: lambda self, node: f"<{self.t(node.typeAnnotation, 0)}>{self.e(node.expression, UNARY)}",
        S.TSNonNullExpression: lambda self, node: f"{self.e(node.expression, MEMBER)}!",
        S.TSInstantiationExpression: lambda self, node: self.e(node.expression, MEMBER) + self.text(
            node.typeArguments),
        S.ArrayPattern: lambda self, node: self.pattern(node, self.array(node)),
        S.ObjectPattern: object_pattern, S.AssignmentPattern: assignment_pattern, S.RestElement: rest,
        S.Decorator: lambda self, node: "@" + self.e(node.expression, MEMBER),
        S.TSParameterProperty: parameter_property,
        S.ImportAttribute: lambda self, node: f"{self.text(node.key)}: {self.text(node.value)}",
        S.ImportSpecifier: lambda self, node: ("type " if node.importKind == "type" else "") + (
            self.text(node.imported) if self.text(node.imported) == self.text(node.local) else
            f"{self.text(node.imported)} as {self.text(node.local)}"),
        S.ImportDefaultSpecifier: lambda self, node: self.text(node.local),
        S.ImportNamespaceSpecifier: lambda self, node: f"* as {self.text(node.local)}",
        S.ExportSpecifier: lambda self, node: ("type " if node.exportKind == "type" else "") + (
            self.text(node.local) if self.text(node.local) == self.text(node.exported) else
            f"{self.text(node.local)} as {self.text(node.exported)}"),
        S.TSExternalModuleReference: lambda self, node: f"require({self.text(node.expression)})",
        S.TSTypeAnnotation: lambda self, node: self.t(node.typeAnnotation, T_FUNCTION),
        S.TSTypeParameter: type_parameter,
        S.TSTypeParameterDeclaration: lambda self, node: "<" + ", ".join(self.text(p) for p in node.params) + ">",
        S.TSTypeParameterInstantiation: lambda self, node: "<" + ", ".join(
            self.t(p, T_FUNCTION) for p in node.params) + ">",
        S.TSInterfaceHeritage: heritage, S.TSClassImplements: heritage,
        S.TSEnumMember: lambda self, node: self.key(node.id, node.computed) + (
            "" if node.initializer is None else f" = {self.e(node.initializer, ASSIGN)}"),
        S.TSPropertySignature: property_signature, S.TSMethodSignature: method_signature,
        S.TSCallSignatureDeclaration: lambda self, node: self.signature(node),
        S.TSConstructSignatureDeclaration: lambda self, node: "new " + self.signature(node),
        S.TSIndexSignature: index_signature,
        S.TSAnyKeyword: lambda self, node: "any", S.TSUnknownKeyword: lambda self, node: "unknown",
        S.TSNumberKeyword: lambda self, node: "number", S.TSBigIntKeyword: lambda self, node: "bigint",
        S.TSBooleanKeyword: lambda self, node: "boolean", S.TSStringKeyword: lambda self, node: "string",
        S.TSSymbolKeyword: lambda self, node: "symbol", S.TSObjectKeyword: lambda self, node: "object",
        S.TSNeverKeyword: lambda self, node: "never", S.TSVoidKeyword: lambda self, node: "void",
        S.TSUndefinedKeyword: lambda self, node: "undefined", S.TSNullKeyword: lambda self, node: "null",
        S.TSIntrinsicKeyword: lambda self, node: "intrinsic", S.TSThisType: lambda self, node: "this",
        S.TSQualifiedName: lambda self, node: f"{self.text(node.left)}.{self.text(node.right)}",
        S.TSTypeReference: lambda self, node: self.text(node.typeName) + (
            "" if node.typeArguments is None else self.text(node.typeArguments)),
        S.TSParenthesizedType: lambda self, node: f"({self.t(node.typeAnnotation, T_FUNCTION)})",
        S.TSLiteralType: lambda self, node: self.text(node.literal),
        S.TSTemplateLiteralType: lambda self, node: "`" + node.quasis[0].raw + "".join(
            "${" + self.t(t, T_FUNCTION) + "}" + q.raw for t, q in zip(node.types, node.quasis[1:])) + "`",
        S.TSArrayType: lambda self, node: self.t(node.elementType, T_POSTFIX) + "[]",
        S.TSTupleType: lambda self, node: "[" + ", ".join(self.t(t, T_FUNCTION) for t in node.elementTypes) + "]",
        S.TSNamedTupleMember: lambda self, node: (f"{self.text(node.label)}{'?' if node.optional else ''}: "
                                                  f"{self.t(node.elementType, T_FUNCTION)}"),
        S.TSOptionalType: lambda self, node: self.t(node.typeAnnotation, T_POSTFIX) + "?",
        S.TSRestType: lambda self, node: "..." + self.t(node.typeAnnotation, T_FUNCTION),
        S.TSUnionType: union, S.TSIntersectionType: union,
        S.TSFunctionType: lambda self, node: self.signature(node, arrow=True),
        S.TSConstructorType: lambda self, node: ("abstract " if node.abstract else "") + "new " + self.signature(
            node, arrow=True),
        S.TSTypeLiteral: type_literal, S.TSMappedType: mapped,
        S.TSIndexedAccessType: lambda self, node: (f"{self.t(node.objectType, T_POSTFIX)}"
                                                   f"[{self.t(node.indexType, T_FUNCTION)}]"),
        S.TSTypeOperator: type_operator,
        S.TSTypeQuery: lambda self, node: "typeof " + self.text(node.exprName) + (
            "" if node.typeArguments is None else self.text(node.typeArguments)),
        S.TSImportType: import_type, S.TSConditionalType: conditional_type,
        S.TSInferType: lambda self, node: "infer " + self.type_parameter(node.typeParameter),
        S.TSTypePredicate: predicate,
        S.JSXIdentifier: lambda self, node: node.name,
        S.JSXNamespacedName: lambda self, node: f"{self.text(node.namespace)}:{self.text(node.name)}",
        S.JSXMemberExpression: lambda self, node: f"{self.text(node.object)}.{self.text(node.property)}",
        S.JSXEmptyExpression: lambda self, node: "",
        S.JSXExpressionContainer: lambda self, node: "{" + self.text(node.expression) + "}",
        S.JSXSpreadChild: lambda self, node: "{..." + self.text(node.expression) + "}",
        S.JSXText: lambda self, node: node.raw, S.JSXAttribute: jsx_attribute,
        S.JSXSpreadAttribute: lambda self, node: "{..." + self.e(node.argument, ASSIGN) + "}",
        S.JSXElement: jsx, S.JSXFragment: jsx,
    }
