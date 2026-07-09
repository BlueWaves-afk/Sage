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
last_updated: '2026-07-09T14:09:54.475245+00:00'
valid_at: '2026-07-09T14:09:01.276986+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_kpc
- supplier_iraqoil
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The [[OFAC]] has added a tanker operator to the SDN list, increasing the complexity of transit operations through the corridor.

## Historical Pattern
The current event shows feature-overlap with the [[2019 Tanker Attacks]], though specific details and outcomes may differ.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier reliant on the corridor.
- [[ADNOC]]: medium exposure based on inventory days at risk.
- [[Kuwait Petroleum Corporation]]: medium exposure due to inventory days at risk.
- [[Iraqi Oil Ministry]]: medium exposure due to inventory days at risk.

## Signal Basis
- [[OFAC]] sanctions signal: tanker operator added to SDN list.

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
| supply_dependency | [[Saudi Aramco]] | supply_dependency | medium |
| supply_dependency | [[NIOC]] | supply_dependency | high |
| supply_dependency | [[ADNOC]] | supply_dependency | medium |
| supply_dependency | [[Kuwait Petroleum Corporation]] | supply_dependency | medium |
| supply_dependency | [[Iraqi Oil Ministry]] | supply_dependency | medium |
| sanctions_link | [[OFAC]] | sanctions_link | high |