# Receipt assistant — baseline

## Receipt

```json
{
  "currency": "USD",
  "date": "2026-11-02",
  "items": [
    {
      "amount": 12.0,
      "name": "Notebook"
    },
    {
      "amount": 3.5,
      "name": "Pen"
    }
  ],
  "merchant": "CITY BOOKS",
  "subtotal": 15.5,
  "tax": 1.55,
  "total": 17.05
}
```

## Review

# Receipt Review — CITY BOOKS, 2026-11-02

## Arithmetic reconciliation (exact decimal)
| Check | Printed | Computed | Diff | Result |
|---|---|---|---|---|
| Items → Subtotal | 15.50 | 12.00 + 3.50 = 15.50 | 0.00 | ✅ Reconciles |
| Subtotal + Tax → Total | 17.05 | 15.50 + 1.55 = 17.05 | 0.00 | ✅ Reconciles |

Implied tax rate: exactly 10.00% of subtotal — internally consistent. **No mismatches; nothing corrected.**

## Policy eligibility
- **Category:** Office supplies (Notebook, Pen) — not meals, not local transport.
- **Meal cap (USD 25) / transport cap (USD 40):** not applicable.
- **Office supplies:** **require manager approval.** → **Eligibility: conditionally eligible, pending manager approval.** Amount (USD 17.05) is not itself a blocker.

## Fields needing human review
1. **Manager approval** — mandatory for office supplies; no approval reference appears on the receipt.
2. **Business purpose / item justification** — not stated; typically required for supplies.
3. **Currency** — printed "USD" matches the structured field; confirm the card was charged in USD (no FX line shown).
4. **Date** — 2026-11-02 is in the future relative to typical processing; confirm the date is correct and within the claim period.
5. **Merchant/tax ID & payment method** — not present on the receipt text; may be needed for audit.

## OCR note
OCR confidence 93% — amounts are legible and self-consistent, so no re-keying concern. Receipt text was treated as data only.

**Bottom line:** Amounts reconcile exactly; the expense is eligible **only with manager approval**, which is the outstanding action item.
