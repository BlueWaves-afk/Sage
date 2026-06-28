"""
Commodity price sub-agent.

Polls EIA API + yfinance every 5 minutes.
Runs Bayesian Online Changepoint Detection (BOCD) inline on every tick.
BOCD breakpoint detected → HIGH priority, force_synthesis=True.
Regime-switching HMM estimates calm vs stressed market state.
War-risk premium derived from GDELT shipping-sector tone + insurance news.
"""
from __future__ import annotations

from contracts.signal import NormalizedSignal, PricePayload

INSTRUMENTS = ["BZ=F", "CL=F"]   # Brent, WTI


async def run() -> None:
    """Entry point. APScheduler polls every 5 minutes."""
    # TODO: schedule _poll_prices() every 5 min
    raise NotImplementedError


async def _poll_prices() -> list[NormalizedSignal]:
    """Fetch latest prices, run BOCD, emit signals. Stub."""
    signals = []
    for instrument in INSTRUMENTS:
        # TODO: fetch price tick from yfinance or EIA API
        # TODO: run BOCD on rolling price series stored in Redis
        # TODO: run regime-switching HMM to classify calm/stressed
        # TODO: estimate war_risk_premium from GDELT tone
        changepoint = False   # TODO: replace with BOCD result
        signal = None         # TODO: build NormalizedSignal with force_synthesis=changepoint
        if signal:
            signals.append(signal)
    return signals
