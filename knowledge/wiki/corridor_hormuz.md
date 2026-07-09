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
last_updated: '2026-07-09T13:56:13.818579+00:00'
valid_at: '2026-07-09T13:55:47.284198+00:00'
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
The [[Strait of Hormuz]] has experienced a confirmed action crossing with no risk score available for this signal. The situation remains calm with no immediate threat to the corridor. Procurement analysis indicates viable alternative crude sources, with [[ADNOC]] (Murban) via [[Cape of Good Hope]] being the top option.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[Saudi Aramco]]: low exposure due to diversified export routes.
- [[NIOC]]: medium exposure as a significant portion of exports pass through the [[Strait of Hormuz]].
- [[ADNOC]]: low exposure due to alternative shipping routes.

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 20 alternative crude sources ranked.

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[NIOC]]               | supply_dependency  | medium   |
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | low      |
| supply_dependency| [[ADNOC]]              | supply_dependency  | low      |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | medium |
| bypass_option    | [[Cape of Good Hope]]  | bypass_option      | high     |
| bypass_option    | [[Suez Canal]]         | bypass_option      | medium   |
| supply_dependency| [[KazMunayGas]]        | supply_dependency  | low      |
| supply_dependency| [[NNPC]]               | supply_dependency  | low      |