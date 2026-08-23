import type { DecaEvent, EventFormat } from "@/lib/deca";

// Mirror of backend/roleplay-gen-model/data/events.json (28 competing events).
export const EVENTS: DecaEvent[] = [
  { code: "AAM", name: "Apparel and Accessories Marketing Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "ACT", name: "Accounting Applications Series", format: "series", careerCluster: "Finance", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "ASM", name: "Automotive Services Marketing Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "BFS", name: "Business Finance Series", format: "series", careerCluster: "Finance", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "BSM", name: "Business Services Marketing Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "ENT", name: "Entrepreneurship Series", format: "series", careerCluster: "Entrepreneurship", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "FMS", name: "Food Marketing Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "HLM", name: "Hotel and Lodging Management Series", format: "series", careerCluster: "Hospitality and Tourism", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "HRM", name: "Human Resources Management Series", format: "series", careerCluster: "Business Management and Administration", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "MCS", name: "Marketing Communications Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "QSRM", name: "Quick Serve Restaurant Management Series", format: "series", careerCluster: "Hospitality and Tourism", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "RFSM", name: "Restaurant and Food Service Management Series", format: "series", careerCluster: "Hospitality and Tourism", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "RMS", name: "Retail Merchandising Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },
  { code: "SEM", name: "Sports and Entertainment Marketing Series", format: "series", careerCluster: "Marketing", roles: 1, piCount: 5, prepMinutes: 10, presentMinutes: 10 },

  { code: "PBM", name: "Principles of Business Management and Administration", format: "principles", careerCluster: "Business Management and Administration", roles: 1, piCount: 4, prepMinutes: 10, presentMinutes: 10 },
  { code: "PEN", name: "Principles of Entrepreneurship", format: "principles", careerCluster: "Entrepreneurship", roles: 1, piCount: 4, prepMinutes: 10, presentMinutes: 10 },
  // PFL carries no careerCluster on purpose: the backend records it as
  // `career_cluster: null`, so anything here would be invented (issue #52).
  { code: "PFL", name: "Personal Financial Literacy", format: "principles", roles: 1, piCount: 3, prepMinutes: 10, presentMinutes: 10 },
  { code: "PFN", name: "Principles of Finance", format: "principles", careerCluster: "Finance", roles: 1, piCount: 4, prepMinutes: 10, presentMinutes: 10 },
  { code: "PHT", name: "Principles of Hospitality and Tourism", format: "principles", careerCluster: "Hospitality and Tourism", roles: 1, piCount: 4, prepMinutes: 10, presentMinutes: 10 },
  { code: "PMK", name: "Principles of Marketing", format: "principles", careerCluster: "Marketing", roles: 1, piCount: 4, prepMinutes: 10, presentMinutes: 10 },

  { code: "BLTDM", name: "Business Law and Ethics Team Decision Making", format: "team", careerCluster: "Business Management and Administration", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "BTDM", name: "Buying and Merchandising Team Decision Making", format: "team", careerCluster: "Marketing", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "ETDM", name: "Entrepreneurship Team Decision Making", format: "team", careerCluster: "Entrepreneurship", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "FTDM", name: "Financial Services Team Decision Making", format: "team", careerCluster: "Finance", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "HTDM", name: "Hospitality Services Team Decision Making", format: "team", careerCluster: "Hospitality and Tourism", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "MTDM", name: "Marketing Management Team Decision Making", format: "team", careerCluster: "Marketing", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "STDM", name: "Sports and Entertainment Marketing Team Decision Making", format: "team", careerCluster: "Marketing", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
  { code: "TTDM", name: "Travel and Tourism Team Decision Making", format: "team", careerCluster: "Hospitality and Tourism", roles: 2, piCount: 7, prepMinutes: 30, presentMinutes: 15 },
];

export const EVENTS_BY_FORMAT: Record<EventFormat, DecaEvent[]> = {
  series: EVENTS.filter((e) => e.format === "series"),
  principles: EVENTS.filter((e) => e.format === "principles"),
  team: EVENTS.filter((e) => e.format === "team"),
};

export function findEvent(code: string): DecaEvent | undefined {
  return EVENTS.find((e) => e.code === code);
}