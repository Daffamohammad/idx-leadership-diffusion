import type { TaxonomyKind } from "./snapshot";

export type RotationPhase = "LEADING" | "IMPROVING" | "WEAKENING" | "LAGGING" | "DATA_GAP";

export interface RotationGroupInput {
  id: string;
  name: string;
  taxonomyId: string;
  taxonomyKind: TaxonomyKind;
  taxonomyVersion?: string;
  prototype?: boolean;
  constituents: number;
  relativeStrength: number | null;
  relativeMomentum: number | null;
  ytdExcess: number | null;
  ytdStartDate: string | null;
  ytdEligible: number;
  dataQuality: string;
}

export interface RotationRow extends RotationGroupInput {
  phase: RotationPhase;
}

/**
 * Rotation quadrants are deliberately based only on the two documented
 * relative-return axes. Missing values are not classified as a signal.
 */
export function classifyRotation(
  relativeStrength: number | null | undefined,
  relativeMomentum: number | null | undefined,
): RotationPhase {
  if (
    relativeStrength === null ||
    relativeStrength === undefined ||
    relativeMomentum === null ||
    relativeMomentum === undefined ||
    !Number.isFinite(relativeStrength) ||
    !Number.isFinite(relativeMomentum)
  ) {
    return "DATA_GAP";
  }
  if (relativeStrength >= 0 && relativeMomentum >= 0) return "LEADING";
  if (relativeStrength < 0 && relativeMomentum >= 0) return "IMPROVING";
  if (relativeStrength >= 0 && relativeMomentum < 0) return "WEAKENING";
  return "LAGGING";
}

export function relativeMomentum(
  excess20d: number | null | undefined,
  excess60d: number | null | undefined,
): number | null {
  if (
    excess20d === null ||
    excess20d === undefined ||
    excess60d === null ||
    excess60d === undefined ||
    !Number.isFinite(excess20d) ||
    !Number.isFinite(excess60d)
  ) {
    return null;
  }
  return excess20d - excess60d;
}

export function withRotationPhase(group: RotationGroupInput): RotationRow {
  return { ...group, phase: classifyRotation(group.relativeStrength, group.relativeMomentum) };
}

