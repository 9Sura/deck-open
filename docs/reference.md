# Reference

Three parts: the copy-paste prompts we run against the playbooks in `docs/`, a rundown of the
Claude Code plugins installed on this machine, and how graphify is wired into this repo.

---

# Part 1 — Copy-paste prompts

Paste verbatim. Each names its playbook and where to stop; the playbooks hold the detail.

---

## 1. Audit the repo and file the issues

```
Audit this repo for bugs and report back to me.

Follow docs/issue-finding-and-debugging.md — read it first, do the full pass (§1 code scan,
§2 visual, §3 report), and honour its false positives and severity rubric.

Verify every finding before reporting it: concrete failure scenario, inputs → wrong result,
not a theory. Fix nothing. File nothing yet.

Report the ranked list in chat, then STOP.

When I say go, file the ones I name to 9Sura/DECK-APP per §4 — one issue per bug, dry run
first, then give me the numbers and URLs.
```

---

## 2. Work an issue

```
Work on issue #N.

Follow docs/issue-branching-and-prs.md, including its stop points.

Phase 1 only: read the issue, confirm it against the code, and give me a plain-language
summary with your recommendation. Then STOP.

When I say go, do phases 2–4.
```

---

# Part 2 — Installed Claude Code plugins

These are installed at **user scope** (`~/.claude/plugins/`), so they apply to every project on this
machine, not just DECK-APP — nothing about them is committed to this repo. Two marketplaces are
registered:

| Marketplace | Source |
|---|---|
| `claude-plugins-official` | `github:anthropics/claude-plugins-official` |
| `caveman` | `github:JuliusBrussee/caveman` |

Manage them with `/plugin` (browse, install, enable/disable, update). The install manifest is
`~/.claude/plugins/installed_plugins.json`; each plugin's files live under
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.

Six plugins are installed, listed newest-install-last.

---

## 1. `caveman@caveman`

**What it is.** An output-compression mode. It rewrites how Claude *talks* — drops articles, filler,
pleasantries, hedging and tool-call narration while keeping technical substance, numbers, code
blocks and error strings exact. The author measures ~65% fewer output tokens. It also ships three
compressed subagents and a token-accounting command.

**How it turns on.** Automatically. A `SessionStart` hook injects the ruleset at the top of every
session (default level `full`), and a `UserPromptSubmit` hook tracks the current level. You do not
invoke anything to get it — you invoke something to *change* or *stop* it.

**Levels.** `lite` · `full` (default) · `ultra` · `wenyan-lite` · `wenyan-full` · `wenyan-ultra` ·
`off`. The `wenyan-*` levels answer in classical Chinese, which is shorter still. Level persists for
the session.

**Commands.**

| Command | Does |
|---|---|
| `/caveman [level]` | Switch intensity. No argument = `full`. |
| `/caveman-help` | One-shot reference card of every mode and command. |
| `/caveman-stats [--share\|--all\|--since 7d]` | Real session token usage, lifetime savings, USD. `--share` prints a one-liner. |
| `/caveman-commit` | Conventional-Commits message for the staged diff. Subject ≤50 chars, imperative, body only when the "why" isn't obvious. |
| `/caveman-review` | One line per finding: `L<line>: <severity> <problem>. <fix>.` Severities: bug, risk, nit, q. Says `LGTM` and stops when clean. |
| `/caveman-compress <path>` | Rewrites a memory/prose file (CLAUDE.md, todos) in place, compressed. Keeps a readable backup at `<file>.original.md`. |
| `/caveman-init [--dry-run\|--force] [--only <agent>]` | Writes always-on caveman rule files into the *current repo* for other IDE agents (Cursor, Windsurf, Cline, Copilot, `AGENTS.md`). |

**Subagents (`cavecrew`).** Delegate to these instead of working inline when you want the
tool-result that comes back into the main thread to be ~60% smaller:

- `cavecrew-investigator` — read-only locator. "Where is X defined", "what calls Y", "map this
  directory". Returns a `file:line` table; refuses to propose fixes.
- `cavecrew-builder` — surgical 1–2 file edit (typo, single-function rewrite, mechanical rename).
  Hard-refuses 3+ file scope; not for new features or cross-file refactors.
- `cavecrew-reviewer` — diff/branch/file review, one severity-tagged line per finding.

Run `/cavecrew` for the decision guide on which to spawn.

**Two cautions for this repo.**

- `/caveman-compress` **overwrites the file you point it at.** Our root `CLAUDE.md` is unusually
  long and load-bearing; if you compress it, review the diff against `CLAUDE.original.md` before
  committing, and remember that everything in `CLAUDE.md` is a project instruction others read too.
- `/caveman-init` **writes new files into the working tree.** We already keep a real
  `frontend/AGENTS.md`. Run it with `--dry-run` first and check what it intends to touch.

**Note on style boundaries.** Caveman applies to chat output only. Anything persisted outside the
chat — code, comments, commit messages, PR bodies, docs like this file, issue text — is written in
normal prose. `/caveman-commit` is the deliberate exception.

**Turn it off:** `/caveman off`, or say "stop caveman" / "normal mode".

---

## 2. `claude-md-management@claude-plugins-official` (v1.0.0)

**What it is.** Two tools for keeping `CLAUDE.md` files honest — one that audits, one that captures
what a session taught you.

**Usage.**

- `/revise-claude-md` — at the end of a working session, updates `CLAUDE.md` with the learnings from
  that session. Run it when you've just discovered something non-obvious that the next agent would
  otherwise re-derive.
- The **`claude-md-improver`** skill — invoke by asking ("audit our CLAUDE.md", "check CLAUDE.md
  quality"). It finds every `CLAUDE.md` in the repo, scores them against a template, prints a
  quality report, then makes targeted edits.

**Fit here.** This repo has three (`CLAUDE.md`, `frontend/CLAUDE.md`, plus `frontend/AGENTS.md`
imported by the frontend one) and the root file is very large. Treat both tools as *proposers* —
read the diff before committing, because our root file deliberately carries findings and rules that
a generic quality rubric may read as bloat and try to trim.

---

## 3. `claude-code-setup@claude-plugins-official` (v1.0.0)

**What it is.** A single skill, `claude-automation-recommender`, that reads a codebase and
recommends Claude Code automations tailored to it — hooks, subagents, skills, plugins, MCP servers.

**Usage.** Ask for it in plain language: "recommend Claude Code automations for this repo", "how
should I set Claude Code up here", "what hooks would help". No slash command.

**When it's worth running.** Onboarding a new repo, or when you notice yourself repeating the same
manual step (a sync command, a lint pass, a check before commit) enough times that a hook should be
doing it. Output is a recommendation list, not applied config — pair it with the `update-config`
skill to actually write `settings.json`.

---

## 4. `security-guidance@claude-plugins-official` (v2.0.6)

**What it is.** Automatic security review of Claude-generated code, in three independent layers:

1. **Pattern warnings** — regex checks that fire instantly on `Edit`/`Write` for ~25 known-dangerous
   patterns (`yaml.load`, `pickle.load` on untrusted data, raw `innerHTML`, hardcoded secrets, …).
2. **LLM diff review** — when Claude finishes a turn, the diff goes to a fast model call and
   high-severity findings are fed back so they get fixed before you see the response.
3. **Agentic commit review** — on `git commit` / `git push` (and Graphite's `gt create|modify|submit`),
   an SDK-driven reviewer reads related files to trace data flow across the codebase, catching
   multi-file issues pattern matching can't see: IDOR, auth bypass, cross-file SSRF.

Between them they cover injection, XSS, SSRF, hardcoded secrets, IDOR, auth bypass, unsafe
deserialization, and path traversal, among others.

**How it runs.** Entirely through hooks — nothing to invoke. Layers 2 and 3 run in the background and
re-wake the session with findings. Requires Python 3.8+ on `PATH` (this machine has 3.14.2) and a
working API path; layers 2–3 cost API tokens on every turn and every commit.

**Configuration** — all environment variables, none required:

| Variable | Default | Effect |
|---|---|---|
| `SECURITY_GUIDANCE_DISABLE=1` | unset | Kill switch for the whole plugin |
| `ENABLE_PATTERN_RULES=0` | on | Disable layer 1 |
| `ENABLE_CODE_SECURITY_REVIEW=0` | on | Disable all LLM review (layers 2 + 3) |
| `ENABLE_STOP_REVIEW=0` | on | Disable only the end-of-turn diff review, keep commit/push review |
| `ENABLE_COMMIT_REVIEW=0` | on | Disable layer 3 |
| `SECURITY_REVIEW_MODEL` | `claude-opus-4-7` | Model for layer 2 |
| `SG_AGENTIC_MODEL` | same as above | Model for layer 3 |
| `SG_DUAL_OR=on` | off | Higher recall: two parallel review calls, unioned findings, ~2× cost |

`ENABLE_STOP_REVIEW=0` is the one worth knowing about here — it exists for shared-worktree setups
where another agent can move `HEAD` between a worker's turns, which is exactly the pattern our
issue workflow uses (`docs/issue-branching-and-prs.md` requires a git worktree per issue).

**Org policy files.** Drop a `claude-security-guidance.md` in `~/.claude/`, `<project>/.claude/`, or
`<project>/.claude/claude-security-guidance.local.md` to add your own rules. All three are
concatenated (user → project → project-local) into layer 2's prompt with an 8 KB budget; the tail is
truncated first, so project-local rules are the first to be dropped. Layer 3 does not read them.

**Relevant to this repo.** `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS and must never be committed;
this plugin's hardcoded-secret patterns are a second line of defence behind `.gitignore`, not a
replacement for it. It also does not replace the `/security-review` skill, which is an on-demand
review of the whole branch.

---

## 5. `typescript-lsp@claude-plugins-official` (v1.0.0)

**What it is.** Wires a TypeScript/JavaScript language server into Claude Code, giving real code
intelligence — go-to-definition, find-references, and type errors — instead of grep-and-guess.
Covers `.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`, `.mjs`, `.cjs`.

**It is not working yet.** The plugin is only the wiring; the server binary is a separate install and
is **not currently on this machine** (`typescript-language-server not found`). Install it globally:

```bash
npm install -g typescript-language-server typescript
```

**Usage after that.** Nothing to invoke — it backs the `LSP` tool, so definition/reference lookups
and diagnostics just become available on the frontend TypeScript sources.

**Why it's worth fixing.** `frontend/` is the whole Next.js 16 / React 19 / TypeScript app, and the
contract seams there are exactly the thing LSP is good at: `BankQuestion extends MockQuestion`,
`ProgressStore` and its four implementations, `lib/roleplay/types.ts` mirroring the Python parser.
Find-references across those beats a text search.

---

## 6. `context7@claude-plugins-official`

**What it is.** An MCP server (Upstash Context7) that fetches **current, version-specific**
documentation and code examples straight from a library's source repository into context. Hosted at
`https://mcp.context7.com/mcp` over HTTP — no local Node or `npx` process.

**Usage.** No command. Ask about a library, framework, SDK, CLI, or cloud service and the docs are
pulled automatically — React, Next.js, Tailwind, Supabase, Prisma, anything. Two tools sit behind it:
`resolve-library-id` (name → Context7 id) then `query-docs` (id + question → docs).

**Use it even when you think you know the answer** — that's the point. Model training data lags, and
this repo runs Next.js 16, whose App Router APIs changed in ways that predate most training data.
`frontend/AGENTS.md` already requires consulting `frontend/node_modules/next/dist/docs/` before
writing Next.js code; Context7 is the same instinct for anything not vendored locally.

**Not for:** refactoring, debugging our own business logic, code review, or general programming
concepts. Docs lookup only.

**Auth.** Works anonymously out of the box. `CONTEXT7_API_KEY` is optional and raises the rate limit;
it is **not set** on this machine. If you ever set it, it goes in the shell environment — never in a
committed file, same rule as `SUPABASE_SERVICE_ROLE_KEY`.

---

## Quick chooser

| I want to… | Use |
|---|---|
| Look up how a library actually works today | `context7` (just ask) |
| Jump to a definition / find every reference in `frontend/` | `typescript-lsp` (install the server first) |
| Know if the code I just wrote is safe | `security-guidance` (automatic) |
| Locate code without burning main-thread context | `cavecrew-investigator` |
| Make one small, bounded edit | `cavecrew-builder` |
| Review a diff, one line per finding | `cavecrew-reviewer` or `/caveman-review` |
| Write a commit message | `/caveman-commit` |
| See what compression has saved | `/caveman-stats` |
| Record what this session taught us | `/revise-claude-md` |
| Audit our `CLAUDE.md` files | `claude-md-improver` skill |
| Set up automation for a new repo | `claude-automation-recommender` skill |

---

# Part 3 — graphify

Not a plugin — a standalone CLI plus a user-level skill — but it is wired into this repo more deeply
than any of the plugins above, so it belongs here.

## What it is

Graphify turns a folder of files into a persistent **knowledge graph**: symbols, files, and concepts
as nodes; calls, imports, and references as edges; with community detection grouping them into named
subsystems. You then ask questions of the graph instead of grepping the tree. Every edge carries an
audit tag — `EXTRACTED` (read from the AST), `INFERRED` (a model's guess, with a confidence score),
or `AMBIGUOUS` — so you can tell a fact from a suggestion.

The point is token cost. `graphify benchmark` on this repo measures **20.1× fewer tokens per query**
than reading the corpus naively — ~9.4k tokens for a typical query against ~189k for the corpus.

## Where it lives

| Piece | Path |
|---|---|
| CLI | `/Users/kelton/.local/bin/graphify` |
| Skill | `~/.claude/skills/graphify/SKILL.md` (+ `references/`) |
| This repo's graph | `graphify-out/` |
| Scope rules | `.graphifyignore` |

It was installed into this project with `graphify claude install`, which did two things: wrote the
`## graphify` section into the root `CLAUDE.md`, and added `PreToolUse` hooks to
`.claude/settings.json` — `Bash|Grep` → `graphify hook-guard search`, `Read|Glob` →
`graphify hook-guard read`. Those hooks are why every shell or file-read call prints a reminder to
query the graph first. `graphify claude uninstall` reverses both.

## This repo's graph, as built

- **2,837 nodes · 5,617 edges · 168 communities** (147 named, 21 too thin to show)
- **97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS** — 194 inferred edges, average confidence 0.81
- Last run covered 70 files / ~615k words; two runs total have cost **1,303,260 input tokens, 0
  output**
- Named communities read like a map of the app: *ProgressStore Seam*, *Bank Loader & Test Composer*,
  *ICDC Deterministic Gate*, *Plan-10 Depth Slice Framework*, *Roleplay Board & Run Surface*, …
- Top god nodes (most connected): `cn()` 103 · `react` 59 · `Level` 43 · `Attempt` 42 · `Session` 40

**Scope is deliberately narrow.** `.graphifyignore` excludes the generated corpora and shipped data —
`backend/*/output/`, `backend/*/data/`, the question bank, `frontend/public/`, `graphify-out/` itself.
Those are bulk content, not architecture, and they outweigh the source roughly 6:1. So the graph
describes *how the app is built*, not what's in the bank. Don't ask it how many questions marketing
has; ask `check-data` or the recount one-liner in `CLAUDE.md`.

## Daily usage

Five read commands. None call a model; all read `graphify-out/graph.json`.

```bash
graphify query "how does the ProgressStore seam work"   # BFS from matched nodes, scoped subgraph
graphify explain "composeTest"                          # one node + its neighbours, plain language
graphify path "LiveQuizModal" "SupabaseStore"           # shortest path between two nodes
graphify affected "Attempt" --depth 2                   # reverse traversal: what breaks if I change X
graphify god-nodes --top 10                             # architectural hubs
```

Useful flags: `--budget N` (token cap, default 2000), `--dfs` (depth-first instead of breadth-first),
`--context <relation>` (repeatable edge filter), `--graph <path>` (point at another graph).

**Read the truncation notice.** The budget is a hard cap and the CLI tells you when it bit — a
`ProgressStore` query matches 150 nodes and a 600-token budget shows 15 of them, with
`[!] TRUNCATED … the answer may be among the 135 cut nodes` printed above the results. Truncated
output is not a negative result. Raise `--budget`, add a `--context` filter, or ask a narrower
question.

**Read the citations.** Every node prints `src=` and `loc=`, e.g.
`NODE NullStore [src=frontend/lib/progress/null-store.ts loc=L15 community=ProgressStore Seam]`.
Quote those when you cite a fact, and open the file before changing anything — the graph orients you,
it does not replace reading the line you're about to edit.

## Keeping it current

```bash
graphify update .            # re-extract changed files. AST-only, no API cost, no LLM
graphify update . --force    # allow a rebuild that has FEWER nodes than before
graphify cluster-only .      # recluster an existing graph without re-extracting
graphify label . --missing-only   # name only the unnamed communities (this one does call a model)
graphify watch .             # rebuild continuously on file change
```

`graphify update .` after any code change is the standing rule in `CLAUDE.md`, and on a **code-only**
change it is free — run it rather than letting the graph rot. The one trap: `update` refuses to write
a graph with fewer nodes than the last one, which is a guard against a broken extraction silently
gutting the graph. After a refactor that genuinely *deletes* code, that refusal is a false alarm —
re-run with `--force` (or `GRAPHIFY_FORCE=1`).

**What is free and what is not.** Only the AST pass is free. The moment a changed file is a doc,
plan or summary, the update dispatches semantic extraction subagents — the 2026-08-08 run over 68
backend `test-gen-model` documents cost **603k tokens**. Community **labels** cost on top of that.
So: after code edits, run `update` freely; after writing a plan or summary, budget for it. Detection
scope is what keeps that number sane — `.graphifyignore` at the repo root cuts the corpus from 2,212
files to 70, so never delete it to "get more coverage."

## Rebuilding from scratch

Only when the shape of the repo changes enough that incremental updates aren't enough:

```
/graphify                    # full pipeline on the current directory
/graphify . --mode deep      # thorough extraction, richer INFERRED edges
/graphify . --no-viz         # skip the 3 MB HTML
/graphify . --wiki           # build graphify-out/wiki/ — an agent-crawlable article per community
```

Exports exist for `--svg`, `--graphml` (Gephi/yEd), `--neo4j`, `--falkordb`, `--obsidian`, and
`--mcp` (serve the graph to agents over MCP stdio). None are set up here.

## Three loose ends — two open, one resolved

1. **No wiki.** `CLAUDE.md` says "if `graphify-out/wiki/index.md` exists, use it for broad
   navigation" — it does not exist. Build it with `graphify . --wiki` if you want that path live,
   or the line stays a no-op.
2. **Git hooks not installed.** `graphify hook status` reports `post-commit: not installed`,
   `post-checkout: not installed`, `merge driver: not registered`. `graphify hook install` would
   refresh the graph automatically on commit and checkout. Worth it given how often our worktree
   workflow switches branches.
3. **~~`graphify-out/` is untracked and NOT in `.gitignore`.~~ RESOLVED 2026-08-08 — selectively
   ignored.** `.gitignore` now carries `graphify-out/*` with two negations. The bulk stays out:
   `graph.json` (3.5 MB), `graph.html` (2.8 MB), `cache/` (3.4 MB) all rewrite wholesale per update,
   and `manifest.json` keys on `mtime` while `.graphify_python`/`.graphify_root` hold absolute
   machine paths, so committing those would make every clone re-extract anyway. Two files are
   tracked: **`.graphify_labels.json`**, the 168 curated community names, and **`GRAPH_REPORT.md`**,
   which GitHub renders inline. The earlier advice here — ignore the whole directory and let each
   machine build its own — was wrong on both premises: a doc-touching rebuild is not free (603k
   tokens, above), and clustering re-runs on every merge so community ids shift, meaning two
   machines building independently would not share a single label. `.graphify_labels.json` does not
   *restore* a graph for that same reason; it is the prior-naming source you diff new membership
   against when re-labelling. `graph.html` is deliberately not committed and cannot be published as
   an Artifact either — it loads vis-network from a CDN, so it needs network to render; attach it to
   a CI run if the team wants the interactive view. If we ever do commit the graph itself, register
   the union merge driver (`graphify hook install`) first, or every branch merge conflicts on the
   whole file.

## When to use it, and when not

Use it to **orient**: where does this live, what touches it, what breaks if I change it, what are the
subsystems. That is what the hooks nudge you toward, and on a repo this size it is genuinely cheaper
than a broad grep.

Do not use it as a source of truth for **line-level behaviour, current data, or anything generated**.
The graph is a snapshot of structure, 3% of its edges are inferred, and the generated corpora are
excluded from it by design. Orient with graphify, then read the file.
