import type { Cluster } from "@/lib/deca";

// Mirror of backend/test-gen-model/data/clusters.json (the 5 exam clusters).
export const CLUSTERS: Cluster[] = [
  { value: "pbm", label: "Business Admin Core", examName: "Business Administration Core" },
  { value: "marketing", label: "Marketing Cluster", examName: "Marketing Cluster" },
  { value: "finance", label: "Finance Cluster", examName: "Finance Cluster" },
  { value: "hospitality", label: "Hospitality & Tourism", examName: "Hospitality and Tourism Cluster" },
  { value: "entrepreneurship", label: "Entrepreneurship", examName: "Entrepreneurship Cluster" },
];
