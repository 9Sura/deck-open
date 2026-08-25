# Mirror journal — DECK

A record of what has landed in this repository, newest first.

DECK is developed in a private repository and published here by an export script
that copies an allowlisted subset of the tree. There is no shared history between
the two: this repo starts at its own initial commit, and every entry below is one
export or one edit made directly here. That is deliberate — the private history
carries files that may not be published, and a public history cannot be
un-published.

Each export commit is named for the moment it ran, so a reader can tell how
current the material is:

```
chore(migration): sync the public mirror — 2026-08-24 20:46 EDT
```

**What is not here, and why.** The generators are few-shot: they were shown real
DECA exams and real DECA roleplays as examples. Those source materials are
copyrighted and are not published, and neither is the performance-indicator
library as a standalone file. What ships is the generator *source* and the
material it produced. The practical consequence is stated in the README and worth
repeating: you can clone this repo and run the app, but you cannot run the
generators end to end, because their inputs are the material being withheld.

---

## 2026-08-24

### `chore(migration): sync the public mirror — 2026-08-24 20:46 EDT`

The first sync after the initial mirror, catching up everything from the day
between. 88 files: 50 added, 20 removed, 18 changed.

**The roleplay bank doubled and one shelf of it was rewritten.** It now holds 60
roleplays across two events — Business Law and Ethics Team Decision Making, and
Human Resources Management Series.

- **Business Law and Ethics: 20 of the 30 roleplays are new.** A review of the
  original 30 found problems in most of them, in two recurring shapes:
  performance indicators the situation gave a competitor no way to actually
  demonstrate, and cases where one of the two courses of action was too plainly
  unacceptable to leave a real decision. Those 20 were discarded and written
  again from scratch; the 10 that read clean were left untouched. Ids are never
  reused, so the shelf's numbering has gaps where the discarded files were, and
  the surviving 10 keep their original ids.
- **Human Resources Management: 30 roleplays, new.** The second event to get a
  full shelf.
- **Instructional areas are now drawn the way DECA draws them, for HRM.** Every
  event lists several instructional areas a case can be built around, and the
  generator had been picking between them evenly — which meant a Human Resources
  event kept producing cases whose indicators came from customer relations or
  economics, and produced its own subject only three times in thirty. The draw is
  now weighted by how often each area appears across 19 years of real HRM cases.
  A side effect worth naming: indicators about hotels or retail merchandising
  could previously reach an HR case through those over-drawn areas, and none of
  the 30 has one.

**The quality gate moved twice, and both changes are in the generator source
here.** A roleplay that fails is discarded and rewritten, never edited into
shape, so a stricter gate shows up as re-authored material rather than as patches:

- **Situation length was re-fitted to DECA's current format.** The target had
  been an average over ten years of source material, and DECA's long-form era
  ended in 2021 — so the band was centred on a register no longer in use. It is
  now fitted to 2022-and-later material only, per event, and the target length is
  stated to the author rather than left implicit in a range. All 28 events moved;
  21 of them by more than 15 words.
- **The author's own claim about its work is now checked and can reject it.** Each
  roleplay is written with a short structured tail naming the courses of action it
  offers and what each one costs. Both halves of each option are now matched
  against the prose actually written, and a mismatch discards the candidate. This
  catches the case with only one course of action really on the page. It does not,
  and cannot, judge whether the second option is a *good* one — that is a human
  reading, and nothing here claims otherwise.

Also in this sync: the app's changelog and privacy page, the footer, the settings
data controls, the study dashboard, and the user manual's sections on what a
progress reset clears and what an account stores.

---

## 2026-08-23

### `docs: trim the README to a reader's view`

Dropped the quickstart, the accounts section and the omissions list — a reader
arriving cold needs to know what this is before how to run it.

### `feat(leakage): add the corpus leakage audit`

A tool that measures whether the published material echoes its source. It indexes
every 8-word run in the private corpus, discards runs the performance-indicator
library also produces and runs appearing in three or more distinct source files
(that is house style, not a fingerprint), and reports the longest verbatim run
each published item shares with a single source file.

It exists because "our questions are original" had been an assumption sitting
underneath a public repository, and an assumption is not a measurement. The tool
is here; running it needs the private corpus.

### `docs: render the repo structure as a tree in the README`

### `chore: drop the CI workflow and the repo dotfiles from the mirror`

The workflow checked data artifacts against a corpus this repo does not have, so
it could only ever fail here.

### `chore(migration): initial public mirror of DECK — 2026-08-23 18:17 EDT`

450 files. The app, the study material it reads, both generator pipelines'
source, and the user-facing docs.

---

## 2026-08-21

### `Initial commit`

Empty repository, created ahead of the first export.
