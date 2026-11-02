# Research team — result 2

## Text

# Founder Briefing — Review Desk

**Evidence base:** three documents only — `launch-plan`, `pricing`, `customer-feedback`. No budget, runway, staffing, or decision-log documents were retrieved. Everything below is bounded by those three sources; gaps are flagged, not filled.

## 1. Launch date

**Facts**
- Planned beta opens **June 15** with **20 design studios** [6fe6651dd0d0:0-432].
- V1 scope: email import, comment threads, approval status [6fe6651dd0d0:0-432].
- Success metric: **12 studios using the inbox weekly after four weeks** [6fe6651dd0d0:0-432].
- Team is **two engineers and one designer**; **email import integration is the largest schedule risk** [6fe6651dd0d0:0-432].

**Status: tentative, not confirmed.** The date is "planned" only — no approval, sign-off, or go/no-go gate is recorded [6fe6651dd0d0:0-432].

**Unknowns**
- No year stated for June 15; no general-availability date.
- No contingency date, buffer, or quantified slip estimate for the email import risk, and no named owner [6fe6651dd0d0:0-432].
- No definition of "weekly" for the success metric.
- No confirmation that the 20 studios are recruited or committed, or how they were selected [6fe6651dd0d0:0-432].

## 2. Pricing

**Facts**
- Proposed **Team plan: $19 per seat per month, minimum three seats** [888fe982edf2:0-379].
- **14-day trial, no payment card required** [888fe982edf2:0-379].
- Estimated service cost **$4 per active seat per month**, *before* support and salaries [888fe982edf2:0-379].
- **The proposal has not been approved** [888fe982edf2:0-379].
- 5 of 12 interviewed studios were willing to try $19/seat/month [3ff219f9c4a3:0-331].

**Unknowns**
- **Currency is unspecified** — only "$" is used [888fe982edf2:0-379].
- No gross margin: the $4 excludes support and salaries, so true unit economics are unknown [888fe982edf2:0-379].
- No other tiers, annual plan, discounts, overage terms, or trial-expiry behaviour documented.
- No beta pricing terms — whether the 20 studios pay, and at what rate, is not stated.
- Willingness to pay is explicitly untested: the doc says it "needs a live pricing test" [888fe982edf2:0-379]. "Willing to try" is not a purchase commitment [3ff219f9c4a3:0-331].

## 3. Customer concerns

**Facts**
- 12 independent design studios interviewed [3ff219f9c4a3:0-331].
- **8 of 12 asked for a shared review inbox**; **6 said scattered client feedback slows approval** [3ff219f9c4a3:0-331].
- **3 of 12 asked for an on-premises edition** [3ff219f9c4a3:0-331] — currently **outside beta scope** [6fe6651dd0d0:0-432].
- Interviews were **exploratory, not a representative survey** [3ff219f9c4a3:0-331].

**Unknowns**
- No recorded objections on price, data security, or migration.
- No reasons recorded for the 4 studios who did not want a shared inbox, or the 7 not willing to try $19.
- No evidence on on-prem demand beyond a count of three; no decision on whether those studios are deferred, declined, or lost.
- The 3-seat minimum is untested — it may be the binding constraint for small studios rather than the price.

**Note on evidence quality:** the sample is 12 studios and self-described as non-representative [3ff219f9c4a3:0-331]. Treat demand and pricing signals as directional only.

## Decisions needed

| # | Decision | Why it's open |
|---|---|---|
| 1 | **Approve, amend, or reject the $19 / 3-seat-minimum Team plan** | Explicitly unapproved [888fe982edf2:0-379] |
| 2 | **Confirm or move the June 15 beta date; set a go/no-go checkpoint** on email import | Date planned only; top risk unquantified and unowned [6fe6651dd0d0:0-432] |
| 3 | **Design the live pricing test** — cohort, price variants, pass/fail threshold — and decide whether it gates launch or runs in parallel | Doc requires a test but specifies none [888fe982edf2:0-379] |
| 4 | **Choose the on-premises position** (defer with a date, decline, or scope) | 3/12 asked; out of scope with no recorded decision [3ff219f9c4a3:0-331][6fe6651dd0d0:0-432] |
| 5 | **Set beta commercial terms** for the 20 studios (free, discounted, or full price) | Undocumented; shapes the June 15 launch [6fe6651dd0d0:0-432] |
| 6 | **Confirm the currency** and whether multi-currency is needed | "$" is ambiguous [888fe982edf2:0-379] |

**Recommended sequence:** decisions 1 and 2 gate everything else. Design the pricing test (3) before June 15 so the beta doubles as the willingness-to-pay experiment the pricing doc calls for [888fe982edf2:0-379]. Give the on-prem question (4) an explicit answer rather than silence — it is the only stated feature gap with named demand [3ff219f9c4a3:0-331].

**Caveat:** budget, runway, and staffing data were searched for and not found. If a finance model, risk register, or approval log exists outside these three documents, decisions 1, 2, and 3 may already be partly answered — verify before the founder meeting.
