# `data/` is not published

This directory is empty in the public repository. Most of
[`../src/generators/`](../src/generators/) will not run without it.

What it holds in the private working repo:

| Path | What it is |
|---|---|
| 28 event-code directories (`PMK/`, `HRM/`, `BLTDM/`, …) | real past DECA roleplay scenarios, used as few-shot examples |
| `pi/` | the performance-indicator library for roleplay events |
| `novelty/` | a similarity index derived from the scenarios above |
| `events.json`, `seed_axes*.json` | event definitions and the scenario-variation axes |

The roleplays are DECA's copyrighted material and the PI library reproduces MBA
Research's taxonomy. Neither is ours to redistribute, so neither ships. The
authoring driver (`fill_bank.py`), the quality gate (`icdc_gate.py`) and every
prompt are published in full — what they read is what is missing.

`fill_buffer.py --status` comes closest to running — it reports how many days of
the daily challenge are already filled, and reads the dealt day files under
`frontend/public/roleplays/` to do it — but it still loads `events.json` for the
event list first, so it stops there too.

The published output of this pipeline is the roleplay bank under
[`frontend/public/roleplays/bank/`](../../../frontend/public/roleplays/bank/).
