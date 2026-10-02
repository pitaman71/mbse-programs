"""Prints Ccpp trees as C and C++ source text, in one fixed layout.

The layout: four spaces per level, braces on the line that opens them, one declaration or statement per line, and
labels, access specifiers and directives outdented. Parentheses written in the tree are printed; those a tree built by
hand needs are added, by precedence for expressions and by binding for declarators (`(*f)(int)`). The printer
assumes a valid tree: standards validate before they print.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import Syntax as S

__all__ = ["Printer"]

_INDENT = "    "

# Precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its place needs.
COMMA, ASSIGNMENT, CONDITIONAL, PRIMARY, POSTFIX, UNARY = 0, 1, 2, 17, 16, 15
_BINARY = {",": COMMA, "||": 3, "&&": 4, "|": 5, "^": 6, "&": 7, "==": 8, "!=": 8, "<": 9, ">": 9, "<=": 9, ">=": 9,
           "<=>": 10, "<<": 11, ">>": 11, "+": 12, "-": 12, "*": 13, "/": 13, "%": 13, ".*": 14, "->*": 14}


def _precedence(node: Any) -> int:
    if isinstance(node, S.BinaryExpression):
        return _BINARY[node.operator]
    if isinstance(node, (S.AssignmentExpression, S.ThrowExpression, S.YieldExpression)):
        return ASSIGNMENT
    if isinstance(node, S.ConditionalExpression):
        return CONDITIONAL
    if isinstance(node, (S.UnaryExpression, S.CastExpression, S.SizeofExpression, S.AlignofExpression,
                         S.NewExpression, S.DeleteExpression, S.AwaitExpression, S.NoexceptExpression,
                         S.ExtensionExpression, S.ReflectExpression, S.SizeofPackExpression)):
        return UNARY
    if isinstance(node, (S.CallExpression, S.SubscriptExpression, S.MemberExpression, S.PostfixExpression,
                         S.NamedCastExpression, S.TypeidExpression, S.FunctionalCastExpression,
                         S.CompoundLiteralExpression, S.PackExpansion)):
        return POSTFIX
    return PRIMARY


def _abstract(declarator: Any) -> bool:
    """Whether a declarator declares no name."""
    while declarator is not None:
        if isinstance(declarator, (S.IdDeclarator, S.StructuredBindingDeclarator)):
            return False
        declarator = declarator.declarator
    return True


class Printer:
    """Prints any Ccpp syntax node: a translation unit as a file, anything else as the text it stands for."""

    def print(self, node: Any) -> str:
        if isinstance(node, S.TranslationUnit):
            return "".join(line + "\n" for line in self.lines(node.items, lambda i: self.item(i, 0)))
        if isinstance(node, (S.Statement, S.Declaration, S.Directive, S.Comment)):
            return self.item(node, 0)
        return self.text(node, 0)

    # Items: declarations, statements, directives and comments, each starting with its own indentation

    def item(self, node: Any, depth: int, enumerators: bool = False) -> str:
        """An item, starting with its indentation. Among `enumerators`, an enumerator ends with a comma."""
        if isinstance(node, S.Directive):
            return self.directive(node, depth, enumerators)
        if isinstance(node, S.Enumerator):
            return _INDENT * depth + self.enumerator(node, depth) + ("," if enumerators else "")
        if isinstance(node, S.Comment):
            return _INDENT * depth + self.comment(node)
        if isinstance(node, S.AccessSpecifier):
            return _INDENT * max(depth - 1, 0) + f"{node.access}:"
        if isinstance(node, (S.CaseStatement, S.DefaultStatement, S.LabeledStatement)):
            return _INDENT * max(depth - 1, 0) + self.label(node, depth)
        return _INDENT * depth + self.statement(node, depth)

    def lines(self, nodes: list[Any], render: Callable[[Any], str]) -> list[str]:
        """Each syntax node rendered on its own lines, but for trailing comments, which end the line before them."""
        out: list[str] = []
        for node in nodes:
            if isinstance(node, S.Comment) and node.trailing and out:
                out[-1] += " " + self.comment(node)
            else:
                out.append(render(node))
        return out

    def items(self, nodes: list[Any], depth: int) -> str:
        """Items, one per line; those after a case or default label until the next one are indented further."""
        labelled = False

        def render(node: Any) -> str:
            nonlocal labelled
            if isinstance(node, (S.CaseStatement, S.DefaultStatement)):
                labelled = True
                return self.item(node, depth + 1)
            return self.item(node, depth + 1 if labelled else depth)

        return "\n".join(self.lines(nodes, render))

    def block(self, nodes: list[Any], depth: int) -> str:
        if not nodes:
            return "{}"
        return "{\n" + self.items(nodes, depth + 1) + "\n" + _INDENT * depth + "}"

    def comment(self, node: S.Comment) -> str:
        return f"/*{node.text}*/" if node.block else f"//{node.text}"

    def label(self, node: Any, depth: int) -> str:
        if isinstance(node, S.CaseStatement):
            head = f"case {self.expression(node.value, CONDITIONAL, depth)}"
            if node.last is not None:
                head += f" ... {self.expression(node.last, CONDITIONAL, depth)}"
        elif isinstance(node, S.DefaultStatement):
            head = "default"
        else:
            head = node.label.spelling
        statement = node.statement
        if statement is None:
            return head + ":"
        if isinstance(statement, (S.CaseStatement, S.DefaultStatement)):
            return head + ":\n" + self.item(statement, depth)
        if isinstance(statement, S.CompoundStatement):
            return head + ": " + self.block(statement.items, depth - 1)
        return head + ":\n" + _INDENT * depth + self.statement(statement, depth)

    # Directives

    def directive(self, node: Any, depth: int, enumerators: bool = False) -> str:
        if isinstance(node, S.IncludeDirective):
            if node.macro is not None:
                target = self.expression(node.macro, COMMA, depth)
            else:
                target = f"<{node.path}>" if node.system else f'"{node.path}"'
            return f"#{node.directive} {target}"
        if isinstance(node, S.DefineDirective):
            head = f"#define {node.name.spelling}"
            if node.function_like:
                names = [p.spelling for p in node.parameters] + (["..."] if node.variadic else [])
                head += "(" + ", ".join(names) + ")"
            return head + (f" {node.replacement}" if node.replacement is not None else "")
        if isinstance(node, S.OtherDirective):
            return "#" + (node.directive or "") + (f" {node.text}" if node.text is not None else "")
        return self.conditional(node, depth, enumerators) + "\n#endif"

    def conditional(self, node: Any, depth: int, enumerators: bool) -> str:
        if isinstance(node, (S.IfDirective, S.ElifDirective)):
            keyword = "if" if isinstance(node, S.IfDirective) else "elif"
            head = f"#{keyword} {self.expression(node.condition, COMMA, depth)}"
        elif isinstance(node, (S.IfdefDirective, S.ElifdefDirective)):
            keyword = "if" if isinstance(node, S.IfdefDirective) else "elif"
            head = f"#{keyword}{'ndef' if node.negated else 'def'} {node.name.spelling}"
        else:
            head = "#else"
        body = "".join("\n" + line for line in self.lines(node.items, lambda i: self.item(i, depth, enumerators)))
        tail = "" if isinstance(node, S.ElseDirective) or node.alternative is None else \
            "\n" + self.conditional(node.alternative, depth, enumerators)
        return head + body + tail

    # Statements and declarations, without their first line's indentation

    def statement(self, node: Any, depth: int, semicolon: bool = True) -> str:
        """A statement or declaration; with `semicolon` False, a declaration without its `;`."""
        return self.STATEMENTS[type(node)](self, node, depth, semicolon)

    def sub(self, node: Any, depth: int) -> str:
        """A substatement: a block on the same line, anything else indented on the next."""
        if isinstance(node, S.CompoundStatement):
            return " " + self.block(node.items, depth)
        return "\n" + self.item(node, depth + 1)

    def after(self, node: Any, depth: int) -> str:
        """What separates a substatement from a following keyword (`else`, `while`)."""
        return " " if isinstance(node, S.CompoundStatement) else "\n" + _INDENT * depth

    def expression_statement(self, node: S.ExpressionStatement, depth: int, semicolon: bool) -> str:
        return (self.expression(node.expression, COMMA, depth) if node.expression is not None else "") + ";"

    def compound(self, node: S.CompoundStatement, depth: int, semicolon: bool) -> str:
        return self.block(node.items, depth)

    def head(self, initializer: Any, condition: Any, depth: int) -> str:
        """`(initializer condition)` of an if, switch or while."""
        text = self.statement(initializer, depth) + " " if initializer is not None else ""
        return f"({text}{self.condition(condition, depth)})"

    def condition(self, node: Any, depth: int) -> str:
        if isinstance(node, S.Declaration):
            return self.statement(node, depth, False)
        return self.expression(node, COMMA, depth)

    def if_(self, node: S.IfStatement, depth: int, semicolon: bool) -> str:
        if node.consteval:
            text = "if " + ("!" if node.negated else "") + "consteval"
        else:
            text = "if " + ("constexpr " if node.constexpr else "") + self.head(node.initializer, node.condition, depth)
        text += self.sub(node.consequence, depth)
        if node.alternative is not None:
            text += self.after(node.consequence, depth) + "else"
            if isinstance(node.alternative, S.IfStatement):
                text += " " + self.statement(node.alternative, depth)
            else:
                text += self.sub(node.alternative, depth)
        return text

    def switch(self, node: S.SwitchStatement, depth: int, semicolon: bool) -> str:
        return "switch " + self.head(node.initializer, node.condition, depth) + self.sub(node.body, depth)

    def while_(self, node: S.WhileStatement, depth: int, semicolon: bool) -> str:
        return "while " + self.head(None, node.condition, depth) + self.sub(node.body, depth)

    def do(self, node: S.DoStatement, depth: int, semicolon: bool) -> str:
        return ("do" + self.sub(node.body, depth) + self.after(node.body, depth)
                + f"while ({self.expression(node.condition, COMMA, depth)});")

    def for_(self, node: S.ForStatement, depth: int, semicolon: bool) -> str:
        text = "for (" + (self.statement(node.initializer, depth) if node.initializer is not None else ";")
        if node.condition is not None:
            text += " " + self.condition(node.condition, depth)
        text += ";"
        if node.increment is not None:
            text += " " + self.expression(node.increment, COMMA, depth)
        return text + ")" + self.sub(node.body, depth)

    def range_for(self, node: S.RangeForStatement, depth: int, semicolon: bool) -> str:
        text = ("template " if node.template_keyword else "") + "for ("
        if node.initializer is not None:
            text += self.statement(node.initializer, depth) + " "
        text += self.statement(node.declaration, depth, False) + " : " + self.expression(node.range, COMMA, depth)
        return text + ")" + self.sub(node.body, depth)

    def jump(self, node: Any, depth: int, semicolon: bool) -> str:
        if isinstance(node, S.BreakStatement):
            return "break;"
        if isinstance(node, S.ContinueStatement):
            return "continue;"
        if isinstance(node, S.GotoStatement):
            return f"goto {node.label.spelling};"
        keyword = "return" if isinstance(node, S.ReturnStatement) else "co_return"
        return keyword + (" " + self.expression(node.value, COMMA, depth) if node.value is not None else "") + ";"

    def try_(self, node: S.TryStatement, depth: int, semicolon: bool) -> str:
        return "try " + self.block(node.body.items, depth) + self.handlers(node, depth)

    def handlers(self, node: S.TryStatement, depth: int) -> str:
        return "".join(f" catch ({self.text(h.parameter, depth)}) {self.block(h.body.items, depth)}"
                       for h in node.handlers)

    def attributed(self, node: S.AttributedStatement, depth: int, semicolon: bool) -> str:
        statement = self.statement(node.statement, depth)
        return self.attributes(node.attributes, depth) + ("" if statement == ";" else " ") + statement

    def contract_assert(self, node: S.ContractAssertStatement, depth: int, semicolon: bool) -> str:
        return ("contract_assert" + self.attributes_after(node.attributes, depth)
                + f"({self.expression(node.predicate, COMMA, depth)});")

    def labeled(self, node: Any, depth: int, semicolon: bool) -> str:
        return self.label(node, depth)

    # Declarations

    def prefix(self, attributes: list[Any], depth: int) -> str:
        return self.attributes(attributes, depth) + " " if attributes else ""

    def specifiers(self, specifiers: list[Any], depth: int) -> str:
        return " ".join(self.text(s, depth) for s in specifiers)

    def declared(self, specifiers: str, declarator: str, abstract: bool) -> str:
        """Specifiers and a declarator: separated by a space, unless the declarator is abstract and starts with a
        pointer, reference, bracket or parenthesis."""
        if not specifiers or not declarator:
            return specifiers + declarator
        if declarator.startswith("..."):
            return specifiers + "..." + (" " + declarator[3:] if len(declarator) > 3 else "")
        if abstract and declarator[0] in "*&[(":
            return specifiers + declarator
        return f"{specifiers} {declarator}"

    def simple(self, node: S.SimpleDeclaration, depth: int, semicolon: bool) -> str:
        declarators = ", ".join(self.init_declarator(d, depth) for d in node.declarators)
        text = self.prefix(node.attributes, depth) + self.declared(self.specifiers(node.specifiers, depth),
                                                                   declarators, False)
        return text + (";" if semicolon else "")

    def init_declarator(self, node: S.InitDeclarator, depth: int) -> str:
        text = self.declarator(node.declarator, depth) if node.declarator is not None else ""
        text += "".join(f" {v.keyword}" for v in node.virt_specifiers)
        if node.pure:
            text += " = 0"
        if node.bitfield is not None:
            text += (" : " if text else ": ") + self.expression(node.bitfield, CONDITIONAL, depth)
        if node.initializer is not None:
            text += self.initializer(node.initializer, depth)
        if node.requires is not None:
            text += " requires " + self.constraint(node.requires, depth)
        return text + self.contracts(node.contracts, depth)

    def initializer(self, node: Any, depth: int) -> str:
        if isinstance(node, S.EqualInitializer):
            return " = " + self.expression(node.value, ASSIGNMENT, depth)
        if isinstance(node, S.ParenthesizedInitializer):
            return "(" + self.list(node.arguments, depth) + ")"
        return self.expression(node, ASSIGNMENT, depth)

    def contracts(self, contracts: list[Any], depth: int) -> str:
        return "".join(" " + self.text(c, depth) for c in contracts)

    def function(self, node: S.FunctionDefinition, depth: int, semicolon: bool) -> str:
        text = self.prefix(node.attributes, depth) + self.declared(
            self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth), False)
        text += "".join(f" {v.keyword}" for v in node.virt_specifiers)
        if node.requires is not None:
            text += " requires " + self.constraint(node.requires, depth)
        text += self.contracts(node.contracts, depth)
        initializers = ""
        if node.initializers:
            initializers = " : " + ", ".join(self.text(i, depth) for i in node.initializers)
        body = node.body
        if isinstance(body, S.TryStatement):
            return text + " try" + initializers + " " + self.block(body.body.items, depth) + self.handlers(body, depth)
        if isinstance(body, S.DefaultedBody):
            return text + initializers + " = default;"
        if isinstance(body, S.DeletedBody):
            reason = f"({self.expression(body.reason, ASSIGNMENT, depth)})" if body.reason is not None else ""
            return text + initializers + f" = delete{reason};"
        return text + initializers + " " + self.block(body.items, depth)

    def template(self, node: S.TemplateDeclaration, depth: int, semicolon: bool) -> str:
        text = "template <" + ", ".join(self.text(p, depth) for p in node.parameters) + ">"
        if node.requires is not None:
            text += " requires " + self.constraint(node.requires, depth)
        return text + "\n" + _INDENT * depth + self.statement(node.declaration, depth)

    def instantiation(self, node: S.ExplicitInstantiation, depth: int, semicolon: bool) -> str:
        return ("extern " if node.extern else "") + "template " + self.statement(node.declaration, depth)

    def namespace(self, node: S.NamespaceDefinition, depth: int, semicolon: bool) -> str:
        text = ("inline " if node.inline else "") + "namespace"
        text += "".join(" " + self.text(a, depth) for a in node.attributes)
        if node.names:
            text += " " + "::".join(("inline " if n.inline else "") + n.name.spelling for n in node.names)
        return text + " " + self.block(node.items, depth)

    def namespace_alias(self, node: S.NamespaceAliasDefinition, depth: int, semicolon: bool) -> str:
        return f"namespace {node.name.spelling} = {self.text(node.target, depth)};"

    def using_directive(self, node: S.UsingDirective, depth: int, semicolon: bool) -> str:
        return self.prefix(node.attributes, depth) + f"using namespace {self.text(node.name, depth)};"

    def using(self, node: S.UsingDeclaration, depth: int, semicolon: bool) -> str:
        return "using " + ", ".join(self.text(d, depth) for d in node.declarators) + ";"

    def using_enum(self, node: S.UsingEnumDeclaration, depth: int, semicolon: bool) -> str:
        return f"using enum {self.text(node.type, depth)};"

    def alias(self, node: S.AliasDeclaration, depth: int, semicolon: bool) -> str:
        return (f"using {node.name.spelling}" + self.attributes_after(node.attributes, depth)
                + f" = {self.text(node.type, depth)};")

    def static_assert(self, node: S.StaticAssertDeclaration, depth: int, semicolon: bool) -> str:
        message = ", " + self.expression(node.message, ASSIGNMENT, depth) if node.message is not None else ""
        return f"{node.keyword}({self.expression(node.condition, ASSIGNMENT, depth)}{message});"

    def attribute_declaration(self, node: S.AttributeDeclaration, depth: int, semicolon: bool) -> str:
        return self.attributes(node.attributes, depth) + ";"

    def empty(self, node: Any, depth: int, semicolon: bool) -> str:
        return ";"

    def linkage(self, node: S.LinkageSpecification, depth: int, semicolon: bool) -> str:
        head = f'extern "{node.language}" '
        if node.braced:
            return head + self.block(node.items, depth)
        return head + self.statement(node.items[0], depth)

    def asm(self, node: S.AsmDeclaration, depth: int, semicolon: bool) -> str:
        text = self.prefix(node.attributes, depth) + node.keyword
        text += "".join(f" {q}" for q in ("volatile", "inline", "goto") if getattr(node, q))
        sections = [", ".join(self.text(o, depth) for o in node.outputs),
                    ", ".join(self.text(o, depth) for o in node.inputs),
                    ", ".join(self.expression(c, ASSIGNMENT, depth) for c in node.clobbers),
                    ", ".join(label.spelling for label in node.labels)]
        while sections and not sections[-1]:
            sections.pop()
        inner = self.expression(node.template, ASSIGNMENT, depth) + "".join(
            " :" + (f" {s}" if s else "") for s in sections)
        return f"{text}({inner});"

    def module(self, node: Any, depth: int, semicolon: bool) -> str:
        if isinstance(node, S.GlobalModuleFragment):
            return "module;"
        if isinstance(node, S.PrivateModuleFragment):
            return "module :private;"
        text = ("export " if node.export else "")
        if isinstance(node, S.ModuleDeclaration):
            text += "module " + node.name + (f":{node.partition}" if node.partition is not None else "")
        elif node.header is not None:
            text += "import " + (f"<{node.header}>" if node.system else f'"{node.header}"')
        else:
            text += "import " + (node.name or "") + (f":{node.partition}" if node.partition is not None else "")
        return text + self.attributes_after(node.attributes, depth) + ";"

    def export(self, node: S.ExportDeclaration, depth: int, semicolon: bool) -> str:
        if node.braced:
            return "export " + self.block(node.items, depth)
        return "export " + self.statement(node.items[0], depth)

    def concept(self, node: S.ConceptDefinition, depth: int, semicolon: bool) -> str:
        return (f"concept {node.name.spelling}" + self.attributes_after(node.attributes, depth)
                + f" = {self.expression(node.constraint, CONDITIONAL, depth)};")

    def friend_types(self, node: S.FriendTypeDeclaration, depth: int, semicolon: bool) -> str:
        return "friend " + ", ".join(self.text(t, depth) for t in node.types) + ";"

    STATEMENTS: dict[type, Callable[..., str]] = {}

    # Expressions

    def expression(self, node: Any, needed: int, depth: int) -> str:
        """`node` where an expression of at least `needed` precedence is needed, parenthesized if it binds less."""
        text = self.text(node, depth)
        return f"({text})" if _precedence(node) < needed else text

    def constraint(self, node: Any, depth: int, needed: int = 3) -> str:
        """A requires-clause: primary expressions joined by `&&` and `||`."""
        if isinstance(node, S.BinaryExpression) and node.operator in ("&&", "||"):
            precedence = _BINARY[node.operator]
            text = (f"{self.constraint(node.left, depth, precedence)} {node.operator} "
                    f"{self.constraint(node.right, depth, precedence + 1)}")
            return f"({text})" if precedence < needed else text
        return self.expression(node, PRIMARY, depth)

    def list(self, nodes: list[Any], depth: int) -> str:
        """Arguments: expressions or types, separated by commas."""
        return ", ".join(self.text(n, depth) if isinstance(n, S.TypeId) else self.expression(n, ASSIGNMENT, depth)
                         for n in nodes)

    def template_arguments(self, nodes: list[Any], depth: int) -> str:
        """Template arguments, parenthesized where a `>` would end the list."""
        out = []
        for n in nodes:
            text = self.text(n, depth) if isinstance(n, S.TypeId) else self.expression(n, CONDITIONAL, depth)
            if _precedence(n) <= _BINARY[">"] and ">" in text and not text.startswith("("):
                text = f"({text})"
            out.append(text)
        return "<" + ", ".join(out) + ">"

    def text(self, node: Any, depth: int) -> str:
        """The text of any syntax node that is neither an item nor a statement: `item` and `statement` print those."""
        return self.TEXTS[type(node)](self, node, depth)

    def unary(self, node: S.UnaryExpression, depth: int) -> str:
        operand = self.expression(node.operand, UNARY, depth)
        space = " " if operand[:1] in ("+", "-", "&", "*") and operand[:1] == node.operator[-1:] else ""
        return node.operator + space + operand

    def binary(self, node: S.BinaryExpression, depth: int) -> str:
        precedence = _BINARY[node.operator]
        left = self.expression(node.left, precedence, depth)
        right = self.expression(node.right, precedence + 1, depth)
        if node.operator in (".*", "->*"):
            return left + node.operator + right
        if node.operator == ",":
            return f"{left}, {right}"
        return f"{left} {node.operator} {right}"

    def assignment(self, node: S.AssignmentExpression, depth: int) -> str:
        return (f"{self.expression(node.left, _BINARY['||'], depth)} {node.operator} "
                f"{self.expression(node.right, ASSIGNMENT, depth)}")

    def conditional_expression(self, node: S.ConditionalExpression, depth: int) -> str:
        condition = self.expression(node.condition, _BINARY["||"], depth)
        alternative = self.expression(node.alternative, ASSIGNMENT, depth)
        if node.consequence is None:
            return f"{condition} ?: {alternative}"
        return f"{condition} ? {self.expression(node.consequence, COMMA, depth)} : {alternative}"

    def call(self, node: S.CallExpression, depth: int) -> str:
        return self.expression(node.function, POSTFIX, depth) + "(" + self.list(node.arguments, depth) + ")"

    def subscript(self, node: S.SubscriptExpression, depth: int) -> str:
        return (self.expression(node.object, POSTFIX, depth) + "["
                + ", ".join(self.expression(i, ASSIGNMENT, depth) for i in node.indices) + "]")

    def member(self, node: S.MemberExpression, depth: int) -> str:
        return (self.expression(node.object, POSTFIX, depth) + node.operator
                + ("template " if node.template_keyword else "") + self.text(node.member, depth))

    def postfix(self, node: S.PostfixExpression, depth: int) -> str:
        return self.expression(node.operand, POSTFIX, depth) + node.operator

    def named_cast(self, node: S.NamedCastExpression, depth: int) -> str:
        return f"{node.operator}<{self.text(node.type, depth)}>({self.expression(node.operand, COMMA, depth)})"

    def functional_cast(self, node: S.FunctionalCastExpression, depth: int) -> str:
        return self.text(node.type, depth) + self.initializer(node.initializer, depth)

    def cast(self, node: S.CastExpression, depth: int) -> str:
        return f"({self.text(node.type, depth)}){self.expression(node.operand, UNARY, depth)}"

    def sizeof(self, node: S.SizeofExpression, depth: int) -> str:
        if isinstance(node.operand, S.TypeId):
            return f"sizeof({self.text(node.operand, depth)})"
        operand = self.expression(node.operand, UNARY, depth)
        return "sizeof" + ("" if operand.startswith("(") else " ") + operand

    def keyword_call(self, keyword: str, operand: Any, depth: int) -> str:
        if isinstance(operand, S.TypeId):
            return f"{keyword}({self.text(operand, depth)})"
        return f"{keyword}({self.expression(operand, COMMA, depth)})"

    def new(self, node: S.NewExpression, depth: int) -> str:
        text = ("::" if node.global_scope else "") + "new "
        if node.placement:
            text += "(" + self.list(node.placement, depth) + ") "
        type_ = self.text(node.type, depth)
        text += f"({type_})" if node.parenthesized_type else type_
        if node.initializer is not None:
            text += self.initializer(node.initializer, depth)
        return text

    def delete(self, node: S.DeleteExpression, depth: int) -> str:
        return (("::" if node.global_scope else "") + "delete" + ("[]" if node.array else "") + " "
                + self.expression(node.operand, UNARY, depth))

    def fold(self, node: S.FoldExpression, depth: int) -> str:
        left = self.expression(node.left, UNARY, depth) + f" {node.operator} " if node.left is not None else ""
        right = f" {node.operator} " + self.expression(node.right, UNARY, depth) if node.right is not None else ""
        return f"({left}...{right})"

    def lambda_(self, node: S.LambdaExpression, depth: int) -> str:
        text = "[" + ", ".join(self.text(c, depth) for c in node.captures) + "]"
        if node.template_parameters:
            text += "<" + ", ".join(self.text(p, depth) for p in node.template_parameters) + ">"
        if node.template_requires is not None:
            text += " requires " + self.constraint(node.template_requires, depth)
        text += self.attributes_after(node.attributes, depth)
        if node.declarator is not None:
            text += (" " if node.template_requires is not None else "") + self.text(node.declarator, depth)
        return text + " " + self.block(node.body.items, depth)

    def lambda_declarator(self, node: S.LambdaDeclarator, depth: int) -> str:
        text = "(" + ", ".join(self.text(p, depth) for p in node.parameters) + ")"
        text += "".join(" " + s.keyword for s in node.specifiers)
        if node.exception is not None:
            text += " " + self.text(node.exception, depth)
        text += self.attributes_after(node.attributes, depth)
        if node.trailing_return is not None:
            text += " -> " + self.text(node.trailing_return, depth)
        if node.requires is not None:
            text += " requires " + self.constraint(node.requires, depth)
        return text + self.contracts(node.contracts, depth)

    def capture(self, node: Any, depth: int) -> str:
        if isinstance(node, S.DefaultCapture):
            return node.mode
        if isinstance(node, S.ThisCapture):
            return "*this" if node.copy else "this"
        reference = "&" if node.by_reference else ""
        if isinstance(node, S.SimpleCapture):
            return reference + node.name.spelling + ("..." if node.pack else "")
        return (reference + ("..." if node.pack else "") + node.name.spelling
                + self.initializer(node.initializer, depth))

    def requires(self, node: S.RequiresExpression, depth: int) -> str:
        text = "requires "
        if node.parameters:
            text += "(" + ", ".join(self.text(p, depth) for p in node.parameters) + ") "
        if not node.requirements:
            return text + "{}"
        return text + "{ " + " ".join(self.text(r, depth) for r in node.requirements) + " }"

    def requirement(self, node: Any, depth: int) -> str:
        if isinstance(node, S.SimpleRequirement):
            return self.expression(node.expression, COMMA, depth) + ";"
        if isinstance(node, S.TypeRequirement):
            return f"typename {self.text(node.name, depth)};"
        if isinstance(node, S.NestedRequirement):
            return f"requires {self.constraint(node.constraint, depth)};"
        text = "{ " + self.expression(node.expression, COMMA, depth) + " }"
        if node.noexcept:
            text += " noexcept"
        if node.return_type is not None:
            text += " -> " + self.text(node.return_type, depth)
        return text + ";"

    def initializer_list(self, node: S.InitializerList, depth: int) -> str:
        items = [self.text(i, depth) if isinstance(i, S.DesignatedInitializer)
                 else self.expression(i, ASSIGNMENT, depth) for i in node.items]
        return "{" + ", ".join(items) + ("," if node.trailing_comma else "") + "}"

    def designated(self, node: S.DesignatedInitializer, depth: int) -> str:
        return "".join(self.text(d, depth) for d in node.designators) + self.initializer(node.initializer, depth)

    def designator(self, node: Any, depth: int) -> str:
        if isinstance(node, S.FieldDesignator):
            return "." + node.name.spelling
        last = f" ... {self.expression(node.last, CONDITIONAL, depth)}" if node.last is not None else ""
        return f"[{self.expression(node.index, CONDITIONAL, depth)}{last}]"

    def generic(self, node: S.GenericSelection, depth: int) -> str:
        controlling = self.text(node.controlling, depth) if isinstance(node.controlling, S.TypeId) else \
            self.expression(node.controlling, ASSIGNMENT, depth)
        associations = [(self.text(a.type, depth) if a.type is not None else "default") + ": "
                        + self.expression(a.value, ASSIGNMENT, depth) for a in node.associations]
        return f"_Generic({', '.join([controlling, *associations])})"

    def literal(self, node: Any, depth: int) -> str:
        if isinstance(node, (S.IntegerLiteral, S.FloatingLiteral)):
            return node.spelling
        if isinstance(node, S.CharacterLiteral):
            return f"{node.prefix or ''}'{node.text}'"
        if isinstance(node, S.StringLiteral):
            return f'{node.prefix or ""}"{node.text}"'
        if isinstance(node, S.RawStringLiteral):
            delimiter = node.delimiter or ""
            return f'{node.prefix or ""}R"{delimiter}({node.text}){delimiter}"'
        if isinstance(node, S.UserDefinedLiteral):
            return self.literal(node.literal, depth) + node.suffix
        if isinstance(node, S.ConcatenatedString):
            return " ".join(self.text(p, depth) for p in node.parts)
        if isinstance(node, S.BooleanLiteral):
            return "true" if node.value else "false"
        return "nullptr"

    # Names

    def name(self, node: Any, depth: int) -> str:
        if isinstance(node, S.Identifier):
            return node.spelling
        if isinstance(node, S.OperatorName):
            return "operator" + (" " if node.operator[0].isalpha() else "") + node.operator
        if isinstance(node, S.ConversionName):
            return "operator " + self.text(node.type, depth)
        if isinstance(node, S.LiteralOperatorName):
            return f'operator""{node.suffix}'
        if isinstance(node, S.DestructorName):
            return "~" + self.text(node.type, depth)
        if isinstance(node, S.TemplateId):
            return (("template " if node.template_keyword else "") + self.text(node.name, depth)
                    + self.template_arguments(node.arguments, depth))
        return (("::" if node.global_scope else "") + "".join(self.text(q, depth) + "::" for q in node.qualifiers)
                + self.text(node.name, depth))

    # Specifiers

    def keyword(self, node: Any, depth: int) -> str:
        return node.keyword

    def specifier(self, node: Any, depth: int) -> str:
        if isinstance(node, S.ExplicitSpecifier):
            return "explicit" + (f"({self.expression(node.condition, COMMA, depth)})"
                                 if node.condition is not None else "")
        if isinstance(node, S.NamedTypeSpecifier):
            return self.text(node.name, depth)
        if isinstance(node, S.TypenameSpecifier):
            return "typename " + self.text(node.name, depth)
        if isinstance(node, S.DecltypeSpecifier):
            return f"decltype({self.expression(node.expression, COMMA, depth)})"
        if isinstance(node, S.PlaceholderTypeSpecifier):
            constraint = self.text(node.constraint, depth) + " " if node.constraint is not None else ""
            return constraint + ("decltype(auto)" if node.decltype else "auto")
        if isinstance(node, S.TypeofSpecifier):
            return self.keyword_call(node.keyword, node.operand, depth)
        if isinstance(node, S.AtomicTypeSpecifier):
            return f"_Atomic({self.text(node.type, depth)})"
        if isinstance(node, S.BitIntSpecifier):
            return f"_BitInt({self.expression(node.width, ASSIGNMENT, depth)})"
        if isinstance(node, S.PackIndexingSpecifier):
            return f"{self.text(node.pack, depth)}...[{self.expression(node.index, CONDITIONAL, depth)}]"
        return self.splice(node, depth)

    def splice(self, node: Any, depth: int) -> str:
        text = ("typename " if getattr(node, "typename_keyword", False) else "")
        text += ("template " if node.template_keyword else "") + f"[: {self.expression(node.reflection, COMMA, depth)} :]"
        if node.arguments or node.template_keyword:
            text += self.template_arguments(node.arguments, depth)
        return text

    def class_(self, node: S.ClassSpecifier, depth: int) -> str:
        text = node.key + self.attributes_after(node.attributes, depth)
        if node.name is not None:
            text += " " + self.text(node.name, depth)
        if node.final:
            text += " final"
        if node.bases:
            text += " : " + ", ".join(self.text(b, depth) for b in node.bases)
        if node.body is not None:
            text += " " + self.members(node.body.items, depth)
        return text

    def members(self, nodes: list[Any], depth: int) -> str:
        """A class body: members one level in, access specifiers at the class's level."""
        if not nodes:
            return "{}"
        return "{\n" + "\n".join(self.lines(nodes, lambda i: self.item(i, depth + 1))) + "\n" + _INDENT * depth + "}"

    def base(self, node: S.BaseSpecifier, depth: int) -> str:
        parts = [self.attributes(node.attributes, depth)] if node.attributes else []
        if node.virtual:
            parts.append("virtual")
        if node.access is not None:
            parts.append(node.access)
        parts.append(self.text(node.type, depth) + ("..." if node.pack else ""))
        return " ".join(parts)

    def enum(self, node: S.EnumSpecifier, depth: int) -> str:
        text = node.key + self.attributes_after(node.attributes, depth)
        if node.name is not None:
            text += " " + self.text(node.name, depth)
        if node.base is not None:
            text += " : " + self.text(node.base, depth)
        if node.body is not None:
            text += " " + self.enumerators(node.body, depth)
        return text

    def enumerators(self, node: S.EnumeratorList, depth: int) -> str:
        if not node.enumerators:
            return "{}"
        last = max((i for i, e in enumerate(node.enumerators) if isinstance(e, S.Enumerator)), default=-1)

        def render(e: Any) -> str:
            text = self.item(e, depth + 1, True)
            return text[:-1] if last >= 0 and e is node.enumerators[last] and not node.trailing_comma else text

        return "{\n" + "\n".join(self.lines(node.enumerators, render)) + "\n" + _INDENT * depth + "}"

    def enumerator(self, node: S.Enumerator, depth: int) -> str:
        text = node.name.spelling + self.attributes_after(node.attributes, depth)
        return text + (f" = {self.expression(node.value, CONDITIONAL, depth)}" if node.value is not None else "")

    # Declarators

    def declarator(self, node: Any, depth: int) -> str:
        if node is None:
            return ""
        if isinstance(node, S.IdDeclarator):
            return self.text(node.name, depth) + self.attributes_after(node.attributes, depth)
        if isinstance(node, S.PackDeclarator):
            return "..." + self.declarator(node.declarator, depth)
        if isinstance(node, (S.PointerDeclarator, S.ReferenceDeclarator)):
            if isinstance(node, S.PointerDeclarator):
                text = self.text(node.scope, depth) + "::*" if node.scope is not None else "*"
                parts = [self.text(a, depth) for a in node.attributes] + [q.keyword for q in node.qualifiers]
            else:
                text = "&&" if node.rvalue else "&"
                parts = [self.text(a, depth) for a in node.attributes]
            inner = self.declarator(node.declarator, depth)
            return text + " ".join(parts) + (" " + inner if parts and inner else inner)
        if isinstance(node, S.ParenthesizedDeclarator):
            return f"({self.declarator(node.declarator, depth)})"
        if isinstance(node, S.StructuredBindingDeclarator):
            return "[" + ", ".join(self.declarator(b, depth) for b in node.bindings) + "]"
        inner = self.declarator(node.declarator, depth)
        if isinstance(node.declarator, (S.PointerDeclarator, S.ReferenceDeclarator)):
            inner = f"({inner})"
        if isinstance(node, S.ArrayDeclarator):
            inside = " ".join(["static"] * node.static + [q.keyword for q in node.qualifiers])
            size = "*" if node.star else self.expression(node.size, ASSIGNMENT, depth) if node.size is not None else ""
            inside = (inside + " " + size if inside and size else inside + size)
            return inner + f"[{inside}]" + self.attributes_after(node.attributes, depth)
        text = inner + "(" + ", ".join(self.text(p, depth) for p in node.parameters) + ")"
        text += "".join(" " + q.keyword for q in node.qualifiers)
        if node.ref_qualifier is not None:
            text += " " + node.ref_qualifier
        if node.exception is not None:
            text += " " + self.text(node.exception, depth)
        text += self.attributes_after(node.attributes, depth)
        if node.trailing_return is not None:
            text += " -> " + self.text(node.trailing_return, depth)
        return text

    def type_id(self, node: S.TypeId, depth: int) -> str:
        return self.declared(self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth), True)

    def parameter(self, node: Any, depth: int) -> str:
        if isinstance(node, S.EllipsisParameter):
            return "..."
        text = self.prefix(node.attributes, depth) + ("this " if node.this_keyword else "")
        text += self.declared(self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth),
                              _abstract(node.declarator))
        return text + (f" = {self.expression(node.default, ASSIGNMENT, depth)}" if node.default is not None else "")

    def template_parameter(self, node: Any, depth: int) -> str:
        if isinstance(node, S.TypeParameter):
            text = self.text(node.constraint, depth) if node.constraint is not None else (node.key or "typename")
        else:
            text = "template <" + ", ".join(self.text(p, depth) for p in node.parameters) + ">"
            if node.requires is not None:
                text += " requires " + self.constraint(node.requires, depth)
            text += " " + node.key
        text += "..." if node.pack else ""
        if node.name is not None:
            text += " " + node.name.spelling
        if node.default is not None:
            text += " = " + self.text(node.default, depth)
        return text

    def exception(self, node: Any, depth: int) -> str:
        if isinstance(node, S.NoexceptSpecifier):
            return "noexcept" + (f"({self.expression(node.condition, COMMA, depth)})"
                                 if node.condition is not None else "")
        return "throw(" + ", ".join(self.text(t, depth) for t in node.types) + ")"

    def contract(self, node: Any, depth: int) -> str:
        if isinstance(node, S.PreconditionSpecifier):
            return ("pre" + self.attributes_after(node.attributes, depth)
                    + f"({self.expression(node.predicate, COMMA, depth)})")
        result = f"{node.result.spelling}: " if node.result is not None else ""
        return ("post" + self.attributes_after(node.attributes, depth)
                + f"({result}{self.expression(node.predicate, COMMA, depth)})")

    # Attributes

    def attributes(self, nodes: list[Any], depth: int) -> str:
        return " ".join(self.text(a, depth) for a in nodes)

    def attributes_after(self, nodes: list[Any], depth: int) -> str:
        return "".join(" " + self.text(a, depth) for a in nodes)

    def attribute_specifier(self, node: Any, depth: int) -> str:
        if isinstance(node, S.StandardAttributeSpecifier):
            using = f"using {node.using_namespace}: " if node.using_namespace is not None else ""
            return "[[" + using + ", ".join(self.text(a, depth) for a in node.attributes) + "]]"
        if isinstance(node, S.AlignasSpecifier):
            operand = self.keyword_call(node.keyword, node.operand, depth)
            return operand[:-1] + "...)" if node.pack else operand
        if isinstance(node, S.GnuAttributeSpecifier):
            return node.keyword + "((" + ", ".join(self.text(a, depth) for a in node.attributes) + "))"
        return "__declspec(" + " ".join(self.text(a, depth) for a in node.attributes) + ")"

    def attribute(self, node: S.Attribute, depth: int) -> str:
        text = (f"{node.namespace}::" if node.namespace is not None else "") + node.name
        if node.arguments:
            text += "(" + self.list(node.arguments, depth) + ")"
        return text + ("..." if node.pack else "")

    def annotation(self, node: S.Annotation, depth: int) -> str:
        return "=" + self.expression(node.value, ASSIGNMENT, depth) + ("..." if node.pack else "")

    # Other parts

    def part(self, node: Any, depth: int) -> str:
        if isinstance(node, S.InitDeclarator):
            return self.init_declarator(node, depth)
        if isinstance(node, S.MemberInitializer):
            return self.text(node.member, depth) + self.initializer(node.initializer, depth) + \
                ("..." if node.pack else "")
        if isinstance(node, S.VirtSpecifier):
            return node.keyword
        if isinstance(node, S.DefaultedBody):
            return "= default;"
        if isinstance(node, S.DeletedBody):
            return "= delete" + (f"({self.expression(node.reason, ASSIGNMENT, depth)})"
                                 if node.reason is not None else "") + ";"
        if isinstance(node, S.MemberList):
            return self.members(node.items, depth)
        if isinstance(node, S.EnumeratorList):
            return self.enumerators(node, depth)
        if isinstance(node, S.Enumerator):
            return self.enumerator(node, depth)
        if isinstance(node, S.NamespaceName):
            return ("inline " if node.inline else "") + node.name.spelling
        if isinstance(node, S.UsingDeclarator):
            return ("typename " if node.typename_keyword else "") + self.text(node.name, depth) + \
                ("..." if node.pack else "")
        if isinstance(node, S.Handler):
            return f"catch ({self.text(node.parameter, depth)}) {self.block(node.body.items, depth)}"
        if isinstance(node, S.AsmOperand):
            name = f"[{node.name.spelling}] " if node.name is not None else ""
            return name + self.expression(node.constraint, ASSIGNMENT, depth) + \
                f" ({self.expression(node.value, COMMA, depth)})"
        if isinstance(node, S.GenericAssociation):
            return (self.text(node.type, depth) if node.type is not None else "default") + ": " + \
                self.expression(node.value, ASSIGNMENT, depth)
        return self.initializer(node, depth).lstrip(" ")  # an initializer, the last part

    TEXTS: dict[type, Callable[..., str]] = {}


Printer.STATEMENTS.update({
    S.ExpressionStatement: Printer.expression_statement, S.CompoundStatement: Printer.compound,
    S.IfStatement: Printer.if_, S.SwitchStatement: Printer.switch, S.WhileStatement: Printer.while_,
    S.DoStatement: Printer.do, S.ForStatement: Printer.for_, S.RangeForStatement: Printer.range_for,
    S.BreakStatement: Printer.jump, S.ContinueStatement: Printer.jump, S.ReturnStatement: Printer.jump,
    S.CoReturnStatement: Printer.jump, S.GotoStatement: Printer.jump, S.TryStatement: Printer.try_,
    S.AttributedStatement: Printer.attributed, S.ContractAssertStatement: Printer.contract_assert,
    S.LabeledStatement: Printer.labeled, S.CaseStatement: Printer.labeled, S.DefaultStatement: Printer.labeled,
    S.SimpleDeclaration: Printer.simple, S.FunctionDefinition: Printer.function,
    S.TemplateDeclaration: Printer.template, S.ExplicitInstantiation: Printer.instantiation,
    S.NamespaceDefinition: Printer.namespace, S.NamespaceAliasDefinition: Printer.namespace_alias,
    S.UsingDirective: Printer.using_directive, S.UsingDeclaration: Printer.using,
    S.UsingEnumDeclaration: Printer.using_enum, S.AliasDeclaration: Printer.alias,
    S.StaticAssertDeclaration: Printer.static_assert, S.AttributeDeclaration: Printer.attribute_declaration,
    S.EmptyDeclaration: Printer.empty, S.LinkageSpecification: Printer.linkage, S.AsmDeclaration: Printer.asm,
    S.ModuleDeclaration: Printer.module, S.GlobalModuleFragment: Printer.module,
    S.PrivateModuleFragment: Printer.module, S.ImportDeclaration: Printer.module,
    S.ExportDeclaration: Printer.export, S.ConceptDefinition: Printer.concept,
    S.FriendTypeDeclaration: Printer.friend_types,
})

Printer.TEXTS.update({
    **{k: Printer.name for k in (S.Identifier, S.OperatorName, S.ConversionName, S.LiteralOperatorName,
                                 S.DestructorName, S.TemplateId, S.QualifiedName)},
    **{k: Printer.literal for k in (S.IntegerLiteral, S.FloatingLiteral, S.CharacterLiteral, S.StringLiteral,
                                    S.RawStringLiteral, S.UserDefinedLiteral, S.ConcatenatedString,
                                    S.BooleanLiteral, S.NullptrLiteral)},
    S.ThisExpression: lambda self, node, depth: "this",
    S.ParenthesizedExpression: lambda self, node, depth: f"({self.expression(node.expression, COMMA, depth)})",
    S.IdExpression: lambda self, node, depth: self.text(node.name, depth),
    S.LambdaExpression: Printer.lambda_, S.LambdaDeclarator: Printer.lambda_declarator,
    **{k: Printer.capture for k in (S.DefaultCapture, S.SimpleCapture, S.ThisCapture, S.InitCapture)},
    S.FoldExpression: Printer.fold, S.RequiresExpression: Printer.requires,
    **{k: Printer.requirement for k in (S.SimpleRequirement, S.TypeRequirement, S.CompoundRequirement,
                                        S.NestedRequirement)},
    S.PackIndexingExpression: lambda self, node, depth: (
        f"{self.text(node.pack, depth)}...[{self.expression(node.index, CONDITIONAL, depth)}]"),
    S.ReflectExpression: lambda self, node, depth: "^^" + (
        "::" if node.operand is None else self.text(node.operand, depth) if not isinstance(node.operand, S.Expression)
        else self.expression(node.operand, UNARY, depth)),
    S.SpliceExpression: Printer.splice,
    S.SubscriptExpression: Printer.subscript, S.CallExpression: Printer.call,
    S.FunctionalCastExpression: Printer.functional_cast, S.MemberExpression: Printer.member,
    S.PostfixExpression: Printer.postfix, S.NamedCastExpression: Printer.named_cast,
    S.TypeidExpression: lambda self, node, depth: self.keyword_call("typeid", node.operand, depth),
    S.UnaryExpression: Printer.unary,
    S.AwaitExpression: lambda self, node, depth: "co_await " + self.expression(node.operand, UNARY, depth),
    S.SizeofExpression: Printer.sizeof,
    S.SizeofPackExpression: lambda self, node, depth: f"sizeof...({node.pack.spelling})",
    S.AlignofExpression: lambda self, node, depth: self.keyword_call(node.keyword, node.operand, depth),
    S.NoexceptExpression: lambda self, node, depth: self.keyword_call("noexcept", node.operand, depth),
    S.NewExpression: Printer.new, S.DeleteExpression: Printer.delete, S.CastExpression: Printer.cast,
    S.BinaryExpression: Printer.binary, S.ConditionalExpression: Printer.conditional_expression,
    S.AssignmentExpression: Printer.assignment,
    S.ThrowExpression: lambda self, node, depth: "throw" + (
        " " + self.expression(node.operand, ASSIGNMENT, depth) if node.operand is not None else ""),
    S.YieldExpression: lambda self, node, depth: "co_yield " + self.expression(node.operand, ASSIGNMENT, depth),
    S.PackExpansion: lambda self, node, depth: (
        self.text(node.pattern, depth) if isinstance(node.pattern, S.TypeId)
        else self.expression(node.pattern, POSTFIX, depth)) + "...",
    S.InitializerList: Printer.initializer_list, S.DesignatedInitializer: Printer.designated,
    S.FieldDesignator: Printer.designator, S.IndexDesignator: Printer.designator,
    S.CompoundLiteralExpression: lambda self, node, depth: (
        f"({self.text(node.type, depth)}){self.initializer_list(node.initializer, depth)}"),
    S.GenericSelection: Printer.generic,
    S.StatementExpression: lambda self, node, depth: f"({self.block(node.body.items, depth)})",
    S.ExtensionExpression: lambda self, node, depth: "__extension__ " + self.expression(node.operand, UNARY, depth),
    S.DefinedExpression: lambda self, node, depth: f"defined({node.name.spelling})",
    **{k: Printer.keyword for k in (S.DeclSpecifier, S.CvQualifier, S.PrimitiveTypeSpecifier)},
    **{k: Printer.specifier for k in (S.ExplicitSpecifier, S.NamedTypeSpecifier, S.TypenameSpecifier,
                                      S.DecltypeSpecifier, S.PlaceholderTypeSpecifier, S.TypeofSpecifier,
                                      S.AtomicTypeSpecifier, S.BitIntSpecifier, S.PackIndexingSpecifier,
                                      S.SpliceSpecifier)},
    S.ClassSpecifier: Printer.class_, S.EnumSpecifier: Printer.enum, S.BaseSpecifier: Printer.base,
    **{k: Printer.declarator for k in (S.IdDeclarator, S.PackDeclarator, S.PointerDeclarator, S.ReferenceDeclarator,
                                       S.ArrayDeclarator, S.FunctionDeclarator, S.ParenthesizedDeclarator,
                                       S.StructuredBindingDeclarator)},
    S.TypeId: Printer.type_id, S.ParameterDeclaration: Printer.parameter, S.EllipsisParameter: Printer.parameter,
    S.TypeParameter: Printer.template_parameter, S.TemplateTemplateParameter: Printer.template_parameter,
    S.NoexceptSpecifier: Printer.exception, S.ThrowSpecifier: Printer.exception,
    S.PreconditionSpecifier: Printer.contract, S.PostconditionSpecifier: Printer.contract,
    **{k: Printer.attribute_specifier for k in (S.StandardAttributeSpecifier, S.AlignasSpecifier,
                                                S.GnuAttributeSpecifier, S.DeclspecSpecifier)},
    S.Attribute: Printer.attribute, S.Annotation: Printer.annotation,
    **{k: Printer.part for k in (S.InitDeclarator, S.MemberInitializer, S.VirtSpecifier, S.DefaultedBody,
                                 S.DeletedBody, S.MemberList, S.EnumeratorList, S.Enumerator, S.NamespaceName,
                                 S.UsingDeclarator, S.Handler, S.AsmOperand, S.GenericAssociation,
                                 S.EqualInitializer, S.ParenthesizedInitializer)},
})
