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
last_updated: '2026-07-09T18:06:33.869834+00:00'
valid_at: '2026-07-09T18:06:08.350223+00:00'
source_episodes: []
links_out:
- refinery_jamnagar
- supplier_adnoc
- corridor_cape
- event_2019_hormuz_attacks
- supplier_nioc
- supplier_aramco
- authority_ofac
- supplier_kazmunaygas
- corridor_suez
- supplier_nnpc
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] is experiencing a projected supply gap of 0.64 mbpd over 10 days due to heightened geopolitical tensions and sanctions. No risk score is available for this signal. The [[Jamnagar Refinery]] is most exposed with a peak gap of 0.64 mbpd from day 0. System 3 procurement analysis has identified 9 alternative crude sources, with the top option being [[ADNOC]] (Murban) via [[Cape of Good Hope]] at $80.10/bbl with a 24-day lead time and a TOPSIS score of 0.78.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing increased sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.
- [[Jamnagar Refinery]]: High exposure with a peak gap of 0.64 mbpd from day 0.

## Signal Basis
- Designation of a second sanctioned tanker by [[OFAC]].
- System 2 scenario modelling (confirmed) for Strait of Hormuz: projected supply gap 0.64 mbpd over 10 days.
- System 3 procurement analysis for Strait of Hormuz: 9 alternative crude sources ranked. Top option: [[ADNOC]] (Murban) via [[Cape of Good Hope]] — $80.10/bbl, 24 day lead time, grade compatibility 0.50, TOPSIS score 0.78. Alternative options: [[KazMunayGas]] via [[Suez Canal]] ($80.55/bbl, TOPSIS 0.69); [[NNPC]] via [[Suez Canal]] ($80.85/bbl, TOPSIS 0.63).

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
| supply_dependency | [[NIOC]] | supply_dependency | high |
| supply_dependency | [[Saudi Aramco]] | supply_dependency | medium |
| supply_dependency | [[ADNOC]] | supply_dependency | medium |
| historical_precedent | [[2019 Tanker Attacks]] | historical_precedent | medium |
| sanctions_link | [[OFAC]] | sanctions_link | high |
| refinery_dependency | [[Jamnagar Refinery]] | refinery_dependency | high |
| bypass_option | [[Cape of Good Hope]] | bypass_option | high |
| bypass_option | [[Suez Canal]] | bypass_option | medium |
| supply_dependency | [[KazMunayGas]] | supply_dependency | medium |
| supply_dependency | [[NNPC]] | supply_dependency | medium |