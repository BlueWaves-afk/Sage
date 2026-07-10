---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/critical
risk_score: 0.936
risk_band: CRITICAL
factors:
  ais: 0.985
  gdelt: 0.8971
  price: 0.9355
  sanctions: 0.9167
last_updated: '2026-07-10T09:47:36.880559+00:00'
valid_at: '2026-07-10T09:47:36.880559+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_nioc
- supplier_aramco
- supplier_adnoc
- refinery_jamnagar
coordinates:
  lat: 26.5
  lon: 56.4
---



## Current Assessment
The [[Strait of Hormuz]] is experiencing heightened geopolitical tensions following direct military strikes between Iran and Israel near the Persian Gulf. The [[OFAC]] has now designated a second sanctioned tanker, further complicating the supply chain dynamics and increasing the risk for entities dependent on this corridor.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing increased geopolitical risks and sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.
- [[Jamnagar Refinery]]: High exposure with a peak gap of 0.21 mbpd from day 0.

## Signal Basis
- News report of direct military strikes between Iran and Israel near the Persian Gulf.
- OFAC adds NIOC-linked tanker operators to the SDN list.
- System 2 scenario modelling (confirmed) for Strait of Hormuz: projected supply gap 0.21 mbpd over 10 days (timeline: day1:0.0, day2:0.1, day3:0.1, day4:0.1, day5:0.2, day6:0.2, day7:0.2).
- OFAC designates a second sanctioned tanker.

## Relations
| Relation | Entity | Type | Strength |
|---|---|---|---|
| supply_dependency | [[NIOC]] | supply_dependency | high |
| supply_dependency | [[Saudi Aramco]] | supply_dependency | medium |
| supply_dependency | [[ADNOC]] | supply_dependency | medium |
| refinery_dependency | [[Jamnagar Refinery]] | refinery_dependency | high |
| threat_actor | Iran | threat_actor | high |
| threat_actor | Israel | threat_actor | high |
| sanctions_link | [[OFAC]] | sanctions_link | high |