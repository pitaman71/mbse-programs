/** mbse-programs: programs as language-neutral data.
 *
 * Complete abstract syntax trees for programming languages, as plain in-memory objects that serialize through
 * mbse-schemas, with the entities they declare, and standards that parse source text into trees and print trees into
 * source text. A transpiler written against these trees never parses or prints strings. See docs/PROGRAMS.md at
 * https://github.com/pitaman71/mbse-programs.
 *
 * The framework is `@mbse/programs/Framework`, and the languages are modules beside it: `@mbse/programs/Ccpp` for C
 * and C++, `@mbse/programs/Python` for Python, and `@mbse/programs/TypeScript` for TypeScript and JavaScript.
 * `@mbse/programs/Transpilers` translates between them, and `@mbse/programs/Bridges` between them and mbse-expressions'
 * dialects.
 *
 * For AI agents: read `skill/SKILL.md` at the root of this package first. It says when to use this package, the rules
 * that prevent most mistakes, and which reference to load for a task. */

export * as Bridges from "./Bridges/index.js";
export * as Ccpp from "./Ccpp/index.js";
export * as Framework from "./Framework/index.js";
export * as Python from "./Python/index.js";
export * as Transpilers from "./Transpilers/index.js";
export * as TypeScript from "./TypeScript/index.js";
