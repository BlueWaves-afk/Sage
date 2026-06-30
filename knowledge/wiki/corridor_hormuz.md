---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
risk_score: 0.55
risk_band: ELEVATED
factors:
  ais: 0.55
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-06-30T10:24:41.370985+00:00'
valid_at: '2026-06-30T10:24:41.370985+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_adnoc
- supplier_nioc
- supplier_iraqoil
- port_vadinar
- port_sikka
coordinates:
  lat: 26.5
  lon: 56.4
---






## Current Assessment
The [[Strait of Hormuz]] is experiencing heightened naval activity, with IRGC fast-attack craft shadowing a crude tanker convoy near Larak Island. This development suggests an increased risk of potential disruptions in the strait.

## Historical Pattern
The current situation bears resemblance to the [[2019 Tanker Attacks]], with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: high exposure due to significant throughput share.
- [[ADNOC]]: high exposure due to significant throughput share.
- [[NIOC]]: high exposure due to significant throughput share.
- [[Iraqi Oil Ministry]]: high exposure due to significant throughput share.
- [[Vadinar]]: high exposure as a major destination port.
- [[Sikka]]: high exposure as a major destination port.

## Signal Basis
- Reuters report on IRGC activity in the [[Strait of Hormuz]].

## Relations
| Relation        | Entity                 | Type               | Strength |
|---              |---                     |---                 |---       |
| threat_actor    | IRGC               | threat_actor       | high     |
| supply_dependency | [[Saudi Aramco]]       | supply_dependency  | high     |
| supply_dependency | [[ADNOC]]              | supply_dependency  | high     |
| supply_dependency | [[NIOC]]               | supply_dependency  | high     |
| supply_dependency | [[Iraqi Oil Ministry]] | supply_dependency  | high     |
| supply_dependency | [[Vadinar]]            | supply_dependency  | high     |
| supply_dependency | [[Sikka]]              | supply_dependency  | high     |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | medium |