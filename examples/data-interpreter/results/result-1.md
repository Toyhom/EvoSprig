# Data Interpreter — result 1

## Answer

Verified against orders.csv (4 campaigns, 1,700 total visits, 93 total conversions). Conversion rate = conversions ÷ visits × 100; Gamma has 0 visits so its rate is undefined and was excluded from division and from the chart.

| Campaign | Visits | Conversions | Conversion rate |
|---|---|---|---|
| Alpha | 1,000 | 40 | 4.00% |
| Beta | 200 | 18 | 9.00% |
| Gamma | 0 | 0 | n/a (undefined — no visits) |
| Delta | 500 | 35 | 7.00% |

Findings:
- Best conversion rate: Beta at 9.00% (18/200), the highest of the three measurable campaigns.
- Highest conversion count: Alpha with 40 conversions, but only a 4.00% rate because of its much larger traffic base (1,000 visits).
- Ranking by rate: Beta (9.00%) > Delta (7.00%) > Alpha (4.00%).
- Gamma's 0/0 is reported as n/a rather than 0% or an error; it carries no rate information.

Data limitations: the dataset is a single small snapshot with no time period, channel, or revenue/order-value data, so rates are unweighted point estimates without confidence intervals; small denominators (Beta's 200 visits) make its rate more volatile, and no statistical significance testing was performed. The chart shows rates only for Alpha, Beta, and Delta (percent units), with Gamma omitted.

## Artifacts

```json
[
  {
    "name": "conversion_rates.svg",
    "url": "result-1-2.svg"
  }
]
```
