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
last_updated: '2026-07-09T14:06:44.476698+00:00'
valid_at: '2026-07-09T14:05:54.111731+00:00'
source_episodes: []
links_out:
- authority_ofac
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
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. This development significantly elevates geopolitical tensions in the region. Additionally, the [[OFAC]] has added a tanker operator to the SDN list, further complicating the transit of oil through the strait.

## Historical Pattern
The situation echoes the [[2019 Tanker Attacks]], where similar threats and actions led to heightened global oil market volatility.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure as a major supplier dependent on the strait.
- [[ADNOC]]: Medium exposure due to regional supply chain dependencies.
- [[Kuwait Petroleum Corporation]]: Medium exposure based on inventory days at risk.
- [[QatarEnergy]]: Medium exposure due to strategic location and supply routes.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].
- [[OFAC]] adds tanker operator to SDN list.

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| threat_actor     | Iran               | threat_actor       | high     |
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | medium   |
| supply_dependency| [[Kuwait Petroleum Corporation]] | supply_dependency | medium   |
| supply_dependency| [[QatarEnergy]]        | supply_dependency  | medium   |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | high    |
| sanctions_link   | [[OFAC]]               | sanctions_link     | high     |