"""Syntax: the abstract syntax of C and C++, as one tree language (Ccpp), organized as the standard's grammar is.

The kinds cover the union of C++26 and C23: every construct of either language is a tree of these kinds, and each
kind and feature records the standards that have it (`SINCE`, `FEATURES`), which `Ccpp17`, `Ccpp20` and later
standards check. Common GNU and Microsoft extensions that real code depends on are kinds too, marked `EXTENSION`.

The tree is abstract where the grammar only spells and concrete where a transpiler needs to see what was written:

- Precedence levels collapse: every binary operator is a `BinaryExpression`. Parentheses written in the source stay,
  as `ParenthesizedExpression`, and printing adds those a hand-built tree needs.
- Equivalent spellings are normalized: alternative tokens (`and`, `bitor`) and digraphs become the primary tokens,
  and `defined X` becomes `defined(X)`. Keywords with distinct spellings (`_Alignof`, `alignof`) keep them.
- Names are syntax nodes (category `Name`) wherever they occur, so one traversal finds every use and declaration of a
  name. Expressions refer to them through `IdExpression`, types through `NamedTypeSpecifier`, declarators through
  `IdDeclarator`.
- Specifiers stay in source order, one syntax node per keyword, as decl-specifier-seq lists them.
- Declarators nest inside out, as the grammar defines them: `int *a[3]` declares `a` with
  `ArrayDeclarator(declarator=PointerDeclarator(declarator=IdDeclarator(a)))`... read from the name outwards.
- Literals keep their spelling: digits, separators and suffixes for numbers, and the characters between the quotes,
  escapes included, for characters and strings.
- Comments are kept where declarations, statements, members and enumerators are listed; elsewhere they are dropped.
  Preprocessor directives are kept where they are listed too, with conditional branches as trees.

Property names avoid both languages' reserved words: an `if` has a `consequence` and an `alternative`.
"""

from __future__ import annotations

from typing import Literal as Choice

from ..Framework.Syntax import Availability, Language, SyntaxNode

__all__ = ["LANGUAGE", "KINDS"]

CPP, C = "C++", "C"


def cpp(year: int) -> Availability:
    """C++ from `year` on; not C."""
    return {CPP: year}


def c(year: int) -> Availability:
    """C from `year` on; not C++."""
    return {C: year}


def both(cpp_year: int, c_year: int) -> Availability:
    """C++ from `cpp_year` on and C from `c_year` on."""
    return {CPP: cpp_year, C: c_year}


# --- Choices ---

Encoding = Choice["L", "u8", "u", "U"]
OverloadableOperator = Choice[
    "new", "delete", "new[]", "delete[]", "co_await", "()", "[]", "->", "->*", "~", "!", "+", "-", "*", "/", "%", "^",
    "&", "|", "=", "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|=", "==", "!=", "<", ">", "<=", ">=", "<=>", "&&", "||",
    "<<", ">>", "<<=", ">>=", "++", "--", ","]
UnaryOperator = Choice["+", "-", "!", "~", "*", "&", "++", "--"]
PostfixOperator = Choice["++", "--"]
BinaryOperator = Choice[
    ".*", "->*", "*", "/", "%", "+", "-", "<<", ">>", "<=>", "<", ">", "<=", ">=", "==", "!=", "&", "^", "|", "&&", "||",
    ","]
AssignmentOperator = Choice["=", "*=", "/=", "%=", "+=", "-=", ">>=", "<<=", "&=", "^=", "|="]
FoldOperator = Choice[
    "+", "-", "*", "/", "%", "^", "&", "|", "<<", ">>", "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|=", "<<=", ">>=",
    "=", "==", "!=", "<", ">", "<=", ">=", "&&", "||", ",", ".*", "->*"]
CastOperator = Choice["static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"]
AlignofKeyword = Choice["alignof", "_Alignof", "__alignof__", "__alignof", "_alignof"]
DeclKeyword = Choice[
    "static", "extern", "thread_local", "_Thread_local", "mutable", "register", "inline", "virtual", "_Noreturn",
    "friend", "typedef", "constexpr", "consteval", "constinit",
    "__inline", "__inline__", "__forceinline", "__thread", "__extension__", "noreturn"]
CvKeyword = Choice["const", "volatile", "restrict", "_Atomic", "__restrict", "__restrict__", "_Nonnull"]
PrimitiveKeyword = Choice[
    "void", "char", "char8_t", "char16_t", "char32_t", "wchar_t", "bool", "_Bool", "short", "int", "long", "signed",
    "unsigned", "float", "double", "_Complex", "_Imaginary", "_Decimal32", "_Decimal64", "_Decimal128", "_Float16",
    "_Float32", "_Float64", "_Float128", "_Float32x", "_Float64x", "_Float128x", "__int128", "__float128"]
TypeofKeyword = Choice["typeof", "typeof_unqual", "__typeof__", "__typeof"]
ClassKey = Choice["class", "struct", "union"]
EnumKey = Choice["enum", "enum class", "enum struct"]
Access = Choice["public", "protected", "private"]
AsmKeyword = Choice["asm", "__asm__", "__asm"]
IncludeKeyword = Choice["include", "include_next", "import"]



# --- Categories ---


class Name(SyntaxNode):
    """A name: what declarations declare and what expressions, types and declarators refer to ([expr.prim.id])."""


class Expression(SyntaxNode):
    """An expression ([expr]); also a braced initializer list where one may stand for an expression."""


class Literal(Expression):
    """A literal ([lex.literal])."""


class Statement(SyntaxNode):
    """A statement ([stmt]). Declarations are not statements here: blocks list them directly, and substatements may be
    declarations, as C++'s declaration statements are."""


class Declaration(SyntaxNode):
    """A declaration ([dcl]), a member declaration ([class.mem]) or a module declaration ([module])."""


class Specifier(SyntaxNode):
    """A decl-specifier or type-specifier ([dcl.spec]): one keyword, a type name, or a class or enum definition."""


class Declarator(SyntaxNode):
    """A declarator ([dcl.decl]), named or abstract: the part of a declaration that declares one name and its type."""


class Parameter(SyntaxNode):
    """A function parameter ([dcl.fct]), or the ellipsis of a variadic function."""


class TemplateParameter(SyntaxNode):
    """A template parameter that is a type or a template ([temp.param]). Constants are `ParameterDeclaration`s."""


class Initializer(SyntaxNode):
    """An initializer ([dcl.init]): `= value` or `(arguments)`; a braced list is an `InitializerList`."""


class Capture(SyntaxNode):
    """A lambda capture ([expr.prim.lambda.capture])."""


class Requirement(SyntaxNode):
    """A requirement in a requires-expression ([expr.prim.req])."""


class Designator(SyntaxNode):
    """A designator in a designated initializer ([dcl.init.general], C [6.7.10])."""


class AttributeSpecifier(SyntaxNode):
    """An attribute specifier ([dcl.attr]): `[[...]]`, `alignas(...)`, or an extension's attribute syntax."""


class ExceptionSpecification(SyntaxNode):
    """An exception specification ([except.spec]): `noexcept(...)` or a dynamic `throw(...)`."""


class ContractSpecifier(SyntaxNode):
    """A function contract specifier ([dcl.contract.func]): a precondition or a postcondition."""


class Directive(SyntaxNode):
    """A preprocessing directive ([cpp]), where declarations, statements, members or enumerators are listed."""


# === Lexical conventions [lex] ===


class Comment(SyntaxNode):
    """`// text` or, with `block`, `/* text */`. `text` excludes the delimiters. A `trailing` comment ends the line of
    the item before it."""

    block: bool
    text: str
    trailing: bool


# === Basics [basic] ===


class TranslationUnit(SyntaxNode):
    """A source file after its directives are kept as trees rather than performed ([basic.link])."""

    items: list[Declaration | Statement | Directive | Comment]


# === Expressions [expr] ===

# --- Names [expr.prim.id], [over.oper], [class.conv.fct], [over.literal], [temp.names] ---


class Identifier(Name):
    """An identifier ([lex.name]): letters, digits, `_` and `$`, not starting with a digit. Characters beyond ASCII
    are taken to be letters."""

    spelling: str

    def check(self) -> list[str]:
        spelling = self.spelling
        if type(spelling) is not str or not spelling:
            return []
        if spelling[0] in "0123456789" or not all(ch.isascii() is False or ch.isalnum() or ch in "_$" for ch in spelling):
            return [f"{spelling!r} is not an identifier"]
        return []


class OperatorName(Name):
    """`operator op`, naming an operator function ([over.oper])."""

    operator: OverloadableOperator
    FEATURES = {"operator": {"<=>": cpp(2020), "co_await": cpp(2020)}}
    SINCE = cpp(1998)


class ConversionName(Name):
    """`operator type`, naming a conversion function ([class.conv.fct])."""

    type: TypeId
    SINCE = cpp(1998)


class LiteralOperatorName(Name):
    """`operator""suffix`, naming a literal operator ([over.literal])."""

    suffix: str
    SINCE = cpp(2011)


class DestructorName(Name):
    """`~type`, naming a destructor ([class.dtor])."""

    type: Identifier | TemplateId | DecltypeSpecifier
    SINCE = cpp(1998)


class TemplateId(Name):
    """`name<arguments>`, or `template name<arguments>` with `template_keyword` ([temp.names])."""

    template_keyword: bool
    name: Identifier | OperatorName | LiteralOperatorName
    arguments: list[Expression | TypeId]
    SINCE = cpp(1998)


class QualifiedName(Name):
    """`q1::q2::name`, or `::q1::name` with `global_scope` ([expr.prim.id.qual]). Each qualifier names a namespace,
    class or enumeration."""

    global_scope: bool
    qualifiers: list[Identifier | TemplateId | DecltypeSpecifier | PackIndexingSpecifier | SpliceSpecifier]
    name: Name
    SINCE = cpp(1998)


# --- Literals [lex.literal] ---


class IntegerLiteral(Literal):
    """An integer literal, spelled as written: prefix, digits, separators and suffix ([lex.icon])."""

    spelling: str


class FloatingLiteral(Literal):
    """A floating-point literal, spelled as written ([lex.fcon])."""

    spelling: str


class CharacterLiteral(Literal):
    """`'text'`, with an optional encoding prefix ([lex.ccon]). `text` is spelled as written, escapes included."""

    prefix: Encoding | None
    text: str
    FEATURES = {"prefix": {"u8": both(2017, 2023), "u": both(2011, 2011), "U": both(2011, 2011)}}


class StringLiteral(Literal):
    """`"text"`, with an optional encoding prefix ([lex.string]). `text` is spelled as written, escapes included."""

    prefix: Encoding | None
    text: str
    FEATURES = {"prefix": {"u8": both(2011, 2011), "u": both(2011, 2011), "U": both(2011, 2011)}}


class RawStringLiteral(Literal):
    """`R"delimiter(text)delimiter"`, with an optional encoding prefix ([lex.string])."""

    prefix: Encoding | None
    delimiter: str | None
    text: str
    SINCE = cpp(2011)


class UserDefinedLiteral(Literal):
    """A literal followed by a user-defined suffix, such as `10_km` ([lex.ext])."""

    literal: IntegerLiteral | FloatingLiteral | CharacterLiteral | StringLiteral | RawStringLiteral
    suffix: str
    SINCE = cpp(2011)


class ConcatenatedString(Literal):
    """Adjacent string literals, concatenated ([lex.string]). Macros expanding to strings, such as `PRId64`, are
    `IdExpression`s among them."""

    parts: list[StringLiteral | RawStringLiteral | UserDefinedLiteral | IdExpression]


class BooleanLiteral(Literal):
    """`true`, or `false` unless `value` ([lex.bool])."""

    value: bool
    SINCE = both(1998, 2023)


class NullptrLiteral(Literal):
    """`nullptr` ([lex.nullptr])."""

    SINCE = both(2011, 2023)


# --- Primary expressions [expr.prim] ---


class ThisExpression(Expression):
    """`this` ([expr.prim.this])."""

    SINCE = cpp(1998)


class ParenthesizedExpression(Expression):
    """`(expression)` ([expr.prim.paren])."""

    expression: Expression


class IdExpression(Expression):
    """A name used as an expression ([expr.prim.id])."""

    name: Name


class LambdaExpression(Expression):
    """`[captures] <template_parameters> requires template_requires attributes declarator body`
    ([expr.prim.lambda]). Without a declarator, the lambda has no parameter list: `[] { ... }`."""

    captures: list[Capture]
    template_parameters: list[TemplateParameter | Parameter]
    template_requires: Expression | None
    attributes: list[AttributeSpecifier]
    declarator: LambdaDeclarator | None
    body: CompoundStatement
    SINCE = cpp(2011)
    FEATURES = {"template_parameters": {True: cpp(2020)}, "attributes": {True: cpp(2023)}}


class LambdaDeclarator(SyntaxNode):
    """`(parameters) specifiers exception attributes -> trailing_return requires contracts` ([expr.prim.lambda])."""

    parameters: list[Parameter]
    specifiers: list[DeclSpecifier]
    exception: ExceptionSpecification | None
    attributes: list[AttributeSpecifier]
    trailing_return: TypeId | None
    requires: Expression | None
    contracts: list[ContractSpecifier]
    SINCE = cpp(2011)
    FEATURES = {"requires": {True: cpp(2020)}, "contracts": {True: cpp(2026)}}


class DefaultCapture(Capture):
    """`=` or `&`: capture what the body uses, by copy or by reference ([expr.prim.lambda.capture])."""

    mode: Choice["=", "&"]
    SINCE = cpp(2011)


class SimpleCapture(Capture):
    """`name`, `&name`, `name...` or `&name...` ([expr.prim.lambda.capture])."""

    by_reference: bool
    name: Identifier
    pack: bool
    SINCE = cpp(2011)


class ThisCapture(Capture):
    """`this`, or `*this` with `copy` ([expr.prim.lambda.capture])."""

    copy: bool
    SINCE = cpp(2011)
    FEATURES = {"copy": {True: cpp(2017)}}


class InitCapture(Capture):
    """`name initializer`, `&name initializer`, `...name initializer` or `&...name initializer`
    ([expr.prim.lambda.capture])."""

    by_reference: bool
    pack: bool
    name: Identifier
    initializer: Initializer | InitializerList
    SINCE = cpp(2014)
    FEATURES = {"pack": {True: cpp(2020)}}


class FoldExpression(Expression):
    """`(left op ...)`, `(... op right)` or `(left op ... op right)` ([expr.prim.fold])."""

    left: Expression | None
    operator: FoldOperator
    right: Expression | None
    SINCE = cpp(2017)


class RequiresExpression(Expression):
    """`requires (parameters) { requirements }` ([expr.prim.req]). Without parameters, `requires { ... }`."""

    parameters: list[Parameter]
    requirements: list[Requirement]
    SINCE = cpp(2020)


class SimpleRequirement(Requirement):
    """`expression;` ([expr.prim.req.simple])."""

    expression: Expression
    SINCE = cpp(2020)


class TypeRequirement(Requirement):
    """`typename name;` ([expr.prim.req.type])."""

    name: Name
    SINCE = cpp(2020)


class CompoundRequirement(Requirement):
    """`{ expression } noexcept -> return_type;` ([expr.prim.req.compound]). `return_type` is a type constraint."""

    expression: Expression
    noexcept: bool
    return_type: Name | None
    SINCE = cpp(2020)


class NestedRequirement(Requirement):
    """`requires constraint;` ([expr.prim.req.nested])."""

    constraint: Expression
    SINCE = cpp(2020)


class PackIndexingExpression(Expression):
    """`pack...[index]` ([expr.prim.pack.index])."""

    pack: Name
    index: Expression
    SINCE = cpp(2026)


class ReflectExpression(Expression):
    """`^^operand`, reflecting a name, type, namespace or expression; `^^::` without an operand ([expr.reflect])."""

    operand: Name | TypeId | Expression | None
    SINCE = cpp(2026)


class SpliceExpression(Expression):
    """`[: reflection :]`, or `template [: reflection :] <arguments>` ([expr.prim.splice])."""

    template_keyword: bool
    reflection: Expression
    arguments: list[Expression | TypeId]
    SINCE = cpp(2026)


# --- Postfix expressions [expr.post] ---


class SubscriptExpression(Expression):
    """`object[indices]` ([expr.sub]); several indices since C++23."""

    object: Expression
    indices: list[Expression]

    def features(self) -> list[tuple[str, Availability]]:
        return [("SubscriptExpression with several indices", cpp(2023))] if len(self.indices) > 1 else []


class CallExpression(Expression):
    """`function(arguments)` ([expr.call]). A macro's arguments may be types, as in `offsetof(S, m)`."""

    function: Expression
    arguments: list[Expression | TypeId]


class FunctionalCastExpression(Expression):
    """`type(arguments)` or `type{items}`: explicit type conversion in functional notation ([expr.type.conv])."""

    type: Specifier
    initializer: ParenthesizedInitializer | InitializerList
    SINCE = cpp(1998)


class MemberExpression(Expression):
    """`object.member` or `object->member`, with `template_keyword` `object.template member` ([expr.ref])."""

    object: Expression
    operator: Choice[".", "->"]
    template_keyword: bool
    member: Name


class PostfixExpression(Expression):
    """`operand++` or `operand--` ([expr.post.incr])."""

    operand: Expression
    operator: PostfixOperator


class NamedCastExpression(Expression):
    """`static_cast<type>(operand)` and its siblings ([expr.static.cast] and following)."""

    operator: CastOperator
    type: TypeId
    operand: Expression
    SINCE = cpp(1998)


class TypeidExpression(Expression):
    """`typeid(operand)` ([expr.typeid])."""

    operand: Expression | TypeId
    SINCE = cpp(1998)


# --- Unary expressions [expr.unary] ---


class UnaryExpression(Expression):
    """`op operand` for the prefix operators ([expr.unary.op], [expr.pre.incr])."""

    operator: UnaryOperator
    operand: Expression


class AwaitExpression(Expression):
    """`co_await operand` ([expr.await])."""

    operand: Expression
    SINCE = cpp(2020)


class SizeofExpression(Expression):
    """`sizeof operand` or `sizeof(type)` ([expr.sizeof])."""

    operand: Expression | TypeId


class SizeofPackExpression(Expression):
    """`sizeof...(pack)` ([expr.sizeof])."""

    pack: Identifier
    SINCE = cpp(2011)


class AlignofExpression(Expression):
    """`alignof(operand)`, or one of its other spellings ([expr.alignof], C [6.5.4.5])."""

    keyword: AlignofKeyword
    operand: TypeId | Expression
    SINCE = both(2011, 2011)
    FEATURES = {"keyword": {"alignof": both(2011, 2023), "_Alignof": c(2011)}}


class NoexceptExpression(Expression):
    """`noexcept(operand)` ([expr.unary.noexcept])."""

    operand: Expression
    SINCE = cpp(2011)


class NewExpression(Expression):
    """`::new (placement) type initializer` ([expr.new]); with `parenthesized_type`, `new (type)`."""

    global_scope: bool
    placement: list[Expression]
    parenthesized_type: bool
    type: TypeId
    initializer: ParenthesizedInitializer | InitializerList | None
    SINCE = cpp(1998)


class DeleteExpression(Expression):
    """`::delete operand` or `::delete[] operand` ([expr.delete])."""

    global_scope: bool
    array: bool
    operand: Expression
    SINCE = cpp(1998)


# --- Other expressions [expr.cast] to [expr.comma] ---


class CastExpression(Expression):
    """`(type) operand` ([expr.cast])."""

    type: TypeId
    operand: Expression


class BinaryExpression(Expression):
    """`left op right` for every binary operator but assignment ([expr.mptr.oper] to [expr.comma])."""

    left: Expression
    operator: BinaryOperator
    right: Expression
    FEATURES = {"operator": {"<=>": cpp(2020), ".*": cpp(1998), "->*": cpp(1998)}}


class ConditionalExpression(Expression):
    """`condition ? consequence : alternative` ([expr.cond]); without a consequence, the GNU `condition ?:
    alternative`."""

    condition: Expression
    consequence: Expression | None
    alternative: Expression


class AssignmentExpression(Expression):
    """`left op right` for the assignment operators ([expr.assign])."""

    left: Expression
    operator: AssignmentOperator
    right: Expression


class ThrowExpression(Expression):
    """`throw operand`, or `throw` to rethrow ([expr.throw])."""

    operand: Expression | None
    SINCE = cpp(1998)


class YieldExpression(Expression):
    """`co_yield operand` ([expr.yield])."""

    operand: Expression
    SINCE = cpp(2020)


class PackExpansion(Expression):
    """`pattern...`, expanding a pack in a list of expressions or types ([temp.variadic])."""

    pattern: Expression | TypeId
    SINCE = cpp(2011)


class InitializerList(Expression):
    """`{items}`, with `trailing_comma` `{items,}` ([dcl.init.list])."""

    items: list[Expression | DesignatedInitializer]
    trailing_comma: bool


class DesignatedInitializer(SyntaxNode):
    """`designators initializer`, such as `.x = 1`, `.x{1}` or C's `[2].y = 3` ([dcl.init.general], C [6.7.10])."""

    designators: list[Designator]
    initializer: EqualInitializer | InitializerList
    SINCE = both(2020, 1999)

    def features(self) -> list[tuple[str, Availability]]:
        nested = len(self.designators) > 1 or any(not isinstance(d, FieldDesignator) for d in self.designators)
        return [("DesignatedInitializer with array or nested designators", c(1999))] if nested else []


class FieldDesignator(Designator):
    """`.name`."""

    name: Identifier


class IndexDesignator(Designator):
    """`[index]`, or the GNU `[index ... last]`."""

    index: Expression
    last: Expression | None
    SINCE = c(1999)


class CompoundLiteralExpression(Expression):
    """`(type){items}`: an unnamed object (C [6.5.3.6])."""

    type: TypeId
    initializer: InitializerList
    SINCE = c(1999)


class GenericSelection(Expression):
    """`_Generic(controlling, associations)` (C [6.5.2.1])."""

    controlling: Expression | TypeId
    associations: list[GenericAssociation]
    SINCE = c(2011)


class GenericAssociation(SyntaxNode):
    """`type: value`, or `default: value` without a type (C [6.5.2.1])."""

    type: TypeId | None
    value: Expression
    SINCE = c(2011)


class StatementExpression(Expression):
    """`({ items })`, a GNU statement expression whose value is its last statement's."""

    body: CompoundStatement
    EXTENSION = True


class ExtensionExpression(Expression):
    """`__extension__ operand`, a GNU marker silencing warnings about extensions."""

    operand: Expression
    EXTENSION = True


class DefinedExpression(Expression):
    """`defined(name)`, in a preprocessing condition ([cpp.cond])."""

    name: Identifier


# === Statements [stmt] ===


class LabeledStatement(Statement):
    """`label: statement` ([stmt.label]); without a statement, a label ending a block (C++23, C23)."""

    label: Identifier
    statement: Statement | Declaration | None

    def features(self) -> list[tuple[str, Availability]]:
        return [("LabeledStatement without a statement", both(2023, 2023))] if self.statement is None else []


class CaseStatement(Statement):
    """`case value: statement`, or the GNU range `case value ... last: statement` ([stmt.label])."""

    value: Expression
    last: Expression | None
    statement: Statement | Declaration | None

    def features(self) -> list[tuple[str, Availability]]:
        return [("CaseStatement without a statement", both(2023, 2023))] if self.statement is None else []


class DefaultStatement(Statement):
    """`default: statement` ([stmt.label])."""

    statement: Statement | Declaration | None

    def features(self) -> list[tuple[str, Availability]]:
        return [("DefaultStatement without a statement", both(2023, 2023))] if self.statement is None else []


class ExpressionStatement(Statement):
    """`expression;`, or `;` without an expression ([stmt.expr])."""

    expression: Expression | None


class CompoundStatement(Statement):
    """`{ items }` ([stmt.block])."""

    items: list[Statement | Declaration | Directive | Comment]


class IfStatement(Statement):
    """`if constexpr (initializer condition) consequence else alternative` ([stmt.if]), or `if !consteval
    consequence else alternative` with `consteval` (and `negated`), which has no condition."""

    constexpr: bool
    consteval: bool
    negated: bool
    initializer: Statement | Declaration | None
    condition: Expression | Declaration | None
    consequence: Statement | Declaration
    alternative: Statement | Declaration | None
    FEATURES = {"constexpr": {True: cpp(2017)}, "consteval": {True: cpp(2023)}, "initializer": {True: cpp(2017)}}


class SwitchStatement(Statement):
    """`switch (initializer condition) body` ([stmt.switch])."""

    initializer: Statement | Declaration | None
    condition: Expression | Declaration
    body: Statement | Declaration
    FEATURES = {"initializer": {True: cpp(2017)}}


class WhileStatement(Statement):
    """`while (condition) body` ([stmt.while])."""

    condition: Expression | Declaration
    body: Statement | Declaration


class DoStatement(Statement):
    """`do body while (condition);` ([stmt.do])."""

    body: Statement | Declaration
    condition: Expression


class ForStatement(Statement):
    """`for (initializer condition; increment) body` ([stmt.for]). The initializer ends with its own `;`; without
    one, the statement is `for (; condition; increment)`."""

    initializer: Statement | Declaration | None
    condition: Expression | Declaration | None
    increment: Expression | None
    body: Statement | Declaration


class RangeForStatement(Statement):
    """`for (initializer declaration : range) body` ([stmt.ranged]), or with `template_keyword` the expansion
    statement `template for (...)` ([stmt.expand])."""

    template_keyword: bool
    initializer: Statement | Declaration | None
    declaration: Declaration
    range: Expression
    body: Statement | Declaration
    SINCE = cpp(2011)
    FEATURES = {"initializer": {True: cpp(2020)}, "template_keyword": {True: cpp(2026)}}


class BreakStatement(Statement):
    """`break;` ([stmt.break])."""


class ContinueStatement(Statement):
    """`continue;` ([stmt.cont])."""


class ReturnStatement(Statement):
    """`return value;` ([stmt.return])."""

    value: Expression | None


class CoReturnStatement(Statement):
    """`co_return value;` ([stmt.return.coroutine])."""

    value: Expression | None
    SINCE = cpp(2020)


class GotoStatement(Statement):
    """`goto label;` ([stmt.goto])."""

    label: Identifier


class TryStatement(Statement):
    """`try body handlers` ([except.pre]); also a function-try-block, as a function definition's body."""

    body: CompoundStatement
    handlers: list[Handler]
    SINCE = cpp(1998)


class Handler(SyntaxNode):
    """`catch (parameter) body`; `catch (...)` when the parameter is an `EllipsisParameter` ([except.pre])."""

    parameter: Parameter
    body: CompoundStatement
    SINCE = cpp(1998)


class AttributedStatement(Statement):
    """`attributes statement` ([stmt.pre])."""

    attributes: list[AttributeSpecifier]
    statement: Statement


class ContractAssertStatement(Statement):
    """`contract_assert attributes (predicate);` ([stmt.contract.assert])."""

    attributes: list[AttributeSpecifier]
    predicate: Expression
    SINCE = cpp(2026)


# === Declarations [dcl] ===


class SimpleDeclaration(Declaration):
    """`attributes specifiers declarators;` ([dcl.pre]): variables, functions, types, typedefs, friends and members.
    Without `;` where it is a condition or a for-range declaration."""

    attributes: list[AttributeSpecifier]
    specifiers: list[Specifier | AttributeSpecifier]
    declarators: list[InitDeclarator]


class InitDeclarator(SyntaxNode):
    """One declarator of a declaration with what follows it ([dcl.decl], [class.mem]): `declarator virt_specifiers
    = 0` (with `pure`), `declarator : bitfield initializer`, `declarator initializer`, or `declarator requires
    contracts`. Without a declarator, an unnamed bit-field."""

    declarator: Declarator | None
    virt_specifiers: list[VirtSpecifier]
    pure: bool
    bitfield: Expression | None
    initializer: Initializer | InitializerList | None
    requires: Expression | None
    contracts: list[ContractSpecifier]
    FEATURES = {"requires": {True: cpp(2020)}, "contracts": {True: cpp(2026)}, "virt_specifiers": {True: cpp(2011)},
                "pure": {True: cpp(1998)}}


class FunctionDefinition(Declaration):
    """`attributes specifiers declarator virt_specifiers requires contracts : initializers body` ([dcl.fct.def]).
    The body is a block, a function-try-block, `= default;` or `= delete;`."""

    attributes: list[AttributeSpecifier]
    specifiers: list[Specifier | AttributeSpecifier]
    declarator: Declarator
    virt_specifiers: list[VirtSpecifier]
    requires: Expression | None
    contracts: list[ContractSpecifier]
    initializers: list[MemberInitializer]
    body: CompoundStatement | TryStatement | DefaultedBody | DeletedBody
    FEATURES = {"requires": {True: cpp(2020)}, "contracts": {True: cpp(2026)}, "virt_specifiers": {True: cpp(2011)},
                "initializers": {True: cpp(1998)}}


class DefaultedBody(SyntaxNode):
    """`= default;` ([dcl.fct.def.default])."""

    SINCE = cpp(2011)


class DeletedBody(SyntaxNode):
    """`= delete;`, or `= delete(reason);` ([dcl.fct.def.delete])."""

    reason: Expression | None
    SINCE = cpp(2011)
    FEATURES = {"reason": {True: cpp(2026)}}


class MemberInitializer(SyntaxNode):
    """`member(arguments)` or `member{items}` in a constructor's initializer list, with `pack` `member(...)...`
    ([class.base.init])."""

    member: Name
    initializer: ParenthesizedInitializer | InitializerList
    pack: bool
    SINCE = cpp(1998)


class VirtSpecifier(SyntaxNode):
    """`override` or `final` ([class.mem])."""

    keyword: Choice["override", "final"]
    SINCE = cpp(2011)


# --- Specifiers [dcl.spec] ---


class DeclSpecifier(Specifier):
    """A keyword specifier: storage class, function specifier, `friend`, `typedef`, `constexpr`, `consteval`,
    `constinit` or `inline` ([dcl.stc] to [dcl.constinit])."""

    keyword: DeclKeyword
    FEATURES = {"keyword": {
        "thread_local": both(2011, 2023), "_Thread_local": c(2011), "mutable": cpp(1998), "register": both((1998, 2017), 1989),
        "inline": both(1998, 1999), "virtual": cpp(1998), "_Noreturn": c(2011), "friend": cpp(1998),
        "constexpr": both(2011, 2023), "consteval": cpp(2020), "constinit": cpp(2020)}}


class ExplicitSpecifier(Specifier):
    """`explicit`, or `explicit(condition)` ([dcl.fct.spec])."""

    condition: Expression | None
    SINCE = cpp(1998)
    FEATURES = {"condition": {True: cpp(2020)}}


class CvQualifier(Specifier):
    """`const`, `volatile`, C's `restrict` and `_Atomic`, and their extensions ([dcl.type.cv], C [6.7.4])."""

    keyword: CvKeyword
    FEATURES = {"keyword": {"restrict": c(1999), "_Atomic": c(2011)}}


class PrimitiveTypeSpecifier(Specifier):
    """A fundamental type keyword: `int`, `unsigned`, `double`... ([dcl.type.simple]). `unsigned long` is two."""

    keyword: PrimitiveKeyword
    FEATURES = {"keyword": {
        "char8_t": cpp(2020), "char16_t": cpp(2011), "char32_t": cpp(2011), "wchar_t": cpp(1998),
        "bool": both(1998, 2023), "_Bool": c(1999), "_Complex": c(1999), "_Imaginary": c(1999),
        "_Decimal32": c(2023), "_Decimal64": c(2023), "_Decimal128": c(2023)}}


class NamedTypeSpecifier(Specifier):
    """A type named by a class, enumeration, typedef or template name ([dcl.type.simple])."""

    name: Name


class TypenameSpecifier(Specifier):
    """`typename name`, naming a type in a dependent scope ([temp.res])."""

    name: Name
    SINCE = cpp(1998)


class ClassSpecifier(Specifier):
    """`key attributes name final : bases { members }` ([class.pre]); without a body, the elaborated type specifier
    `key attributes name` ([dcl.type.elab])."""

    key: ClassKey
    attributes: list[AttributeSpecifier]
    name: Name | None
    final: bool
    bases: list[BaseSpecifier]
    body: MemberList | None
    FEATURES = {"final": {True: cpp(2011)}, "bases": {True: cpp(1998)}}


class MemberList(SyntaxNode):
    """`{ items }`: a class's member specification ([class.mem])."""

    items: list[Declaration | Directive | Comment]


class EnumSpecifier(Specifier):
    """`key attributes name : base { enumerators }` ([dcl.enum]); without a body, an opaque enumeration declaration
    or an elaborated type specifier."""

    key: EnumKey
    attributes: list[AttributeSpecifier]
    name: Name | None
    base: TypeId | None
    body: EnumeratorList | None
    FEATURES = {"key": {"enum class": cpp(2011), "enum struct": cpp(2011)}, "base": {True: both(2011, 2023)}}


class EnumeratorList(SyntaxNode):
    """`{ enumerators }`, with `trailing_comma` `{ enumerators, }` ([dcl.enum])."""

    enumerators: list[Enumerator | Directive | Comment]
    trailing_comma: bool


class Enumerator(SyntaxNode):
    """`name attributes = value` ([dcl.enum])."""

    name: Identifier
    attributes: list[AttributeSpecifier]
    value: Expression | None


class DecltypeSpecifier(Specifier):
    """`decltype(expression)` ([dcl.type.decltype])."""

    expression: Expression
    SINCE = cpp(2011)


class PlaceholderTypeSpecifier(Specifier):
    """`auto`, `decltype(auto)` with `decltype`, each optionally constrained: `C<T> auto` ([dcl.spec.auto])."""

    constraint: Name | None
    decltype: bool
    SINCE = both(2011, 2023)
    FEATURES = {"decltype": {True: cpp(2014)}, "constraint": {True: cpp(2020)}}


class TypeofSpecifier(Specifier):
    """`typeof(operand)` or `typeof_unqual(operand)` (C [6.7.3.6]), and the GNU `__typeof__`."""

    keyword: TypeofKeyword
    operand: Expression | TypeId
    SINCE = c(2023)

    def availability(self) -> Availability | None:
        return None if self.keyword in ("__typeof__", "__typeof") else self.SINCE


class AtomicTypeSpecifier(Specifier):
    """`_Atomic(type)` (C [6.7.3.5])."""

    type: TypeId
    SINCE = c(2011)


class BitIntSpecifier(Specifier):
    """`_BitInt(width)` (C [6.7.3])."""

    width: Expression
    SINCE = c(2023)


class PackIndexingSpecifier(Specifier):
    """`pack...[index]`, a type of a pack ([dcl.type.pack.index])."""

    pack: Name
    index: Expression
    SINCE = cpp(2026)


class SpliceSpecifier(Specifier):
    """`typename [: reflection :]`, or `template [: reflection :] <arguments>` ([dcl.type.splice])."""

    typename_keyword: bool
    template_keyword: bool
    reflection: Expression
    arguments: list[Expression | TypeId]
    SINCE = cpp(2026)


# --- Declarators [dcl.decl] ---


class IdDeclarator(Declarator):
    """`name attributes`: the declarator-id, innermost in every named declarator ([dcl.decl])."""

    name: Name
    attributes: list[AttributeSpecifier]


class PackDeclarator(Declarator):
    """`...declarator`, declaring a pack; abstract (`...` alone) without a declarator ([dcl.fct])."""

    declarator: Declarator | None
    SINCE = cpp(2011)


class PointerDeclarator(Declarator):
    """`* attributes qualifiers declarator`, or `scope::* ...` for a pointer to member ([dcl.ptr], [dcl.mptr])."""

    scope: Name | None
    attributes: list[AttributeSpecifier]
    qualifiers: list[CvQualifier]
    declarator: Declarator | None
    FEATURES = {"scope": {True: cpp(1998)}}


class ReferenceDeclarator(Declarator):
    """`& attributes declarator`, or `&& ...` with `rvalue` ([dcl.ref])."""

    rvalue: bool
    attributes: list[AttributeSpecifier]
    declarator: Declarator | None
    SINCE = cpp(1998)
    FEATURES = {"rvalue": {True: cpp(2011)}}


class ArrayDeclarator(Declarator):
    """`declarator[static qualifiers size] attributes`, or C's `[*]` with `star` ([dcl.array], C [6.7.7.3])."""

    declarator: Declarator | None
    static: bool
    qualifiers: list[CvQualifier]
    size: Expression | None
    star: bool
    attributes: list[AttributeSpecifier]
    FEATURES = {"static": {True: c(1999)}, "qualifiers": {True: c(1999)}, "star": {True: c(1999)}}


class FunctionDeclarator(Declarator):
    """`declarator(parameters) qualifiers ref_qualifier exception attributes -> trailing_return` ([dcl.fct])."""

    declarator: Declarator | None
    parameters: list[Parameter]
    qualifiers: list[CvQualifier]
    ref_qualifier: Choice["&", "&&"] | None
    exception: ExceptionSpecification | None
    attributes: list[AttributeSpecifier]
    trailing_return: TypeId | None
    FEATURES = {"qualifiers": {True: cpp(1998)}, "ref_qualifier": {True: cpp(2011)},
                "trailing_return": {True: cpp(2011)}}


class ParenthesizedDeclarator(Declarator):
    """`(declarator)` ([dcl.decl])."""

    declarator: Declarator


class StructuredBindingDeclarator(Declarator):
    """`[bindings]` ([dcl.struct.bind]): each binding is a name with attributes, or a pack of one."""

    bindings: list[IdDeclarator | PackDeclarator]
    SINCE = cpp(2017)

    def features(self) -> list[tuple[str, Availability]]:
        found: list[tuple[str, Availability]] = []
        if any(isinstance(b, PackDeclarator) for b in self.bindings):
            found.append(("StructuredBindingDeclarator with a pack", cpp(2026)))
        if any(isinstance(b, IdDeclarator) and b.attributes for b in self.bindings):
            found.append(("StructuredBindingDeclarator with attributes", cpp(2026)))
        return found


class TypeId(SyntaxNode):
    """`specifiers declarator`: a type, named by specifiers and an abstract declarator ([dcl.name])."""

    specifiers: list[Specifier | AttributeSpecifier]
    declarator: Declarator | None


class ParameterDeclaration(Parameter):
    """`attributes this specifiers declarator = default` ([dcl.fct]); with `this_keyword`, an explicit object
    parameter. Also a constant template parameter."""

    attributes: list[AttributeSpecifier]
    this_keyword: bool
    specifiers: list[Specifier | AttributeSpecifier]
    declarator: Declarator | None
    default: Expression | None
    FEATURES = {"this_keyword": {True: cpp(2023)}}


class EllipsisParameter(Parameter):
    """`...`: the variable arguments of a variadic function, or the parameter of `catch (...)` ([dcl.fct])."""


# --- Initializers [dcl.init] ---


class EqualInitializer(Initializer):
    """`= value` ([dcl.init])."""

    value: Expression


class ParenthesizedInitializer(Initializer):
    """`(arguments)` ([dcl.init])."""

    arguments: list[Expression]
    SINCE = cpp(1998)


# --- Exception specifications [except.spec] ---


class NoexceptSpecifier(ExceptionSpecification):
    """`noexcept`, or `noexcept(condition)` ([except.spec])."""

    condition: Expression | None
    SINCE = cpp(2011)


class ThrowSpecifier(ExceptionSpecification):
    """`throw(types)`: a dynamic exception specification, removed in C++17; `throw()` lasted until C++20
    ([except.spec] in C++14)."""

    types: list[TypeId | PackExpansion]
    SINCE = cpp(1998)

    def features(self) -> list[tuple[str, Availability]]:
        if self.types:
            return [("ThrowSpecifier with types", {CPP: (1998, 2017)})]
        return [("ThrowSpecifier", {CPP: (1998, 2020)})]


# --- Contract specifiers [dcl.contract] ---


class PreconditionSpecifier(ContractSpecifier):
    """`pre attributes (predicate)` ([dcl.contract.func])."""

    attributes: list[AttributeSpecifier]
    predicate: Expression
    SINCE = cpp(2026)


class PostconditionSpecifier(ContractSpecifier):
    """`post attributes (result: predicate)` ([dcl.contract.func])."""

    attributes: list[AttributeSpecifier]
    result: Identifier | None
    predicate: Expression
    SINCE = cpp(2026)


# --- Namespaces [basic.namespace] ---


class NamespaceDefinition(Declaration):
    """`inline namespace attributes names { items }` ([namespace.def]); unnamed without names, nested with several
    (`namespace a::inline b`)."""

    inline: bool
    attributes: list[AttributeSpecifier]
    names: list[NamespaceName]
    items: list[Declaration | Directive | Comment]
    SINCE = cpp(1998)
    FEATURES = {"inline": {True: cpp(2011)}, "attributes": {True: cpp(2017)}}

    def features(self) -> list[tuple[str, Availability]]:
        found: list[tuple[str, Availability]] = []
        if len(self.names) > 1:
            found.append(("NamespaceDefinition with nested names", cpp(2017)))
            if any(n.inline for n in self.names):
                found.append(("NamespaceDefinition with inline nested names", cpp(2020)))
        return found


class NamespaceName(SyntaxNode):
    """One name of a namespace definition, `inline name` with `inline` ([namespace.def])."""

    inline: bool
    name: Identifier
    SINCE = cpp(1998)


class NamespaceAliasDefinition(Declaration):
    """`namespace name = target;` ([namespace.alias])."""

    name: Identifier
    target: Name
    SINCE = cpp(1998)


class UsingDirective(Declaration):
    """`attributes using namespace name;` ([namespace.udir])."""

    attributes: list[AttributeSpecifier]
    name: Name
    SINCE = cpp(1998)


class UsingDeclaration(Declaration):
    """`using declarators;` ([namespace.udecl])."""

    declarators: list[UsingDeclarator]
    SINCE = cpp(1998)

    def features(self) -> list[tuple[str, Availability]]:
        return [("UsingDeclaration with several declarators", cpp(2017))] if len(self.declarators) > 1 else []


class UsingDeclarator(SyntaxNode):
    """`typename name...` ([namespace.udecl])."""

    typename_keyword: bool
    name: Name
    pack: bool
    SINCE = cpp(1998)
    FEATURES = {"pack": {True: cpp(2017)}}


class UsingEnumDeclaration(Declaration):
    """`using enum type;` ([enum.udecl])."""

    type: Name
    SINCE = cpp(2020)


class AliasDeclaration(Declaration):
    """`using name attributes = type;` ([dcl.typedef])."""

    name: Identifier
    attributes: list[AttributeSpecifier]
    type: TypeId
    SINCE = cpp(2011)


class StaticAssertDeclaration(Declaration):
    """`static_assert(condition, message);` ([dcl.pre], C [6.7.12])."""

    keyword: Choice["static_assert", "_Static_assert"]
    condition: Expression
    message: Expression | None
    SINCE = both(2011, 2011)
    FEATURES = {"keyword": {"static_assert": both(2011, 2023), "_Static_assert": c(2011)}}

    def features(self) -> list[tuple[str, Availability]]:
        return [("StaticAssertDeclaration without a message", both(2017, 2023))] if self.message is None else []


class AttributeDeclaration(Declaration):
    """`attributes;` ([dcl.pre])."""

    attributes: list[AttributeSpecifier]
    SINCE = both(2011, 2023)


class EmptyDeclaration(Declaration):
    """`;` ([dcl.pre])."""


class LinkageSpecification(Declaration):
    """`extern "language" { items }`, or without `braced` `extern "language" item` ([dcl.link])."""

    language: str
    braced: bool
    items: list[Declaration | Directive | Comment]
    SINCE = cpp(1998)


class AsmDeclaration(Declaration):
    """`asm volatile inline goto (template : outputs : inputs : clobbers : labels);` ([dcl.asm]). Operands and the
    sections after the template are GNU extensions."""

    attributes: list[AttributeSpecifier]
    keyword: AsmKeyword
    volatile: bool
    inline: bool
    goto: bool
    template: Expression
    outputs: list[AsmOperand]
    inputs: list[AsmOperand]
    clobbers: list[Expression]
    labels: list[Identifier]


class AsmOperand(SyntaxNode):
    """`[name] constraint (value)` (GNU)."""

    name: Identifier | None
    constraint: Expression
    value: Expression
    EXTENSION = True


# --- Attributes [dcl.attr] ---


class StandardAttributeSpecifier(AttributeSpecifier):
    """`[[using namespace: attributes]]` ([dcl.attr.grammar])."""

    using_namespace: str | None
    attributes: list[Attribute | Annotation]
    SINCE = both(2011, 2023)
    FEATURES = {"using_namespace": {True: cpp(2017)}}


class Attribute(SyntaxNode):
    """`namespace::name(arguments)`, or `name...` with `pack` ([dcl.attr.grammar]). The arguments of an attribute are
    balanced tokens in the grammar; here they are expressions."""

    namespace: str | None
    name: str
    arguments: list[Expression | TypeId]
    pack: bool


class Annotation(SyntaxNode):
    """`=value`, or `=value...` with `pack`: an annotation for reflection ([dcl.attr.annotation])."""

    value: Expression
    pack: bool
    SINCE = cpp(2026)


class AlignasSpecifier(AttributeSpecifier):
    """`alignas(operand)`, `alignas(operand...)` with `pack`, or C's `_Alignas(operand)` ([dcl.align])."""

    keyword: Choice["alignas", "_Alignas"]
    operand: Expression | TypeId
    pack: bool
    SINCE = both(2011, 2011)
    FEATURES = {"keyword": {"alignas": both(2011, 2023), "_Alignas": c(2011)}}


class GnuAttributeSpecifier(AttributeSpecifier):
    """`__attribute__((attributes))` (GNU)."""

    keyword: Choice["__attribute__", "__attribute"]
    attributes: list[Attribute]
    EXTENSION = True


class DeclspecSpecifier(AttributeSpecifier):
    """`__declspec(attributes)` (Microsoft)."""

    attributes: list[Attribute]
    EXTENSION = True


# === Modules [module] ===


class ModuleDeclaration(Declaration):
    """`export module name:partition attributes;` ([module.unit]). Names are dotted, such as `std.core`."""

    export: bool
    name: str
    partition: str | None
    attributes: list[AttributeSpecifier]
    SINCE = cpp(2020)


class GlobalModuleFragment(Declaration):
    """`module;`, opening the global module fragment ([module.global.frag])."""

    SINCE = cpp(2020)


class PrivateModuleFragment(Declaration):
    """`module :private;`, opening the private module fragment ([module.private.frag])."""

    SINCE = cpp(2020)


class ImportDeclaration(Declaration):
    """`export import name:partition attributes;`, or `import <header>;` with `system` and `import "header";`
    ([module.import])."""

    export: bool
    name: str | None
    partition: str | None
    header: str | None
    system: bool
    attributes: list[AttributeSpecifier]
    SINCE = cpp(2020)


class ExportDeclaration(Declaration):
    """`export { items }`, or without `braced` `export item` ([module.interface])."""

    braced: bool
    items: list[Declaration | Directive | Comment]
    SINCE = cpp(2020)


# === Classes [class] ===


class AccessSpecifier(Declaration):
    """`public:`, `protected:` or `private:` among a class's members ([class.access.spec])."""

    access: Access
    SINCE = cpp(1998)


class BaseSpecifier(SyntaxNode):
    """`attributes virtual access type...` ([class.derived]). `virtual` is written before the access."""

    attributes: list[AttributeSpecifier]
    virtual: bool
    access: Access | None
    type: Name | DecltypeSpecifier | PackIndexingSpecifier | SpliceSpecifier
    pack: bool
    SINCE = cpp(1998)
    FEATURES = {"pack": {True: cpp(2011)}, "attributes": {True: cpp(2011)}}


class FriendTypeDeclaration(Declaration):
    """`friend types;`: befriending several types, or packs of them ([class.friend])."""

    types: list[TypeId | PackExpansion]
    SINCE = cpp(2026)


# === Templates [temp] ===


class TemplateDeclaration(Declaration):
    """`template <parameters> requires declaration` ([temp.pre]); an explicit specialization without parameters."""

    parameters: list[TemplateParameter | Parameter]
    requires: Expression | None
    declaration: Declaration
    SINCE = cpp(1998)
    FEATURES = {"requires": {True: cpp(2020)}}


class TypeParameter(TemplateParameter):
    """`key ...name = default` with `key` `class` or `typename`, or the constrained `constraint ...name = default`
    ([temp.param])."""

    key: Choice["class", "typename"] | None
    constraint: Name | None
    pack: bool
    name: Identifier | None
    default: TypeId | None
    SINCE = cpp(1998)
    FEATURES = {"pack": {True: cpp(2011)}, "constraint": {True: cpp(2020)}}


class TemplateTemplateParameter(TemplateParameter):
    """`template <parameters> requires key ...name = default` ([temp.param]); `key` is `class` or `typename`, or for
    a concept or variable template `concept` or `auto`."""

    parameters: list[TemplateParameter | Parameter]
    requires: Expression | None
    key: Choice["class", "typename", "concept", "auto"]
    pack: bool
    name: Identifier | None
    default: Name | None
    SINCE = cpp(1998)
    FEATURES = {"pack": {True: cpp(2011)}, "requires": {True: cpp(2020)}, "key": {
        "typename": cpp(2017), "concept": cpp(2026), "auto": cpp(2026)}}


class ConceptDefinition(Declaration):
    """`concept name attributes = constraint;` ([temp.concept])."""

    name: Identifier
    attributes: list[AttributeSpecifier]
    constraint: Expression
    SINCE = cpp(2020)


class ExplicitInstantiation(Declaration):
    """`template declaration`, or with `extern` `extern template declaration` ([temp.explicit])."""

    extern: bool
    declaration: Declaration
    SINCE = cpp(1998)
    FEATURES = {"extern": {True: cpp(2011)}}


# === Preprocessing directives [cpp] ===


class IncludeDirective(Directive):
    """`#include <path>` with `system`, `#include "path"`, or `#include macro` ([cpp.include]); also `#include_next`
    and `#import`, which are extensions."""

    directive: IncludeKeyword
    path: str | None
    system: bool
    macro: Expression | None


class DefineDirective(Directive):
    """`#define name replacement`, or with `function_like` `#define name(parameters, ...) replacement` ([cpp.replace]).
    The replacement is the text of its tokens, which are not a tree until the macro is used."""

    name: Identifier
    function_like: bool
    parameters: list[Identifier]
    variadic: bool
    replacement: str | None


class IfDirective(Directive):
    """`#if condition items alternative #endif` ([cpp.cond])."""

    condition: Expression
    items: list[SyntaxNode]
    alternative: ElifDirective | ElifdefDirective | ElseDirective | None


class IfdefDirective(Directive):
    """`#ifdef name items alternative #endif`, or `#ifndef` with `negated` ([cpp.cond])."""

    negated: bool
    name: Identifier
    items: list[SyntaxNode]
    alternative: ElifDirective | ElifdefDirective | ElseDirective | None


class ElifDirective(Directive):
    """`#elif condition items alternative` ([cpp.cond])."""

    condition: Expression
    items: list[SyntaxNode]
    alternative: ElifDirective | ElifdefDirective | ElseDirective | None


class ElifdefDirective(Directive):
    """`#elifdef name items alternative`, or `#elifndef` with `negated` ([cpp.cond])."""

    negated: bool
    name: Identifier
    items: list[SyntaxNode]
    alternative: ElifDirective | ElifdefDirective | ElseDirective | None
    SINCE = both(2023, 2023)


class ElseDirective(Directive):
    """`#else items` ([cpp.cond])."""

    items: list[SyntaxNode]


class OtherDirective(Directive):
    """`#directive text` for every other directive: `#undef`, `#pragma`, `#error`, `#warning`, `#line`, `#embed`,
    `#ident` and the null directive `#` without a name ([cpp.pre])."""

    directive: str | None
    text: str | None

    def features(self) -> list[tuple[str, Availability]]:
        since = {"warning": both(2023, 2023), "embed": both(2026, 2023)}.get(self.directive or "")
        return [] if since is None else [(f"#{self.directive}", since)]


# --- Helpers ---


def binding(declarator: Declarator | None) -> tuple[IdDeclarator | StructuredBindingDeclarator | None, Declarator | None]:
    """The innermost declarator of `declarator`, which names what it declares, and the declarator binding that name
    most closely, parentheses aside: a `FunctionDeclarator` there declares a function (`int *f()`), and anything else
    an object (`int (*f)()`). The innermost is None for an abstract declarator."""
    binder: Declarator | None = None
    while declarator is not None and not isinstance(declarator, (IdDeclarator, StructuredBindingDeclarator)):
        if not isinstance(declarator, ParenthesizedDeclarator):
            binder = declarator
        declarator = declarator.declarator  # type: ignore[attr-defined]
    return declarator, binder


# --- The language ---

KINDS: list[type[SyntaxNode]] = [
    Comment, TranslationUnit,
    Identifier, OperatorName, ConversionName, LiteralOperatorName, DestructorName, TemplateId, QualifiedName,
    IntegerLiteral, FloatingLiteral, CharacterLiteral, StringLiteral, RawStringLiteral, UserDefinedLiteral,
    ConcatenatedString, BooleanLiteral, NullptrLiteral,
    ThisExpression, ParenthesizedExpression, IdExpression, LambdaExpression, LambdaDeclarator, DefaultCapture,
    SimpleCapture, ThisCapture, InitCapture, FoldExpression, RequiresExpression, SimpleRequirement, TypeRequirement,
    CompoundRequirement, NestedRequirement, PackIndexingExpression, ReflectExpression, SpliceExpression,
    SubscriptExpression, CallExpression, FunctionalCastExpression, MemberExpression, PostfixExpression,
    NamedCastExpression, TypeidExpression, UnaryExpression, AwaitExpression, SizeofExpression, SizeofPackExpression,
    AlignofExpression, NoexceptExpression, NewExpression, DeleteExpression, CastExpression, BinaryExpression,
    ConditionalExpression, AssignmentExpression, ThrowExpression, YieldExpression, PackExpansion, InitializerList,
    DesignatedInitializer, FieldDesignator, IndexDesignator, CompoundLiteralExpression, GenericSelection,
    GenericAssociation, StatementExpression, ExtensionExpression, DefinedExpression,
    LabeledStatement, CaseStatement, DefaultStatement, ExpressionStatement, CompoundStatement, IfStatement,
    SwitchStatement, WhileStatement, DoStatement, ForStatement, RangeForStatement, BreakStatement, ContinueStatement,
    ReturnStatement, CoReturnStatement, GotoStatement, TryStatement, Handler, AttributedStatement,
    ContractAssertStatement,
    SimpleDeclaration, InitDeclarator, FunctionDefinition, DefaultedBody, DeletedBody, MemberInitializer, VirtSpecifier,
    DeclSpecifier, ExplicitSpecifier, CvQualifier, PrimitiveTypeSpecifier, NamedTypeSpecifier, TypenameSpecifier,
    ClassSpecifier, MemberList, EnumSpecifier, EnumeratorList, Enumerator, DecltypeSpecifier, PlaceholderTypeSpecifier,
    TypeofSpecifier, AtomicTypeSpecifier, BitIntSpecifier, PackIndexingSpecifier, SpliceSpecifier,
    IdDeclarator, PackDeclarator, PointerDeclarator, ReferenceDeclarator, ArrayDeclarator, FunctionDeclarator,
    ParenthesizedDeclarator, StructuredBindingDeclarator, TypeId, ParameterDeclaration, EllipsisParameter,
    EqualInitializer, ParenthesizedInitializer, NoexceptSpecifier, ThrowSpecifier, PreconditionSpecifier,
    PostconditionSpecifier,
    NamespaceDefinition, NamespaceName, NamespaceAliasDefinition, UsingDirective, UsingDeclaration, UsingDeclarator,
    UsingEnumDeclaration, AliasDeclaration, StaticAssertDeclaration, AttributeDeclaration, EmptyDeclaration,
    LinkageSpecification, AsmDeclaration, AsmOperand,
    StandardAttributeSpecifier, Attribute, Annotation, AlignasSpecifier, GnuAttributeSpecifier, DeclspecSpecifier,
    ModuleDeclaration, GlobalModuleFragment, PrivateModuleFragment, ImportDeclaration, ExportDeclaration,
    AccessSpecifier, BaseSpecifier, FriendTypeDeclaration,
    TemplateDeclaration, TypeParameter, TemplateTemplateParameter, ConceptDefinition, ExplicitInstantiation,
    IncludeDirective, DefineDirective, IfDirective, IfdefDirective, ElifDirective, ElifdefDirective, ElseDirective,
    OtherDirective,
]

LANGUAGE = Language("Ccpp", KINDS, base={CPP: 1998, C: 1989})

__all__ += [k.__name__ for k in KINDS] + [
    "Name", "Expression", "Literal", "Statement", "Declaration", "Specifier", "Declarator", "Parameter",
    "TemplateParameter", "Initializer", "Capture", "Requirement", "Designator", "AttributeSpecifier",
    "ExceptionSpecification", "ContractSpecifier", "Directive", "cpp", "c", "both", "CPP", "C", "binding"]
