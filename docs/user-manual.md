# DECK — User Manual

*A plain-English guide to what DECK does, who it's for, and how to use every part of it.*

DECK is a study app for **DECA** competitors. It gives you three things DECA practice normally
makes you hunt for: a large bank of exam-style multiple-choice questions, vocabulary decks for
every competitive event, and daily roleplay case studies — plus a dashboard that watches what
you get wrong and tells you what to study next.

> DECK is **not affiliated with DECA Inc.** All practice material is AI-generated for study use.
> It is in **beta**: everyone testing accounts shares one database, and things change often.

---

## Contents

1. [The 60-second version](#1-the-60-second-version)
2. [Getting started](#2-getting-started)
3. [Guest vs. account — what you get](#3-guest-vs-account--what-you-get)
4. [The study dashboard (your home screen)](#4-the-study-dashboard-your-home-screen)
5. [Practice Tests](#5-practice-tests)
6. [The quiz screen (used everywhere)](#6-the-quiz-screen-used-everywhere)
7. [Question Bank](#7-question-bank)
8. [Vocab Terms](#8-vocab-terms)
9. [Roleplay Challenge](#9-roleplay-challenge)
10. [Progress](#10-progress)
11. [Review (your error log)](#11-review-your-error-log)
12. [Settings — themes, effects, and your data](#12-settings--themes-effects-and-your-data)
13. [Accounts, privacy, and safety](#13-accounts-privacy-and-safety)
14. [What's actually in the library](#14-whats-actually-in-the-library)
15. [How the material is made](#15-how-the-material-is-made)
16. [Known limits and what's still coming](#16-known-limits-and-whats-still-coming)
17. [Troubleshooting & FAQ](#17-troubleshooting--faq)
18. [Running DECK yourself (demo / dev setup)](#18-running-deck-yourself-demo--dev-setup)
19. [Demo script for a presentation](#19-demo-script-for-a-presentation)
20. [Glossary](#20-glossary)

---

## 1. The 60-second version

DECA competitors prepare for two things: a **cluster exam** (100 multiple-choice questions) and a
**roleplay** (a timed business scenario you solve in front of a judge). DECK covers both.

- **Practice Tests** — build a 10, 25, or 50-question test for your cluster and level, with a
  difficulty mix you choose. Instant, free to re-roll, composed from the question bank below.
- **Question Bank** — browse the ready-made exam sets by cluster, set, and level. Every question
  is labelled Easy, Medium, or Hard and tagged with the performance indicator it tests.
- **Vocab Terms** — flashcards for all 28 DECA events, 250 terms each, with a definition, a
  "why it matters" note and a difficulty. Filter by difficulty or topic area, or draw a 20- or
  50-card session out of the deck.
- **Roleplay Challenge** — full case studies across the 28 events, run against real DECA prep and
  presentation timers, ending in a self-scored debrief. The archive is thin so far (see §9).
- **Progress** — a readiness score, a mastery heatmap by topic, and a practice history.
- **Review** — every question you've missed, collected in one place until you get it right.
- **Dashboard** — reads all of the above and hands you an ordered to-do list for today.

Nothing in the app calls an AI model while you use it. All the material was generated ahead of
time and ships with the app, so everything loads instantly and works the same for everyone.

---

## 2. Getting started

### If someone is hosting DECK for you

1. Open the site. You land on the marketing home page with a carousel of the tools.
2. Browse the **Question Bank** right away — no sign-up needed.
3. When you want your practice remembered, press **Dashboard** (top right) and create an account.
4. Pick a **username and password**. There's no email step and no email is ever collected.
5. You confirm you're **13 or older** at sign-up.
6. You're in. Home now shows your dashboard instead of the landing page.

### First run after you sign up

The dashboard walks you through three steps once:

1. **Set your target** — which cluster you compete in, which level (District, Association, or
   ICDC), and optionally your competition date.
2. **Take the diagnostic** — a short mixed test (about 18 questions) so the app has something to
   reason about. You can skip it, and take it later from the dashboard header.
3. **Get your plan** — from then on, opening DECK shows today's ordered study plan.

> ⚠️ **There is no password reset.** Because accounts have no email attached, a forgotten
> password locks the account permanently. Write it down somewhere safe.

---

## 3. Guest vs. account — what you get

|  | Guest (no sign-up) | Account |
|---|---|---|
| Question Bank (browse + focus quizzes) | ✅ | ✅ |
| Changelog, Help, Terms, Privacy, Developers | ✅ | ✅ |
| Study dashboard (`/`) | — | ✅ |
| Practice Tests | — | ✅ |
| Vocab Terms | — | ✅ |
| Roleplay Challenge | — | ✅ |
| Progress + Review | — | ✅ |
| Practice remembered across sessions | — | ✅ |
| Syncs between your devices | — | ✅ |

**Guest mode records nothing.** Not on our servers, not on your device. That's deliberate —
it's the free, zero-commitment way to try the question bank — but it's also why Progress and
Review need an account: they have nothing to show without a saved history.

If you open a members-only page as a guest, you get a sign-up panel in place of the page rather
than a dead end (Progress and Review send you home, since they'd be empty anyway).

**Signing out** drops you back to guest mode. Signing back in restores everything.

---

## 4. The study dashboard (your home screen)

Signed in, `/` is your dashboard. It's rebuilt from scratch every time you load it — nothing
about the plan is stored, so finishing a task immediately reshapes what's left.

### The header

Your target cluster, level, and (if set) how many days until your competition, plus a **pacing
read**: whether your current readiness is ahead of, on, or behind where it should be with that
much time left. **Edit plan** changes the target or the date. Changing your competition date
does not disturb today's work.

### Today's Plan

An ordered list of tasks, roughly in the sequence a good study session runs:

| Task | What it is |
|---|---|
| **Warm-up** | A quick 10-question mixed set to get going. |
| **Drill: \<PI\>** | Your weakest performance indicator. Difficulty tilts to how well you're doing on it. |
| **Learn: \<PI\>** | A performance indicator you've never attempted. Draws only from questions you haven't seen. |
| **Fix your misses** | Re-answers the questions you got wrong, until you get them right. |
| **Challenge set** | A hard-heavy 10-question mix to push your ceiling. |
| **Milestone test** | A full 50-question exam-real test as a check-in. |

Three behaviours worth knowing:

- **Today's recommendations are frozen once per day.** The first time the plan is built for a
  given day, that set of recommended tasks is locked in. Your stats will shift as you practise,
  but new recommended cards won't keep appearing mid-session and moving the goalposts.
- **A task's progress counts only its own work.** The bar on "Drill: Positioning" fills from
  questions you answered by pressing *that card's* Start — not from a matching question you
  happened to answer somewhere else.
- **Start resumes, it doesn't re-roll.** A task's questions are saved the first time you launch
  it, so pressing Start again returns to the same set with your earlier answers restored.

You can **dismiss** any recommended task (the ×) and **Add a task** of any type yourself. The add
menu greys out options that don't apply right now and tells you why on hover — e.g. "No misses to
fix — you're all caught up."

### The 3-day calendar

A rolling forecast that runs the same planning logic forward and shows what tomorrow and the day
after would look like. Future days are **read-only previews** — you can't start tomorrow's work
early, and the app enforces that at the data layer, not just by hiding the button.

### Readiness graph and mastery heatmap

The same two modules that live on the Progress page, embedded here for your target cluster. The
heatmap's **Practice this** button opens a 10-question drill on any topic you tap.

### Quick actions

Escape hatches at the bottom: a 10-question focus quiz, the full Test Generator, your Review
errors, and the full Progress page.

---

## 5. Practice Tests

`Practice Tests` in the nav (the Test Generator). You pick five things, press Start, and the app
composes a test out of the real question bank instantly.

| Control | Options | Notes |
|---|---|---|
| **Cluster** | Business Admin Core, Marketing, Finance, Hospitality & Tourism, Entrepreneurship | |
| **Level** | District, Association, ICDC | |
| **Questions** | 10 (quick), 25 (short), 50 (half exam) | |
| **Draw from** | Whole bank, or Pool only | "Pool only" excludes anything that appears in a numbered exam set, so you can drill purely fresh material. |
| **Difficulty mix** | Exam-real 20/60/20, Balanced 25/50/25, Challenge 10/40/50 | Easy / Medium / Hard percentages. |

**Challenge is 25-question only.** A 50-question Challenge would need a deeper shelf of hard
questions than exists for every cluster, so rather than quietly serving you mediums and calling
them hard, the option is disabled at 50.

**Honest shelf warnings.** If you pick a hard-heavy mix for a cluster and level whose hard
questions are thin, a note appears telling you exactly how many hard questions exist there and
warning that the draw will lean medium. The app would rather admit that than fake it. The count
follows your **Draw from** choice — on "Pool only" it measures the pool alone and says so, since
the exam sets' hard questions aren't in that draw.

If a cluster and level combination has nothing to draw from, the Start button is disabled and the
page says which choice to change.

---

## 6. The quiz screen (used everywhere)

Every practice surface — the Test Generator, focus quizzes from the bank, dashboard tasks, and
"Practice this" drills — opens the same quiz screen. Learn it once.

**Main panel.** One question at a time: the stem, four lettered choices, and a difficulty badge.
Pick a choice and the answer is revealed immediately along with an explanation and the
performance indicator it tests.

**Side navigator.** A grid of every question in the set. Jump anywhere at any time. Once you
start answering it doubles as a score map:

- green = correct
- red = wrong
- grey = seen but unanswered (a question you skipped past stays here — skipping is
  navigation, so it locks nothing and records nothing)
- a coloured dot on each = easy / medium / hard

You can move the navigator to the left or right side of the screen.

**Keyboard.** `Enter` moves to the next question (and finishes on the last one). **`Esc` does
*not* exit** — the only way out is the `Exit quiz` button, and Tab focus is trapped inside the
quiz, so a stray keypress can't drop you out mid-question.

**Buttons.** `← Prev`, `Skip` (moves on without locking the question, so you can come back to it),
`Next →` / `Finish`, and `Exit quiz`.

**The end screen** shows your score, your percentage, how many of the set you answered, and a chip
per difficulty (`Easy 7/8 · Medium 9/14 · Hard 1/3`) so you can see *where* you lost points, not
just how many. From there:

- **New set** — reshuffles a fresh draw with the same settings (composed tests only; a fixed set
  like a bank set or a drill has nothing to re-roll). It counts as a new session.
- **Review answers** — walks back through the set with everything revealed. Anything you fill in
  there is still part of the *same* session, so Progress records one row for the whole run.
- **Exit**.

Every graded answer is logged (when you're signed in), which is what feeds Progress, Review, and
tomorrow's plan.

---

## 7. Question Bank

The free, no-account surface — the committed **exam sets**, browsable. This route serves the
numbered sets only: `loadSet` fetches one `cluster × level × set` file, and the much larger
per-cluster `-pool` files behind them are reached only by the compose paths (Practice Tests,
dashboard drills, Review), which need an account.

You drill down through four steps, with a breadcrumb you can click back through at any point:

**All clusters → a cluster → a set → a level → the questions.**

- **Cluster tiles** show how many sets exist and a summary of the instructional areas covered.
- **Set tiles** are numbered exam sets, each available at District, Association, and ICDC.
- **Level tiles** show the question count and the area breakdown for that exact test.
- **The study view** lists all 100 questions as cards, each with its choices and an
  Easy/Medium/Hard badge. The answer stays hidden behind a **reveal answer & explanation** button,
  so browsing doesn't spoil the question — the reveal also shows the performance indicator it
  tests.

**Start focus quiz →** at the top of any set turns that exact 100-question set into the quiz
screen described above — one at a time, no reveal until you answer, with the side navigator.
This is the same experience as a real cluster exam, minus the clock.

---

## 8. Vocab Terms

Flashcards for terminology, organised **cluster → event → deck**.

Every one of DECA's 28 competitive events has a **250-term deck** — 7,000 cards in total. Every
card is **medium or hard**; there is no easy tier, because a term you already know is not worth a
card.

Each card has:

- the **term** on the front;
- click (or **Flip**) to reveal the **definition** and a **"Why it matters"** note explaining how
  the term actually shows up in competition;
- a **difficulty badge** — Medium or Hard — on both faces;
- a **topic tag** for the instructional area it belongs to. Most cards carry exactly one. Cards
  written specifically for your event carry none and are labelled **Event-specific** instead —
  they are the most event-particular vocabulary in the deck, not cards that were missed.

Controls: **Prev / Next**, **Flip**, and **Mark learned**. A progress bar tracks your position in
the deck and a tape label counts how many you've marked learned.

**Three ways to cut the deck down**, because 250 cards in a row is a lot:

- **Difficulty** — All, Medium or Hard.
- **Area** — any single topic area in the deck, or Event-specific. A deck spans 12 to 21 areas
  depending on the event, covering the whole cluster exam rather than only the topics tied to
  your event's roleplay.
- **Session** — All, or a random draw of **20** or **50**. A sized draw never repeats a card, and
  **New draw** re-deals it.

The two filters count against each other, so each number tells you what you would actually get if
you clicked it. All three live in the address bar, so a filtered deck is a link you can share or
bookmark.

**Marking a card learned is not saved yet.** It resets on a reload or a filter change — the
20-card session exists partly for that reason. Getting it onto your account is planned work.

> Vocab is a reading tool, not a graded one — marking a card learned is for your own tracking in
> that sitting and doesn't feed the Progress page.

---

## 9. Roleplay Challenge

The roleplay half of DECA: a business scenario, a short prep window, and a presentation to a
judge. DECK gives you a fresh one to run whenever the archive has one for your event.

### The day board

One day's drop, showing all 28 events as cards. Events with a scenario that day are live; the rest
are greyed out. Step **prev / next** between days, or **browse the archive** by month.

**The day is one global day, on Eastern midnight — not your local midnight.** Everyone in the
country sees the same scenarios at the same instant, so two teammates in different time zones
can't end up on different drops. If you're on the west coast, the day flips at 9pm your time. The
board says so on screen.

### Running a scenario

Opening a card steps you through four stages:

| Stage | What happens |
|---|---|
| **Brief** | Your event, cluster, the performance indicators you'll be judged on, and your prep/present times. |
| **Prep** | The situation and any exhibit, against a live countdown (10 minutes for individual events, 30 for team events). |
| **Present** | A second countdown (10 minutes individual, 15 team). The judge's role is revealed and judge questions appear one at a time. |
| **Debrief** | Everything unlocks for re-reading, and you self-score each performance indicator. |

Some things are deliberate:

- **Judge questions genuinely don't exist on the page during Prep** — they're not just hidden with
  styling, because that can be read out of the browser or spoken by a screen reader. You can't
  peek even if you want to.
- **Timings come from the real event definitions**, not from the scenario text. Some scenarios
  carry boilerplate instructions that say there's no time for judge questions and then ask three;
  that text is shown to you verbatim because it's a known defect in the source material, not
  something to quietly rewrite.
- **Self-scores use DECA's own four-level judging scale**, so scoring yourself produces the same
  artefact a judge would produce.
- **A run is not saved.** Refreshing loses it, closing mid-timer asks you to confirm first, and
  the debrief tells you plainly that your self-scores are temporary. Roleplays also never enter
  your Progress score — a roleplay isn't a graded question, and letting a self-score move your
  readiness number would make that number a lie.
- **No claim is made that a scenario is "ICDC difficulty."** There's no referee to verify that.
  The strongest honest statement is "harder than the district-level material DECA publishes," and
  that's the only one you'll see.

### The archive is thin right now

Today it holds **7 scenarios across 3 days** — real, generated, committed, but sparse. That's why
most cards on the board are greyed. The board was built for exactly this state; it fills in when
a full generation batch is run (see [§16](#16-known-limits-and-whats-still-coming)).

---

## 10. Progress

Everything derived from your practice log. Filter the whole page by **cluster × level** (or leave
both on "all").

**Readiness** — the headline percentage. It's a blend of how well you're doing across the
instructional areas of that cluster, weighted the way DECA's own exam blueprint weights them, so
being strong in an area that's worth 8 questions counts more than being strong in one worth 2.
With no data it says so rather than showing a fake 0%.

**Overall accuracy** — plain correct-out-of-answered.

**Readiness trajectory** — a full-width graph of that readiness number over time, one point per
finished practice session (collapsed to one point per day once you have enough history to make the
line unreadable otherwise).

**Mastery by area** — a heatmap. Each row is an instructional area; open it to see the individual
performance indicators underneath, coloured by how you're doing. Every cell has a **Practice this**
button that opens a 10-question drill on exactly that topic. If the bank has nothing left on that
exact indicator — a topic you practiced before that part of the bank was rewritten — the drill
widens to the surrounding instructional area and says so at the top of the quiz: *Closest available
— practicing the whole area.* The same note now appears on the dashboard, which used to widen the
draw silently.

**Practice history** — every session you've run, tagged by where it came from: Focus, Test-gen,
Review, Diagnostic, or Browse.

All of it is recomputed from the log on every load. Nothing here is a stored score that can drift
out of sync with reality.

---

## 11. Review (your error log)

Every question you've answered wrong, in one place, until you fix it. (Skipped questions
aren't here — skipping records nothing, so a question you moved past is simply unanswered.)

- **Group by performance indicator** to see which topic your errors cluster in, or **by mistake
  pattern** to see *how* you're going wrong.
- Each card shows the question and **the wrong answer you picked — with the correct answer
  hidden**, so you can actually re-attempt it instead of just reading the key.
- **Review now** on any card opens a short session on that question.
- **Answer it correctly and it drops off the list.** Get it wrong again and it stays.

Filter by cluster and level the same way as Progress. The dashboard's "Fix your misses" task is
the same engine, launched from your plan instead.

---

## 12. Settings — themes, effects, and your data

The **gear icon** in the top bar opens a two-tab settings dialog.

### Themes

Six looks, each with its own palette:

| Theme | Season | Animated overlay |
|---|---|---|
| **Classic** | Year-round | — |
| **Golden Hour** | Year-round | — |
| **Terminal** | Year-round | — |
| **First Bloom** | Spring | Fluttering petals |
| **Midsummer** | Summer | Dandelion seeds drifting up, sunset sky |
| **First Snow** | Winter | Drifting flakes |

Seasonal themes carry an **"in season"** badge when their window is current. An **Animated
effects** switch at the top of the tab turns every overlay off. Motion also respects your
operating system's reduce-motion setting automatically — if you have that on, nothing animates
regardless of the switch.

### Data

- **Export my data (JSON)** — everything DECK holds about you, in a file you keep.
- **Reset progress** — erases your practice history. Two-step confirm. For a signed-in user it
  clears both your device and your account, and it also clears **today's plan** (its task cards,
  their saved question sets, and anything you added today), so the dashboard builds a fresh plan.
  Your target event, level and competition date survive a reset — that's setup, not progress.
- **Delete account** — permanently removes the account and all its data everywhere. You type your
  username to confirm.

---

## 13. Accounts, privacy, and safety

**Accounts are username + password.** No email, no confirmation step, no email address stored.
The trade-off is that **there is no password reset** — a forgotten password locks the account.

**You must be 13 or older** to create an account. Under 13, use guest mode, which stores nothing
about you anywhere.

**As a guest, nothing is recorded.** Not on the server, not in your browser.

**With an account, we store** your username, display name and avatar emoji; your practice log —
each answered question's topic, the choice you made, whether it was right, and the timing — plus a
row per practice session; your **study plan** — target cluster and level, the competition date you
enter, and today's plan state (tasks added, tasks dismissed, and how far into each one you are);
and a **sign-in token** that enforces one account to one device at a time. We do **not** collect
your email, real name, school, or location.

**A copy also lives on your device.** Once you're signed in, the practice log and study plan are
cached in your browser (IndexedDB plus a few `deck-*` keys) so the app stays fast and keeps
working offline, syncing back when the connection returns. **Reset progress** clears the practice
log and today's plan on both sides but keeps your target event, level and date (see §12);
**Delete account** clears everything, device copy included.

**Where it lives.** A hosted database (Supabase). During beta that's one shared project for
everyone testing. Database security rules mean only you, signed in, can read or write your own
rows — other testers can't see your history — but the people running the beta can access what's
stored in order to fix bugs, and data may be reset as things change. Don't put anything personal
in your username, and don't treat beta account data as permanent.

**Leaderboards don't exist.** If they ever arrive they'll be off by default and opt-in, and would
show standings only — never your individual answers.

**The practice material is AI-generated, so some of it is wrong.** Every question, roleplay and
vocab term was written by a model, not by DECA and not by a teacher. Drill with it and use it to
find weak spots — but don't cite it, and check anything that matters against DECA's own published
material. DECK is not affiliated with or endorsed by DECA Inc., and nothing here is official DECA
preparation.

The full, plain-language versions are on the **Terms** and **Privacy** pages in the app, both
linked from the footer of every page. Terms covers who may use DECK, what an account is and how
either side can close one, the accuracy disclaimer above, and the fact that a free beta can change
or go away; Privacy covers everything about data. They deliberately don't repeat each other.

---

## 14. What's actually in the library

### Questions — 10,226 total

| Cluster | District | Association | ICDC | Total |
|---|---|---|---|---|
| Finance | 1,229 | 1,142 | 1,157 | **3,528** |
| Business Admin Core | 1,052 | 1,038 | 1,008 | **3,098** |
| Marketing | 400 | 400 | 400 | **1,200** |
| Hospitality & Tourism | 400 | 400 | 400 | **1,200** |
| Entrepreneurship | 400 | 400 | 400 | **1,200** |

By difficulty: **5,112 easy · 4,294 medium · 820 hard.**

Structurally that's **30 numbered 100-question exam sets** (a full mock exam each) plus **15
pools** of additional questions that aren't in any set — which is what the Test Generator's
"Pool only" option draws from.

Finance and Business Admin Core are deeper than the rest because they've been through a review
pass that fills in every performance indicator until there's enough behind each one to actually
drill it. The other three clusters are queued for the same treatment.

### Vocab — 7,000 cards

**28 events × 250 terms**, across all five clusters (Marketing 11 events, Hospitality & Tourism 6,
Finance 5, Business Admin Core 3, Entrepreneurship 3). Every card is medium or hard.

Decks overlap on purpose. Events in the same cluster sit the same cluster-wide exam — BLTDM, HRM
and PBM all take Business Administration Core — so the 7,000 cards are drawn from a smaller pool
of distinct terms, and studying your own event's deck is still studying the right material.

That pool holds **1,978 distinct terms, and 1,976 of them appear in at least one deck.** A deck
still leans on your own event's topics; it just no longer stops there, so an area on your cluster
exam that no event's roleplay names — Strategic Management is the clearest one — is in every deck
rather than almost none.

### Roleplays — 7 scenarios

Across 3 days, covering a handful of the 28 events. This is the one thin part of the library.

---

## 15. How the material is made

Worth knowing, because it explains why DECK behaves the way it does.

**Nothing is generated while you use the app.** There is no AI model running behind any button.
Every question, term, and scenario was written ahead of time by an offline generator, checked,
and committed into the app. That's why everything is instant, costs nothing to run, works with
no account, and gives every user identical material.

**Questions** are generated from real past DECA exams used as examples, against DECA's own
performance-indicator library, allocated across instructional areas the way a real cluster exam
allocates them. Each generated question is validated, normalised, and tagged with its answer,
explanation, performance indicator, and difficulty.

**Hard questions get extra scrutiny.** A question isn't "hard" because the generator said so —
that claim is checked independently before it's allowed into the bank, because an author marking
its own work is not evidence.

**Roleplays** are generated in two passes (a single pass reliably produces scenarios about a third
too short) and then run through a deterministic quality gate. The gate is explicit about what it
can and can't verify: it counts things like whether an exhibit with real numbers exists and
whether judge questions are properly formed, it records but does not enforce some self-reported
claims, and it ships the rest **unverified rather than pretending otherwise**. That honesty is why
no screen in the app claims a scenario is a verified difficulty level.

---

## 16. Known limits and what's still coming

**Be upfront about these in any demo.**

| Limit | Detail |
|---|---|
| Everything is AI-generated | It's modelled closely on real DECA material but it isn't official, and it isn't perfect. |
| No password reset | No email on file. A forgotten password locks the account. |
| Beta database is shared | All testers' accounts live in one project. Data may be reset. |
| The roleplay archive is thin | 7 scenarios, 3 days. Fills in when a full batch is generated (a 7-day, 28-event batch takes roughly 15–16 hours of generation). |
| Marketing / Hospitality / Entrepreneurship banks are shallower | 1,200 each vs. finance's 3,528. The review pass that deepened finance and business admin core is rolling out to them next. |
| No leaderboards | Deferred. |
| Roleplay runs aren't saved | Refreshing loses the run; self-scores are temporary and say so. |
| Roleplay results don't affect readiness | A self-score is not a graded answer, so it never moves your Progress number. |
| 50-question Challenge mix | Disabled — the hard shelf isn't deep enough to fill it honestly. |

**In flight:** deepening the remaining three question banks; generating the first real roleplay
batch so the daily board fills out; saving roleplay run state so a refresh doesn't lose it.

---

## 17. Troubleshooting & FAQ

**"Progress and Review are empty."**
You're signed out. Logging is account-only by design — guest mode records nothing anywhere. Sign
in and your history starts from that point.

**"I forgot my password."**
There's no reset, because there's no email on file. The account is locked. Make a new one, and
this time write the password down.

**"The Start button on Practice Tests is greyed out."**
That cluster-and-level combination has nothing to draw from — usually because you have "Pool only"
selected for a slice with no pool questions. Switch back to "Whole bank" or pick another slice.
The page tells you which.

**"Challenge is greyed out."**
You have 50 questions selected — that's the only count Challenge is blocked at, because no
50-question Challenge hard shelf was ever authored. Drop to 25 or 10 and it comes back.

**"I picked a hard mix and got mostly medium questions."**
Read the heads-up note under the mix selector — it tells you exactly how many hard questions exist
for that cluster and level. When the shelf is short, the draw leans medium rather than faking it.

**"My roleplay board is mostly greyed out."**
That's real. The archive currently holds 7 scenarios across 3 days.

**"The roleplay day changed at 9pm."**
Expected. The challenge day flips at **midnight Eastern**, globally, so everyone sees the same
drop at the same moment. On the west coast that's 9pm local.

**"I refreshed during a roleplay and lost everything."**
Roleplay run state is intentionally not saved yet. Closing mid-timer will warn you first.

**"A question I got wrong is still in Review."**
It clears when you answer *that specific question* correctly. Use **Review now** on the card.

**"Two tasks on my dashboard cover the same topic."**
Shouldn't happen — added tasks pick a topic that isn't already targeted today. If it does, dismiss
one; it's worth reporting.

**"I answered questions but a plan task's progress bar didn't move."**
A task counts only the sessions launched from its own Start button. Answering matching questions
elsewhere is still logged for Progress and Review, but doesn't fill that card.

**"Animations are distracting."**
Settings → Themes → turn off **Animated effects**. Or pick a year-round theme. Or enable
reduce-motion in your OS, which the app honours automatically.

**"Nothing loaded / the page is blank."**
Hard-refresh. If a members-only page won't render, check whether you're signed in — guests get a
sign-up panel instead of the page.

---

## 18. Running DECK yourself (demo / dev setup)

The web app needs **Node.js 20+** and nothing else — no API keys, no backend, no database.

```bash
cd "frontend"        # the folder path contains a space — keep the quotes
npm install          # first time only
npm run dev
```

Open **http://localhost:3000**. Stop with `Ctrl+C`.

Other scripts: `npm run build` (production build), `npm run start` (serve it), `npm run lint`.

**With zero configuration the app runs account-less** — fully local, no network, no auth UI. Every
route is reachable and the Question Bank, Practice Tests, Vocab, and Roleplay all work. But
because logging is account-only, **nothing is recorded**: `/` always shows the marketing landing
(never the dashboard), and Progress and Review render empty. Zero-config is fine for showing the
practice material; it cannot show the analytics half of the app.

**To get the dashboard, Progress, and Review**, copy `frontend/.env.local.example` to
`frontend/.env.local` and fill in the two public Supabase values documented in the project README,
then sign in. A third, server-only key is needed *only* for the "delete account" flow and is never
committed to the repo — ask the project owner. Restart the dev server after editing the file.

**The generators** (optional — only if you're working on the material itself) are Python CLIs run
from the repo root:

```bash
source venv/bin/activate
python backend/test-gen-model/src/generators/generate_test.py
python backend/roleplay-gen-model/src/generators/generate_roleplay.py
```

They prompt for cluster, level, and count, and write timestamped files into each model's `output/`
folder. They drive a local model, so they cost nothing to run but are slow — a full roleplay day is
around 2.5 hours.

---

## 19. Demo script for a presentation

A tested ~8-minute path that shows the whole product and lands the differentiators.

**1 · Open cold, signed out (30s).**
Land on the carousel home. Press a card — it centres against a blurred belt of the others. Sets
the tone: this is a study tool that doesn't look like a worksheet.

**2 · Question Bank as a guest (60s).**
Nav → Question Bank. Drill cluster → set → level. Scroll the 100 questions; point out the
difficulty badge and the performance indicator on each card. **Say the number: 10,226 questions.**

**3 · Focus quiz (90s).**
Press *Start focus quiz*. Answer two right and one deliberately wrong. Show the instant
explanation, then the side navigator filling in green/red. Jump to question 40 to show it's a
navigator, not just a progress bar. Finish → land on the score screen and point at the
**per-difficulty chips** — "it doesn't just tell you 7/10, it tells you that you're fine on easy
and losing all the hard ones."

**4 · Sign in (30s).**
Switch to a pre-made account so the dashboard has real history. *(Have this account ready
beforehand — a fresh account shows an empty dashboard.)*

**5 · The dashboard (2 min).**
This is the centrepiece. Walk the header (target, days to competition, pacing), then Today's Plan
top to bottom — "warm up, drill your weakest topic, learn one you've never touched, fix what you
got wrong, then push your ceiling." Note that it's **derived, not stored**: finish a task and the
plan reshapes. Show the 3-day calendar and that future days are previews only.

**6 · Progress + Review (90s).**
Progress → readiness graph, then open a heatmap row and press **Practice this** on a weak topic —
this is the loop closing. Then Review: "here is every question I've ever missed, showing my wrong
answer with the key hidden, and it disappears when I finally get it right."

**7 · Roleplay (90s).**
Open a live card. Brief → point at the PIs and timers. Prep → start the countdown, note the judge
questions **are not on the page yet**. Present → they appear. Debrief → self-score on DECA's own
scale. Say plainly that the archive is still 7 scenarios and that runs aren't saved yet.

**8 · Themes (20s).**
Gear → Themes → switch to a seasonal one for the animated overlay, then show the off switch.
Good, cheap closer.

**Three lines worth saying out loud:**

- *"Nothing here calls an AI while you use it — all 10,226 questions were generated and checked
  offline, so it's instant, it's free to run, and everyone gets identical material."*
- *"When the app doesn't have enough hard questions for what you asked for, it tells you instead of
  pretending. Same with roleplay difficulty — there's no referee, so we don't claim one."*
- *"Guest mode stores nothing at all. Logging only starts when you choose an account."*

---

## 20. Glossary

**Cluster** — the exam family you compete in. DECK covers five: Business Administration Core,
Marketing, Finance, Hospitality & Tourism, Entrepreneurship.

**Level** — how far you've advanced. **District** → **Association** (state) → **ICDC**
(International Career Development Conference). Higher levels are harder.

**Event** — your specific competition (e.g. HRM, Human Resources Management Series). 28 of them.
They come in three formats: *Series* (individual, 5 PIs), *Principles* (individual, 3–4 PIs, for
first-year competitors), and *Team Decision Making* (two people, 7 PIs, longer prep).

**Performance Indicator (PI)** — the specific skill a question or roleplay is testing, e.g.
"Explain the nature of positive customer relations." DECA publishes these; DECK tags every
question with the one it tests, which is what makes topic-level mastery tracking possible.

**Instructional Area** — the topic group a PI belongs to (Promotion, Financial Analysis,
Emotional Intelligence, …). The heatmap's rows.

**Cluster exam** — the 100-question multiple-choice test. What Practice Tests and the Question
Bank prepare you for.

**Roleplay** — the judged half of DECA: a scenario, prep time, a presentation to a judge, and
judge questions. Individual events get 10 minutes prep and 10 to present; team events get 30 and
15.

**Exhibit** — supporting material inside a roleplay (a table of numbers, a figure) that you're
expected to reason from.

**Readiness** — DECK's headline score: how well you're doing across a cluster's instructional
areas, weighted the way the real exam weights them.

**Mastery** — the same idea at a single-topic level; what the heatmap colours.

**Set** — one of the 30 numbered, 100-question mock exams in the bank.

**Pool** — additional bank questions that don't belong to any numbered set. Drillable on their own
via the Test Generator's "Pool only" option.

**Diagnostic** — the ~18-question test the dashboard offers on first run so it has something to
plan from.

---

*DECK is a student-built practice tool in active development, not affiliated with DECA Inc.
Practice material is AI-generated. If something is broken or unclear — or you want your data
removed and can't do it yourself — reach out.*
