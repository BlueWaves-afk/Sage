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
last_updated: '2026-07-09T14:06:35.062217+00:00'
valid_at: '2026-07-09T14:06:10.656878+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- corridor_cape
- supplier_kazmunaygas
- corridor_suez
- supplier_nnpc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] remains in a state of calm with no immediate risk factors identified. However, alternative crude procurement analyses indicate potential shifts in supply chain strategies.

## Affected Entities
- [[ADNOC]]: High exposure due to top-ranked alternative crude source (Murban) via [[Cape of Good Hope]].
- [[KazMunayGas]]: Medium exposure as a secondary alternative crude source via [[Suez Canal]].
- [[NNPC]]: Medium exposure as another secondary alternative crude source via [[Suez Canal]].

## Signal Basis
- System 3 procurement analysis for [[Strait of Hormuz]]: 20 alternative crude sources ranked.

## Relations
| Relation       | Entity                | Type             | Strength |
|----------------|-----------------------|------------------|----------|
| supply_dependency | [[ADNOC]]             | supply_dependency | high     |
| supply_dependency | [[KazMunayGas]]       | supply_dependency | medium   |
| supply_dependency | [[NNPC]]              | supply_dependency | medium   |
| bypass_option  | [[Cape of Good Hope]] | bypass_option     | high     |
| bypass_option  | [[Suez Canal]]        | bypass_option     | medium   |