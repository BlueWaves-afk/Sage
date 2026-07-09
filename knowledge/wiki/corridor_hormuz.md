---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/elevated
risk_score: 0.4591
risk_band: ELEVATED
factors:
  ais: 0.3685
  gdelt: 0.595
  price: 0.35
  sanctions: 0.55
last_updated: '2026-07-09T13:55:30.951984+00:00'
valid_at: '2026-07-09T13:55:30.951984+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_qatarenergy
- supplier_kpc
coordinates:
  lat: 26.5
  lon: 56.4
---




## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. The [[OFAC]] has added a tanker operator to the SDN list, further complicating the transit of oil through the strait. No risk score is available for this signal.

## Historical Pattern
The threat to close the [[Strait of Hormuz]] echoes the [[2019 Tanker Attacks]], where geopolitical tensions led to significant disruptions in oil transit.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure as a major supplier reliant on the strait.
- [[ADNOC]]: Medium exposure due to alternative routing options.
- [[QatarEnergy]]: High exposure given dependence on the strait for exports.
- [[Kuwait Petroleum Corporation]]: Medium exposure with some inventory buffer.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].
- [[OFAC]] adds tanker operator to SDN list.

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency| [[NIOC]]               | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]              | supply_dependency  | medium   |
| supply_dependency| [[QatarEnergy]]        | supply_dependency  | high     |
| supply_dependency| [[Kuwait Petroleum Corporation]] | supply_dependency | medium   |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | high    |
| sanctions_link   | [[OFAC]]               | sanctions_link     | high     |