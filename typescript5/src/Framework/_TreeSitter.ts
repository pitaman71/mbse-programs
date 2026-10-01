/** web-tree-sitter, initialized once for every language: initializing it again would break the parsers made before. */

import { createRequire } from "node:module";

import { Language as Grammar, Parser } from "web-tree-sitter";

await Parser.init();

/** A parser for the grammar in the npm package's wasm file, such as `tree-sitter-cpp/tree-sitter-cpp.wasm`. */
export async function parser(wasm: string): Promise<Parser> {
  const made = new Parser();
  made.setLanguage(await Grammar.load(createRequire(import.meta.url).resolve(wasm)));
  return made;
}
