# Algorithms

Every "intelligent" behaviour is deterministic and explainable: each result carries the reasons that produced it.
Code lives in `backend/app/intelligence/` (pure Python, plus scikit-learn behind one interface) and
`backend/app/domain/strategies/`. Only `text_similarity.py` imports scikit-learn.

| # | Feature | Code | Where it shows up |
|---|---|---|---|
| 0 | Priority calculation | `domain/strategies/priority.py` | every new / edited incident |
| 1 | Duplicate / related detection | `intelligence/duplicate_detector.py` | report form preview, on create, incident links |
| 2 | Smart technician recommendation | `intelligence/recommender.py` | incident page (staff) |
| 3 | SLA risk detection | `intelligence/sla_risk.py` | risk list on dashboards |
| 4 | Automatic escalation chain | `intelligence/escalation.py` + `services/escalation_service.py` | background monitor |
| 5 | Category suggestion | `intelligence/category_classifier.py` | report form, auto-fill when no category is chosen |
| + | Service correlation (innovation) | `intelligence/correlation.py` | dependency graph view |
| + | Suggested resolutions (spec G) | `intelligence/resolution_suggester.py` | incident page (staff); "Try this first" on the report form (self-service) |
| + | Recurring problem detection | `intelligence/recurring.py` | Service health page |
| + | Predicted resolution time | `intelligence/resolution_time.py` | incident page, Details card (everyone who can view it) |

---

## 0. Priority (Strategy: `PriorityCalculator` → `WeightedPriorityCalculator`)

```
base   = impact (1-4) x urgency (1-4) x business criticality of the service (1-4)      -> 1..64
factor = 1.0 if affected users <= 10, 1.25 if <= 100, else 1.5
score  = min(64, base x factor)
P1 >= 32 > P2 >= 16 > P3 >= 6 > P4
```

**Why:** it is the spec's formula, plus the spec's "number of affected users" factor, and the thresholds live in one place
(`PriorityThresholds`). A 64-point scale means P1 requires at least two "4"s, or "3"s plus many users.
Example: payment outage, I=4, U=4, C=4, 500 users → 64 → **P1**. A Wiki typo, I=1, U=1, C=1 → 1 → **P4**.
Changing impact/urgency later re-runs the calculator and rebases the SLA deadlines on the original creation time.

## 1. Duplicate / related incident detection

1. **Candidates:** not-closed incidents on the **same service**, created in the last **24 h** (repository query).
2. **Text:** `title. title. description` (the title counts twice because it is the densest signal).
3. **Similarity:** scikit-learn `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)` fitted on
   the new text plus the candidates, then `cosine_similarity`.
4. **Decision:** similarity ≥ **0.85** → `DUPLICATE`; ≥ **0.18** → `RELATED`; the top 5 are stored in `incident_links`,
   and the strongest duplicate becomes the incident's parent. A `RELATED_DETECTED` audit entry lists them.
5. **Blocking rule:** only a `DUPLICATE` from the **same reporter within 30 min** (an accidental double submit) is
   rejected with `DuplicateIncidentError` (HTTP 409, with the matching incident numbers). Resubmitting with `force=true`
   creates it anyway. Reports from other people are linked, never blocked.

**Calibration (why character n-grams and why 0.18).** On the spec's own example:

| Query: "Payment application unavailable…" vs | word TF-IDF | char 3-5 TF-IDF |
|---|---|---|
| "Payment transaction failing…" (related) | 0.05 | **0.23–0.25** |
| "Unable to make payment…" (related) | 0.09 | **0.22–0.24** |
| "Payments portal down - cannot pay" (related) | – | **0.34** |
| "Payment application is unavailable, users cannot…" (duplicate) | 1.00 | **0.93** |
| Unrelated tickets on the same service (refund CSV, GST invoice, access request) | 0.00 | **0.00–0.04** |
| Unrelated tickets on other services (VPN, printer) | 0.00 | **0.02–0.04** |

Word-level TF-IDF misses "payment"/"payments"/"pay", which short incident titles depend on. Character n-grams
separate related reports (≥ 0.19) from unrelated ones (≤ 0.04), so 0.18 sits in the gap. In the seed data the system
links exactly the spec's three payment reports plus a true duplicate (0.91).

## 2. Smart technician recommendation

For each active technician (except the current assignee):

| Factor | Value in [0,1] | Weight (P3/P4) | Weight (P1/P2) |
|---|---|---|---|
| Skill matches incident category | 1 or 0 | 0.40 | 0.40 |
| Free capacity | 1 − active / max workload | 0.25 | 0.15 |
| Experience | min(years, 15) / 15 | 0.15 | 0.25 |
| History on this service | min(resolved incidents here, 5) / 5 | 0.15 | 0.15 |
| Available and under the cap | 1 or 0 | 0.05 | 0.05 |

`score = 100 x Σ weight x value`. The top 3 are returned with a per-factor breakdown and readable reasons
("has NETWORK skill · 1/8 active incidents · 10 yrs experience · resolved 4 incident(s) on this service").
Ineligible technicians are listed last and flagged. Critical incidents shift weight from load-spreading to experience.
The **assignment strategies** (Skill / Load / Round-robin / Experience) *decide*; the recommender *explains* and supports
an administrator's manual choice.

## 3. SLA risk detection

For every open, non-paused incident with an SLA, using the target currently running (response until acknowledged,
then resolution):

```
score = min(elapsed %, 150) x priority weight (P1 1.3, P2 1.15, P3 1.0, P4 0.9)
        + 15 if no technician is assigned
        + 10 if still unacknowledged after half of the response window
level = BREACHED if the deadline has passed, HIGH if score >= 90, MEDIUM if >= 60, else LOW
```

The list is sorted by level, then score, and each entry has reasons and minutes left. Paused clocks (`PENDING_INFO`)
are not at risk. The 150 % cap keeps very late incidents comparable instead of producing scores in the thousands.

## 4. Automatic escalation chain

Applies to **unacknowledged** (CLASSIFIED or ASSIGNED) incidents of the configured priorities: P1 always, P2 when an
administrator enables it.

```
overdue = now - response deadline          (nothing happens until it is strictly positive)
level   = min(4, 1 + floor(overdue / response window))
          1 Technician -> 2 Team Lead -> 3 System Administrator -> 4 IT Manager
```

For a P1 with a 5-minute response target, the levels fire at due + 0, +5, +10 and +15 minutes. The background monitor
(every 60 s) walks the chain **one level at a time**, so each level is audited and notified (in-app, e-mail, SMS),
even if the monitor was down for a while. Recipients:

1. the assigned technician (system administrators if nobody is assigned);
2. team leads of the assignee's team (any team lead if there is none);
3. administrators with level `SYSTEM_ADMIN`;
4. administrators with level `IT_MANAGER`.

Acknowledging stops the chain.

## 5. Category suggestion

```
hits          = occurrences of the category's keywords in "title. title. description" (prefix match, so
                "printers" matches "printer"); title words therefore count twice
keyword score = hits / (hits + 1)            1 -> 0.50, 2 -> 0.67, 3 -> 0.75  (saturating)
history score = char TF-IDF cosine similarity between the text and one document per category
                (its keywords + up to 30 most recent resolved incidents in that category)
confidence    = 0.6 x keyword score + 0.4 x history score;  shown if >= 0.12; top 3 returned
```

Keywords are data in the `categories` table, so a category an administrator adds (e.g. PRINTING: "toner",
"print queue") is suggested immediately, and suggestions improve as resolved history accumulates. If the reporter picks a
category it always wins: the audit entry notes "reporter chose it over suggested X". If they pick none, the top suggestion
is used ("auto-suggested, confidence 0.58"). If nothing scores ≥ 0.12, the reporter is asked to choose.

**Measured on the seed data:** the suggestion equals the final category for **39 of 43** incidents (91 %). The four misses
are genuinely ambiguous (e.g. "API gateway returning 502 errors": application or cloud?).

## Innovation: service dependency correlation

Services declare `depends_on` (a directed graph, kept acyclic by a depth-first search when an administrator edits it).
Over incidents still open:

- **Hotspot:** a service with ≥ 3 incidents reported in the last 2 h → "likely one underlying problem".
- **Upstream cause:** a service with recent incidents that depends on a service which *also* has recent incidents →
  the upstream service is flagged as the likely common cause (e.g. Payments → API Gateway).
- Node health: HOTSPOT / DEGRADED (any open incident) / HEALTHY, plus edges for the graph view.

## Recurring problem detection

The spec lists "difficulty identifying recurring problems" as a challenge. Duplicate detection and the hotspot look at
the last 24 h / 2 h, so they catch a **burst**. This feature catches a problem that **keeps coming back** after being fixed.

```
window      = incidents (any status) created in the last 30 days, grouped per service
same issue  = TF-IDF similarity (same char n-grams as feature 1) >= 0.25 between two incidents
groups      = connected components of "same issue" (single-link, computed with union-find),
              so A~B and B~C put A, B and C in one group
recurring   = group of >= 3 incidents whose first and last are >= 24 h apart
sorted by   = still-open incidents, then occurrences, then most recent
```

Each result shows the service, the latest title, how many times it happened and how many are still open, the date
range, the **latest fix** and a reason, e.g. "3 similar incidents on Corporate VPN within 12 day(s); it was fixed before
but came back (1 still open)".

**Calibration on the seed data:** at 0.20 three different database problems (connections, replication lag,
deadlocks) were wrongly grouped; at 0.35 the real VPN drop-outs were missed; 0.25 and 0.30 find exactly the VPN
problem and leave the unrelated "VPN client update fails" out. Without the 24 h rule, today's payment outage (4 reports in
minutes) would also show, but that is a burst the hotspot already reports.
**Cost:** one TF-IDF fit per incident within a service (O(n²) comparisons per service), which is fine for 30 days of
one service's incidents; at much larger volumes it would run as a nightly batch job instead.

## Suggested resolutions (spec feature G)

The same TF-IDF similarity is used against **resolved** incidents that have a resolution summary. Matches with similarity
≥ 0.15 are shown (top 3), together with the fix that worked.

**Self-service (deflection).** The same search runs on the text an employee is still typing in the report form
(`POST /api/intelligence/self-help`, debounced). The "Try this first" card shows the past title, the fix and the similarity,
so the employee can solve it without submitting. Incident ids and numbers are left out because employees cannot open
other people's incidents. Example: typing "VPN keeps disconnecting" shows "Replaced a flapping uplink on the access
switch…" at 59 %.

## Predicted resolution time

```
working time = resolved_at - created_at - time paused in PENDING_INFO      (waiting on the reporter is not work)
basis        = resolved incidents with the same priority AND category       if there are >= 3
               else resolved incidents with the same priority               if there are >= 3
               else no estimate
estimate     = median working time of the basis
expected by  = created_at + estimate + completed pauses                      (open incidents only)
```

**Why the median:** a few very late incidents (the seed has deliberate SLA violations) would pull an average far up; the
median is the "usual" case and is easy to explain. **Why 3 samples:** below that, one incident would be presented as a
trend. Shown on the incident page as "Typical time to resolve ~1.4 h · expected around 14:05", with the reason
("median of 5 resolved P2 incidents"). If an open incident is already past the expected time, the page says "taking
longer than usual" instead. While it is waiting on the reporter, no expected time is shown, because the clock is paused.
It complements the SLA, which says what was promised; the estimate says what usually happens.
