# AI-Powered Portfolio v1.3 Product Document and Implementation Plan

Gangadhar Allam | April 2026

---

## Save Target

Save this document in the repo root beside `portfolio_v1_2.md` as:

`portfolio_v1_3.md`

---

## 1. What v1.3 Is and Why It Exists

v1.2 gave the system richer context about how applications were submitted and how recruiters engaged. v1.3 uses that context to answer a harder question: not just what happened, but what should happen next.

The private admin currently shows you that applications exist and that recruiters visited. It cannot tell you which applications deserve follow-up attention or whether your resume was a strong match for the role. That judgement is made manually, on instinct, with no data behind it.

v1.3 introduces a structured fit assessment pipeline. For each application, you paste the JD and the resume version you used. The system parses the JD, matches it against the resume using a controlled vocabulary, scores the result deterministically, and records every attempt. The dashboard then derives priority and disagreement signals from those scores — telling you which applications to act on and where the system's signal contradicted the real outcome.

**The public portfolio is not touched.** Recruiters see the same site. v1.3 is entirely a private admin upgrade.

---

## 2. Core Principle

The fit score must be reproducible. The same JD and resume, assessed on two different days, must produce the same score. This rules out any design where the LLM is responsible for weighting or scoring. The LLM handles pattern recognition — extracting requirements from the JD and matching skills from the resume. All weighting, scoring, and label assignment is deterministic Python, not model output.

This is the same principle that motivated the context quality fix in v1.2. The LLM is only as reliable as the structure around it.

---

## 3. Scope

**In scope for v1.3:**

- Versioned JD and resume context per application
- Manual fit assessment trigger
- Controlled skill vocabulary and normalization
- JD parsing via LLM (first call)
- Resume-vs-JD matching via LLM (second call)
- Deterministic fit score and confidence label
- Historical assessment records
- Dashboard display for fit, priority, disagreement, and assessment status
- Dashboard navigation link to the context page per application

**Out of scope for v1.3:**

- Public portfolio page changes
- GA4 event changes
- Recruiter tracking changes
- Groq intelligence summary changes
- Automated resume rewriting or email drafting
- Background jobs or automatic assessment on save
- Expanding the outcome ENUM (deferred to v1.4 — see Section 18)
- Extracting fit routes into `routers/fit.py` (deferred to v1.4 — see Section 18)

---

## 4. Data Model

### 4.1 New Table: `application_context`

```sql
CREATE TABLE IF NOT EXISTS application_context (
    id             SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    jd_text        TEXT NOT NULL,
    resume_text    TEXT NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    is_active      BOOLEAN DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_context_per_application
ON application_context (application_id)
WHERE is_active = TRUE;
```

One active context per application is enforced at the database level via partial unique index. The application layer deactivates the old context before inserting the new one, but the index is the authoritative constraint.

### 4.2 New Table: `fit_assessments`

```sql
CREATE TABLE IF NOT EXISTS fit_assessments (
    id               SERIAL PRIMARY KEY,
    application_id   INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    context_id       INTEGER REFERENCES application_context(id),
    fit_score        TEXT,
    fit_confidence   TEXT,
    confidence_score FLOAT,
    signal_conflict  BOOLEAN DEFAULT FALSE,
    matching_skills  JSONB,
    missing_skills   JSONB,
    jd_weights       JSONB,
    rejected_terms   JSONB,
    failure_reason   TEXT,
    vocab_version    TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

Every real assessment attempt is recorded here, whether successful or failed. Rows are never deleted. Old assessments remain tied to their original `context_id` so history is always interpretable even after context replacement.

**Note on CockroachDB SERIAL:** CockroachDB maps `SERIAL` to `unique_rowid()`, which generates large non-sequential integers rather than `1, 2, 3`. This is consistent with the existing schema and is not a functional issue. The `ORDER BY created_at DESC, id DESC` tiebreaker pattern works correctly regardless of ID magnitude. However, the context page assessment history must not display raw `id` values — use a Python-derived row number for display instead. See Section 12.3.

### 4.3 New Column on `applications`

```sql
ALTER TABLE applications
ADD COLUMN IF NOT EXISTS assessment_status TEXT DEFAULT 'not_run';
```

### 4.4 Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_application_context_application_id
ON application_context(application_id);

CREATE INDEX IF NOT EXISTS idx_fit_assessments_application_latest
ON fit_assessments(application_id, created_at DESC, id DESC);
```

The `created_at DESC, id DESC` ordering on the index matches the ordering used everywhere latest records are selected. This is not optional — it makes those queries deterministic.

---

## 5. Vocabulary v1

### 5.1 Purpose

The vocabulary is the controlled list of canonical skill terms the system accepts. It defines what the matcher can return, what the normalizer will accept, and what gets tracked as rejected. It is a product decision, not an implementation detail. Defining it here forces the scope of v1 to be explicit.

### 5.2 Role Coverage

Vocabulary v1 covers skills relevant to the five active role categories defined in v1.2:

- `data_analyst`
- `apm`
- `founders_office`
- `ai_engineer`
- `business_analyst`

Skills outside these categories are not in scope for v1. The vocabulary is not exhaustive — it covers the skills most likely to appear in JDs targeting these roles at early-stage and mid-stage companies.

### 5.3 Structure

```python
CANONICAL_SKILLS: list[str]   # accepted canonical terms, lowercase
SYNONYM_MAP: dict[str, str]   # variant → canonical term
VOCAB_VERSION: str = "v1"
```

### 5.4 Illustrative Canonical Skills

```text
SQL, Python, Excel, Tableau, Power BI, data analysis, data visualization,
product management, product strategy, user research, A/B testing,
machine learning, LLMs, prompt engineering, API integration,
stakeholder management, go-to-market, market research,
business analysis, requirements gathering, process improvement,
communication, problem solving
```

This list is illustrative. The full canonical list lives in `services/fit/vocabulary.py`. It should be reviewed and extended before the first production assessment run.

### 5.5 Illustrative Synonym Mappings

```text
"ml"                    → "machine learning"
"llm"                   → "LLMs"
"large language models" → "LLMs"
"pm"                    → "product management"
"sql"                   → "SQL"
"ms excel"              → "Excel"
"microsoft excel"       → "Excel"
"data viz"              → "data visualization"
"ab testing"            → "A/B testing"
"a/b"                   → "A/B testing"
"apis"                  → "API integration"
"rest api"              → "API integration"
"gtm"                   → "go-to-market"
```

### 5.6 Fuzzy Matching Threshold

The fuzzy match threshold is **88**.

Rationale: tested against role-specific skill variants commonly appearing in Indian startup JDs. Below 88, false positives emerge — for example, "Excel" incorrectly matching "Axel", or "SQL" matching "SOL". Above 88, real variants fail — for example, "postgre" failing to match "PostgreSQL". 88 is the calibrated midpoint that maximises true matches while controlling false positives.

Fuzzy matching is the third layer of normalization, applied only after exact match and synonym resolution fail. See Section 7.3.

---

## 6. Core User Flow

1. User creates an application in the existing admin flow.
2. User clicks the "Add Context" link in the dashboard table for that application.
3. User is taken to `/admin/context/{application_id}`.
4. User pastes the JD text and the resume version used for that application.
5. System saves the new active context, deactivates any previous context, and resets `assessment_status` to `not_run`.
6. User clicks Assess Fit.
7. System runs JD parsing, normalization, matching, and deterministic scoring.
8. System inserts a historical assessment row into `fit_assessments`.
9. System updates `applications.assessment_status`.
10. User returns to the dashboard. The Context column now shows "Edit Context". Fit confidence, priority, and disagreement columns reflect the latest assessment.

---

## 7. Fit Engine

### 7.1 Architecture

The fit engine uses two separate LLM calls followed by a deterministic scoring layer. The two calls are isolated by design — the matcher does not receive JD weights, and the scorer does not call the LLM.

```
JD text ──────────────────────────────────────► JD Parser (LLM call 1)
                                                        │
                                              must_have, important, nice_to_have
                                                        │
                                                        ▼
JD text + Resume text + Vocabulary ──► Matcher (LLM call 2)
                                                        │
                                         matching_skills, missing_skills, fit_score
                                                        │
                                                        ▼
                                           Deterministic Scorer
                                                        │
                                         confidence_score, fit_confidence
```

**LLM provider:** Groq, using `llama-3.3-70b-versatile` or the equivalent available model at build time.

**Temperature:** Both LLM calls use `temperature=0`. This is intentional and differs from the intelligence layer in `intelligence.py`, which uses `temperature=0.4`. The intelligence layer benefits from variation to produce readable natural-language insights. The fit engine requires deterministic, reproducible outputs — the same inputs must produce the same score across runs. Temperature 0 is a hard requirement for the fit engine, not a preference.

**API key:** Both calls use the existing `GROQ_API_KEY` environment variable already loaded in `intelligence.py`. No new environment variables are needed.

### 7.2 JD Parser (Call 1)

**Input:** JD text only.

**System prompt constraint:** The parser must be instructed to return a JSON object with exactly three keys: `must_have`, `important`, `nice_to_have`. Each value must be an array of strings. No other keys, no preamble, no explanation. Use `response_format={"type": "json_object"}` consistent with the existing Groq integration pattern in `intelligence.py`.

**Output:**

```json
{
  "must_have": ["SQL", "Python", "data analysis"],
  "important": ["Tableau", "stakeholder management"],
  "nice_to_have": ["machine learning"]
}
```

**Validation:** If the output is unparseable, missing required keys, has non-array category values, or contains non-string skill items, classify as `jd_extraction_invalid` and insert a failed row.

### 7.3 Normalization

After JD parser output is validated, each skill string is normalized against the vocabulary using three layers in order:

1. **Exact match:** lowercase the term and check against the canonical list directly.
2. **Synonym resolution:** check the synonym map for the lowercased term.
3. **Fuzzy match:** use `rapidfuzz` at threshold 88. If the best match score is below 88, the term is rejected.

Terms that fail all three layers are collected in `rejected_terms` and stored in the assessment row. They are not counted in scoring. If must-have skills pass JD parser validation but are later rejected by vocabulary normalization, that is a vocabulary coverage limitation — it is not a weak JD. Extend the vocabulary in the next cycle.

Duplicate skills across JD categories keep the highest weight. A skill appearing in both `must_have` and `important` is treated as `must_have`.

### 7.4 Matcher (Call 2)

**Input:** JD text, resume text, and the canonical vocabulary list. The matcher does not receive `jd_weights`. Weighting is not the LLM's responsibility.

**System prompt constraint:** The matcher must be instructed to return a JSON object with exactly three keys: `matching_skills` (array of strings), `missing_skills` (array of strings), and `fit_score` (exactly one of: `high`, `medium`, `low`). Use `response_format={"type": "json_object"}` consistent with the existing Groq integration pattern.

Any value for `fit_score` outside `{high, medium, low}` is treated as `matcher_invalid` — the output is rejected, not normalised. This differs deliberately from the intelligence layer in `intelligence.py`, which clamps invalid type values. The fit engine rejects because `fit_score` participates in signal conflict comparison and must be semantically precise. Clamping an out-of-range value would silently corrupt the signal conflict diagnostic.

**Validation:** If the output is unparseable, missing required keys, has non-array skill values, or has a `fit_score` value outside `{high, medium, low}`, classify as `matcher_invalid` and insert a failed row.

### 7.5 Deterministic Scoring

JD weights:

| Category | Weight |
|---|---|
| `must_have` | 3 |
| `important` | 2 |
| `nice_to_have` | 1 |

After normalization and deduplication, `jd_weights` is a dict mapping canonical skill → weight.

```python
matching_set = set(matching_skills)
weighted_matching = sum(jd_weights.get(skill, 0) for skill in matching_set)
weighted_total = sum(jd_weights.values())
confidence_score = weighted_matching / weighted_total
```

**Guardrails (in execution order):**

1. If `weighted_total <= 0`, abort before division and insert a failed row with `weighted_total_zero`.
2. After division, require `math.isfinite(confidence_score)`.
3. Require `0.0 <= confidence_score <= 1.0`.
4. If either check fails, insert a failed row with `score_invalid`.

**Confidence labels:**

| Score | Label |
|---|---|
| `> 0.7` | `high` |
| `0.4 – 0.7` | `medium` |
| `< 0.4` | `low` |

**Signal conflict:**

```python
signal_conflict = (
    fit_score is not None
    and fit_confidence is not None
    and fit_score != fit_confidence
)
```

Signal conflict records where the LLM's qualitative impression disagreed with the deterministic score. It is stored per assessment row. It is not used to compute priority or disagreement. Failed rows always store `signal_conflict = FALSE`.

---

## 8. Assessment Status Model

`applications.assessment_status` reflects the state of the latest attempt for the currently active context.

| Value | Meaning |
|---|---|
| `not_run` | No assessment has been run for the current active context |
| `completed` | Latest assessment produced a valid score |
| `weak_jd` | Latest assessment produced a valid score, but JD structure was weak |
| `failed` | Latest assessment started but failed before producing a usable score |

### 8.1 Failure Reason Model

A `fit_assessments` row is inserted only when an assessment attempt actually begins. Clicking Assess Fit with no active context is a precondition failure and creates no row.

| Failure reason | Trigger |
|---|---|
| `jd_extraction_invalid` | JD parser output is malformed, unparseable, missing required keys, has non-array category values, or contains non-string skill items |
| `jd_extraction_empty` | JD parser output is structurally valid but all three arrays are empty |
| `weighted_total_zero` | Normalized JD skills produce no valid weighted requirements |
| `matcher_invalid` | Matcher output is malformed, unparseable, missing required keys, has invalid value types, or has `fit_score` outside `{high, medium, low}` |
| `matcher_failed` | Matcher call fails due to timeout, API error, missing response, or unexpected execution error |
| `score_invalid` | Deterministic scoring produces a non-finite or out-of-bounds score |

### 8.2 Weak JD Rule

Evaluated only after the `jd_extraction_empty` check passes.

1. If all JD parser arrays are empty → `jd_extraction_empty` → fail, no score.
2. Else if `must_have` and `important` are both empty while `nice_to_have` has at least one skill → `weak_jd` → continue to scoring, insert usable row, set status `weak_jd`.
3. Else → normal assessment.

Weak JD is evaluated against parser output before vocabulary rejection. If must-have skills exist in parser output but are later rejected by normalization, that is not a weak JD.

---

## 9. Context Versioning

Each application can have one active context at a time.

When a new context is saved:

1. The previous active context's `is_active` is set to `FALSE`.
2. A new context row is inserted with `is_active = TRUE`.
3. `applications.assessment_status` is reset to `not_run`.
4. Old assessment rows remain in `fit_assessments` tied to their original `context_id`. They are not deleted and not shown as current.

The partial unique index on `application_context (application_id) WHERE is_active = TRUE` enforces steps 1 and 2 at the database level.

---

## 10. Latest Attempt vs Latest Usable Assessment

All latest-record queries use `ORDER BY created_at DESC, id DESC`. This ordering is deterministic and must be used everywhere — not `created_at DESC` alone, which is ambiguous on rows inserted in the same transaction. CockroachDB's non-sequential `SERIAL` values are large unique integers and work correctly as a tiebreaker regardless of magnitude.

**Latest attempt:** The latest `fit_assessments` row for the application regardless of status. Used for failure reason display and attempt history.

**Latest usable assessment:** The latest `fit_assessments` row where `fit_confidence IS NOT NULL`, ordered by `created_at DESC, id DESC`. Used for score display only when `assessment_status` is `completed` or `weak_jd`.

---

## 11. Dashboard Behavior

### 11.1 Fields Added Per Application

| Field | Source | Computed where |
|---|---|---|
| `assessment_status` | `applications.assessment_status` | SQL |
| `fit_confidence` | Latest usable assessment | SQL (correlated subquery) |
| `confidence_score` | Latest usable assessment | SQL (correlated subquery) |
| `fit_score` | Latest usable assessment | SQL (correlated subquery) |
| `signal_conflict` | Latest usable assessment | SQL (correlated subquery) |
| `failure_reason` | Latest attempt | SQL (correlated subquery) |
| `has_active_context` | `application_context` | SQL (EXISTS subquery) |
| `followed_up` | `applications.followed_up` | SQL (was missing from current query — added now) |
| `priority` | Derived from `fit_confidence`, `visit_count`, `followed_up`, `date_applied` | **Server-side Python**, after SQL returns |
| `disagreement` | Derived from `fit_confidence` and `outcome` | **Server-side Python**, after SQL returns |

Priority and disagreement are computed in the route handler in Python, after the SQL query returns and before `json_data` is serialised for the client. They are passed to the frontend as pre-computed string fields — the JS reads them directly and renders them. The JS does not re-derive them. This keeps derivation logic in one place and avoids duplicating it in JavaScript.

### 11.2 Display Rules

| Status | Score | Priority | Disagreement | Failure reason |
|---|---|---|---|---|
| `not_run` | — | — | — | — |
| `failed` | — | — | — | ✓ (from latest attempt) |
| `completed` | ✓ | ✓ | ✓ | — |
| `weak_jd` | ✓ + warning | ✓ | ✓ | — |

### 11.3 Priority Derivation

Computed server-side for each application row after SQL returns. Never stored.

```text
IF fit_confidence = "high"
   AND visit_count > 0
   AND followed_up = FALSE
   AND date_applied < today - 3 days:
       priority = "HIGH"

ELSE IF fit_confidence = "high"
     AND visit_count = 0:
       priority = "MEDIUM"

ELSE IF fit_confidence = "low":
       priority = "LOW"

ELSE:
       priority = "MEDIUM"
```

Set `priority = None` when `assessment_status` is `not_run` or `failed`. The JS renders an empty cell for `None`.

### 11.4 Disagreement Derivation

Computed server-side for each application row after SQL returns. Never stored. The actual outcome ENUM values in `schema.sql` are: `pending`, `got_call`, `rejected`, `no_response`.

```text
IF fit_confidence = "high" AND outcome IN ("rejected", "no_response"):
    disagreement = True

ELSE IF fit_confidence = "low" AND outcome = "got_call":
    disagreement = True

ELSE:
    disagreement = False
```

Pending outcomes always produce `disagreement = False`. Set `disagreement = None` when `assessment_status` is `not_run` or `failed`. The JS renders an empty cell for `None`.

**Note on `offer`:** There is no `offer` value in the current outcome ENUM. Adding it requires `ALTER TYPE` on CockroachDB, deferred to v1.4. When added, the disagreement rule extends to: `fit_confidence = "low" AND outcome = "offer" → disagreement = True`.

### 11.5 Dashboard Table: Context Column and Fit Columns

The dashboard `renderTable` function currently renders 7 columns. v1.3 adds the following:

| New column | Content | Condition |
|---|---|---|
| Context | Link to `/admin/context/{id}`. Label: "Edit Context" if `has_active_context = true`, "Add Context" if `false`. | Always shown |
| Assessment | `assessment_status` badge | Always shown |
| Fit | `fit_confidence` + `confidence_score` (e.g. "high (0.82)") | Only when status is `completed` or `weak_jd` |
| Priority | `priority` badge (HIGH / MEDIUM / LOW) | Only when status is `completed` or `weak_jd` |
| Disagreement | Boolean indicator (Yes / No) | Only when status is `completed` or `weak_jd` |

### 11.6 Dashboard Query Shape

The existing dashboard query in `tracking.py` (lines 611–627) is **replaced** by `repository.get_dashboard_fit_summary()`. The `tracking.py` route handler calls this function and receives the complete dataset. The old query is deleted.

```sql
SELECT
    a.id,
    a.company_name,
    a.person_name,
    a.position,
    a.date_applied,
    a.outcome,
    a.ref_code,
    a.followed_up,
    a.assessment_status,
    COUNT(v.id)           AS visit_count,
    MIN(v.timestamp)      AS first_visit,
    (SELECT fa.fit_confidence
     FROM fit_assessments fa
     WHERE fa.application_id = a.id
       AND fa.fit_confidence IS NOT NULL
     ORDER BY fa.created_at DESC, fa.id DESC
     LIMIT 1)             AS fit_confidence,
    (SELECT fa.confidence_score
     FROM fit_assessments fa
     WHERE fa.application_id = a.id
       AND fa.fit_confidence IS NOT NULL
     ORDER BY fa.created_at DESC, fa.id DESC
     LIMIT 1)             AS confidence_score,
    (SELECT fa.fit_score
     FROM fit_assessments fa
     WHERE fa.application_id = a.id
       AND fa.fit_confidence IS NOT NULL
     ORDER BY fa.created_at DESC, fa.id DESC
     LIMIT 1)             AS fit_score,
    (SELECT fa.signal_conflict
     FROM fit_assessments fa
     WHERE fa.application_id = a.id
       AND fa.fit_confidence IS NOT NULL
     ORDER BY fa.created_at DESC, fa.id DESC
     LIMIT 1)             AS signal_conflict,
    (SELECT fa2.failure_reason
     FROM fit_assessments fa2
     WHERE fa2.application_id = a.id
     ORDER BY fa2.created_at DESC, fa2.id DESC
     LIMIT 1)             AS failure_reason,
    EXISTS (
        SELECT 1
        FROM application_context ac
        WHERE ac.application_id = a.id
          AND ac.is_active = TRUE
    )                     AS has_active_context
FROM applications a
LEFT JOIN visits v ON a.ref_code = v.ref_code
GROUP BY a.id
ORDER BY a.date_applied DESC
```

### 11.7 Dashboard JS Functions Requiring Updates

`dashboard.html` is 1,075 lines of client-side JS. The following functions require changes in v1.3:

| Function | Change required |
|---|---|
| `renderTable` | Add Context, Assessment, Fit, Priority, Disagreement columns. Read `priority` and `disagreement` directly from the row object — they are pre-computed by the server and require no JS derivation. Render empty cell when value is `null`. |
| `updateStatCards` | No change required for v1.3. Fit metrics are table-level, not stat card level. |
| Filter bar | No new filters for v1.3. Assessment status and priority filters deferred to v1.4. |

---

## 12. Context Page

### 12.1 Route and Auth

Three new private routes, all requiring the existing admin cookie auth pattern:

```text
GET  /admin/context/{application_id}
POST /admin/context/{application_id}
POST /admin/assess-fit
```

Auth check uses the same `hmac.compare_digest(auth, SESSION_TOKEN)` pattern as all existing admin routes. On auth failure, redirect to `admin_login.html` with `redirect_to=/admin/context/{application_id}`.

**Router location:** These routes are added to `tracking.py` for v1.3, consistent with the existing pattern. `tracking.py` will reach approximately 900+ lines after v1.3. The `services/fit/` package already separates business logic from routing — extraction into `routers/fit.py` is deferred to v1.4 and will be clean when it happens.

### 12.2 Template

A new standalone template, `templates/context.html`, following the same standalone pattern as `admin.html` and `dashboard.html`. It does not extend `base.html`.

### 12.3 Page Content

The context page displays:

- **Application summary:** company name, position, date applied, current outcome
- **JD textarea:** pre-filled with active context's `jd_text` if an active context exists
- **Resume textarea:** pre-filled with active context's `resume_text` if an active context exists
- **Save Context button:** saves new context, deactivates old, resets `assessment_status` to `not_run`
- **Assess Fit button:** disabled when no active context exists (frontend guard; the backend handles this as a precondition failure regardless)
- **Assessment history table:** all `fit_assessments` rows for this `application_id`, regardless of `context_id`, ordered `created_at DESC, id DESC`

Assessment history table columns:

| Column | Notes |
|---|---|
| # | Row number derived in Python (1, 2, 3…). Do not display raw database `id` values — CockroachDB's `SERIAL` produces large non-sequential integers that are meaningless to users. |
| Attempt date | `created_at`, formatted as a readable date |
| fit_score | LLM qualitative score. Empty on failure rows. |
| fit_confidence | Deterministic label. Empty on failure rows. |
| confidence_score | Float formatted to 2 decimal places. Empty on failure rows. |
| signal_conflict | Rendered as Yes / No. Always No on failure rows. |
| failure_reason | Empty on successful rows. Failure code on failed rows. |

---

## 13. Fit Service Package

Create `services/fit/` as a new Python package. This is the first service layer in the codebase, separate from routers. It requires two empty init files: `services/__init__.py` and `services/fit/__init__.py`.

### 13.1 Modules

| Module | Owns |
|---|---|
| `vocabulary.py` | Canonical skill list, synonym map, `VOCAB_VERSION = "v1"` |
| `normalization.py` | Exact match, synonym resolution, fuzzy match at threshold 88, rejected term collection, deduplication |
| `jd_parser.py` | First LLM call — JD extraction, validation, weak JD evaluation |
| `matcher.py` | Second LLM call — matching, qualitative `fit_score`, validation, rejection (not clamping) |
| `scoring.py` | JD weights, deterministic score, confidence label, score validation, signal conflict |
| `repository.py` | All SQL for context and assessments, including the full dashboard query that replaces the existing one in `tracking.py` |

### 13.2 Repository Functions

```text
get_active_context(application_id)
deactivate_existing_context(application_id)
insert_context(application_id, jd_text, resume_text)
insert_assessment(...)
update_assessment_status(application_id, status)
get_latest_usable_assessment(application_id)
get_latest_attempt(application_id)
get_assessment_history(application_id)
get_dashboard_fit_summary()          ← replaces existing dashboard query in tracking.py
```

`get_dashboard_fit_summary()` returns the complete dataset for all applications including all fit fields. The `tracking.py` dashboard route calls this function, runs the server-side priority/disagreement derivation loop in Python, then serialises to `json_data`. The old inline query in `tracking.py` is deleted.

---

## 14. Implementation Order

| Step | Task | Files affected | Dependency |
|---|---|---|---|
| 1 | Create `services/` and `services/fit/` directories with empty `__init__.py` files | New directories | None |
| 2 | Add `rapidfuzz` to `requirements.txt`. Install locally and confirm the binary wheel builds correctly. `psycopg[binary]` already works on Vercel, so risk is low — but verify here rather than at deployment. | `requirements.txt` | None |
| 3 | Run CREATE TABLE for `application_context` and `fit_assessments`; create all indexes | Database schema | None |
| 4 | Run ALTER TABLE to add `assessment_status` to `applications` | Database schema | Step 3 |
| 5 | Write `vocabulary.py` — canonical list, synonym map, vocab version | `services/fit/vocabulary.py` | Step 1 |
| 6 | Write `normalization.py` — all three normalization layers | `services/fit/normalization.py` | Steps 1, 5 |
| 7 | Write `jd_parser.py` — first LLM call, validation, weak JD evaluation | `services/fit/jd_parser.py` | Steps 1, 6 |
| 8 | Write `matcher.py` — second LLM call, validation, rejection (not clamping) | `services/fit/matcher.py` | Steps 1, 6 |
| 9 | Write `scoring.py` — weights, deterministic score, confidence label, signal conflict | `services/fit/scoring.py` | Step 1 |
| 10 | Write `repository.py` — all SQL operations including the full dashboard query | `services/fit/repository.py` | Steps 3, 4 |
| 11 | Add context routes and `context.html` template | `routers/tracking.py`, `templates/context.html` | Steps 3, 4, 7, 8, 9, 10 |
| 12 | Replace existing dashboard query in `tracking.py` with call to `repository.get_dashboard_fit_summary()`. Add server-side priority/disagreement derivation loop. Add `followed_up` and all fit fields to `json_data`. Update `renderTable` and related JS in `dashboard.html` to add Context column and fit columns. | `routers/tracking.py`, `templates/dashboard.html` | Steps 10, 11 |
| 13 | Full local test via `uvicorn` | All routes | All steps |
| 14 | Deploy to Vercel and verify end to end | Live deployment | Step 13 |

---

## 15. Input Assumptions

- JD text is assumed to be under 3,000 words.
- Resume text is assumed to be under 1,500 words.
- Combined matcher input stays within Groq's 128K token context window for `llama-3.3-70b-versatile`. No truncation logic is implemented in v1.3.
- If inputs exceed these limits, the Groq API call will return an error, caught and recorded as `matcher_failed`. Truncation is deferred to v1.4.
- Manual resume paste is acceptable for v1.3.
- Assessment remains manually triggered.
- No background jobs are introduced.
- The vocabulary remains fixed at v1 during this release.
- Fuzzy matching threshold is fixed at 88.
- The outcome ENUM is not expanded in v1.3.

---

## 16. Test Plan

### 16.1 Unit Tests

- Vocabulary exact match returns canonical term.
- Synonym resolution maps variant to canonical correctly.
- Fuzzy match accepts valid variant at threshold 88.
- Fuzzy match rejects term below threshold.
- Rejected terms are collected and stored, not silently dropped.
- Empty JD classified as `jd_extraction_empty`, not `weak_jd`.
- Weak JD evaluated only after empty check passes.
- Must-have skills rejected by vocabulary treated as vocabulary limitation, not weak JD.
- Duplicate JD skills across categories keep highest weight.
- Matcher does not receive `jd_weights` in its input.
- `weighted_total_zero` aborts before division.
- Non-finite or out-of-bounds score becomes `score_invalid`.
- Confidence thresholds map correctly at boundaries (0.4 and 0.7).
- `signal_conflict` is FALSE when either value is NULL.
- `signal_conflict` is TRUE when `fit_score != fit_confidence` and both are non-NULL.
- Matcher returns `fit_score` outside `{high, medium, low}` → `matcher_invalid`, not clamped.
- Priority derivation: `followed_up = TRUE` suppresses HIGH priority even when confidence is high and viewed.
- Disagreement derivation: `pending` outcome always returns `False`.

### 16.2 Route and Persistence Tests

- Saving context deactivates old context.
- Saving context resets `assessment_status` to `not_run`.
- Partial unique index blocks two active contexts for same application.
- Assess Fit with no active context creates no `fit_assessments` row.
- Invalid JD parser output creates failed row with `jd_extraction_invalid`.
- Empty JD parser output creates failed row with `jd_extraction_empty`.
- Matcher timeout creates failed row with `matcher_failed`.
- Matcher invalid JSON creates failed row with `matcher_invalid`.
- Matcher `fit_score` outside allowed set creates failed row with `matcher_invalid`.
- Score validation failure creates failed row with `score_invalid`.
- Weak JD creates usable row and sets status to `weak_jd`.
- Successful assessment creates usable row and sets status to `completed`.
- Latest attempt ordering uses `created_at DESC, id DESC`.
- Latest usable ordering uses `created_at DESC, id DESC`.
- Assessment history on context page shows all rows regardless of `context_id`.
- Context page assessment history displays row numbers (1, 2, 3…), not raw database IDs.

### 16.3 Dashboard Tests

- Application with no context: "Add Context" link shown, no score, no priority, no disagreement.
- Application with active context: "Edit Context" link shown.
- Context saved, not assessed: `not_run` status, no score displayed.
- Completed assessment: score, priority, disagreement shown.
- Weak JD assessment: score shown with weak-JD warning.
- Failed latest attempt: failure reason shown, no score, no priority, no disagreement.
- Context replaced after completed assessment: score and priority cleared until re-assessed.
- Outcome update to `got_call` changes disagreement for low-confidence application on next dashboard load.
- New visit changes priority on next dashboard load.
- `not_run` and `failed` produce `priority = None` and `disagreement = None` — JS renders empty cells.
- Priority uses `fit_confidence`, not `fit_score`.
- Disagreement uses `fit_confidence`, not `fit_score`.
- Signal conflict displayed separately from disagreement.
- Dashboard renders without JS errors after new columns are added.

---

## 17. Acceptance Criteria

- Public portfolio behavior is unchanged.
- Existing v1.2 tracking continues to work without modification.
- Application context is versioned and historically preserved.
- Every real assessment attempt is recorded in `fit_assessments`.
- Precondition errors create no assessment rows.
- Dashboard never presents stale fit scores as current after context replacement.
- Dashboard table includes a Context column with "Add Context" or "Edit Context" links per application.
- Priority and disagreement are computed server-side and passed as pre-computed fields in `json_data`. The JS does not re-derive them.
- Priority and disagreement are derived from deterministic `fit_confidence`, not `fit_score`.
- Signal conflict is stored and displayed separately from disagreement.
- Fit data is not included in Groq intelligence summaries in v1.3.
- Latest-record selection is deterministic using `created_at DESC, id DESC` throughout.
- Matcher output with `fit_score` outside `{high, medium, low}` is rejected, not clamped.
- Temperature 0 is used for both LLM calls in the fit engine.
- Context page assessment history displays row numbers, not raw database IDs.
- The existing dashboard query in `tracking.py` is replaced by `repository.get_dashboard_fit_summary()`, not merged with it.
- The implementation is fully testable locally via `uvicorn` before Vercel deployment.

---

## 18. Deferred to v1.4

- **Expanding the outcome ENUM to include `offer`.** Requires `ALTER TYPE` on CockroachDB. When added, the disagreement rule extends to: `fit_confidence = "low" AND outcome = "offer" → disagreement = True`.
- **Extracting fit routes into `routers/fit.py`.** `tracking.py` reaches approximately 900+ lines after v1.3. The `services/fit/` package already separates business logic — the router extraction in v1.4 completes that separation cleanly.
- **Truncation logic** for JD or resume inputs exceeding word limits.
- **Automated assessment on context save.**
- **Groq intelligence summary integration** with fit data.
- **Dashboard filter bar extensions** for assessment status and priority.

---

## 19. Commit Plan

| Commit message | What it covers |
|---|---|
| `chore: add services/fit package structure` | Directory creation, `__init__.py` files, `rapidfuzz` in requirements |
| `feat: add application_context and fit_assessments tables` | CREATE TABLE statements, indexes, partial unique index |
| `feat: add assessment_status column to applications` | ALTER TABLE, default value |
| `feat: add vocabulary v1 and normalization pipeline` | `vocabulary.py`, `normalization.py` |
| `feat: add JD parser and matcher LLM calls` | `jd_parser.py`, `matcher.py` |
| `feat: add deterministic scoring and signal conflict` | `scoring.py` |
| `feat: add fit assessment repository` | `repository.py`, full dashboard query replacing existing |
| `feat: add context routes and template` | New routes in `tracking.py`, `templates/context.html` |
| `feat: extend dashboard with fit summary, priority, and context nav` | Dashboard query replacement in `tracking.py`, server-side priority/disagreement derivation, `dashboard.html` column updates including Context link |
| `docs: update CLAUDE.md for v1.3 completion` | Current task context updated, v1.4 deferrals noted |

---