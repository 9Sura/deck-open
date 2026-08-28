// Vocab bank generator (assembler).
//
// Reads the reviewable term catalog under catalog/{areas,events}/*.json and
// composes one deck per DECA event, filling it in three tiers of decreasing
// specificity (vocab plan 01 §2), each interleaved round-robin so a many-area
// deck isn't all-economics-first, then deduped by slug and cut at
// MAX_TERMS_PER_EVENT:
//   1. event flavor  — catalog/events/<CODE>.json, guaranteed inclusion
//   2. the event's own roleplay areas — the eventMeta list below
//   3. the rest of the cluster's exam blueprint — `core` + `extra_areas` from
//      backend/test-gen-model/data/clusters.json
// Tier 3 is what makes 250 reachable for a four-area event like ACT, and it is
// correct rather than merely convenient: a series event's written exam IS the
// cluster exam, so every blueprint area is fair game even when it is not in that
// event's roleplay PI list. Tiers 2 and 3 are UNIONED, never assumed to contain
// one another — four events declare an area their cluster blueprint does not
// list (see resolveAreas below), and taking tier 3 alone would silently drop it.
// Tier order is the priority order: the event's own areas are exhausted before
// the wider blueprint is drawn on, so ACT's deck still leans accounting.
// Every term carries sourceRefs tracing to a real PI / roleplay / exam source.
// Fully offline, deterministic, $0 at runtime.
//
// Env: MAX_TERMS_PER_EVENT (default 250), MIN_TERMS_PER_EVENT floor (default 200).
// A deck below the floor fails the build unless VOCAB_ALLOW_THIN=1 (authoring).
// Every catalog term must carry difficulty "medium" | "hard" (vocab plan 01 §5);
// an ungraded term fails the run unless VOCAB_ALLOW_UNGRADED=1. That guard is
// what keeps a deck from being regenerated before the plan's Phase 1 purge has
// graded the catalog it draws from.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { slugify } from "./lib/slug.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const dataRoot = path.join(root, "data");
const catalogRoot = path.join(root, "catalog");

const MAX_TERMS_PER_EVENT = Number(process.env.MAX_TERMS_PER_EVENT ?? 250);
const MIN_TERMS_PER_EVENT = Number(process.env.MIN_TERMS_PER_EVENT ?? 200);
const ALLOW_THIN = process.env.VOCAB_ALLOW_THIN === "1";
const ALLOW_UNGRADED = process.env.VOCAB_ALLOW_UNGRADED === "1";
const DIFFICULTIES = new Set(["medium", "hard"]);

// The exam blueprint — `core` shared by all five clusters plus per-cluster
// `extra_areas`. This is the tier-3 source and it is NOT the `clusters` map
// below: that one is local to this file and holds label / examName / events /
// testGenPath. Both are needed; they describe different things and must not be
// merged. clusters.json drives question allocation across the 16,283-question
// exam bank — this file only reads it.
const blueprintPath = path.join(root, "..", "test-gen-model", "data", "clusters.json");
const blueprint = JSON.parse(fs.readFileSync(blueprintPath, "utf8"));

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

// Reorder one area's terms so that ANY prefix carries approximately the whole
// file's hard share, preserving each difficulty group's authored order.
//
// This is not a preference for `hard` — it is the removal of a preference for
// `medium` that the catalog's authoring history had baked in. Phase 1's purge
// survivors are mostly legacy `medium` and sit at the TOP of every area file;
// Phase 3 appended its 62%-hard batch below them. A 250-card deck round-robins
// across 12-21 areas, so it takes only the first ~12-20 terms of each file —
// exactly that legacy head. Measured on the finished catalog, `promotion` is 53%
// hard overall but 0% hard in its first 15 terms, and
// `marketing_information_management` 66% against 7%. Drawn in authored order the
// decks came out 42-66% hard against a 62%-hard pool, the spread decided by
// nothing but where each file's authoring happened to sit.
//
// A Bresenham-style merge fixes it deterministically: term i is taken from the
// `hard` group when the running hard quota crosses an integer, otherwise from
// `medium`. Every prefix is then a representative sample of the area.
function stratifyByDifficulty(list) {
  const hard = list.filter((t) => t.difficulty === "hard");
  const rest = list.filter((t) => t.difficulty !== "hard");
  const total = list.length;
  if (!hard.length || !rest.length) return list;

  const out = [];
  let hi = 0;
  let ri = 0;
  for (let i = 0; i < total; i += 1) {
    const takeHard = Math.floor(((i + 1) * hard.length) / total) > Math.floor((i * hard.length) / total);
    if (takeHard && hi < hard.length) out.push(hard[hi++]);
    else if (ri < rest.length) out.push(rest[ri++]);
    else out.push(hard[hi++]);
  }
  return out;
}

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

// Tier 2 (the event's own areas) and tier 3 (the rest of its cluster's exam
// blueprint) as two disjoint, order-stable lists. The union is what the draw
// spans; the split is what keeps tier 2 ahead of tier 3.
//
// Containment does NOT hold in either direction, and four events prove it:
// PFL declares `risk_management`, which is in no finance blueprint; ENT declares
// `entrepreneurship` and `marketing_information_management`; ETDM and PEN declare
// `entrepreneurship`. `entrepreneurship` is the sharpest case — it is the one
// area file that appears in no cluster's blueprint at all, so tier 3 alone would
// drop 50 authored terms from all three entrepreneurship decks. That gap is
// deliberate (vocab plan 01 §6, Phase 3): clusters.json is not edited to close
// it, because the union already gets the vocab draw everything it needs.
function resolveAreas(eventAreas, cluster) {
  const own = new Set(eventAreas);
  const blueprintAreas = [...blueprint.core, ...(blueprint.clusters[cluster]?.extra_areas ?? [])];
  return { tier2: eventAreas, tier3: blueprintAreas.filter((area) => !own.has(area)) };
}

function composeDeck(eventAreas, code, cluster) {
  const { tier2, tier3 } = resolveAreas(eventAreas, cluster);
  const listFor = (area) =>
    stratifyByDifficulty((areaCatalog[area] ?? []).map((t) => ({ ...t, area })));
  const tier2Lists = tier2.map(listFor);
  const tier3Lists = tier3.map(listFor);

  // slug -> set of the areas in this event's draw whose catalog contains it (for
  // the tag summary, and so Phase 6's area filter sees every area a card came
  // from — blueprint areas included, not just the event's own).
  const areaBySlug = new Map();
  for (const list of [...tier2Lists, ...tier3Lists]) {
    for (const t of list) {
      const slug = slugify(t.term);
      if (!areaBySlug.has(slug)) areaBySlug.set(slug, new Set());
      areaBySlug.get(slug).add(t.area);
    }
  }

  const eventRows = (eventCatalog[code] ?? []).map((t) => ({
    term: t.term,
    slug: slugify(t.term),
    definition: t.definition,
    whyItMatters: t.whyItMatters,
    difficulty: t.difficulty,
    ...(t.confusableWith?.length ? { confusableWith: t.confusableWith } : {}),
    tags: t.areas ?? [],
    sourceRefs: t.sourceRefs ?? [`backend/roleplay-gen-model/data/${code}`, "backend/test-gen-model/data"],
  }));

  const toAreaRow = (t) => {
    const slug = slugify(t.term);
    return {
      term: t.term,
      slug,
      definition: t.definition,
      whyItMatters: t.whyItMatters,
      difficulty: t.difficulty,
      ...(t.confusableWith?.length ? { confusableWith: t.confusableWith } : {}),
      tags: [...(areaBySlug.get(slug) ?? [])].sort(),
      sourceRefs: t.sourceRefs ?? [`backend/test-gen-model/data/pi/${t.area}.txt`],
    };
  };

  // Event flavor first (guaranteed inclusion), then the event's own areas, then
  // the rest of the blueprint — deduped by slug, capped at MAX_TERMS_PER_EVENT.
  const seen = new Set();
  const deck = [];
  const draw = [
    ...eventRows,
    ...interleave(tier2Lists).map(toAreaRow),
    ...interleave(tier3Lists).map(toAreaRow),
  ];
  for (const row of draw) {
    if (!row.term || seen.has(row.slug)) continue;
    seen.add(row.slug);
    deck.push(row);
    if (deck.length >= MAX_TERMS_PER_EVENT) break;
  }
  return deck;
}

const thinDecks = [];
const ungraded = [];

// Compose every deck in memory FIRST, then check the guards, then write. A guard
// that fires after the write has already published what it was meant to stop.
const pending = [];

for (const [cluster, meta] of Object.entries(clusters)) {
  const clusterPath = path.join(dataRoot, cluster);

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
    const terms = composeDeck(instructionalAreas, code, cluster);
    if (terms.length < MIN_TERMS_PER_EVENT) thinDecks.push(`${cluster}/${code} (${terms.length})`);
    for (const t of terms) {
      if (!DIFFICULTIES.has(t.difficulty)) ungraded.push(`${cluster}/${code}: ${t.slug} (${t.difficulty ?? "none"})`);
    }
    const payload = {
      version: 1,
      cluster,
      event: { code, name, format },
      instructionalAreas,
      sourceNotes: [
        `Seeded from ${code} roleplay performance indicators and ${meta.examName.toLowerCase()} exam data.`,
        `Drawn in three tiers: ${code} event flavor, then this event's own instructional areas, then the rest of the ${meta.examName.toLowerCase()} exam blueprint.`,
        "Terms are scoped for future vocab-card, quiz, and event-filter UI use.",
      ],
      terms,
    };
    pending.push({ file: path.join(clusterPath, code, "vocab.json"), payload });
    manifest.events.push({ code, name, file: `${code}/vocab.json`, termCount: terms.length });
  }

  pending.push({ file: path.join(clusterPath, "manifest.json"), payload: manifest });
}

if (ungraded.length) {
  const shown = ungraded.slice(0, 20);
  const rest = ungraded.length - shown.length;
  const msg = `[seed-vocab] ${ungraded.length} deck term(s) carry no difficulty of "medium" | "hard":\n  ${shown.join("\n  ")}${rest > 0 ? `\n  ...and ${rest} more` : ""}`;
  if (ALLOW_UNGRADED) {
    console.warn(`${msg}\n[seed-vocab] VOCAB_ALLOW_UNGRADED=1 — continuing anyway.`);
  } else {
    console.error(`${msg}\n[seed-vocab] Grade the catalog (vocab plan 01 Phase 1) or re-run with VOCAB_ALLOW_UNGRADED=1.`);
    process.exit(1);
  }
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

for (const { file, payload } of pending) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`);
}

console.log(`[seed-vocab] wrote decks for ${Object.keys(clusters).length} cluster(s), cap ${MAX_TERMS_PER_EVENT}/event.`);
