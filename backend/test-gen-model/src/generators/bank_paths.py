"""Where the question bank lives. The ONE definition — import it, never re-derive it.

The bank is a SINGLE tree at `frontend/public/question-bank/`, which is both what the
generators read and write and what the app serves. There is deliberately no backend
copy (issue #203). Two paths holding the same text is the duplication the roleplay
bank already refuses -- `frontend/public/roleplays/bank/` is canonical for the same
reason, and this side had drifted into holding 20M of it twice.

WHAT THIS REPLACED, AND WHY IT WAS WORTH A MODULE
-------------------------------------------------
`BANK_DIR = BASE_DIR / "question bank"` was copy-pasted into nine generators, seven
slice-tool files and two shell globs -- EIGHTEEN independent literals for one fact, so
rerouting the bank meant editing eighteen files and hoping the grep was complete. The
issue that proposed this counted fifteen and put three of them in a column headed
"path-agnostic"; they were not.
It also carried a SPACE, which every command in every plan had to quote around and
which `verify_bank` needed a paragraph of comment to explain surviving `git ls-tree`.
The new path has neither problem.

WHAT THIS DOES NOT DO
---------------------
It does not restore the publish gate it removed. Until issue #203 the backend tree was
the staging buffer: a slice wrote there, and `npm run sync-bank` published to the
frontend once a whole CLUSTER closed, in its own commit (CLAUDE.md's standing rule,
made deliberate by issue #63). With one tree, a bank write IS a write to what the app
serves and `git status` is the remaining guard -- so DO NOT COMMIT a partially built
cluster. That gate was retired on the measured grounds that plan 10 is complete and
Section 10-17 was its last bank-writing slice; a future generation campaign should
re-read that decision rather than inherit it.

Note also that `verify_bank --additive` now proves additivity of the PUBLISHED bank,
which is the stronger guarantee -- but it is not universal: Section 10-17 established
that a non-additive bank edit is legitimate, gated by `verify_reword.py` instead.
"""

from pathlib import Path

# .../backend/test-gen-model/src/generators/bank_paths.py
#      [4]     [3]             [2] [1]        [0]
REPO_ROOT = Path(__file__).resolve().parents[4]

# Canonical AND served. Next.js serves `frontend/public/` verbatim, so a question at
# `<cluster>/<file>.json` here is reachable at `/question-bank/<cluster>/<file>.json`.
BANK_DIR = REPO_ROOT / "frontend" / "public" / "question-bank"
MANIFEST_PATH = BANK_DIR / "manifest.json"
