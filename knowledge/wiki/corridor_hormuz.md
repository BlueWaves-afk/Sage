---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/critical
risk_score: 0.9198
risk_band: CRITICAL
factors:
  ais: 0.0
  gdelt: 0.595
  price: 0.35
  sanctions: 0.0
last_updated: '2026-07-09T14:12:11.718399+00:00'
valid_at: '2026-07-09T14:12:11.718399+00:00'
source_episodes: []
links_out:
- supplier_adnoc
- corridor_cape
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_qatarenergy
- supplier_kpc
- supplier_iraqoil
- supplier_us
- corridor_suez
- supplier_kazmunaygas
- supplier_nnpc
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, significantly heightening geopolitical tensions in the region. No risk score is available for this signal, but the situation is critical given the strait's importance for global oil supply. System 3 procurement analysis has identified 20 alternative crude sources, with [[ADNOC]] (Murban) via [[Cape of Good Hope]] being the top option at $98.05/bbl with a 24-day lead time.

## Historical Pattern
The current situation echoes the [[2019 Tanker Attacks]], where similar threats and actions led to a sharp increase in oil prices and naval deployments.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure as a major supplier reliant on the strait.
- [[ADNOC]]: Medium exposure due to regional supply dependencies.
- [[QatarEnergy]]: Medium exposure based on inventory days at risk.
- [[Kuwait Petroleum Corporation]]: Medium exposure due to strategic location.
- [[Iraqi Oil Ministry]]: High exposure given dependency on Hormuz for exports.
- [[United States]]: Low exposure, primarily through strategic interest and alliance support.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]].
- System 3 procurement analysis for alternative crude sources.

## Relations
| Relation         | Entity                        | Type               | Strength |
|------------------|-------------------------------|--------------------|----------|
| threat_actor     | Iran                      | threat_actor       | high     |
| supply_dependency| [[Saudi Aramco]]              | supply_dependency  | high     |
| supply_dependency| [[NIOC]]                      | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]                     | supply_dependency  | medium   |
| supply_dependency| [[QatarEnergy]]               | supply_dependency  | medium   |
| supply_dependency| [[Kuwait Petroleum Corporation]]| supply_dependency | medium   |
| supply_dependency| [[Iraqi Oil Ministry]]        | supply_dependency  | high     |
| strategic_interest| [[United States]]             | strategic_interest | low      |
| bypass_option    | [[Cape of Good Hope]]         | bypass_option      | medium   |
| bypass_option    | [[Suez Canal]]                | bypass_option      | medium   |
| supply_dependency| [[KazMunayGas]]               | supply_dependency  | low      |
| supply_dependency| [[NNPC]]                      | supply_dependency  | low      |