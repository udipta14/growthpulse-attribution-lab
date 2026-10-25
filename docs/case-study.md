# Case study: make attribution disagreements explainable

## Problem

Channel reports often assign credit using different rules. A customer may first discover a product through paid social, return through search, and convert later. The resulting channel numbers can disagree even when the underlying journey is the same.

## Product approach

GrowthPulse keeps one synthetic touchpoint and order model, then applies first-touch, last-touch, and linear credit rules to the same paths. Users can compare attributed orders and revenue by channel, inspect example journeys, review cohort retention, and see a simple forecast alongside data-quality checks.

## Data flow

1. Generate deterministic, synthetic campaign touchpoints and orders.
2. Quarantine missing paid UTMs, duplicate event IDs, and invalid dates.
3. Aggregate spend, sessions, orders, and revenue by day and channel.
4. Apply each attribution rule and generate cohort, forecast, anomaly, and QA outputs.
5. Render the dashboard from a versionable JSON snapshot.

## What makes the result useful

- Attribution differences are shown as a modeling choice, not a source-data discrepancy.
- The sample paths make the model's behavior visible to non-technical stakeholders.
- Quarantined rows and anomaly flags point to specific review steps.
- The pipeline can be regenerated without any private or production dataset.

## Limits and next steps

The data is synthetic, the forecast is a baseline, and the anomaly rules are illustrative. A production version would require approved data access, agreed metric definitions, consent-aware identity rules, warehouse-specific transformations, and validation against experimentation or incrementality studies.
