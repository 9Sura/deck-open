// Shared DECA domain types + option lists for the generator UIs.
// Data mirrored from backend/*/data/*.json into ./data/*.ts (client-safe).

export type Level = "District" | "Association" | "ICDC";

export const LEVELS: { value: Level; label: string; note: string }[] = [
  { value: "District", label: "District", note: "Regional / first round" },
  { value: "Association", label: "Association", note: "State-level" },
  { value: "ICDC", label: "ICDC", note: "International Career Development Conference" },
];

export interface Cluster {
  value: string; // e.g. "marketing"
  label: string; // friendly, e.g. "Marketing Cluster"
  examName: string; // e.g. "Marketing Cluster"
}

export type EventFormat = "series" | "principles" | "team";

export interface DecaEvent {
  code: string; // e.g. "HRM"
  name: string; // full event name
  format: EventFormat;
  /**
   * Absent for PFL — DECA publishes no career cluster for that event, and the
   * backend records it as `career_cluster: null`. Optional here so the mirror
   * can say so rather than inventing one; render it only when present.
   */
  careerCluster?: string;
  roles: number;
  piCount: number;
  prepMinutes: number;
  presentMinutes: number;
}

export const FORMAT_LABEL: Record<EventFormat, string> = {
  series: "Individual Series",
  principles: "Principles (Entry-level)",
  team: "Team Decision Making",
};
