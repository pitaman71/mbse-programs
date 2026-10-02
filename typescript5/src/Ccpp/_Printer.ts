/**
 * Prints Ccpp trees as C and C++ source text, in one fixed layout.
 *
 * The layout: four spaces per level, braces on the line that opens them, one declaration or statement per line, and
 * labels, access specifiers and directives outdented. Parentheses written in the tree are printed; those a tree built
 * by hand needs are added, by precedence for expressions and by binding for declarators (`(*f)(int)`). The printer
 * assumes a valid tree: standards validate before they print.
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

const INDENT = "    ";
const indent = (depth: number) => INDENT.repeat(Math.max(depth, 0));

// Precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its place needs.
const COMMA = 0;
const ASSIGNMENT = 1;
const CONDITIONAL = 2;
const UNARY = 15;
const POSTFIX = 16;
const PRIMARY = 17;
const BINARY: Record<string, number> = {
  ",": COMMA, "||": 3, "&&": 4, "|": 5, "^": 6, "&": 7, "==": 8, "!=": 8, "<": 9, ">": 9, "<=": 9, ">=": 9, "<=>": 10,
  "<<": 11, ">>": 11, "+": 12, "-": 12, "*": 13, "/": 13, "%": 13, ".*": 14, "->*": 14,
};

const isAny = (node: unknown, kinds: Function[]) => kinds.some((k) => node instanceof k);

function precedence(node: unknown): number {
  if (node instanceof S.BinaryExpression) return BINARY[node.operator as string] as number;
  if (isAny(node, [S.AssignmentExpression, S.ThrowExpression, S.YieldExpression])) return ASSIGNMENT;
  if (node instanceof S.ConditionalExpression) return CONDITIONAL;
  if (isAny(node, [S.UnaryExpression, S.CastExpression, S.SizeofExpression, S.AlignofExpression, S.NewExpression,
    S.DeleteExpression, S.AwaitExpression, S.NoexceptExpression, S.ExtensionExpression, S.ReflectExpression,
    S.SizeofPackExpression])) return UNARY;
  if (isAny(node, [S.CallExpression, S.SubscriptExpression, S.MemberExpression, S.PostfixExpression,
    S.NamedCastExpression, S.TypeidExpression, S.FunctionalCastExpression, S.CompoundLiteralExpression,
    S.PackExpansion])) return POSTFIX;
  return PRIMARY;
}

/** Whether a declarator declares no name. */
function abstract(declarator: any): boolean {
  for (let d = declarator; d !== null; d = d.declarator) {
    if (d instanceof S.IdDeclarator || d instanceof S.StructuredBindingDeclarator) return false;
  }
  return true;
}

type StatementMethod = (self: Printer, node: any, depth: number, semicolon: boolean) => string;
type TextMethod = (self: Printer, node: any, depth: number) => string;

/** Prints any Ccpp syntax node: a translation unit as a file, anything else as the text it stands for. */
export class Printer {
  static STATEMENTS = new Map<Function, StatementMethod>();
  static TEXTS = new Map<Function, TextMethod>();

  print(node: SyntaxNode): string {
    if (node instanceof S.TranslationUnit) return this.lines(node.items, (i) => this.item(i, 0)).map((l) => l + "\n").join("");
    if (isAny(node, [S.Statement, S.Declaration, S.Directive, S.Comment])) return this.item(node, 0);
    return this.text(node, 0);
  }

  // Items: declarations, statements, directives and comments, each starting with its own indentation

  /** An item, starting with its indentation. Among `enumerators`, an enumerator ends with a comma. */
  item(node: any, depth: number, enumerators = false): string {
    if (node instanceof S.Directive) return this.directive(node, depth, enumerators);
    if (node instanceof S.Enumerator) return indent(depth) + this.enumerator(node, depth) + (enumerators ? "," : "");
    if (node instanceof S.Comment) return indent(depth) + this.comment(node);
    if (node instanceof S.AccessSpecifier) return indent(depth - 1) + `${node.access}:`;
    if (isAny(node, [S.CaseStatement, S.DefaultStatement, S.LabeledStatement])) return indent(depth - 1) + this.label(node, depth);
    return indent(depth) + this.statement(node, depth);
  }

  /** Each syntax node rendered on its own lines, but for trailing comments, which end the line before them. */
  lines(nodes: readonly any[], render: (node: any) => string): string[] {
    const out: string[] = [];
    for (const node of nodes) {
      if (node instanceof S.Comment && node.trailing && out.length > 0) out[out.length - 1] += " " + this.comment(node);
      else out.push(render(node));
    }
    return out;
  }

  /** Items, one per line; those after a case or default label until the next one are indented further. */
  items(nodes: readonly any[], depth: number): string {
    let labelled = false;
    return this.lines(nodes, (node) => {
      if (node instanceof S.CaseStatement || node instanceof S.DefaultStatement) {
        labelled = true;
        return this.item(node, depth + 1);
      }
      return this.item(node, labelled ? depth + 1 : depth);
    }).join("\n");
  }

  block(nodes: readonly any[], depth: number): string {
    if (nodes.length === 0) return "{}";
    return "{\n" + this.items(nodes, depth + 1) + "\n" + indent(depth) + "}";
  }

  comment(node: S.Comment): string {
    return node.block ? `/*${node.text}*/` : `//${node.text}`;
  }

  label(node: any, depth: number): string {
    let head: string;
    if (node instanceof S.CaseStatement) {
      head = `case ${this.expression(node.value, CONDITIONAL, depth)}`;
      if (node.last !== null) head += ` ... ${this.expression(node.last, CONDITIONAL, depth)}`;
    } else if (node instanceof S.DefaultStatement) {
      head = "default";
    } else {
      head = node.label.spelling;
    }
    const statement = node.statement;
    if (statement === null) return head + ":";
    if (statement instanceof S.CaseStatement || statement instanceof S.DefaultStatement) {
      return head + ":\n" + this.item(statement, depth);
    }
    if (statement instanceof S.CompoundStatement) return head + ": " + this.block(statement.items, depth - 1);
    return head + ":\n" + indent(depth) + this.statement(statement, depth);
  }

  // Directives

  directive(node: any, depth: number, enumerators = false): string {
    if (node instanceof S.IncludeDirective) {
      const target = node.macro !== null ? this.expression(node.macro, COMMA, depth)
        : node.system ? `<${node.path}>` : `"${node.path}"`;
      return `#${node.directive} ${target}`;
    }
    if (node instanceof S.DefineDirective) {
      let head = `#define ${node.name?.spelling}`;
      if (node.function_like) {
        head += "(" + [...node.parameters.map((p) => p.spelling), ...(node.variadic ? ["..."] : [])].join(", ") + ")";
      }
      return head + (node.replacement !== null ? ` ${node.replacement}` : "");
    }
    if (node instanceof S.OtherDirective) return "#" + (node.directive ?? "") + (node.text !== null ? ` ${node.text}` : "");
    return this.conditional(node, depth, enumerators) + "\n#endif";
  }

  conditional(node: any, depth: number, enumerators: boolean): string {
    let head: string;
    if (node instanceof S.IfDirective || node instanceof S.ElifDirective) {
      head = `#${node instanceof S.IfDirective ? "if" : "elif"} ${this.expression(node.condition, COMMA, depth)}`;
    } else if (node instanceof S.IfdefDirective || node instanceof S.ElifdefDirective) {
      head = `#${node instanceof S.IfdefDirective ? "if" : "elif"}${node.negated ? "ndef" : "def"} ${node.name?.spelling}`;
    } else {
      head = "#else";
    }
    const body = this.lines(node.items, (i) => this.item(i, depth, enumerators)).map((l) => "\n" + l).join("");
    const tail = node instanceof S.ElseDirective || node.alternative === null ? ""
      : "\n" + this.conditional(node.alternative, depth, enumerators);
    return head + body + tail;
  }

  // Statements and declarations, without their first line's indentation

  /** A statement or declaration; with `semicolon` false, a declaration without its `;`. */
  statement(node: any, depth: number, semicolon = true): string {
    return (Printer.STATEMENTS.get(node.constructor) as StatementMethod)(this, node, depth, semicolon);
  }

  /** A substatement: a block on the same line, anything else indented on the next. */
  sub(node: any, depth: number): string {
    if (node instanceof S.CompoundStatement) return " " + this.block(node.items, depth);
    return "\n" + this.item(node, depth + 1);
  }

  /** What separates a substatement from a following keyword (`else`, `while`). */
  after(node: any, depth: number): string {
    return node instanceof S.CompoundStatement ? " " : "\n" + indent(depth);
  }

  /** `(initializer condition)` of an if, switch or while. */
  head(initializer: any, condition: any, depth: number): string {
    const text = initializer !== null ? this.statement(initializer, depth) + " " : "";
    return `(${text}${this.condition(condition, depth)})`;
  }

  condition(node: any, depth: number): string {
    if (node instanceof S.Declaration) return this.statement(node, depth, false);
    return this.expression(node, COMMA, depth);
  }

  handlers(node: S.TryStatement, depth: number): string {
    return node.handlers.map((h) => ` catch (${this.text(h.parameter, depth)}) ${this.block((h.body as S.CompoundStatement).items, depth)}`).join("");
  }

  prefix(attributes: readonly SyntaxNode[], depth: number): string {
    return attributes.length > 0 ? this.attributes(attributes, depth) + " " : "";
  }

  specifiers(specifiers: readonly SyntaxNode[], depth: number): string {
    return specifiers.map((s) => this.text(s, depth)).join(" ");
  }

  /** Specifiers and a declarator: separated by a space, unless the declarator is abstract and starts with a pointer,
   * reference, bracket or parenthesis. */
  declared(specifiers: string, declarator: string, isAbstract: boolean): string {
    if (!specifiers || !declarator) return specifiers + declarator;
    if (declarator.startsWith("...")) return specifiers + "..." + (declarator.length > 3 ? " " + declarator.slice(3) : "");
    if (isAbstract && "*&[(".includes(declarator[0] as string)) return specifiers + declarator;
    return `${specifiers} ${declarator}`;
  }

  initDeclarator(node: S.InitDeclarator, depth: number): string {
    let text = node.declarator !== null ? this.declarator(node.declarator, depth) : "";
    text += node.virt_specifiers.map((v) => ` ${v.keyword}`).join("");
    if (node.pure) text += " = 0";
    if (node.bitfield !== null) text += (text ? " : " : ": ") + this.expression(node.bitfield, CONDITIONAL, depth);
    if (node.initializer !== null) text += this.initializer(node.initializer, depth);
    if (node.requires !== null) text += " requires " + this.constraint(node.requires, depth);
    return text + this.contracts(node.contracts, depth);
  }

  initializer(node: any, depth: number): string {
    if (node instanceof S.EqualInitializer) return " = " + this.expression(node.value, ASSIGNMENT, depth);
    if (node instanceof S.ParenthesizedInitializer) return "(" + this.list(node.arguments, depth) + ")";
    return this.expression(node, ASSIGNMENT, depth);
  }

  contracts(contracts: readonly SyntaxNode[], depth: number): string {
    return contracts.map((c) => " " + this.text(c, depth)).join("");
  }

  // Expressions

  /** `node` where an expression of at least `needed` precedence is needed, parenthesized if it binds less. */
  expression(node: any, needed: number, depth: number): string {
    const text = this.text(node, depth);
    return precedence(node) < needed ? `(${text})` : text;
  }

  /** A requires-clause: primary expressions joined by `&&` and `||`. */
  constraint(node: any, depth: number, needed = 3): string {
    if (node instanceof S.BinaryExpression && (node.operator === "&&" || node.operator === "||")) {
      const own = BINARY[node.operator] as number;
      const text = `${this.constraint(node.left, depth, own)} ${node.operator} ${this.constraint(node.right, depth, own + 1)}`;
      return own < needed ? `(${text})` : text;
    }
    return this.expression(node, PRIMARY, depth);
  }

  /** Arguments: expressions or types, separated by commas. */
  list(nodes: readonly SyntaxNode[], depth: number): string {
    return nodes.map((n) => (n instanceof S.TypeId ? this.text(n, depth) : this.expression(n, ASSIGNMENT, depth))).join(", ");
  }

  /** Template arguments, parenthesized where a `>` would end the list. */
  templateArguments(nodes: readonly SyntaxNode[], depth: number): string {
    return "<" + nodes.map((n) => {
      const text = n instanceof S.TypeId ? this.text(n, depth) : this.expression(n, CONDITIONAL, depth);
      return precedence(n) <= (BINARY[">"] as number) && text.includes(">") && !text.startsWith("(") ? `(${text})` : text;
    }).join(", ") + ">";
  }

  /** The text of any syntax node that is neither an item nor a statement: `item` and `statement` print those. */
  text(node: any, depth: number): string {
    return (Printer.TEXTS.get(node.constructor) as TextMethod)(this, node, depth);
  }

  keywordCall(keyword: string, operand: any, depth: number): string {
    if (operand instanceof S.TypeId) return `${keyword}(${this.text(operand, depth)})`;
    return `${keyword}(${this.expression(operand, COMMA, depth)})`;
  }

  initializerList(node: S.InitializerList, depth: number): string {
    const items = node.items.map((i) => (i instanceof S.DesignatedInitializer ? this.text(i, depth)
      : this.expression(i, ASSIGNMENT, depth)));
    return "{" + items.join(", ") + (node.trailing_comma ? "," : "") + "}";
  }

  literal(node: any, depth: number): string {
    if (node instanceof S.IntegerLiteral || node instanceof S.FloatingLiteral) return node.spelling as string;
    if (node instanceof S.CharacterLiteral) return `${node.prefix ?? ""}'${node.text}'`;
    if (node instanceof S.StringLiteral) return `${node.prefix ?? ""}"${node.text}"`;
    if (node instanceof S.RawStringLiteral) {
      const delimiter = node.delimiter ?? "";
      return `${node.prefix ?? ""}R"${delimiter}(${node.text})${delimiter}"`;
    }
    if (node instanceof S.UserDefinedLiteral) return this.literal(node.literal, depth) + node.suffix;
    if (node instanceof S.ConcatenatedString) return node.parts.map((p) => this.text(p, depth)).join(" ");
    if (node instanceof S.BooleanLiteral) return node.value ? "true" : "false";
    return "nullptr";
  }

  splice(node: any, depth: number): string {
    let text = node.typename_keyword === true ? "typename " : "";
    text += (node.template_keyword ? "template " : "") + `[: ${this.expression(node.reflection, COMMA, depth)} :]`;
    if (node.arguments.length > 0 || node.template_keyword) text += this.templateArguments(node.arguments, depth);
    return text;
  }

  /** A class body: members one level in, access specifiers at the class's level. */
  members(nodes: readonly SyntaxNode[], depth: number): string {
    if (nodes.length === 0) return "{}";
    return "{\n" + this.lines(nodes, (i) => this.item(i, depth + 1)).join("\n") + "\n" + indent(depth) + "}";
  }

  enumerators(node: S.EnumeratorList, depth: number): string {
    if (node.enumerators.length === 0) return "{}";
    let last = -1;
    node.enumerators.forEach((e, i) => { if (e instanceof S.Enumerator) last = i; });
    const render = (e: SyntaxNode) => {
      const text = this.item(e, depth + 1, true);
      return last >= 0 && e === node.enumerators[last] && !node.trailing_comma ? text.slice(0, -1) : text;
    };
    return "{\n" + this.lines(node.enumerators, render).join("\n") + "\n" + indent(depth) + "}";
  }

  enumerator(node: S.Enumerator, depth: number): string {
    const text = node.name?.spelling + this.attributesAfter(node.attributes, depth);
    return text + (node.value !== null ? ` = ${this.expression(node.value, CONDITIONAL, depth)}` : "");
  }

  // Declarators

  declarator(node: any, depth: number): string {
    if (node === null) return "";
    if (node instanceof S.IdDeclarator) return this.text(node.name, depth) + this.attributesAfter(node.attributes, depth);
    if (node instanceof S.PackDeclarator) return "..." + this.declarator(node.declarator, depth);
    if (node instanceof S.PointerDeclarator || node instanceof S.ReferenceDeclarator) {
      let text: string;
      let parts: string[];
      if (node instanceof S.PointerDeclarator) {
        text = node.scope !== null ? this.text(node.scope, depth) + "::*" : "*";
        parts = [...node.attributes.map((a) => this.text(a, depth)), ...node.qualifiers.map((q) => q.keyword as string)];
      } else {
        text = node.rvalue ? "&&" : "&";
        parts = node.attributes.map((a) => this.text(a, depth));
      }
      const inner = this.declarator(node.declarator, depth);
      return text + parts.join(" ") + (parts.length > 0 && inner ? " " + inner : inner);
    }
    if (node instanceof S.ParenthesizedDeclarator) return `(${this.declarator(node.declarator, depth)})`;
    if (node instanceof S.StructuredBindingDeclarator) {
      return "[" + node.bindings.map((b) => this.declarator(b, depth)).join(", ") + "]";
    }
    let inner = this.declarator(node.declarator, depth);
    if (node.declarator instanceof S.PointerDeclarator || node.declarator instanceof S.ReferenceDeclarator) inner = `(${inner})`;
    if (node instanceof S.ArrayDeclarator) {
      let inside = [...(node.static ? ["static"] : []), ...node.qualifiers.map((q) => q.keyword as string)].join(" ");
      const size = node.star ? "*" : node.size !== null ? this.expression(node.size, ASSIGNMENT, depth) : "";
      inside = inside && size ? inside + " " + size : inside + size;
      return inner + `[${inside}]` + this.attributesAfter(node.attributes, depth);
    }
    let text = inner + "(" + node.parameters.map((p: SyntaxNode) => this.text(p, depth)).join(", ") + ")";
    text += node.qualifiers.map((q: S.CvQualifier) => " " + q.keyword).join("");
    if (node.ref_qualifier !== null) text += " " + node.ref_qualifier;
    if (node.exception !== null) text += " " + this.text(node.exception, depth);
    text += this.attributesAfter(node.attributes, depth);
    if (node.trailing_return !== null) text += " -> " + this.text(node.trailing_return, depth);
    return text;
  }

  // Attributes

  attributes(nodes: readonly SyntaxNode[], depth: number): string {
    return nodes.map((a) => this.text(a, depth)).join(" ");
  }

  attributesAfter(nodes: readonly SyntaxNode[], depth: number): string {
    return nodes.map((a) => " " + this.text(a, depth)).join("");
  }
}

const P = Printer.STATEMENTS;
const T = Printer.TEXTS;
const label: StatementMethod = (self, node, depth) => self.label(node, depth);

P.set(S.ExpressionStatement, (self, node: S.ExpressionStatement, depth) =>
  (node.expression !== null ? self.expression(node.expression, COMMA, depth) : "") + ";");
P.set(S.CompoundStatement, (self, node: S.CompoundStatement, depth) => self.block(node.items, depth));
P.set(S.IfStatement, (self, node: S.IfStatement, depth) => {
  let text = node.consteval ? "if " + (node.negated ? "!" : "") + "consteval"
    : "if " + (node.constexpr ? "constexpr " : "") + self.head(node.initializer, node.condition, depth);
  text += self.sub(node.consequence, depth);
  if (node.alternative !== null) {
    text += self.after(node.consequence, depth) + "else";
    text += node.alternative instanceof S.IfStatement ? " " + self.statement(node.alternative, depth)
      : self.sub(node.alternative, depth);
  }
  return text;
});
P.set(S.SwitchStatement, (self, node: S.SwitchStatement, depth) =>
  "switch " + self.head(node.initializer, node.condition, depth) + self.sub(node.body, depth));
P.set(S.WhileStatement, (self, node: S.WhileStatement, depth) =>
  "while " + self.head(null, node.condition, depth) + self.sub(node.body, depth));
P.set(S.DoStatement, (self, node: S.DoStatement, depth) => "do" + self.sub(node.body, depth)
  + self.after(node.body, depth) + `while (${self.expression(node.condition, COMMA, depth)});`);
P.set(S.ForStatement, (self, node: S.ForStatement, depth) => {
  let text = "for (" + (node.initializer !== null ? self.statement(node.initializer, depth) : ";");
  if (node.condition !== null) text += " " + self.condition(node.condition, depth);
  text += ";";
  if (node.increment !== null) text += " " + self.expression(node.increment, COMMA, depth);
  return text + ")" + self.sub(node.body, depth);
});
P.set(S.RangeForStatement, (self, node: S.RangeForStatement, depth) => {
  let text = (node.template_keyword ? "template " : "") + "for (";
  if (node.initializer !== null) text += self.statement(node.initializer, depth) + " ";
  text += self.statement(node.declaration, depth, false) + " : " + self.expression(node.range, COMMA, depth);
  return text + ")" + self.sub(node.body, depth);
});
const jump: StatementMethod = (self, node, depth) => {
  if (node instanceof S.BreakStatement) return "break;";
  if (node instanceof S.ContinueStatement) return "continue;";
  if (node instanceof S.GotoStatement) return `goto ${node.label?.spelling};`;
  const keyword = node instanceof S.ReturnStatement ? "return" : "co_return";
  return keyword + (node.value !== null ? " " + self.expression(node.value, COMMA, depth) : "") + ";";
};
for (const k of [S.BreakStatement, S.ContinueStatement, S.ReturnStatement, S.CoReturnStatement, S.GotoStatement]) P.set(k, jump);
P.set(S.TryStatement, (self, node: S.TryStatement, depth) =>
  "try " + self.block((node.body as S.CompoundStatement).items, depth) + self.handlers(node, depth));
P.set(S.AttributedStatement, (self, node: S.AttributedStatement, depth) => {
  const statement = self.statement(node.statement, depth);
  return self.attributes(node.attributes, depth) + (statement === ";" ? "" : " ") + statement;
});
P.set(S.ContractAssertStatement, (self, node: S.ContractAssertStatement, depth) => "contract_assert"
  + self.attributesAfter(node.attributes, depth) + `(${self.expression(node.predicate, COMMA, depth)});`);
for (const k of [S.LabeledStatement, S.CaseStatement, S.DefaultStatement]) P.set(k, label);
P.set(S.SimpleDeclaration, (self, node: S.SimpleDeclaration, depth, semicolon) => {
  const declarators = node.declarators.map((d) => self.initDeclarator(d, depth)).join(", ");
  return self.prefix(node.attributes, depth) + self.declared(self.specifiers(node.specifiers, depth), declarators, false)
    + (semicolon ? ";" : "");
});
P.set(S.FunctionDefinition, (self, node: S.FunctionDefinition, depth) => {
  let text = self.prefix(node.attributes, depth)
    + self.declared(self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth), false);
  text += node.virt_specifiers.map((v) => ` ${v.keyword}`).join("");
  if (node.requires !== null) text += " requires " + self.constraint(node.requires, depth);
  text += self.contracts(node.contracts, depth);
  const initializers = node.initializers.length > 0 ? " : " + node.initializers.map((i) => self.text(i, depth)).join(", ") : "";
  const body = node.body;
  if (body instanceof S.TryStatement) {
    return text + " try" + initializers + " " + self.block((body.body as S.CompoundStatement).items, depth)
      + self.handlers(body, depth);
  }
  if (body instanceof S.DefaultedBody) return text + initializers + " = default;";
  if (body instanceof S.DeletedBody) {
    const reason = body.reason !== null ? `(${self.expression(body.reason, ASSIGNMENT, depth)})` : "";
    return text + initializers + ` = delete${reason};`;
  }
  return text + initializers + " " + self.block((body as S.CompoundStatement).items, depth);
});
P.set(S.TemplateDeclaration, (self, node: S.TemplateDeclaration, depth) => {
  let text = "template <" + node.parameters.map((p) => self.text(p, depth)).join(", ") + ">";
  if (node.requires !== null) text += " requires " + self.constraint(node.requires, depth);
  return text + "\n" + indent(depth) + self.statement(node.declaration, depth);
});
P.set(S.ExplicitInstantiation, (self, node: S.ExplicitInstantiation, depth) =>
  (node.extern ? "extern " : "") + "template " + self.statement(node.declaration, depth));
P.set(S.NamespaceDefinition, (self, node: S.NamespaceDefinition, depth) => {
  let text = (node.inline ? "inline " : "") + "namespace" + node.attributes.map((a) => " " + self.text(a, depth)).join("");
  if (node.names.length > 0) text += " " + node.names.map((n) => (n.inline ? "inline " : "") + n.name?.spelling).join("::");
  return text + " " + self.block(node.items, depth);
});
P.set(S.NamespaceAliasDefinition, (self, node: S.NamespaceAliasDefinition, depth) =>
  `namespace ${node.name?.spelling} = ${self.text(node.target, depth)};`);
P.set(S.UsingDirective, (self, node: S.UsingDirective, depth) =>
  self.prefix(node.attributes, depth) + `using namespace ${self.text(node.name, depth)};`);
P.set(S.UsingDeclaration, (self, node: S.UsingDeclaration, depth) =>
  "using " + node.declarators.map((d) => self.text(d, depth)).join(", ") + ";");
P.set(S.UsingEnumDeclaration, (self, node: S.UsingEnumDeclaration, depth) => `using enum ${self.text(node.type, depth)};`);
P.set(S.AliasDeclaration, (self, node: S.AliasDeclaration, depth) =>
  `using ${node.name?.spelling}` + self.attributesAfter(node.attributes, depth) + ` = ${self.text(node.type, depth)};`);
P.set(S.StaticAssertDeclaration, (self, node: S.StaticAssertDeclaration, depth) => {
  const message = node.message !== null ? ", " + self.expression(node.message, ASSIGNMENT, depth) : "";
  return `${node.keyword}(${self.expression(node.condition, ASSIGNMENT, depth)}${message});`;
});
P.set(S.AttributeDeclaration, (self, node: S.AttributeDeclaration, depth) => self.attributes(node.attributes, depth) + ";");
P.set(S.EmptyDeclaration, () => ";");
P.set(S.LinkageSpecification, (self, node: S.LinkageSpecification, depth) => {
  const head = `extern "${node.language}" `;
  return node.braced ? head + self.block(node.items, depth) : head + self.statement(node.items[0], depth);
});
P.set(S.AsmDeclaration, (self, node: S.AsmDeclaration, depth) => {
  let text = self.prefix(node.attributes, depth) + node.keyword;
  text += (["volatile", "inline", "goto"] as const).filter((q) => node[q]).map((q) => ` ${q}`).join("");
  const sections = [node.outputs.map((o) => self.text(o, depth)).join(", "), node.inputs.map((o) => self.text(o, depth)).join(", "),
    node.clobbers.map((c) => self.expression(c, ASSIGNMENT, depth)).join(", "), node.labels.map((l) => l.spelling).join(", ")];
  while (sections.length > 0 && !sections[sections.length - 1]) sections.pop();
  const inner = self.expression(node.template, ASSIGNMENT, depth) + sections.map((s) => " :" + (s ? ` ${s}` : "")).join("");
  return `${text}(${inner});`;
});
const module: StatementMethod = (self, node, depth) => {
  if (node instanceof S.GlobalModuleFragment) return "module;";
  if (node instanceof S.PrivateModuleFragment) return "module :private;";
  let text = node.export ? "export " : "";
  const partition = node.partition !== null ? `:${node.partition}` : "";
  if (node instanceof S.ModuleDeclaration) text += "module " + node.name + partition;
  else if (node.header !== null) text += "import " + (node.system ? `<${node.header}>` : `"${node.header}"`);
  else text += "import " + (node.name ?? "") + partition;
  return text + self.attributesAfter(node.attributes, depth) + ";";
};
for (const k of [S.ModuleDeclaration, S.GlobalModuleFragment, S.PrivateModuleFragment, S.ImportDeclaration]) P.set(k, module);
P.set(S.ExportDeclaration, (self, node: S.ExportDeclaration, depth) =>
  "export " + (node.braced ? self.block(node.items, depth) : self.statement(node.items[0], depth)));
P.set(S.ConceptDefinition, (self, node: S.ConceptDefinition, depth) => `concept ${node.name?.spelling}`
  + self.attributesAfter(node.attributes, depth) + ` = ${self.expression(node.constraint, CONDITIONAL, depth)};`);
P.set(S.FriendTypeDeclaration, (self, node: S.FriendTypeDeclaration, depth) =>
  "friend " + node.types.map((t) => self.text(t, depth)).join(", ") + ";");

const name: TextMethod = (self, node, depth) => {
  if (node instanceof S.Identifier) return node.spelling as string;
  if (node instanceof S.OperatorName) return "operator" + (/^[a-z]/i.test(node.operator as string) ? " " : "") + node.operator;
  if (node instanceof S.ConversionName) return "operator " + self.text(node.type, depth);
  if (node instanceof S.LiteralOperatorName) return `operator""${node.suffix}`;
  if (node instanceof S.DestructorName) return "~" + self.text(node.type, depth);
  if (node instanceof S.TemplateId) {
    return (node.template_keyword ? "template " : "") + self.text(node.name, depth) + self.templateArguments(node.arguments, depth);
  }
  return (node.global_scope ? "::" : "") + node.qualifiers.map((q: SyntaxNode) => self.text(q, depth) + "::").join("")
    + self.text(node.name, depth);
};
for (const k of [S.Identifier, S.OperatorName, S.ConversionName, S.LiteralOperatorName, S.DestructorName, S.TemplateId,
  S.QualifiedName]) T.set(k, name);
for (const k of [S.IntegerLiteral, S.FloatingLiteral, S.CharacterLiteral, S.StringLiteral, S.RawStringLiteral,
  S.UserDefinedLiteral, S.ConcatenatedString, S.BooleanLiteral, S.NullptrLiteral]) T.set(k, (self, node, depth) => self.literal(node, depth));
T.set(S.ThisExpression, () => "this");
T.set(S.ParenthesizedExpression, (self, node, depth) => `(${self.expression(node.expression, COMMA, depth)})`);
T.set(S.IdExpression, (self, node, depth) => self.text(node.name, depth));
T.set(S.LambdaExpression, (self, node: S.LambdaExpression, depth) => {
  let text = "[" + node.captures.map((c) => self.text(c, depth)).join(", ") + "]";
  if (node.template_parameters.length > 0) text += "<" + node.template_parameters.map((p) => self.text(p, depth)).join(", ") + ">";
  if (node.template_requires !== null) text += " requires " + self.constraint(node.template_requires, depth);
  text += self.attributesAfter(node.attributes, depth);
  if (node.declarator !== null) text += (node.template_requires !== null ? " " : "") + self.text(node.declarator, depth);
  return text + " " + self.block((node.body as S.CompoundStatement).items, depth);
});
T.set(S.LambdaDeclarator, (self, node: S.LambdaDeclarator, depth) => {
  let text = "(" + node.parameters.map((p) => self.text(p, depth)).join(", ") + ")";
  text += node.specifiers.map((s) => " " + s.keyword).join("");
  if (node.exception !== null) text += " " + self.text(node.exception, depth);
  text += self.attributesAfter(node.attributes, depth);
  if (node.trailing_return !== null) text += " -> " + self.text(node.trailing_return, depth);
  if (node.requires !== null) text += " requires " + self.constraint(node.requires, depth);
  return text + self.contracts(node.contracts, depth);
});
const capture: TextMethod = (self, node, depth) => {
  if (node instanceof S.DefaultCapture) return node.mode as string;
  if (node instanceof S.ThisCapture) return node.copy ? "*this" : "this";
  const reference = node.by_reference ? "&" : "";
  if (node instanceof S.SimpleCapture) return reference + node.name?.spelling + (node.pack ? "..." : "");
  return reference + (node.pack ? "..." : "") + node.name.spelling + self.initializer(node.initializer, depth);
};
for (const k of [S.DefaultCapture, S.SimpleCapture, S.ThisCapture, S.InitCapture]) T.set(k, capture);
T.set(S.FoldExpression, (self, node: S.FoldExpression, depth) => {
  const left = node.left !== null ? self.expression(node.left, UNARY, depth) + ` ${node.operator} ` : "";
  const right = node.right !== null ? ` ${node.operator} ` + self.expression(node.right, UNARY, depth) : "";
  return `(${left}...${right})`;
});
T.set(S.RequiresExpression, (self, node: S.RequiresExpression, depth) => {
  let text = "requires ";
  if (node.parameters.length > 0) text += "(" + node.parameters.map((p) => self.text(p, depth)).join(", ") + ") ";
  if (node.requirements.length === 0) return text + "{}";
  return text + "{ " + node.requirements.map((r) => self.text(r, depth)).join(" ") + " }";
});
const requirement: TextMethod = (self, node, depth) => {
  if (node instanceof S.SimpleRequirement) return self.expression(node.expression, COMMA, depth) + ";";
  if (node instanceof S.TypeRequirement) return `typename ${self.text(node.name, depth)};`;
  if (node instanceof S.NestedRequirement) return `requires ${self.constraint(node.constraint, depth)};`;
  let text = "{ " + self.expression(node.expression, COMMA, depth) + " }";
  if (node.noexcept) text += " noexcept";
  if (node.return_type !== null) text += " -> " + self.text(node.return_type, depth);
  return text + ";";
};
for (const k of [S.SimpleRequirement, S.TypeRequirement, S.CompoundRequirement, S.NestedRequirement]) T.set(k, requirement);
T.set(S.PackIndexingExpression, (self, node, depth) =>
  `${self.text(node.pack, depth)}...[${self.expression(node.index, CONDITIONAL, depth)}]`);
T.set(S.ReflectExpression, (self, node, depth) => "^^" + (node.operand === null ? "::"
  : node.operand instanceof S.Expression ? self.expression(node.operand, UNARY, depth) : self.text(node.operand, depth)));
T.set(S.SpliceExpression, (self, node, depth) => self.splice(node, depth));
T.set(S.SubscriptExpression, (self, node: S.SubscriptExpression, depth) => self.expression(node.object, POSTFIX, depth)
  + "[" + node.indices.map((i) => self.expression(i, ASSIGNMENT, depth)).join(", ") + "]");
T.set(S.CallExpression, (self, node: S.CallExpression, depth) =>
  self.expression(node.function, POSTFIX, depth) + "(" + self.list(node.arguments, depth) + ")");
T.set(S.FunctionalCastExpression, (self, node, depth) => self.text(node.type, depth) + self.initializer(node.initializer, depth));
T.set(S.MemberExpression, (self, node: S.MemberExpression, depth) => self.expression(node.object, POSTFIX, depth)
  + node.operator + (node.template_keyword ? "template " : "") + self.text(node.member, depth));
T.set(S.PostfixExpression, (self, node, depth) => self.expression(node.operand, POSTFIX, depth) + node.operator);
T.set(S.NamedCastExpression, (self, node, depth) =>
  `${node.operator}<${self.text(node.type, depth)}>(${self.expression(node.operand, COMMA, depth)})`);
T.set(S.TypeidExpression, (self, node, depth) => self.keywordCall("typeid", node.operand, depth));
T.set(S.UnaryExpression, (self, node: S.UnaryExpression, depth) => {
  const operand = self.expression(node.operand, UNARY, depth);
  const first = operand.slice(0, 1);
  const space = ["+", "-", "&", "*"].includes(first) && first === (node.operator as string).slice(-1) ? " " : "";
  return node.operator + space + operand;
});
T.set(S.AwaitExpression, (self, node, depth) => "co_await " + self.expression(node.operand, UNARY, depth));
T.set(S.SizeofExpression, (self, node, depth) => {
  if (node.operand instanceof S.TypeId) return `sizeof(${self.text(node.operand, depth)})`;
  const operand = self.expression(node.operand, UNARY, depth);
  return "sizeof" + (operand.startsWith("(") ? "" : " ") + operand;
});
T.set(S.SizeofPackExpression, (_self, node) => `sizeof...(${node.pack.spelling})`);
T.set(S.AlignofExpression, (self, node, depth) => self.keywordCall(node.keyword, node.operand, depth));
T.set(S.NoexceptExpression, (self, node, depth) => self.keywordCall("noexcept", node.operand, depth));
T.set(S.NewExpression, (self, node: S.NewExpression, depth) => {
  let text = (node.global_scope ? "::" : "") + "new ";
  if (node.placement.length > 0) text += "(" + self.list(node.placement, depth) + ") ";
  const type = self.text(node.type, depth);
  text += node.parenthesized_type ? `(${type})` : type;
  return text + (node.initializer !== null ? self.initializer(node.initializer, depth) : "");
});
T.set(S.DeleteExpression, (self, node, depth) => (node.global_scope ? "::" : "") + "delete" + (node.array ? "[]" : "")
  + " " + self.expression(node.operand, UNARY, depth));
T.set(S.CastExpression, (self, node, depth) => `(${self.text(node.type, depth)})${self.expression(node.operand, UNARY, depth)}`);
T.set(S.BinaryExpression, (self, node: S.BinaryExpression, depth) => {
  const own = BINARY[node.operator as string] as number;
  const left = self.expression(node.left, own, depth);
  const right = self.expression(node.right, own + 1, depth);
  if (node.operator === ".*" || node.operator === "->*") return left + node.operator + right;
  if (node.operator === ",") return `${left}, ${right}`;
  return `${left} ${node.operator} ${right}`;
});
T.set(S.ConditionalExpression, (self, node: S.ConditionalExpression, depth) => {
  const condition = self.expression(node.condition, BINARY["||"] as number, depth);
  const alternative = self.expression(node.alternative, ASSIGNMENT, depth);
  if (node.consequence === null) return `${condition} ?: ${alternative}`;
  return `${condition} ? ${self.expression(node.consequence, COMMA, depth)} : ${alternative}`;
});
T.set(S.AssignmentExpression, (self, node, depth) =>
  `${self.expression(node.left, BINARY["||"] as number, depth)} ${node.operator} ${self.expression(node.right, ASSIGNMENT, depth)}`);
T.set(S.ThrowExpression, (self, node, depth) => "throw" + (node.operand !== null ? " " + self.expression(node.operand, ASSIGNMENT, depth) : ""));
T.set(S.YieldExpression, (self, node, depth) => "co_yield " + self.expression(node.operand, ASSIGNMENT, depth));
T.set(S.PackExpansion, (self, node, depth) => (node.pattern instanceof S.TypeId ? self.text(node.pattern, depth)
  : self.expression(node.pattern, POSTFIX, depth)) + "...");
T.set(S.InitializerList, (self, node, depth) => self.initializerList(node, depth));
T.set(S.DesignatedInitializer, (self, node: S.DesignatedInitializer, depth) =>
  node.designators.map((d) => self.text(d, depth)).join("") + self.initializer(node.initializer, depth));
const designator: TextMethod = (self, node, depth) => {
  if (node instanceof S.FieldDesignator) return "." + node.name?.spelling;
  const last = node.last !== null ? ` ... ${self.expression(node.last, CONDITIONAL, depth)}` : "";
  return `[${self.expression(node.index, CONDITIONAL, depth)}${last}]`;
};
T.set(S.FieldDesignator, designator);
T.set(S.IndexDesignator, designator);
T.set(S.CompoundLiteralExpression, (self, node, depth) => `(${self.text(node.type, depth)})${self.initializerList(node.initializer, depth)}`);
T.set(S.GenericSelection, (self, node: S.GenericSelection, depth) => {
  const controlling = node.controlling instanceof S.TypeId ? self.text(node.controlling, depth)
    : self.expression(node.controlling, ASSIGNMENT, depth);
  const associations = node.associations.map((a) => self.text(a, depth));
  return `_Generic(${[controlling, ...associations].join(", ")})`;
});
T.set(S.StatementExpression, (self, node, depth) => `(${self.block(node.body.items, depth)})`);
T.set(S.ExtensionExpression, (self, node, depth) => "__extension__ " + self.expression(node.operand, UNARY, depth));
T.set(S.DefinedExpression, (_self, node) => `defined(${node.name.spelling})`);
for (const k of [S.DeclSpecifier, S.CvQualifier, S.PrimitiveTypeSpecifier]) T.set(k, (_self, node) => node.keyword);
T.set(S.ExplicitSpecifier, (self, node, depth) => "explicit"
  + (node.condition !== null ? `(${self.expression(node.condition, COMMA, depth)})` : ""));
T.set(S.NamedTypeSpecifier, (self, node, depth) => self.text(node.name, depth));
T.set(S.TypenameSpecifier, (self, node, depth) => "typename " + self.text(node.name, depth));
T.set(S.DecltypeSpecifier, (self, node, depth) => `decltype(${self.expression(node.expression, COMMA, depth)})`);
T.set(S.PlaceholderTypeSpecifier, (self, node, depth) =>
  (node.constraint !== null ? self.text(node.constraint, depth) + " " : "") + (node.decltype ? "decltype(auto)" : "auto"));
T.set(S.TypeofSpecifier, (self, node, depth) => self.keywordCall(node.keyword, node.operand, depth));
T.set(S.AtomicTypeSpecifier, (self, node, depth) => `_Atomic(${self.text(node.type, depth)})`);
T.set(S.BitIntSpecifier, (self, node, depth) => `_BitInt(${self.expression(node.width, ASSIGNMENT, depth)})`);
T.set(S.PackIndexingSpecifier, (self, node, depth) => `${self.text(node.pack, depth)}...[${self.expression(node.index, CONDITIONAL, depth)}]`);
T.set(S.SpliceSpecifier, (self, node, depth) => self.splice(node, depth));
T.set(S.ClassSpecifier, (self, node: S.ClassSpecifier, depth) => {
  let text = node.key + self.attributesAfter(node.attributes, depth);
  if (node.name !== null) text += " " + self.text(node.name, depth);
  if (node.final) text += " final";
  if (node.bases.length > 0) text += " : " + node.bases.map((b) => self.text(b, depth)).join(", ");
  if (node.body !== null) text += " " + self.members(node.body.items, depth);
  return text;
});
T.set(S.EnumSpecifier, (self, node: S.EnumSpecifier, depth) => {
  let text = node.key + self.attributesAfter(node.attributes, depth);
  if (node.name !== null) text += " " + self.text(node.name, depth);
  if (node.base !== null) text += " : " + self.text(node.base, depth);
  if (node.body !== null) text += " " + self.enumerators(node.body, depth);
  return text;
});
T.set(S.BaseSpecifier, (self, node: S.BaseSpecifier, depth) => {
  const parts = node.attributes.length > 0 ? [self.attributes(node.attributes, depth)] : [];
  if (node.virtual) parts.push("virtual");
  if (node.access !== null) parts.push(node.access);
  parts.push(self.text(node.type, depth) + (node.pack ? "..." : ""));
  return parts.join(" ");
});
for (const k of [S.IdDeclarator, S.PackDeclarator, S.PointerDeclarator, S.ReferenceDeclarator, S.ArrayDeclarator,
  S.FunctionDeclarator, S.ParenthesizedDeclarator, S.StructuredBindingDeclarator]) T.set(k, (self, node, depth) => self.declarator(node, depth));
T.set(S.TypeId, (self, node: S.TypeId, depth) =>
  self.declared(self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth), true));
const parameter: TextMethod = (self, node, depth) => {
  if (node instanceof S.EllipsisParameter) return "...";
  let text = self.prefix(node.attributes, depth) + (node.this_keyword ? "this " : "");
  text += self.declared(self.specifiers(node.specifiers, depth), self.declarator(node.declarator, depth), abstract(node.declarator));
  return text + (node.default !== null ? ` = ${self.expression(node.default, ASSIGNMENT, depth)}` : "");
};
T.set(S.ParameterDeclaration, parameter);
T.set(S.EllipsisParameter, parameter);
const templateParameter: TextMethod = (self, node, depth) => {
  let text: string;
  if (node instanceof S.TypeParameter) {
    text = node.constraint !== null ? self.text(node.constraint, depth) : node.key ?? "typename";
  } else {
    text = "template <" + node.parameters.map((p: SyntaxNode) => self.text(p, depth)).join(", ") + ">";
    if (node.requires !== null) text += " requires " + self.constraint(node.requires, depth);
    text += " " + node.key;
  }
  text += node.pack ? "..." : "";
  if (node.name !== null) text += " " + node.name.spelling;
  if (node.default !== null) text += " = " + self.text(node.default, depth);
  return text;
};
T.set(S.TypeParameter, templateParameter);
T.set(S.TemplateTemplateParameter, templateParameter);
const exception: TextMethod = (self, node, depth) => {
  if (node instanceof S.NoexceptSpecifier) {
    return "noexcept" + (node.condition !== null ? `(${self.expression(node.condition, COMMA, depth)})` : "");
  }
  return "throw(" + node.types.map((t: SyntaxNode) => self.text(t, depth)).join(", ") + ")";
};
T.set(S.NoexceptSpecifier, exception);
T.set(S.ThrowSpecifier, exception);
const contract: TextMethod = (self, node, depth) => {
  if (node instanceof S.PreconditionSpecifier) {
    return "pre" + self.attributesAfter(node.attributes, depth) + `(${self.expression(node.predicate, COMMA, depth)})`;
  }
  const result = node.result !== null ? `${node.result.spelling}: ` : "";
  return "post" + self.attributesAfter(node.attributes, depth) + `(${result}${self.expression(node.predicate, COMMA, depth)})`;
};
T.set(S.PreconditionSpecifier, contract);
T.set(S.PostconditionSpecifier, contract);
const attributeSpecifier: TextMethod = (self, node, depth) => {
  if (node instanceof S.StandardAttributeSpecifier) {
    const using = node.using_namespace !== null ? `using ${node.using_namespace}: ` : "";
    return "[[" + using + node.attributes.map((a) => self.text(a, depth)).join(", ") + "]]";
  }
  if (node instanceof S.AlignasSpecifier) {
    const operand = self.keywordCall(node.keyword as string, node.operand, depth);
    return node.pack ? operand.slice(0, -1) + "...)" : operand;
  }
  if (node instanceof S.GnuAttributeSpecifier) return node.keyword + "((" + node.attributes.map((a) => self.text(a, depth)).join(", ") + "))";
  return "__declspec(" + node.attributes.map((a: SyntaxNode) => self.text(a, depth)).join(" ") + ")";
};
for (const k of [S.StandardAttributeSpecifier, S.AlignasSpecifier, S.GnuAttributeSpecifier, S.DeclspecSpecifier]) T.set(k, attributeSpecifier);
T.set(S.Attribute, (self, node: S.Attribute, depth) => (node.namespace !== null ? `${node.namespace}::` : "") + node.name
  + (node.arguments.length > 0 ? "(" + self.list(node.arguments, depth) + ")" : "") + (node.pack ? "..." : ""));
T.set(S.Annotation, (self, node, depth) => "=" + self.expression(node.value, ASSIGNMENT, depth) + (node.pack ? "..." : ""));
T.set(S.InitDeclarator, (self, node, depth) => self.initDeclarator(node, depth));
T.set(S.MemberInitializer, (self, node, depth) => self.text(node.member, depth) + self.initializer(node.initializer, depth)
  + (node.pack ? "..." : ""));
T.set(S.VirtSpecifier, (_self, node) => node.keyword);
T.set(S.DefaultedBody, () => "= default;");
T.set(S.DeletedBody, (self, node, depth) => "= delete" + (node.reason !== null ? `(${self.expression(node.reason, ASSIGNMENT, depth)})` : "") + ";");
T.set(S.MemberList, (self, node, depth) => self.members(node.items, depth));
T.set(S.EnumeratorList, (self, node, depth) => self.enumerators(node, depth));
T.set(S.Enumerator, (self, node, depth) => self.enumerator(node, depth));
T.set(S.NamespaceName, (_self, node) => (node.inline ? "inline " : "") + node.name.spelling);
T.set(S.UsingDeclarator, (self, node, depth) => (node.typename_keyword ? "typename " : "") + self.text(node.name, depth)
  + (node.pack ? "..." : ""));
T.set(S.Handler, (self, node, depth) => `catch (${self.text(node.parameter, depth)}) ${self.block(node.body.items, depth)}`);
T.set(S.AsmOperand, (self, node, depth) => (node.name !== null ? `[${node.name.spelling}] ` : "")
  + self.expression(node.constraint, ASSIGNMENT, depth) + ` (${self.expression(node.value, COMMA, depth)})`);
T.set(S.GenericAssociation, (self, node, depth) => (node.type !== null ? self.text(node.type, depth) : "default") + ": "
  + self.expression(node.value, ASSIGNMENT, depth));
for (const k of [S.EqualInitializer, S.ParenthesizedInitializer]) T.set(k, (self, node, depth) => self.initializer(node, depth).trimStart());
