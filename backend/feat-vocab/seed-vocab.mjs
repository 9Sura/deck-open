// Vocab bank generator (assembler).
//
// Reads the reviewable term catalog under catalog/{areas,events}/*.json and
// composes one deck per DECA event:
//   - interleaves each event's instructional-area vocab (so a many-area deck
//     isn't all-economics-first),
//   - prepends event-specific flavor vocab (guaranteed inclusion),
//   - dedupes by slug, then caps at MAX_TERMS_PER_EVENT.
// Every term carries sourceRefs tracing to a real PI / roleplay / exam source.
// Fully offline, deterministic, $0 at runtime.
//
// Env: MAX_TERMS_PER_EVENT (default 50), MIN_TERMS_PER_EVENT floor (default 40).
// A deck below the floor fails the build unless VOCAB_ALLOW_THIN=1 (authoring).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const dataRoot = path.join(root, "data");
const catalogRoot = path.join(root, "catalog");

const MAX_TERMS_PER_EVENT = Number(process.env.MAX_TERMS_PER_EVENT ?? 50);
const MIN_TERMS_PER_EVENT = Number(process.env.MIN_TERMS_PER_EVENT ?? 40);
const ALLOW_THIN = process.env.VOCAB_ALLOW_THIN === "1";

const clusters = {
  pbm: {
    label: "Business Admin Core",
    examName: "Business Administration Core",
    events: ["BLTDM", "HRM", "PBM"],
    testGenPath: "backend/test-gen-model/data/pbm",
  },
  finance: {
    label: "Finance Cluster",
    examName: "Finance Cluster",
    events: ["ACT", "BFS", "FTDM", "PFN", "PFL"],
    testGenPath: "backend/test-gen-model/data/finance",
  },
  hospitality: {
    label: "Hospitality & Tourism",
    examName: "Hospitality and Tourism Cluster",
    events: ["HLM", "HTDM", "PHT", "QSRM", "RFSM", "TTDM"],
    testGenPath: "backend/test-gen-model/data/hospitality",
  },
  marketing: {
    label: "Marketing Cluster",
    examName: "Marketing Cluster",
    events: ["AAM", "ASM", "BSM", "BTDM", "FMS", "MCS", "MTDM", "PMK", "RMS", "SEM", "STDM"],
    testGenPath: "backend/test-gen-model/data/marketing",
  },
  entrepreneurship: {
    label: "Entrepreneurship",
    examName: "Entrepreneurship Cluster",
    events: ["ENT", "ETDM", "PEN"],
    testGenPath: "backend/test-gen-model/data/entrepreneurship",
  },
};

const eventMeta = {
  AAM: ["Apparel and Accessories Marketing Series", "series", ["market_planning", "promotion", "selling", "customer_relations", "product_service_management", "marketing", "operations", "economics", "marketing_information_management"]],
  ACT: ["Accounting Applications Series", "series", ["financial_analysis", "information_management", "professional_development", "financial_information_management"]],
  ASM: ["Automotive Services Marketing Series", "series", ["customer_relations", "market_planning", "marketing", "economics", "promotion", "communication_skills", "selling"]],
  BFS: ["Business Finance Series", "series", ["financial_analysis", "professional_development", "economics", "financial_information_management"]],
  BLTDM: ["Business Law and Ethics Team Decision Making", "team", ["business_law", "customer_relations", "communication_skills", "economics", "emotional_intelligence", "marketing"]],
  BSM: ["Business Services Marketing Series", "series", ["product_service_management", "customer_relations", "market_planning", "promotion", "emotional_intelligence", "marketing", "pricing", "selling"]],
  BTDM: ["Buying and Merchandising Team Decision Making", "team", ["product_service_management", "market_planning", "selling", "economics", "channel_management"]],
  ENT: ["Entrepreneurship Series", "series", ["product_service_management", "entrepreneurship", "information_management", "marketing_information_management", "channel_management", "promotion", "marketing", "market_planning", "operations", "economics"]],
  ETDM: ["Entrepreneurship Team Decision Making", "team", ["product_service_management", "marketing", "promotion", "human_resources_management", "entrepreneurship"]],
  FMS: ["Food Marketing Series", "series", ["product_service_management", "marketing", "operations", "economics", "selling", "customer_relations", "emotional_intelligence", "information_management", "market_planning", "promotion"]],
  FTDM: ["Financial Services Team Decision Making", "team", ["financial_analysis", "customer_relations", "operations", "economics", "financial_information_management"]],
  HLM: ["Hotel and Lodging Management Series", "series", ["marketing", "selling", "customer_relations", "economics", "operations", "product_service_management", "professional_development", "promotion", "pricing", "financial_analysis"]],
  HRM: ["Human Resources Management Series", "series", ["emotional_intelligence", "human_resources_management", "information_management", "economics", "communication_skills", "customer_relations"]],
  HTDM: ["Hospitality Services Team Decision Making", "team", ["customer_relations", "promotion", "selling", "product_service_management", "economics", "marketing"]],
  MCS: ["Marketing Communications Series", "series", ["promotion", "information_management", "customer_relations", "emotional_intelligence", "market_planning", "marketing", "product_service_management"]],
  MTDM: ["Marketing Management Team Decision Making", "team", ["economics", "market_planning", "communication_skills", "customer_relations", "product_service_management", "promotion", "selling"]],
  PBM: ["Principles of Business Management and Administration", "principles", ["customer_relations", "communication_skills", "information_management", "economics", "emotional_intelligence"]],
  PEN: ["Principles of Entrepreneurship", "principles", ["information_management", "customer_relations", "entrepreneurship", "economics", "communication_skills"]],
  PFL: ["Personal Financial Literacy", "principles", ["financial_analysis", "financial_information_management", "economics", "risk_management"]],
  PFN: ["Principles of Finance", "principles", ["operations", "customer_relations", "communication_skills", "economics", "financial_analysis", "information_management", "professional_development"]],
  PHT: ["Principles of Hospitality and Tourism", "principles", ["economics", "professional_development", "communication_skills", "customer_relations", "emotional_intelligence"]],
  PMK: ["Principles of Marketing", "principles", ["economics", "operations", "professional_development", "communication_skills", "customer_relations", "emotional_intelligence"]],
  QSRM: ["Quick Serve Restaurant Management Series", "series", ["product_service_management", "economics", "promotion", "customer_relations", "marketing", "communication_skills", "operations", "selling", "information_management", "market_planning"]],
  RFSM: ["Restaurant and Food Service Management Series", "series", ["promotion", "communication_skills", "customer_relations", "marketing", "market_planning", "product_service_management", "operations", "selling", "information_management"]],
  RMS: ["Retail Merchandising Series", "series", ["customer_relations", "market_planning", "marketing", "pricing", "product_service_management", "promotion", "economics", "selling", "information_management", "operations", "marketing_information_management"]],
  SEM: ["Sports and Entertainment Marketing Series", "series", ["channel_management", "communication_skills", "economics", "pricing", "market_planning", "customer_relations", "selling", "product_service_management", "information_management", "promotion", "emotional_intelligence"]],
  STDM: ["Sports and Entertainment Marketing Team Decision Making", "team", ["channel_management", "promotion", "economics", "customer_relations", "market_planning", "marketing"]],
  TTDM: ["Travel and Tourism Team Decision Making", "team", ["marketing", "market_planning", "promotion", "customer_relations", "product_service_management"]],
};

function slugify(term) {
  return term.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function readCatalog(dir) {
  const out = {};
  const abs = path.join(catalogRoot, dir);
  if (!fs.existsSync(abs)) return out;
  for (const file of fs.readdirSync(abs)) {
    if (!file.endsWith(".json")) continue;
    const parsed = JSON.parse(fs.readFileSync(path.join(abs, file), "utf8"));
    out[file.replace(/\.json$/, "")] = parsed.terms ?? [];
  }
  return out;
}

const areaCatalog = readCatalog("areas");
const eventCatalog = readCatalog("events");

// Round-robin interleave of per-area term lists: one term from each area per pass.
function interleave(lists) {
  const out = [];
  const max = Math.max(0, ...lists.map((l) => l.length));
  for (let i = 0; i < max; i += 1) {
    for (const list of lists) {
      if (i < list.length) out.push(list[i]);
    }
  }
  return out;
}

function composeDeck(areas, code) {
  const areaLists = areas.map((area) => (areaCatalog[area] ?? []).map((t) => ({ ...t, area })));

  // slug -> set of this event's areas whose catalog contains it (for tag summary).
  const areaBySlug = new Map();
  for (const [i, list] of areaLists.entries()) {
    for (const t of list) {
      const slug = slugify(t.term);
      if (!areaBySlug.has(slug)) areaBySlug.set(slug, new Set());
      areaBySlug.get(slug).add(areas[i]);
    }
  }

  const eventRows = (eventCatalog[code] ?? []).map((t) => ({
    term: t.term,
    slug: slugify(t.term),
    definition: t.definition,
    whyItMatters: t.whyItMatters,
    tags: t.areas ?? [],
    sourceRefs: t.sourceRefs ?? [`backend/roleplay-gen-model/data/${code}`, "backend/test-gen-model/data"],
  }));

  const areaRows = interleave(areaLists).map((t) => {
    const slug = slugify(t.term);
    return {
      term: t.term,
      slug,
      definition: t.definition,
      whyItMatters: t.whyItMatters,
      tags: [...(areaBySlug.get(slug) ?? [])].sort(),
      sourceRefs: t.sourceRefs ?? [`backend/test-gen-model/data/pi/${t.area}.txt`],
    };
  });

  // Event-specific flavor first (guaranteed inclusion), then interleaved area
  // vocab, deduped by slug, capped at MAX_TERMS_PER_EVENT.
  const seen = new Set();
  const deck = [];
  for (const row of [...eventRows, ...areaRows]) {
    if (!row.term || seen.has(row.slug)) continue;
    seen.add(row.slug);
    deck.push(row);
    if (deck.length >= MAX_TERMS_PER_EVENT) break;
  }
  return deck;
}

const thinDecks = [];

for (const [cluster, meta] of Object.entries(clusters)) {
  const clusterPath = path.join(dataRoot, cluster);
  fs.mkdirSync(clusterPath, { recursive: true });

  const manifest = {
    version: 1,
    cluster,
    label: meta.label,
    examName: meta.examName,
    seededFrom: {
      testGenModel: [meta.testGenPath],
      roleplayGenModel: ["backend/roleplay-gen-model/data/events.json", ...meta.events.map((code) => `backend/roleplay-gen-model/data/${code}`)],
    },
    events: [],
  };

  for (const code of meta.events) {
    const [name, format, instructionalAreas] = eventMeta[code];
    const eventPath = path.join(clusterPath, code);
    fs.mkdirSync(eventPath, { recursive: true });
    const terms = composeDeck(instructionalAreas, code);
    if (terms.length < MIN_TERMS_PER_EVENT) thinDecks.push(`${cluster}/${code} (${terms.length})`);
    const payload = {
      version: 1,
      cluster,
      event: { code, name, format },
      instructionalAreas,
      sourceNotes: [
        `Seeded from ${code} roleplay performance indicators and ${meta.examName.toLowerCase()} exam data.`,
        "Terms are scoped for future vocab-card, quiz, and event-filter UI use.",
      ],
      terms,
    };
    fs.writeFileSync(path.join(eventPath, "vocab.json"), `${JSON.stringify(payload, null, 2)}\n`);
    manifest.events.push({ code, name, file: `${code}/vocab.json`, termCount: terms.length });
  }

  fs.writeFileSync(path.join(clusterPath, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
}

if (thinDecks.length) {
  const msg = `[seed-vocab] ${thinDecks.length} deck(s) below floor of ${MIN_TERMS_PER_EVENT}:\n  ${thinDecks.join("\n  ")}`;
  if (ALLOW_THIN) {
    console.warn(`${msg}\n[seed-vocab] VOCAB_ALLOW_THIN=1 — continuing anyway.`);
  } else {
    console.error(`${msg}\n[seed-vocab] Deepen the catalog or re-run with VOCAB_ALLOW_THIN=1.`);
    process.exit(1);
  }
}

console.log(`[seed-vocab] wrote decks for ${Object.keys(clusters).length} cluster(s), cap ${MAX_TERMS_PER_EVENT}/event.`);
