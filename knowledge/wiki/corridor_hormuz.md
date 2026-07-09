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
last_updated: '2026-07-09T14:00:50.027190+00:00'
valid_at: '2026-07-09T14:00:25.332546+00:00'
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
The [[Strait of Hormuz]] remains a critical chokepoint for global oil supply, with recent analysis highlighting alternative crude procurement strategies due to potential disruptions. The top alternative identified is [[ADNOC]]'s [[Murban]] crude via the [[Cape of Good Hope]], priced at $98.05/bbl with a 24-day lead time and a TOPSIS score of 0.78.

## Affected Entities
- [[ADNOC]]: High exposure due to identified alternative crude supply via [[Cape of Good Hope]].
- [[Murban]]: Medium exposure as the top-ranked alternative crude grade.
- [[Cape of Good Hope]]: High exposure as the recommended bypass route.
- [[KazMunayGas]]: Medium exposure as an alternative supplier via [[Suez Canal]].
- [[NNPC]]: Medium exposure as an alternative supplier via [[Suez Canal]].
- [[Suez Canal]]: Medium exposure as a bypass route for alternative suppliers.

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 20 alternative crude sources ranked.

## Relations
| Relation      | Entity             | Type           | Strength |
|---------------|--------------------|----------------|----------|
| bypass_option | [[Cape of Good Hope]] | supply_dependency | high     |
| supply_dependency | [[ADNOC]]         | supply_dependency | high     |
| supply_dependency | [[Murban]]        | supply_dependency | medium   |
| supply_dependency | [[KazMunayGas]]   | supply_dependency | medium   |
| supply_dependency | [[NNPC]]          | supply_dependency | medium   |
| supply_dependency | [[Suez Canal]]    | supply_dependency | medium   |