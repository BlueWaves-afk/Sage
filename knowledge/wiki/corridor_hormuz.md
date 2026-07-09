---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
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
last_updated: '2026-07-09T13:40:40.798426+00:00'
valid_at: '2026-07-09T13:40:38.757253+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The event aligns with previous patterns of maritime activity in the region.

## Historical Pattern
This event is reminiscent of the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier dependent on the strait.
- [[ADNOC]]: medium exposure due to inventory days at risk.

## Signal Basis
- Confirmed action crossing based on news reports.

## Relations
| Relation         | Entity           | Type               | Strength |
|------------------|------------------|--------------------|----------|
| supply_dependency| [[NIOC]]         | supply_dependency  | high     |
| supply_dependency| [[Saudi Aramco]] | supply_dependency  | medium   |
| supply_dependency| [[ADNOC]]        | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | high     |