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
last_updated: '2026-07-09T14:09:49.635086+00:00'
valid_at: '2026-07-09T14:09:24.435970+00:00'
source_episodes: []
links_out:
- supplier_aramco
- event_2019_hormuz_attacks
- supplier_nioc
- supplier_adnoc
- supplier_kpc
- supplier_iraqoil
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The event aligns with the predicted timeline, indicating a stable yet monitored situation. System 3 procurement analysis has identified 24 alternative crude sources, with [[Saudi Aramco]] (Arab Light) via [[Strait of Hormuz]] being the top option.

## Historical Pattern
The current event shows feature-overlap with the [[2019 Tanker Attacks]], though specific details and outcomes may differ.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier reliant on the corridor.
- [[ADNOC]]: medium exposure based on inventory days at risk.
- [[Kuwait Petroleum Corporation]]: medium exposure due to inventory days at risk.
- [[Iraqi Oil Ministry]]: medium exposure due to inventory days at risk.

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 24 alternative crude sources ranked.

## Relations
| Relation         | Entity                           | Type               | Strength |
|------------------|----------------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]                 | supply_dependency  | medium   |
| supply_dependency| [[NIOC]]                         | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]                        | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]]     | historical_precedent | medium |
| supply_dependency| [[Kuwait Petroleum Corporation]] | supply_dependency  | medium   |
| supply_dependency| [[Iraqi Oil Ministry]]           | supply_dependency  | medium   |