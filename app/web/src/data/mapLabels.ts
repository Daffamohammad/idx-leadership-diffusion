export interface MapLabelCandidate {
  id: string;
  text: string;
  x: number;
  y: number;
  radius: number;
  priority: number;
}

export interface MapLabelPosition {
  id: string;
  text: string;
  x: number;
  y: number;
  textAnchor: "start" | "middle" | "end";
  targetX?: number;
  targetY?: number;
}

interface LabelBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

interface LabelOffset {
  dx: number;
  dy: number;
  textAnchor: "start" | "middle" | "end";
}

const OFFSETS: LabelOffset[] = [
  { dx: 12, dy: -9, textAnchor: "start" },
  { dx: 12, dy: 15, textAnchor: "start" },
  { dx: -12, dy: -9, textAnchor: "end" },
  { dx: -12, dy: 15, textAnchor: "end" },
  { dx: 0, dy: -19, textAnchor: "middle" },
  { dx: 0, dy: 25, textAnchor: "middle" },
  { dx: 19, dy: 0, textAnchor: "start" },
  { dx: -19, dy: 0, textAnchor: "end" },
];

// Geist Mono at the map's 11px label size is approximately 6.5 units wide.
// The conservative estimate keeps visual collision checks ahead of rasterized text.
const CHAR_WIDTH = 6.5;
const LABEL_HEIGHT = 12;
const LABEL_GAP = 6;
const LABEL_X_MIN_SPACING = 40;

function boxFor(
  x: number,
  baseline: number,
  text: string,
  textAnchor: "start" | "middle" | "end",
): LabelBox {
  const width = Math.max(18, text.length * CHAR_WIDTH);
  const left =
    textAnchor === "start" ? x : textAnchor === "end" ? x - width : x - width / 2;
  return {
    left: left - LABEL_GAP,
    right: left + width + LABEL_GAP,
    top: baseline - LABEL_HEIGHT,
    bottom: baseline + LABEL_GAP,
  };
}

function overlaps(a: LabelBox, b: LabelBox): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

function touchesPoint(box: LabelBox, candidate: MapLabelCandidate): boolean {
  const nearestX = Math.max(box.left, Math.min(candidate.x, box.right));
  const nearestY = Math.max(box.top, Math.min(candidate.y, box.bottom));
  return Math.hypot(candidate.x - nearestX, candidate.y - nearestY) < candidate.radius + 3;
}

function inBounds(box: LabelBox, bounds: { left: number; right: number; top: number; bottom: number }): boolean {
  return (
    box.left >= bounds.left &&
    box.right <= bounds.right &&
    box.top >= bounds.top &&
    box.bottom <= bounds.bottom
  );
}

/**
 * Place a small, deterministic set of labels without stacking every group
 * name on top of the map. The map remains fully inspectable through points,
 * keyboard focus, and the table below it.
 */
export function placeMapLabels(
  candidates: MapLabelCandidate[],
  bounds: { left: number; right: number; top: number; bottom: number },
  maxLabels = 3,
): MapLabelPosition[] {
  const selected: MapLabelPosition[] = [];
  const boxes: LabelBox[] = [];
  // Deduplicate candidates that are too close in x to fit separate labels.
  // Deterministic: sort by priority desc, then by id asc; keep the first
  // candidate in each x-grid bucket of size LABEL_X_MIN_SPACING.
  const sorted = [...candidates].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  const deduped: typeof sorted = [];
  const usedXBuckets = new Set<number>();
  for (const c of sorted) {
    const bucket = Math.round(c.x / LABEL_X_MIN_SPACING);
    if (usedXBuckets.has(bucket)) continue;
    usedXBuckets.add(bucket);
    deduped.push(c);
  }
  const ranked = deduped.slice(0, Math.max(0, maxLabels));

  for (const candidate of ranked) {
    const placement = OFFSETS.map((offset) => {
      const x = candidate.x + offset.dx;
      const y = candidate.y + offset.dy;
      return {
        ...offset,
        x,
        y,
        box: boxFor(x, y, candidate.text, offset.textAnchor),
      };
    }).sort((a, b) => {
      const aPenalty = (inBounds(a.box, bounds) ? 0 : 1000) + (touchesPoint(a.box, candidate) ? 100 : 0);
      const bPenalty = (inBounds(b.box, bounds) ? 0 : 1000) + (touchesPoint(b.box, candidate) ? 100 : 0);
      return aPenalty - bPenalty;
    });

    const valid = placement.find(
      (item) =>
        inBounds(item.box, bounds) &&
        !touchesPoint(item.box, candidate) &&
        !boxes.some((box) => overlaps(item.box, box)),
    );
    if (!valid) continue;
    selected.push({
      id: candidate.id,
      text: candidate.text,
      x: valid.x,
      y: valid.y,
      textAnchor: valid.textAnchor,
      targetX: candidate.x,
      targetY: candidate.y,
    });
    boxes.push(valid.box);
  }
  return selected;
}
