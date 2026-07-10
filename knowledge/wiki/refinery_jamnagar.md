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
last_updated: '2026-07-10T19:01:58.646313+00:00'
valid_at: '2026-07-10T19:01:42.874057+00:00'
source_episodes: []
links_out:
- supplier_us
- corridor_suez
- supplier_adnoc
- grade_murban
- corridor_cape
- supplier_kazmunaygas
- supplier_rosneft
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] has identified two alternative crude sources, reducing its supply chain vulnerability. The top option is from the [[United States]] via the [[Suez Canal]], with a grade compatibility score of 1.00 and a TOPSIS score of 0.50.

## Affected Entities
- [[ADNOC]]: reduced exposure due to new alternative crude sources.
- [[Murban]]: reduced exposure as the preferred crude grade.
- [[Cape of Good Hope]]: reduced exposure as the recommended shipping route.
- [[KazMunayGas]]: reduced exposure as an alternative supplier.
- [[Rosneft]]: reduced exposure as an alternative supplier.
- [[Suez Canal]]: increased exposure as the primary alternative shipping route.
- [[United States]]: new exposure as a top-ranked alternative crude supplier.
- Indian Oil Corporation Limited: new exposure as an alternative crude supplier.

## Signal Basis
- System 3 procurement analysis for Jamnagar Refinery.

## Relations
| Relation        | Entity                                | Type               | Strength |
|-----------------|---------------------------------------|--------------------|----------|
| supply_dependency | [[ADNOC]]                            | supply_dependency  | high     |
| supply_dependency | [[Murban]]                            | supply_dependency  | high     |
| bypass_option   | [[Cape of Good Hope]]                 | bypass_option      | medium   |
| supply_dependency | [[KazMunayGas]]                       | supply_dependency  | medium   |
| supply_dependency | [[Rosneft]]                           | supply_dependency  | medium   |
| bypass_option   | [[Suez Canal]]                        | bypass_option      | high     |
| supply_dependency | [[United States]]                     | supply_dependency  | high     |
| supply_dependency | Indian Oil Corporation Limited    | supply_dependency  | medium   |