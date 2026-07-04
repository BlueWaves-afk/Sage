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
last_updated: '2026-07-04T08:31:46.731566+00:00'
valid_at: '2026-07-04T08:31:17.318109+00:00'
source_episodes: []
links_out:
- supplier_iraqoil
- grade_basrah_medium
- corridor_hormuz
- supplier_adnoc
- supplier_qatarenergy
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] is currently evaluating alternative crude sources to optimize procurement, with [[Iraqi Oil Ministry]]'s [[Basrah Medium]] via the [[Strait of Hormuz]] identified as the top option. This assessment is based on a detailed System 3 procurement analysis ranking 24 alternative sources.

## Affected Entities
- [[Iraqi Oil Ministry]]: High exposure due to proposed increased supply of [[Basrah Medium]].
- [[Strait of Hormuz]]: High exposure as the primary transit route for the top crude option.
- [[ADNOC]]: Medium exposure as an alternative supplier via [[Strait of Hormuz]].
- [[QatarEnergy]]: Medium exposure as another alternative supplier via [[Strait of Hormuz]].

## Signal Basis
- System 3 procurement analysis for Jamnagar Refinery.

## Relations
| Relation        | Entity                 | Type             | Strength |
|-----------------|------------------------|------------------|----------|
| supply_dependency | [[Iraqi Oil Ministry]] | supply_dependency | high     |
| supply_dependency | [[Strait of Hormuz]]   | supply_dependency | high     |
| supply_dependency | [[ADNOC]]              | supply_dependency | medium   |
| supply_dependency | [[QatarEnergy]]        | supply_dependency | medium   |