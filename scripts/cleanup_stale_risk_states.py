#!/usr/bin/env python3
"""
G3 cleanup: delete RISK_STATE edges with malformed band values (e.g. band='.')
that were seeded by the old seed_kb.py RISK_STATES list and spammed gateway logs.

Run once on any instance that was seeded with the old seed_kb.py:
  docker compose exec sage-core python -m scripts.cleanup_stale_risk_states
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    from falkordb import FalkorDB

    host = os.environ.get("FALKORDB_HOST", "localhost")
    port = int(os.environ.get("FALKORDB_PORT", "6379"))

    db = FalkorDB(host=host, port=port)
    g = db.select_graph("sage")

    # Count malformed edges first
    count_q = "MATCH ()-[r:RISK_STATE]->() WHERE r.band IS NOT NULL AND NOT r.band IN ['calm','watch','elevated','action','critical'] RETURN count(r) AS n"
    result = g.query(count_q)
    count = result.result_set[0][0] if result.result_set else 0
    print(f"Found {count} malformed RISK_STATE edge(s) with invalid band values")

    if count == 0:
        print("Nothing to do.")
        return

    # Delete them
    del_q = "MATCH ()-[r:RISK_STATE]->() WHERE r.band IS NOT NULL AND NOT r.band IN ['calm','watch','elevated','action','critical'] DELETE r RETURN count(*) AS deleted"
    del_result = g.query(del_q)
    deleted = del_result.result_set[0][0] if del_result.result_set else 0
    print(f"Deleted {deleted} malformed RISK_STATE edge(s)")


if __name__ == "__main__":
    main()
