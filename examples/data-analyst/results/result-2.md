# Data analyst — result 2

## Text

**March had the larger month-over-month percentage increase: +37.06% vs. +29.18% in February.**

| Month | Total revenue | Previous month | MoM growth |
|---|---|---|---|
| 2026-01 | 1,220 | — | — |
| 2026-02 | 1,576 | 1,220 | **+29.18%** |
| 2026-03 | 2,160 | 1,576 | **+37.06%** |

In plain terms: revenue rose from 1,220 to 1,576 in February (+356), then from 1,576 to 2,160 in March (+584). March's increase was both larger in absolute terms and larger in percentage terms, so growth accelerated.

SQL used:
```sql
WITH m AS (SELECT month, SUM(revenue) AS rev FROM orders GROUP BY month)
SELECT month, rev,
       LAG(rev) OVER (ORDER BY month) AS prev_rev,
       ROUND(100.0 * (rev - LAG(rev) OVER (ORDER BY month)) / LAG(rev) OVER (ORDER BY month), 2) AS mom_growth_pct
FROM m ORDER BY month;
```

Caveats: the `orders` table has only 4 orders per month, so these percentages rest on a very small sample and should be treated as indicative rather than statistically robust. The `month` column is stored as a numeric value formatted like `2026-01`; I grouped on it directly, which is valid as long as each value represents a single calendar month.
