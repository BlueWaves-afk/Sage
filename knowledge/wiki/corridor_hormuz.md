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
last_updated: '2026-07-10T19:11:11.605418+00:00'
valid_at: '2026-07-10T19:11:03.079065+00:00'
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
The [[Strait of Hormuz]] is experiencing heightened geopolitical tensions following direct military strikes between Iran and Israel near the Persian Gulf. The [[OFAC]] has designated a second sanctioned tanker, further complicating the supply chain dynamics and increasing the risk for entities dependent on this corridor.

## Historical Pattern
The current event shows similarity to the [[2019 Tanker Attacks]] with a feature-overlap percentage of approximately 30%.

## Affected Entities
- [[NIOC]]: High exposure due to a significant portion of exports passing through the [[Strait of Hormuz]] and now facing increased geopolitical risks and sanctions.
- [[Saudi Aramco]]: Medium exposure as a major supplier in the region with diversified but still vulnerable routes.
- [[ADNOC]]: Medium exposure due to reliance on the [[Strait of Hormuz]] for a portion of its exports.
- [[Jamnagar Refinery]]: High exposure with a peak gap of 1.12 mbpd from day 0.

## Signal Basis
- News report of direct military strikes between Iran and Israel near the Persian Gulf.
- OFAC adds NIOC-linked tanker operators to the SDN list.
- System 2 scenario modelling (confirmed) for Strait of Hormuz: projected supply gap 1.12 mbpd over 10 days (timeline: day1:1.1, day2:1.1, day3:1.1, day4:1.1, day5:1.1, day6:1.1, day7:0.9). Projected price impact $9-$15/bbl, SPR cover would last 45.0 days at the projected draw rate, GDP impact -2.36%, inflation impact 1.06%. Most-exposed nodes: Jamnagar Refinery peak gap 1.12 mbpd from day 0.0; Mangaluru peak gap 0.00 mbpd from day 45.0; Mina Al-Ahmadi peak gap 0.00 mbpd from day 45.0. Key assumptions: import_dependence_pct=88.6%; hormuz_share_pct=42.5%; spr_total_mmt=5.33MMT; spr_fill_frac=0.572frac. Model confidence 100%.
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