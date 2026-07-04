---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/critical
risk_score: 0.92
risk_band: CRITICAL
factors:
  ais: 0.3
  gdelt: 0.85
  price: 0.2
  sanctions: 0.05
last_updated: '2026-07-04T08:09:28.318767+00:00'
valid_at: '2026-07-04T08:09:28.318767+00:00'
source_episodes: []
links_out:
- event_tanker_war
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_adnoc
- supplier_nioc
- supplier_iraqoil
- port_vadinar
- port_sikka
- port_yanbu
- port_fujairah
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
The [[Strait of Hormuz]] is experiencing heightened military activity due to direct military strikes between Iran and Israel, raising the risk of closure to critical levels. This situation echoes the patterns observed during the [[Tanker War]] and the [[2019 Tanker Attacks]].

## Historical Pattern
The current situation has a clear precedent in the [[Tanker War]] with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[ADNOC]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure due to significant throughput share.
- [[Iraqi Oil Ministry]]: High exposure due to significant throughput share.
- [[Vadinar]]: High exposure as a major destination port.
- [[Sikka]]: High exposure as a major destination port.

## Signal Basis
- News report indicating direct military strikes between Iran and Israel near the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | high     |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[Iraqi Oil Ministry]] | supply_dependency  | high     |
| threat_actor     | Iran               | threat_actor       | high     |
| threat_actor     | Israel             | threat_actor       | high     |
| historical_precedent| [[Tanker War]]      | historical_precedent| high     |
| historical_precedent| [[2019 Tanker Attacks]]| historical_precedent| medium  |
| bypass_option    | [[Yanbu]]              | bypass_option      | medium   |
| bypass_option    | [[Fujairah]]           | bypass_option      | medium   |