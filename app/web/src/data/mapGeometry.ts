// Shared map geometry contract used by the Overview mini-map and
// the full Leadership Map page. One contract, one label, one truth.
//
// The primary Leadership × Diffusion map uses:
//   X axis: 20-day excess return vs IHSG (leadership signal)
//   Y axis: 20-day breadth delta in percentage points (diffusion signal)
//
// A first snapshot has no valid prior breadth observation. In that case the
// UI uses an explicitly different current-snapshot view with current breadth
// on Y; it never substitutes a fabricated breadth delta.

export interface MapPlotBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LeadershipDiffusionDomain {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

export type MapViewMode = "trajectory" | "current";

export interface MapPointInput {
  excess20d: number | null;
  breadth: number | null;
  prevBreadth?: number;
}

export const LEADERSHIP_DIFFUSION_X_MIN = -15;
export const LEADERSHIP_DIFFUSION_X_MAX = 15;
export const LEADERSHIP_DIFFUSION_Y_MIN = -30;
export const LEADERSHIP_DIFFUSION_Y_MAX = 30;

export const DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN: LeadershipDiffusionDomain = {
  xMin: LEADERSHIP_DIFFUSION_X_MIN,
  xMax: LEADERSHIP_DIFFUSION_X_MAX,
  yMin: LEADERSHIP_DIFFUSION_Y_MIN,
  yMax: LEADERSHIP_DIFFUSION_Y_MAX,
};

export const CURRENT_BREADTH_DOMAIN: LeadershipDiffusionDomain = {
  xMin: LEADERSHIP_DIFFUSION_X_MIN,
  xMax: LEADERSHIP_DIFFUSION_X_MAX,
  yMin: 0,
  yMax: 100,
};

export const MAP_AXIS_LABELS = {
  x: "20D excess return vs IHSG (%)",
  y: "20D breadth delta (%)",
  title: "Leadership × Diffusion Map",
  subtitle: "Relative leadership / breadth momentum",
} as const;

export const CURRENT_BREADTH_AXIS_LABELS = {
  x: "20D excess return vs IHSG (%)",
  y: "20D breadth (current snapshot)",
  title: "Leadership × Current Breadth Map",
  subtitle: "Relative leadership / current participation",
} as const;

export function mapViewDomain(mode: MapViewMode): LeadershipDiffusionDomain {
  return mode === "current"
    ? CURRENT_BREADTH_DOMAIN
    : DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN;
}

export function mapViewLabels(mode: MapViewMode) {
  return mode === "current" ? CURRENT_BREADTH_AXIS_LABELS : MAP_AXIS_LABELS;
}

export function mapYValue(
  point: MapPointInput,
  mode: MapViewMode,
): number | null {
  if (point.breadth === null || !Number.isFinite(point.breadth)) return null;
  if (mode === "current") return point.breadth;
  if (point.prevBreadth === undefined || !Number.isFinite(point.prevBreadth)) {
    return null;
  }
  return point.breadth - point.prevBreadth;
}

export function mapYBaseline(mode: MapViewMode): number {
  return mode === "current" ? 50 : 0;
}

export function mapX(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): number {
  return (
    plot.left +
    ((value - domain.xMin) / (domain.xMax - domain.xMin)) * plot.width
  );
}

export function mapY(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): number {
  return (
    plot.top +
    (1 - (value - domain.yMin) / (domain.yMax - domain.yMin)) * plot.height
  );
}

export function clamp(
  value: number,
  min: number,
  max: number,
): number {
  return Math.max(min, Math.min(max, value));
}

export function clampX(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): number {
  return clamp(mapX(value, plot, domain), plot.left, plot.left + plot.width);
}

export function clampY(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): number {
  return clamp(mapY(value, plot, domain), plot.top, plot.top + plot.height);
}

export function isOutOfXBounds(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): boolean {
  const x = mapX(value, plot, domain);
  return x < plot.left || x > plot.left + plot.width;
}

export function isOutOfYBounds(
  value: number,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
): boolean {
  const y = mapY(value, plot, domain);
  return y < plot.top || y > plot.top + plot.height;
}
export type MapClassification =
  | "missing-metric"
  | "missing-prior"
  | "off-scale-x"
  | "off-scale-y"
  | "plottable";

export interface MapClassificationResult {
  classification: MapClassification;
  reason: string;
}

export function classifyMapPoint(
  value: MapPointInput,
  plot: MapPlotBounds,
  domain: LeadershipDiffusionDomain = DEFAULT_LEADERSHIP_DIFFUSION_DOMAIN,
  hasPriorBreadth: boolean = false,
  mode: MapViewMode = "trajectory",
): MapClassificationResult {
  if (value.excess20d === null || !Number.isFinite(value.excess20d)) {
    return { classification: "missing-metric", reason: "20D excess return is missing or non-finite" };
  }
  if (mode === "current") {
    // Current-snapshot mode uses current breadth on the Y axis (0-100 domain).
    // A point is plottable when current breadth is a valid finite number.
    if (value.breadth === null || !Number.isFinite(value.breadth)) {
      return { classification: "missing-prior", reason: "No current breadth observation" };
    }
    const x = mapX(value.excess20d, plot, domain);
    const xOutOfBounds = x < plot.left || x > plot.left + plot.width;
    if (xOutOfBounds) {
      return { classification: "off-scale-x", reason: "X-axis value outside domain" };
    }
    return { classification: "plottable", reason: "Within domain bounds" };
  }
  if (
    value.breadth === null ||
    !Number.isFinite(value.breadth) ||
    value.prevBreadth === undefined ||
    !Number.isFinite(value.prevBreadth) ||
    !hasPriorBreadth
  ) {
    return { classification: "missing-prior", reason: "No comparable prior breadth observation" };
  }
  const yValue = mapYValue(value, mode);
  const x = mapX(value.excess20d, plot, domain);
  const xOutOfBounds = x < plot.left || x > plot.left + plot.width;
  const yOutOfBounds = yValue !== null && isOutOfYBounds(yValue, plot, domain);
  if (xOutOfBounds && yOutOfBounds) {
    return { classification: "off-scale-x", reason: "Both axes out of bounds" };
  }
  if (xOutOfBounds) {
    return { classification: "off-scale-x", reason: "X-axis value outside domain" };
  }
  if (yOutOfBounds) {
    return { classification: "off-scale-y", reason: "Y-axis value outside domain" };
  }
  return { classification: "plottable", reason: "Within domain bounds" };
}
