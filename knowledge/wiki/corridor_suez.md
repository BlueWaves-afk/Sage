---
entity_id: corridor_suez
aliases:
- Suez Canal
entity_type: Corridor
tags:
- sage/corridor
- risk/calm
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-07-09T19:04:54.240878+00:00'
valid_at: '2026-07-09T19:04:37.312116+00:00'
source_episodes: []
links_out:
- supplier_us
coordinates:
  lat: 30.7
  lon: 32.3
---


## Current Assessment
The [[Suez Canal]] is currently under evaluation for alternative crude procurement options, with the [[United States]] emerging as the top candidate at $99.00/bbl with a 28-day lead time and a grade compatibility score of 0.50. This assessment is based on a System 3 procurement analysis.

## Affected Entities
- [[United States]]: High exposure due to being the top-ranked alternative crude source.
- [[Suez Canal]]: Medium exposure as the transit route for the alternative crude sources.

## Signal Basis
- System 3 procurement analysis for Suez Canal.

## Relations
| Relation        | Entity              | Type               | Strength |
|-----------------|---------------------|--------------------|----------|
| supply_dependency | [[United States]]   | supply_dependency  | high     |
| supply_dependency | [[Suez Canal]]      | supply_dependency  | medium   |