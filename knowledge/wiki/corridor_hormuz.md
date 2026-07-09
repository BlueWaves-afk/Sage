---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/calm
risk_score: 0.0875
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.35
  sanctions: 0.0
last_updated: '2026-07-09T13:55:30.938271+00:00'
valid_at: '2026-07-09T13:55:30.938271+00:00'
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
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The situation remains calm with no immediate threat to the corridor.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[Saudi Aramco]]: low exposure due to diversified export routes.
- [[NIOC]]: medium exposure as a significant portion of exports pass through the [[Strait of Hormuz]].
- [[ADNOC]]: low exposure due to alternative shipping routes.

## Signal Basis
- News report confirming the action crossing in the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[NIOC]]               | supply_dependency  | medium   |
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | low      |
| supply_dependency| [[ADNOC]]              | supply_dependency  | low      |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | medium |