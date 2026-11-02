# Data Interpreter — result 2

## Answer

Verified against the 6-row dataset (columns: priority, state, hours).

Method: keep only rows with state = resolved, then average only those with a recorded hours value. Blank hours are treated as missing (excluded), not as 0; the open ticket is excluded entirely.

Results (hours):
- high: (2 + 6) / 2 = 4.0 h (n = 2)
- low: (12 + 4) / 2 = 8.0 h (n = 2)

So low-priority resolved tickets take about twice as long on average as high-priority ones (8.0 h vs 4.0 h).

Missing values (2 of 6 rows):
1. low / open / blank hours — excluded because the ticket is not resolved (counting it as 0 would be wrong per the requirement).
2. high / resolved / blank hours — a resolved ticket with no recorded duration; excluded from the average rather than counted as 0. Had it been counted as 0, high would drop to 2.67 h (n = 3), which would understate the true resolution time.

Data limitations: each priority has only n = 2 usable observations, so the averages are indicative only and not statistically reliable; the single missing resolved duration (high) could shift the high average materially (e.g., any value above 4 h would raise it). No timestamps are available, so "hours" is assumed to be the recorded resolution duration in hours.

Chart: avg_resolution.svg is a bar chart of average resolution hours by priority (high = 4.0, low = 8.0), built from the resolved, non-blank rows only.

## Artifacts

```json
[
  {
    "name": "avg_resolution.svg",
    "url": "result-2-2.svg"
  }
]
```
