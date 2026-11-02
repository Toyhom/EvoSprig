Extract the merchant, date, currency, item amounts, subtotal, tax and total from OCR text. Use null for missing numeric values and an empty string for missing text. Keep the amounts as printed; do not invent values to make the receipt balance.


## Experience-based rules
- Reconcile printed subtotal and total against computed sums using exact decimal arithmetic and the policy's stated tolerance; report the numeric variance rather than a pass/fail alone.
- When printed figures mismatch, flag the discrepancy explicitly; never silently alter or substitute figures to force reconciliation.
- Present each arithmetic check (items→subtotal, subtotal+tax→total) in a table with printed value, computed value, and difference so the reconciliation is auditable.
- Apply policy limits by computing remaining headroom (limit minus total) and state explicit eligibility with the currency checked against the policy denomination.
- Determine approval requirements from the actual line items (e.g., office supplies trigger manager approval) rather than assuming them; state when no approval is needed and why.
- Treat OCR confidence below a typical auto-accept threshold (e.g., ~95%) as a human-review flag and recommend a visual spot-check of key fields.
- Flag dates that are in the future or otherwise implausible as potential OCR misreads and ask for confirmation rather than accepting them silently.
- When a value such as an implied tax rate is accepted as printed rather than validated against an external reference, state that limitation and its risk level.
- Conclude the review with a summary table of key fields and an explicit action/verdict (e.g., approve pending spot-check) consistent with the evidence.
- If a tool call fails with an argument-validation error, correct the arguments and retry rather than abandoning the verification step.