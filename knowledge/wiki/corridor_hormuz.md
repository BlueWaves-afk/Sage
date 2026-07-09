---
entity_id: corridor_hormuz
aliases:
- Strait of Hormuz
entity_type: Corridor
tags:
- sage/corridor
- risk/critical
risk_score: 0.9193
risk_band: CRITICAL
factors:
  ais: 0.3685
  gdelt: 0.595
  price: 0.35
  sanctions: 0.55
last_updated: '2026-07-09T14:03:45.548715+00:00'
valid_at: '2026-07-09T14:03:45.548715+00:00'
source_episodes: []
links_out:
- authority_ofac
- event_2019_hormuz_attacks
- supplier_aramco
- supplier_nioc
- supplier_adnoc
- supplier_iraqoil
- supplier_kpc
- supplier_qatarenergy
coordinates:
  lat: 26.5
  lon: 56.4
---




## Current Assessment
Iran has threatened to close the [[Strait of Hormuz]] following recent strikes, potentially disrupting a critical chokepoint for global oil supply. Additionally, the [[OFAC]] has added a tanker operator to the SDN list, further complicating the transit of oil through the strait. No risk score is available for this signal.

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
- [[OFAC]] adds tanker operator to SDN list.

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
| sanctions_link   | [[OFAC]]               | authority          | high     |