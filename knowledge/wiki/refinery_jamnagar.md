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
last_updated: '2026-07-04T08:35:55.733614+00:00'
valid_at: '2026-07-04T08:35:23.717468+00:00'
source_episodes: []
links_out:
- supplier_aramco
- grade_arab_light
- corridor_hormuz
- supplier_iraqoil
- grade_basrah_medium
- supplier_adnoc
- supplier_qatarenergy
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] is now prioritizing [[Saudi Aramco]]'s [[Arab Light]] crude via the [[Strait of Hormuz]] as the top procurement option, based on the latest System 3 procurement analysis. This shift is driven by the optimal cost, lead time, and grade compatibility metrics.

## Contradiction Note
The new signal contradicts the previous assessment, which identified [[Iraqi Oil Ministry]]'s [[Basrah Medium]] as the top crude option. The contradiction arises from updated procurement metrics favoring [[Saudi Aramco]]'s [[Arab Light]].

## Affected Entities
- [[Saudi Aramco]]: High exposure due to the new top crude option.
- [[Strait of Hormuz]]: High exposure as the primary transit route for the top crude option.
- [[Iraqi Oil Ministry]]: Medium exposure as the previous top crude option.
- [[ADNOC]]: Medium exposure as an alternative supplier via [[Strait of Hormuz]].
- [[QatarEnergy]]: Low exposure as a less preferred alternative supplier via [[Strait of Hormuz]].

## Signal Basis
- System 3 procurement analysis for Jamnagar Refinery.

## Relations
| Relation        | Entity                 | Type             | Strength |
|-----------------|------------------------|------------------|----------|
| supply_dependency | [[Saudi Aramco]]      | supply_dependency | high     |
| supply_dependency | [[Strait of Hormuz]]   | supply_dependency | high     |
| supply_dependency | [[Iraqi Oil Ministry]] | supply_dependency | medium   |
| supply_dependency | [[ADNOC]]              | supply_dependency | medium   |
| supply_dependency | [[QatarEnergy]]        | supply_dependency | low      |