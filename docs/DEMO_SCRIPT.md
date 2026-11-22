# Demo video script (15-20 minutes, one take)

**File name:** `[Group No.]_OOP_S1_2025-2026_Project` · **Speakers:** Abhinandan Chandak (Part 1), Adi Rajauria (Part 2), Shrey Bhasker (Part 3). Each member introduces themselves and explains their module (a spec requirement).

All accounts use the password **`Demo@1234`**. Steps marked 🎤 use voice; type instead if voice does not work.

**How to read the tables:** the left column is what to do on screen, the right column is what to say while doing it.
Times are targets, not limits.

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
- [ ] In Window A, keep a second tab open on the API documentation: <http://127.0.0.1:8000/docs>.
- [ ] Refresh every window once with **Ctrl + F5**, so the browser has the latest version (Domine font, new logo).

### Countdown (the seed is time-relative, so do this right before recording)

| When | Do |
|---|---|
| **T − 3 min** | `cd backend` then `.\.venv\Scripts\python.exe -m scripts.seed --reset` |
| **T − 2 min** | Sign in, one role per window (normal window, private window, second browser): **Window A** `abhinandan@decerno.demo` (Dashboard) · **Window B** `arjun@decerno.demo` (My queue) · **Window C** `adi@decerno.demo` (My incidents) |
| **T − 0** | Start recording. Start on **Window A**. |

**Why the order below matters:** P1 escalations at three different levels are only visible for about 5 minutes after
seeding, the upstream-cause finding for about 24 minutes, and the payment hotspot for about 36 minutes. So the
dashboard comes first.

**If the take goes wrong:** stop, reseed, sign in again in the three windows, restart (about 3 minutes).

---

## Part 1: Abhinandan, overview and the live dashboard (0:00-5:00)

| Do | Say |
|---|---|
| **0:00** Window A, **Operations dashboard**. | "Hello, I am **Abhinandan Chandak**, and I worked on **[module, e.g. the frontend and the role interfaces]**. This is **Decerno** (*deh-CHAIR-no*), our Intelligent IT Service Management system. The name is Latin for 'I decide, I settle', because the system decides priority, deadlines and who handles each incident, and helps settle it; the logo is a D holding a tick for the same reason." |
| Stay on the dashboard. | "It manages the full incident lifecycle: report, classify, prioritise, assign, investigate, resolve, verify and close. It is a React and TypeScript frontend on a Python FastAPI backend with PostgreSQL, built around a pure object-oriented domain model. Each role gets its own interface: this is the administrator's." |
| **0:40** **Incidents** → filter **Priority = P1**, **open only**. Point at the **escalation badges** (three different levels). *(Do this first: it is the most time-sensitive.)* | "These critical incidents were not acknowledged in time, so the system **escalated** them automatically: Technician, then Team Lead, then System Administrator, then IT Manager. You can see three different levels here." |
| Open one of them; scroll to **History**. | "Each escalation is in the audit trail, and each level was notified in the app, by e-mail and by SMS." |
| **1:30** Back to the **Dashboard**. Point at **Likely to breach**. | "This is **SLA risk detection**. Each incident gets a risk score from how much of its SLA has been used, its priority, and whether it is unassigned or unacknowledged. The *Why* column gives the reasons." |
| Point at **Waiting for a technician**. | "This one could not be assigned: no available technician had the skill. That is the 'technician unavailable' case, so it waits here for an administrator." |
| Point at **Live activity**. | "Updates arrive in real time through Server-Sent Events, with no refresh." |
| Point at the **overview numbers**, then the **charts**. | "This is the incident overview from the spec: total, open, critical, resolved, SLA violations, mean time to resolve and the average rating. Below, created versus resolved over two weeks, and open incidents by priority and status." |
| **2:45** **Reports → Services** (Service health). Point at the red box and the **Likely common causes** list. | "This is the **service dependency graph**. Payments depends on the API Gateway, which depends on the campus network. Red means a **hotspot**: three or more incidents on one service within two hours, so probably one underlying problem. The findings also point at an **upstream cause**: a service that Payments depends on also has recent incidents." |
| Scroll to **Recurring problems**. | "Here the system noticed the VPN dropping out three times in twelve days. That is a candidate for root-cause analysis, not just another ticket, and the last fix is shown." |
| **3:30** **Workload**. | "Active incidents per technician: the spec's workload report." |
| **SLA** → click **Download CSV**. | "Compliance per priority and every violation. Any list can be exported to CSV, and cells are escaped so a malicious title cannot run as a spreadsheet formula." |
| **4:30** Hand over. | "Now **Adi** will show what happens when an employee reports a problem." |

---

## Part 2: Adi, Workflow 1 and Workflow 2 (5:00-12:00)

### Workflow 1: employee reports → system prioritises → technician assigned → notification

| Do | Say |
|---|---|
| **5:00** Switch to **Window C** (Adi, employee). | "I am **Adi Rajauria**, and I worked on **[module, e.g. the domain model, the lifecycle and the backend services]**. I am signed in to the employee's self-service portal with my own demo account: Adi Rajauria, Finance." |
| **5:15** **Report an incident**. Choose service **Payments Platform**. | "I cannot make a payment, so I report it." |
| 🎤 Click **Speak instead** and say the report: *"Unable to make payment. I am unable to make a payment, the payment page shows an error and all customers cannot pay."* | *(Speaking the report is the step itself.)* Then: "Reports can be typed or spoken." |
| Point at the **category suggestion** and its **Use it** link. | "While I type, Decerno suggests the category, here Application, from keywords and similar past incidents." |
| Point at the hints under **Who is affected** and **How urgent**; click **Use it** on both (impact 4, urgency 4). | "It also noticed 'all customers' and 'cannot pay', so it suggests the highest impact and urgency, and shows the phrase it reacted to." |
| Point at **Is it already reported?** | "This is **duplicate detection** with TF-IDF text similarity: the employee can see the payment outage is already known." |
| Point at **Try this first**. | "And these are fixes that worked for similar problems before. Sometimes the employee can solve it without a ticket." |
| Set "Roughly how many people are affected?" to **200**. Click **Submit incident**. | "Two hundred people are affected. Let's submit." |
| **6:45** The new incident page. Point at the header (number, **P1 · Critical**, status, assignee). | "In one step the system has classified it, calculated the priority, attached the SLA and assigned a technician. The number is **DCN-10xx**, Decerno's own numbering." |
| Point at **Priority score** in **Details**. | "Priority is impact 4 times urgency 4 times the payment service's business criticality 4, times a factor for 200 affected users, capped at 64. Anything from 32 up is P1." |
| Point at the **Service level** panel. | "Payments has its own stricter P1 policy: respond within 3 minutes, resolve within 20. Other services use the spec's table, 5 and 30 minutes." |
| Point at **Related incidents**. | "The similar reports were linked automatically." |
| Scroll to **Why Decerno decided**. | "This card is what the name means. Every decision the system made is listed with its reason: the category, the priority formula, which SLA applies, why this technician was chosen, which reports were linked and why. Nothing is a black box." |
| Scroll to **History (audit trail)**. | "And everything is in the audit trail: created, classified, priority calculated, assigned, each with the time, the user and the state before and after." |
| **7:30** Switch to **Window B** (Arjun, technician). Point at the **bell**, then open **Notifications**. | "Arjun got the assignment instantly: in the app, plus a simulated e-mail and, because it is P1, an SMS. The channels are chosen per event." |
| *(Only if the incident went to someone else: Window A, open it, **Assign / reassign**, pick Arjun from **Recommended technicians**.)* | *(If needed:)* "An administrator can reassign it. The recommendations explain themselves: skill, workload, experience and ratings." |

### Workflow 2: technician investigates → SLA monitored → resolved → user notified

| Do | Say |
|---|---|
| **8:00** Window B: open the incident from **My queue**. Click **Acknowledge**. | "Arjun acknowledges it. The response SLA is met, and the escalation chain stops." |
| Click **Start work**. | "Now the investigation starts." |
| 🎤 In the conversation box, click **Dictate**: *"Gateway logs show TLS handshake errors."* Tick **Internal note**, click **Post**. | "Arjun adds an investigation note by voice. It is internal, so the employee will not see it." |
| Click **Request more info**: *"Which browser are you using, and when did it start?"* | "Arjun needs more information. The incident moves to **Pending info**, and the **SLA clock pauses**, because we are now waiting for the reporter, not for IT." |
| **9:15** Switch to **Window C** (Adi). Point at the yellow banner. | "As the employee, I can see the technician needs more information. Notice the internal note is not shown to me." |
| Click **Answer the question**: *"Chrome, since about ten o'clock."* | "I answer, and the clock starts again." |
| **9:45** Switch to **Window B**. Point at the reply. | "The reply appears live." |
| Point at **Fixes that worked before** and **Typical time to resolve**. | "Decerno suggests fixes from similar resolved incidents, and predicts how long this kind of incident usually takes." |
| Click **Resolve**: *"Renewed the expired TLS certificate on the payment gateway."* | "Arjun resolves it with a summary." |
| **10:30** Switch to **Window C**. Click **Confirm it's fixed**, give **5 stars** and a comment. | "I confirm it is fixed and rate it. Ratings feed back into technician recommendations." |
| **11:00** Window B: **Close incident**. Scroll through the **History**. | "Now it can be closed. The history shows the complete lifecycle, from created to closed." |
| **11:20** Editor: `backend/app/domain/lifecycle.py`. | "This is the **State pattern**. Each state class only overrides the transitions it allows. Everything else falls through to the base class, which raises `InvalidStateTransitionError`. So NEW to CLOSED is impossible: there is no code path for it, and a test checks every state against every action." |
| **11:50** Hand over. | "**Shrey** will now show what happens when many people report the same problem." |

---

## Part 3: Shrey, Workflow 3, administration and quality (12:00-19:00)

### Workflow 3: multiple reports → duplicates / related → correlated / escalated

| Do | Say |
|---|---|
| **12:00** Window C: **Sign out**. The sign-in page appears; point at the left panel and the demo accounts. | "I am **Shrey Bhasker**, and I worked on **[module, e.g. the intelligent features, the database and testing]**. This is the sign-in page, with the meaning of the name and one-click demo accounts for each role." |
| Sign in as `neha@decerno.demo` → **Report an incident**: Payments Platform, title **"Payment application unavailable"**, description *"The payment application is unavailable, customers cannot pay."*, impact 4, urgency 4, 200 users. | "Now a second employee, Neha, reports the same outage in different words." |
| Before submitting, point at **Is it already reported?** Then **Submit incident**. | "Neha can already see a very similar incident." |
| On the new incident, point at **Related incidents** (**duplicate**). | "Above 85 % similarity it is a **duplicate**: it is linked to the original as its parent, so the team works on one problem instead of two. Other people's reports are never blocked, only linked." |
| **13:15** Sign out, sign in as `zoya@decerno.demo`. Report **"Payment transaction failing"**, description *"Every payment transaction is failing at the last step."* Leave the category empty and submit. | "A third report, worded differently, and without a category." |
| Point at the message on the **Category** field: "Could not suggest a category…". Choose **Application**, submit. Point at the **related** link. | "Here the text was not clear enough to guess a category, so the system asks instead of guessing. That is the invalid-incident case handled properly. Once submitted, it is linked as **related**." |
| *(Optional: submit the same text again.)* | *(Optional:)* "The same person submitting the same report twice within 30 minutes is blocked as an accidental double submit, though the reporter can still force it." |
| **14:15** Window A: **Services**. Point at the Payments hotspot count. | "All these reports are **correlated** with the service and its dependencies: the Payments hotspot has grown." |
| **Dashboard** → click **Run SLA check now**. | "The new P1s are already in the at-risk list. If nobody acknowledges them, they will escalate like the ones we saw at the start. The monitor runs every 60 seconds; this button runs it now." |

### Administration and technical depth

| Do | Say |
|---|---|
| **15:00** **Configuration** → **Assignment & escalation**: switch **Skill-based → Load-based**. | "Administrators configure everything here. The assignment strategy is the **Strategy pattern**: four interchangeable classes, switched at runtime with no restart, and every change is audited." |
| *(Optional: enable P2 escalation.)* | *(Optional:)* "Escalation can also be turned on for P2 incidents." |
| **Categories** tab. *(Optional: add PRINTING with keywords "toner, print queue".)* | "A new category is just data. Its keywords are used for suggestions immediately, with no code change." |
| **SLA policies** tab. | "The default SLA table from the spec, plus service-specific overrides like the stricter one for Payments." |
| **16:00** **Users**. | "Users and technicians: skills, team, workload cap and availability." |
| **16:20** **Audit log**: filter by an incident; open the **Notification deliveries** tab. | "Every action is recorded, and so is every notification on every channel, including failed deliveries." |
| **16:45** **Incidents**: combine filters (status, priority P1, service Payments, SLA status). Click **Download CSV**. | "Search combines eleven criteria, the URL can be bookmarked, and the results export to CSV." |
| **17:15** Editor: `strategies/assignment.py`, then `events.py`. | "Each assignment strategy registers itself with a decorator, so a new strategy is one new class; the service only knows the abstract `AssignmentStrategy`. And incidents never call the audit or notification code directly: they raise **domain events**, and **observers** react: the audit logger, the notification dispatcher, the SLA tracker and the live forwarder. That is the **Observer pattern**. We used seven patterns in total: Strategy, State, Observer, Factory, Repository with Unit of Work, Adapter for the e-mail and SMS providers, and Template Method." |
| **17:55** Window A, the **`/docs`** tab (Swagger). | "The backend is a documented REST API: 73 operations, generated automatically as this page. Lifecycle actions are explicit, like `POST /incidents/{id}/acknowledge`, so every transition is checked and audited, and every endpoint is protected by role." |
| **18:25** Terminal with the test result, or the GitHub **Actions** page. | "We have **178 automated tests**: unit tests for the domain, service tests with in-memory repositories, and API tests. GitHub Actions runs them on every push, on both SQLite and PostgreSQL, and also builds the frontend." |
| **18:50** Back to the **Dashboard**. | "To sum up: Decerno covers every MVP requirement, adds thirteen explainable intelligent features, explains every decision it makes, and adds real-time dashboards, a dependency graph and voice reporting. The object-oriented design kept all of it easy to change. Thank you." |
| Stop recording. | |

*(For the test result: run `.\.venv\Scripts\python.exe -m pytest -q` in `backend` before recording and keep the terminal
open; it takes about 45 seconds.)*

---

## Backup plan

| Problem | Do |
|---|---|
| Voice does not work | Type the text. Say "voice input uses the browser's speech service; this network blocks it". |
| The new incident is assigned to someone other than Arjun | Window A: open it, **Assign / reassign** to Arjun using **Recommended technicians** (this is also a feature to show) |
| A step shows an error | Read the message out: it is usually an exception case working as designed (for example, an illegal action) |
| Something breaks badly | Stop, reseed, sign in again, restart |
| Over 20 minutes | Skip the optional rows, the API moment and the second code moment |
| A history entry still says INC… | The database was seeded before the DCN change: reseed |

## Checklist: what the video must show (from the spec)

- [ ] Each member introduces themselves and explains a module
- [ ] Workflow 1: employee reports → prioritised → technician assigned → notification
- [ ] Workflow 2: technician investigates → SLA monitored (pause / resume) → resolved → user notified
- [ ] Workflow 3: multiple reports → duplicate / related → correlated / escalated
- [ ] Three different role interfaces
- [ ] Intelligent features: priority, duplicates, correlation, escalation, recommendation, SLA risk, category suggestion, suggested resolutions
- [ ] The **Why Decerno decided** card (explainability)
- [ ] Innovation: voice reporting, real-time dashboard, dependency graph
- [ ] API documentation (Swagger) and tests (technical depth)
- [ ] Length 15-20 minutes
