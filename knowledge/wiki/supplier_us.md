---
entity_id: supplier_us
aliases:
- United States
entity_type: Supplier
tags:
- sage/supplier
- risk/calm
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-07-09T19:04:54.537896+00:00'
valid_at: '2026-07-09T19:04:37.298619+00:00'
source_episodes: []
links_out:
- corridor_suez
coordinates: {}
---


## Current Assessment
The [[United States]] remains a significant and stable supplier in the global oil market, with recent procurement analysis indicating alternative crude sources via the [[Suez Canal]].

## Affected Entities
- [[United States]]: High exposure due to potential shifts in export routes and supply chain dependencies.
- [[Suez Canal]]: Medium exposure as a critical corridor for U.S. oil exports.

## Signal Basis
- System 3 procurement analysis for United States.

## Relations
| Relation        | Entity                 | Type               | Strength |
|-----------------|------------------------|--------------------|----------|
| supply_dependency | [[United States]]      | supply_dependency  | high     |
| corridor         | [[Suez Canal]]         | corridor           | medium   |