# test-gen-model

Generates exam-authentic DECA multiple-choice questions. Two ways to run it:

- **Batch CLI** — `generate_test.py`, interactive; writes a timestamped `.txt` to `output/`.
- **Live single-question service** — `py_gen_service.py`, an HTTP façade that returns
  one validated question at a time (drives the frontend's 10-question JIT flow).

Both call a local **Ollama** model. Key env vars: `OLLAMA_API_URL`,
`OLLAMA_MODEL` (default `llama3.2:latest`), `OLLAMA_API_KEY`, `OLLAMA_TEMPERATURE`,
`OLLAMA_NUM_CTX`.

## Batch CLI

```bash
source venv/bin/activate            # from repo root
python backend/test-gen-model/src/generators/generate_test.py
```

Prompts for cluster + level, then generates `TEST_TARGET_QUESTIONS` (default 10)
questions in batches of up to 10.

## Live single-question service (`py_gen_service.py`)

A minimal stdlib `http.server` (no extra deps) exposing one generation endpoint.
Stateless and localhost-only.

```bash
source venv/bin/activate
python backend/test-gen-model/src/py_gen_service.py
# override the port: PY_GEN_PORT=8000 python .../src/py_gen_service.py
```

Binds `127.0.0.1:8000` by default (`PY_GEN_HOST`, `PY_GEN_PORT`). The Next.js route
handler proxies to it via `PY_GEN_URL`.

### Endpoints

`GET /health` → `{ ok, clusters, levels, difficulties, model }`

`POST /generate-question`
```jsonc
// request
{
  "cluster": "marketing",        // one of the configured clusters
  "level": "District",           // District | Association | ICDC
  "difficulty": "medium",        // easy | medium | hard
  "area": "Selling",             // optional — DECA area name or pi/ slug
  "excludePis": ["Explain ..."]  // optional — PIs already used in this quiz
}
// 200 response: a BankQuestion
{
  "id": "marketing-district-live-1a2b3c4d",
  "cluster": "marketing", "level": "District",
  "instructionalArea": "Selling", "performanceIndicator": "...",
  "question": "...", "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
  "answer": "B", "explanation": "...",
  "difficulty": "medium", "verified": false
}
```

Errors: `400` for a bad/unknown field, `502` if generation fails after retries.

### Speed notes

The PI library, system prompt, and parsed example blocks are cached per process
(first call for a cluster warms them), so subsequent `/generate-question` calls are
essentially just the model round-trip. The live path uses fewer few-shot examples
than the batch path (`TEST_LIVE_MAX_EXAMPLES`, default 3) to keep prompts small.

Live-generated questions are marked `verified: false` — a 3B model is below the
Sonnet-authored static bank in quality; a later pass can promote validated ones.

## Difficulty

`generate_one` (and the service) take a `difficulty` of `easy | medium | hard`,
appended as a `TARGET DIFFICULTY` directive to the prompt and echoed back as the
question's `difficulty` field. The batch CLI does not request a difficulty and is
unaffected. See `plans/03-practice-test-live-and-difficulty-plan.md`.
