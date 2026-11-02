# Decision room — baseline

## Arguments

```json
{
  "challenge": {
    "text": "# Response to the Strongest Opposing Argument\n\nThe opponent's case is strongest where it is most concrete: **the proposal's scope (\"all support\") exceeds its evidence (FAQ only), and the 20% FAQ error rate has no severity analysis.** I concede both points fully. What follows is where I think the opponent overreaches, where my own position needs correction, and what evidence would actually settle the disagreement.\n\n## Where the opponent is right (and I should concede more cleanly)\n\n1. **\"Switch all support\" is not supported by the evidence.** My own framing tried to rescue the proposal by reinterpreting it as \"AI-first triage with human gates.\" The opponent correctly notes this is a *different proposal*. I should stop defending the original wording. The honest position is: **the evidence supports automating FAQ with human backup — not \"all support.\"** If the decision-maker insists on the literal proposal, the answer is no.\n\n2. **The 20% error rate needs severity decomposition before any auto-send.** My Gate 1 set ≥90% accuracy, but the opponent's point stands: 90% accuracy with one high-severity error is worse than 85% with only cosmetic misses. **I should adopt the opponent's severity-weighted criterion** (zero high-severity errors, or a pre-agreed threshold) rather than a flat accuracy number. This is a genuine correction to my gates.\n\n3. **The staffing model is an assumption, not a capacity plan.** Two staff absorbing ~405 non-FAQ tickets plus FAQ-error review plus escalations is untested. My Gate 2 pass criterion (\"two staff confirmed sufficient\") was doing too much work without a measurement method. **Correction:** Gate 2 must include a measured queue simulation or a live time-boxed trial with handling-time data, not a judgment call.\n\n## Where the opponent overreaches\n\n1. **\"~99 incorrect FAQ answers per month\" is a worst-case extrapolation, not a forecast.** It assumes (a) full auto-send of all FAQ, (b) the 80% holds in production, and (c) no confidence thresholding. My proposal — and even the opponent's own Gate 2 — routes only *high-confidence, low-risk* FAQ to auto-send. The realistic error exposure is a fraction of 99, and the opponent's own gates concede this by allowing auto-send with guardrails. The number is rhetorically useful but not decision-relevant as stated.\n\n2. **\"Two people cannot absorb ~405 non-FAQ tickets\" is asserted, not shown.** 405 tickets/month is ~13–14 per working day across two staff — roughly 7 each. That is not obviously infeasible; it depends entirely on handling time, which neither of us has. The opponent is right that it's unmeasured, but wrong to treat it as a refutation. It's a **Gate 2 measurement item**, which is exactly where I placed it.\n\n3. **The \"internal ambiguity\" charge (point 3) is fair to the original proposal but not to a gated rollout.** If refunds/account access keep human approval throughout — as both my gates and the opponent's gates require — then there is no ambiguity in the *deployed* system. The ambiguity is in the *slogan*, not the plan. The opponent and I are converging on the same architecture; the disagreement is about what to call it.\n\n## Where my own position was weakest\n\n- **I under-specified the confidence threshold.** \"Auto-send FAQ answers\" without a confidence gate is the actual risk the opponent is pointing at. **Correction:** Gate 2 must specify a confidence threshold calibrated on the shadow-mode data, with a measured false-confidence rate. Low-confidence FAQ routes to human, not auto-send.\n- **I had no rollback trigger tied to severity.** **Correction:** adopt the opponent's trigger — any high-severity error or CSAT drop below baseline triggers automatic rollback to human-first, not just a weekly audit.\n- **I treated \"80% is directionally sound\" too generously.** 80/100 with a wide confidence interval (roughly 71–87% at 95% CI) is a *starting point for shadow mode*, not a basis for auto-send. My Gate 1 already required shadow mode first; I should state plainly that **the pilot alone justifies shadow mode, nothing more.**\n\n## What new evidence would change my conclusion\n\nI would move from \"gated FAQ automation\" to \"full switch\" only if:\n\n1. **Non-FAQ shadow-mode results** show ≥95% accuracy with zero high-severity errors on refunds and account access *in draft-only mode*, plus a safety review.\n2. **Severity-decomposed FAQ production data** shows the 20% misses are overwhelmingly low-severity and confidence-thresholding removes most of them.\n3. **A measured capacity trial** shows two staff clear the non-FAQ queue plus escalation load within agreed SLA at peak, not average, volume.\n4. **CSAT and containment** in live FAQ auto-send match or beat human baseline over a defined window.\n\nConversely, I would **abandon even FAQ automation** if shadow mode reveals high-severity errors that confidence thresholding cannot filter, or if the two-staff capacity trial fails at realistic peak load.\n\n## Bottom line\n\nThe opponent and I agree on the architecture — staged gates, human approval retained for refunds/account access, severity-weighted pass criteria, measured capacity. The real disagreement is narrower than it appears: **whether the pilot justifies starting FAQ shadow mode now.** I say yes — 80/100 on the largest ticket category is enough to *test*, not to *deploy*. The opponent's gates implicitly agree, since Gate 1 is shadow mode. The corrected position is: **reject \"switch all support\" as stated; approve FAQ shadow mode with severity-weighted gates, confidence thresholding, a measured capacity trial, and automatic rollback — and treat every expansion beyond FAQ as requiring its own evidence.**"
  },
  "support": {
    "text": "# Response to the Strongest Opposing Argument\n\nThe opponent's case is strong, and I concede its central factual claims. What follows is where I accept correction, where I push back, and what evidence would change my conclusion.\n\n## Where the opponent is right (and I was wrong)\n\n**1. \"Switch all support\" is not supported by the evidence — and my own framing quietly conceded this.** My support case ended by redefining the proposal as \"AI-first triage with humans on approvals.\" That is *not* what the proposal says. The opponent correctly identifies this as internal ambiguity: either humans still approve refunds/account access (in which case \"all support\" is false advertising) or they don't (in which case the evidence is silent). I should not have papered over that. **Correction: the honest position is \"AI-first triage across all tickets, with human approval retained on refunds/account access\" — and that must be stated as the proposal, not smuggled in as an implementation detail.**\n\n**2. The 80% figure cannot be extrapolated, and 20% is material.** I treated 80/100 as \"directionally sound.\" The opponent's arithmetic is correct: ~99 wrong FAQ answers/month at full automation. My \"credible starting point\" language was doing too much work. A 1-in-5 error rate is a *shadow-mode* result, not an auto-send result. **Correction: I should not have implied 80% justifies FAQ auto-send; it justifies shadow mode and a severity analysis.**\n\n**3. The staffing math is an assumption, not a demonstration.** \"Two staff can remain available\" is a constraint I treated as sufficient capacity. The opponent is right that ~405 non-FAQ tickets plus approval queues plus escalations plus FAQ-error review is unmeasured. I have no handling-time data to rebut this.\n\n## Where I push back\n\n**1. The opponent's Gate 1 pass criterion (≥95% correct, zero high-severity errors) may be stricter than the human baseline it's implicitly compared against.** The challenge case never establishes what human FAQ accuracy is. If humans are at, say, 92%, a 95% AI bar is a *higher* standard than the status quo — defensible as a risk choice, but it should be labeled as such rather than presented as \"no worse than human.\" **This is a genuine gap in the opposing case: it demands AI beat an unmeasured human baseline.** The right gate is \"no worse than measured human baseline on the same ticket sample,\" which requires measuring humans too.\n\n**2. \"Two people cannot absorb 405 non-FAQ tickets\" is asserted, not shown.** 405/month is ~13–14 per working day. Whether two staff can handle that depends entirely on handling time, which neither side has measured. The opponent treats a capacity concern as a refutation; it's actually a *gate input* (measure handling time in shadow mode). I concede the burden is on me to measure it, but the opponent hasn't shown the staffing is infeasible — only that it's unproven.\n\n**3. The opponent's own gates are compatible with my position, which weakens the \"against\" framing.** Gates 0–4 in the challenge case are essentially my gates with stricter thresholds. The real disagreement is narrower than \"switch vs. don't switch\": it's about (a) whether \"all support\" is honest framing, and (b) what the pass thresholds are. On (a) the opponent wins. On (b) it's a risk-tolerance judgment neither of us can settle from the data.\n\n## Corrected position\n\nI withdraw \"switch all support\" as stated. The defensible proposal is:\n\n- **AI-first intake and triage on 100% of tickets** (this is the real efficiency claim and is testable in shadow mode).\n- **FAQ auto-send only after shadow-mode severity analysis** — not on the strength of 80/100 alone.\n- **Human approval retained on refunds and account access indefinitely**, until a separate safety pilot clears them.\n- **Staffing validated, not assumed**: shadow mode must measure handling time and queue behavior before Gate 2.\n\n## What new evidence would change my conclusion\n\n- **Human FAQ baseline accuracy and handling time** on the same 100-ticket sample. If humans are at ~80% too, the AI's error rate is not a differentiator and the case for automation rests on cost/speed, not accuracy — which changes the argument entirely.\n- **Error severity breakdown of the 20 misses.** If they're harmless phrasing issues, 80% is more tolerable; if any are misleading or policy-violating, auto-send is off the table until fixed.\n- **Shadow-mode containment and escalation data** on live traffic, including adversarial/ambiguous inputs — the pilot's sample selection method is unknown, so generalization is untested.\n- **Handling-time data** showing two staff can clear the approval queue plus escalations at peak, not just average.\n- **A non-FAQ draft-only pilot** showing the assistant can at least *assist* (not decide) on refunds/account access without introducing new error modes.\n\n**Bottom line after correction:** The opponent wins the framing argument — \"switch all support\" overclaims. The evidence supports AI-first triage with FAQ auto-send gated on severity analysis and a measured human baseline, and human approval retained on the sensitive categories. The remaining dispute is threshold-setting, which is a risk-tolerance decision the team must make explicitly, not something either case can derive from 80/100."
  }
}
```

## Text

# Decision Brief: Should We Switch All Customer Support to the AI Assistant?

## Recommendation (bottom line)

**Do not switch all support to the AI assistant.** Approve a narrower, gated program: **AI-first intake/triage across all tickets, FAQ auto-send only after shadow-mode validation, and human approval retained indefinitely on refunds and account access.** Treat every expansion beyond FAQ as requiring its own evidence. This is the position both advocates converged on after rebuttal — and it is the only one the evidence supports.

## Strongest arguments FOR the proposal

1. **The largest ticket bucket is automatable in principle.** ~495 of 900 monthly tickets (55%) are routine FAQ — exactly the category the pilot tested.
2. **The pilot shows real capability on that bucket.** 80/100 correct is a credible starting point for automation *with oversight*, not a non-starter.
3. **The riskiest work stays human by design.** Refunds and account access already require human approval; the proposal does not remove humans from the highest-consequence work.
4. **Favorable economics on the tested slice.** Absorbing a large share of FAQ volume frees two staff to concentrate on refunds, account access, and escalations.
5. **A phased switch is compatible with the intent.** AI-first triage with human approval gates preserves "AI as primary channel" while keeping staff as the approval/escalation layer.

## Strongest arguments AGAINST the proposal

1. **Scope exceeds evidence.** "All support" means deploying on ~405 tickets/month (45%) with **zero measured performance**. The 80% figure cannot be extrapolated to transactional, identity-sensitive, policy-bound work.
2. **Even on FAQ, 20% error is material.** ~99 incorrect FAQ answers/month at full automation, with no severity breakdown, false-confidence data, or CSAT/escalation outcomes.
3. **The highest-risk categories are the unmeasured ones.** Refunds and account access carry financial and security consequences; the evidence is silent on them.
4. **Staffing is an assumption, not a capacity plan.** Two staff absorbing ~405 non-FAQ tickets plus approval queues plus escalations plus FAQ-error review is untested.
5. **The proposal is internally ambiguous.** Either humans still approve sensitive categories (so "all support" is false) or they don't (so the evidence doesn't support it).

## Where the two sides actually agree (post-rebuttal)

Both advocates, after rebuttal, converged on the same architecture:

- **Reject "switch all support" as stated.** Both concede the framing overclaims.
- **AI-first intake/triage on 100% of tickets** is the testable efficiency claim.
- **FAQ auto-send only after shadow-mode severity analysis** — not on 80/100 alone.
- **Human approval retained on refunds and account access indefinitely**, until a separate safety pilot clears them.
- **Staffing validated by measurement**, not assumed.
- **Severity-weighted pass criteria** (zero high-severity errors, or a pre-agreed threshold) rather than flat accuracy.
- **Automatic rollback** on any high-severity error or CSAT drop below baseline.

## Unresolved disagreements

1. **Whether to start FAQ shadow mode now.** The support case says yes (80/100 justifies *testing*); the challenge case's own Gate 1 is shadow mode, so this is narrower than it appears — but the challenge side has not explicitly endorsed starting.
2. **Pass thresholds.** The challenge case proposes ≥95% correct with zero high-severity errors; the support case notes this may be *stricter than the unmeasured human baseline*. Neither side can derive the threshold from 80/100 — it is a risk-tolerance decision.
3. **What "no worse than human" means** when human FAQ accuracy has never been measured on the same sample.
4. **Whether the ~99 errors/month figure is decision-relevant** — the challenge side treats it as a forecast; the support side correctly notes it assumes full auto-send with no confidence thresholding.

## Evidence gaps (must be closed before any autonomy)

- **Human baseline:** FAQ accuracy, handling time, and CSAT on the same ticket sample — without this, "no worse than human" is undefined.
- **Error severity decomposition** of the 20 pilot misses (harmless vs. misleading vs. policy-violating).
- **False-confidence rate** and calibration data for any confidence threshold.
- **Sample selection method** for the 100-ticket pilot (generalization is untested).
- **Production metrics:** containment, escalation, CSAT, handling time, latency, cost.
- **Non-FAQ performance:** zero data on refunds, account access, or other ticket types.
- **Capacity model:** handling time and queue behavior for two staff at *peak*, not average, load.
- **Adversarial/ambiguous input behavior.**

## Concrete deployment gates

**Gate 0 — Scope correction and baseline (before any switch):**
- Restate the proposal as "AI-first triage with human approval retained on refunds/account access." "All support" is not deployable on current evidence.
- Confirm the 55% FAQ share against a fresh sample; define ticket taxonomy.
- **Measure the human baseline** on the same sample: accuracy, handling time, CSAT, escalation rate.

**Gate 1 — FAQ shadow mode (2–4 weeks):**
- AI drafts; humans review every draft before send.
- Measure: accuracy **by severity**, false-confidence rate, escalation rate, handling time, CSAT.
- **Pass:** accuracy no worse than measured human baseline, **zero high-severity errors** (or a pre-agreed severity-weighted threshold), and a documented error taxonomy.

**Gate 2 — FAQ auto-send with guardrails:**
- Auto-send only high-confidence, low-risk FAQ; route the rest to humans.
- Confidence threshold calibrated on shadow-mode data.
- **Pass:** error rate and CSAT no worse than human baseline over a defined window; **measured capacity trial** confirms two staff clear the non-FAQ queue plus escalations at peak load.
- **Rollback trigger:** any high-severity error or CSAT drop below baseline reverts to human-first automatically.

**Gate 3 — Non-FAQ pilot (draft-only/assist only):**
- Test refunds and account access in draft-only mode.
- **Pass:** measured accuracy and safety review before any autonomy; human approval remains mandatory throughout.

**Gate 4 — Expand only on measured evidence:**
- Any removal of human approval for refunds/account access requires a **separate pilot** with explicit safety and financial-error thresholds.
- Ongoing: weekly accuracy audit on a random sample; kill switch to revert to human-first.

## Practical recommendation

1. **Reject the literal proposal** ("switch all support") — the evidence covers at most 55% of volume, with a 20% error rate on that subset and no data on the sensitive remainder.
2. **Approve Gate 0 and Gate 1 now** — baseline measurement plus FAQ shadow mode. This is low-risk, reversible, and generates the data both sides agree is missing.
3. **Make the risk-tolerance decision explicitly** — the team, not the data, must set the severity-weighted pass threshold and the acceptable error rate on FAQ vs. sensitive categories.
4. **Hold refunds and account access human-approved indefinitely** until a separate safety pilot clears them.
5. **Do not treat 80/100 as a deployment result** — it justifies shadow mode and a severity analysis, nothing more.

The defensible path is staged gates with pre-agreed, severity-weighted pass/fail thresholds and automatic rollback — not a full switch, and not a blanket rejection of the assistant's demonstrated capability on the largest ticket category.
