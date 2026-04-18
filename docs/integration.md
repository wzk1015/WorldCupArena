# Integrating Your Model or Agent with WorldCupArena

This guide is for **LLM and deep-research agent developers** who want their system evaluated on the WorldCupArena leaderboard. The full integration typically takes under 2 hours.

Three integration paths, listed by effort:

| Path | When to use | Effort |
|---|---|---|
| **A. OpenAI-compatible endpoint** | your model speaks the OpenAI chat-completions API | ~10 min |
| **B. Anthropic Messages API shape** | your model speaks the Anthropic Messages API | ~10 min |
| **C. Custom runner** | your model has a unique API or multi-step agent loop | ~1–2 h |

---

## Path A — OpenAI-compatible endpoint (easiest)

If your service exposes `/v1/chat/completions` with the standard request/response shape (OpenAI, DeepSeek, Together, DashScope, xAI, Perplexity all fit), you don't need any Python code. Just add an entry to [configs/models.yaml](../configs/models.yaml):

```yaml
closed_llm:                           # or open_llm, depending on how you classify it
  - id: my-model-v1                   # used as filename in data/predictions/
    provider: openai                  # any provider that maps to OpenAICompatRunner
    model: my-model-v1                # the name the API expects in the "model" field
    api_key_env: MY_MODEL_API_KEY     # env var name to read the key from
    base_url: https://api.myservice.ai/v1
    price_per_mtok: { input: 1.50, output: 6.00 }
    settings_supported: [S0, S1, S2]  # which context settings this model runs under
```

Set `MY_MODEL_API_KEY` in `.env`. That is the entire integration.

The registered providers that route to `OpenAICompatRunner` are: `openai`, `deepseek`, `together`, `dashscope`, `xai`, `perplexity`. Any of them will do — pick whichever is semantically closest.

### Settings cheat-sheet

| Setting | What your model receives | When to support it |
|---|---|---|
| **S0** | fixture header only (teams, kickoff, venue) | plain LLMs, tests pure prior knowledge |
| **S1** | + official squads | plain LLMs, tests squad-aware reasoning |
| **S2** | + squads + form + news + stats | plain LLMs, tests full-context synthesis |
| **S3** | fixture header; tools enabled | **only** search-enabled LLMs and research agents |

Do **not** declare `S3` unless your model actually has live browsing / tool use.

---

## Path B — Anthropic-shaped endpoint

Same as Path A, but set `provider: anthropic`. The runner accepts optional tools:

```yaml
search_llm:
  - id: my-model-search
    provider: anthropic
    model: my-model-search-v1
    api_key_env: MY_MODEL_API_KEY
    base_url: https://api.myservice.ai
    tools: [web_search]              # or [web_search, extended_thinking]
    price_per_mtok: { input: 3.00, output: 15.00 }
    settings_supported: [S3]
```

The runner wires up the `web_search_20250305` tool block and extracts sources from `web_search_tool_result` blocks.

---

## Path C — Custom runner

For agents with a unique API (multi-step planning, streaming tool use, custom auth, long-running async jobs), implement a subclass of [`BaseRunner`](../src/runners/base.py).

### Minimum viable runner

```python
# src/runners/myagent_runner.py
from typing import Any
from .base import BaseRunner

class MyAgentRunner(BaseRunner):
    category = "deep_research_agent"

    def generate(self, system_prompt: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        # 1. Call your API. Use self.api_key() and self.base_url().
        # 2. Return a dict with these keys:
        return {
            "text": "<assistant response as a JSON string>",
            "thinking": None,                 # optional reasoning trace
            "input_tokens": 1234,
            "output_tokens": 567,
            "tool_calls": 3,
            "sources": [                      # optional — only if your agent browses
                {"url": "https://...", "accessed_at": "2026-04-15T12:34:56Z",
                 "published_at": "2026-04-12T09:00:00Z",  # critical for leakage audit
                 "title": "..."},
            ],
        }
```

Then register it in [src/runners/__init__.py](../src/runners/__init__.py):

```python
from .myagent_runner import MyAgentRunner

PROVIDER_RUNNERS: dict[str, type[BaseRunner]] = {
    ...
    "myagent": MyAgentRunner,
}
```

And add the model entry to `configs/models.yaml` with `provider: myagent`.

### Flat-price agents

If your agent charges per-run (not per-token), replace `price_per_mtok` with `price_per_run_usd` in the YAML entry, and override `price_tokens()` in your runner:

```python
def price_tokens(self, input_tokens: int, output_tokens: int) -> float:
    return float(self.cfg.get("price_per_run_usd", 0.0))
```

### What BaseRunner does for you (you don't need to reimplement)

- **JSON extraction** (`parse_json`) — handles ```json fences and best-effort object extraction.
- **Schema + semantic validation + repair retries** — the orchestrator wraps your `generate()` with a `validate_fn` that will call back with a repair prompt (up to 2 times) if the output fails checks. Just return text from `generate()`; the rest is automatic.
- **Source merging** — both sources you return AND sources declared by the model inside the JSON are merged for the leakage audit.
- **Cost accounting, wall-clock, retry count, error wrapping** — filled in by the base class.

---

## Output contract

Regardless of integration path, the model's final JSON response must conform to [schemas/prediction.schema.json](../schemas/prediction.schema.json). The required fields, in the order they must appear:

1. `fixture_id`, `model_id`, `setting`, `submitted_at`
2. `reasoning` — **must come first before any numeric field**. Required keys: `overall` (≥80 characters). Optional but recommended: `t1_result`, `t2_player`, `t3_events`, `t4_stats`.
3. `win_probs` — `{home, draw, away}`, summing to 1 ±1e-2.
4. `score_dist` — array of `{score: "H-A", p}` objects summing to 1 ±1e-2.
5. `most_likely_score`, `expected_goal_diff`, optional `advance_prob`.
6. `lineups.home.starting` and `lineups.away.starting` — exactly 11 players each.
7. `formations.home`, `formations.away` — e.g. `"4-3-3"`.
8. `scorers` — array, each with `{player, team, p}` (optional `minute_range`).
9. `stats` — 8 required keys: `possession`, `shots`, `shots_on_target`, `corners`, `pass_accuracy`, `fouls`, `saves`, `defensive_actions`. Each value is `{home, away}`.

Optional but scored: `assisters`, `substitutions`, `cards`, `penalties`, `own_goals`, `motm_probs`, `sources`.

If the model emits malformed output, the orchestrator sends a targeted repair prompt back through the same runner. You will see `repair_retries: N` in the saved prediction record. After `max_format_retries` (default 2), we stop retrying and flag `validation_errors`.

---

## Leakage policy (critical for search / agent models)

Every source your agent cites must include `accessed_at` (ISO 8601 UTC, best if from your tool result). If `published_at` is also available, **include it** — the grader uses `published_at > lock_at_utc` to zero out any task that depends on a post-lock source.

If you skip `published_at`, we err on the side of trust (no penalty), **but** we will flag the run as "leakage audit incomplete" on the leaderboard, which reviewers treat as a weaker result than an equally-scoring leakage-clean run. **Honest `published_at` is a competitive advantage.**

---

## Validating your integration locally

Before opening a PR, run the bundled dry-run limited to your model:

```bash
DRYRUN_MODELS=my-model-v1 bash scripts/dryrun_bayern_madrid.sh
```

This will lock → predict → grade → leaderboard on a real past fixture whose truth is checked in. Expected signals of a successful integration:

- `data/predictions/bayern_madrid_ucl_qf_l2/my-model-v1__S0.json` exists.
- Inside that file: `prediction` is a fully-populated JSON, `validation_errors` is `null`, `repair_retries` is 0 or 1, `cost_usd` is plausible.
- `data/results/bayern_madrid_ucl_qf_l2/my-model-v1__S0.json` has a `composite` score in [0, 100].

If `repair_retries == 2` and `validation_errors` is non-null, your system prompt is probably hiding the `reasoning` field or emitting stats as numbers instead of `{home, away}` pairs. Check [prompts/system.md](../prompts/system.md) and [prompts/task_per_match.md](../prompts/task_per_match.md) — your model receives both.

---

## Submitting

Open a PR with:

1. Your model entry in `configs/models.yaml`.
2. (Path C only) your runner file + registration in `src/runners/__init__.py`.
3. A one-paragraph README-snippet: what your model is, expected strengths, cost per fixture.
4. The output of your local dry-run (attach `data/predictions/bayern_madrid_ucl_qf_l2/<your-model>__*.json`).

We'll run a single-fixture validation pass, add you to the next Phase 1 batch, and attribute all model outputs to you on the public leaderboard.

---

## FAQ

**Can my model skip settings it doesn't support well?**
Yes — only list the `settings_supported` you want evaluated. An open model without strong long-context handling may drop S2.

**Can I sponsor a closed-weight model I don't own?**
Yes — provide an API key with sufficient quota + a budget ceiling. We'll cap spending at the budget.

**Does the leaderboard separate LLMs from agents?**
Yes — three leaderboards: Main (all), Above-Market (vs. Pinnacle), and Research Uplift (S3 − S2). Agents and search-LLMs compete on all three; plain LLMs compete on Main and Above-Market only.

**Does the benchmark allow self-hosted open models?**
Yes — point `base_url` at your vLLM / TGI / SGLang endpoint. `openai_compat` works out of the box.

**How are ties broken?**
By composite score. Ties beyond that are broken by RPS on T1, then by Brier. See [docs/tech_report.md](tech_report.md) §4 for the full scoring spec.
