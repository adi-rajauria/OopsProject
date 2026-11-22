# Demo video script (15-20 minutes, one take)

**File name:** `[Group No.]_OOP_S1_2025-2026_Project` · **Speakers:** Member 1, Member 2, Member 3
(replace with names). Each member introduces themselves and explains their module (a spec requirement).

All accounts use the password **`Demo@1234`**.

---

## Before recording

### Same day (any time)

- [ ] Backend running (`.\run_backend.ps1`) and frontend running (`.\run_frontend.ps1`). Check <http://127.0.0.1:5173>.
- [ ] Use **Chrome or Edge**. Test voice once on the report form. If it fails on this network, use a phone hotspot or
      skip the voice steps (marked 🎤).
- [ ] Screen recorder ready (OBS, Xbox Game Bar `Win + Alt + R`, or Teams / Zoom recording), microphone checked,
      notifications on the computer muted, browser zoom 110-125 % so text is readable.
- [ ] Open in an editor (for the short code moments): `backend/app/domain/lifecycle.py`,
      `backend/app/domain/strategies/assignment.py`, `backend/app/domain/events.py`.

### Countdown (the seed is time-relative, so do this right before recording)

| When | Do |
|---|---|
| **T − 3 min** | `cd backend` then `.\.venv\Scripts\python.exe -m scripts.seed --reset` |
| **T − 2 min** | Sign in, one role per window (normal window, private window, second browser): **Window A** `abhinandan@decerno.demo` (Dashboard) · **Window B** `arjun@decerno.demo` (My queue) · **Window C** `isha@decerno.demo` (My incidents) |
| **T − 0** | Start recording. Start on **Window A**. |

**Why the order below matters:** P1 escalations at three different levels are only visible for about 5 minutes after
seeding, the upstream-cause finding for about 24 minutes, and the payment hotspot for about 36 minutes. So the
dashboard comes first.

**If the take goes wrong:** stop, reseed, sign in again in the three windows, restart (about 3 minutes).

---

## Part 1: Member 1, overview and the live dashboard (0:00-5:00)

**[0:00] Window A, Operations dashboard**

> "Hello, I am **[Member 1]**, and I worked on **[module, e.g. the frontend and the role interfaces]**. This is
> **Decerno** (say *deh-CHAIR-no*), our Intelligent IT Service Management system. The name is Latin for 'I decide, I
> settle', because the system decides priority, deadlines and who handles each incident, and helps settle it. It manages the full incident lifecycle: report, classify, prioritise,
> assign, investigate, resolve, verify and close. It is a React and TypeScript frontend on a Python FastAPI backend with
> PostgreSQL, built around a pure object-oriented domain model. Each role gets its own interface: this is the
> administrator's."

**[0:40] Operations → Incidents, filter Priority = P1, open only** (do this first: it is the most time-sensitive)

- "These critical incidents were not acknowledged in time, so the system **escalated** them automatically: Technician,
  then Team Lead, then System Administrator, then IT Manager." Point at the **escalation badges**: three different
  levels. Open one and show the escalation entries in its **History**.

**[1:30] Back to the Dashboard, top to bottom:**

1. **Likely to breach:** "This is **SLA risk detection**: each incident gets a risk score from how much of its SLA has
   been used, its priority, and whether it is unassigned or unacknowledged. The *Why* column gives the reasons."
2. **Waiting for a technician:** an incident nobody could take (no available technician with the skill, the
   "technician unavailable" exception), waiting for an admin.
3. **Live activity** panel: "Updates arrive in real time through Server-Sent Events, with no refresh."
4. **Overview numbers:** total, open, critical, resolved, SLA violations, mean time to resolve, average rating ("the
   spec's incident overview").
5. **Charts:** created vs resolved over 14 days; open incidents by priority and by status.

**[2:45] Services (Reports → Services): Service health & correlation**

> "This is the **service dependency graph**. Payments depends on API Gateway, which depends on the campus network. Red
> means a **hotspot**: three or more incidents on one service in two hours, so probably one underlying problem. The
> findings below also point at an **upstream cause**: a service Payments depends on also has recent incidents."

- Scroll to **Recurring problems**: "Here the system found the VPN dropping out three times over twelve days. That is a
  candidate for root-cause analysis, not just another ticket. The last fix is shown."

**[3:30] Workload**, then **SLA**

- Workload: "Active incidents per technician, the spec's workload report."
- SLA: compliance per priority, violation list. Click **Download CSV**: "Any list can be exported. Cells are escaped so
  a malicious title cannot run as a spreadsheet formula."

**[4:30] Hand-over**

> "Now **[Member 2]** will show what happens when an employee reports a problem."

---

## Part 2: Member 2, Workflow 1 and Workflow 2 (5:00-12:00)

> "I am **[Member 2]**, and I worked on **[module, e.g. the domain model, the lifecycle and the backend services]**."

### Workflow 1: employee reports → system prioritises → technician assigned → notification

**[5:15] Window C (Isha, employee) → Report an incident**

1. Service: **Payments Platform**.
2. 🎤 Click **Speak instead** and say: *"Unable to make payment. I am unable to make a payment, the payment page shows
   an error and all customers cannot pay."* (Or type it.)
3. While it fills in, point at the live panels:
   - **Category suggestion** ("Application"), with **Use it**: "Suggested from keywords and similar past incidents."
   - **Impact / urgency hints** under the two scales: "It noticed 'all customers' and 'cannot pay'." Click **Use it**
     on both (impact 4, urgency 4).
   - **Is it already reported?** shows the open payment incidents: "**Duplicate detection** with TF-IDF similarity, so
     the employee sees the outage is already known."
   - **Try this first** shows fixes that worked for similar resolved incidents.
4. "Roughly how many people are affected?": **200**. Click **Submit incident**.

**[6:45] The new incident page**

> "The system has classified it, calculated the priority, attached the SLA and assigned a technician, all in one step."

- **Priority P1** with the formula: "Impact 4 × urgency 4 × business criticality 4 of the payment service, times a
  factor for 200 affected users, capped at 64. 32 or more is P1."
- **SLA:** response due in 5 minutes, resolution in 30, the spec's table.
- **Assigned to** Arjun: "chosen by the active **assignment strategy**".
- **Related incidents** linked automatically.
- **History (audit trail):** created, classified, priority calculated, assigned, with time, user and states.

**[7:30] Window B (Arjun, technician)**

- The **notification bell** shows the new assignment (it arrived live). Open **Notifications**: "In-app, plus simulated
  e-mail and, for P1, SMS. Channels are chosen per event."
- *(If the incident went to someone else, go to Window A, open it, and use **Assign / reassign** with **Recommended
  technicians** to give it to Arjun. Point at the reasons: skill, workload, experience, ratings.)*

### Workflow 2: technician investigates → SLA monitored → resolved → user notified

**[8:00] Window B, open the incident from My queue**

1. Click **Acknowledge**: "The response SLA is met; escalation stops."
2. Click **Start work**.
3. 🎤 Add an **internal note** with **Dictate**: *"Gateway logs show TLS handshake errors."* Point out it is marked
   "Internal note, staff only": the employee will not see it.
4. Click **Request more info** and ask: *"Which browser are you using, and when did it start?"*
   > "The incident is now **Pending info**, and the **SLA clock pauses**, because we are waiting for the reporter."

**[9:15] Window C (Isha):** a banner says "The technician needs more information from you". Click
**Answer the question**: *"Chrome, since about ten o'clock."* Point out the internal note is not visible here.

**[9:45] Window B:** the reply appears live and the clock resumes.

- Point at **Fixes that worked before** (suggested resolutions) and the **typical time to resolve** estimate.
- Click **Resolve** with: *"Renewed the expired TLS certificate on the payment gateway."*

**[10:30] Window C:** "This incident was resolved" notice. Click **Confirm it's fixed**, give **5 stars** and a
comment. "Feedback is stored, and ratings feed back into technician recommendations."

**[11:00] Window B or A:** click **Close incident**. Show the full **History** from created to closed.

**[11:20] Code moment (about 40 s, editor): `backend/app/domain/lifecycle.py`**

> "This is the **State pattern**. Each state class only overrides the transitions it allows. Everything else falls
> through to the base class, which raises `InvalidStateTransitionError`. So NEW → CLOSED is impossible: there is no code
> path for it, and a test checks every state against every action."

**[11:50] Hand-over**

> "**[Member 3]** will now show what happens when many people report the same problem."

---

## Part 3: Member 3, Workflow 3, administration and quality (12:00-18:30)

> "I am **[Member 3]**, and I worked on **[module, e.g. the intelligent features, the database and testing]**."

### Workflow 3: multiple reports → duplicates / related → correlated / escalated

**[12:15] Window C: sign out, sign in as `neha@decerno.demo`, Report an incident**

- Payments Platform, title **"Payment application unavailable"**, description *"The payment application is
  unavailable, customers cannot pay."*, impact 4, urgency 4, 200 users.
- Before submitting, point at **Is it already reported?**: a very similar incident is listed. Submit.
- On the incident page, **Related incidents** shows a **DUPLICATE** link: "Similarity above 0.85 is a duplicate. The
  new incident is linked to the original as its parent, so the team works on one problem."

**[13:15] Sign out, sign in as `zoya@decerno.demo`, report "Payment transaction failing"**

- Description *"Every payment transaction is failing at the last step."* Submit **without a category**.
- The form says **"Could not suggest a category from the description; please choose one"**: "That is the
  invalid-incident exception handled properly." Pick **Application** and submit. It is linked as **RELATED**.
- *(Optional: show the double-submit rule: click submit twice on the same text. The second one is blocked with "A very
  similar incident was reported by you recently", and the reporter can still force it.)*

**[14:15] Window A, Services:** the Payments hotspot count has gone up: "These reports are **correlated** with the
service and its dependencies." Back on the **Dashboard**, the new P1s appear under **Likely to breach**. If they are
left unacknowledged they will **escalate** like the ones we saw at the start (**Run SLA check now** runs the monitor
immediately instead of waiting for the 60-second cycle).

### Administration (spec: configure strategies, SLA, categories, users, audit)

**[15:00] Configuration**

1. **Assignment & escalation:** switch the strategy (Skill-based → Load-based). "This is the **Strategy pattern**:
   four interchangeable classes, switched at runtime with no restart. Every change is audited." Optionally enable P2
   escalation.
2. **Categories:** "A new category is just data: its keywords are used for suggestions immediately, with no code
   change." (Optionally add PRINTING with keywords *toner, print queue*.)
3. **SLA policies:** the default table and service-specific overrides.

**[16:00] Users:** technicians with skills, team, workload cap and availability.

**[16:20] Audit log:** filter by an incident; show the **Notification deliveries** tab (in-app, e-mail, SMS, and
delivery failures).

**[16:45] Incidents (search):** combine filters (status, priority P1, service Payments, SLA status) and show that the URL
is bookmarkable; **Download CSV**.

**[17:15] Code moment (about 40 s): `strategies/assignment.py` and `events.py`**

> "Each assignment strategy registers itself with a decorator, so a new strategy is one new class. The service only
> knows the abstract `AssignmentStrategy`. And incidents never call the audit or notification code directly: they
> raise **domain events**, and **observers** (audit logger, notification dispatcher, SLA tracker, live forwarder) react.
> That is the **Observer pattern**. We used seven patterns in total: Strategy, State, Observer, Factory, Repository with
> Unit of Work, Adapter for the e-mail and SMS providers, and Template Method."

**[17:55] Testing (terminal or GitHub Actions page)**

> "We have **171 automated tests**: unit tests for the domain, service tests with in-memory repositories, and API tests.
> GitHub Actions runs them on every push, on both SQLite and PostgreSQL, and also builds the frontend."

(Optional: run `.\.venv\Scripts\python.exe -m pytest -q` in `backend` before recording and show the result, since it
takes about 20 seconds.)

**[18:20] Close**

> "To sum up: Decerno covers every MVP requirement, adds thirteen explainable intelligent features, real-time
> dashboards, a dependency graph and voice reporting, and the object-oriented design kept all of it easy to change.
> Thank you."

Stop recording.

---

## Backup plan

| Problem | Do |
|---|---|
| Voice does not work | Type the text. Say "voice input uses the browser's speech service; this network blocks it". |
| The new incident is assigned to someone other than Arjun | Window A: open it, **Assign / reassign** to Arjun using **Recommended technicians** (this is also a feature to show) |
| A step shows an error | Read the message out: it is usually an exception case working as designed (for example, an illegal action) |
| Something breaks badly | Stop, reseed, sign in again, restart |
| Over 20 minutes | Skip the optional parts and the second code moment |

## Checklist: what the video must show (from the spec)

- [ ] Each member introduces themselves and explains a module
- [ ] Workflow 1: employee reports → prioritised → technician assigned → notification
- [ ] Workflow 2: technician investigates → SLA monitored (pause / resume) → resolved → user notified
- [ ] Workflow 3: multiple reports → duplicate / related → correlated / escalated
- [ ] Three different role interfaces
- [ ] Intelligent features: priority, duplicates, correlation, escalation, recommendation, SLA risk, category suggestion, suggested resolutions
- [ ] Innovation: voice reporting, real-time dashboard, dependency graph
- [ ] Length 15-20 minutes
