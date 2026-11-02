# SQL analyst — baseline

## Text

**Desk lamp** has the higher revenue per unit across the full dataset: **40.00 per unit** vs. **12.00 per unit** for Notebook.

This is computed as total revenue ÷ total units (a weighted ratio), not an average of per-order ratios:

| Product | Orders | Total units | Total revenue | Revenue per unit |
|---|---|---|---|---|
| Desk lamp | 6 | 81 | 3,240 | 40.00 |
| Notebook | 6 | 143 | 1,716 | 12.00 |

SQL used:
```sql
SELECT product,
       COUNT(*) AS orders,
       SUM(quantity) AS total_units,
       SUM(revenue) AS total_revenue,
       SUM(revenue) / NULLIF(SUM(quantity), 0) AS revenue_per_unit
FROM orders
GROUP BY product
ORDER BY revenue_per_unit DESC;
```

Note: the dataset contains only two products, so the comparison is limited to Desk lamp vs. Notebook.
