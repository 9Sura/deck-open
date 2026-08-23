# `data/` is not published

This directory is empty in the public repository, and the generators in
[`../src/generators/`](../src/generators/) will not run without it.

What it holds in the private working repo:

| Path | What it is |
|---|---|
| `{finance,marketing,entrepreneurship,pbm,hospitality}/` | real past DECA exam papers, used as few-shot examples |
| `pi/` | the performance-indicator library, one file per instructional area |
| `pi-pools/` | per-cluster pools of computational PIs |
| `clusters.json` | cluster definitions — the shared `core` areas plus per-cluster `extra_areas` |

The exam papers are DECA's copyrighted material — verbatim question stems,
answer keys, and official explanations. They are inputs to generation and
nothing more: no part of them is copied into the published question bank, and
they are not ours to redistribute. The PI library reproduces a taxonomy authored
by MBA Research, which is likewise not ours to hand out as a file.

So the pipeline is readable here but not runnable. That is deliberate, not an
oversight. What *is* published is its entire output — 16,283 original questions
under [`frontend/public/question-bank/`](../../../frontend/public/question-bank/)
— and every prompt and validation gate that produced them, under
[`../src/`](../src/).

If you want to run the pipeline yourself, point `data/` at your own corpus. The
paths the code expects are the table above; `src/generators/bank_paths.py`
defines where the bank it writes to lives.
