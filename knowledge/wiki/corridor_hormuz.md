---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/watch
risk_score: 0.3485
risk_band: WATCH
factors:
  ais: 0.0
  gdelt: 0.595
  price: 0.35
  sanctions: 0.55
last_updated: '2026-07-09T13:52:50.045112+00:00'
valid_at: '2026-07-09T13:52:50.045112+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
The [[Strait of Hormuz]] is under immediate threat of closure following recent strikes, as Iran has publicly threatened to close the strait. Additionally, the [[OFAC]] has added a tanker operator to the SDN list, increasing the complexity of navigating the strait. No risk score is available for this signal at the moment.

## Historical Pattern
This event is reminiscent of the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: medium exposure due to significant throughput share.
- [[NIOC]]: high exposure as a major supplier dependent on the strait.
- [[ADNOC]]: medium exposure due to inventory days at risk.
- [[OFAC]]: high exposure due to the addition of a tanker operator to the SDN list.

## Signal Basis
- Confirmed threat of closure based on news reports.
- [[OFAC]] adds tanker operator to SDN list.

## Relations
| Relation         | Entity           | Type               | Strength |
|------------------|------------------|--------------------|----------|
| supply_dependency| [[NIOC]]         | supply_dependency  | high     |
| supply_dependency| [[Saudi Aramco]] | supply_dependency  | medium   |
| supply_dependency| [[ADNOC]]        | supply_dependency  | medium   |
| historical_precedent| [[2019 Tanker Attacks]] | historical_precedent | high     |
| sanctions_link   | [[OFAC]]         | sanctions_link     | high     |