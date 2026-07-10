---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/calm
risk_score: 0.2197
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.4275
  price: 0.0
  sanctions: 0.0
last_updated: '2026-07-09T08:52:59'
valid_at: '2026-07-09T08:52:59'
source_episodes: []
links_out:
- authority_ofac
- supplier_us
- corridor_suez
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
The [[Strait of Hormuz]] is experiencing heightened geopolitical tensions following direct military strikes between Iran and Israel near the Persian Gulf. The [[OFAC]] has designated a second sanctioned tanker, further complicating the supply chain dynamics. System 3 procurement analysis has identified alternative crude sources, with the top option being from the [[United States]] via the [[Suez Canal]].

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing increased geopolitical risks and sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.
- [[Jamnagar Refinery]]: High exposure with a peak gap of 0.21 mbpd from day 0.
- [[United States]]: New potential supply source identified via [[Suez Canal]].

## Signal Basis
- News report of direct military strikes between Iran and Israel near the Persian Gulf.
- OFAC adds NIOC-linked tanker operators to the SDN list.
- OFAC designates a second sanctioned tanker.
- System 2 scenario modelling (confirmed) for Strait of Hormuz: projected supply gap 0.21 mbpd over 10 days (timeline: day1:0.0, day2:0.1, day3:0.1, day4:0.1, day5:0.2, day6:0.2, day7:0.2).
- System 3 procurement analysis identifies alternative crude sources: [[United States]] via [[Suez Canal]] and Indian Oil Corporation Limited via [[Suez Canal]].

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
| bypass_option | [[United States]] | bypass_option | medium |
| bypass_option | [[Suez Canal]] | bypass_option | medium |