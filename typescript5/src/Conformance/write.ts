/**
 * Writes this implementation's conformance files: `npm run conformance [directory]`.
 *
 * For each source in `conformance/sources`, it writes the tree the source parses to, as a JSON snapshot
 * (`<source>.json`), and the text that tree prints to (`<source>.cpp`); and it writes each language's grammar
 * (`<language>.grammar.json`). Every implementation must write the same bytes. The default directory is
 * `conformance/typescript5` at the repository root.
 */

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { JSON as SchemaJSON } from "@mbse/schemas/Framework";

import * as Ccpp20 from "../Ccpp/Ccpp20.js";
import * as Syntax from "../Ccpp/Syntax.js";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../conformance");
const STANDARDS: Record<string, typeof Ccpp20> = { ".cpp": Ccpp20 };

/** File name -> text, for every file this implementation writes. */
export function render(sources: string = join(ROOT, "sources")): Map<string, string> {
  const files = new Map<string, string>([["Ccpp.grammar.json", JSON.stringify(Syntax.LANGUAGE.grammar(), null, 1) + "\n"]]);
  for (const name of readdirSync(sources).sort()) {
    const suffix = extname(name);
    const standard = STANDARDS[suffix] as typeof Ccpp20;
    const unit = standard.parse(readFileSync(join(sources, name), "utf8"));
    const stem = name.slice(0, -suffix.length);
    files.set(`${stem}.json`, SchemaJSON.ToJSON.Reachable(Syntax.TranslationUnit.Schema, unit, { indent: 2 }) + "\n");
    files.set(`${stem}${suffix}`, standard.print(unit));
  }
  return files;
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = process.argv[2] ?? join(ROOT, "typescript5");
  mkdirSync(directory, { recursive: true });
  for (const [name, text] of render()) {
    writeFileSync(join(directory, name), text, "utf8");
    console.log("wrote", join(directory, name));
  }
}
