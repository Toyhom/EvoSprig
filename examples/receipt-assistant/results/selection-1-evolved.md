# Receipt assistant — evolved

## Receipt

```json
{
  "currency": "USD",
  "date": "2026-11-03",
  "items": [
    {
      "amount": 18.0,
      "name": "Lunch"
    },
    {
      "amount": 3.0,
      "name": "Tea"
    }
  ],
  "merchant": "PARK DELI",
  "subtotal": 21.0,
  "tax": 2.1,
  "total": 24.1
}
```

## Review

# Receipt Review — PARK DELI

## 1. Arithmetic reconciliation (exact decimal, tolerance 0.01)

| Check | Printed | Computed | Difference | Within 0.01? |
|---|---|---|---|---|
| Items → Subtotal (18.00 + 3.00) | 21.00 | 21.00 | 0.00 | ✅ Yes |
| Subtotal + Tax → Total (21.00 + 2.10) | 24.10 | **23.10** | **+1.00** | ❌ **No** |

**Mismatch flagged (not corrected):** the printed TOTAL of **24.10** exceeds the computed subtotal-plus-tax of **23.10** by **1.00 USD**. This is 100× the policy tolerance. The printed figures are reported as-is; no substitution has been made. Possible causes: a missing line item (~1.00), a misread tax or total digit, or a service charge not itemized. This must be resolved by a human before payment.

## 2. Policy eligibility

- **Category:** Meals (Lunch, Tea) — eligible category.
- **Currency:** USD — matches the policy denomination (USD). ✅
- **Limit:** USD 25.00 per receipt.
  - Against printed total 24.10 → headroom **+0.90 USD** (within limit).
  - Against computed total 23.10 → headroom **+1.90 USD** (within limit).
  - Either way the amount is under the cap, but the total is **not yet verified**, so eligibility is conditional.
- **Approval:** No office supplies on the receipt, so the manager-approval rule is **not triggered**. No approval needed on category grounds.

## 3. Fields needing human review

| Field | Issue | Action |
|---|---|---|
| **TOTAL** | Printed 24.10 vs computed 23.10 (Δ 1.00) | Reconcile against itemized receipt; do not pay until explained |
| **Date** | 2026-11-03 is in the future / implausible | Likely OCR misread (e.g., 2025-11-03 or 2026-01-03); confirm actual date |
| **OCR confidence** | 89% — below the ~95% auto-accept threshold | Visual spot-check of merchant, date, tax, and total |
| **Tax** | 2.10 accepted as printed; implied rate 10.00% not validated against any external reference | Low risk, but unverified — confirm tax line visually |

## 4. Summary

| Field | Value | Status |
|---|---|---|
| Merchant | PARK DELI | OK (spot-check) |
| Date | 2026-11-03 | ⚠️ Implausible — confirm |
| Currency | USD | ✅ Matches policy |
| Items | Lunch 18.00, Tea 3.00 | ✅ Sum to subtotal |
| Subtotal | 21.00 | ✅ Reconciles |
| Tax | 2.10 (10.00% implied) | ⚠️ Unverified rate |
| Total | 24.10 (computed 23.10) | ❌ **Mismatch +1.00** |
| Limit check | 24.10 ≤ 25.00 (headroom 0.90) | ✅ Under cap |
| Approval | Not required (no office supplies) | ✅ |

**Verdict: HOLD — do not approve yet.** The receipt is within the USD 25 meal limit and needs no manager approval, but the printed total fails reconciliation by 1.00 USD and the date is implausible, with OCR confidence at 89%. **Action:** obtain a corrected/legible receipt or itemization explaining the 1.00 difference and confirm the date; then re-run reconciliation. If the corrected total remains ≤ 25.00 USD and reconciles within 0.01, it can be approved without further escalation.
