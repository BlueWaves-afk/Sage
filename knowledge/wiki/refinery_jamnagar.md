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
last_updated: '2026-07-04T08:42:26.843190+00:00'
valid_at: '2026-07-04T08:41:52.066933+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- grade_murban
- corridor_cape
- supplier_aramco
- grade_arab_light
- corridor_hormuz
- supplier_kazmunaygas
- corridor_suez
- supplier_nnpc
coordinates:
  lat: 22.47
  lon: 70.07
---


## Current Assessment
The [[Jamnagar Refinery]] is now prioritizing [[ADNOC]]'s [[Murban]] crude via the [[Cape of Good Hope]] as the top procurement option, based on the latest System 3 procurement analysis. This shift is driven by the optimal cost, lead time, and grade compatibility metrics.

## Contradiction Note
The new signal contradicts the previous assessment, which identified [[Saudi Aramco]]'s [[Arab Light]] crude via the [[Strait of Hormuz]] as the top procurement option. The contradiction arises from updated procurement metrics favoring [[ADNOC]]'s [[Murban]].

## Affected Entities
- [[ADNOC]]: High exposure due to the new top crude option.
- [[Cape of Good Hope]]: High exposure as the primary transit route for the top crude option.
- [[Saudi Aramco]]: Medium exposure as the previous top crude option.
- [[Strait of Hormuz]]: Medium exposure as the previous primary transit route.
- [[KazMunayGas]]: Low exposure as an alternative supplier via [[Suez Canal]].
- [[NNPC]]: Low exposure as an alternative supplier via [[Suez Canal]].

## Signal Basis
- System 3 procurement analysis for Jamnagar Refinery.

## Relations
| Relation        | Entity                 | Type             | Strength |
|-----------------|------------------------|------------------|----------|
| supply_dependency | [[ADNOC]]              | supply_dependency | high     |
| supply_dependency | [[Cape of Good Hope]]  | supply_dependency | high     |
| supply_dependency | [[Saudi Aramco]]       | supply_dependency | medium   |
| supply_dependency | [[Strait of Hormuz]]   | supply_dependency | medium   |
| supply_dependency | [[KazMunayGas]]        | supply_dependency | low      |
| supply_dependency | [[NNPC]]               | supply_dependency | low      |