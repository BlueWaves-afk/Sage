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
last_updated: '2026-07-09T14:09:42.813591+00:00'
valid_at: '2026-07-09T14:09:17.713229+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- corridor_cape
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- corridor_suez
- supplier_kazmunaygas
- supplier_nnpc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The event aligns with the predicted timeline, indicating a stable yet monitored situation. System 3 procurement analysis has identified 20 alternative crude sources, with [[ADNOC]] (Murban) via [[Cape of Good Hope]] being the top option.

## Historical Pattern
The current event shows feature-overlap with the [[2019 Tanker Attacks]], though specific details and outcomes may differ.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier reliant on the corridor.
- [[ADNOC]]: medium exposure based on inventory days at risk.

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 20 alternative crude sources ranked.

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | medium   |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | medium |
| bypass_option    | [[Cape of Good Hope]]  | bypass_option      | medium   |
| bypass_option    | [[Suez Canal]]         | bypass_option      | medium   |
| supply_dependency| [[KazMunayGas]]        | supply_dependency  | medium   |
| supply_dependency| [[NNPC]]               | supply_dependency  | medium   |