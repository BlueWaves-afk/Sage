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
last_updated: '2026-07-09T14:12:38.096772+00:00'
valid_at: '2026-07-09T14:12:35.081569+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_qatarenergy
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no prediction error, indicating a momentary but resolved tension. The risk score is currently unavailable for this signal.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 60%.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier dependent on the corridor.
- [[ADNOC]]: medium exposure due to inventory days at risk.
- [[QatarEnergy]]: medium exposure due to strategic location and throughput dependency.

## Signal Basis
- News report indicating confirmed action crossing in the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | medium   |
| supply_dependency| [[QatarEnergy]]        | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | high     |