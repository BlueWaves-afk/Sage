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
last_updated: '2026-07-09T18:03:55.816803+00:00'
valid_at: '2026-07-09T18:03:52.355263+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_nioc
- supplier_aramco
- supplier_adnoc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no deviation from the predicted timeline, indicating stable conditions in the corridor. However, recent direct military strikes between Iran and Israel near the Persian Gulf introduce a new layer of geopolitical risk. No risk score is available for this signal.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]].
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.

## Signal Basis
- Confirmed military strikes between Iran and Israel near the Persian Gulf.

## Relations
| Relation         | Entity               | Type               | Strength |
|------------------|----------------------|--------------------|----------|
| supply_dependency| [[NIOC]]             | supply_dependency  | high     |
| supply_dependency| [[Saudi Aramco]]     | supply_dependency  | medium   |
| supply_dependency| [[ADNOC]]            | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | medium |