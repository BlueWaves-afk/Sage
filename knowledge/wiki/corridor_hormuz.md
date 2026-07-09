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
last_updated: '2026-07-09T18:06:18.689157+00:00'
valid_at: '2026-07-09T18:05:46.347478+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_nioc
- supplier_aramco
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
The [[Strait of Hormuz]] remains under heightened geopolitical and sanctions risk following the designation of a second sanctioned tanker by [[OFAC]], exacerbating the existing tensions from recent military strikes between Iran and Israel near the Persian Gulf. No risk score is available for this signal.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing increased sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.

## Signal Basis
- Designation of a second sanctioned tanker by [[OFAC]].
- System 3 procurement analysis for Strait of Hormuz: 9 alternative crude sources ranked. Top option: [[ADNOC]] ([[Murban]]) via [[Cape of Good Hope]] — $80.10/bbl, 24 day lead time, grade compatibility 0.50, TOPSIS score 0.78. Alternative options: [[KazMunayGas]] via [[Suez Canal]] ($80.55/bbl, TOPSIS 0.69); [[NNPC]] via [[Suez Canal]] ($80.85/bbl, TOPSIS 0.63).

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
| supply_dependency | [[NIOC]] | supply_dependency | high |
| supply_dependency | [[Saudi Aramco]] | supply_dependency | medium |
| supply_dependency | [[ADNOC]] | supply_dependency | medium |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | medium |
| sanctions_link | [[OFAC]] | sanctions_link | high |
| bypass_option | [[Cape of Good Hope]] | bypass_option | medium |
| bypass_option | [[Suez Canal]] | bypass_option | medium |
| supply_dependency | [[KazMunayGas]] | supply_dependency | low |
| supply_dependency | [[NNPC]] | supply_dependency | low |