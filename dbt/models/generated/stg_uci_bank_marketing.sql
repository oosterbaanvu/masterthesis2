-- GENERATED from config/contracts/uci_bank_marketing.yaml by `dqf controls generate`. Do not edit.
-- Batch under test (one or more scenarios), typed by the Python loader from the contract.
select
    _scenario_id,
    _row_id,
    "age",
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "contact",
    "month",
    "day_of_week",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
    "emp.var.rate",
    "cons.price.idx",
    "cons.conf.idx",
    "euribor3m",
    "nr.employed"
from read_parquet('{{ var("batch_path") }}')
