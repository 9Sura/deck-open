#!/usr/bin/env python3
"""Extract a DECA roleplay PDF into the approved cleaned-txt format.

Usage: extract_roleplay.py <pdf> <ABBR> <SERIES NAME> <YEAR> <EVENT_NO> <LEVEL>
Prints formatted txt to stdout. Exits 2 (SKIP) if new-format/non-standard.
"""
import sys, os, re, difflib
import fitz  # pymupdf

BULLET = re.compile(r'^\s*[▪§•●‣⁃\*]\s*')

def is_furniture(s, abbr):
    s = s.strip()
    if re.fullmatch(r'\d+', s):
        return True
    if re.fullmatch(rf'{abbr}-?\s*\d{{2}}', s, re.I):
        return True
    suffix = r'\s*(?:[-–]?\s*(?:Virtual|CR))?'   # older running headers add "- Virtual" / "- CR"
    if re.fullmatch(rf'(District|Association|International|ICDC)\s+(Career\s+Development\s+Conference\s+)?Event\s*#?\s*\d*{suffix}', s, re.I):
        return True
    if re.fullmatch(rf'(DISTRICT|ASSOCIATION|ICDC)\s+EVENT\s*#?\s*\d*{suffix}', s, re.I):
        return True
    if 'Published' in s and 'DECA' in s:
        return True
    if 'written permission' in s or 'Printed in the United States' in s:
        return True
    return False

def normalize_quotes(s):
    return (s.replace('’', "'").replace('‘', "'")
             .replace('“', '"').replace('”', '"')
             .replace('–', '–'))  # keep en-dash as-is

def load_lines(pdf, abbr):
    """Return cleaned lines with '' marking paragraph breaks (collapsed)."""
    doc = fitz.open(pdf)
    text = normalize_quotes("\n".join(p.get_text() for p in doc))
    # Cut the evaluation section. Header is line-anchored and may be titled
    # "EVALUATION INSTRUCTIONS" or "JUDGE'S EVALUATION INSTRUCTIONS" (older files),
    # possibly with irregular spacing. Line-anchoring avoids matching the mid-line
    # "Judge Evaluation Instructions and Judge Evaluation Form" boilerplate on p.3.
    m = re.search(r"\n[ \t]*(?:JUDGE'?S\s+)?EVALUATION\s+INSTRUCTIONS", text, re.I)
    if m:
        text = text[:m.start()]
    out = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            if out and out[-1] != '':
                out.append('')          # keep single paragraph break
            continue
        if is_furniture(s, abbr):
            continue
        out.append(s)
    while out and out[-1] == '':
        out.pop()
    return out, text

def is_header(line, label):
    """A section header is a STANDALONE line equal to the label (ignoring case,
    trailing ':' and surrounding whitespace). Prevents matching prose that merely
    starts with the same words (e.g. '...performance indicators of this event.')."""
    return line.strip().rstrip(':').upper() == label

def find_idx(lines, label):
    for i, l in enumerate(lines):
        if is_header(l, label):
            return i
    return -1

def value_after(lines, label):
    i = find_idx(lines, label)
    if i < 0:
        return ''
    for j in range(i+1, len(lines)):
        if lines[j]:
            return lines[j]
    return ''

def between(lines, start_label, end_labels):
    i = find_idx(lines, start_label)
    if i < 0:
        return []
    seg = []
    for l in lines[i+1:]:
        if any(is_header(l, e) for e in end_labels):
            break
        seg.append(l)
    return seg

def to_bullets(seg):
    # An item starts with a bullet glyph (▪ § •) OR a number ("1. "). Older files
    # number their performance indicators instead of bulleting them.
    def is_item(l):
        return bool(BULLET.match(l) or re.match(r'^\d+\.\s', l))
    strip_marker = re.compile(r'^\s*(?:[▪§•●‣⁃\*]|\d+\.)\s*')
    res = []
    for l in seg:
        if l == '':
            continue
        if is_item(l):
            res.append(strip_marker.sub('', l))
        elif res:
            res[-1] += ' ' + l            # wrapped continuation
        else:
            res.append(l)
    # older files sometimes put the whole numbered list on ONE line
    # ("1. A 2. B 3. C") -> after stripping the leading "1." it survives as a
    # single run-on item; split it back into separate indicators.
    if len(res) == 1 and re.search(r'\s\d+\.\s', res[0]):
        res = [p.strip() for p in re.split(r'\s+\d+\.\s+', res[0]) if p.strip()]
    return ['- ' + r for r in res]

def to_blocks(seg):
    """Group into paragraph blocks. Wrapped lines are joined with spaces, but a
    line starting 'N. ' begins a new sub-line kept on its own line within the
    block (so numbered judge questions render as a tight list, not one run-on)."""
    blocks, subs = [], []
    def flush():
        if subs:
            blocks.append("\n".join(subs)); subs.clear()
    for l in seg:
        if l == '':
            flush()
        elif re.match(r'^\d+\.\s', l):
            subs.append(l)
        elif subs:
            subs[-1] += ' ' + l
        else:
            subs.append(l)
    flush()
    # bind a "...:" intro line to the numbered list that follows it (tight list)
    merged = []
    for b in blocks:
        if merged and merged[-1].rstrip().endswith(':') and re.match(r'^\d+\.\s', b):
            merged[-1] += "\n" + b
        else:
            merged.append(b)
    return merged

def main():
    pdf, abbr, series, year, evno, level = sys.argv[1:7]
    yy = year[-2:]
    lines, rawtext = load_lines(pdf, abbr)
    if '21st Century Skills'.upper() not in rawtext.upper():
        sys.stderr.write(f"SKIP:new-format-or-nonstandard\n"); sys.exit(2)

    cluster = value_after(lines, 'CAREER CLUSTER')
    pathway = value_after(lines, 'CAREER PATHWAY')
    inst    = value_after(lines, 'INSTRUCTIONAL AREA')

    # Series events use "EVENT SITUATION"; Team Decision Making events use
    # "CASE STUDY SITUATION" for the same slot (otherwise identical structure).
    sit_label = 'EVENT SITUATION' if find_idx(lines, 'EVENT SITUATION') >= 0 else 'CASE STUDY SITUATION'

    pi   = to_bullets(between(lines, 'PARTICIPANT INSTRUCTIONS', ['21ST CENTURY SKILLS']))
    sk   = to_bullets(between(lines, '21ST CENTURY SKILLS', ['PERFORMANCE INDICATORS']))
    perf = to_bullets(between(lines, 'PERFORMANCE INDICATORS', [sit_label]))
    esit = to_blocks(between(lines, sit_label,
                    ["JUDGE'S INSTRUCTIONS", 'JUDGE INSTRUCTIONS',
                     'JUDGE ROLE-PLAY CHARACTERIZATION', 'JUDGE CHARACTERIZATION',
                     'JUDGE SITUATION CHARACTERIZATION']))

    # Judge section header wording varies by era/family: newer files use
    # "JUDGE ROLE-PLAY CHARACTERIZATION"; older Principles/PFL (2017-2019) title it
    # "JUDGE SITUATION CHARACTERIZATION". Try each in turn so the body is never dropped.
    judge = to_blocks(between(lines, 'JUDGE ROLE-PLAY CHARACTERIZATION', ['ZZZ_END']))
    if not judge:
        judge = to_blocks(between(lines, 'JUDGE CHARACTERIZATION', ['ZZZ_END']))
    if not judge:
        judge = to_blocks(between(lines, 'JUDGE SITUATION CHARACTERIZATION', ['ZZZ_END']))
    if not judge:
        # Older Team Decision Making files (2017-2019) have NO separate
        # characterization header: the judge role-play + questions sit directly
        # under "JUDGE'S INSTRUCTIONS", ending at the "JUDGING THE PRESENTATION"
        # evaluation boilerplate. (In every other format JUDGE INSTRUCTIONS is
        # boilerplate and a real characterization header exists, so this branch is
        # only reached once those yielded nothing.)
        for jlabel in ("JUDGE'S INSTRUCTIONS", 'JUDGE INSTRUCTIONS'):
            judge = to_blocks(between(lines, jlabel,
                        ['JUDGING THE PRESENTATION', "JUDGE'S EVALUATION FORM"]))
            if judge:
                break

    # condense judge background if it duplicates the event situation
    event_blob = ' '.join(esit)
    def contained(block):
        # autojunk=False: on long event text, difflib otherwise treats common
        # chars as junk and under-matches verbatim repeats inconsistently.
        sm = difflib.SequenceMatcher(None, block, event_blob, autojunk=False)
        return sum(b.size for b in sm.get_matching_blocks()) / max(1, len(block))
    # matches single-participant "participant will present" and team
    # "(participant team) will present" phrasings alike
    pres = next((i for i, p in enumerate(judge) if re.search(r'(?:participant|team)[^\n]*\bwill present\b', p, re.I)), None)
    if pres is not None and pres >= 1:
        framing, background, tail = judge[:1], judge[1:pres], judge[pres:]
        if os.environ.get('DEBUG_CONDENSE'):
            for b in background:
                sys.stderr.write(f"[{contained(b):.2f}] {b[:70]}...\n")
        # drop background paragraphs that are (near-)verbatim repeats of the event
        # situation; KEEP any paragraph carrying info not already stated there.
        kept = [b for b in background if contained(b) <= 0.80]
        if len(kept) < len(background):   # dropped at least one repeat
            mid = [f'(Business background is the same as the {sit_label.title()} above.)'] + kept
        else:
            mid = background
        judge = framing + mid + tail

    header = [f"{abbr}-{yy} — {level} Event {evno}", series.upper(), ""]
    for lbl, val in [("CAREER CLUSTER", cluster), ("CAREER PATHWAY", pathway),
                     ("INSTRUCTIONAL AREA", inst)]:
        if val:                       # omit fields the PDF doesn't have (e.g. ENT has no pathway)
            header.append(f"{lbl}: {val}")
    out = [*header, "",
           "PARTICIPANT INSTRUCTIONS", *pi, "",
           "21st CENTURY SKILLS", *sk, "",
           "PERFORMANCE INDICATORS", *perf, "",
           sit_label, "\n\n".join(esit), "",
           "JUDGE ROLE-PLAY CHARACTERIZATION", "\n\n".join(judge), ""]
    print("\n".join(out))

if __name__ == '__main__':
    main()
