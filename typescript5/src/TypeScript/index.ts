/** TypeScript and JavaScript as one tree language: the abstract syntax (`Syntax`), the names a program declares
 * (`Definitions`), and the standards that parse and print source text (`TypeScript50`, `TypeScript59`,
 * `ECMAScript2020`, `ECMAScript2025`, each with a `JSX` variant). */

export * as Definitions from "./Definitions.js";
export * as ECMAScript2020 from "./ECMAScript2020.js";
export * as ECMAScript2025 from "./ECMAScript2025.js";
export * as Syntax from "./Syntax.js";
export * as TypeScript50 from "./TypeScript50.js";
export * as TypeScript59 from "./TypeScript59.js";
export { TypeScriptStandard, ECMAScriptStandard } from "./_Standard.js";
