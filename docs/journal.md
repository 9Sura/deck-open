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

## 2026-08-30

### `chore(migration): sync the public mirror — 2026-08-30 23:31 EDT`

Six new roleplay shelves, and a pass over text that sits on a coloured background
in every theme.

**The roleplay bank went from 60 practice roleplays to 240.** Six shelves were
filled, 30 each: Principles of Business Management and Administration, Personal
Financial Literacy and Sports and Entertainment Marketing, then Entrepreneurship,
Business Finance and Quick Serve Restaurant Management. With the two shelves that
were already here, that is 240 roleplays on 8 of the 28 events. The last three
matter beyond the count: until this run no banked roleplay came from the
Entrepreneurship, Finance, or Hospitality and Tourism career clusters at all, and
each of those events opens one. The remaining 20 shelves are still empty — the
bank is being rebuilt event by event, and the app tells you when an event has
nothing banked yet.

Every one of the 240 was authored against the same deterministic quality gate and
banked only after passing it; a roleplay that fails is discarded and written again
rather than patched.

**Coloured text is readable on every theme now, which it was not.** Three separate
problems, all the same shape — a colour chosen to be a *fill* was being used as
*text*:

- On First Bloom and Midsummer, filled buttons painted near-white writing on a
  mid-tone green or coral. That is the DECK logo, the main call to action and every
  primary button, on every page, on those two themes. The writing on top is now
  dark. First Bloom keeps its green and its blossom pink; Midsummer keeps its coral
  but its magenta moved a shade deeper, because it was the one colour where no
  writing — white or black — was readable enough.
- The accent-coloured word in a page heading (the *pool* in "Browse the pool", and
  the same treatment on the vocab, roleplay, progress and review pages) used the
  fill colour rather than the darker text tone that had been sitting unused in every
  theme since the themes shipped. Sixteen places moved onto it. Golden Hour,
  Midsummer and First Bloom were the ones failing; the two dark themes got clearer
  as a side effect.
- The selected option in a segmented control — the level and mode switches on the
  question bank — was a gold pill that no text colour could sit on legibly in the
  two dark themes. The dark themes now use a much lighter wash of that gold; the
  four light themes are pixel-identical to before.

Every one of these was measured on the rendered page in each of the six themes,
not read off the stylesheet.

**The vocab flashcard is one box on both sides.** The term side was drawing a
shorter card than the definition side, and the term itself sat below the middle of
the card because it was centring inside the space under the header rather than on
the card. Both faces are now the same frame and the term is centred on it.

**Saving your data out of Settings is more reliably a download.** The export built
its download link in a way some browsers are entitled to ignore, and a download that
never starts reports no error, so the button could have finished with no file and no
message. That could not be reproduced in the browser available to test, so this is a
correctness fix rather than an observed bug being closed.

## 2026-08-28

### `chore(migration): sync the public mirror — 2026-08-28 19:32 EDT`

Two changes to how vocabulary works: the decks were re-dealt so each one covers the
whole exam its event sits, and the flashcards themselves now move.

**A deck now spans your cluster exam, not just your event's roleplay.** Decks were
built outward from the topics tied to an event's roleplay, and they leaned on those
topics so heavily that some subjects on the same exam never made the cut. A deck now
covers 12 to 21 topic areas instead of 5 to 13, so the Area filter lists the subjects
you will actually be tested on. Strategic Management is the clearest case: it is on
all five cluster exams and it had 2 cards in the entire app. It now has 103, spread
across all 28 decks. Business Law went from 42 cards to 153, and Pricing from 89 to
123.

**Terms that were written but unreachable are now in a deck.** 247 finished terms sat
in the catalog where the deck builder could not draw them. 245 of those now appear in
at least one deck — 1,976 of 1,978 distinct terms in total.

Every deck is still 250 cards and every card is still medium or hard, and the balance
between the two is about what it was. The cards themselves are unchanged; which deck
each one lands in is what moved. A deck you were part-way through will look different.

**Flashcards flip, and a card you mark learned blows away.** Clicking a card turns it
over in 3D rather than swapping the text, so the term and the definition read as two
sides of one card. Marking a card learned lifts it, tumbles it and drifts it off the
screen while the next card is already there underneath, so nothing waits on the
animation. Each card catches the wind a little differently, and the same card always
flies the same way. Pressing Learned again only takes the mark off — a card flying
away to say you do not know it after all would read as the opposite of what it means.
Both animations respect the system Reduce Motion setting: the card swaps faces
instantly and nothing flies.

**Marking a card learned still is not saved.** It resets on a reload or a filter
change. The 20- and 50-card sessions exist partly for that reason, and putting the
mark on your account is planned work.

---

## 2026-08-27

### `chore(migration): sync the public mirror — 2026-08-27 23:43 EDT`

The largest single change to the study material since the mirror opened: every
vocabulary deck was rebuilt, and the vocab page grew the controls that make a
250-card deck usable. Around 130 changed files, most of them the decks
themselves.

**Every deck is 250 cards, on all 28 events.** They were 50, and three of them
were shorter still — Principles of Hospitality and Tourism at 38, Principles of
Business Management and Administration at 43, Principles of Marketing at 47.
All 28 are now 250, which is 7,000 cards in total. Each deck still opens with
vocabulary written for that event in particular, then works outward through the
instructional areas the event is judged on, then the rest of the cluster's exam.
Roughly 150 of the 250 are hard and 100 medium, and the split is a fair sample of
the terms behind each deck rather than whatever happened to be authored first —
so no event ends up with an easier deck than its neighbours by accident.

**Nothing easy is left in.** The term list was re-graded from scratch and every
word a competitor already knows — money, profit, teamwork, work ethic — was cut.
Terms that were cut are recorded so they cannot drift back in later. Every card
that survived carries a difficulty of medium or hard; there is no easy grade any
more, and the tool that checks a deck before it ships refuses the value outright.
Definitions are written to name the distinction a judge is listening for, and
each says where the term actually shows up on an exam or in a roleplay.

**The vocab page can now cut a deck down.** Study 20 cards, 50, or the whole
deck — a short session is a shuffled random draw from whatever you have filtered
to, with no repeats, and a new draw deals a different set. Filter by difficulty
(all, medium, hard) or by instructional area; a deck can span up to 13 areas, so
you can drill just Financial Analysis or just Customer Relations. There is also
an event-specific bucket for the cards written for your event rather than for a
general area — usually 25 to 33 per deck, and the most event-specific vocabulary
in it. Every card shows its difficulty badge on both sides, the event tiles say
how many hard cards a deck holds, and the filters live in the URL, so a deck link
carries the difficulty, area and session size along with the cluster and event.

**The vocabulary authoring tools ship too.** `backend/feat-vocab/` now carries
the quality gate that schema-checks a deck and enforces the difficulty bar, the
prompt builder and ingest step that author terms area by area, and the purge tool
that removes a term and records the removal. The vocabulary is our own writing,
so its whole source catalog is published alongside the decks it produces, and the
gate and the ingest step run here on that catalog. The prompt builder and the
purge tool do not: both read the performance-indicator library, which is one of
the withheld inputs described at the top of this file.

**Smaller things.** The dot-grid background is gone from behind the pages, and
the decorative sparkle marks are gone from the beta line and the footer wordmark.

## 2026-08-25

### `chore(migration): sync the public mirror — 2026-08-25 12:23 EDT`

Four changed files in the app, one document withdrawn, plus this journal. The
question bank's two kinds of material now sit behind two tabs instead of one
mixed list, and the words describing them agree with each other again.

**The pool is its own browse mode now.** The previous export gave the pool a page
for the first time, but it arrived stacked underneath the exam sets on a single
screen — 3,000 questions of numbered practice exams, and then 13,283 loose
questions below them, sharing one set of filters. Those are two different things
to want. Exam sets are for sitting a whole paper; the pool is for drilling a
cluster or a performance indicator until it sticks. They are now separate tabs,
each with the filters that make sense for it, so choosing one no longer means
scrolling past the other.

**The filter counts were counting the wrong thing.** On the pool tab, the number
beside each filter label was computed against the unfiltered bank rather than
against the other filters you had already set. Narrow to one cluster and the
level counts still reported totals from every cluster, so a label could promise
questions that selecting it would not produce. Each count is now computed over
everything except its own filter, which is what makes the numbers add up as you
narrow.

**Both shelves are named where the app introduces itself.** The help page and the
landing page each described the question bank as though the exam sets were all of
it. They now name both shelves and say how many questions are in each, so the
first thing you read about the bank matches what you find when you open it.

**A contributor-workflow document has been withdrawn.** `docs/reference.md`
indexed the tooling used to develop DECK in its private repository and described
processes that have no counterpart here. It was more likely to mislead a reader
of this repo than to help one. The user manual — the document about using the app
— is unaffected and still ships.

---

## 2026-08-24

### `chore(migration): sync the public mirror — 2026-08-24 21:26 EDT`

Three changed files in the app, plus this journal. The question bank now has a
page for the material it had been holding but not showing.

**Four-fifths of the question bank had no page.** The bank ships as numbered exam
sets — two per cluster, at three competition levels, 100 questions each, 3,000 in
total — plus a *pool* file per cluster and level holding everything written for
that cluster that a 100-question exam could not fit. The pool is **13,283 of the
bank's 16,283 questions**. The test generator has always drawn from it, so the
questions were reachable; there was simply no way to sit and read them.

There is now a second shelf under each cluster's exam sets. It carries the same
filters a reader needs at that size — instructional area, difficulty, and a search
across the question text, the performance indicator and the answer choices —
paged twenty at a time, with a button that draws a random twenty from whatever the
filter leaves and runs them as a quiz.

Two notes on how it behaves, both deliberate:

- **A pool is browsed, not read.** A set is 100 questions and renders whole; a pool
  is 800 to 1,029 and does not. The page renders a page at a time for that reason.
- **It needs no account**, like the rest of the question bank. An account is what
  records answers, not what unlocks the material.

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
