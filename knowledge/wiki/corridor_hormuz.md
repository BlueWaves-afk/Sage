---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/watch
risk_score: 0.266
risk_band: WATCH
factors:
  ais: 0.0
  gdelt: 0.595
  price: 0.35
  sanctions: 0.0
last_updated: '2026-07-09T14:00:03.181304+00:00'
valid_at: '2026-07-09T14:00:03.181304+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_iraqoil
- supplier_kpc
- supplier_qatarenergy
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. The situation remains fluid with no immediate risk score available.

## Historical Pattern
The threat to close the [[Strait of Hormuz]] echoes the [[2019 Tanker Attacks]], though the current situation appears more severe given the explicit threat from Iran.

## Affected Entities
- **[[Saudi Aramco]]**: High exposure due to significant throughput share.
- **[[NIOC]]**: High exposure as primary Iranian oil supplier.
- **[[ADNOC]]**: Medium exposure due to UAE's reliance on the strait.
- **[[Iraqi Oil Ministry]]**: High exposure given Iraq's dependence on Hormuz for oil exports.
- **[[Kuwait Petroleum Corporation]]**: Medium exposure due to Kuwait's export reliance.
- **[[QatarEnergy]]**: High exposure as Qatar's primary export route.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].

## Relations
| Relation         | Entity                 | Type               | Strength |
|------------------|------------------------|--------------------|----------|
| threat_actor     | Iran               | geopolitical_actor | high     |
| supply_dependency| [[Saudi Aramco]]       | supplier           | high     |
| supply_dependency| [[NIOC]]               | supplier           | high     |
| supply_dependency| [[ADNOC]]              | supplier           | medium   |
| supply_dependency| [[Iraqi Oil Ministry]]| supplier           | high     |
| supply_dependency| [[Kuwait Petroleum Corporation]]| supplier | medium |
| supply_dependency| [[QatarEnergy]]        | supplier           | high     |