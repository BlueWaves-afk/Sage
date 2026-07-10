"""
Sanctions diff sub-agent.

Downloads OFAC SDN, EU, and UN sanctions lists.
Diffs against Redis-cached last snapshot.
Any change (addition OR removal) → HIGH priority, force_synthesis=True.

Payload contract (fusion reads these exact keys):
    change       — "add" or "remove"
    subject_type — "entity", "person", "state", or "vessel"
    vessel_mmsi  — str or None
    operator     — str or None (parent company)
    list         — "OFAC", "EU", or "UN"
    subject      — name of sanctioned party
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from xml.etree import ElementTree as ET

import redis.asyncio as aioredis

from contracts.signal import NormalizedSignal
from knowledge.registry import (
    resolve_name,
    canonical_name,
    register_vessel,
    ALIAS_TO_ENTITY,
)
from sensory_agent._base import emit, new_signal_id, utcnow

log = logging.getLogger(__name__)

POLL_INTERVAL_S = int(os.environ.get("SANCTIONS_POLL_INTERVAL_S", "21600"))  # 6h
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Redis keys for snapshot caching
_CACHE_KEY_PREFIX = "sage:sanctions:snapshot:"

# ── Sanctions list URLs ───────────────────────────────────────────────────────

SANCTIONS_LISTS = [
    {
        "name": "OFAC",
        "url": "https://www.treasury.gov/ofac/downloads/sdn.xml",
    },
    {
        "name": "UN",
        "url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
    },
    # EU consolidated list: the old open data.europa.eu download now 404s (the EU
    # FSF endpoint requires a per-user token). Disabled to avoid recurring fetch
    # errors — OFAC SDN + UN cover the sanctions signal. Re-enable with a valid
    # EU FSF token URL when available.
    # {"name": "EU", "url": "https://webgate.ec.europa.eu/fsd/fsf/public/files/..."},
]

# Energy / maritime keywords for filtering relevant sanctions
ENERGY_KEYWORDS = {
    "oil", "petroleum", "crude", "lng", "lpg", "gas", "tanker", "vessel",
    "maritime", "shipping", "energy", "refinery", "pipeline", "irgc",
    "iran", "russia", "venezuela", "pdvsa", "nioc", "rosneft",
    "houthi", "yemen", "syria", "north korea", "dprk",
}


# ── XML Parsing ──────────────────────────────────────────────────────────────

def _parse_ofac_xml(xml_text: str) -> list[dict]:
    """Parse OFAC SDN XML into a list of entry dicts."""
    entries = []
    try:
        root = ET.fromstring(xml_text)
        # Handle namespace
        ns = {"sdn": "http://www.un.org/sanctions/1.0"}
        # Try without namespace first (OFAC uses varying schemas)
        sdn_entries = root.findall(".//sdnEntry") or root.findall(".//sdn:sdnEntry", ns)

        for entry in sdn_entries:
            last_name = entry.findtext("lastName", "") or entry.findtext("sdn:lastName", "", ns) or ""
            first_name = entry.findtext("firstName", "") or entry.findtext("sdn:firstName", "", ns) or ""
            sdn_type = entry.findtext("sdnType", "") or entry.findtext("sdn:sdnType", "", ns) or ""
            uid = entry.findtext("uid", "") or entry.findtext("sdn:uid", "", ns) or ""
            program = entry.findtext("programList/program", "") or ""
            remarks = entry.findtext("remarks", "") or ""

            name = f"{first_name} {last_name}".strip() or last_name
            if not name:
                continue

            # Determine subject type
            subject_type = "entity"
            if sdn_type.lower() == "individual":
                subject_type = "person"
            elif "vessel" in sdn_type.lower() or "vessel" in remarks.lower():
                subject_type = "vessel"

            # Extract MMSI/IMO from remarks if vessel
            mmsi = None
            imo = None
            if subject_type == "vessel":
                mmsi_match = re.search(r"MMSI[:\s]+(\d{9})", remarks)
                if mmsi_match:
                    mmsi = mmsi_match.group(1)
                imo_match = re.search(r"IMO[:\s]+(\d{7})", remarks)
                if imo_match:
                    imo = imo_match.group(1)

            entries.append({
                "uid": uid,
                "subject": name,
                "subject_type": subject_type,
                "mmsi": mmsi,
                "imo": imo,
                "program": program,
                "remarks": remarks,
            })
    except ET.ParseError as exc:
        log.error("Failed to parse OFAC XML: %s", exc)

    return entries


def _parse_un_xml(xml_text: str) -> list[dict]:
    """Parse UN consolidated sanctions XML."""
    entries = []
    try:
        root = ET.fromstring(xml_text)
        for ind in root.findall(".//INDIVIDUAL") + root.findall(".//ENTITY"):
            tag = ind.tag
            name_parts = []
            for key in ["FIRST_NAME", "SECOND_NAME", "THIRD_NAME"]:
                val = ind.findtext(key)
                if val:
                    name_parts.append(val)
            name = " ".join(name_parts) or ind.findtext("NAME_ORIGINAL_SCRIPT", "")
            if not name:
                continue

            subject_type = "person" if tag == "INDIVIDUAL" else "entity"
            ref_num = ind.findtext("REFERENCE_NUMBER", "")

            entries.append({
                "uid": ref_num,
                "subject": name,
                "subject_type": subject_type,
                "mmsi": None,
                "imo": None,
            })
    except ET.ParseError as exc:
        log.error("Failed to parse UN XML: %s", exc)

    return entries


def _parse_eu_xml(xml_text: str) -> list[dict]:
    """Parse EU sanctions XML (simplified — covers common formats)."""
    entries = []
    try:
        root = ET.fromstring(xml_text)
        # EU uses various schemas; try common element names
        for entity in (root.findall(".//entity") or root.findall(".//sanctionEntity")
                       or root.findall(".//{*}entity")):
            name_el = entity.find(".//nameAlias") or entity.find(".//{*}nameAlias")
            name = (name_el.get("wholeName", "") if name_el is not None
                    else entity.findtext("name", ""))
            if not name:
                continue

            sub_type = entity.get("subjectType", "entity")
            if sub_type == "person":
                subject_type = "person"
            else:
                subject_type = "entity"

            log_id = entity.get("logicalId", "") or entity.get("euReferenceNumber", "")

            entries.append({
                "uid": log_id,
                "subject": name,
                "subject_type": subject_type,
                "mmsi": None,
                "imo": None,
            })
    except ET.ParseError as exc:
        log.error("Failed to parse EU XML: %s", exc)

    return entries


def _parse_xml(list_name: str, xml_text: str) -> list[dict]:
    """Route to the correct parser based on list name."""
    if list_name == "OFAC":
        return _parse_ofac_xml(xml_text)
    elif list_name == "UN":
        return _parse_un_xml(xml_text)
    elif list_name == "EU":
        return _parse_eu_xml(xml_text)
    return []


def _filter_relevant(entries: list[dict]) -> list[dict]:
    """
    Filter entries to those relevant to energy/maritime sector.
    Keeps all vessel-type entries and any entry whose name/remarks
    contain energy keywords.
    """
    relevant = []
    for e in entries:
        if e["subject_type"] == "vessel":
            relevant.append(e)
            continue

        searchable = (e.get("subject", "") + " " +
                      e.get("program", "") + " " +
                      e.get("remarks", "")).lower()
        if any(kw in searchable for kw in ENERGY_KEYWORDS):
            relevant.append(e)

    return relevant


def _compute_snapshot_hash(entries: list[dict]) -> str:
    """Deterministic hash of a sanctions list for diff detection."""
    # Sort by uid for stability
    sorted_entries = sorted(entries, key=lambda e: e.get("uid", e.get("subject", "")))
    canonical = json.dumps(sorted_entries, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _diff_entries(
    old_entries: list[dict],
    new_entries: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Diff two snapshots. Returns (additions, removals).
    Uses (subject, subject_type) as identity key.
    """
    def _key(e: dict) -> str:
        return f"{e.get('subject', '').lower()}|{e.get('subject_type', '')}"

    old_set = {_key(e): e for e in old_entries}
    new_set = {_key(e): e for e in new_entries}

    added = [new_set[k] for k in new_set if k not in old_set]
    removed = [old_set[k] for k in old_set if k not in new_set]

    return added, removed


async def _fetch_xml(url: str) -> str | None:
    """Fetch XML content from a URL."""
    import urllib.request
    import ssl

    try:
        # Create SSL context that doesn't verify (some govt sites have cert issues)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers={
            "User-Agent": "SAGE-System1/1.0 (Energy Supply Chain Monitor)",
        })
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=60, context=ctx),
        )
        return response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return None


async def _diff_one_list(list_info: dict) -> list[NormalizedSignal]:
    """
    Download one sanctions list, parse, diff against cached snapshot,
    and return signals for any changes.
    """
    list_name = list_info["name"]
    url = list_info["url"]
    cache_key = f"{_CACHE_KEY_PREFIX}{list_name}"

    log.info("Fetching %s sanctions list from %s", list_name, url)
    xml_text = await _fetch_xml(url)
    if not xml_text:
        return []

    # Parse
    new_entries = _parse_xml(list_name, xml_text)
    new_entries = _filter_relevant(new_entries)
    log.info("%s: parsed %d relevant entries", list_name, len(new_entries))

    # Load cached snapshot from Redis
    signals = []
    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            cached_json = await client.get(cache_key)
            old_entries = json.loads(cached_json) if cached_json else []

            # Diff
            added, removed = _diff_entries(old_entries, new_entries)

            if not added and not removed:
                log.info("%s: no changes detected", list_name)
            else:
                log.info("%s: %d additions, %d removals", list_name, len(added), len(removed))

            # Build signals for additions
            for entry in added:
                sig = await _build_signal(list_name, entry, change="add")
                if sig:
                    signals.append(sig)

            # Build signals for removals
            for entry in removed:
                sig = await _build_signal(list_name, entry, change="remove")
                if sig:
                    signals.append(sig)

            # Update cache
            await client.set(cache_key, json.dumps(new_entries))

        finally:
            await client.aclose()

    except Exception as exc:
        log.error("Redis error during %s diff: %s", list_name, exc)
        # On first run (no Redis), still try to seed the cache
        try:
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            try:
                await client.set(cache_key, json.dumps(new_entries))
                log.info("%s: seeded initial snapshot (%d entries)", list_name, len(new_entries))
            finally:
                await client.aclose()
        except Exception:
            pass

    return signals


async def _build_signal(
    list_name: str,
    entry: dict,
    change: str,
) -> NormalizedSignal | None:
    """
    Build a NormalizedSignal from a sanctions diff entry.
    Handles entity resolution and vessel registration.
    """
    subject = entry["subject"]
    subject_type = entry.get("subject_type", "entity")
    mmsi = entry.get("mmsi")
    imo = entry.get("imo")

    # Entity resolution
    eid = resolve_name(subject)

    # If vessel with new MMSI → register FIRST
    if not eid and mmsi and subject_type == "vessel":
        eid = register_vessel(
            mmsi=mmsi,
            vessel_name=subject,
            imo=imo,
        )
        log.info("Registered new vessel: %s (MMSI=%s) → %s", subject, mmsi, eid)

    refs = [canonical_name(eid)] if eid else [subject]

    # Try to resolve operator
    operator = entry.get("operator")
    if operator:
        op_id = resolve_name(operator)
        if op_id:
            refs.append(canonical_name(op_id))

    return NormalizedSignal(
        signal_id=new_signal_id("sanctions"),
        source="sanctions",
        observed_at=utcnow(),
        ingested_at=utcnow(),
        priority_hint="HIGH",
        force_synthesis=True,     # sanctions ALWAYS force synthesis
        entity_refs=refs,
        summary=(
            f"{list_name}: {subject} {change}ed — "
            f"{subject_type}"
            + (f", MMSI {mmsi}" if mmsi else "")
        ),
        payload={
            "list": list_name,
            "change": change,
            "subject": subject,
            "subject_type": subject_type,
            "vessel_mmsi": mmsi,
            "operator": operator,
        },
    )


async def _diff_all_lists() -> list[NormalizedSignal]:
    """Download and diff all sanctions lists. Return signals for changes."""
    all_signals = []
    for list_info in SANCTIONS_LISTS:
        try:
            signals = await _diff_one_list(list_info)
            all_signals.extend(signals)
        except Exception as exc:
            log.error("Failed to process %s: %s", list_info["name"], exc)
    return all_signals


async def run() -> None:
    """
    Entry point. Polls sanctions lists every 6 hours.
    force_synthesis=True for every change — the LLM always writes
    implications prose for sanctions events.
    """
    log.info(
        "Sanctions sub-agent started. Lists=%s, interval=%ds",
        [s["name"] for s in SANCTIONS_LISTS],
        POLL_INTERVAL_S,
    )

    while True:
        try:
            signals = await _diff_all_lists()
            for signal in signals:
                await emit(signal)
                log.info("Sanctions signal: %s", signal.summary)

            if signals:
                log.info("Sanctions cycle complete: %d signals emitted", len(signals))
            else:
                log.info("Sanctions cycle complete: no changes detected")

        except Exception as exc:
            log.error("Sanctions poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_S)
