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
last_updated: '2026-07-09T14:09:19.808416+00:00'
valid_at: '2026-07-09T14:09:01.276986+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_qatarenergy
- supplier_iraqoil
- supplier_kpc
- supplier_us
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. The situation remains fluid with no immediate risk score available.

## Historical Pattern
The threat to close the [[Strait of Hormuz]] echoes the [[2019 Tanker Attacks]], where geopolitical tensions led to significant disruptions in oil transit.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure as a major supplier reliant on the strait.
- [[ADNOC]]: Medium exposure due to inventory days at risk.
- [[QatarEnergy]]: Medium exposure based on throughput dependency.
- [[Iraqi Oil Ministry]]: High exposure due to critical supply route.
- [[Kuwait Petroleum Corporation]]: Medium exposure from inventory risk.
- [[United States]]: Low exposure, but potential secondary impacts on global markets.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | medium   |
| supply_dependency| [[QatarEnergy]]        | supply_dependency  | medium   |
| supply_dependency| [[Iraqi Oil Ministry]] | supply_dependency  | high     |
| supply_dependency| [[Kuwait Petroleum Corporation]] | supply_dependency | medium   |
| threat_actor     | Iran               | threat_actor       | high     |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | high     |