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
last_updated: '2026-07-09T14:57:25.355343+00:00'
valid_at: '2026-07-09T14:57:25.355343+00:00'
source_episodes: []
links_out:
- grade_arab_light
- grade_arab_medium
- supplier_aramco
- grade_basrah_heavy
- supplier_iraqoil
- grade_urals
- supplier_rosneft
- port_vadinar
- port_sikka
- corridor_hormuz
- port_yanbu
coordinates:
  lat: 22.47
  lon: 70.07
---


## Overview
The [[Jamnagar Refinery]] (Reliance) is the world's largest single-site refining complex —
~1.40 mbpd across its DTA and SEZ units, with a Nelson Complexity Index of 21.1.

## Crude Diet
Its high complexity lets it process a very wide slate: [[Arab Light]] and [[Arab Medium]] from
[[Saudi Aramco]], [[Basrah Heavy]] from the [[Iraqi Oil Ministry]], and [[Urals]] from [[Rosneft]]
(increased post-2022 for price advantage). See the CONFIGURED_FOR edges for compatibility scores.

## Supply Path
Crude arrives via [[Vadinar]] (~70%) and [[Sikka]] (~30%), both fed through the
[[Strait of Hormuz]]. This makes Jamnagar SAGE's most Hormuz-exposed demand node.

## SAGE Risk Profile
High exposure to a Hormuz disruption; bypass feasibility is high because it can absorb
[[Yanbu]]-routed [[Arab Light]] with a modest cost premium. On-site crude inventory ≈ 22 days.