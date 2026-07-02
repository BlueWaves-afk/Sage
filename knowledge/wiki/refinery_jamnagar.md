---
entity_id: refinery_jamnagar
aliases:
- Jamnagar
entity_type: Refinery
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-07-02T16:18:13.907281+00:00'
valid_at: '2026-07-02T16:17:34.991607+00:00'
source_episodes: []
links_out:
- corridor_hormuz
- supplier_aramco
- supplier_kpc
- supplier_iraqoil
- event_tanker_war
- event_2019_hormuz_attacks
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] continues to rely heavily on crude imports via the [[Strait of Hormuz]], with [[Saudi Aramco]], [[Kuwait Petroleum Corporation]], and [[Iraqi Oil Ministry]] as top alternative suppliers. The refinery's high complexity allows it to adapt to various crude grades, though its primary exposure remains through the [[Strait of Hormuz]].

## Historical Pattern
The refinery's dependency on [[Strait of Hormuz]] has precedents in the [[Tanker War]] (80% feature-overlap) and the [[2019 Tanker Attacks]] (75% feature-overlap).

## Affected Entities
- **[[Saudi Aramco]]**: High exposure due to primary crude supplier.
- **[[Kuwait Petroleum Corporation]]**: Medium exposure as an alternative supplier.
- **[[Iraqi Oil Ministry]]**: Medium exposure as an alternative supplier.
- **[[Strait of Hormuz]]**: High exposure due to primary supply route.

## Signal Basis
- System 3 procurement analysis for Jamnagar: 18 alternative crude sources ranked.

## Relations
| Relation         | Entity                        | Type               | Strength |
|------------------|-------------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]              | supply_dependency  | high     |
| supply_dependency| [[Kuwait Petroleum Corporation]]| supply_dependency  | medium   |
| supply_dependency| [[Iraqi Oil Ministry]]       | supply_dependency  | medium   |
| supply_dependency| [[Strait of Hormuz]]          | supply_dependency  | high     |