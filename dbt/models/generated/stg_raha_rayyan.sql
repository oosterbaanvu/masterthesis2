-- GENERATED from config/contracts/raha_rayyan.yaml by `dqf controls generate`. Do not edit.
-- Batch under test (one or more scenarios), typed by the Python loader from the contract.
select
    _scenario_id,
    _row_id,
    "id",
    "article_title",
    "article_language",
    "journal_title",
    "jounral_abbreviation",
    "journal_issn",
    "article_jvolumn",
    "article_jissue",
    "article_jcreated_at",
    "article_pagination",
    "author_list"
from read_parquet('{{ var("batch_path") }}')
