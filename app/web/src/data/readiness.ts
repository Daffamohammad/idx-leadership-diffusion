import type { DataStatus, SnapshotPayload } from "./snapshot";

// Keep this aligned with config/methodology.yaml. The snapshot contract does
// not currently persist the full methodology config, so the UI only uses this
// value to explain an already-emitted classification result; it never changes
// the backend state.
export const MINIMUM_GROUP_SIZE = 5;

export interface DiffusionReadiness {
  status: DataStatus;
  totalGroups: number;
  confirmedGroups: number;
  unconfirmedGroups: number;
  belowMinimumGroups: number;
  missingBreadthDeltaGroups: number;
  note: string;
}

/**
 * Explain why diffusion states are or are not available for this snapshot.
 *
 * A comparable prior is a data prerequisite. Once that exists, the group
 * minimum is a methodology prerequisite. Keeping those causes separate makes
 * UNCONFIRMED auditable instead of presenting it as a generic failure.
 */
export function buildDiffusionReadiness(
  payload: SnapshotPayload | null,
): DiffusionReadiness {
  const groups = payload?.groups ?? [];
  const totalGroups = groups.length;
  const confirmedGroups = groups.filter(
    (group) => group.diffusion_state !== "UNCONFIRMED",
  ).length;
  const unconfirmedGroups = totalGroups - confirmedGroups;
  const unconfirmedRows = groups.filter(
    (group) => group.diffusion_state === "UNCONFIRMED",
  );
  const belowMinimumGroups = unconfirmedRows.filter(
    (group) => group.constituent_count < MINIMUM_GROUP_SIZE,
  ).length;
  const missingBreadthDeltaGroups = unconfirmedRows.filter(
    (group) => group.breadth_delta === null || group.breadth_delta === undefined,
  ).length;
  const hasComparablePrior =
    payload?.comparability?.status === "COMPATIBLE" &&
    Boolean(payload.comparability.selected_previous);

  if (totalGroups === 0) {
    return {
      status: "DATA_GAP",
      totalGroups,
      confirmedGroups,
      unconfirmedGroups,
      belowMinimumGroups,
      missingBreadthDeltaGroups,
      note: "No group observations were emitted by the current snapshot.",
    };
  }

  if (!hasComparablePrior) {
    return {
      status: "DATA_GAP",
      totalGroups,
      confirmedGroups,
      unconfirmedGroups,
      belowMinimumGroups,
      missingBreadthDeltaGroups,
      note:
        "No persisted comparable prior snapshot is available; breadth change and diffusion states remain UNCONFIRMED by design.",
    };
  }

  if (unconfirmedGroups === 0) {
    return {
      status: "READY",
      totalGroups,
      confirmedGroups,
      unconfirmedGroups,
      belowMinimumGroups,
      missingBreadthDeltaGroups,
      note: `All ${totalGroups} groups have a comparable diffusion classification.`,
    };
  }

  const causes: string[] = [];
  if (belowMinimumGroups > 0) {
    causes.push(
      `${belowMinimumGroups} group(s) are below the configured minimum group size`,
    );
  }
  if (missingBreadthDeltaGroups > 0) {
    causes.push(
      `${missingBreadthDeltaGroups} group(s) are missing a comparable breadth delta`,
    );
  }
  if (causes.length === 0) {
    causes.push("some groups do not meet the diffusion evidence requirements");
  }

  return {
    status: "READY_WITH_GAPS",
    totalGroups,
    confirmedGroups,
    unconfirmedGroups,
    belowMinimumGroups,
    missingBreadthDeltaGroups,
    note: `${confirmedGroups}/${totalGroups} groups classified; ${causes.join(" and ")}. UNCONFIRMED is retained rather than inferred.`,
  };
}
