"""Feasibility pilot: detector selection from controlled error injection, and its reliability on held-out data.

Layout of one pilot replication (one dataset, one *pilot seed*):

* The rows of the split-seed-1 **test** partition are a global hold-out reserved for the confirmatory study and
  are never read by the pilot (``splits.design_pool``).
* The remaining *design pool* is re-split per pilot seed, group-aware, into ``reference`` (historical data:
  fits statistical controls and detectors), ``selection`` (scenarios used to choose a detector) and ``test``
  (fresh scenarios on other rows, used only to evaluate the choice). A temporal variant orders the pool by
  delivery period instead.
* Scenarios: two injection *strategies* with the same error cases, rates, number of scenarios and rows:
  ``simple`` (ECAR only) and ``diverse`` (ECAR plus context-dependent mechanisms and realistic segment/batch
  mechanisms); plus a ``heldout`` family of error cases and mechanisms used by neither strategy.
* Baselines: deterministic dbt rules only, and rules + statistical controls.

Modules: ``config`` (YAML), ``splits``, ``scenarios``, ``metrics`` (matrix-based evaluation), ``runner`` (one
replication), ``analysis`` (selection, decisions, regret, overlap, aggregation).
"""
