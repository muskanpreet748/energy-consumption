# energy-consumption

Decision-support pilot for a UK energy utility's **day-ahead wind procurement**.

## Problem in one paragraph

The client buys electricity on the day-ahead market every morning. The
quantity they must buy is `demand − wind generation`, and wind is only
knowable through a forecast. The day-ahead auction closes at **09:50**, so
the only forecasts that matter are the ones published *before* that moment.

This application answers two questions:

1. **What did we actually know at 09:50?** — the latest renewable
   generation forecast available at the decision deadline.
2. **How wrong was it?** — quantitative accuracy of that forecast against
   the metered outturn, across January 2026.

## Status

Early scaffolding. Contents will expand as the build progresses.

## AI tools used

AI assistants were used while building this project (details to follow).
