// Generate TypeScript types from the exported Pydantic JSON Schema bundle.
// Run via `corepack pnpm types` (or `uv run python tasks.py schema`).
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../contracts/schema/contracts.json");
const out = resolve(here, "../src/types/contracts.ts");

const schema = JSON.parse(await readFile(src, "utf8"));
const ts = await compile(schema, "Contracts", {
  bannerComment:
    "/* Generated from contracts/schema/contracts.json — do not edit. Run `pnpm types`. */",
  additionalProperties: false,
  unreachableDefinitions: true,
  style: { singleQuote: false, semi: true },
});

await mkdir(dirname(out), { recursive: true });
await writeFile(out, ts, "utf8");
console.log(`wrote ${out}`);
