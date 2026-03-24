# Decision Logic Policy Layer: Cotton Relevance + Query Complexity

## Goal

Create explicit, auditable decision logic for:

1. `is_question_cotton_related?`
2. `is_question_simple_vs_complex?`

This document maps what exists today, what is missing, and a proposed transparent policy layer with testable rules and monitoring.

---

## What Exists Today

### A) Simple vs Complex (implemented)

- Deterministic classifier exists in `rag/routing/classifier.py`.
- Rule-based score with threshold:
  - Multi-doc intent: `+2`
  - Explicit quantity: `+2`
  - Output format ask: `+1`
  - Time range ask: `+1`
  - Length: `+1` (>20 words), `+2` (>35 words)
  - Default threshold: `>=3` => `complex` (env override `COMPLEX_QUERY_THRESHOLD`)
- Used in API routing in `app/api/routers/ask.py` (both standard and streaming paths).
- Unit tests exist in `tests/test_classifier.py`.

### B) Cotton-related (not explicitly implemented)

- No deterministic `cotton_related` classifier module exists.
- System prompts are cotton-scoped (`app/application/services/prompting.py`), but prompts are not policy gates.
- `app/factory.py` has an LLM query analyzer for `intent` (`conversational` vs `knowledge`) and dynamic `k`; this is not the same as cotton-domain relevance.

### C) Observability today

- Complexity score and query type are returned in API response.
- Classification breakdown is logged by classifier logger.
- General latency/retrieval stats exist in ask response/logging.
- No dedicated domain-policy metrics, no rule-level counters, no misroute dashboard.

---

## Missing Pieces

1. No explicit decision for domain scope (`in-domain`, `ambiguous`, `out-of-domain`).
2. No single policy object that records *why* a route decision happened.
3. No stable rule IDs/versioning for auditability.
4. No test suite for cotton-related decision logic.
5. No monitoring for decision quality (false in/out domain, complexity misroute rate).
6. No explicit fallback behavior matrix when signals disagree.

---

## Proposed Transparent Policy Layer

## Policy interface

Add a dedicated policy module (example: `rag/routing/policy.py`) returning:

```json
{
  "policy_version": "2026-02-24.v1",
  "cotton_related": "in_domain|ambiguous|out_of_domain",
  "cotton_score": 0,
  "complexity": "simple|complex",
  "complexity_score": 0,
  "rules_fired": ["COTTON_KEYWORD", "COMPLEX_MULTI_DOC"],
  "explanations": {
    "cotton": "Matched 2 domain terms; no out-of-domain override.",
    "complexity": "Multi-doc intent (+2) + table request (+1)."
  }
}
```

## Rule model

Each rule must be deterministic and versioned:

- `rule_id` (stable ID, e.g., `COTTON_KEYWORD`)
- `description`
- `condition` (regex/list/threshold)
- `effect` (score delta or hard label)
- `priority` (for tie-break precedence)

### Decision 1: Cotton-related rules (proposed)

- `COTTON_KEYWORD` (+2): matches cotton domain lexicon (`cotton`, `bollworm`, `heliothis`, `picking`, `ginning`, `mybmp`, `CRDC`, etc.).
- `AGRONOMY_KEYWORD` (+1): agronomy terms commonly present in corpus (`irrigation`, `yield`, `soil carbon`, `IPM`, `water productivity`).
- `CORPUS_ENTITY_MATCH` (+2): match known report titles/program names from metadata index.
- `OUT_OF_SCOPE_HARD` (force `out_of_domain`): obvious unrelated asks (`write javascript game`, `movie review`, etc.).
- `AMBIGUOUS_SHORT` (force `ambiguous`): very short generic queries with weak evidence (`help`, `what is best practice?`).

Suggested thresholds:

- Score `>=3` and no out-of-scope hard rule => `in_domain`
- Score `1-2` => `ambiguous`
- Score `<=0` => `out_of_domain`

### Decision 2: Simple vs complex rules (proposed)

- Keep existing complexity scoring logic as-is for v1 (already shipped + tested).
- Move classifier output into shared policy object so route decisions are unified and inspectable.

### Precedence

1. `OUT_OF_SCOPE_HARD` always wins for domain.
2. Domain decision computed first.
3. Complexity is only actionable when domain is `in_domain` or `ambiguous`.
4. `ambiguous` domain uses conservative route: simple retrieval + clarification prompt.

---

## Testable Rules

Minimum test suite additions:

- `tests/test_policy_cotton_domain.py`
  - in-domain positive cases
  - out-of-domain clear negatives
  - ambiguous short/generic cases
  - precedence checks (`OUT_OF_SCOPE_HARD` beats keyword noise)
- `tests/test_policy_decision_contract.py`
  - output schema includes `policy_version`, `rules_fired`, explanations
  - deterministic output for fixed inputs
- `tests/test_policy_routing_integration.py`
  - API response includes policy payload
  - complex path selected only when domain not out-of-domain and complexity is complex

Golden-set evaluation (offline CSV) should include labeled fields:

- `expected_domain`: in/ambiguous/out
- `expected_complexity`: simple/complex
- `notes`

---

## Monitoring Metrics (Policy Quality + Ops)

Emit counters/histograms tagged by `policy_version`, `route`, `persona`.

Core metrics:

1. `policy.domain.in_rate`, `policy.domain.ambiguous_rate`, `policy.domain.out_rate`
2. `policy.complexity.complex_rate`
3. `policy.rule.fire_count{rule_id}`
4. `policy.route.map_reduce_rate`
5. `policy.latency_ms` (policy eval only)
6. `policy.disagreement_rate`
   - Example: deterministic domain says `out`, LLM fallback says `in`
7. `policy.feedback_negative_rate_by_bucket`
   - join feedback thumbs-down by `(domain_bucket, complexity_bucket, rule_combo)`
8. `policy.override_rate`
   - fraction of requests where fallback/override changed primary decision

Suggested alert seeds:

- Domain out-rate shifts >30% week-over-week
- Complex-rate doubles day-over-day
- Negative feedback rate for a rule combo >2x baseline
- Policy latency p95 > 20ms (deterministic rules should be cheap)

---

## Rollout Plan

1. Introduce policy module in shadow mode (log-only, no routing change).
2. Compare shadow decisions vs current behavior for 1-2 weeks.
3. Tune lexicons/thresholds using false-positive and false-negative review.
4. Turn on routing for domain decision.
5. Keep complexity routing unchanged but sourced from policy object.
6. Version bump on any rule or threshold change; keep changelog of policy versions.

---

## Recommended First Deliverables

1. `rag/routing/policy.py` with deterministic rule engine and structured output.
2. `tests/test_policy_cotton_domain.py` and integration tests.
3. API response field `policy` in `/api/ask` payload for transparency.
4. Dashboard with rule fire counts + feedback overlays.

