---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
risk_score: 0.0
risk_band: CALM
factors:
  ais: 0.0
  gdelt: 0.0
  price: 0.0
  sanctions: 0.0
last_updated: '2026-06-30T18:01:11.095851+00:00'
valid_at: '2026-06-30T18:01:03.178992+00:00'
source_episodes: []
links_out:
- event_2019_hormuz_attacks
- refinery_jamnagar
- refinery_mangaluru
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] is currently experiencing a projected supply gap of 0.00 mbpd over 0 days, with a price impact of $2-$4/bbl. The Strategic Petroleum Reserves (SPR) would last 45.0 days at the projected draw rate, with an inflation impact of 0.27%.

## Historical Pattern
The current situation shows no significant precedent in terms of supply gap, aligning closely with the [[2019 Tanker Attacks]] in terms of minimal immediate impact but with a notable price impact.

## Affected Entities
- [[Jamnagar Refinery]]: Peak gap of 0.00 mbpd from day 45.0.
- [[Mangaluru]]: Peak gap of 0.00 mbpd from day 45.0.
- Umm Al Nar: Peak gap of 0.00 mbpd from day 45.0.

## Signal Basis
- System 2 scenario modelling (confirmed) for Strait of Hormuz.

## Relations
| Relation         | Entity               | Type               | Strength |
|------------------|----------------------|--------------------|----------|
| supply_dependency| [[Jamnagar Refinery]]| refinery           | high     |
| supply_dependency| [[Mangaluru]]        | refinery           | high     |
| supply_dependency| Umm Al Nar       | refinery           | high     |