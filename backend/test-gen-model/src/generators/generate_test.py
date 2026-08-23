import json
import os
import random
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import requests

# PATHS
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PI_DIR = DATA_DIR / "pi"
CLUSTERS_CONFIG_PATH = DATA_DIR / "clusters.json"
PROMPTS_DIR = BASE_DIR / "src" / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.txt"
OUTPUT_DIR = BASE_DIR / "output"
REPO_ROOT = BASE_DIR.parents[1]


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a local .env into os.environ (no dependency).

    Looks in the repo root and this package dir. Never overrides a variable that
    is already set in the real environment, so an explicit `export` still wins.
    Lines that are blank, comments (#), or lack an '=' are skipped; surrounding
    quotes on the value are stripped. The .env file is git-ignored (see
    .gitignore) so real keys are never committed.
    """
    for env_path in (REPO_ROOT / ".env", BASE_DIR / ".env"):
        if not env_path.is_file():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

# ---- Model backend ----------------------------------------------------------
# The live single-question path (generate_one) runs against local Ollama, the only
# dependable generator. Hosted free tiers (Groq / Cerebras / Gemini) were evaluated
# and dropped: their free budgets are per-account and exhaust almost immediately
# (Groq 429, Cerebras 402, Gemini 429 all observed in one sitting — plan 07-8 §0.2),
# so none can serve real generation. Ollama is unlimited but slow (~29s p50); that
# is fine because serving is bank-first (§3a) and generation is background (§3b),
# and the length tell it carries is handled by background rejection sampling (§5).
LLM_BACKEND = "ollama"  # kept as a constant so /health still reports the backend.


def active_model_name() -> str:
    return OLLAMA_MODEL


OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")
REQUEST_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600")) 
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.4"))

NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# Stream tokens from Ollama by default so the user sees live progress instead of
# a blank terminal. Set OLLAMA_STREAM=0 for the blocking path (programmatic use).
STREAM = os.environ.get("OLLAMA_STREAM", "1").lower() not in ("0", "false", "no", "")


TARGET_QUESTIONS = int(os.environ.get("TEST_TARGET_QUESTIONS", "10"))
# Hard cap of 10 questions per model call, regardless of env override, to keep
# each batch small enough for reliable, well-formed output.
MAX_BATCH_SIZE = 10
BATCH_SIZE = min(int(os.environ.get("TEST_BATCH_SIZE", "10")), MAX_BATCH_SIZE)
MAX_EXAMPLE_QUESTIONS = int(os.environ.get("TEST_MAX_EXAMPLES", "5"))
MAX_RETRIES = int(os.environ.get("TEST_MAX_RETRIES", "2"))
DIFFICULTY_LEVELS = ["District", "Association", "ICDC"]

# Per-question target difficulty (orthogonal to the DECA competition LEVEL above).
# Shared by the live single-question path and the offline bank authoring.
DIFFICULTY_TIERS = ["easy", "medium", "hard"]
# The live single-question path uses fewer few-shot examples than the batch path:
# 2-3 is enough to fix the format for one question and keeps the prompt small/fast.
LIVE_MAX_EXAMPLES = int(os.environ.get("TEST_LIVE_MAX_EXAMPLES", "3"))

# Length-tell rejection sampling for generate_one (plan 07-8 §5). The local model
# makes the correct option the longest ~39% of the time (audit_tells, over the 35%
# gate). When a well-formed draw has the key among the longest options, we reject
# and regenerate it — but only up to TEST_REJECT_RETRIES times, and we still ACCEPT
# such a draw with probability TEST_REJECT_KEEP_LONGEST so the aggregate lands near
# the 25% chance baseline instead of inverting into the mirror defect (key always
# shortest). Set TEST_REJECT_RETRIES=0 to disable (e.g. for lowest-latency on-demand
# serving); the background pre-gen job leaves it on, where the extra calls are free.
TEST_REJECT_RETRIES = int(os.environ.get("TEST_REJECT_RETRIES", "3"))
TEST_REJECT_KEEP_LONGEST = float(os.environ.get("TEST_REJECT_KEEP_LONGEST", "0.35"))

# Appended to the user message only when a target difficulty is requested (live
# gen + pool authoring). The batch CLI path passes no difficulty and is unaffected.
DIFFICULTY_DIRECTIVE = (
    "TARGET DIFFICULTY: {difficulty}\n"
    "  easy   -- single-fact recall/definition; one clearly correct option.\n"
    "  medium -- apply the concept to the described scenario; distractors "
    "plausible & same-domain.\n"
    "  hard   -- multi-step reasoning/computation, or discriminating between two "
    "near-correct options.\n"
    "Add a final line 'Difficulty: {difficulty}' to each question block."
)


# Cluster definitions, the shared instructional-area core, and DECA's
# name-punctuation overrides all live in data/clusters.json so content changes
# (new area, renamed cluster) don't require touching this module.
def _load_clusters_config() -> Dict:
    raw = json.loads(CLUSTERS_CONFIG_PATH.read_text(encoding="utf-8"))
    core = raw["core"]
    clusters = {
        key: {
            "exam_name": cfg["exam_name"],
            "folder": cfg["folder"],
            # Each cluster is the shared core plus its own extra areas.
            "pi_sections": core + cfg.get("extra_areas", []),
        }
        for key, cfg in raw["clusters"].items()
    }
    return {"clusters": clusters, "area_names": raw.get("area_names", {})}


_CONFIG = _load_clusters_config()
CLUSTERS: Dict[str, Dict] = _CONFIG["clusters"]

# DECA writes a few instructional-area names with specific punctuation; everything
# else is just the slug title-cased.
AREA_NAME_OVERRIDES: Dict[str, str] = _CONFIG["area_names"]


# ----------------------------
# Small helpers
# ----------------------------
def humanize_area(slug: str) -> str:
    """Turn a pi/ file stem into its DECA instructional-area name."""
    return AREA_NAME_OVERRIDES.get(slug, slug.replace("_", " ").title())


def prompt_choice(label: str, choices: List[str]) -> str:
    options = ", ".join(choices)
    lookup = {c.lower(): c for c in choices}
    while True:
        answer = input(f"{label} ({options}): ").strip()
        if answer.lower() in lookup:
            return lookup[answer.lower()]
        print(f"  '{answer}' is not valid. Choose one of: {options}\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


# ----------------------------
# Load performance indicators for a cluster
# ----------------------------
def load_pi_by_area(cluster_cfg: Dict) -> Dict[str, List[str]]:
    """Map each mapped instructional area -> its list of performance indicators.

    Empty/missing pi/ files are skipped with a warning so a thin data set still
    produces a valid test instead of crashing.
    """
    pi_by_area: Dict[str, List[str]] = {}
    for slug in cluster_cfg["pi_sections"]:
        pi_file = PI_DIR / f"{slug}.txt"
        if not pi_file.exists():
            print(f"  [warn] Missing PI file, skipping: {pi_file.name}")
            continue

        lines = [ln.strip() for ln in read_text(pi_file).splitlines() if ln.strip()]
        if not lines:
            print(f"  [warn] Empty PI section, skipping: {pi_file.name}")
            continue

        pi_by_area[humanize_area(slug)] = lines

    return pi_by_area


# ----------------------------
# Distribute questions across areas, then sample PIs
# ----------------------------
def _apportion(
    counts: Dict[str, int], n: int, pi_by_area: Dict[str, List[str]]
) -> None:
    """Add `n` questions to `counts`, weighted by PI count (largest-remainder)."""
    if n <= 0:
        return
    areas = list(counts.keys())
    total_pis = sum(len(pi_by_area[a]) for a in areas)
    quotas = {a: n * len(pi_by_area[a]) / total_pis for a in areas}
    floors = {a: int(quotas[a]) for a in areas}
    leftover = n - sum(floors.values())
    # Hand the leftover to the areas with the largest fractional remainder.
    by_remainder = sorted(areas, key=lambda a: quotas[a] - floors[a], reverse=True)
    for a in by_remainder[:leftover]:
        floors[a] += 1
    for a in areas:
        counts[a] += floors[a]


def allocate_questions(pi_by_area: Dict[str, List[str]], total: int) -> Dict[str, int]:
    """Split `total` questions across areas, weighted by each area's PI count.

    Exam-size requests (>= number of areas) guarantee at least one question per
    area so the test covers the full breadth of the cluster. Smaller "quick quiz"
    requests honor the exact count and simply sample that many questions across
    areas by weight -- some areas may get none, which is expected for a short quiz.
    """
    areas = list(pi_by_area.keys())
    n_areas = len(areas)
    counts = {a: 0 for a in areas}

    if total >= n_areas:
        # Exam-style: floor of 1 per area, then apportion the remainder by weight.
        for a in areas:
            counts[a] = 1
        _apportion(counts, total - n_areas, pi_by_area)
    else:
        # Quiz-style: no coverage guarantee; sample `total` across areas by weight.
        _apportion(counts, total, pi_by_area)

    return counts


def select_pis(
    pi_by_area: Dict[str, List[str]], counts: Dict[str, int]
) -> List[Dict[str, str]]:
    """Randomly pick the allocated number of PIs from each area.

    Sampling is without replacement when an area has enough PIs. If an area is
    allotted more questions than it has PIs, the extra questions reuse PIs (a PI
    may be assessed by more than one question). The final list is shuffled so the
    test isn't grouped by area.
    """
    items: List[Dict[str, str]] = []
    for area, n in counts.items():
        pis = pi_by_area[area]
        if n <= len(pis):
            chosen = random.sample(pis, n)
        else:
            chosen = list(pis) + random.choices(pis, k=n - len(pis))
        for pi in chosen:
            items.append({"area": area, "pi": pi})

    random.shuffle(items)
    return items


# ----------------------------
# Load a few example questions for a cluster
# ----------------------------
def _split_on_question(text: str) -> List[str]:
    """Segment text on each ``Question:`` line, one block per question.

    Splits at every line starting with ``Question:`` (case-insensitive), taking
    each match up to the next. This is the reliable boundary when the model omits
    the ``---`` separators -- a 3B model does this often -- which would otherwise
    collapse a whole batch into one blob. Any preamble before the first
    ``Question:`` is dropped. If the text has no ``Question:`` line at all (e.g. a
    numbered source exam), it is returned unchanged so ``---`` splitting still works.
    """
    matches = list(re.finditer(r"^Question:", text, flags=re.M | re.I))
    if not matches:
        stripped = text.strip()
        return [stripped] if stripped else []
    segments = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.start() : end].strip()
        if seg:
            segments.append(seg)
    return segments


def _split_example_questions(text: str) -> List[str]:
    """Split a raw exam file into individual question blocks.

    Both the core and cluster exam formats separate questions with a line of
    three or more hyphens; we split on those first, then re-split any part on the
    ``Question:`` boundary so a missing separator can't merge two questions. A
    block only counts as usable if it actually contains an answer and option A,
    which also drops the file's metadata header.
    """
    blocks = []
    for part in re.split(r"^-{3,}\s*$", text, flags=re.M):
        for seg in _split_on_question(part):
            if re.search(r"^Answer:", seg, re.M) and re.search(r"^A[.)]", seg, re.M):
                blocks.append(seg)
    return blocks


def _normalize_example(block: str) -> str:
    """Strip the source's question numbering so it doesn't leak into output."""
    block = re.sub(r"^(?:Question\s+\d+\s*:\s*|\d+\.\s*)", "", block.strip())
    if not block.lower().startswith("question:"):
        block = f"Question: {block}"
    return block


# The file read + parse is the slow part; cache the raw block list per folder so
# repeated live calls (which re-sample per question) only pay it once (see §1.3).
_EXAMPLE_BLOCK_CACHE: Dict[str, List[str]] = {}


def _collect_example_blocks(cluster_cfg: Dict) -> List[str]:
    folder_name = cluster_cfg["folder"]
    cached = _EXAMPLE_BLOCK_CACHE.get(folder_name)
    if cached is not None:
        return cached

    folder = DATA_DIR / folder_name
    files = sorted(folder.glob("*.txt"))
    all_blocks: List[str] = []
    for f in files:
        all_blocks.extend(_split_example_questions(read_text(f)))
    _EXAMPLE_BLOCK_CACHE[folder_name] = all_blocks
    return all_blocks


def load_examples(
    cluster_cfg: Dict, max_examples: int = MAX_EXAMPLE_QUESTIONS, verbose: bool = True
) -> str:
    """Sample a small set of real question blocks as style references.

    The parsed block list is cached per folder (``_collect_example_blocks``); each
    call still re-samples so few-shot variety is preserved without re-reading files.
    """
    all_blocks = _collect_example_blocks(cluster_cfg)
    folder = DATA_DIR / cluster_cfg["folder"]
    if not all_blocks:
        if verbose:
            print(f"  [warn] No parsable example questions in {folder}")
        return ""

    k = min(max_examples, len(all_blocks))
    sample = [_normalize_example(b) for b in random.sample(all_blocks, k)]
    if verbose:
        print(
            f"  Sampled {k} example question(s) from {len(all_blocks)} found "
            f"in {folder.name}/"
        )
    return "\n\n---\n\n".join(sample)


# ----------------------------
# Build the user message for one PI batch
# ----------------------------
def format_pi_batch(items: List[Dict[str, str]]) -> str:
    blocks = []
    for it in items:
        blocks.append(
            f"- INSTRUCTIONAL AREA: {it['area']}\n"
            f"  PERFORMANCE INDICATOR: {it['pi']}"
        )
    return "\n".join(blocks)


STRICT_REMINDER = (
    "FORMATTING REMINDER: Output ONLY the question blocks. Every block MUST contain, "
    "each on its own line: 'Question:', 'A.', 'B.', 'C.', 'D.', 'Answer:' (a single "
    "letter A-D), 'Explanation:', 'Instructional Area:', and 'Performance Indicator:'. "
    "Do NOT number the questions, use markdown headers, or add any preamble, summary, "
    "or commentary. Separate consecutive blocks with a line containing only ---."
)


def build_user_message(
    exam_name: str,
    level: str,
    pi_items: List[Dict[str, str]],
    examples: str,
    reminder: str = "",
    difficulty: Optional[str] = None,
) -> str:
    parts = [
        f"EXAM/CATEGORY: {exam_name}",
        f"COMPETITION LEVEL: {level}",
        "",
        "PERFORMANCE INDICATORS TO ASSESS "
        "(write exactly ONE question per indicator, in the order given):",
        format_pi_batch(pi_items),
    ]

    if difficulty:
        parts += ["", DIFFICULTY_DIRECTIVE.format(difficulty=difficulty)]

    if examples:
        parts += [
            "",
            "EXAMPLE QUESTIONS (style/tone/format reference ONLY -- never copy the "
            "wording, scenario, or answer):",
            examples,
        ]

    if reminder:
        parts += ["", reminder]

    return "\n".join(parts)


# ----------------------------
# Validate generated output
# ----------------------------
# Only the core question fields are required from the model. The Instructional
# Area and Performance Indicator lines are attached afterwards from the batch item
# we asked about, so a weak model omitting them doesn't cost us a whole question.
REQUIRED_BLOCK_PATTERNS = [
    re.compile(r"^Question:\s*\S", re.M),
    re.compile(r"^A[.)]\s*\S", re.M),
    re.compile(r"^B[.)]\s*\S", re.M),
    re.compile(r"^C[.)]\s*\S", re.M),
    re.compile(r"^D[.)]\s*\S", re.M),
    re.compile(r"^Answer:\s*[ABCD]\b", re.M),
    re.compile(r"^Explanation:\s*\S", re.M),
]


# is_valid_block METHOD
def is_valid_block(block: str) -> bool:
    # Reject a multi-question blob (a missing --- separator merging two questions)
    # so it gets split rather than accepted whole and counted as one.
    if len(re.findall(r"^Question:", block, flags=re.M | re.I)) > 1:
        return False
    return all(p.search(block) for p in REQUIRED_BLOCK_PATTERNS)


# extract_valid_blocks METHOD
def extract_valid_blocks(output: str) -> List[str]:
    """Keep only well-formed question blocks, discarding preamble/noise.

    Splits on the ``---`` separators first, then re-splits each part on the
    ``Question:`` boundary. This makes parsing robust to a model that drops the
    separators: without it, a whole batch collapses into one blob that passes the
    (search-based) validation as a single block, so 9 of 10 questions are lost.
    """
    blocks = []
    for part in re.split(r"^-{3,}\s*$", output, flags=re.M):
        for seg in _split_on_question(part):
            if is_valid_block(seg):
                blocks.append(seg)
    return blocks


# normalize_answer_line METHOD
def normalize_answer_line(block: str) -> str:
    """Reduce the Answer line to a bare letter (e.g. 'Answer: B').

    Some source example files write 'Answer: B. <option text>', and the model
    copies that style. Downstream consumers expect a single letter, so strip
    anything after it regardless of what the model emitted.
    """
    return re.sub(
        r"^(Answer:\s*)([ABCD])\b.*$", r"\1\2", block, flags=re.M
    )


# attach_metadata METHOD
def attach_metadata(block: str, item: Dict[str, str]) -> str:
    """Append the known Instructional Area / Performance Indicator if missing."""
    additions = []
    if not re.search(r"^Instructional Area:", block, re.M):
        additions.append(f"Instructional Area: {item['area']}")
    if not re.search(r"^Performance Indicator:", block, re.M):
        additions.append(f"Performance Indicator: {item['pi']}")
    if additions:
        block = block.rstrip() + "\n" + "\n".join(additions)
    return block


# call_ollama METHOD
def call_ollama(
    system_prompt: str, user_message: str, stream: Optional[bool] = None
) -> str:
    if stream is None:
        stream = STREAM

    url = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": stream,
        "options": {
            "temperature": TEMPERATURE,
            "num_ctx": NUM_CTX,
        },
    }

    if not stream:
        resp = requests.post(
            url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()

    # Streaming path: accumulate NDJSON chunks and print one '.' to stderr per
    # completed question (each new 'Answer:' line) for live progress. Total compute
    # is unchanged; only the perceived latency drops.
    pieces: List[str] = []
    printed = 0
    with requests.post(
        url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT, stream=True
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise requests.RequestException(chunk["error"])
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                pieces.append(piece)
                done_count = "".join(pieces).count("Answer:")
                if done_count > printed:
                    sys.stderr.write("." * (done_count - printed))
                    sys.stderr.flush()
                    printed = done_count
            if chunk.get("done"):
                break
    if printed:
        sys.stderr.write("\n")
        sys.stderr.flush()
    return "".join(pieces).strip()


# call_llm METHOD — the live path's single model entry point.
def call_llm(
    system_prompt: str, user_message: str, stream: Optional[bool] = None
) -> str:
    """Generate one completion via local Ollama (the only backend).

    Kept as a named seam so the live path has one call site; if a dependable
    hosted generator is ever added, route it here."""
    return call_ollama(system_prompt, user_message, stream=stream)


# generate_batch METHOD
def generate_batch(
    system_prompt: str,
    exam_name: str,
    level: str,
    batch: List[Dict[str, str]],
    examples: str,
) -> List[str]:
    """Return validated question blocks for a batch, retrying only what's missing.

    Each PI in the batch holds one slot. Every attempt requests only the still-empty
    slots and fills them (positionally, in request order) with newly returned valid
    blocks, so a 9/10 first pass costs a tiny 1-PI follow-up instead of a full regen.
    Retries stop once every slot is filled or MAX_RETRIES is exhausted.
    """
    filled: List[Optional[str]] = [None] * len(batch)

    reminder = ""
    for attempt in range(1, MAX_RETRIES + 2):
        pending = [i for i, b in enumerate(filled) if b is None]
        if not pending:
            break

        request_items = [batch[i] for i in pending]
        user_message = build_user_message(
            exam_name, level, request_items, examples, reminder
        )
        try:
            output = call_ollama(system_prompt, user_message)
        except requests.RequestException as e:
            print(f"    [error] Ollama request failed: {e}")
            break

        # Map returned blocks positionally onto the still-empty slots we requested.
        blocks = extract_valid_blocks(output)
        for slot, block in zip(pending, blocks):
            filled[slot] = block

        missing = sum(1 for b in filled if b is None)
        if missing == 0:
            break
        if attempt <= MAX_RETRIES:
            print(
                f"    attempt {attempt}: {len(batch) - missing}/{len(batch)} "
                f"well-formed; re-requesting {missing} missing indicator(s)..."
            )
            reminder = STRICT_REMINDER

    kept = sum(1 for b in filled if b is not None)
    if kept < len(batch):
        print(f"    [warn] kept {kept}/{len(batch)} well-formed question(s)")

    # Normalize the Answer line and attach each kept block's Instructional Area /
    # Performance Indicator, preserving the requested PI order.
    return [
        attach_metadata(normalize_answer_line(block), batch[i])
        for i, block in enumerate(filled)
        if block is not None
    ]


# generate_test METHOD
def generate_test(
    cluster_key: str, level: str, target: int = TARGET_QUESTIONS
) -> str:
    cluster_cfg = CLUSTERS[cluster_key]
    system_prompt = read_text(SYSTEM_PROMPT_PATH)

    print(f"\nResolving PIs and examples for '{cluster_key}'...")
    pi_by_area = load_pi_by_area(cluster_cfg)
    examples = load_examples(cluster_cfg)

    if not pi_by_area:
        raise RuntimeError(
            f"No performance indicators available for cluster '{cluster_key}'. "
            "Seed the relevant data/pi/*.txt files first."
        )

    counts = allocate_questions(pi_by_area, target)
    pi_items = select_pis(pi_by_area, counts)

    covered = [a for a in counts if counts[a] > 0]
    mode = "exam" if target >= len(pi_by_area) else "quiz"
    print(
        f"\n  {len(pi_items)} questions across {len(covered)}/{len(pi_by_area)} "
        f"instructional areas ({mode} mode):"
    )
    for area in sorted(covered, key=lambda a: counts[a], reverse=True):
        print(f"       {counts[area]:>3}  {area}  (pool: {len(pi_by_area[area])})")

    batches = [
        pi_items[i : i + BATCH_SIZE] for i in range(0, len(pi_items), BATCH_SIZE)
    ]
    print(
        f"\n  {len(pi_items)} questions "
        f"-> {len(batches)} batch(es) of up to {BATCH_SIZE}\n"
    )

    generated_blocks: List[str] = []
    for idx, batch in enumerate(batches, start=1):
        print(f"  Generating batch {idx}/{len(batches)} ({len(batch)} questions)...")
        blocks = generate_batch(
            system_prompt, cluster_cfg["exam_name"], level, batch, examples
        )
        generated_blocks.extend(blocks)

    print(f"\n  Kept {len(generated_blocks)}/{len(pi_items)} well-formed questions.")
    # Question blocks are separated by a line containing only three hyphens.
    return "\n\n---\n\n".join(generated_blocks)


# ----------------------------
# Live single-question generation (drives the frontend 10-Q JIT flow)
# ----------------------------
# Warm caches so each /generate-question call is just the model round-trip. The
# file/parse steps (system prompt, PI library) are done once per process.
_SYSTEM_PROMPT: Optional[str] = None
_PI_BY_AREA_CACHE: Dict[str, Dict[str, List[str]]] = {}


def get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = read_text(SYSTEM_PROMPT_PATH)
    return _SYSTEM_PROMPT


def get_pi_by_area(cluster_key: str) -> Dict[str, List[str]]:
    cached = _PI_BY_AREA_CACHE.get(cluster_key)
    if cached is None:
        cached = load_pi_by_area(CLUSTERS[cluster_key])
        _PI_BY_AREA_CACHE[cluster_key] = cached
    return cached


# A block's fields are line-oriented (see system.txt OUTPUT FORMAT); a small
# label->key scan is more robust than one big regex when the model wraps the
# Question stem or Explanation across lines.
_BLOCK_LABELS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^Question:\s*(.*)$", re.I), "question"),
    (re.compile(r"^A[.)]\s*(.*)$"), "A"),
    (re.compile(r"^B[.)]\s*(.*)$"), "B"),
    (re.compile(r"^C[.)]\s*(.*)$"), "C"),
    (re.compile(r"^D[.)]\s*(.*)$"), "D"),
    (re.compile(r"^Answer:\s*(.*)$", re.I), "answer"),
    (re.compile(r"^Explanation:\s*(.*)$", re.I), "explanation"),
    (re.compile(r"^Instructional Area:\s*(.*)$", re.I), "instructionalArea"),
    (re.compile(r"^Performance Indicator:\s*(.*)$", re.I), "performanceIndicator"),
    (re.compile(r"^Difficulty:\s*(.*)$", re.I), "difficulty"),
]
# Lines under these keys may wrap; anything else is a hard field boundary.
_WRAPPABLE = {"question", "explanation"}


def parse_block(block: str) -> Dict[str, str]:
    """Parse a validated question text block into its labeled fields."""
    fields: Dict[str, str] = {}
    current: Optional[str] = None
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        for pat, key in _BLOCK_LABELS:
            m = pat.match(line)
            if m:
                fields[key] = m.group(1).strip()
                current = key
                break
        else:
            if current in _WRAPPABLE:
                fields[current] = (fields.get(current, "") + " " + line).strip()
    return fields


def block_to_bank_question(
    block: str,
    cluster_key: str,
    level: str,
    item: Dict[str, str],
    difficulty: str,
) -> Dict:
    """Convert a validated text block into a BankQuestion-shaped dict.

    Shape mirrors the committed bank (see frontend lib/question-bank.ts): the
    MockQuestion core plus id/cluster/level/verified, with difficulty attached.
    """
    fields = parse_block(block)
    answer = fields.get("answer", "")
    answer_letter = answer[0].upper() if answer[:1].upper() in ("A", "B", "C", "D") else ""
    return {
        "id": f"{cluster_key}-{level.lower()}-live-{uuid.uuid4().hex[:8]}",
        "cluster": cluster_key,
        "level": level,
        "instructionalArea": fields.get("instructionalArea") or item["area"],
        "performanceIndicator": fields.get("performanceIndicator") or item["pi"],
        "question": fields.get("question", ""),
        "options": {k: fields.get(k, "") for k in ("A", "B", "C", "D")},
        "answer": answer_letter,
        "explanation": fields.get("explanation", ""),
        # We asked for a specific tier, so that is the source of truth; fall back
        # to whatever the model echoed, then to medium.
        "difficulty": (difficulty or fields.get("difficulty") or "medium").lower(),
        "verified": False,
    }


def _pick_pi(
    pi_by_area: Dict[str, List[str]], area: Optional[str], exclude: set
) -> Dict[str, str]:
    """Pick one {area, pi}. If `area` is given, sample within it; else weight by
    each area's PI count. PIs in `exclude` are skipped to avoid repeats within a
    quiz, unless that would leave nothing to pick."""
    if area:
        # Accept either the DECA area name or its pi/ slug.
        area_name = area if area in pi_by_area else humanize_area(area)
        pis = pi_by_area.get(area_name)
        if not pis:
            raise ValueError(f"Unknown area '{area}' for this cluster.")
        candidates = [p for p in pis if p not in exclude] or pis
        return {"area": area_name, "pi": random.choice(candidates)}

    areas = list(pi_by_area.keys())
    weights = [len(pi_by_area[a]) for a in areas]
    chosen = random.choices(areas, weights=weights, k=1)[0]
    candidates = [p for p in pi_by_area[chosen] if p not in exclude] or pi_by_area[chosen]
    return {"area": chosen, "pi": random.choice(candidates)}


def _key_is_longest(question: Dict) -> bool:
    """True if the correct option is (tied for) the longest — the length tell.

    Reuses audit_tells._measure so the reject filter and the offline gate score
    a question identically. A malformed measure (shouldn't happen post-validation)
    counts as not-longest so it can never wedge the reject loop."""
    from audit_tells import _measure as measure_tell  # sibling module, lazy import

    m = measure_tell(question)
    return bool(m and m["among_longest"])


def generate_one(
    cluster_key: str,
    level: str,
    difficulty: str,
    area: Optional[str] = None,
    exclude_pis: Sequence[str] = (),
) -> Dict:
    """Generate ONE validated BankQuestion-shaped dict for (cluster, level,
    difficulty[, area]). Reuses the batch machinery for a single-item batch and
    retries a malformed block instead of returning junk. Raises on hard failure.

    Applies length-tell rejection sampling (plan 07-8 §5): a well-formed draw whose
    correct option is the longest is rejected and regenerated up to
    TEST_REJECT_RETRIES times, but still accepted with probability
    TEST_REJECT_KEEP_LONGEST so the aggregate 'key is longest' rate lands near the
    25% chance baseline rather than collapsing to always-shortest."""
    if cluster_key not in CLUSTERS:
        raise ValueError(f"Unknown cluster '{cluster_key}'.")
    if difficulty not in DIFFICULTY_TIERS:
        raise ValueError(f"difficulty must be one of {DIFFICULTY_TIERS}.")

    cluster_cfg = CLUSTERS[cluster_key]
    pi_by_area = get_pi_by_area(cluster_key)
    if not pi_by_area:
        raise RuntimeError(
            f"No performance indicators available for cluster '{cluster_key}'."
        )

    item = _pick_pi(pi_by_area, area, set(exclude_pis or ()))
    examples = load_examples(cluster_cfg, max_examples=LIVE_MAX_EXAMPLES, verbose=False)
    system_prompt = get_system_prompt()

    last_error: Optional[Exception] = None
    # The first well-formed draw, kept as a fallback so that exhausting the reject
    # budget on stubbornly-longest draws still returns a valid question, never junk.
    fallback: Optional[Dict] = None
    rejects_left = max(0, TEST_REJECT_RETRIES)
    max_attempts = MAX_RETRIES + 1 + max(0, TEST_REJECT_RETRIES)

    for attempt in range(1, max_attempts + 1):
        # Nudge format only after a MALFORMED draw. A draw rejected for the length
        # tell was already well-formed, so it doesn't need the strict reminder.
        reminder = STRICT_REMINDER if (attempt > 1 and fallback is None) else ""
        user_message = build_user_message(
            cluster_cfg["exam_name"], level, [item], examples, reminder,
            difficulty=difficulty,
        )
        try:
            # Single question: non-streaming is simplest. Runs on local Ollama.
            output = call_llm(system_prompt, user_message, stream=False)
        except requests.RequestException as e:
            last_error = e
            continue

        blocks = extract_valid_blocks(output)
        if not blocks:
            continue

        block = attach_metadata(normalize_answer_line(blocks[0]), item)
        question = block_to_bank_question(block, cluster_key, level, item, difficulty)
        if fallback is None:
            fallback = question

        # Length-tell rejection sampling. Reject a key-is-longest draw only while
        # budget remains and the keep-roll says so; otherwise accept it.
        if (
            rejects_left > 0
            and _key_is_longest(question)
            and random.random() > TEST_REJECT_KEEP_LONGEST
        ):
            rejects_left -= 1
            continue

        return question

    if fallback is not None:
        return fallback
    raise RuntimeError(
        f"generate_one: no valid question after {max_attempts} attempt(s)"
        + (f" (last error: {last_error})" if last_error else "")
    )


def save_output(cluster_key: str, level: str, test_text: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{cluster_key}_{level.lower()}_{stamp}.txt"
    out_path.write_text(test_text, encoding="utf-8")
    return out_path


def main() -> None:
    print("Generate a DECA practice test for a given cluster.\n")

    cluster_key = prompt_choice("DECA cluster", list(CLUSTERS.keys()))
    level = prompt_choice("Competition level", DIFFICULTY_LEVELS)

    test_text = generate_test(cluster_key, level, TARGET_QUESTIONS)

    if not test_text:
        print("\nNo questions were generated.")
        return

    out_path = save_output(cluster_key, level, test_text)
    print(f"\nTest generated and saved to: {out_path}")


if __name__ == "__main__":
    main()
