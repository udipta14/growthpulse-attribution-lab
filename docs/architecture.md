# Architecture

```text
Synthetic customer journeys
          │
          ▼
Python pipeline ──► validation / quarantine ──► attribution & cohorts
          │                                      │
          ├──► demo input sample                 ├──► trend + weekday forecast
          │                                      └──► anomaly flags
          └──────────────────────────────────────────► app/data/demo.json
                                                        │
                                                        ▼
                                            Static browser dashboard
```

The pipeline has one deterministic seed so every run is reproducible. In a real deployment, source extracts would be staged in object storage or a lakehouse, transformed with SQL/Spark, and promoted only after data-quality checks pass. The included PySpark example sketches that adaptation without pretending a Databricks job was run here.

## Data contract

Each touchpoint has `event_id`, `user_id`, `event_date`, `channel`, `campaign`, `medium`, and `landing_page`. Paid rows require a campaign and medium. Orders have `order_id`, `user_id`, `order_date`, `revenue_inr`, and `customer_type`. Attribution assigns each order's value to the first, last, or equally weighted touches in its path.
