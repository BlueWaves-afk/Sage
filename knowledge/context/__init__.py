"""
SAGE context bundles — foundational static knowledge.

A context bundle is the geopolitical/structural graph state SAGE is instantiated
with before any live signal arrives. Conceptually it is to SAGE what pretrained
weights are to a model: load it, and the system starts with foundational world
knowledge. Swap it for a newer or region-specific bundle to re-base the worldview.

    from knowledge.context import load_bundle
    bundle = load_bundle("data/india-energy-2026.context")
    await bundle.instantiate(graphiti)      # writes all structural episodes

The bundle format (manifest.yaml + nodes/*.csv + edges/*.csv) is documented in
data/CONTEXT_BUNDLE_SCHEMA.md.
"""
from knowledge.context.loader import (
    ContextBundle,
    BundleValidationError,
    load_bundle,
    validate_bundle,
)
from knowledge.context.dedup import canonicalize_graph

__all__ = [
    "ContextBundle",
    "BundleValidationError",
    "load_bundle",
    "validate_bundle",
    "canonicalize_graph",
]
