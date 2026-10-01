/**
 * Prints TypeScript trees as TypeScript or JavaScript source text, in one fixed layout.
 *
 * The layout: four spaces per level, braces on the line that opens them, one statement or member per line, and a
 * semicolon after every statement that takes one. Parentheses written in the tree are printed; those a tree built by
 * hand needs are added, by the precedence of the grammar: for expressions, also where `??` meets `||` or `&&`, where a
 * statement would start with `{`, `function`, `class` or `let [`, and where an arrow's body is an object; for types,
 * where a function, conditional or union type is an operand. The printer assumes a valid tree: standards validate
 * before they print.
 */

import * as S from "./Syntax.js";

const INDENT = "    ";

// Expressions' precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its
// place needs. `new` is printed with its arguments, so it binds as a member does.
const SEQUENCE = 0, ASSIGN = 1, CONDITIONAL = 2, COALESCE = 3, OR = 4, AND = 5, BOR = 6, BXOR = 7, BAND = 8,
  EQUALITY = 9, RELATIONAL = 10, SHIFT = 11, ADD = 12, MULTIPLY = 13, POWER = 14, UNARY = 15, POSTFIX = 16, NEW = 17,
  MEMBER = 18, PRIMARY = 19;
const BINARY: Record<string, number> = {
  "==": EQUALITY, "!=": EQUALITY, "===": EQUALITY, "!==": EQUALITY, "<": RELATIONAL, "<=": RELATIONAL,
  ">": RELATIONAL, ">=": RELATIONAL, in: RELATIONAL, instanceof: RELATIONAL, "<<": SHIFT, ">>": SHIFT, ">>>": SHIFT,
  "+": ADD, "-": ADD, "*": MULTIPLY, "/": MULTIPLY, "%": MULTIPLY, "**": POWER, "|": BOR, "^": BXOR, "&": BAND,
  "&&": AND, "||": OR, "??": COALESCE,
};
const PRECEDENCE = new Map<Function, number>([
  [S.SequenceExpression, SEQUENCE], [S.AssignmentExpression, ASSIGN], [S.ArrowFunctionExpression, ASSIGN],
  [S.YieldExpression, ASSIGN], [S.ConditionalExpression, CONDITIONAL], [S.TSAsExpression, RELATIONAL],
  [S.TSSatisfiesExpression, RELATIONAL], [S.UnaryExpression, UNARY], [S.AwaitExpression, UNARY],
  [S.TSTypeAssertion, UNARY], [S.UpdateExpression, POSTFIX], [S.TSNonNullExpression, MEMBER],
  [S.NewExpression, MEMBER], [S.CallExpression, MEMBER], [S.MemberExpression, MEMBER], [S.ChainExpression, MEMBER],
  [S.TaggedTemplateExpression, MEMBER], [S.TSInstantiationExpression, MEMBER], [S.ImportExpression, MEMBER],
]);

// Types' precedence.
const T_FUNCTION = 0, T_CONDITIONAL = 1, T_UNION = 2, T_INTERSECTION = 3, T_OPERATOR = 4, T_POSTFIX = 5,
  T_PRIMARY = 6;
const TYPE_PRECEDENCE = new Map<Function, number>([
  [S.TSFunctionType, T_FUNCTION], [S.TSConstructorType, T_FUNCTION], [S.TSConditionalType, T_CONDITIONAL],
  [S.TSUnionType, T_UNION], [S.TSIntersectionType, T_INTERSECTION], [S.TSTypeOperator, T_OPERATOR],
  [S.TSInferType, T_OPERATOR], [S.TSArrayType, T_POSTFIX], [S.TSIndexedAccessType, T_POSTFIX],
  [S.TSTypePredicate, T_FUNCTION],
]);

function precedence(node: any): number {
  if (node instanceof S.BinaryExpression || node instanceof S.LogicalExpression) {
    return BINARY[node.operator as string] as number;
  }
  if (node instanceof S.UpdateExpression && node.prefix) return UNARY;
  return PRECEDENCE.get(node.constructor) ?? PRIMARY;
}

/** The expression a statement made of `node` starts with. */
function leftmost(node: any): any {
  for (;;) {
    if (node instanceof S.BinaryExpression || node instanceof S.LogicalExpression
      || node instanceof S.AssignmentExpression) {
      node = node.left;
    } else if (node instanceof S.MemberExpression) {
      node = node.object;
    } else if (node instanceof S.CallExpression) {
      node = node.callee;
    } else if (node instanceof S.TaggedTemplateExpression) {
      node = node.tag;
    } else if (node instanceof S.ConditionalExpression) {
      node = node.test;
    } else if (node instanceof S.SequenceExpression) {
      node = node.expressions[0];
    } else if (node instanceof S.TSAsExpression || node instanceof S.TSSatisfiesExpression
      || node instanceof S.TSNonNullExpression || node instanceof S.ChainExpression
      || node instanceof S.TSInstantiationExpression) {
      node = node.expression;
    } else if (node instanceof S.UpdateExpression && !node.prefix) {
      node = node.argument;
    } else {
      return node;
    }
  }
}

const is = (kinds: Function[], node: unknown): boolean => kinds.some((k) => node instanceof k);

type Text = (self: Printer, node: any) => string;
type Lines = (self: Printer, node: any, level: number) => string[];

/** Prints a program as a file, and any other node as the text it stands for: a statement or a member as its lines, an
 * expression, a pattern or a type as its text. With `jsx`, it prints for the JSX grammar, where an arrow function's
 * lone type parameter is `<T,>`. */
export class Printer {
  static STATEMENTS = new Map<Function, Lines>();
  static SIMPLE = new Map<Function, Text>();
  static TEXTS = new Map<Function, Text>();
  /** The level of the statement being printed, where a function or class within an expression indents from. */
  level = 0;

  constructor(readonly jsx = false) {}

  print(node: any): string {
    if (node instanceof S.Program) {
      const head = node.hashbang === null ? "" : `#!${node.hashbang}\n`;
      return head + this.block(node.body, 0).map((line) => line + "\n").join("");
    }
    if (is([S.Statement, S.ClassElement, S.TypeElement, S.SwitchCase], node)) return this.lines(node, 0).join("\n");
    return this.text(node);
  }

  // Statements

  /** The lines of a list of statements or members, a trailing comment on the line before it. */
  block(statements: any[], level: number): string[] {
    const lines: string[] = [];
    for (const statement of statements) {
      if (statement instanceof S.Comment && statement.trailing && lines.length > 0) {
        lines[lines.length - 1] += " " + this.comment(statement);
        continue;
      }
      lines.push(...this.lines(statement, level));
    }
    return lines;
  }

  /** `head {`, the body one level in, and `}`; a trailing comment first in the body goes on the head's line. */
  braced(head: string, body: any[], level: number): string[] {
    const lines = [`${INDENT.repeat(level)}${head}${head !== "" ? " " : ""}{`];
    if (body.length > 0 && body[0] instanceof S.Comment && body[0].trailing) {
      lines[0] += " " + this.comment(body[0]);
      body = body.slice(1);
    }
    if (body.length === 0 && (lines[0] as string).endsWith("{")) return [lines[0] + "}"];
    return [...lines, ...this.block(body, level + 1), `${INDENT.repeat(level)}}`];
  }

  comment(node: S.Comment): string {
    return node.block ? `/*${node.text}*/` : `//${node.text}`;
  }

  lines(node: any, level: number): string[] {
    const outer = this.level;
    this.level = level;
    const method = Printer.STATEMENTS.get(node.constructor);
    const lines = method !== undefined ? method(this, node, level) : [INDENT.repeat(level) + this.simple(node)];
    this.level = outer;
    return lines;
  }

  simple(node: any): string {
    return (Printer.SIMPLE.get(node.constructor) as Text)(this, node);
  }

  /** `head` and a statement it governs: a block on the same line, another statement on the next. */
  body(head: string, body: any, level: number): string[] {
    if (body instanceof S.BlockStatement) return this.braced(head, body.body, level);
    return [INDENT.repeat(level) + head, ...this.lines(body, level + 1)];
  }

  expressionStatement(node: S.ExpressionStatement): string {
    const expression = node.expression;
    let text = this.e(expression, SEQUENCE);
    const start = leftmost(expression);
    if (is([S.ObjectExpression, S.FunctionExpression, S.ClassExpression, S.ObjectPattern], start)
      || (start instanceof S.Identifier && start.name === "let" && text.startsWith("let["))) {
      text = `(${text})`;
    }
    return text + ";";
  }

  declaration(node: S.VariableDeclaration, withoutIn = false): string {
    const declarators = node.declarations.map((d) => this.declarator(d, withoutIn)).join(", ");
    return `${node.declare ? "declare " : ""}${node.declarationKind} ${declarators}`;
  }

  declarator(node: S.VariableDeclarator, withoutIn = false): string {
    let text = this.text(node.id);
    if (node.definite) { // `id!: type`, where `id` is a name
      const id = node.id as S.Identifier;
      text = `${this.bindingName(id)}!${this.annotation(id.typeAnnotation as S.TSTypeAnnotation)}`;
    }
    if (node.init !== null) text += ` = ${this.e(node.init, ASSIGN, withoutIn)}`;
    return text;
  }

  ifStatement(node: S.IfStatement, level: number): string[] {
    const lines = this.body(`if (${this.e(node.test, SEQUENCE)})`, node.consequent, level);
    const alternate = node.alternate;
    if (alternate === null) return lines;
    let tail: string[];
    if (alternate instanceof S.IfStatement) {
      tail = this.ifStatement(alternate, level);
      tail[0] = `${INDENT.repeat(level)}else ${(tail[0] as string).trimStart()}`;
    } else {
      tail = this.body("else", alternate, level);
    }
    if (node.consequent instanceof S.BlockStatement) { // `} else {`
      lines[lines.length - 1] += " " + (tail[0] as string).trimStart();
      tail = tail.slice(1);
    }
    return [...lines, ...tail];
  }

  loop(node: any, level: number): string[] {
    if (node instanceof S.WhileStatement) return this.body(`while (${this.e(node.test, SEQUENCE)})`, node.body, level);
    if (node instanceof S.DoWhileStatement) {
      const lines = this.body("do", node.body, level);
      const tail = `while (${this.e(node.test, SEQUENCE)});`;
      if (node.body instanceof S.BlockStatement) lines[lines.length - 1] += " " + tail;
      else lines.push(INDENT.repeat(level) + tail);
      return lines;
    }
    if (node instanceof S.ForStatement) {
      const init = node.init === null ? "" : node.init instanceof S.VariableDeclaration
        ? this.declaration(node.init, true) : this.e(node.init, SEQUENCE, true);
      const test = node.test === null ? "" : " " + this.e(node.test, SEQUENCE);
      const update = node.update === null ? "" : " " + this.e(node.update, SEQUENCE);
      return this.body(`for (${init};${test};${update})`, node.body, level);
    }
    let left = node.left instanceof S.VariableDeclaration ? this.declaration(node.left)
      : this.e(node.left, node instanceof S.ForOfStatement ? MEMBER : UNARY);
    if (node instanceof S.ForInStatement) {
      return this.body(`for (${left} in ${this.e(node.right, SEQUENCE)})`, node.body, level);
    }
    const keyword = node.isAwait ? "for await" : "for";
    if (node.left instanceof S.Identifier && node.left.name === "async" && !node.isAwait) {
      left = `(${left})`; // `for (async of ...)` would start an arrow
    }
    return this.body(`${keyword} (${left} of ${this.e(node.right, ASSIGN)})`, node.body, level);
  }

  switchStatement(node: S.SwitchStatement, level: number): string[] {
    const lines = [`${INDENT.repeat(level)}switch (${this.e(node.discriminant, SEQUENCE)}) {`];
    for (const kase of node.cases) lines.push(...this.switchCase(kase, level + 1));
    return [...lines, `${INDENT.repeat(level)}}`];
  }

  switchCase(node: S.SwitchCase, level: number): string[] {
    const head = node.test === null ? "default:" : `case ${this.e(node.test, SEQUENCE)}:`;
    const lines = [INDENT.repeat(level) + head];
    let body = node.consequent;
    if (body.length > 0 && body[0] instanceof S.Comment && body[0].trailing) {
      lines[0] += " " + this.comment(body[0]);
      body = body.slice(1);
    }
    return [...lines, ...this.block(body, level + 1)];
  }

  tryStatement(node: any, level: number): string[] {
    const lines = this.braced("try", node.block.body, level);
    const join = (inner: string[]): void => {
      lines[lines.length - 1] += " " + (inner[0] as string).trim();
      lines.push(...inner.slice(1));
    };
    if (node.handler !== null) {
      const handler = node.handler;
      const head = handler.param === null ? "catch" : `catch (${this.text(handler.param)})`;
      join(this.braced(head, handler.body.body, level));
    }
    if (node.finalizer !== null) join(this.braced("finally", node.finalizer.body, level));
    return lines;
  }

  labeled(node: S.LabeledStatement, level: number): string[] {
    const inner = this.lines(node.body, level);
    inner[0] = `${INDENT.repeat(level)}${this.text(node.label)}: ${(inner[0] as string).trim()}`;
    return inner;
  }

  functionLines(node: any, level: number): string[] {
    const head = this.functionHead(node);
    if (node instanceof S.TSDeclareFunction) {
      return [`${INDENT.repeat(level)}${node.declare ? "declare " : ""}${head};`];
    }
    return this.braced(head, node.body.body, level);
  }

  functionHead(node: any): string {
    const keyword = (node.isAsync ? "async " : "") + "function" + (node.generator ? "*" : "");
    const name = node.id === null ? "" : " " + this.text(node.id);
    return `${keyword}${name}${this.signature(node)}`;
  }

  /** `<typeParameters>(params): returnType`, or with `arrow` `... => returnType` for a function type. */
  signature(node: any, arrow = false): string {
    const parameters = node.typeParameters === null ? "" : this.text(node.typeParameters);
    const params = node.params.map((p: any) => this.text(p)).join(", ");
    const returns = node.returnType === null ? ""
      : arrow ? ` => ${this.t(node.returnType.typeAnnotation, T_FUNCTION)}` : this.annotation(node.returnType);
    return `${parameters}(${params})${returns}`;
  }

  classLines(node: any, level: number): string[] {
    const decorators = node.decorators.map((d: any) => INDENT.repeat(level) + this.text(d));
    return [...decorators, ...this.braced(this.classHead(node), node.body.body, level)];
  }

  classHead(node: any): string {
    let head = (node.declare === true ? "declare " : "") + (node.abstract === true ? "abstract " : "") + "class";
    if (node.id !== null) head += " " + this.text(node.id);
    if (node.typeParameters !== null) head += this.text(node.typeParameters);
    if (node.superClass !== null) {
      head += ` extends ${this.e(node.superClass, MEMBER)}`;
      if (node.superTypeArguments !== null) head += this.text(node.superTypeArguments);
    }
    if (node.implements.length > 0) head += " implements " + node.implements.map((i: any) => this.text(i)).join(", ");
    return head;
  }

  /** A class member's modifiers, in the order TypeScript requires. */
  memberModifiers(node: any, abstract = false): string {
    const words: string[] = node.accessibility ? [node.accessibility] : [];
    if (node.declare === true) words.push("declare");
    if (node.static === true) words.push("static");
    if (abstract) words.push("abstract");
    if (node.override === true) words.push("override");
    if (node.readonly === true) words.push("readonly");
    return words.map((w) => w + " ").join("");
  }

  method(node: any, level: number): string[] {
    const value = node.value;
    let head = this.memberModifiers(node, node instanceof S.TSAbstractMethodDefinition);
    head += (value.isAsync ? "async " : "") + (value.generator ? "*" : "");
    if (node.methodKind === "get" || node.methodKind === "set") head += node.methodKind + " ";
    head += this.key(node.key, node.computed) + (node.optional ? "?" : "") + this.signature(value);
    const decorators = node.decorators.map((d: any) => INDENT.repeat(level) + this.text(d));
    if (value instanceof S.TSEmptyBodyFunctionExpression) return [...decorators, `${INDENT.repeat(level)}${head};`];
    return [...decorators, ...this.braced(head, value.body.body, level)];
  }

  propertyDefinition(node: any, level: number): string[] {
    let head = this.memberModifiers(node, is([S.TSAbstractPropertyDefinition, S.TSAbstractAccessorProperty], node));
    if (is([S.AccessorProperty, S.TSAbstractAccessorProperty], node)) head += "accessor ";
    head += this.key(node.key, node.computed) + (node.optional ? "?" : "") + (node.definite ? "!" : "");
    if (node.typeAnnotation !== null) head += this.annotation(node.typeAnnotation);
    if (node.value !== null) head += ` = ${this.e(node.value, ASSIGN)}`;
    return [...node.decorators.map((d: any) => INDENT.repeat(level) + this.text(d)), `${INDENT.repeat(level)}${head};`];
  }

  key(key: any, computed: boolean): string {
    return computed ? `[${this.e(key, ASSIGN)}]` : this.text(key);
  }

  interfaceLines(node: any, level: number): string[] {
    let head = `${node.declare ? "declare " : ""}interface ${this.text(node.id)}`;
    if (node.typeParameters !== null) head += this.text(node.typeParameters);
    if (node.extends.length > 0) head += " extends " + node.extends.map((h: any) => this.text(h)).join(", ");
    return this.braced(head, node.body.body, level);
  }

  enumLines(node: any, level: number): string[] {
    const head = `${node.declare ? "declare " : ""}${node.const ? "const " : ""}enum ${this.text(node.id)}`;
    const lines = [`${INDENT.repeat(level)}${head} {`];
    for (const member of node.body.members) { // each on its line, with a comma; a trailing comment on the line before
      if (member instanceof S.Comment) {
        if (member.trailing) lines[lines.length - 1] += " " + this.comment(member);
        else lines.push(INDENT.repeat(level + 1) + this.comment(member));
      } else {
        lines.push(`${INDENT.repeat(level + 1)}${this.text(member)},`);
      }
    }
    if (lines.length === 1 && (lines[0] as string).endsWith("{")) return [lines[0] + "}"];
    return [...lines, `${INDENT.repeat(level)}}`];
  }

  moduleLines(node: any, level: number): string[] {
    let head = node.declare ? "declare " : "";
    head += node.moduleKind === "global" ? "global" : `${node.moduleKind} ${this.text(node.id)}`;
    if (node.body === null) return [`${INDENT.repeat(level)}${head};`];
    return this.braced(head, node.body.body, level);
  }

  exportNamed(node: S.ExportNamedDeclaration, level: number): string[] {
    if (node.declaration !== null) return this.exported(this.lines(node.declaration, level), "export ", level);
    const kind = node.exportKind === "type" ? "type " : "";
    let text = `export ${kind}{${node.specifiers.map((s) => this.text(s)).join(", ")}}`;
    if (node.source !== null) text += ` from ${this.text(node.source)}`;
    return [INDENT.repeat(level) + text + this.withAttributes(node.attributes) + ";"];
  }

  /** A declaration's lines with `prefix` before it, after its decorators. */
  exported(inner: string[], prefix: string, level: number): string[] {
    const index = inner.findIndex((line) => !line.trim().startsWith("@"));
    inner[index] = `${INDENT.repeat(level)}${prefix}${(inner[index] as string).trim()}`;
    return inner;
  }

  exportDefault(node: S.ExportDefaultDeclaration, level: number): string[] {
    const declaration = node.declaration;
    if (declaration instanceof S.Statement) {
      return this.exported(this.lines(declaration, level), "export default ", level);
    }
    let text = this.e(declaration, ASSIGN);
    if (is([S.FunctionExpression, S.ClassExpression], leftmost(declaration))) text = `(${text})`;
    return [`${INDENT.repeat(level)}export default ${text};`];
  }

  withAttributes(attributes: any[]): string {
    if (attributes.length === 0) return "";
    return " with { " + attributes.map((a) => this.text(a)).join(", ") + " }";
  }

  importDeclaration(node: S.ImportDeclaration): string {
    const head = "import " + (node.importKind === "type" ? "type " : "") + (node.phase === "defer" ? "defer " : "");
    if (node.specifiers.length === 0) return `${head}${this.text(node.source)}${this.withAttributes(node.attributes)};`;
    const parts: string[] = [];
    const named: string[] = [];
    for (const specifier of node.specifiers) {
      if (specifier instanceof S.ImportSpecifier) named.push(this.text(specifier));
      else parts.push(this.text(specifier));
    }
    if (named.length > 0) parts.push("{" + named.join(", ") + "}");
    return `${head}${parts.join(", ")} from ${this.text(node.source)}${this.withAttributes(node.attributes)};`;
  }

  exportAll(node: S.ExportAllDeclaration): string {
    let text = "export " + (node.exportKind === "type" ? "type " : "") + "*";
    if (node.exported !== null) text += ` as ${this.text(node.exported)}`;
    return `${text} from ${this.text(node.source)}${this.withAttributes(node.attributes)};`;
  }

  jump(keyword: string, node: S.BreakStatement | S.ContinueStatement): string {
    return keyword + (node.label === null ? "" : " " + this.text(node.label)) + ";";
  }

  // Expressions

  /** `node`'s text, parenthesized if it binds less than its place needs; with `withoutIn`, also if it holds an `in`
   * operator outside parentheses (a `for` statement's initializer). */
  e(node: any, needed: number, withoutIn = false): string {
    const text = this.text(node);
    if (precedence(node) < needed || (withoutIn && this.hasIn(node))) return `(${text})`;
    return text;
  }

  hasIn(node: any): boolean {
    if (node instanceof S.BinaryExpression) {
      return node.operator === "in" || this.hasIn(node.left) || this.hasIn(node.right);
    }
    if (node instanceof S.LogicalExpression || node instanceof S.AssignmentExpression) {
      return this.hasIn(node.left) || this.hasIn(node.right);
    }
    if (node instanceof S.ConditionalExpression) {
      return this.hasIn(node.test) || this.hasIn(node.consequent) || this.hasIn(node.alternate);
    }
    if (node instanceof S.SequenceExpression) return node.expressions.some((x) => this.hasIn(x));
    if (node instanceof S.TSAsExpression || node instanceof S.TSSatisfiesExpression) return this.hasIn(node.expression);
    if (node instanceof S.ArrowFunctionExpression) return this.hasIn(node.body);
    return false;
  }

  text(node: any): string {
    return (Printer.TEXTS.get(node.constructor) as Text)(this, node);
  }

  binary(node: S.BinaryExpression | S.LogicalExpression): string {
    const operator = node.operator as string;
    const level = BINARY[operator] as number;
    if (operator === "**") {
      let left = this.e(node.left, POWER + 1);
      if (is([S.UnaryExpression, S.AwaitExpression, S.TSTypeAssertion], node.left)) {
        left = `(${this.text(node.left)})`; // `-a ** b` is not JavaScript
      }
      return `${left} ** ${this.e(node.right, POWER)}`;
    }
    let left = this.e(node.left, level);
    let right = this.e(node.right, level + 1);
    if (node instanceof S.LogicalExpression) { // `??` does not mix with `||` and `&&` without parentheses
      const mixes = (operand: any): boolean => operand instanceof S.LogicalExpression
        && (operand.operator === "??") !== (operator === "??");
      if (mixes(node.left)) left = `(${this.text(node.left)})`;
      if (mixes(node.right)) right = `(${this.text(node.right)})`;
    }
    if (node.left instanceof S.PrivateIdentifier) left = this.text(node.left);
    return `${left} ${operator} ${right}`;
  }

  assignment(node: S.AssignmentExpression): string {
    const left = is([S.ObjectPattern, S.ArrayPattern], node.left) ? this.text(node.left) : this.e(node.left, MEMBER);
    return `${left} ${node.operator} ${this.e(node.right, ASSIGN)}`;
  }

  unary(node: S.UnaryExpression): string {
    const operator = node.operator as string;
    const argument = this.e(node.argument, UNARY);
    if (operator === "typeof" || operator === "void" || operator === "delete") return `${operator} ${argument}`;
    if ((operator === "+" || operator === "-") && argument.startsWith(operator)) {
      return `${operator} ${argument}`; // `--a` and `++a` would be updates
    }
    return `${operator}${argument}`;
  }

  update(node: S.UpdateExpression): string {
    if (node.prefix) return `${node.operator}${this.e(node.argument, UNARY)}`;
    return `${this.e(node.argument, POSTFIX + 1)}${node.operator}`;
  }

  member(node: S.MemberExpression): string {
    let target = this.e(node.object, MEMBER);
    if (node.object instanceof S.Literal && /^[0-9_]*$/.test(node.object.raw as string)) {
      target = `(${target})`; // `1.toString()` would be a number
    }
    if (node.computed) return `${target}${node.optional ? "?." : ""}[${this.e(node.property, SEQUENCE)}]`;
    return `${target}${node.optional ? "?." : "."}${this.text(node.property)}`;
  }

  call(node: S.CallExpression): string {
    const callee = this.e(node.callee, MEMBER);
    const args = node.typeArguments === null ? "" : this.text(node.typeArguments);
    return `${callee}${node.optional ? "?." : ""}${args}(${this.arguments(node.arguments)})`;
  }

  arguments(args: any[]): string {
    return args.map((a) => this.e(a, ASSIGN)).join(", ");
  }

  newExpression(node: S.NewExpression): string {
    let callee = this.e(node.callee, NEW);
    if (this.calls(node.callee)) callee = `(${callee})`; // `new f()()` would call `f`'s instance
    const args = node.typeArguments === null ? "" : this.text(node.typeArguments);
    return `new ${callee}${args}(${this.arguments(node.arguments)})`;
  }

  /** Whether `node`, as a `new` callee, holds a call, a `new` or a non-null assertion outside parentheses, which would
   * end the callee: tree-sitter-typescript reads `new a!.b()` as `(new a)!.b()`. */
  calls(node: any): boolean {
    while (node instanceof S.MemberExpression) node = node.object;
    return is([S.CallExpression, S.ChainExpression, S.ImportExpression, S.TSNonNullExpression, S.NewExpression], node);
  }

  arrow(node: S.ArrowFunctionExpression): string {
    let head = (node.isAsync ? "async " : "") + this.signature(node);
    const parameters = node.typeParameters;
    if (this.jsx && parameters !== null && parameters.params.length === 1
      && (parameters.params[0] as S.TSTypeParameter).constraint === null) {
      const written = this.text(parameters);
      head = head.replace(written, written.slice(0, -1) + ",>"); // `<T>(` would open an element
    }
    if (node.body instanceof S.BlockStatement) return head + " => " + this.inlineBlock(node.body);
    let body = this.e(node.body, ASSIGN);
    if (is([S.ObjectExpression, S.ObjectPattern], leftmost(node.body))) body = `(${body})`;
    return `${head} => ${body}`;
  }

  /** A block within an expression: its lines joined, its body one level in from the statement's. */
  inlineBlock(node: S.BlockStatement): string {
    return this.braced("", node.body, this.level).join("\n").trimStart();
  }

  classExpression(node: any): string {
    const decorators = node.decorators.map((d: any) => this.text(d) + " ").join("");
    return decorators + this.braced(this.classHead(node), node.body.body, this.level).join("\n").trimStart();
  }

  template(node: S.TemplateLiteral): string {
    const parts = [(node.quasis[0] as S.TemplateElement).raw];
    node.expressions.forEach((expression, i) => {
      parts.push("${" + this.e(expression, SEQUENCE) + "}" + (node.quasis[i + 1] as S.TemplateElement).raw);
    });
    return "`" + parts.join("") + "`";
  }

  property(node: S.Property): string {
    const key = this.key(node.key, node.computed);
    const value: any = node.value;
    if (node.shorthand) {
      if (value instanceof S.AssignmentPattern) return `${this.text(value.left)} = ${this.e(value.right, ASSIGN)}`;
      return key;
    }
    if (node.propertyKind === "get" || node.propertyKind === "set" || node.method) {
      let prefix = node.propertyKind === "get" || node.propertyKind === "set" ? node.propertyKind + " " : "";
      prefix += (value.isAsync ? "async " : "") + (value.generator ? "*" : "");
      if (value instanceof S.TSEmptyBodyFunctionExpression) return `${prefix}${key}${this.signature(value)}`;
      return `${prefix}${key}${node.optional ? "?" : ""}${this.signature(value)} ${this.inlineBlock(value.body)}`;
    }
    return `${key}: ${this.e(value, ASSIGN)}`;
  }

  array(node: S.ArrayExpression | S.ArrayPattern): string {
    const elements = node.elements.map((x) => this.element(x));
    if (node.elements.length > 0 && node.elements.at(-1) instanceof S.Elision) {
      elements.push(""); // `[a, ,]` keeps its last hole
    }
    return "[" + elements.map((x, i) => (i > 0 && x !== "" ? " " : "") + x).join(",") + "]";
  }

  element(node: any): string {
    return node instanceof S.Elision ? "" : this.e(node, ASSIGN);
  }

  jsxElement(node: S.JSXElement | S.JSXFragment): string {
    if (node instanceof S.JSXFragment) return "<>" + node.children.map((c) => this.text(c)).join("") + "</>";
    const opening = node.openingElement as S.JSXOpeningElement;
    const name = this.text(opening.name);
    const args = opening.typeArguments === null ? "" : this.text(opening.typeArguments);
    const attributes = opening.attributes.map((a) => " " + this.text(a)).join("");
    if (opening.selfClosing) return `<${name}${args}${attributes} />`;
    const children = node.children.map((c) => this.text(c)).join("");
    return `<${name}${args}${attributes}>${children}</${this.text((node.closingElement as S.JSXClosingElement).name)}>`;
  }

  // Patterns and parameters

  bindingName(node: S.Identifier): string {
    return node.name + (node.optional ? "?" : "");
  }

  identifier(node: S.Identifier): string {
    const decorators = node.decorators.map((d) => this.text(d) + " ").join("");
    const text = decorators + this.bindingName(node);
    return text + (node.typeAnnotation === null ? "" : this.annotation(node.typeAnnotation));
  }

  pattern(node: any, inner: string): string {
    const decorators = node.decorators.map((d: any) => this.text(d) + " ").join("");
    const text = decorators + inner + (node.optional ? "?" : "");
    return text + (node.typeAnnotation === null ? "" : this.annotation(node.typeAnnotation));
  }

  // Types

  annotation(node: S.TSTypeAnnotation): string {
    return ": " + this.t(node.typeAnnotation, T_FUNCTION);
  }

  /** A type's text, parenthesized if it binds less than its place needs. */
  t(node: any, needed: number): string {
    const text = this.text(node);
    return (TYPE_PRECEDENCE.get(node.constructor) ?? T_PRIMARY) < needed ? `(${text})` : text;
  }

  union(node: S.TSUnionType | S.TSIntersectionType): string {
    const [operator, level] = node instanceof S.TSUnionType ? [" | ", T_INTERSECTION] : [" & ", T_OPERATOR];
    return node.types.map((t) => this.t(t, level)).join(operator);
  }

  typeOperator(node: S.TSTypeOperator): string {
    if (node.typeAnnotation === null) return node.operator as string;
    return `${node.operator} ${this.t(node.typeAnnotation, T_OPERATOR)}`;
  }

  conditionalType(node: S.TSConditionalType): string {
    // a function type needs no parentheses, unless it returns a conditional type
    const extendsType: any = node.extendsType;
    let extended: string;
    if (extendsType instanceof S.TSConditionalType || (is([S.TSFunctionType, S.TSConstructorType], extendsType)
      && extendsType.returnType !== null && extendsType.returnType.typeAnnotation instanceof S.TSConditionalType)) {
      extended = `(${this.text(extendsType)})`;
    } else {
      extended = this.t(extendsType, T_FUNCTION);
    }
    return `${this.t(node.checkType, T_UNION)} extends ${extended} ? `
      + `${this.t(node.trueType, T_FUNCTION)} : ${this.t(node.falseType, T_FUNCTION)}`;
  }

  mapped(node: S.TSMappedType): string {
    const readonly = node.readonly === null ? "" : node.readonly + " ";
    const name = node.nameType === null ? "" : ` as ${this.t(node.nameType, T_FUNCTION)}`;
    const optional = node.optional ?? "";
    const value = node.typeAnnotation === null ? "" : `: ${this.t(node.typeAnnotation, T_FUNCTION)}`;
    const constraint = this.t(node.constraint, T_FUNCTION);
    return `{ ${readonly}[${this.text(node.key)} in ${constraint}${name}]${optional}${value} }`;
  }

  typeParameter(node: S.TSTypeParameter): string {
    let text = (node.const ? "const " : "") + (node.isIn ? "in " : "") + (node.isOut ? "out " : "");
    text += this.text(node.name);
    if (node.constraint !== null) text += ` extends ${this.t(node.constraint, T_FUNCTION)}`;
    if (node.default !== null) text += ` = ${this.t(node.default, T_FUNCTION)}`;
    return text;
  }

  predicate(node: S.TSTypePredicate): string {
    let text = (node.asserts ? "asserts " : "") + this.text(node.parameterName);
    if (node.typeAnnotation !== null) text += ` is ${this.t(node.typeAnnotation.typeAnnotation, T_FUNCTION)}`;
    return text;
  }

  /** `{ a: A; b(): B }` on one line, or with comments its members' lines, one level in from the statement's. */
  typeLiteral(node: S.TSTypeLiteral): string {
    if (node.members.some((m) => m instanceof S.Comment)) {
      return this.braced("", node.members, this.level).join("\n").trimStart();
    }
    if (node.members.length === 0) return "{}";
    return "{ " + node.members.map((m) => this.simple(m)).join(" ") + " }";
  }

  indexSignature(node: S.TSIndexSignature): string {
    const words = [...(node.accessibility ? [node.accessibility] : []), ...(node.static ? ["static"] : []),
      ...(node.readonly ? ["readonly"] : [])];
    const parameters = node.parameters.map((p) => this.text(p)).join(", ");
    const annotation = node.typeAnnotation === null ? "" : this.annotation(node.typeAnnotation);
    return `${words.map((w) => w + " ").join("")}[${parameters}]${annotation}`;
  }

  propertySignature(node: S.TSPropertySignature): string {
    const text = (node.readonly ? "readonly " : "") + this.key(node.key, node.computed) + (node.optional ? "?" : "");
    return text + (node.typeAnnotation === null ? "" : this.annotation(node.typeAnnotation));
  }

  methodSignature(node: S.TSMethodSignature): string {
    const prefix = node.methodKind === "get" || node.methodKind === "set" ? node.methodKind + " " : "";
    return `${prefix}${this.key(node.key, node.computed)}${node.optional ? "?" : ""}${this.signature(node)}`;
  }

  importType(node: S.TSImportType): string {
    const options = node.options === null ? "" : ", " + this.text(node.options);
    let text = `import(${this.text(node.source)}${options})`;
    if (node.qualifier !== null) text += "." + this.text(node.qualifier);
    return text + (node.typeArguments === null ? "" : this.text(node.typeArguments));
  }

  heritage(node: S.TSInterfaceHeritage | S.TSClassImplements): string {
    return this.e(node.expression, MEMBER) + (node.typeArguments === null ? "" : this.text(node.typeArguments));
  }
}

const P = Printer.prototype;
const lines = (method: (this: Printer, node: any, level: number) => string[]): Lines =>
  (self, node, level) => method.call(self, node, level);
const text = (method: (this: Printer, node: any) => string): Text => (self, node) => method.call(self, node);
const optional = (self: Printer, node: any): string => (node === null ? "" : self.text(node));
const typed = (keyword: string): Text => (self, node) =>
  `${self.e(node.expression, RELATIONAL)} ${keyword} ${self.t(node.typeAnnotation, 0)}`;
const signed: Text = (self, node) => self.text(node) + ";";

Printer.STATEMENTS = new Map<Function, Lines>([
  [S.BlockStatement, (self, node, level) => self.braced("", node.body, level)],
  [S.IfStatement, lines(P.ifStatement)], [S.WhileStatement, lines(P.loop)], [S.DoWhileStatement, lines(P.loop)],
  [S.ForStatement, lines(P.loop)], [S.ForInStatement, lines(P.loop)], [S.ForOfStatement, lines(P.loop)],
  [S.SwitchStatement, lines(P.switchStatement)], [S.SwitchCase, lines(P.switchCase)],
  [S.TryStatement, lines(P.tryStatement)], [S.LabeledStatement, lines(P.labeled)],
  [S.WithStatement, (self, node, level) => self.body(`with (${self.e(node.object, SEQUENCE)})`, node.body, level)],
  [S.FunctionDeclaration, lines(P.functionLines)], [S.TSDeclareFunction, lines(P.functionLines)],
  [S.ClassDeclaration, lines(P.classLines)], [S.MethodDefinition, lines(P.method)],
  [S.TSAbstractMethodDefinition, lines(P.method)], [S.PropertyDefinition, lines(P.propertyDefinition)],
  [S.TSAbstractPropertyDefinition, lines(P.propertyDefinition)], [S.AccessorProperty, lines(P.propertyDefinition)],
  [S.TSAbstractAccessorProperty, lines(P.propertyDefinition)],
  [S.StaticBlock, (self, node, level) => self.braced("static", node.body, level)],
  [S.TSInterfaceDeclaration, lines(P.interfaceLines)], [S.TSEnumDeclaration, lines(P.enumLines)],
  [S.TSModuleDeclaration, lines(P.moduleLines)], [S.ExportNamedDeclaration, lines(P.exportNamed)],
  [S.ExportDefaultDeclaration, lines(P.exportDefault)],
]);

Printer.SIMPLE = new Map<Function, Text>([
  [S.Comment, (self, node) => self.comment(node)], [S.ExpressionStatement, text(P.expressionStatement)],
  [S.VariableDeclaration, (self, node) => self.declaration(node) + ";"], [S.EmptyStatement, () => ";"],
  [S.DebuggerStatement, () => "debugger;"],
  [S.ReturnStatement, (self, node) =>
    (node.argument === null ? "return;" : `return ${self.e(node.argument, SEQUENCE)};`)],
  [S.ThrowStatement, (self, node) => `throw ${self.e(node.argument, SEQUENCE)};`],
  [S.BreakStatement, (self, node) => self.jump("break", node)],
  [S.ContinueStatement, (self, node) => self.jump("continue", node)],
  [S.ImportDeclaration, text(P.importDeclaration)], [S.ExportAllDeclaration, text(P.exportAll)],
  [S.TSImportEqualsDeclaration, (self, node) =>
    `import ${node.importKind === "type" ? "type " : ""}${self.text(node.id)} = ${self.text(node.moduleReference)};`],
  [S.TSExportAssignment, (self, node) => `export = ${self.e(node.expression, ASSIGN)};`],
  [S.TSNamespaceExportDeclaration, (self, node) => `export as namespace ${self.text(node.id)};`],
  [S.TSTypeAliasDeclaration, (self, node) => `${node.declare ? "declare " : ""}type ${self.text(node.id)}`
    + `${optional(self, node.typeParameters)} = ${self.t(node.typeAnnotation, T_FUNCTION)};`],
  [S.TSIndexSignature, signed], [S.TSPropertySignature, signed], [S.TSMethodSignature, signed],
  [S.TSCallSignatureDeclaration, signed], [S.TSConstructSignatureDeclaration, signed],
]);

const specifier = (self: Printer, kind: boolean, from: any, to: any): string => (kind ? "type " : "")
  + (self.text(from) === self.text(to) ? self.text(from) : `${self.text(from)} as ${self.text(to)}`);
const keyword = (word: string): Text => () => word;

Printer.TEXTS = new Map<Function, Text>([
  [S.Comment, (self, node) => self.comment(node)],
  [S.Identifier, text(P.identifier)], [S.PrivateIdentifier, (_self, node) => "#" + node.name],
  [S.Literal, (_self, node) => node.raw], [S.TemplateElement, (_self, node) => node.raw],
  [S.TemplateLiteral, text(P.template)],
  [S.TaggedTemplateExpression, (self, node) =>
    self.e(node.tag, MEMBER) + optional(self, node.typeArguments) + self.text(node.quasi)],
  [S.ThisExpression, keyword("this")], [S.Super, keyword("super")],
  [S.ParenthesizedExpression, (self, node) => `(${self.e(node.expression, SEQUENCE)})`],
  [S.Elision, keyword("")], [S.SpreadElement, (self, node) => `...${self.e(node.argument, ASSIGN)}`],
  [S.ArrayExpression, text(P.array)], [S.Property, text(P.property)],
  [S.ObjectExpression, (self, node) => (node.properties.length === 0 ? "{}"
    : "{ " + node.properties.map((p: any) => self.text(p)).join(", ") + " }")],
  [S.FunctionExpression, (self, node) => self.functionHead(node) + " " + self.inlineBlock(node.body)],
  [S.ArrowFunctionExpression, text(P.arrow)], [S.ClassExpression, text(P.classExpression)],
  [S.MetaProperty, (self, node) => `${self.text(node.meta)}.${self.text(node.property)}`],
  [S.MemberExpression, text(P.member)], [S.CallExpression, text(P.call)],
  [S.ChainExpression, (self, node) => self.text(node.expression)], [S.NewExpression, text(P.newExpression)],
  [S.ImportExpression, (self, node) => "import" + (node.phase === "defer" ? ".defer" : "") + "("
    + [node.source, ...(node.options === null ? [] : [node.options])].map((a) => self.e(a, ASSIGN)).join(", ") + ")"],
  [S.UpdateExpression, text(P.update)], [S.UnaryExpression, text(P.unary)],
  [S.AwaitExpression, (self, node) => `await ${self.e(node.argument, UNARY)}`],
  [S.BinaryExpression, text(P.binary)], [S.LogicalExpression, text(P.binary)],
  [S.ConditionalExpression, (self, node) => `${self.e(node.test, COALESCE)} ? ${self.e(node.consequent, ASSIGN)} : `
    + self.e(node.alternate, ASSIGN)],
  [S.AssignmentExpression, text(P.assignment)],
  [S.SequenceExpression, (self, node) => node.expressions.map((x: any) => self.e(x, ASSIGN)).join(", ")],
  [S.YieldExpression, (self, node) => (node.delegate ? "yield*" : "yield")
    + (node.argument === null ? "" : " " + self.e(node.argument, ASSIGN))],
  [S.TSAsExpression, typed("as")], [S.TSSatisfiesExpression, typed("satisfies")],
  [S.TSTypeAssertion, (self, node) => `<${self.t(node.typeAnnotation, 0)}>${self.e(node.expression, UNARY)}`],
  [S.TSNonNullExpression, (self, node) => `${self.e(node.expression, MEMBER)}!`],
  [S.TSInstantiationExpression, (self, node) => self.e(node.expression, MEMBER) + self.text(node.typeArguments)],
  [S.ArrayPattern, (self, node) => self.pattern(node, self.array(node))],
  [S.ObjectPattern, (self, node) => self.pattern(node, node.properties.length === 0 ? "{}"
    : "{ " + node.properties.map((p: any) => self.text(p)).join(", ") + " }")],
  [S.AssignmentPattern, (self, node) => self.pattern(node, `${self.text(node.left)} = ${self.e(node.right, ASSIGN)}`)],
  [S.RestElement, (self, node) => self.pattern(node, `...${self.text(node.argument)}`)],
  [S.Decorator, (self, node) => "@" + self.e(node.expression, MEMBER)],
  [S.TSParameterProperty, (self, node) => node.decorators.map((d: any) => self.text(d) + " ").join("")
    + self.memberModifiers(node) + self.text(node.parameter)],
  [S.ImportAttribute, (self, node) => `${self.text(node.key)}: ${self.text(node.value)}`],
  [S.ImportSpecifier, (self, node) => specifier(self, node.importKind === "type", node.imported, node.local)],
  [S.ImportDefaultSpecifier, (self, node) => self.text(node.local)],
  [S.ImportNamespaceSpecifier, (self, node) => `* as ${self.text(node.local)}`],
  [S.ExportSpecifier, (self, node) => specifier(self, node.exportKind === "type", node.local, node.exported)],
  [S.TSExternalModuleReference, (self, node) => `require(${self.text(node.expression)})`],
  [S.TSTypeAnnotation, (self, node) => self.t(node.typeAnnotation, T_FUNCTION)],
  [S.TSTypeParameter, text(P.typeParameter)],
  [S.TSTypeParameterDeclaration, (self, node) => "<" + node.params.map((p: any) => self.text(p)).join(", ") + ">"],
  [S.TSTypeParameterInstantiation, (self, node) =>
    "<" + node.params.map((p: any) => self.t(p, T_FUNCTION)).join(", ") + ">"],
  [S.TSInterfaceHeritage, text(P.heritage)], [S.TSClassImplements, text(P.heritage)],
  [S.TSEnumMember, (self, node) => self.key(node.id, node.computed)
    + (node.initializer === null ? "" : ` = ${self.e(node.initializer, ASSIGN)}`)],
  [S.TSPropertySignature, text(P.propertySignature)], [S.TSMethodSignature, text(P.methodSignature)],
  [S.TSCallSignatureDeclaration, (self, node) => self.signature(node)],
  [S.TSConstructSignatureDeclaration, (self, node) => "new " + self.signature(node)],
  [S.TSIndexSignature, text(P.indexSignature)],
  [S.TSAnyKeyword, keyword("any")], [S.TSUnknownKeyword, keyword("unknown")], [S.TSNumberKeyword, keyword("number")],
  [S.TSBigIntKeyword, keyword("bigint")], [S.TSBooleanKeyword, keyword("boolean")],
  [S.TSStringKeyword, keyword("string")], [S.TSSymbolKeyword, keyword("symbol")],
  [S.TSObjectKeyword, keyword("object")], [S.TSNeverKeyword, keyword("never")], [S.TSVoidKeyword, keyword("void")],
  [S.TSUndefinedKeyword, keyword("undefined")],
  [S.TSNullKeyword, keyword("null")], [S.TSIntrinsicKeyword, keyword("intrinsic")], [S.TSThisType, keyword("this")],
  [S.TSQualifiedName, (self, node) => `${self.text(node.left)}.${self.text(node.right)}`],
  [S.TSTypeReference, (self, node) => self.text(node.typeName) + optional(self, node.typeArguments)],
  [S.TSParenthesizedType, (self, node) => `(${self.t(node.typeAnnotation, T_FUNCTION)})`],
  [S.TSLiteralType, (self, node) => self.text(node.literal)],
  [S.TSTemplateLiteralType, (self, node) => "`" + node.quasis[0].raw + node.types.map((t: any, i: number) =>
    "${" + self.t(t, T_FUNCTION) + "}" + node.quasis[i + 1].raw).join("") + "`"],
  [S.TSArrayType, (self, node) => self.t(node.elementType, T_POSTFIX) + "[]"],
  [S.TSTupleType, (self, node) => "[" + node.elementTypes.map((t: any) => self.t(t, T_FUNCTION)).join(", ") + "]"],
  [S.TSNamedTupleMember, (self, node) =>
    `${self.text(node.label)}${node.optional ? "?" : ""}: ${self.t(node.elementType, T_FUNCTION)}`],
  [S.TSOptionalType, (self, node) => self.t(node.typeAnnotation, T_POSTFIX) + "?"],
  [S.TSRestType, (self, node) => "..." + self.t(node.typeAnnotation, T_FUNCTION)],
  [S.TSUnionType, text(P.union)], [S.TSIntersectionType, text(P.union)],
  [S.TSFunctionType, (self, node) => self.signature(node, true)],
  [S.TSConstructorType, (self, node) => (node.abstract ? "abstract " : "") + "new " + self.signature(node, true)],
  [S.TSTypeLiteral, text(P.typeLiteral)], [S.TSMappedType, text(P.mapped)],
  [S.TSIndexedAccessType, (self, node) =>
    `${self.t(node.objectType, T_POSTFIX)}[${self.t(node.indexType, T_FUNCTION)}]`],
  [S.TSTypeOperator, text(P.typeOperator)],
  [S.TSTypeQuery, (self, node) => "typeof " + self.text(node.exprName) + optional(self, node.typeArguments)],
  [S.TSImportType, text(P.importType)], [S.TSConditionalType, text(P.conditionalType)],
  [S.TSInferType, (self, node) => "infer " + self.typeParameter(node.typeParameter)],
  [S.TSTypePredicate, text(P.predicate)],
  [S.JSXIdentifier, (_self, node) => node.name],
  [S.JSXNamespacedName, (self, node) => `${self.text(node.namespace)}:${self.text(node.name)}`],
  [S.JSXMemberExpression, (self, node) => `${self.text(node.object)}.${self.text(node.property)}`],
  [S.JSXEmptyExpression, keyword("")],
  [S.JSXExpressionContainer, (self, node) => "{" + self.text(node.expression) + "}"],
  [S.JSXSpreadChild, (self, node) => "{..." + self.text(node.expression) + "}"],
  [S.JSXText, (_self, node) => node.raw],
  [S.JSXAttribute, (self, node) => self.text(node.name) + (node.value === null ? "" : "=" + self.text(node.value))],
  [S.JSXSpreadAttribute, (self, node) => "{..." + self.e(node.argument, ASSIGN) + "}"],
  [S.JSXElement, text(P.jsxElement)], [S.JSXFragment, text(P.jsxElement)],
]);
