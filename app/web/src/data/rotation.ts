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
  excess20d: number | null;
  excess60d: number | null;
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

/** Minimum dated observations before a trail may be drawn at all. */
export const MIN_ROTATION_TRAIL_POINTS = 3;

export interface RotationTrailPoint {
  asOf: string;
  x: number;
  y: number;
}

/**
 * Build a real dated trail from persisted rotation history.
 *
 * Every returned point is an observation the pipeline actually computed for
 * that date: nothing is interpolated, repeated, or extrapolated. Points are
 * sorted oldest-first so the polyline follows time, and `tailLength` selects
 * how many of the most recent observations are connected to the current
 * position (0 = current point only).
 */
export function buildRotationTrail(
  history: ReadonlyArray<{
    as_of: string;
    group_excess_return_ytd: number;
    relative_momentum: number | null;
  }>,
  tailLength: number,
): RotationTrailPoint[] {
  if (!Number.isFinite(tailLength) || tailLength <= 0) return [];
  const dated = history
    .filter(
      (point) =>
        typeof point.as_of === "string" &&
        point.as_of.length > 0 &&
        Number.isFinite(point.group_excess_return_ytd) &&
        point.relative_momentum !== null &&
        point.relative_momentum !== undefined &&
        Number.isFinite(point.relative_momentum as number),
    )
    .sort((left, right) => left.as_of.localeCompare(right.as_of));
  if (dated.length < MIN_ROTATION_TRAIL_POINTS) return [];
  return dated.slice(-(tailLength + 1)).map((point) => ({
    asOf: point.as_of.slice(0, 10),
    x: point.group_excess_return_ytd,
    y: point.relative_momentum as number,
  }));
}
