# Block Planner — Round 2: The Harder Questions
### Judge panel simulation: tier-1 CS professor + multi-exit startup founders

This picks up where `hackathon_qa_prep.txt` leaves off — read that one first, this assumes it. Everything below came from actually reading this codebase end to end, the way a judge who used to run engineering at a startup and now guest-lectures at a top CS department would: fast, unimpressed by buzzwords, and willing to open a file mid-sentence to check a claim. Several of these are new gaps the first pass didn't catch. Others are business and ethics questions no amount of code-reading will save you from — you just have to have thought about them.

Same rule as before: "we haven't validated that yet, here's our plan" beats a confident answer that falls apart under one follow-up.

---

## SECTION 11 — THE HEADLINE NUMBERS: WHERE DID "BEFORE" ACTUALLY COME FROM?

Possibly the most dangerous section here, because it's the number on your title slide.

**IMPORTANT CONTEXT FOR THE TEAM:** `main.py`'s `/api/comparison/before-after` endpoint does not simulate an unoptimized baseline — it hardcodes one:

```
before_metrics = {
    "total_blocks": total_tasks,               # every task = its own block
    "total_downtime_minutes": total_tasks * 60, # flat 60 min per task, real duration ignored
    "train_conflicts": total_tasks // 2,        # arbitrary half-of-tasks formula
    "block_utilization": 35.0,                  # a literal constant
}
```

With 300 tasks this produces exactly 300 blocks, 18,000 minutes, and 150 conflicts — precisely the "Before" column in your README. None of these three numbers comes from running anything. They come from assuming the worst conceivable baseline: zero coordination, a flat 60-minute guess regardless of each task's real `estimated_duration_minutes`, and a made-up conflict ratio.

**Q: Is your 88% downtime reduction measured against a real or simulated "before" scenario, or an assumption?**
A: It's an assumption, not a measurement. "Before" assumes one block per task at a flat 60 minutes each — a worst-case strawman, not a modeled "how departments actually schedule today" baseline. The *direction* of improvement (fewer, better-coordinated blocks) is real and defensible; the specific percentage is not, because the denominator was never run through any process, real or synthetic.

**Q: If I asked you to build a fairer "before" baseline right now, what would it look like?**
A: At minimum, use each task's actual `estimated_duration_minutes` instead of a flat 60, and a naive-but-real per-department greedy scheduler (each department packs its own tasks independently, no cross-department merging) instead of "every task gets its own block." That would still show real improvement from coordination — just a smaller, defensible number instead of an inflated one.

**Q: `BlockOptimizer._calculate_metrics` computes `train_conflicts` from actual block/train time overlaps. The separate `/api/comparison/before-after` endpoint's `_compute_after_metrics` hardcodes `train_conflicts: 0` and `train_disruption_minutes: 0`. Which of these produced the "36" in your README — and do the two ever disagree on screen?**
A: There are two independently-written "after metrics" implementations, and only one of them actually counts conflicts — the other silently reports zero. If your Before/After screen calls `/api/comparison/before-after`, a judge could watch it claim *zero* train conflicts after optimization, a much bigger claim than 36 and a much easier one to be suspicious of. Trace which endpoint each screen actually calls before demo day, and make sure your slide matches your running app.

**Q: Is the README's "After" row a live number, or a value someone ran once and typed in?**
A: `random.seed(42)` makes the dataset reproducible, so a fresh run today *should* match — if nothing else has changed. Confirm this by literally re-running it before the demo. If anyone tweaked priority weights, compatibility rules, or the data generator since that README was written, your slide may no longer match what your live app shows on stage.

---

## SECTION 12 — OPTIMIZER GOTCHAS THE FIRST PASS MISSED

The original prep covers the CP-SAT-vs-greedy gap well. These are separate issues in the same files.

**Q: FR-04 in your own PRD lists "block type" as something compatibility must consider. Where in `_is_compatible` or `_pack_tasks_for_window` is `task.required_block_type` checked against `window.block_type`?**
A: It isn't checked anywhere. `required_block_type` is generated per task, stored in the model, and saved to the database — and never read by the optimizer. A task requiring "Possession" can currently be packed into a "Lines Up" window with no check at all. The honest line: "corridor, dependency, isolation, and two hardcoded safety-conflict pairs are checked — block-type matching isn't implemented yet."

**Q: `_pack_tasks_for_window` builds a `used_depts` set and passes it into `_is_compatible` — where inside `_is_compatible` is `used_depts` actually read?**
A: Nowhere — it's populated and passed in but never referenced in the function body. Functionally, there is no resource-contention check at all. Your PRD lists "resource availability" as a hard constraint, and `required_resources` (e.g. "Track Gang," "Welding Team") exists on every task, but nothing checks whether the same team is already committed elsewhere at an overlapping time. Two tasks both needing the only "OHE Team" in a corridor can be scheduled into overlapping blocks today with no warning.

**Q: Walk me through `separate_blocks_avoided = max(0, total_tasks - len(blocks) - assigned_count)`. What is this number supposed to represent, and does the formula compute that?**
A: If the intent is "how many blocks did we avoid needing by combining tasks," that's closer to `assigned_count - len(blocks)`. What's actually written simplifies to `maintenance_backlog - len(blocks)` — backlog minus block count, a different and much less meaningful quantity. Do this arithmetic yourselves before a judge does it on stage from numbers already on your screen.

**Q: Your `asset_availability` formula divides total block-minutes — summed across every corridor — by a single week's minutes (`7*24*60`), regardless of corridor count. With 3 independent corridors, shouldn't the denominator scale with them?**
A: As written, adding a 4th corridor would mechanically drag "asset availability" down even though no individual asset's uptime changed, because you're comparing system-wide block-minutes to one corridor's time budget. Either compute and average it per-corridor, or give the current number a more honest name than "asset availability."

**Q: Your README's flagship example shows three departments each requesting a different time window, merged into one compatible window. Show me the field on `MaintenanceTask` that holds a department's originally-requested time.**
A: There isn't one. Tasks carry `corridor_id` and `required_block_type`, but no requested start/end time — `block_windows` is a fixed, pre-generated, department-agnostic list per corridor. The greedy packer assigns tasks from any department into whichever existing window fits by priority; it never reconciles competing department-requested times, because that concept doesn't exist in the data model. The README visual is a good illustration of the *target* behavior — be ready to say clearly that it's illustrative, not a trace of what the code does today, because "show me that exact scenario running" will come up empty.

**Q: A 4th corridor just needs a new `corridor_id` in the data. Does the same hold for a 4th department?**
A: No. `Department` is a hardcoded 3-value Python `Enum` (Engineering, S&T, Traction). Real railways sometimes split responsibilities differently — a 4th department here means a code change and redeploy, not a data change, unlike corridors. Know which parts of your system are actually general and which only look that way.

---

## SECTION 13 — IS THE SCORING SYSTEM ACTUALLY DATA-DRIVEN?

Open `data_generator.py` before this section — it changes the honest answer to several Section 2 questions in the original prep.

**Q: `failure_risk` (25% weight) and `safety_criticality` (10% weight) make up 35% of every task's score. How are they generated in the synthetic data?**
A: `failure_risk = round(random.uniform(20, 95), 1)` and `safety_crit = round(random.uniform(20, 90), 1)` — independent uniform random draws per task, unrelated to department, asset, or task type. `train_impact` (15% weight) is generated the same way. That's 50% of the total weighted score coming from three numbers that are, structurally, dice rolls. Only `criticality` (30%) is actually derived from something real (the asset's base criticality, bumped for Emergency/Defect task types), and `days_overdue` (20%) is a genuine calculation from the due date. If pushed: "roughly half our priority score's weight sits on fields that are randomly generated in this demo dataset, not derived from asset condition — a real deployment needs these from sensor data, inspection history, or a trained risk model."

**Q: Assets have a `historical_failure_rate` field, generated per asset and saved to the database. Where does the priority engine use it?**
A: It doesn't. `historical_failure_rate` appears only in the generator, the Pydantic model, and the seed script — never read by `priority_engine.py` or anywhere else. You generate a plausible asset-level signal and then don't use it, while the field that *is* used (`failure_risk`) is a fresh random number per task, disconnected from that asset's own rate. If asked why: it's a decorative leftover from an earlier design, not a wired-up feature — say that plainly.

**Q: When your explanation panel says "High failure risk: 90.9%," what is that number actually telling a planner about the physical world?**
A: Nothing, currently. It's a synthetic random draw, so the explanation text accurately describes what's in the field — but the field itself carries no real-world signal in this prototype. This sharpens the original prep's Section 8 point: there's no ML here, and even the inputs a future model would eventually learn from aren't wired to anything structural yet.

**Q: If you later trained a real ML model for `failure_risk`, what's the risk your synthetic data would make that model meaningless to validate?**
A: Training on this generator's output means training a model to predict noise from noise — there's no real signal to find. Worse, any historical-outcome label added later (e.g., "did this asset actually fail") would need to be generated independently of `failure_risk`, or you'd build a model that "predicts" a label the generator used to construct its own input — data leakage baked into the generator, not the model. A real deployment needs `failure_risk` sourced from actual inspection or sensor history, with no synthetic shortcuts.

---

## SECTION 14 — TESTING & ENGINEERING DISCIPLINE

**Q: What's your test coverage on the optimizer and the priority engine?**
A: `backend/tests/` contains exactly one file, `test_security.py` (39 tests, all auth-focused). Zero automated tests exist for `block_optimizer.py`, `priority_engine.py`, or `data_generator.py` — the actual core logic of the product. If asked "if I changed one line in `_is_compatible` right now, what catches the regression before your next demo" — the honest answer is nothing automated would.

**Q: What would a meaningful test for the optimizer actually check?**
A: Have concrete examples ready, not a vague promise: a test that two tasks with a mutual `dependencies` conflict never land in the same block; a test that a corridor with tasks but zero matching windows produces zero blocks rather than an error; a monotonicity check that increasing `available_duration` never decreases the number of tasks packed. None of these need OR-Tools or a database — they run against the packing function directly with hand-built fixtures.

**Q: Two planners click "Run Optimizer" at the same moment. Walk me through what happens in `save_blocks`.**
A: `save_blocks` parallel-deletes three dependent tables (`block_task_assignments`, `block_departments`, `maintenance_blocks`) via separate REST calls to Supabase, then parallel-inserts new rows — with no transaction spanning delete-then-insert, and no lock against a second concurrent run. If the process errors between phases, or two runs interleave, the database can genuinely end up inconsistent (blocks deleted but not yet replaced, or one run's inserts clobbered by the other's delete). This hasn't been tested under concurrency; say so rather than asserting it "just works."

**Q: Have you actually run this in Docker, or does `docker-compose.yml` just exist?**
A: Try `docker-compose up` cold, on a machine that isn't your dev laptop, before demo day. A compose file that's never been exercised end-to-end is exactly the kind of thing that produces the on-stage surprise the original prep's Section 9 already tells you to have a fallback for.

---

## SECTION 15 — SECURITY: THE NEXT LAYER DOWN

The original prep's Section 6 covers password hashing, secrets, and session-restart well. These go one level further.

**Q: An admin deactivates a user in User Management. Does that user's existing JWT stop working immediately, or keep working until natural expiry?**
A: Token validation in `core/security.py` is purely stateless — decode, signature, expiry check, no revocation list, no server-side session store. There's no way to invalidate an already-issued token early. A deactivated user's access token still works for up to 30 minutes, and a leaked refresh token keeps minting new access tokens for up to 7 days, admin action or not. For a system with a dedicated Audit Log and User Management screen, this is worth naming as a known gap plainly: "revocation would need a server-side blacklist or much shorter-lived tokens; we don't have that yet."

**Q: `CORSMiddleware` is configured with `allow_origins=["*"]`. What's the actual risk given you use Bearer tokens, not cookies?**
A: Because auth is a manually-attached Bearer token rather than an auto-sent cookie, a wildcard origin doesn't hand out CSRF for free the way it would with cookie sessions. The real risk is that any website can call your read endpoints from a visitor's browser if a token ever leaks into page JavaScript — and in any real deployment you'd restrict this to your actual frontend's origin. Don't overclaim severity, but don't wave it away either.

**Q: Your README states the frontend stores tokens in localStorage. If anything in the app ever renders unsanitized text via `dangerouslySetInnerHTML`, what's the blast radius?**
A: localStorage is readable by any JavaScript on the page — if an attacker ever got a script to execute via a stored-XSS hole anywhere, they read the access and refresh tokens directly, no cookie flags to bypass. Check whether any component renders raw HTML or strings from task/explanation data without escaping. If nothing does, say so with confidence; if you're not sure, check before claiming the app is safe — the real TMS/SMMS/TDMS/COA integrations you'd eventually plug in are exactly the kind of upstream text you wouldn't fully control.

**Q: This system sits between maintenance data sources and a human approver. If an upstream feed — real TMS/SMMS/TDMS data, eventually — fed in manipulated or simply wrong criticality numbers for one asset, could the system quietly bury a genuinely urgent task under a wave of inflated "high priority" noise elsewhere?**
A: Nothing in the current architecture validates that priority inputs are plausible or flags an asset whose risk profile just changed sharply. A real deployment feeding off live operational systems needs basic input sanity-checking and anomaly flagging on incoming data, not just on user-submitted API calls — otherwise one bad upstream feed, malicious or just broken, silently degrades trust in every ranking downstream of it.

---

## SECTION 16 — ALGORITHMS & COMPUTATIONAL THEORY (the CS-professor gauntlet)

This is where a professor on the panel stops asking about your code and starts asking about the problem itself.

**Q: What computational complexity class does this scheduling problem actually belong to?**
A: It's a variant of interval/machine scheduling with side constraints — resource contention, mutual-exclusion pairs, dependencies. General versions of this problem family are NP-hard. That doesn't mean your instance is intractable (300 tasks, ~21 windows is small) — it means "provably optimal" isn't free, which is exactly why exact solvers like CP-SAT exist for this class of problem in the first place, and exactly why it's notable that the CP-SAT instance is instantiated but never invoked.

**Q: The code comment says CP-SAT "can be slow for 300 tasks," and that's the reason it's unused. Have you actually run the CP-SAT solve on this dataset and measured it, or is that an assumption?**
A: This is the sharpest version of a question the original prep already raises. If you haven't measured it, say so, and treat "CP-SAT would be too slow" as an untested hypothesis, not a justified decision. At 300 tasks and a handful of windows per corridor, a well-formed CP-SAT model quite plausibly solves in well under your 30-second timeout — you won't know until you run it. "We measured it and it took N seconds" is a categorically stronger answer than "we assumed it would be slow."

**Q: Setting optimality aside — how do you even define "optimal" here, given you're simultaneously maximizing utilization, maximizing multi-department coordination, and minimizing train disruption, which can trade off against each other?**
A: This is a real multi-objective optimization question, and "highest priority first" is a single-objective proxy, not a stated trade-off policy. The current *optimizer* has no explicit Pareto frontier or weighted multi-objective function — unlike the priority *score*, which is an explicit weighted formula — it implicitly encodes a preference order (priority, then greedy fill) rather than jointly optimizing the objectives your own PRD Section 13 lists. A more rigorous version defines an explicit objective (as the PRD's `w1...w9` sketch does) and actually optimizes it.

**Q: Why greedy rather than simulated annealing, a genetic algorithm, or local search with swap moves — all standard tools for this class of packing problem?**
A: Greedy is simple, fast, and easy to explain to a non-technical approver — a real advantage in a safety-critical, human-in-the-loop context, worth stating explicitly. The honest trade-off: greedy commits early and never revisits, so it can lock in a locally-good, globally-mediocre plan. A local-search pass that tries swapping tasks between blocks after the initial greedy pass is a natural, relatively cheap next step that catches some of those cases without CP-SAT's full complexity.

**Q: Your priority formula normalizes every input to 0–1 and takes a weighted sum. What's the justification for an additive model here rather than a gated one, where a task must clear a minimum safety bar rather than just average well?**
A: An additive model lets a task with catastrophic `safety_criticality` but low everything-else still lose to a task that's mediocre-but-decent across all five dimensions, because the low safety score gets diluted by averaging. A safety-critical domain arguably wants certain thresholds (e.g., safety above some level) to force a high floor on priority regardless of the other four terms, rather than letting enough "good enough" elsewhere outweigh one "actually dangerous" dimension. Whether or not you implement this, having thought about additive-vs-gated is exactly the judgment a domain expert probes for.

---

## SECTION 17 — RAILWAY DOMAIN, SAFETY CASE & REGULATORY REALITY

**Q: Precisely who inside Indian Railways is your user — a Divisional Engineer, a zonal planning cell, CRIS, RDSO, or the Railway Board's safety directorate? "Railway planners" isn't specific enough for a judge who's worked with a PSU.**
A: Prepare a specific, reasoned answer as a team — even a guess with justification ("we believe this sits at the divisional level, since block/possession planning is coordinated there today, based on [your research]") beats "railway planners" in general. If you haven't identified a level, say so plainly and name it as validation you still need, exactly as the original prep recommends for "how is this done today."

**Q: Has anyone with real signaling, S&T, or civil engineering railway experience reviewed your safety-requirement rules, or is that your team's best guess?**
A: The original prep already tells you to admit domain rules are inferred, not sourced. Go further: name specifically what you'd want reviewed (the two hardcoded safety-conflict pairs, isolation logic, the block-type taxonomy) and by whom — a working S&T or P.Way engineer, not just publicly available documentation.

**Q: This tool never issues commands to signaling or interlocking systems — it's explicitly advisory. If a human approves a plan this system recommended and it later contributes to an incident, who's accountable?**
A: This deserves real thought, not a reflexive "the human approved it." Human-in-the-loop approval reduces certain risks but doesn't automatically resolve liability — if the explanation was misleading, or a real gap (the silent task-drop, the unenforced block-type check) contributed to a plan a time-pressured approver reasonably trusted, "they clicked approve" is an incomplete answer. Acknowledge this is genuinely unresolved, not something your architecture has already solved by inserting a button.

**Q: What would it actually take to get a tool like this through the Commissioner of Railway Safety or an equivalent RDSO review before any real corridor could depend on it?**
A: You don't need a full answer — you need to show you know the process exists: safety-case documentation, extensive shadow-running against real operations before any planning authority is delegated, sign-off chains far beyond a hackathon demo. Naming this unprompted signals you understand deployment is a multi-year regulatory process, not a software rollout.

**Q: How would this realistically get procured and deployed inside Indian Railways?**
A: Government technology adoption here typically runs through tendering (GeM, e-tenders), often via an empanelled systems integrator rather than a five-person team selling directly, and can take years. A founder-judge will ask what your path from "won a hackathon" to "one division actually uses this" looks like — "we'd pursue an incubation route or a pilot partnership with one zonal railway" is more credible than assuming a direct sale.

---

## SECTION 18 — BUSINESS MODEL, MARKET & FOUNDER-STYLE DUE DILIGENCE

**Q: Is this a company you intend to build, IP you'll hand to Indian Railways, or a hackathon exercise that ends after judging?**
A: Decide this as a team before demo day — the honest answer changes your answers on monetization, defensibility, and roadmap. An inconsistent answer between teammates on stage reads worse than a clear "here's what we've decided," whichever it is.

**Q: If this became a product, what's the business model — SaaS license per zonal railway, a one-time integration contract, something else? What would you charge, against what budget line?**
A: Have a rough, reasoned number, not silence. Even a back-of-envelope estimate tied to your claimed downtime savings, converted into a rupee figure a division would recognize, shows you've thought about this as a business. Don't invent a number you can't defend — "we haven't priced this, here's how we'd think about it" is fine if that's genuinely where you are.

**Q: What's your actual moat? If CRIS's internal team, or a systems integrator like TCS or L&T, saw this exact demo, what stops them from building an equivalent in six months?**
A: "We thought of it first" isn't an answer once you've demoed it publicly. Legitimate answers: domain-specific constraint knowledge accumulated through real deployment feedback, integration relationships with the actual source systems (the genuinely slow, hard part — not the optimizer), or a head start on the explainability/what-if UX operational staff actually trust.

**Q: How does this compare to existing commercial or research work — enterprise asset management suites, or academic literature on railway possession/maintenance-window scheduling?**
A: Even a brief "we looked at X, this differs by Y" beats implying no one has thought about this before. If your team hasn't done this scan, name it as a gap honestly — "we focused our time on the working prototype, and a competitive landscape study is a next step" — rather than asserting novelty you haven't checked.

**Q: Translate "88% downtime reduction" into money. What's the estimated annual cost of uncoordinated maintenance disruption for a typical division, and what fraction could this plausibly capture?**
A: This is the "make the founder in the room believe the ROI" question. If you don't have a grounded estimate, don't fabricate one — say what inputs you'd need (real disruption-cost data you don't currently have) and your rough approach once you had them, rather than presenting your KPI table as if it were already a financial argument.

**Q: What's your realistic rollout path across Indian Railways' dozens of divisions — one pilot corridor to broader adoption over what timeline?**
A: A single successful pilot doesn't imply automatic rollout. A credible answer names the pilot-to-scale path honestly — per-division validation, likely per-division procurement, integration work repeated for each corridor's actual data sources — rather than implying one demo scales itself.

---

## SECTION 19 — ETHICS, EQUITY & UNINTENDED CONSEQUENCES

**Q: Could optimizing for `train_impact` systematically deprioritize maintenance on low-traffic rural or branch corridors, since fewer/less-critical trains naturally produce lower scores, versus high-traffic trunk routes?**
A: Sit with this rather than deflect. As weighted today, a task on a quiet branch line scores lower on 15% of the formula purely because fewer trains run there — independent of the asset's actual condition. Over many cycles, that's a plausible mechanism for exactly the kind of quiet-corridor neglect that later surfaces as a rural safety incident precisely because it never accumulated enough priority to get fixed while still minor. Acknowledge this as a real design tension between urgency and equity rather than claiming the formula is neutral.

**Q: Could this create a "squeaky wheel" dynamic — an asset only gets scheduled once it's become urgent (high `days_overdue`, high `failure_risk`), rather than surfacing while still cheap to fix preventively?**
A: This is a legitimate critique of urgency-driven scoring generally, not just this implementation. A production version might want an explicit incentive for preventive work that doesn't purely compete with already-overdue tasks on the same scale.

**Q: If a human approver starts trusting the "AI recommendation" and rubber-stamps plans faster over time, does a confident-sounding explanation panel increase automation bias — reduced scrutiny precisely because the system sounds authoritative?**
A: This is a well-documented human-factors risk in decision-support tools generally, and it's fair to be asked about directly. Don't oversell the explainability panel as a safeguard against it — a template that always sounds confident, even when explaining a random-noise-driven score (Section 13), can plausibly make approval feel like formality rather than genuine review over time. Name this as a real risk to monitor, not something the approval step automatically prevents.

**Q: If this reduces the need for department planners to manually coordinate, have you thought about the workforce/change-management angle among railway staff?**
A: You don't need a solved answer, but you should have thought about it once. "We automate the coordination, not the judgment" — consistent with keeping a human approval step per your own PRD — is a reasonable starting frame, but acknowledge some coordination roles genuinely could shrink if this worked as intended at scale.

---

## SECTION 20 — PRODUCT, UX & REAL USERS

**Q: Has anyone outside your team — ideally with actual railway operations experience — used this UI without you explaining it first?**
A: Answer honestly. If no, that's a normal hackathon-timeline limitation — say so and name it as the first thing you'd do with more time, rather than implying informal validation happened when it didn't.

**Q: The UI is in English. Would planners and engineers who'd actually operate this day to day across most Indian Railways divisions be comfortable working entirely in English under time pressure?**
A: Have a real answer, not a generic "we'd add i18n later." Naming Hindi and relevant regional-language support as a concrete, specific gap shows you understand the actual user base, not just a checklist item.

**Q: Your priority levels (Critical/High/Medium/Low) presumably use color coding. Is that palette colorblind-safe, given the colors stand in for genuinely safety-relevant urgency?**
A: Check this concretely rather than assume. Red/green-only distinctions are a common, avoidable accessibility failure, and it matters more here than in a typical dashboard because the colors carry safety meaning, not just a business metric.

**Q: The What-If Simulator asks a planner to reason about several changed constraints at once. Is that usable under real time pressure, or does it assume unhurried, exploratory use?**
A: Think this through honestly rather than defending the feature reflexively. A tool that's genuinely useful in a calm planning session can still be the wrong shape for someone who needs an answer in the next two minutes because a block window just got cancelled. If untested under time pressure, name that as an open question rather than an implicit strength.

---

## SECTION 21 — RAPID-FIRE, LATERAL & LOADED QUESTIONS

These are the kind a sharp panel fires quickly to test composure and whether you actually understand your own system, not to get one "correct" answer. Practice answering fast and straight.

**Q: "So this is a fully autonomous AI scheduling system, right?"**
A: No — say so immediately. It's a decision-support tool with a mandatory human approval step; nothing it produces takes effect without a person clicking approve.

**Q: "You've basically solved Indian Railways' maintenance coordination problem end to end?"**
A: No — a single-corridor, synthetic-data prototype demonstrating an approach, with known gaps in the optimizer, integrations, and validation, all listed plainly in your own gap sections.

**Q: If I deleted your Supabase project right now, what would you lose, and what's your actual recovery story?**
A: Everything not re-generatable from `data_generator.py`/`seed.py` — anything created live during the demo (approvals, weight changes, audit history) — would be gone, with no backup process described anywhere in this repo. That's a fine answer for a hackathon prototype as long as you say it plainly instead of improvising a recovery plan that doesn't exist.

**Q: What's the single line or function in this codebase you're least confident defending, and why?**
A: Have a real, specific answer ready — ideally from Sections 11–13 above, since you now know exactly where the soft spots are — rather than a rehearsed "everything is solid."

**Q: If Indian Railways handed you ₹1 crore and 12 months tomorrow, what's the very first thing you'd build that isn't in this prototype?**
A: Have a genuine, prioritized answer: most teams should name some combination of a real integration with one actual data source, a validated safety-rule set from a real domain expert, and a properly benchmarked exact-vs-heuristic comparison. "We'd scale it up" reads as not having thought past the demo.

**Q: Which of the 20 blocks in your demo plan would you personally be least comfortable standing on that track during?**
A: Designed to make the silent-task-drop and unenforced-compatibility gaps feel visceral rather than abstract. A good answer names a specific known limitation (e.g., "the ones where block-type compatibility isn't actually checked") rather than deflecting with "they're all fine, it's just a demo."

**Q: Name a scheduling problem from a totally different field that's mathematically similar to yours, and what that field learned the hard way.**
A: Have one ready — operating-room scheduling, airline gate assignment, and cloud data-center maintenance windows are all structurally similar (scarce shared resource, competing priorities, hard constraints, human override). Any of these fields has hard-won lessons about the exact failure modes above (silently dropped low-priority items, gamed baselines, automation bias). Showing you've looked outside your own domain is a strong signal.

**Q: If two of you disagreed tonight about the honest "greedy heuristic" framing versus the more impressive "CP-SAT optimization" framing, who has final say, and on what basis?**
A: However you'd actually decide this internally, the "right" answer for a judge is the one your own original prep already argues for: accuracy over impressiveness — a technical judge finding the gap themselves costs far more credibility than admitting it upfront ever would.

---

## SECTION 22 — QUICK-REFERENCE: NEW GAPS THIS PASS FOUND

Add these to the original prep's Section 10 list. Same rule applies: "yes, we know, here's why" beats getting caught.

9. `task.required_block_type` is generated and stored but never checked against `window.block_type` anywhere in the optimizer — block-type incompatibility can pass silently.
10. `used_depts` is threaded into `_is_compatible` but never read inside it — there is no resource-contention/capacity check anywhere, despite "resource availability" being listed as a hard constraint in the PRD.
11. `asset.historical_failure_rate` is generated and saved but never consumed; the `failure_risk`, `safety_criticality`, and `train_impact` fields that ARE used (50% of the priority weight combined) are independent `random.uniform()` draws with no structural relationship to department, asset, or task type.
12. `separate_blocks_avoided` is computed as `total_tasks - len(blocks) - assigned_count`, which algebraically reduces to `maintenance_backlog - len(blocks)` — a different quantity than the field name implies.
13. `asset_availability` divides total block-minutes summed across all corridors by one corridor's weekly minutes, not scaled by corridor count.
14. The README/PRD's flagship "three department-requested windows merge into one" example has no corresponding data field — tasks carry no requested time, only a fixed, pre-generated, department-agnostic window list per corridor.
15. `Department` is a hardcoded 3-value Enum; unlike corridors (data-driven), adding a 4th department needs a code change.
16. `/api/comparison/before-after`'s "Before" baseline (`total_tasks`, `total_tasks * 60`, `total_tasks // 2`, a hardcoded `35.0`) is an assumption, not a simulated or measured scenario — and it's the exact source of the README's headline "-93%/-88%/-76%" claims.
17. That same endpoint's `_compute_after_metrics` hardcodes `train_conflicts`/`train_disruption_minutes` to 0, while the optimizer's own `_calculate_metrics` computes real values — the two can disagree on-screen.
18. `backend/tests/` contains exactly one test file (`test_security.py`); there are zero automated tests for the optimizer, priority engine, or data generator.
19. `save_blocks` parallel-deletes three dependent tables and then parallel-inserts new rows with no transaction spanning the two phases and no lock against a concurrent optimizer run — a crash or a second simultaneous run can leave the database in a partially-updated state.
20. JWTs cannot be revoked before natural expiry — no blacklist or server-side session store, so a deactivated user or leaked refresh token stays valid for up to 7 days regardless of admin action.
21. `CORSMiddleware` is configured with `allow_origins=["*"]`.
