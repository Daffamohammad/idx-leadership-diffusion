import { readdir, readFile, rm, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const releasesDir = resolve(appRoot, "dist", "releases");
const pointer = JSON.parse(await readFile(resolve(releasesDir, "active.json"), "utf8"));
const activeId = pointer?.active?.release_id;
const rollbackId = pointer?.previous?.release_id;
const validId = (value) => typeof value === "string" && /^rel-[a-f0-9]{64}$/.test(value);

if (!validId(activeId) || !validId(rollbackId) || activeId === rollbackId) {
  throw new Error("The release pointer must identify an active release and a distinct rollback release.");
}

const keep = new Set([activeId, rollbackId]);
for (const releaseId of keep) {
  const manifest = resolve(releasesDir, releaseId, "manifest.json");
  if (!(await stat(manifest)).isFile()) {
    throw new Error(`The release output is missing ${releaseId}/manifest.json.`);
  }
}

for (const entry of await readdir(releasesDir, { withFileTypes: true })) {
  if (entry.isDirectory() && !keep.has(entry.name)) {
    await rm(resolve(releasesDir, entry.name), { recursive: true, force: true });
  }
}

console.log(`Release output includes active ${activeId} and rollback ${rollbackId}.`);
