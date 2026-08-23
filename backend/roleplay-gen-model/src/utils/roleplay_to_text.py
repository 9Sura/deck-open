#!/usr/bin/env python3
"""Render bank roleplay JSON into readable text.

Reads `frontend/public/roleplays/bank/<CODE>/<CODE>-NNNN.json` (or any roleplay
JSON that matches the same contract, including the dated day files under
`frontend/public/roleplays/<YYYY>/<MM>/<DD>/`) and writes one `.txt` per
roleplay into `backend/roleplay-gen-model/output/`.

The layout follows the cleaned-txt shape produced by `extract_roleplay.py`, so a
generated roleplay reads like the real DECA files the corpus is built from.

Usage:
  roleplay_to_text.py                    # every shelf in the bank
  roleplay_to_text.py HRM                # one shelf
  roleplay_to_text.py HRM-0001 PFL-0003  # single entries
  roleplay_to_text.py path/to/file.json  # an explicit file or directory

Options:
  --out DIR      output root (default: <model>/output/bank-text)
  --stdout       print instead of writing files
  --width N      wrap prose at N columns; 0 disables wrapping (default 92)
  --meta         append a MACHINE NOTES block (gate/generator/defects)
  --force        overwrite existing .txt files (default: skip unchanged writes)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

# .../backend/roleplay-gen-model/src/utils/roleplay_to_text.py
MODEL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = MODEL_ROOT.parents[1]
BANK_DIR = REPO_ROOT / "frontend" / "public" / "roleplays" / "bank"
DEFAULT_OUT = MODEL_ROOT / "output" / "bank-text"
EVENTS_JSON = MODEL_ROOT / "data" / "events.json"

SHELF_ID = re.compile(r"^[A-Z]{2,6}-\d{3,}$")
SHELF_CODE = re.compile(r"^[A-Z]{2,6}$")


def load_events() -> dict:
    try:
        return json.loads(EVENTS_JSON.read_text()).get("events", {})
    except (OSError, ValueError):
        return {}


def wrap(text: str, width: int, indent: str = "") -> str:
    """Wrap a paragraph block, preserving blank-line paragraph breaks.

    `indent` is a HANGING indent: continuation lines only, so a numbered judge
    question or a "- " bullet keeps its marker flush and its wrapped body lined
    up under the text rather than under the marker.
    """
    if not width:
        return text
    out = []
    for para in text.split("\n\n"):
        lines = []
        for line in para.split("\n"):
            lines.append(textwrap.fill(line, width=width, subsequent_indent=indent)
                         if line.strip() else "")
        out.append("\n".join(lines))
    return "\n\n".join(out)


def pi_text(item) -> str:
    """A performance indicator's displayed text.

    Bank entries carry `{area, pi, role}` pairs, not bare strings -- the area a
    case declared cannot be recovered from the PI afterwards (~26% of distinct
    PIs are filed by DECA under more than one area), so the pair is the schema.
    A real DECA sheet prints the indicator alone, so that is what renders.
    """
    if isinstance(item, dict):
        return str(item.get("pi", item))
    return str(item)


def bullets(items, width: int) -> list[str]:
    return [wrap("- " + pi_text(i), width, indent="  ") for i in items]


def render_exhibit(exhibit: dict, width: int) -> list[str]:
    """Render the exhibit's rows.

    Two real shapes occur (frontend types.ts): a markdown table, or plain
    labelled figures. Split on `|` only when EVERY row has one, matching the
    frontend renderer, so a lone pipe inside a prose row is never mistaken for
    a table.
    """
    rows = [r for r in exhibit.get("rows", []) if str(r).strip()]
    if not rows:
        return []
    title = str(exhibit.get("title", "")).strip()
    head = [f"EXHIBIT: {title}" if title else "EXHIBIT", ""]

    if all("|" in r for r in rows):
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        # drop markdown rule rows (---|---)
        cells = [c for c in cells if not all(re.fullmatch(r":?-{2,}:?", x) for x in c)]
        if cells:
            ncol = max(len(c) for c in cells)
            cells = [c + [""] * (ncol - len(c)) for c in cells]
            widths = [max(len(c[i]) for c in cells) for i in range(ncol)]
            lines = ["  ".join(c[i].ljust(widths[i]) for i in range(ncol)).rstrip()
                     for c in cells]
            return head + lines

    return head + [wrap(str(r), width) for r in rows]


def render(rp: dict, events: dict, width: int, with_meta: bool) -> str:
    code = str(rp.get("code", "")).upper()
    ev = events.get(code, {})
    rid = rp.get("id") or code
    level = rp.get("level", "")
    fmt = rp.get("format", "")

    name = ev.get("event_name", "")
    title = f"{rid} — {level} {fmt}".strip()
    out: list[str] = [title]
    if name:
        out.append(name.upper())
    out.append("")

    if rp.get("date"):
        out.append(f"DATE: {rp['date']}")
    if rp.get("tier"):
        out.append(f"TIER: {rp['tier']}")
    if rp.get("careerCluster"):
        out.append(f"CAREER CLUSTER: {rp['careerCluster']}")
    if rp.get("instructionalArea"):
        out.append(f"INSTRUCTIONAL AREA: {rp['instructionalArea']}")
    # Timings come from events.json, NEVER from participantInstructions, which is
    # boilerplate and unreliable about judge questions (frontend types.ts).
    if ev:
        out.append(
            f"TIMING: {ev.get('prep_minutes', '?')} min prep · "
            f"{ev.get('presentation_minutes', '?')} min presentation · "
            f"{ev.get('participant_roles', '?')} participant(s)"
        )
    out.append("")

    def section(label: str, body: list[str]) -> None:
        if not body:
            return
        out.append(label)
        out.extend(body)
        out.append("")

    section("PARTICIPANT INSTRUCTIONS",
            [wrap(str(rp.get("participantInstructions", "")), width)]
            if rp.get("participantInstructions") else [])
    section("21st CENTURY SKILLS", bullets(rp.get("twentyFirstCenturySkills", []), width))
    section("PERFORMANCE INDICATORS", bullets(rp.get("performanceIndicators", []), width))
    section("EVENT SITUATION",
            [wrap(str(rp.get("situation", "")), width)] if rp.get("situation") else [])

    if rp.get("exhibit"):
        section_body = render_exhibit(rp["exhibit"], width)
        if section_body:
            out.extend(section_body)
            out.append("")

    section("JUDGE ROLE-PLAY CHARACTERIZATION",
            [wrap(str(rp.get("judgeCharacterization", "")), width)]
            if rp.get("judgeCharacterization") else [])

    questions = rp.get("judgeQuestions", [])
    if questions:
        out.append("JUDGE QUESTIONS")
        for i, q in enumerate(questions, 1):
            out.append(wrap(f"{i}. {q}", width, indent=" " * (len(str(i)) + 2)))
        out.append("")

    if with_meta:
        meta = rp.get("meta", {}) or {}
        gate = meta.get("gate", {}) or {}
        gen = meta.get("generator", {}) or {}
        notes = [
            f"gate passed: {gate.get('passed')}"
            + (f" · failed knobs: {', '.join(gate.get('failedKnobs', []))}"
               if gate.get("failedKnobs") else ""),
            f"situation words: {meta.get('situationWords')}",
            f"generator: {gen.get('model')} · passes {gen.get('passes')}",
        ]
        if meta.get("defects"):
            notes.append("defects: " + ", ".join(meta["defects"]))
        for issue in gate.get("issues", []) or []:
            notes.append(f"issue: {issue}")
        # meta is NEVER roleplay text (frontend F10) — it is fenced off here.
        out.append("--- MACHINE NOTES (not part of the roleplay) ---")
        out.extend(notes)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def resolve(targets: list[str]) -> list[Path]:
    """Expand CLI targets into roleplay JSON paths."""
    if not targets:
        return sorted(p for p in BANK_DIR.rglob("*.json") if p.name != "manifest.json")

    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files += [q for q in sorted(p.rglob("*.json")) if q.name != "manifest.json"]
            continue
        if p.is_file():
            files.append(p)
            continue
        up = t.upper()
        if SHELF_ID.match(up):
            cand = BANK_DIR / up.split("-")[0] / f"{up}.json"
            if cand.is_file():
                files.append(cand)
                continue
        if SHELF_CODE.match(up) and (BANK_DIR / up).is_dir():
            files += [q for q in sorted((BANK_DIR / up).glob("*.json"))
                      if q.name != "manifest.json"]
            continue
        sys.stderr.write(f"not found: {t}\n")
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*",
                    help="shelf code (HRM), entry id (HRM-0001), file, or directory")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--width", type=int, default=92, help="0 disables wrapping")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    files = resolve(args.targets)
    if not files:
        sys.stderr.write("nothing to convert\n")
        return 1

    events = load_events()
    written = skipped = failed = 0
    for f in files:
        try:
            rp = json.loads(f.read_text())
        except ValueError as e:
            sys.stderr.write(f"SKIP {f}: bad json ({e})\n")
            failed += 1
            continue
        if not isinstance(rp, dict) or "situation" not in rp:
            sys.stderr.write(f"SKIP {f}: not a roleplay\n")
            failed += 1
            continue

        text = render(rp, events, args.width, args.meta)
        if args.stdout:
            print(text)
            written += 1
            continue

        code = str(rp.get("code", "MISC")).upper()
        rid = str(rp.get("id") or f.stem)
        dest = args.out / code / f"{rid}.txt"
        if dest.exists() and not args.force and dest.read_text() == text:
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        written += 1

    if not args.stdout:
        sys.stderr.write(
            f"wrote {written} · unchanged {skipped} · failed {failed} -> {args.out}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
