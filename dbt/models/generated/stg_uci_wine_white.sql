-- GENERATED from config/contracts/uci_wine_white.yaml by `dqf controls generate`. Do not edit.
-- Batch under test (one or more scenarios), typed by the Python loader from the contract.
select
    _scenario_id,
    _row_id,
    "fixed acidity",
    "volatile acidity",
    "citric acid",
    "residual sugar",
    "chlorides",
    "free sulfur dioxide",
    "total sulfur dioxide",
    "density",
    "pH",
    "sulphates",
    "alcohol"
from read_parquet('{{ var("batch_path") }}')
