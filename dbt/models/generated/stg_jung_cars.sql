-- GENERATED from config/contracts/jung_cars.yaml by `dqf controls generate`. Do not edit.
-- Batch under test (one or more scenarios), typed by the Python loader from the contract.
select
    _scenario_id,
    _row_id,
    "MPG",
    "Cylinders",
    "Displacement",
    "Horsepower",
    "Weight",
    "Acceleration",
    "Model",
    "Origin"
from read_parquet('{{ var("batch_path") }}')
