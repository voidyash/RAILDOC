/**
 * Maintenance recommendation mapping (pure data layer — no AI involvement).
 *
 * The YOLOv26 detector (backend/app/cv/inference.py) reports these classes
 * from the RAILDOC_02.yolo26 dataset, mapped to defect_type via _CLASS_MAP:
 *
 *   tracks_fault → track_defect   (rail/track surface faults)
 *   light_pole   → light_pole
 *
 * To support a new defect type later, add an entry to
 * MAINTENANCE_RECOMMENDATIONS keyed by its defect_type. Classes without an
 * entry are handled gracefully by the UI ("recommendation unavailable") and
 * the operator can add tools and estimated time manually.
 */

export interface MaintenanceRecommendation {
  /** Human-readable defect name shown in the UI. */
  displayName: string;
  /** Tools/equipment the maintenance crew needs. */
  tools: string[];
  /** Estimated repair/maintenance time, e.g. "2 hr 30 min". */
  estimatedTime: string;
}

export const MAINTENANCE_RECOMMENDATIONS: Record<string, MaintenanceRecommendation> = {
  track_defect: {
    displayName: 'Track Defect',
    tools: ['Rail Grinder', 'Measuring Gauge', 'Safety Kit'],
    estimatedTime: '2 hr 30 min',
  },
  light_pole: {
    displayName: 'Light Pole',
    tools: ['Aerial Lift (Bucket Truck)', 'Voltage Tester', 'Torque Wrench', 'Safety Kit'],
    estimatedTime: '1 hr 45 min',
  },
};

/** Raw YOLO dataset class names accepted as aliases for defect_type keys. */
const CLASS_ALIASES: Record<string, string> = {
  tracks_fault: 'track_defect',
};

/** Title-cased defect name for headings (e.g. "track_defect" → "Track Defect"). */
export function defectDisplayName(defectType: string): string {
  const rec = MAINTENANCE_RECOMMENDATIONS[defectType];
  if (rec) return rec.displayName;
  return defectType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Look up the recommendation for a detection. Tries the mapped defect_type
 * first, then the raw YOLO class label, so either key works. Returns null for
 * unknown classes (UI shows "recommendation unavailable" + manual entry).
 */
export function getMaintenanceRecommendation(
  defectType: string,
  label?: string,
): MaintenanceRecommendation | null {
  for (const candidate of [defectType, label ?? '']) {
    if (!candidate) continue;
    const key = CLASS_ALIASES[candidate] ?? candidate;
    if (MAINTENANCE_RECOMMENDATIONS[key]) return MAINTENANCE_RECOMMENDATIONS[key];
  }
  return null;
}
