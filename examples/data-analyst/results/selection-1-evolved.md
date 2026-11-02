# SQL analyst — evolved

## Text

## Revenue per unit by product (whole dataset)

| Product | Orders | Total units | Total revenue | Revenue per unit |
|---|---|---|---|---|
| **Desk lamp** | 6 | 81 | $3,240 | **$40.00** |
| Notebook | 6 | 143 | $1,716 | $12.00 |

**Answer: the Desk lamp** has the higher revenue per unit — $40.00 vs. $12.00 for the Notebook, more than 3× higher.

Note that the Notebook actually sells far more units (143 vs. 81) and appears in the same number of orders, but at a much lower price point, so its total revenue ($1,716) is only about half the Desk lamp's ($3,240).

**SQL used:**
```sql
SELECT product,
       COUNT(*) AS orders,
       SUM(quantity) AS total_units,
       SUM(revenue) AS total_revenue,
       ROUND(SUM(revenue) / NULLIF(SUM(quantity), 0), 2) AS revenue_per_unit
FROM orders
GROUP BY product
ORDER BY revenue_per_unit DESC;
```

This uses the ratio of totals (total revenue ÷ total units), as requested, rather than averaging per-order ratios — so large orders are weighted by their actual volume.

**Caveats:** The dataset is small (12 orders total, 6 per product), and the `product` column is stored as a numeric type while holding text values like "Desk lamp" — a schema mismatch worth flagging. The per-unit figures are exact round numbers here, which suggests they may be fixed list prices rather than realized prices.
