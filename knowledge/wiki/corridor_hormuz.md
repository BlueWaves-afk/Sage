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
last_updated: '2026-07-09T13:25:52.256697+00:00'
valid_at: '2026-07-09T13:22:30.868316+00:00'
source_episodes: []
links_out:
- authority_ofac
- supplier_aramco
- event_tanker_war
- supplier_adnoc
- supplier_nioc
- supplier_iraqoil
- supplier_kpc
- port_vadinar
- port_sikka
- refinery_jamnagar
- refinery_chennai
- refinery_visakh
- port_yanbu
- port_fujairah
coordinates:
  lat: 26.5
  lon: 56.4
---


## Current Assessment
The [[Strait of Hormuz]] remains under immediate threat of closure following Iran's declaration to shut down the strait in response to recent strikes. The [[OFAC]] has added a tanker operator to the SDN list, further complicating the transit of oil through the strait. System 3 procurement analysis has identified 24 alternative crude sources, with the top option being [[Saudi Aramco]] (Arab Light) via [[Strait of Hormuz]] at $96.80/bbl with a 20-day lead time and a TOPSIS score of 0.64.

## Historical Pattern
The current situation has a clear precedent in the [[Tanker War]] with a feature-overlap percentage of approximately 70%.

## Affected Entities
- [[Saudi Aramco]]: High exposure due to significant throughput share.
- [[ADNOC]]: High exposure due to significant throughput share.
- [[NIOC]]: High exposure due to significant throughput share.
- [[Iraqi Oil Ministry]]: High exposure due to significant throughput share.
- [[Kuwait Petroleum Corporation]]: High exposure due to significant throughput share.
- [[Vadinar]]: High exposure as a major destination port.
- [[Sikka]]: High exposure as a major destination port.
- [[Jamnagar Refinery]]: High exposure due to peak gap of 0.61 mbpd from day 0.0.
- [[Chennai Refinery]]: High exposure due to peak gap of 0.00 mbpd from day 45.0.
- [[Visakhapatnam Refinery]]: High exposure due to peak gap of 0.00 mbpd from day 45.0.

## Signal Basis
- News report indicating Iran's threat to close the [[Strait of Hormuz]] after strikes.
- [[OFAC]] adds tanker operator to SDN list.
- System 3 procurement analysis for Strait of Hormuz: 24 alternative crude sources ranked.

## Relations
| Relation         | Entity                                 | Type               | Strength |
|------------------|----------------------------------------|--------------------|----------|
| supply_dependency| [[Saudi Aramco]]                       | supply_dependency  | high     |
| supply_dependency| [[ADNOC]]                              | supply_dependency  | high     |
| supply_dependency| [[NIOC]]                               | supply_dependency  | high     |
| supply_dependency| [[Iraqi Oil Ministry]]                 | supply_dependency  | high     |
| supply_dependency| [[Kuwait Petroleum Corporation]]        | supply_dependency  | high     |
| threat_actor     | Iran                                   | threat_actor       | high     |
| threat_actor     | Israel                                 | threat_actor       | high     |
| historical_precedent| [[Tanker War]]                       | historical_precedent| high     |
| bypass_option    | [[Yanbu]]                              | bypass_option      | medium   |
| bypass_option    | [[Fujairah]]                           | bypass_option      | medium   |
| supply_dependency| [[Jamnagar Refinery]]                  | supply_dependency  | high     |
| supply_dependency| [[Chennai Refinery]]                   | supply_dependency  | high     |
| supply_dependency| [[Visakhapatnam Refinery]]             | supply_dependency  | high     |
| sanctions_link   | [[OFAC]]                               | sanctions_link     | high     |