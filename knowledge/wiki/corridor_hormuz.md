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
last_updated: '2026-07-09T13:59:03.866079+00:00'
valid_at: '2026-07-09T13:59:01.342274+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_kpc
- supplier_qatarenergy
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no deviation from the predicted timeline, indicating stable yet critical maritime activity in the region.

## Historical Pattern
The current situation mirrors the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: high exposure due to significant throughput share.
- [[NIOC]]: high exposure due to critical supply dependency.
- [[ADNOC]]: medium exposure based on inventory days at risk.
- [[Kuwait Petroleum Corporation]]: medium exposure due to regional supply chains.
- [[QatarEnergy]]: high exposure from strategic location and throughput.

## Signal Basis
- News report confirming the action crossing in the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                   | Type               | Strength |
|------------------|--------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]         | supply_dependency | high     |
| supply_dependency| [[NIOC]]                 | supply_dependency | high     |
| supply_dependency| [[ADNOC]]                | supply_dependency | medium   |
| supply_dependency| [[Kuwait Petroleum Corporation]] | supply_dependency | medium |
| supply_dependency| [[QatarEnergy]]          | supply_dependency | high     |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | high |