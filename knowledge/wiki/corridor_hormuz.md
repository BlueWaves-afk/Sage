---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/action
risk_score: 0.854
risk_band: ACTION
factors:
  ais: 0.8533
  gdelt: 0.8971
  price: 0.9355
  sanctions: 0.6333
last_updated: '2026-07-09T18:03:52.355263+00:00'
valid_at: '2026-07-09T18:03:52.355263+00:00'
source_episodes: []
links_out:
- authority_ofac
- supplier_nioc
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_adnoc
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no deviation from the predicted timeline, indicating stable conditions in the corridor. However, recent direct military strikes between Iran and Israel near the Persian Gulf, coupled with [[OFAC]] adding [[NIOC]]-linked tanker operators to the SDN list, introduce a new layer of geopolitical and sanctions risk. No risk score is available for this signal.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.

## Signal Basis
- Confirmed military strikes between Iran and Israel near the Persian Gulf.
- [[OFAC]] adds [[NIOC]]-linked tanker operators to the SDN list.

## Relations
| Relation         | Entity               | Type               | Strength |
|------------------|----------------------|--------------------|----------|
| supply_dependency| [[NIOC]]             | supply_dependency  | high     |
| supply_dependency| [[Saudi Aramco]]     | supply_dependency  | medium   |
| supply_dependency| [[ADNOC]]            | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | medium |
| sanctions_link   | [[OFAC]]             | sanctions_link     | high     |