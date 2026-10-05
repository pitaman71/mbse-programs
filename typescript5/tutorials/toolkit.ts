/**
 * What the case studies share: `outline`, which shows a tree one syntax node per line.
 *
 * Each line is a syntax node's kind and the attributes it has set, under the property of its parent that holds it, such
 * as `left: Name` under a `BinOp`. Case study 1 explains attributes and children.
 */

import { Attribute, children, type SyntaxNode } from "@mbse/programs/Framework/Syntax";

const value = (v: unknown) => (typeof v === "string" ? `'${v}'` : String(v));

/** The tree under `node`, one syntax node per line, indented by depth. */
export function outline(node: SyntaxNode, label = "", depth = 0): string {
  const attributes = node.kind().PROPERTIES
    .filter((p) => p instanceof Attribute && ![null, false, ""].includes(node.get(p.name) as any))
    .map((p) => `${p.name}=${value(node.get(p.name))}`).join(", ");
  const lines = ["  ".repeat(depth) + label + node.kind().KIND + (attributes ? `(${attributes})` : "")];
  for (const [prop, index, child] of children(node)) {
    lines.push(outline(child, `${prop}${index === null ? "" : `[${index}]`}: `, depth + 1));
  }
  return lines.join("\n");
}
