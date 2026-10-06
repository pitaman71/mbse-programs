/**
 * Prints Verilog trees as SystemVerilog source text, in one fixed layout.
 *
 * The layout: four spaces per level, `begin` on the line it opens and `end else begin`, one item or statement per
 * line, a design unit's parameters and ports one per line, directives at the start of their line, and a blank line
 * around items that span several lines. Parentheses written in the tree are printed; those a tree built by hand needs
 * are added, by the precedence of IEEE 1800's Table 11-2. The printer assumes a valid tree: standards validate before
 * they print.
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

const INDENT = "    ";
const pad = (level: number) => INDENT.repeat(level);

// Precedence (Table 11-2): higher binds tighter.
const [IMPLY, CONDITIONAL, OR, AND, BOR, BXOR, BAND, EQUALITY, RELATIONAL, SHIFT, ADDITIVE, MULTIPLICATIVE, POWER,
  UNARY, PRIMARY] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] as const;
const BINARY: Record<string, number> = {
  "->": IMPLY, "<->": IMPLY, "||": OR, "&&": AND, "|": BOR, "^": BXOR, "^~": BXOR, "~^": BXOR, "&": BAND,
  "==": EQUALITY, "!=": EQUALITY, "===": EQUALITY, "!==": EQUALITY, "==?": EQUALITY, "!=?": EQUALITY,
  "<": RELATIONAL, "<=": RELATIONAL, ">": RELATIONAL, ">=": RELATIONAL, "<<": SHIFT, ">>": SHIFT, "<<<": SHIFT,
  ">>>": SHIFT, "+": ADDITIVE, "-": ADDITIVE, "*": MULTIPLICATIVE, "/": MULTIPLICATIVE, "%": MULTIPLICATIVE,
  "**": POWER,
};
// Sequences and properties (Table 16-3) bind looser than any expression operator.
const [REPEAT, DELAY, THROUGHOUT, WITHIN, INTERSECT, SEQUENCE_AND, SEQUENCE_OR, NOT, PROPERTY_AND, PROPERTY_OR, IFF, UNTIL,
  IMPLICATION, TEMPORAL] = [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10, -11, -12, -13, -14] as const;
const SEQUENCE: Record<string, number> = {
  throughout: THROUGHOUT, within: WITHIN, intersect: INTERSECT, and: SEQUENCE_AND, or: SEQUENCE_OR,
};
const PROPERTY: Record<string, number> = {
  and: PROPERTY_AND, or: PROPERTY_OR, iff: IFF, implies: UNTIL, until: UNTIL, s_until: UNTIL, until_with: UNTIL,
  s_until_with: UNTIL,
};
const RIGHT = new Set<number>([IMPLY, CONDITIONAL, THROUGHOUT, IFF, UNTIL, IMPLICATION]); // right-associative levels

const isAny = (node: unknown, kinds: Function[]) => kinds.some((k) => node instanceof k);
const joined = (parts: (string | null | undefined)[], separator = " ") => parts.filter((p) => p).join(separator);

function precedence(node: unknown): number {
  if (node instanceof S.BinaryExpression) return BINARY[node.operator as string] as number;
  if (isAny(node, [S.InsideExpression, S.DistExpression])) return RELATIONAL;
  if (node instanceof S.ConditionalExpression) return CONDITIONAL;
  if (isAny(node, [S.UnaryExpression, S.IncrementExpression])) return UNARY;
  if (node instanceof S.AssignmentExpression) return 0;
  if (node instanceof S.RepetitionSequence) return REPEAT;
  if (node instanceof S.DelaySequence) return DELAY;
  if (node instanceof S.BinarySequence) return SEQUENCE[node.operator as string] as number;
  if (node instanceof S.BinaryProperty) return PROPERTY[node.operator as string] as number;
  if (node instanceof S.UnaryProperty) return ["not", "nexttime", "s_nexttime"].includes(node.operator as string) ? NOT : TEMPORAL;
  if (node instanceof S.ImplicationProperty) return IMPLICATION;
  // they reach as far right as they can
  if (isAny(node, [S.ConditionalProperty, S.AbortProperty, S.ClockedProperty, S.ClockedSequence])) return TEMPORAL;
  return PRIMARY;
}

/** Whether a function or task is a prototype, without a body: `extern` or `pure`. */
function prototype(node: any): boolean {
  return node.extern || node.pure;
}

function multiline(node: unknown): boolean {
  if (isAny(node, [S.FunctionDeclaration, S.TaskDeclaration])) return !prototype(node);
  return isAny(node, [S.ModuleDeclaration, S.InterfaceDeclaration, S.ProgramDeclaration, S.PackageDeclaration,
    S.ClassDeclaration, S.ConstraintDeclaration, S.PropertyDeclaration, S.SequenceDeclaration, S.ClockingDeclaration,
    S.AlwaysConstruct, S.InitialConstruct, S.FinalConstruct, S.GenerateRegion, S.GenerateFor,
    S.GenerateIf, S.GenerateCase, S.GenerateBlock, S.IfdefDirective]);
}

type Method = (self: Printer, node: any, level: number) => string[];

/** Prints source text as a file, and any other syntax node as the text it stands for: an item or a statement as its
 * lines, an expression or a part (a port, a dimension, ...) as its text. */
export class Printer {
  static ITEMS = new Map<Function, Method>();
  static STATEMENTS = new Map<Function, Method>();

  print(node: SyntaxNode): string {
    if (node instanceof S.SourceText) return this.items(node.items, 0).map((line) => line + "\n").join("");
    if (isAny(node, [S.Item, S.Statement, S.Directive, S.Comment])) return this.item(node, 0).join("\n");
    return this.text(node);
  }

  // Lists of items and statements

  /** The lines of a list of items. A trailing comment ends the line before it: for the first item, the last line of
   * `after`, the header the items follow. */
  items(items: readonly any[], level: number, after: string[] | null = null): string[] {
    const lines: string[] = [];
    let previousMultiline = false;
    items.forEach((item, i) => {
      const host = lines.length > 0 ? lines : after;
      if (item instanceof S.Comment && item.trailing && host !== null && host.length > 0) {
        host[host.length - 1] += "  " + this.comment(item);
        return;
      }
      const starts = multiline(item) && !this.led(items, i) || item instanceof S.Comment && this.leads(items, i);
      if (lines.length > 0 && (previousMultiline || starts)) {
        lines.push("");
      }
      lines.push(...this.item(item, level));
      previousMultiline = multiline(item);
    });
    return lines;
  }

  /** Whether the comment `items[i]` starts the comments directly before a multi-line item. */
  leads(items: readonly any[], i: number): boolean {
    let j = i;
    while (j < items.length && items[j] instanceof S.Comment) j += 1;
    return j < items.length && multiline(items[j])
      && (i === 0 || !(items[i - 1] instanceof S.Comment) || items[i - 1].trailing);
  }

  led(items: readonly any[], i: number): boolean {
    return i > 0 && items[i - 1] instanceof S.Comment && !items[i - 1].trailing;
  }

  comment(node: any): string {
    return node.block ? `/*${node.text}*/` : `//${node.text}`;
  }

  item(node: any, level: number): string[] {
    if (node instanceof S.Comment) return this.comment(node).split("\n").map((line, i) => i === 0 ? pad(level) + line : line);
    if (node instanceof S.Directive) return this.directive(node, level);
    if (node instanceof S.Statement) return this.statement(node, level);
    if (node instanceof S.Constraint) return this.constraint(node, level);
    return (Printer.ITEMS.get(node.constructor) as Method)(this, node, level);
  }

  // Directives

  directive(node: any, level: number): string[] {
    if (node instanceof S.IfdefDirective) {
      const lines = [`\`${node.negated ? "ifndef" : "ifdef"} ${node.name?.spelling}`];
      lines.push(...this.branch(node.items, level));
      for (const branch of node.branches) {
        lines.push(`\`elsif ${branch.name?.spelling}`);
        lines.push(...this.branch(branch.items, level));
      }
      if (node.has_else) {
        lines.push("`else");
        lines.push(...this.branch(node.alternative, level));
      }
      lines.push("`endif");
      return lines;
    }
    if (node instanceof S.DisabledText) return (node.text as string).split("\n");
    if (node instanceof S.IncludeDirective) return [node.system ? `\`include <${node.path}>` : `\`include "${node.path}"`];
    if (node instanceof S.DefineDirective) {
      const parameters = node.function_like ? `(${node.parameters.map((p) => p.spelling).join(", ")})` : "";
      return [`\`define ${node.name?.spelling}${parameters}` + (node.body ? ` ${node.body}` : "")];
    }
    if (node instanceof S.UndefDirective) return [`\`undef ${node.name?.spelling}`];
    if (node instanceof S.TimescaleDirective) return [`\`timescale ${node.unit} / ${node.precision}`];
    if (node instanceof S.DefaultNettypeDirective) return [`\`default_nettype ${node.net_type}`];
    return [node.text]; // an OtherDirective: the tree is valid, so nothing else is here
  }

  branch(items: readonly any[], level: number): string[] {
    return items.flatMap((item) => item instanceof S.Statement ? this.statement(item, level) : this.item(item, level));
  }

  // Design units

  designUnit(node: any, level: number): string[] {
    const p = pad(level);
    const keyword = node instanceof S.ModuleDeclaration ? node.keyword : node instanceof S.InterfaceDeclaration
      ? "interface" : node instanceof S.ProgramDeclaration ? "program" : "package";
    const end = { module: "endmodule", macromodule: "endmodule", interface: "endinterface", program: "endprogram",
      package: "endpackage" }[keyword as string] as string;
    let head = `${p}${keyword}${node.lifetime ? ` ${node.lifetime}` : ""} ${node.name.spelling}`;
    const lines: string[] = [];
    const imports: any[] = node.imports ?? [];
    if (imports.length > 0) {
      lines.push(head);
      lines.push(...imports.map((i) => `${p}${INDENT}${this.importText(i)};`));
      head = p;
    }
    const parameters: any[] = node.parameters ?? [];
    const ports: any[] = node.ports ?? [];
    if (parameters.length > 0) {
      lines.push(head + (head === p ? "#(" : " #("));
      lines.push(...parameters.map((q, i) => `${p}${INDENT}${this.parameterText(q)}${i < parameters.length - 1 ? "," : ""}`));
      head = p + ")";
    }
    const tail = `${p}${end}` + (node.labeled ? ` : ${node.name.spelling}` : "");
    if (ports.length > 0 && ports.every((q) => q instanceof S.PortReference)) { // a non-ANSI header's names, on one line
      const names = ports.map((q) => q.name?.spelling).join(", ");
      lines.push((head.trim() ? head + " (" : head + "(") + names + ");");
      lines.push(...this.items(node.items, level + 1, lines));
      lines.push(tail);
      return lines;
    }
    if (ports.length > 0) {
      lines.push(head.trim() ? head + " (" : head + "(");
      lines.push(...ports.map((q, i) => `${p}${INDENT}${this.port(q)}${i < ports.length - 1 ? "," : ""}`));
      head = p + ")";
    }
    lines.push(head + ";");
    lines.push(...this.items(node.items, level + 1, lines));
    lines.push(tail);
    return lines;
  }

  port(node: any): string {
    if (node instanceof S.PortReference) return node.name?.spelling as string;
    const dimensions = node.dimensions.map((d: any) => this.dimension(d)).join("");
    if (node instanceof S.InterfacePort) {
      const interfaceName = node.interface !== null ? node.interface.spelling : "interface";
      const modport = node.modport !== null ? `.${node.modport.spelling}` : "";
      return `${interfaceName}${modport} ${node.name?.spelling}${dimensions}`;
    }
    const head = joined([node.direction, node.net_type, node.var ? "var" : null,
      node.type !== null ? this.typeText(node.type) : null]);
    const value = node.value !== null ? ` = ${this.text(node.value)}` : "";
    return (head ? head + " " : "") + node.name.spelling + dimensions + value;
  }

  portDeclaration(node: any, level: number): string[] {
    const head = joined([node.direction, node.net_type, node.var ? "var" : null,
      node.type !== null ? this.typeText(node.type) : null]);
    return [pad(level) + head + " " + this.declarators(node.declarators) + ";"];
  }

  // Parameters

  parameterText(node: any): string {
    if (node instanceof S.TypeParameterDeclaration) {
      const assignments = node.assignments.map((a) => a.name?.spelling + (a.type !== null ? ` = ${this.typeText(a.type)}` : ""));
      return joined([node.keyword, "type", assignments.join(", ")]);
    }
    const assignments = node.assignments.map((a: any) => a.name.spelling
      + a.dimensions.map((d: any) => this.dimension(d)).join("") + (a.value !== null ? ` = ${this.text(a.value)}` : ""));
    return joined([node.keyword, node.type !== null ? this.typeText(node.type) : null, assignments.join(", ")]);
  }

  parameter(node: any, level: number): string[] {
    return [pad(level) + this.parameterText(node) + ";"];
  }

  // Data types

  typeText(node: any): string {
    const dimensions = (node.dimensions ?? []).map((d: any) => this.dimension(d)).join("");
    const withDimensions = (text: string) => text + (dimensions ? ` ${dimensions}` : "");
    if (node instanceof S.IntegerVectorType) return withDimensions(joined([node.keyword, node.signing]));
    if (node instanceof S.IntegerAtomType) return joined([node.keyword, node.signing]);
    if (node instanceof S.NonIntegerType || node instanceof S.KeywordType) return node.keyword as string;
    if (node instanceof S.NamedType) return withDimensions(this.name(node.name));
    if (node instanceof S.VirtualInterfaceType) {
      const modport = node.modport !== null ? `.${node.modport.spelling}` : "";
      return `${node.interface_keyword ? "virtual interface" : "virtual"} ${node.interface?.spelling}`
        + `${this.parameterValues(node.parameters)}${modport}`;
    }
    if (node instanceof S.ImplicitType) return joined([node.signing, dimensions]);
    if (node instanceof S.StructType) {
      const head = joined([node.keyword, node.packed ? "packed" : null, node.signing]);
      const members = node.members.map((m) => `${this.typeText(m.type)} ${this.declarators(m.declarators)};`).join(" ");
      return withDimensions(`${head} { ${members} }`);
    }
    const base = node.base !== null ? ` ${this.typeText(node.base)}` : ""; // an EnumType
    const members = node.members.map((m: any) => m.name.spelling + (m.value !== null ? ` = ${this.text(m.value)}` : ""));
    return withDimensions(`enum${base} {${members.join(", ")}}`);
  }

  /** A structure or union over several lines, one member per line. */
  structLines(node: any, level: number): string[] {
    const p = pad(level);
    const head = joined([node.keyword, node.packed ? "packed" : null, node.signing]);
    const lines = [`${head} {`];
    lines.push(...node.members.map((m: any) => `${p}${INDENT}${this.typeText(m.type)} ${this.declarators(m.declarators)};`));
    const dimensions = node.dimensions.map((d: any) => this.dimension(d)).join("");
    lines.push(`${p}}` + (dimensions ? ` ${dimensions}` : ""));
    return lines;
  }

  name(node: any): string {
    if (node instanceof S.ScopedName) return `${this.name(node.scope)}::${this.name(node.name)}`;
    if (node instanceof S.LocalName) return `local::${node.name?.spelling}`;
    if (node instanceof S.ParameterizedName) return node.name?.spelling + this.parameterValues(node.parameters);
    return node.spelling;
  }

  /** ` #(values)`, or nothing without values. */
  parameterValues(parameters: readonly any[]): string {
    return parameters.length > 0 ? " #(" + parameters.map((p) => this.connection(p)).join(", ") + ")" : "";
  }

  dimension(node: any): string {
    if (node instanceof S.RangeDimension) return `[${this.text(node.left)}:${this.text(node.right)}]`;
    if (node instanceof S.SizeDimension) return `[${this.text(node.size)}]`;
    if (node instanceof S.UnsizedDimension) return "[]";
    if (node instanceof S.AssociativeDimension) return `[${node.type !== null ? this.typeText(node.type) : "*"}]`;
    return `[$${node.bound !== null ? `:${this.text(node.bound)}` : ""}]`; // a QueueDimension
  }

  // Declarations

  declarators(declarators: readonly any[]): string {
    return declarators.map((d) => d.name.spelling + d.dimensions.map((x: any) => this.dimension(x)).join("")
      + (d.value !== null ? ` = ${this.text(d.value)}` : "")).join(", ");
  }

  declarationHead(node: any): string {
    if (node instanceof S.NetDeclaration) {
      return joined([node.net_type, node.type !== null ? this.typeText(node.type) : null,
        node.delay !== null ? this.timingText(node.delay) : null]);
    }
    return joined([this.variablePrefix(node), node.type !== null ? this.typeText(node.type) : null]);
  }

  /** What a variable declaration says before its type: `local rand const var static`. */
  variablePrefix(node: any): string {
    return joined([node.visibility, node.random, node.const ? "const" : null, node.var ? "var" : null, node.lifetime]);
  }

  declaration(node: any, level: number): string[] {
    const p = pad(level);
    const kind = node.type;
    if (kind instanceof S.StructType && kind.members.length > 1) {
      const lines = this.structLines(kind, level);
      const prefix = node instanceof S.VariableDeclaration ? this.variablePrefix(node) : node.net_type;
      lines[0] = p + (prefix ? prefix + " " : "") + lines[0];
      lines[lines.length - 1] += " " + this.declarators(node.declarators) + ";";
      return lines;
    }
    return [p + this.declarationHead(node) + " " + this.declarators(node.declarators) + ";"];
  }

  typedef(node: any, level: number): string[] {
    const p = pad(level);
    const dimensions = node.dimensions.map((d: any) => this.dimension(d)).join("");
    if (node.type instanceof S.StructType && node.type.members.length > 1) {
      const lines = this.structLines(node.type, level);
      lines[0] = `${p}typedef ${lines[0]}`;
      lines[lines.length - 1] += ` ${node.name.spelling}${dimensions};`;
      return lines;
    }
    return [`${p}typedef ${this.typeText(node.type)} ${node.name.spelling}${dimensions};`];
  }

  genvar(node: any, level: number): string[] {
    return [`${pad(level)}genvar ${node.names.map((n: any) => n.spelling).join(", ")};`];
  }

  importText(node: any): string {
    return "import " + node.items.map((i: any) => `${i.package.spelling}::${i.name !== null ? i.name.spelling : "*"}`).join(", ");
  }

  importDeclaration(node: any, level: number): string[] {
    return [pad(level) + this.importText(node) + ";"];
  }

  modport(node: any, level: number): string[] {
    const items = node.items.map((i: any) => `${i.name.spelling} (${i.ports.map((p: any) => `${p.direction} ${p.name.spelling}`).join(", ")})`);
    return [`${pad(level)}modport ${items.join(", ")};`];
  }

  continuousAssign(node: any, level: number): string[] {
    const delay = node.delay !== null ? ` ${this.timingText(node.delay)}` : "";
    return [`${pad(level)}assign${delay} ${node.assignments.map((a: any) => this.text(a)).join(", ")};`];
  }

  procedural(node: any, level: number): string[] {
    const keyword = node instanceof S.AlwaysConstruct ? node.keyword : node instanceof S.InitialConstruct ? "initial" : "final";
    return this.headed(pad(level) + keyword, node.body, level);
  }

  subroutine(node: any, level: number): string[] {
    const p = pad(level);
    const task = node instanceof S.TaskDeclaration;
    const parts = [node.extern ? "extern" : null, node.pure ? "pure" : null, node.virtual ? "virtual" : null,
      node.visibility, node.static ? "static" : null, task ? "task" : "function", node.lifetime];
    if (!task && node.type !== null) parts.push(this.typeText(node.type));
    let head = joined(parts) + " " + this.name(node.name);
    if (node.ports.length > 0) head += "(" + node.ports.map((q: any) => this.tfPort(q)).join(", ") + ")";
    const lines = [p + head + ";"];
    if (prototype(node)) return lines;
    lines.push(...this.items(node.body, level + 1, lines));
    lines.push(p + (task ? "endtask" : "endfunction") + (node.labeled ? ` : ${this.name(node.name)}` : ""));
    return lines;
  }

  classDeclaration(node: any, level: number): string[] {
    const p = pad(level);
    const keyword = node.virtual ? "virtual class" : node.interface ? "interface class" : "class";
    let head = `${p}${keyword} ${node.name.spelling}`;
    const lines: string[] = [];
    if (node.parameters.length > 0) {
      lines.push(head + " #(");
      lines.push(...node.parameters.map((q: any, i: number) =>
        `${p}${INDENT}${this.parameterText(q)}${i < node.parameters.length - 1 ? "," : ""}`));
      head = p + ")";
    }
    if (node.base !== null) {
      const args = node.arguments.length > 0 ? `(${node.arguments.map((a: any) => this.connection(a)).join(", ")})` : "";
      head += ` extends ${this.typeText(node.base)}${args}`;
    }
    if (node.interfaces.length > 0) {
      head += ` ${node.interface ? "extends" : "implements"} ` + node.interfaces.map((i: any) => this.typeText(i)).join(", ");
    }
    lines.push(head + ";");
    lines.push(...this.items(node.items, level + 1, lines));
    lines.push(`${p}endclass` + (node.labeled ? ` : ${node.name.spelling}` : ""));
    return lines;
  }

  // Constraints

  constraintDeclaration(node: any, level: number): string[] {
    const lines = [`${pad(level)}${node.static ? "static " : ""}constraint ${this.name(node.name)} {`];
    const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
    return [...lines, ...body, `${pad(level)}}`];
  }

  constraintPrototype(node: any, level: number): string[] {
    return [pad(level) + joined([node.qualifier, node.static ? "static" : null, "constraint", node.name.spelling]) + ";"];
  }

  /** A constraint's lines: a block opens on its header's line, any other body goes on the next. */
  constraint(node: any, level: number): string[] {
    const p = pad(level);
    if (node instanceof S.ConstraintBlock) {
      const lines = [`${p}{`];
      const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
      return [...lines, ...body, `${p}}`];
    }
    if (node instanceof S.ImplicationConstraint) {
      return this.constraintHeaded(`${p}${this.operand(node.condition, IMPLY + 1)} ->`, node.body, level);
    }
    if (node instanceof S.ConditionalConstraint) {
      const lines = this.constraintHeaded(`${p}if (${this.text(node.condition)})`, node.consequence, level);
      if (node.alternative === null) return lines;
      let tail: string[];
      if (node.alternative instanceof S.ConditionalConstraint) { // else if
        tail = this.constraint(node.alternative, level);
        tail[0] = "else " + (tail[0] as string).trim();
      } else {
        tail = this.constraintHeaded("else", node.alternative, level);
      }
      if (node.consequence instanceof S.ConstraintBlock) {
        lines[lines.length - 1] += " " + tail[0];
        return [...lines, ...tail.slice(1)];
      }
      return [...lines, p + tail[0], ...tail.slice(1)];
    }
    if (node instanceof S.ForeachConstraint) {
      const variables = node.variables.map((v) => v.spelling).join(", ");
      return this.constraintHeaded(`${p}foreach (${this.text(node.array)}[${variables}])`, node.body, level);
    }
    return [p + this.constraintText(node)];
  }

  constraintHeaded(head: string, body: any, level: number): string[] {
    if (body instanceof S.ConstraintBlock) {
      const block = this.constraint(body, level);
      return [head + " " + (block[0] as string).trim(), ...block.slice(1)];
    }
    return [head, ...this.constraint(body, level + 1)];
  }

  /** A constraint on one line, as `randomize() with` writes them. */
  constraintText(node: any): string {
    if (node instanceof S.ExpressionConstraint) return `${node.soft ? "soft " : ""}${this.text(node.expression)};`;
    if (node instanceof S.ConstraintBlock) return this.inline(node.items);
    if (node instanceof S.ImplicationConstraint) {
      return `${this.operand(node.condition, IMPLY + 1)} -> ${this.constraintText(node.body)}`;
    }
    if (node instanceof S.ConditionalConstraint) {
      const alternative = node.alternative !== null ? ` else ${this.constraintText(node.alternative)}` : "";
      return `if (${this.text(node.condition)}) ${this.constraintText(node.consequence)}${alternative}`;
    }
    if (node instanceof S.ForeachConstraint) {
      const variables = node.variables.map((v) => v.spelling).join(", ");
      return `foreach (${this.text(node.array)}[${variables}]) ${this.constraintText(node.body)}`;
    }
    if (node instanceof S.SolveBeforeConstraint) {
      return `solve ${node.solve.map((e) => this.text(e)).join(", ")} before ${node.before.map((e) => this.text(e)).join(", ")};`;
    }
    if (node instanceof S.DisableSoftConstraint) return `disable soft ${this.text(node.target)};`;
    return `unique {${node.set.map((r: any) => this.rangeText(r)).join(", ")}};`; // a UniqueConstraint
  }

  /** `{ constraints }` on one line; a line comment, or a directive, ends its line. */
  inline(items: readonly any[]): string {
    const parts = items.map((item) => {
      if (item instanceof S.Comment) return this.comment(item) + (item.block ? "" : "\n");
      if (item instanceof S.Directive) return "\n" + this.directive(item, 0).join("\n") + "\n";
      return this.constraintText(item);
    });
    let text = "{";
    for (const part of [...parts, "}"]) { // a space between parts, but not at a line's end or start
      text += text.endsWith("\n") || part.startsWith("\n") ? part : " " + part;
    }
    return parts.length > 0 ? text : "{}";
  }

  forwardTypedef(node: any, level: number): string[] {
    return [`${pad(level)}typedef ${node.keyword ? `${node.keyword} ` : ""}${node.name.spelling};`];
  }

  tfPort(node: any): string {
    const text = joined([node.direction, node.var ? "var" : null, node.type !== null ? this.typeText(node.type) : null,
      node.name.spelling + node.dimensions.map((d: any) => this.dimension(d)).join("")]);
    return text + (node.value !== null ? ` = ${this.text(node.value)}` : "");
  }

  // Generate constructs

  generateRegion(node: any, level: number): string[] {
    const lines = [`${pad(level)}generate`];
    const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
    return [...lines, ...body, `${pad(level)}endgenerate`];
  }

  generateFor(node: any, level: number): string[] {
    const head = `${pad(level)}for (${node.genvar ? "genvar " : ""}${node.name.spelling} = ${this.text(node.start)}; `
      + `${this.text(node.condition)}; ${this.text(node.step)})`;
    return this.generateHeaded(head, node.body, level);
  }

  generateIf(node: any, level: number): string[] {
    const lines = this.generateHeaded(`${pad(level)}if (${this.text(node.condition)})`, node.consequence, level);
    const alternative = node.alternative;
    if (alternative === null) return lines;
    let tail: string[];
    if (alternative instanceof S.GenerateIf) { // else if
      tail = this.generateIf(alternative, level);
      tail[0] = "else " + (tail[0] as string).trim();
    } else {
      tail = this.generateHeaded("else", alternative, level);
    }
    if (node.consequence instanceof S.GenerateBlock) {
      lines[lines.length - 1] += " " + tail[0];
      return [...lines, ...tail.slice(1)];
    }
    return [...lines, pad(level) + tail[0], ...tail.slice(1)];
  }

  generateCase(node: any, level: number): string[] {
    const p = pad(level);
    const lines = [`${p}case (${this.text(node.expression)})`];
    for (const item of node.items) {
      const label = item.expressions.length > 0 ? item.expressions.map((e: any) => this.text(e)).join(", ") : "default";
      lines.push(...this.generateHeaded(`${p}${INDENT}${label}:`, item.body, level + 1));
    }
    lines.push(`${p}endcase`);
    return lines;
  }

  /** `head body`: a block opens on the header's line, any other item goes on the next. */
  generateHeaded(head: string, body: any, level: number): string[] {
    if (body instanceof S.GenerateBlock) {
      const block = this.generateBlock(body, level);
      return [head + " " + (block[0] as string).trim(), ...block.slice(1)];
    }
    return [head, ...this.item(body, level + 1)];
  }

  generateBlock(node: any, level: number): string[] {
    const name = node.name !== null ? ` : ${node.name.spelling}` : "";
    const end = node.labeled && node.name !== null ? ` : ${node.name.spelling}` : "";
    const lines = [`${pad(level)}begin${name}`];
    const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
    return [...lines, ...body, `${pad(level)}end${end}`];
  }

  // Instantiation

  instantiation(node: any, level: number): string[] {
    const parameters = this.parameterValues(node.parameters);
    const instances = node.instances.map((i: any) => i.name.spelling + i.dimensions.map((d: any) => this.dimension(d)).join("")
      + " (" + i.connections.map((c: any) => this.connection(c)).join(", ") + ")").join(", ");
    return [`${pad(level)}${node.module.spelling}${parameters} ${instances};`];
  }

  connection(node: any): string {
    if (node instanceof S.WildcardConnection) return ".*";
    if (node instanceof S.NamedConnection) {
      if (node.implicit) return `.${node.name?.spelling}`;
      const value = node.value === null ? "" : this.typeOrText(node.value);
      return `.${node.name?.spelling}(${value})`;
    }
    return this.typeOrText(node);
  }

  typeOrText(node: any): string {
    return node instanceof S.DataType ? this.typeText(node) : this.text(node);
  }

  // Statements

  /** `head body`: a block opens on the header's line, a null statement ends it, and any other statement goes on the
   * next line, one level in. */
  headed(head: string, body: any, level: number): string[] {
    if (isAny(body, [S.SeqBlock, S.ParBlock, S.TimedStatement])) {
      const lines = this.statement(body, level);
      return [head + " " + (lines[0] as string).trim(), ...lines.slice(1)];
    }
    if (body instanceof S.NullStatement) return [head + ";"];
    return [head, ...this.statement(body, level + 1)];
  }

  statement(node: any, level: number): string[] {
    const method = Printer.STATEMENTS.get(node.constructor);
    if (method !== undefined) return method(this, node, level);
    return [pad(level) + this.simple(node)];
  }

  simple(node: any): string {
    if (node instanceof S.AssignmentStatement) {
      const timing = node.timing !== null ? `${this.timingText(node.timing)} ` : "";
      return `${this.text(node.target)} ${node.operator} ${timing}${this.text(node.value)};`;
    }
    if (node instanceof S.ExpressionStatement) return this.text(node.expression) + ";";
    if (node instanceof S.NullStatement) return ";";
    if (node instanceof S.BreakStatement) return "break;";
    if (node instanceof S.ContinueStatement) return "continue;";
    if (node instanceof S.ReturnStatement) return "return" + (node.value !== null ? ` ${this.text(node.value)}` : "") + ";";
    if (node instanceof S.EventTrigger) return `${node.nonblocking ? "->>" : "->"} ${this.text(node.event)};`;
    return `disable ${node.target !== null ? this.text(node.target) : "fork"};`; // a DisableStatement
  }

  block(node: any, level: number): string[] {
    const opener = node instanceof S.SeqBlock ? "begin" : "fork";
    const closer = node instanceof S.SeqBlock ? "end" : node.join;
    const name = node.name !== null ? ` : ${node.name.spelling}` : "";
    const end = node.labeled && node.name !== null ? ` : ${node.name.spelling}` : "";
    const lines = [`${pad(level)}${opener}${name}`];
    const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
    return [...lines, ...body, `${pad(level)}${closer}${end}`];
  }

  ifStatement(node: any, level: number, head: string | null = null): string[] {
    const p = pad(level);
    const qualifier = node.qualifier ? `${node.qualifier} ` : "";
    const start = (head !== null ? head : p) + `${qualifier}if (${this.text(node.condition)})`;
    const lines = this.headed(start, node.consequence, level);
    const alternative = node.alternative;
    if (alternative === null) return lines;
    const block = isAny(node.consequence, [S.SeqBlock, S.ParBlock]);
    if (alternative instanceof S.IfStatement && alternative.qualifier === null) {
      if (block) {
        const tail = this.ifStatement(alternative, level, "else ");
        lines[lines.length - 1] += " " + tail[0];
        return [...lines, ...tail.slice(1)];
      }
      return [...lines, ...this.ifStatement(alternative, level, p + "else ")];
    }
    if (block) {
      const tail = this.headed("else", alternative, level);
      lines[lines.length - 1] += " " + tail[0];
      return [...lines, ...tail.slice(1)];
    }
    return [...lines, ...this.headed(p + "else", alternative, level)];
  }

  case(node: any, level: number): string[] {
    const p = pad(level);
    const qualifier = node.qualifier ? `${node.qualifier} ` : "";
    const lines = [`${p}${qualifier}${node.keyword} (${this.text(node.expression)})${node.inside ? " inside" : ""}`];
    for (const item of node.items) {
      const label = item.expressions.length > 0 ? item.expressions.map((e: any) => this.rangeText(e)).join(", ") : "default";
      lines.push(...this.caseItem(`${p}${INDENT}${label}:`, item.body, level));
    }
    lines.push(`${p}endcase`);
    return lines;
  }

  /** `label: body`: a null statement, a block or a one-line statement on the label's line, else on the next. */
  caseItem(head: string, body: any, level: number): string[] {
    if (body instanceof S.NullStatement) return [`${head} ;`];
    if (isAny(body, [S.SeqBlock, S.ParBlock])) return this.headed(head, body, level + 1);
    if (body instanceof S.Statement && this.statement(body, 0).length === 1) return [`${head} ${this.statement(body, 0)[0]}`];
    return this.headed(head, body, level + 1);
  }

  randcase(node: any, level: number): string[] {
    const p = pad(level);
    const lines = [`${p}randcase`];
    for (const item of node.items) lines.push(...this.caseItem(`${p}${INDENT}${this.text(item.weight)}:`, item.body, level));
    lines.push(`${p}endcase`);
    return lines;
  }

  loop(node: any, level: number): string[] {
    const p = pad(level);
    if (node instanceof S.ForStatement) {
      const initializers = node.initializers.map((i) => this.forInitializer(i)).join(", ");
      const condition = node.condition !== null ? this.text(node.condition) : "";
      const steps = node.steps.map((s) => this.text(s)).join(", ");
      return this.headed(`${p}for (${initializers}; ${condition}; ${steps})`, node.body, level);
    }
    if (node instanceof S.WhileStatement) return this.headed(`${p}while (${this.text(node.condition)})`, node.body, level);
    if (node instanceof S.RepeatStatement) return this.headed(`${p}repeat (${this.text(node.count)})`, node.body, level);
    if (node instanceof S.ForeverStatement) return this.headed(`${p}forever`, node.body, level);
    if (node instanceof S.ForeachStatement) {
      const variables = node.variables.map((v) => v.spelling).join(", ");
      return this.headed(`${p}foreach (${this.text(node.array)}[${variables}])`, node.body, level);
    }
    const lines = this.headed(`${p}do`, node.body, level); // a DoWhileStatement
    const tail = `while (${this.text(node.condition)});`;
    if (isAny(node.body, [S.SeqBlock, S.ParBlock])) {
      lines[lines.length - 1] += " " + tail;
    } else {
      lines.push(p + tail);
    }
    return lines;
  }

  forInitializer(node: any): string {
    if (node instanceof S.VariableDeclaration) {
      const head = this.declarationHead(node);
      return (head ? head + " " : "") + this.declarators(node.declarators);
    }
    return this.text(node);
  }

  timed(node: any, level: number): string[] {
    const head = pad(level) + this.timingText(node.timing);
    if (node.body === null) return [head + ";"];
    if (isAny(node.body, [S.SeqBlock, S.ParBlock])) return this.headed(head, node.body, level);
    const inner = this.statement(node.body, 0);
    if (inner.length === 1) return [`${head} ${inner[0]}`];
    return this.headed(head, node.body, level);
  }

  wait(node: any, level: number): string[] {
    const head = `${pad(level)}wait (${this.text(node.condition)})`;
    if (node.body === null) return [head + ";"];
    const inner = this.statement(node.body, 0);
    if (inner.length === 1 && !isAny(node.body, [S.SeqBlock, S.ParBlock])) return [`${head} ${inner[0]}`];
    return this.headed(head, node.body, level);
  }

  assertion(node: any, level: number): string[] {
    const deferral = node.deferral ? ` ${node.deferral}` : "";
    return this.actions(`${pad(level)}${node.keyword}${deferral} (${this.text(node.expression)})`, node, level);
  }

  concurrent(node: any, level: number): string[] {
    return this.actions(`${pad(level)}${node.keyword} ${node.sequence ? "sequence" : "property"} (${this.spec(node.spec)})`,
      node, level);
  }

  expect(node: any, level: number): string[] {
    return this.actions(`${pad(level)}expect (${this.spec(node.spec)})`, node, level);
  }

  labeled(node: any, level: number): string[] {
    const lines = this.statement(node.statement, level);
    return [`${pad(level)}${node.label.spelling}: ${(lines[0] as string).trim()}`, ...lines.slice(1)];
  }

  /** An assertion's head, then what passes and after `else` what fails. */
  actions(head: string, node: any, level: number): string[] {
    if (node.pass_action === null && node.fail_action === null) return [head + ";"];
    let lines: string[];
    if (node.pass_action !== null) {
      const inner = this.statement(node.pass_action, 0);
      lines = inner.length === 1 ? [`${head} ${inner[0]}`] : this.headed(head, node.pass_action, level);
    } else {
      lines = [head];
    }
    if (node.fail_action !== null) {
      const inner = this.statement(node.fail_action, 0);
      if (inner.length === 1) {
        lines[lines.length - 1] += ` else ${inner[0]}`;
      } else {
        const tail = this.headed("else", node.fail_action, level);
        lines[lines.length - 1] += " " + tail[0];
        lines.push(...tail.slice(1));
      }
    }
    return lines;
  }

  // Assertions

  assertionItem(node: any, level: number): string[] {
    const lines = this.statement(node.assertion, level);
    if (node.label !== null) lines[0] = `${pad(level)}${node.label.spelling}: ${(lines[0] as string).trim()}`;
    return lines;
  }

  /** `@(clock) disable iff (disable) property`. */
  spec(node: any): string {
    return joined([node.clock !== null ? this.timingText(node.clock) : null,
      node.disable !== null ? `disable iff (${this.text(node.disable)})` : null, this.text(node.property)]);
  }

  /** `(ports)`, or nothing without ports. */
  assertionPorts(ports: readonly any[]): string {
    if (ports.length === 0) return "";
    return "(" + ports.map((q) => joined([q.local ? "local" : null, q.direction, q.type !== null ? this.typeText(q.type) : null,
      q.name.spelling + q.dimensions.map((d: any) => this.dimension(d)).join("")])
      + (q.value !== null ? ` = ${this.text(q.value)}` : "")).join(", ") + ")";
  }

  assertionDeclaration(node: any, level: number): string[] {
    const p = pad(level);
    const keyword = node instanceof S.PropertyDeclaration ? "property" : "sequence";
    const lines = [`${p}${keyword} ${node.name.spelling}${this.assertionPorts(node.ports)};`];
    lines.push(...node.variables.map((v: any) => this.declaration(v, level + 1)[0]));
    const body = node instanceof S.PropertyDeclaration ? this.spec(node.spec) : this.text(node.sequence);
    lines.push(`${p}${INDENT}${body};`);
    lines.push(`${p}end${keyword}` + (node.labeled ? ` : ${node.name.spelling}` : ""));
    return lines;
  }

  letDeclaration(node: any, level: number): string[] {
    return [`${pad(level)}let ${node.name.spelling}${this.assertionPorts(node.ports)} = ${this.text(node.value)};`];
  }

  /** A number of ticks or repetitions, or `low:high`. */
  cycles(node: any): string {
    return node instanceof S.CycleRange ? `${this.text(node.low)}:${this.text(node.high)}` : this.text(node);
  }

  delayStep(node: any, last: boolean): string {
    const delay = node.delay;
    let text: string;
    if (delay instanceof S.CycleRange) {
      text = `##[${this.cycles(delay)}]`;
    } else {
      const simple = isAny(delay, [S.IntegerLiteral, S.NameExpression, S.ParenthesizedExpression, S.MacroUsage]);
      text = simple ? `##${this.text(delay)}` : `##(${this.text(delay)})`;
    }
    return `${text} ${this.part(node.sequence, DELAY + 1, last)}`;
  }

  /** An operand of a sequence or property operator, in parentheses where it would bind otherwise. One that reaches as
   * far right as it can (`always p`, `if`, `@(clock) p`) needs none where nothing follows it: `last`. */
  part(node: any, level: number, last: boolean): string {
    if (!isAny(node, [S.Sequence, S.Property])) return this.operand(node, level);
    if (precedence(node) === TEMPORAL && last || precedence(node) >= level) return this.propertyText(node, last);
    return `(${this.propertyText(node)})`;
  }

  /** A sequence or a property; `last` when nothing follows it. */
  propertyText(node: any, last = true): string {
    if (node instanceof S.DelaySequence) {
      const first = node.first !== null ? `${this.part(node.first, DELAY, false)} ` : "";
      return first + node.steps.map((s, i) => this.delayStep(s, last && i === node.steps.length - 1)).join(" ");
    }
    if (node instanceof S.RepetitionSequence) {
      return `${this.part(node.sequence, REPEAT, false)}[${node.operator}${this.cycles(node.count)}]`;
    }
    if (isAny(node, [S.BinarySequence, S.BinaryProperty])) {
      const level = precedence(node);
      const [left, right] = RIGHT.has(level) ? [level + 1, level] : [level, level + 1];
      return `${this.part(node.left, left, false)} ${node.operator} ${this.part(node.right, right, last)}`;
    }
    if (isAny(node, [S.ParenthesizedSequence, S.FirstMatchSequence])) {
      const inner = [this.text(node.sequence), ...node.items.map((i: any) => this.text(i))].join(", ");
      return node instanceof S.FirstMatchSequence ? `first_match(${inner})` : `(${inner})`;
    }
    if (node instanceof S.ClockedSequence) return `${this.timingText(node.clock)} ${this.part(node.sequence, TEMPORAL, last)}`;
    if (node instanceof S.ClockedProperty) return `${this.timingText(node.clock)} ${this.part(node.property, TEMPORAL, last)}`;
    if (node instanceof S.ImplicationProperty) {
      return `${this.part(node.antecedent, IMPLICATION + 1, false)} ${node.operator} `
        + `${this.part(node.consequent, IMPLICATION, last)}`;
    }
    if (node instanceof S.UnaryProperty) {
      const cycles = node.range !== null ? ` [${this.cycles(node.range)}]` : "";
      return `${node.operator}${cycles} ${this.part(node.operand, precedence(node), last)}`;
    }
    if (node instanceof S.StrengthProperty) return `${node.keyword}(${this.text(node.sequence)})`;
    if (node instanceof S.AbortProperty) {
      return `${node.keyword} (${this.text(node.condition)}) ${this.part(node.operand, TEMPORAL, last)}`;
    }
    if (node instanceof S.ConditionalProperty) {
      if (node.alternative === null) return `if (${this.text(node.condition)}) ${this.part(node.consequence, TEMPORAL, last)}`;
      return `if (${this.text(node.condition)}) ${this.part(node.consequence, TEMPORAL + 1, false)} `
        + `else ${this.part(node.alternative, TEMPORAL, last)}`;
    }
    if (node instanceof S.CaseProperty) {
      const items = node.items.map((i: any) => (i.expressions.length > 0 ? i.expressions.map((e: any) => this.text(e)).join(", ")
        : "default") + `: ${this.text(i.body)};`).join(" ");
      return `case (${this.text(node.expression)}) ${items} endcase`;
    }
    return `(${this.text(node.property)})`; // a ParenthesizedProperty
  }

  // Clocking blocks

  clockingDeclaration(node: any, level: number): string[] {
    const p = pad(level);
    const name = node.name !== null ? ` ${node.name.spelling}` : "";
    const lines = [`${p}${node.scope ? `${node.scope} ` : ""}clocking${name} ${this.timingText(node.clock)};`];
    const body = this.items(node.items, level + 1, lines); // after `lines` takes a trailing comment
    const end = node.labeled && node.name !== null ? ` : ${node.name.spelling}` : "";
    return [...lines, ...body, `${p}endclocking${end}`];
  }

  skew(node: any): string | null {
    if (node === null) return null;
    return joined([node.edge, node.delay !== null ? this.timingText(node.delay) : null]);
  }

  defaultSkew(node: any, level: number): string[] {
    const words = ["default", ...(node.input !== null ? ["input", this.skew(node.input)] : []),
      ...(node.output !== null ? ["output", this.skew(node.output)] : [])];
    return [pad(level) + joined(words) + ";"];
  }

  clockingSignals(node: any, level: number): string[] {
    const words: (string | null)[] = [];
    if (node.direction === "input" || node.direction === "input output") words.push("input", this.skew(node.input_skew));
    if (node.direction === "output" || node.direction === "input output") words.push("output", this.skew(node.output_skew));
    if (node.direction === "inout") words.push("inout");
    const signals = node.signals.map((s: any) => s.name.spelling + (s.value !== null ? ` = ${this.text(s.value)}` : "")).join(", ");
    return [pad(level) + joined(words) + ` ${signals};`];
  }

  defaultClocking(node: any, level: number): string[] {
    return [`${pad(level)}default clocking ${node.name.spelling};`];
  }

  defaultDisable(node: any, level: number): string[] {
    return [`${pad(level)}default disable iff ${this.text(node.condition)};`];
  }

  // Timing controls

  timingText(node: any): string {
    if (node instanceof S.DelayControl) {
      const value = node.value;
      const text = this.text(value);
      const simple = isAny(value, [S.IntegerLiteral, S.RealLiteral, S.TimeLiteral, S.NameExpression,
        S.ParenthesizedExpression, S.MacroUsage]);
      return simple ? `#${text}` : `#(${text})`;
    }
    if (node instanceof S.CycleDelay) {
      const simple = isAny(node.value, [S.IntegerLiteral, S.NameExpression, S.ParenthesizedExpression, S.MacroUsage]);
      return simple ? `##${this.text(node.value)}` : `##(${this.text(node.value)})`;
    }
    if (node.events.length === 0) return "@(*)";
    return "@(" + node.events.map((e: any) => this.event(e)).join(" or ") + ")";
  }

  event(node: any): string {
    const text = (node.edge ? `${node.edge} ` : "") + this.text(node.expression);
    return text + (node.condition !== null ? ` iff ${this.text(node.condition)}` : "");
  }

  // Expressions

  rangeText(node: any): string {
    if (node instanceof S.ValueRange) return `[${this.text(node.left)}:${this.text(node.right)}]`;
    return this.text(node);
  }

  operand(node: any, level: number): string {
    const text = this.text(node);
    return precedence(node) < level ? `(${text})` : text;
  }

  text(node: any): string {
    if (node instanceof S.NameExpression) return this.name(node.name);
    if (node instanceof S.MemberExpression) return `${this.operand(node.value, PRIMARY)}.${node.member?.spelling}`;
    if (node instanceof S.IndexExpression) return `${this.operand(node.value, PRIMARY)}[${this.text(node.index)}]`;
    if (node instanceof S.RangeSelect) {
      const operator = node.operator === ":" ? node.operator : ` ${node.operator} `;
      return `${this.operand(node.value, PRIMARY)}[${this.text(node.left)}${operator}${this.text(node.right)}]`;
    }
    if (isAny(node, [S.IntegerLiteral, S.RealLiteral, S.TimeLiteral])) return node.spelling;
    if (node instanceof S.UnbasedUnsizedLiteral) return `'${node.value}`;
    if (node instanceof S.StringLiteral) return node.triple ? `"""${node.text}"""` : `"${node.text}"`;
    if (node instanceof S.UnaryExpression) {
      let operand = this.operand(node.operand, UNARY + 1);
      if (isAny(node.operand, [S.UnaryExpression, S.IncrementExpression])) operand = `(${this.text(node.operand)})`;
      return `${node.operator}${operand}`;
    }
    if (node instanceof S.IncrementExpression) {
      const operand = this.operand(node.operand, PRIMARY);
      return node.postfix ? `${operand}${node.operator}` : `${node.operator}${operand}`;
    }
    if (node instanceof S.BinaryExpression) {
      const level = BINARY[node.operator as string] as number;
      const [left, right] = RIGHT.has(level) ? [level + 1, level] : [level, level + 1];
      return `${this.operand(node.left, left)} ${node.operator} ${this.operand(node.right, right)}`;
    }
    if (node instanceof S.AssignmentExpression) return `${this.text(node.target)} ${node.operator} ${this.text(node.value)}`;
    if (node instanceof S.ConditionalExpression) {
      return `${this.operand(node.condition, CONDITIONAL + 1)} ? ${this.operand(node.consequence, CONDITIONAL + 1)}`
        + ` : ${this.operand(node.alternative, CONDITIONAL)}`;
    }
    if (node instanceof S.InsideExpression) {
      return `${this.operand(node.value, RELATIONAL + 1)} inside {${node.set.map((r) => this.rangeText(r)).join(", ")}}`;
    }
    if (node instanceof S.Concatenation) return "{" + node.items.map((i) => this.text(i)).join(", ") + "}";
    if (node instanceof S.Replication) {
      return `{${this.operand(node.count, PRIMARY)}{${node.items.map((i) => this.text(i)).join(", ")}}}`;
    }
    if (node instanceof S.AssignmentPattern) {
      const prefix = node.type !== null ? this.typeText(node.type) : "";
      return `${prefix}'{${node.items.map((i) => this.patternItem(i)).join(", ")}}`;
    }
    if (node instanceof S.CallExpression) {
      return `${this.operand(node.callee, PRIMARY)}(${node.arguments.map((a) => this.connection(a)).join(", ")})`;
    }
    if (node instanceof S.SystemCall) {
      if (node.arguments.length === 0) return node.name as string;
      return `${node.name}(${node.arguments.map((a) => this.typeOrText(a)).join(", ")})`;
    }
    if (node instanceof S.CastExpression) {
      const target = node.type instanceof S.DataType ? this.typeText(node.type) : this.operand(node.type, PRIMARY);
      return `${target}'(${this.text(node.value)})`;
    }
    if (node instanceof S.ParenthesizedExpression) return `(${this.text(node.expression)})`;
    if (node instanceof S.MacroUsage) return `\`${node.name?.spelling}` + (node.arguments !== null ? `(${node.arguments})` : "");
    if (node instanceof S.DollarExpression) return "$";
    if (node instanceof S.NullLiteral) return "null";
    if (isAny(node, [S.Sequence, S.Property])) return this.propertyText(node);
    if (node instanceof S.DistExpression) {
      const items = node.items.map((i: any) => (i.value !== null ? this.rangeText(i.value) : "default")
        + (i.operator !== null ? ` ${i.operator} ${this.text(i.weight)}` : "")).join(", ");
      return `${this.operand(node.value, RELATIONAL)} dist {${items}}`;
    }
    if (node instanceof S.RandomizeWithExpression) {
      const variables = node.restricted ? ` (${node.variables.map((v) => v.spelling).join(", ")})` : "";
      return `${this.operand(node.call, PRIMARY)} with${variables} ${this.inline(node.items)}`;
    }
    if (node instanceof S.ArrayMethodWithExpression) {
      return `${this.operand(node.call, PRIMARY)} with (${this.text(node.expression)})`;
    }
    if (node instanceof S.ThisExpression) return "this";
    if (node instanceof S.SuperExpression) return "super";
    if (node instanceof S.NewExpression) {
      const scope = node.scope instanceof S.SuperExpression ? "super." : node.scope !== null ? this.name(node.scope) + "::" : "";
      const args = node.arguments.length > 0 ? `(${node.arguments.map((a) => this.connection(a)).join(", ")})` : "";
      return `${scope}new${args}`;
    }
    if (node instanceof S.NewCopyExpression) return `new ${this.operand(node.value, PRIMARY)}`;
    if (node instanceof S.NewArrayExpression) {
      return `new[${this.text(node.size)}]${node.value !== null ? `(${this.text(node.value)})` : ""}`;
    }
    return node instanceof S.Port ? this.port(node) : node instanceof S.Dimension ? this.dimension(node) : this.typeText(node);
  }

  patternItem(node: any): string {
    if (!(node instanceof S.PatternItem)) return this.text(node);
    const key = node.key === null ? "default" : this.typeOrText(node.key);
    return `${key}: ${this.text(node.value)}`;
  }
}

const items: [Function[], Method][] = [
  [[S.ModuleDeclaration, S.InterfaceDeclaration, S.ProgramDeclaration, S.PackageDeclaration], (s, n, l) => s.designUnit(n, l)],
  [[S.PortDeclaration], (s, n, l) => s.portDeclaration(n, l)],
  [[S.ParameterDeclaration, S.TypeParameterDeclaration], (s, n, l) => s.parameter(n, l)],
  [[S.NetDeclaration, S.VariableDeclaration], (s, n, l) => s.declaration(n, l)],
  [[S.TypedefDeclaration], (s, n, l) => s.typedef(n, l)],
  [[S.GenvarDeclaration], (s, n, l) => s.genvar(n, l)],
  [[S.ImportDeclaration], (s, n, l) => s.importDeclaration(n, l)],
  [[S.ModportDeclaration], (s, n, l) => s.modport(n, l)],
  [[S.ContinuousAssign], (s, n, l) => s.continuousAssign(n, l)],
  [[S.AlwaysConstruct, S.InitialConstruct, S.FinalConstruct], (s, n, l) => s.procedural(n, l)],
  [[S.FunctionDeclaration, S.TaskDeclaration], (s, n, l) => s.subroutine(n, l)],
  [[S.GenerateRegion], (s, n, l) => s.generateRegion(n, l)],
  [[S.GenerateFor], (s, n, l) => s.generateFor(n, l)],
  [[S.GenerateIf], (s, n, l) => s.generateIf(n, l)],
  [[S.GenerateCase], (s, n, l) => s.generateCase(n, l)],
  [[S.GenerateBlock], (s, n, l) => s.generateBlock(n, l)],
  [[S.ModuleInstantiation], (s, n, l) => s.instantiation(n, l)],
  [[S.ClassDeclaration], (s, n, l) => s.classDeclaration(n, l)],
  [[S.ForwardTypedefDeclaration], (s, n, l) => s.forwardTypedef(n, l)],
  [[S.ConstraintDeclaration], (s, n, l) => s.constraintDeclaration(n, l)],
  [[S.ConstraintPrototype], (s, n, l) => s.constraintPrototype(n, l)],
  [[S.AssertionItem], (s, n, l) => s.assertionItem(n, l)],
  [[S.PropertyDeclaration, S.SequenceDeclaration], (s, n, l) => s.assertionDeclaration(n, l)],
  [[S.LetDeclaration], (s, n, l) => s.letDeclaration(n, l)],
  [[S.ClockingDeclaration], (s, n, l) => s.clockingDeclaration(n, l)],
  [[S.DefaultSkew], (s, n, l) => s.defaultSkew(n, l)],
  [[S.ClockingSignals], (s, n, l) => s.clockingSignals(n, l)],
  [[S.DefaultClocking], (s, n, l) => s.defaultClocking(n, l)],
  [[S.DefaultDisable], (s, n, l) => s.defaultDisable(n, l)],
];
for (const [kinds, method] of items) for (const kind of kinds) Printer.ITEMS.set(kind, method);
const statements: [Function[], Method][] = [
  [[S.SeqBlock, S.ParBlock], (s, n, l) => s.block(n, l)],
  [[S.IfStatement], (s, n, l) => s.ifStatement(n, l)],
  [[S.CaseStatement], (s, n, l) => s.case(n, l)],
  [[S.ForStatement, S.WhileStatement, S.RepeatStatement, S.ForeverStatement, S.ForeachStatement, S.DoWhileStatement],
    (s, n, l) => s.loop(n, l)],
  [[S.TimedStatement], (s, n, l) => s.timed(n, l)],
  [[S.WaitStatement], (s, n, l) => s.wait(n, l)],
  [[S.ImmediateAssertion], (s, n, l) => s.assertion(n, l)],
  [[S.RandCaseStatement], (s, n, l) => s.randcase(n, l)],
  [[S.ConcurrentAssertion], (s, n, l) => s.concurrent(n, l)],
  [[S.ExpectStatement], (s, n, l) => s.expect(n, l)],
  [[S.LabeledStatement], (s, n, l) => s.labeled(n, l)],
];
for (const [kinds, method] of statements) for (const kind of kinds) Printer.STATEMENTS.set(kind, method);
