"""Operational data-quality scan of a new batch (no error injection, no ground truth).

This is the *operational* workflow, deliberately separate from the offline evaluation (``pilot``):

1. connect a dataset through its source contract (``config/contracts/<dataset>.yaml``);
2. choose *historical* rows (training / reference) and a *new batch* (e.g. a later delivery period);
3. run the generated dbt/SQL controls on the batch (statistical bounds fitted on history);
4. fit the configured learned detectors on history (or on the batch, for transductive methods) and score
   the batch;
5. report every finding with record id, column, value, source (rule or detector), score (if the method has
   one) and an explanation;
6. give a recommendation per detector - ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE - that is based only on
   *offline evidence* (pilot results on held-out synthetic scenarios), on the alert burden observed on this
   batch, and on a shift check between this batch and the evaluation conditions. The scan never claims that a
   finding is a true error: findings are review candidates.

An optional feedback file lets a data engineer annotate findings (confirmed_error / not_an_error / unsure);
``summarise_feedback`` turns those annotations into adjudicated precision per source. Feedback is an
annotation aid, not part of the research question.
"""
