/** Browser-side reader for one immutable, hash-verified frontend release. */

export const RELEASE_FAMILIES = ["snapshot", "market", "ownership", "foreign", "rotation"] as const;
export type ReleaseFamily = (typeof RELEASE_FAMILIES)[number];

export interface ReleaseFile {
  path: string;
  sha256: string;
  bytes: number;
  schema: string;
  observation_date: string;
}

export interface ReleaseManifest {
  schema_version: "idx-release-manifest-v1";
  release_id: string;
  target_session: string;
  snapshot_identity: {
    snapshot_id: string;
    provider: string;
    provider_mode: string;
    price_basis: string;
  };
  analytical_contracts: Record<string, string>;
  validation: Record<string, unknown>;
  source_evidence: Record<string, unknown>[];
  families: Record<ReleaseFamily, ReleaseFile>;
  additional_files: (ReleaseFile & { file_id: string; family: string })[];
}

interface ReleaseReference {
  release_id: string;
  manifest_path: string;
  manifest_sha256: string;
}

interface ActivePointer {
  schema_version: "idx-active-release-v1";
  active: ReleaseReference;
  previous: ReleaseReference | null;
}

const expectedSchemas: Record<ReleaseFamily, string> = {
  snapshot: "web-snapshot-v1",
  market: "market-workspace-v1",
  ownership: "idx-ownership-v1",
  foreign: "idx-foreign-history-v1",
  rotation: "rotation-history-v1",
};
const digestPattern = /^[0-9a-f]{64}$/;
const releasePattern = /^rel-[0-9a-f]{64}$/;
const assetRequests = new Map<string, Promise<unknown>>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) &&
    new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

function matchesObservationDate(value: Record<string, unknown>, expected: string): boolean {
  const asOf = value.as_of;
  if (typeof asOf === "string") return validDate(asOf) && asOf === expected;
  if (!isRecord(asOf) || Object.keys(asOf).sort().join(",") !== "max,min" ||
      !validDate(asOf.min) || !validDate(asOf.max)) return false;
  return asOf.min <= asOf.max && asOf.max === expected;
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function sha256(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

function validateReference(value: unknown, label: string): ReleaseReference {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "manifest_path,manifest_sha256,release_id") {
    throw new Error(`Active release ${label} reference is malformed`);
  }
  const id = value.release_id;
  if (typeof id !== "string" || !releasePattern.test(id) || value.manifest_path !== `${id}/manifest.json` ||
      typeof value.manifest_sha256 !== "string" || !digestPattern.test(value.manifest_sha256)) {
    throw new Error(`Active release ${label} reference is invalid`);
  }
  return value as unknown as ReleaseReference;
}

function validateEntry(value: unknown, label: string, expectedSchema?: string): ReleaseFile {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "bytes,observation_date,path,schema,sha256") {
    throw new Error(`${label} manifest entry is malformed`);
  }
  const { path, sha256: hash, bytes, schema, observation_date: observationDate } = value;
  if (typeof path !== "string" || !path || path.startsWith("/") || path.includes("\\") ||
      path.split("/").some(part => !part || part === "." || part === "..") ||
      /(^|\/)(active|index|latest)\.json$/i.test(path) || /_latest\.json$/i.test(path)) {
    throw new Error(`${label} manifest path is unsafe or mutable`);
  }
  if (typeof hash !== "string" || !digestPattern.test(hash) ||
      !Number.isSafeInteger(bytes) || (bytes as number) <= 0 || typeof schema !== "string" || !schema ||
      !validDate(observationDate) || (expectedSchema && schema !== expectedSchema)) {
    throw new Error(`${label} manifest metadata is invalid`);
  }
  return value as unknown as ReleaseFile;
}

function fileIdentity(file: ReleaseFile, extra?: { file_id: string; family: string }): Record<string, unknown> {
  const result: Record<string, unknown> = {
    path: file.path,
    sha256: file.sha256,
    bytes: file.bytes,
    schema: file.schema,
    observation_date: file.observation_date,
  };
  if (extra) Object.assign(result, extra);
  return result;
}

function compareId(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

async function validateManifest(value: unknown, expectedId: string): Promise<ReleaseManifest> {
  const manifestKeys = ["additional_files", "analytical_contracts", "families", "release_id", "schema_version", "snapshot_identity", "source_evidence", "target_session", "validation"];
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== manifestKeys.join(",") ||
      value.schema_version !== "idx-release-manifest-v1" || value.release_id !== expectedId ||
      !validDate(value.target_session) || !isRecord(value.snapshot_identity) || !isRecord(value.families) ||
      !isRecord(value.analytical_contracts) || !isRecord(value.validation) ||
      !Array.isArray(value.source_evidence) || !Array.isArray(value.additional_files)) {
    throw new Error("Active release manifest schema is invalid");
  }
  const familyNames = Object.keys(value.families).sort();
  if (familyNames.join(",") !== [...RELEASE_FAMILIES].sort().join(",")) {
    throw new Error("Active release manifest does not contain all five asset families");
  }
  const families = {} as Record<ReleaseFamily, ReleaseFile>;
  for (const family of RELEASE_FAMILIES) {
    families[family] = validateEntry(value.families[family], `${family} family`, expectedSchemas[family]);
  }
  const identity = value.snapshot_identity;
  if (Object.keys(identity).sort().join(",") !== "price_basis,provider,provider_mode,snapshot_id" ||
      typeof identity.snapshot_id !== "string" || typeof identity.provider !== "string" ||
      typeof identity.provider_mode !== "string" || typeof identity.price_basis !== "string") {
    throw new Error("Active release snapshot identity is invalid");
  }
  for (const family of RELEASE_FAMILIES) {
    if (family === "ownership") {
      if (families[family].observation_date > String(value.target_session)) {
        throw new Error("ownership family contains future observation evidence");
      }
    }
  }
  const target = value.target_session;
  for (const family of ["snapshot", "market", "foreign", "rotation"] as const) {
    if (families[family].observation_date !== target) throw new Error(`${family} family does not reach the target session`);
  }
  const additional = value.additional_files.map((raw, index) => {
    if (!isRecord(raw) || Object.keys(raw).sort().join(",") !== "bytes,family,file_id,observation_date,path,schema,sha256" ||
        typeof raw.file_id !== "string" || !raw.file_id || raw.family !== "snapshot") {
      throw new Error(`Additional release file ${index} is malformed`);
    }
    return { ...validateEntry({
      path: raw.path, sha256: raw.sha256, bytes: raw.bytes, schema: raw.schema, observation_date: raw.observation_date,
    }, `additional file ${raw.file_id}`), file_id: raw.file_id, family: raw.family };
  });
  if (new Set(additional.map(file => file.file_id)).size !== additional.length) {
    throw new Error("Active release manifest has duplicate additional file IDs");
  }
  if (new Set([...RELEASE_FAMILIES.map(family => families[family].path), ...additional.map(file => file.path)]).size !==
      RELEASE_FAMILIES.length + additional.length) throw new Error("Active release manifest reuses an asset path");
  const packagePaths = [...RELEASE_FAMILIES.map(family => families[family].path), ...additional.map(file => file.path)].sort();
  for (let index = 0; index < packagePaths.length; index++) {
    if (packagePaths.slice(index + 1).some(other => other.startsWith(`${packagePaths[index]}/`))) {
      throw new Error("Active release manifest contains overlapping asset paths");
    }
  }

  const sourceEvidence = value.source_evidence as Record<string, unknown>[];
  const sortedSources = [...sourceEvidence].sort((a, b) => String(a?.source_id ?? "").localeCompare(String(b?.source_id ?? "")));
    if (sortedSources.some((source, index) => !isRecord(source) || typeof source.source_id !== "string" ||
      (index > 0 && source.source_id === sortedSources[index - 1]?.source_id) || "candidate_path" in source)) {
    throw new Error("Active release source evidence is invalid");
  }
  const contractHashes = Object.values(value.analytical_contracts);
  if (!contractHashes.length || Object.keys(value.analytical_contracts).some(key => !key) ||
      contractHashes.some(hash => typeof hash !== "string" || !digestPattern.test(hash))) {
    throw new Error("Active release analytical contract fingerprints are invalid");
  }
  const validation = value.validation;
  const validationKeys = ["analytical_status", "contract_fingerprints", "evidence_reports", "input_hashes", "package_status", "validator_contract"];
  if (Object.keys(validation).sort().join(",") !== validationKeys.join(",") || validation.package_status !== "PASS" ||
      typeof validation.analytical_status !== "string" || !validation.analytical_status ||
      validation.validator_contract !== "idx-release-validator-v1" || !isRecord(validation.contract_fingerprints) ||
      canonical(validation.contract_fingerprints) !== canonical(value.analytical_contracts) || !isRecord(validation.evidence_reports) ||
      !isRecord(validation.input_hashes)) {
    throw new Error("Active release validation summary is invalid");
  }
  if (!("market_panel" in validation.evidence_reports)) throw new Error("Active release is missing its panel validation report");
  for (const [reportId, report] of Object.entries(validation.evidence_reports)) {
    if (!reportId || !isRecord(report) || Object.keys(report).sort().join(",") !== "contract,input_hashes,sha256,status" ||
        report.status !== "PASS" || typeof report.contract !== "string" || !report.contract ||
        typeof report.sha256 !== "string" || !digestPattern.test(report.sha256) || !isRecord(report.input_hashes)) {
      throw new Error(`Active release evidence report ${reportId} is invalid`);
    }
  }
  if ((validation.evidence_reports.market_panel as Record<string, unknown>).contract !== "public-panel-validation-v2") {
    throw new Error("Active release panel validation contract is unsupported");
  }
  const sourceIds = sourceEvidence.map(source => source?.source_id);
  if (sourceEvidence.some((source, index) => !isRecord(source) || typeof source.source_id !== "string" || !source.source_id ||
      typeof source.sha256 !== "string" || !digestPattern.test(source.sha256) || "candidate_path" in source ||
      (index > 0 && String(sourceIds[index - 1]) >= String(sourceIds[index])))) {
    throw new Error("Active release source evidence is invalid or unsorted");
  }
  const inputHashes = validation.input_hashes;
  if (Object.keys(inputHashes).sort().join(",") !== "additional_files,families,source_evidence" ||
      !isRecord(inputHashes.families) || !isRecord(inputHashes.additional_files) || !isRecord(inputHashes.source_evidence) ||
      canonical(inputHashes.families) !== canonical(Object.fromEntries(RELEASE_FAMILIES.slice().sort().map(family => [family, families[family].sha256]))) ||
      canonical(inputHashes.additional_files) !== canonical(Object.fromEntries(additional.slice().sort((a, b) => compareId(a.file_id, b.file_id)).map(file => [file.file_id, file.sha256]))) ||
      canonical(inputHashes.source_evidence) !== canonical(Object.fromEntries(sourceEvidence.map(source => [String(source.source_id), source.sha256])))) {
    throw new Error("Active release input hashes do not match its asset inventory");
  }

  const material = {
    target_session: target,
    snapshot_identity: identity,
    analytical_contracts: value.analytical_contracts,
    source_evidence: sortedSources,
    validation: value.validation,
    families: Object.fromEntries(RELEASE_FAMILIES.slice().sort().map(family => [family, fileIdentity(families[family])])),
    additional_files: additional.slice().sort((a, b) => compareId(a.file_id, b.file_id))
      .map(file => fileIdentity(file, { file_id: file.file_id, family: file.family })),
  };
  const materialBytes = new TextEncoder().encode(canonical(material));
  const idDigest = await sha256(materialBytes.buffer);
  if (`rel-${idDigest}` !== expectedId) throw new Error("Active release ID does not match its manifest inventory");

  return value as unknown as ReleaseManifest;
}

async function fetchBytes(path: string, cache: RequestCache): Promise<ArrayBuffer> {
  const response = await fetch(path, { cache });
  if (!response.ok || !response.headers.get("content-type")?.includes("json")) {
    throw new Error(`Release file unavailable: ${path} (HTTP ${response.status})`);
  }
  return response.arrayBuffer();
}

export interface SelectedRelease {
  id: string;
  manifest: ReleaseManifest;
}

export async function loadActiveRelease(): Promise<SelectedRelease> {
  const pointerBytes = await fetchBytes("/releases/active.json", "no-store");
  const pointer = JSON.parse(new TextDecoder().decode(pointerBytes)) as unknown;
  if (!isRecord(pointer) || Object.keys(pointer).sort().join(",") !== "active,previous,schema_version" ||
      pointer.schema_version !== "idx-active-release-v1") throw new Error("Active release pointer schema is invalid");
  const active = validateReference(pointer.active, "active");
  if (pointer.previous !== null) validateReference(pointer.previous, "previous");
  const manifestPath = `/releases/${active.release_id}/manifest.json`;
  const manifestBytes = await fetchBytes(manifestPath, "no-store");
  if (await sha256(manifestBytes) !== active.manifest_sha256) throw new Error("Active release manifest integrity check failed");
  const manifest = await validateManifest(JSON.parse(new TextDecoder().decode(manifestBytes)), active.release_id);
  return { id: active.release_id, manifest };
}

export function loadReleaseAsset<T = unknown>(release: SelectedRelease, entry: ReleaseFile): Promise<T> {
  const key = `${release.id}:${entry.sha256}`;
  if (!assetRequests.has(key)) {
    const packagePath = `/releases/${release.id}/${entry.path.split("/").map(encodeURIComponent).join("/")}`;
    assetRequests.set(key, (async () => {
      const bytes = await fetchBytes(packagePath, "force-cache");
      if (bytes.byteLength !== entry.bytes || await sha256(bytes) !== entry.sha256) {
        throw new Error(`Release asset integrity check failed: ${entry.path}`);
      }
      const value = JSON.parse(new TextDecoder().decode(bytes)) as unknown;
      if (!isRecord(value) || value.schema_version !== entry.schema || !matchesObservationDate(value, entry.observation_date)) {
        throw new Error(`Release asset identity mismatch: ${entry.path}`);
      }
      if (entry.schema === "web-snapshot-v1" && value.snapshot_id !== release.manifest.snapshot_identity.snapshot_id) {
        throw new Error("Snapshot identity differs from its selected release");
      }
      if ((entry.schema === "market-workspace-v1" || entry.schema === "rotation-history-v1") &&
          value.snapshot_id !== release.manifest.snapshot_identity.snapshot_id) {
        throw new Error("Market or rotation family differs from its selected snapshot");
      }
      return value;
    })());
    assetRequests.get(key)!.catch(() => assetRequests.delete(key));
  }
  return assetRequests.get(key) as Promise<T>;
}

export function loadReleaseAdditionalFile<T = unknown>(release: SelectedRelease, fileId: string): Promise<T | null> {
  const entry = release.manifest.additional_files.find(file => file.file_id === fileId);
  return entry ? loadReleaseAsset<T>(release, entry) : Promise.resolve(null);
}
