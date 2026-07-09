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
last_updated: '2026-07-09T14:12:56.963487+00:00'
valid_at: '2026-07-09T14:12:29.464072+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- grade_murban
- corridor_cape
- supplier_kazmunaygas
- corridor_suez
- supplier_nnpc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] remains a critical chokepoint for global oil supply, with recent analysis indicating alternative crude sources are being considered to mitigate risks. The top alternative identified is [[ADNOC]]'s [[Murban]] crude, routed via the [[Cape of Good Hope]], priced at $98.05/bbl with a 24-day lead time and a TOPSIS score of 0.78.

## Affected Entities
- [[ADNOC]]: High exposure due to identified as top alternative crude source.
- [[Murban]]: High exposure as the recommended alternative crude grade.
- [[Cape of Good Hope]]: Medium exposure as the recommended alternative route.
- [[KazMunayGas]]: Medium exposure as an alternative crude source via [[Suez Canal]].
- [[NNPC]]: Medium exposure as an alternative crude source via [[Suez Canal]].

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 20 alternative crude sources ranked.

## Relations
| Relation      | Entity              | Type             | Strength |
|---------------|---------------------|------------------|----------|
| supply_dependency | [[ADNOC]]           | alternative_source | high     |
| supply_dependency | [[Murban]]          | alternative_grade  | high     |
| bypass_option   | [[Cape of Good Hope]] | alternative_route | medium   |
| supply_dependency | [[KazMunayGas]]     | alternative_source | medium   |
| supply_dependency | [[NNPC]]            | alternative_source | medium   |