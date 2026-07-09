"""
Commodity price sub-agent.

Polls yfinance every 5 minutes for Brent (BZ=F) and WTI (CL=F).
Also fetches EIA Open Data API for SPR stocks & refinery utilisation.
Runs Bayesian Online Changepoint Detection (BOCD) on every tick.
Emits a NormalizedSignal ONLY on changepoint or regime shift — never on
normal ticks.

Data sources:
    - yfinance: BZ=F (Brent), CL=F (WTI) — real-time futures prices
    - EIA API:  petroleum/pri/spt — Brent/WTI spot prices
                petroleum/stoc/wstk — weekly US petroleum stocks (SPR proxy)
                petroleum/pnp/wiup — refinery utilisation

Payload contract (fusion reads these exact keys):
    price_change_pct   — float, % change from prior close
    changepoint        — bool, True if BOCD detected
    bocd_probability   — float, P(changepoint) from BOCD
    regime_stressed    — float, 1.0 if stressed regime, else 0.0
    war_risk_premium_proxy — float, derived from price volatility
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import urllib.request
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yfinance as yf

from contracts.signal import NormalizedSignal
from knowledge.registry import resolve_instrument, canonical_name
from sensory_agent._base import emit, new_signal_id, utcnow

log = logging.getLogger(__name__)

INSTRUMENTS = ["BZ=F", "CL=F"]  # Brent, WTI
POLL_INTERVAL_S = int(os.environ.get("PRICE_POLL_INTERVAL_S", "300"))  # 5 min

# ── EIA Open Data API ────────────────────────────────────────────────────────
EIA_API_KEY = os.environ.get(
    "EIA_API_KEY",
    "uvHN4ZnezdnCdjRdQMa9UmQzvgKV8DMBUieULWXq",
)
EIA_BASE_URL = "https://api.eia.gov/v2"
EIA_POLL_INTERVAL_S = int(os.environ.get("EIA_POLL_INTERVAL_S", "3600"))  # 1 hour
_last_eia_poll: float = 0.0

# ── Rolling price series (in-memory, per instrument) ──────────────────────────

_series: dict[str, list[float]] = defaultdict(list)
_last_price: dict[str, float] = {}

# ── BOCD (simplified Bayesian Online Changepoint Detection) ──────────────────

# We use a lightweight hazard-function approach:
#   - Model observations as Gaussian with conjugate Normal-Inverse-Gamma prior
#   - At each tick compute P(changepoint) via the hazard function
#   - If P(changepoint) > threshold or |z-score| > 3 → flag changepoint

BOCD_HAZARD_RATE = 1 / 100       # expected 1 changepoint every 100 ticks
BOCD_THRESHOLD = 0.6             # P(cp) threshold to fire signal
REGIME_VOLATILITY_THRESHOLD = 3.0  # annualised vol threshold for stressed regime


@dataclass
class _BOCDState:
    """Minimal online changepoint detector state per instrument."""
    n: int = 0
    mean: float = 0.0
    M2: float = 0.0        # running variance (Welford)
    run_length: int = 0
    prev_price: float | None = None


_bocd_state: dict[str, _BOCDState] = defaultdict(_BOCDState)


def _update_bocd(instrument: str, price: float) -> tuple[bool, float, str]:
    """
    Update BOCD state with new price. Returns (is_changepoint, probability, regime).

    Uses Welford's online algorithm for mean/variance + simplified hazard model.
    """
    st = _bocd_state[instrument]

    if st.prev_price is None:
        st.prev_price = price
        return False, 0.0, "calm"

    # Log return
    ret = math.log(price / st.prev_price) if st.prev_price > 0 else 0.0
    st.prev_price = price

    # Welford update
    st.n += 1
    st.run_length += 1
    delta = ret - st.mean
    st.mean += delta / st.n
    delta2 = ret - st.mean
    st.M2 += delta * delta2

    if st.n < 5:
        return False, 0.0, "calm"

    variance = st.M2 / (st.n - 1)
    std = math.sqrt(max(variance, 1e-12))

    # Z-score of latest return
    z = abs(ret - st.mean) / std if std > 0 else 0.0

    # Simplified changepoint probability:
    #   P(cp) = hazard × (1 + z²/2) — higher z → higher P(cp)
    cp_prob = min(1.0, BOCD_HAZARD_RATE * (1 + z * z / 2))

    # Hard flag: either high probability or extreme z-score
    is_cp = cp_prob > BOCD_THRESHOLD or z > 3.5

    if is_cp:
        # Reset run length on changepoint
        st.run_length = 0

    # Regime detection: annualised vol proxy (sqrt(252) × daily std)
    annualised_vol = std * math.sqrt(252) * 100  # in percentage points
    regime = "stressed" if annualised_vol > REGIME_VOLATILITY_THRESHOLD else "calm"

    return is_cp, cp_prob, regime


def _compute_war_risk_premium(instrument: str) -> float:
    """
    Estimate war-risk premium proxy from recent price volatility.
    Higher realised vol → higher implied risk premium.
    Simple heuristic: vol / baseline_vol - 1, clamped to [0, 1].
    """
    series = _series.get(instrument, [])
    if len(series) < 10:
        return 0.0

    recent = series[-20:]  # last ~100 minutes
    if len(recent) < 2:
        return 0.0

    returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent))
               if recent[i - 1] > 0]
    if not returns:
        return 0.0

    vol = (sum(r * r for r in returns) / len(returns)) ** 0.5
    baseline_vol = 0.01  # ~1% daily vol in calm markets
    premium = min(1.0, max(0.0, vol / baseline_vol - 1))
    return round(premium, 4)


async def _poll_instrument(instrument: str) -> NormalizedSignal | None:
    """
    Fetch latest price for one instrument, run BOCD.
    Returns a signal only if a changepoint or regime shift is detected.
    """
    try:
        ticker = yf.Ticker(instrument)
        hist = ticker.history(period="1d", interval="5m")
        if hist.empty:
            log.warning("No price data for %s", instrument)
            return None

        price = float(hist["Close"].iloc[-1])
    except Exception as exc:
        log.error("yfinance fetch failed for %s: %s", instrument, exc)
        return None

    _series[instrument].append(price)

    # Keep rolling window bounded (last 500 ticks ≈ ~42 hours)
    if len(_series[instrument]) > 500:
        _series[instrument] = _series[instrument][-500:]

    # Run BOCD
    is_cp, cp_prob, regime = _update_bocd(instrument, price)

    if not is_cp:
        return None  # normal tick → DO NOT push

    # Compute price change
    last = _last_price.get(instrument)
    pct_change = ((price - last) / last * 100) if last and last > 0 else 0.0
    _last_price[instrument] = price

    # Resolve to tracked entities
    entity_ids = resolve_instrument(instrument)
    if not entity_ids:
        log.debug("No entities mapped for instrument %s", instrument)
        return None

    war_risk = _compute_war_risk_premium(instrument)
    regime_flag = 1.0 if regime == "stressed" else 0.0

    signal = NormalizedSignal(
        signal_id=new_signal_id("price"),
        source="price",
        observed_at=utcnow(),
        ingested_at=utcnow(),
        priority_hint="HIGH",
        force_synthesis=False,   # price NEVER forces synthesis
        entity_refs=[canonical_name(eid) for eid in entity_ids],
        summary=(
            f"{instrument} BOCD changepoint: {pct_change:+.1f}% move, "
            f"regime={regime}, P(cp)={cp_prob:.2f}"
        ),
        payload={
            "instrument": instrument,
            "price": price,
            "price_change_pct": round(pct_change, 2),
            "changepoint": True,
            "bocd_probability": round(cp_prob, 4),
            "regime_stressed": regime_flag,
            "war_risk_premium_proxy": war_risk,
        },
    )
    return signal


async def _poll_prices() -> list[NormalizedSignal]:
    """Fetch latest prices for all instruments, run BOCD, return signals."""
    signals = []
    for instrument in INSTRUMENTS:
        signal = await _poll_instrument(instrument)
        if signal:
            signals.append(signal)
    return signals


# ── EIA Open Data API ────────────────────────────────────────────────────────

async def _eia_request(route: str, params: dict | None = None) -> dict | None:
    """
    Make a GET request to the EIA API v2.
    Returns the JSON response or None on failure.
    """
    if not EIA_API_KEY:
        return None

    all_params = {"api_key": EIA_API_KEY}
    if params:
        all_params.update(params)

    url = f"{EIA_BASE_URL}/{route}?{urllib.parse.urlencode(all_params)}"

    try:
        loop = asyncio.get_event_loop()
        req = urllib.request.Request(url, headers={
            "User-Agent": "SAGE-System1/1.0",
        })
        response = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30),
        )
        data = json.loads(response.read().decode("utf-8"))
        return data.get("response", data)
    except Exception as exc:
        log.error("EIA API error (%s): %s", route, exc)
        return None


async def _poll_eia_spot_prices() -> list[NormalizedSignal]:
    """
    Fetch Brent/WTI spot prices from EIA.
    Supplements yfinance with authoritative government data.
    """
    signals = []
    data = await _eia_request("petroleum/pri/spt/data", {
        "frequency": "daily",
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": "5",
    })

    if not data or "data" not in data:
        return signals

    for row in data["data"]:
        series_id = row.get("series", "")
        value = row.get("value")
        if value is None:
            continue

        price = float(value)
        instrument = None

        if "RBRTE" in series_id:   # Brent
            instrument = "BZ=F"
        elif "RWTC" in series_id:  # WTI
            instrument = "CL=F"

        if instrument:
            # Feed into BOCD (same pipeline as yfinance)
            _series[instrument].append(price)
            if len(_series[instrument]) > 500:
                _series[instrument] = _series[instrument][-500:]

            is_cp, cp_prob, regime = _update_bocd(instrument, price)
            if is_cp:
                last = _last_price.get(instrument)
                pct = ((price - last) / last * 100) if last and last > 0 else 0.0
                _last_price[instrument] = price

                entity_ids = resolve_instrument(instrument)
                if entity_ids:
                    signals.append(NormalizedSignal(
                        signal_id=new_signal_id("price-eia"),
                        source="price",
                        observed_at=utcnow(),
                        ingested_at=utcnow(),
                        priority_hint="HIGH",
                        force_synthesis=False,
                        entity_refs=[canonical_name(eid) for eid in entity_ids],
                        summary=(
                            f"EIA {instrument}: {pct:+.1f}% move, "
                            f"regime={regime}, P(cp)={cp_prob:.2f}"
                        ),
                        payload={
                            "instrument": instrument,
                            "price": price,
                            "price_change_pct": round(pct, 2),
                            "changepoint": True,
                            "bocd_probability": round(cp_prob, 4),
                            "regime_stressed": 1.0 if regime == "stressed" else 0.0,
                            "war_risk_premium_proxy": _compute_war_risk_premium(instrument),
                        },
                    ))

    return signals


async def _poll_eia_weekly_stocks() -> None:
    """
    Fetch weekly US petroleum stocks from EIA (SPR proxy).
    Logs stock levels for monitoring — large drawdowns are
    picked up by the BOCD on price impact.
    """
    data = await _eia_request("petroleum/stoc/wstk/data", {
        "frequency": "weekly",
        "data[0]": "value",
        "facets[product][]": "EPC0",   # Crude oil
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": "2",
    })

    if data and "data" in data:
        for row in data["data"]:
            value = row.get("value")
            period = row.get("period", "")
            if value:
                log.info("EIA weekly crude stocks: %s = %s thousand barrels", period, value)


async def _poll_eia() -> list[NormalizedSignal]:
    """
    Combined EIA API polling. Runs hourly (less frequent than yfinance).
    Returns signals only if EIA spot price triggers BOCD.
    """
    global _last_eia_poll
    import time as _time

    now = _time.monotonic()
    if now - _last_eia_poll < EIA_POLL_INTERVAL_S:
        return []
    _last_eia_poll = now

    log.info("Polling EIA Open Data API...")
    signals = await _poll_eia_spot_prices()
    await _poll_eia_weekly_stocks()
    return signals


async def run() -> None:
    """
    Entry point. Polls yfinance every 5 minutes and EIA hourly.
    Emits signals only on BOCD changepoints or regime shifts.
    """
    log.info(
        "Price sub-agent started. Instruments=%s, interval=%ds, EIA_key=%s...",
        INSTRUMENTS, POLL_INTERVAL_S,
        EIA_API_KEY[:8] if EIA_API_KEY else "MISSING",
    )

    # Seed initial prices from yfinance
    for instrument in INSTRUMENTS:
        try:
            ticker = yf.Ticker(instrument)
            hist = ticker.history(period="5d", interval="5m")
            if not hist.empty:
                closes = hist["Close"].tolist()
                _series[instrument].extend(closes)
                _last_price[instrument] = closes[-1]
                # Warm up BOCD state
                for p in closes:
                    _update_bocd(instrument, p)
                log.info("Seeded %s with %d historical ticks, latest=%.2f",
                         instrument, len(closes), closes[-1])
        except Exception as exc:
            log.warning("Failed to seed %s: %s", instrument, exc)

    # Seed from EIA on first run
    try:
        eia_signals = await _poll_eia()
        for sig in eia_signals:
            await emit(sig)
    except Exception as exc:
        log.warning("EIA initial seed failed: %s", exc)

    while True:
        try:
            # yfinance (every cycle)
            signals = await _poll_prices()

            # EIA (hourly, rate-limited internally)
            eia_sigs = await _poll_eia()
            signals.extend(eia_sigs)

            for signal in signals:
                await emit(signal)
                log.info("Price signal: %s", signal.summary)
        except Exception as exc:
            log.error("Price poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_S)
