-- GENERATED from config/contracts/jung_restaurant.yaml by `dqf controls generate`. Do not edit.
-- Batch under test (one or more scenarios), typed by the Python loader from the contract.
select
    _scenario_id,
    _row_id,
    "name",
    "addr",
    "city",
    "phone",
    "type"
from read_parquet('{{ var("batch_path") }}')
