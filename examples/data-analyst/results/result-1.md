# Data analyst — result 1

## Text

## Answer

**Desk lamps accounted for 66.67% of March revenue.**

| Item | Value |
|---|---|
| Numerator (desk lamp revenue, March) | 1,440 |
| Denominator (total revenue, March) | 2,160 |
| Share | **66.67%** |

### SQL used
```sql
SELECT SUM(CASE WHEN product = 'Desk lamp' THEN revenue ELSE 0 END) AS desk_lamp_rev,
       SUM(revenue) AS march_total,
       ROUND(100.0 * SUM(CASE WHEN product = 'Desk lamp' THEN revenue ELSE 0 END) / SUM(revenue), 2) AS pct
FROM orders
WHERE month = '2026-03';
```

### Notes on the data
- The `orders` table has one row per order line with `month`, `product`, `quantity`, and `revenue`. Only two products exist in the data: **Desk lamp** and **Notebook**.
- `month` is stored as text in `YYYY-MM` format (values: 2026-01, 2026-02, 2026-03), so March was filtered as `'2026-03'`. My first attempt using `month = 3` returned no rows — that was a type mismatch, not an absence of March data.
- March contains only 4 order lines, so this percentage rests on a very small sample and should be read as indicative rather than stable.
- The `region` column is numeric-coded and was not needed here; no region breakdown was requested.

### Unresolved gaps
- No gaps in the calculation itself. However, the data cannot tell us *why* desk lamps dominate, nor whether "revenue" is net of returns/discounts — no such fields exist. If a different definition of March (e.g., a fiscal calendar) is intended, this answer would not apply.
