---
entity_id: refinery_jamnagar
aliases:
- Jamnagar Refinery
entity_type: Refinery
tags:
- sage/refinery
- risk/calm
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-07-09T18:17:01.084383+00:00'
valid_at: '2026-07-09T18:16:21.065364+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- grade_murban
- corridor_cape
- supplier_kazmunaygas
- corridor_suez
- supplier_rosneft
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] is currently evaluating alternative crude sources, with [[ADNOC]]'s [[Murban]] crude via the [[Cape of Good Hope]] emerging as the top option due to its favorable cost, lead time, and grade compatibility. The refinery is also considering [[KazMunayGas]] via the [[Suez Canal]] and [[Rosneft]] via the ESPO Pipeline as viable alternatives.

## Affected Entities
- [[ADNOC]]: high exposure due to being the top-ranked crude supplier.
- [[Murban]]: high exposure as the preferred crude grade.
- [[Cape of Good Hope]]: medium exposure as the recommended shipping route.
- [[KazMunayGas]]: medium exposure as an alternative supplier.
- [[Rosneft]]: medium exposure as an alternative supplier.
- [[Suez Canal]]: medium exposure as an alternative shipping route.

## Signal Basis
- System 3 procurement analysis for Jamnagar Refinery.

## Relations
| Relation        | Entity             | Type               | Strength |
|-----------------|--------------------|--------------------|----------|
| supply_dependency | [[ADNOC]]         | supply_dependency  | high     |
| supply_dependency | [[Murban]]         | supply_dependency  | high     |
| bypass_option   | [[Cape of Good Hope]] | bypass_option     | medium   |
| supply_dependency | [[KazMunayGas]]    | supply_dependency  | medium   |
| supply_dependency | [[Rosneft]]        | supply_dependency  | medium   |
| bypass_option   | [[Suez Canal]]     | bypass_option      | medium   |