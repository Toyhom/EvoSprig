# Research team — evolved

## Text

# Should we launch the $19 plan? — Brief

**Recommendation: Do not launch $19 as a committed public price yet. Run it as a live pricing test inside the June 15 beta, then decide.** The pricing proposal is explicitly **not approved** and itself states that willingness to pay "needs a live pricing test" [888fe982edf2:0-379]. The evidence supports demand for the *problem*; it does not yet support the *price*.

## What the records say

**Pricing proposal** [888fe982edf2:0-379]
- "Team plan": **$19 per seat per month**, **minimum three seats** → effective floor ≈ **$57/month per customer**.
- 14-day trial, **no payment card required**.
- Estimated service cost **$4 per active seat per month**, *before* support and salaries.
- Status: **not approved**.

**Customer feedback** [3ff219f9c4a3:0-331] — 12 independent design studios, exploratory
- **8/12** asked for a shared review inbox; **6/12** said scattered client feedback slows approval.
- **5/12** were willing to *try* a $19 per-seat monthly plan.
- **3/12** asked for an on-premises edition.
- Explicit caveat: interviews were **exploratory, not a representative survey**.

**Launch context** [6fe6651dd0d0:0-432]
- Beta opens **June 15** with **20 design studios**.
- V1 scope: email import, comment threads, approval status. **On-premises is out of beta scope.**
- Team: 2 engineers, 1 designer; **email import is the largest schedule risk**.
- Success bar: **12 studios using the inbox weekly after four weeks**.

## Feedback vs. proposal

| Dimension | Feedback | Proposal | Gap |
|---|---|---|---|
| Core value | 8/12 want shared inbox; 6/12 cite slow approvals | Shared review is the wedge | **Consistent — strongest signal in the corpus** |
| Price | 5/12 "willing to try" $19/seat | $19/seat | "Willing to try" ≠ willing to pay; no commitment measured |
| Packaging | Not addressed | 3-seat minimum | **Untested**; may exclude solo/small studios |
| Segment fit | 3/12 want on-prem | On-prem out of scope | Known mismatch, deferred |
| Margin | — | $4/seat cost, excludes support + salaries | True unit cost unknown |

## Assumptions that remain unvalidated
1. **"Willing to try" converts to paid** — the 5/12 figure is stated intent in a non-representative sample.
2. **The 3-seat minimum is acceptable** — no record shows anyone was quoted the $57/month floor; a 2-person studio faces a 50% premium.
3. **$19 is above the indifference point** — no price-sensitivity test or competitor benchmark exists in the corpus.
4. **$4/seat is a real margin** — it excludes support and salaries [888fe982edf2:0-379], so gross margin at $19 is overstated.
5. **The beta cohort resembles the interview sample** — both are small-n and self-selected [3ff219f9c4a3:0-331].
6. **On-prem demand (3/12) won't block deals** in the beta window.

## Conflicts and missing information
- **"Willing to try" vs. willingness to pay:** the card-free trial [888fe982edf2:0-379] cannot measure payment intent; trial signups will look like demand regardless.
- **Seat minimum untested:** the $19 figure was discussed in interviews; the 3-seat floor was not [3ff219f9c4a3:0-331 vs 888fe982edf2:0-379].
- **On-prem segment:** 3/12 want it [3ff219f9c4a3:0-331] but it's out of scope [6fe6651dd0d0:0-432] — those studios may be unaddressable at any price.
- **Missing entirely:** conversion/churn data, competitor or alternative-price benchmarks, support/salary cost per seat, breakdown of the 5 willing-to-try studios by size, reasons the other 7 declined, and whether the 20 beta studios overlap the 12 interviewees.

## Practical validation plan
1. **Instrument the beta as a pricing test** across the 20 studios [6fe6651dd0d0:0-432]. With n=20, a clean A/B has little power — use a **staggered/sequential** design rather than two-arm randomization.
2. **Test price and minimum separately:** (a) $19/seat + 3-seat minimum (as written); (b) $19/seat, no minimum; optionally (c) $29/seat to bracket the ceiling.
3. **Measure behavior, not intent:** require a card or signed order at trial end, or track trial→paid conversion — the card-free trial [888fe982edf2:0-379] otherwise measures interest only.
4. **Pre-register decision criteria** before the test, tied to the existing success metric (12/20 weekly-active after four weeks [6fe6651dd0d0:0-432]) plus a conversion floor. Revisit packaging if the no-minimum arm wins; revisit price if conversion is low but usage is high.
5. **Complete the margin math:** add support and salary cost per seat before approving $19 — $4 is a floor, not a cost [888fe982edf2:0-379].
6. **Segment out the on-prem seekers** [3ff219f9c4a3:0-331] so their non-conversion isn't read as a price failure; log on-prem as a separate roadmap decision.
7. **Timeline:** beta opens June 15; first cohort converts ~June 29; run through ~mid-August for two conversion cohorts before any launch decision.

**Caveat:** all quantitative claims trace to a 12-studio exploratory sample explicitly labeled non-representative [3ff219f9c4a3:0-331] — treat them as directional only. If a competitor benchmark, retention data, or a fully loaded cost model later shows $19 is clearly mispriced, that would move this from "test first" to a firmer yes/no.
