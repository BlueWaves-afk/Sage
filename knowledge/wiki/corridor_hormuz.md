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
last_updated: '2026-07-09T14:04:28.360263+00:00'
valid_at: '2026-07-09T14:04:05.008986+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- corridor_cape
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_iraqoil
- supplier_kpc
- supplier_qatarenergy
- corridor_suez
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. The risk score for this signal is currently unavailable. System 3 procurement analysis has identified 20 alternative crude sources, with the top option being [[ADNOC]] (Murban) via [[Cape of Good Hope]] at $98.05/bbl with a 24-day lead time and a TOPSIS score of 0.78.

## Historical Pattern
The situation bears resemblance to the [[2019 Tanker Attacks]], where tensions in the region led to significant disruptions in oil transit through the [[Strait of Hormuz]].

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure as a major supplier reliant on the strait.
- [[ADNOC]]: Medium exposure due to regional supply dependencies.
- [[Iraqi Oil Ministry]]: High exposure given dependency on Hormuz for exports.
- [[Kuwait Petroleum Corporation]]: Medium exposure based on inventory days at risk.
- [[QatarEnergy]]: High exposure due to strategic location and export reliance.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].
- System 3 procurement analysis for alternative crude sources.

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
| bypass_option    | [[Cape of Good Hope]]  | corridor           | high     |
| bypass_option    | [[Suez Canal]]         | corridor           | medium   |
| signal_source    | System 3 procurement analysis | analysis_tool | high     |