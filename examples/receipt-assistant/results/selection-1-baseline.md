# Receipt assistant — baseline

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

## Receipt Review — PARK DELI, 2026-11-03 (USD)

**Verdict: NOT eligible as printed — arithmetic mismatch must be resolved before approval.**

### Arithmetic check (exact decimal)
| Check | Printed | Computed | Difference | Within 0.01? |
|---|---|---|---|---|
| Subtotal (18.00 + 3.00) | 21.00 | 21.00 | 0.00 | ✅ Yes |
| Total (subtotal + tax) | 24.10 | **23.10** | **−1.00** | ❌ **No** |

The line items and subtotal reconcile perfectly. The **printed TOTAL is $1.00 higher than the sum of subtotal + tax**. Per policy, this is flagged and **not corrected** — the receipt is reported as printed.

### Policy eligibility
- **Category:** Meal (Lunch + Tea) — meals are eligible up to USD 25.00 per receipt.
- **Amount test:** Printed total 24.10 ≤ 25.00 → within cap by **0.90**.
- **Currency:** USD matches policy currency. ✅
- **Manager approval:** Not required (meal, not office supplies).
- **Date:** 2026-11-03 — present and well-formed.

⚠️ **Eligibility is conditional.** The $24.10 figure passes the cap, but it is the *unreconciled* figure. The reconciled amount would be $23.10. Either way the receipt is under $25, so the cap is not the blocker — the **reconciliation failure is**.

### Fields needing human review
1. **TOTAL (24.10)** — does not equal subtotal + tax (23.10). Off by exactly $1.00. Possible causes: a missing $1.00 line item, a mis-keyed total, or a rounding/OCR error. **Do not auto-correct.**
2. **OCR confidence: 89%** — moderate. The $1.00 gap is consistent with a digit misread (e.g., 23.10 → 24.10). Recommend re-checking the source image for the TOTAL line.
3. **Tax rate sanity** — 2.10 / 21.00 = exactly 10.0%. This is internally consistent, which supports the subtotal and tax being correct and points the error at the TOTAL line.

### Recommended action
Hold for human review. Request a corrected/legible receipt or manager sign-off on the $1.00 discrepancy. If resolved to $23.10, the receipt is eligible as a meal expense with $1.90 headroom under the $25 cap.
