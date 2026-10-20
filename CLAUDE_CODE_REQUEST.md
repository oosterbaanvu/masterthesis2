Voer deze wijzigingsset uit in mijn GitHub-repository `oosterbaanvu/masterthesis2` op een nieuwe branch vanaf `claude/exciting-ritchie-w1e31t`.

Ik voeg het ZIP-bestand `dq_published_benchmarks_github_patch.zip` toe. Pak de inhoud daarvan uit in de root van de repository (de paden in de ZIP zijn relatief aan de repo-root). Als je niet bij de ZIP kunt, geef dan precies aan welke bestanden je mist; verzin geen datasets of hashes.

De wijzigingsset is gebaseerd op gepubliceerde dirty/clean-benchmarks:
- Raha Rayyan (SIGMOD 2019): 1.000 rijen × 11 kolommen, owner-corrected, real-world bibliographic data.
- Jung et al. Restaurant (JDIQ 2025): 864 rijen × 6 kolommen, synthetisch vervuilde benchmark uit de foutmodelpaper.
- Jung et al. Cars (JDIQ 2025): 406 rijen × 9 kolommen, optioneel: numerieke opmaakverschillen kunnen verkeerde labels opleveren.

Voer achtereenvolgens uit:

1. `python scripts/register_published_benchmarks.py --dry-run` en daarna zonder `--dry-run`.
2. `uv sync --frozen --extra dev` (of de gedocumenteerde installatiestappen).
3. `python scripts/download_datasets.py raha_rayyan jung_restaurant jung_cars` (alle drie expliciet).
4. `python scripts/verify_datasets.py raha_rayyan jung_restaurant jung_cars`.
5. `python scripts/qualify_published_pairs.py raha_rayyan jung_restaurant jung_cars --output data/local_pair_audit.json`.
6. `python -m pytest -q` plus eventuele noodzakelijke dbt-regeneratietests.
7. Controleer de gegenereerde audit, licentiecaveats en of ruwe CSV's genegeerd worden door Git.
8. Commit alleen code, registraties, documentatie en kleine testfixtures; push naar de nieuwe branch. Voeg eventueel een PR toe, maar merge niet automatisch.

Maak vervolgens ook een beknopt technisch vervolgplan om `raha_rayyan` en `jung_restaurant` als onafhankelijke nieuwe databron in de operationele `dqf scan`-service te gebruiken. Dat vereist echte broncontracten, detectorcompatibiliteit, eerlijke train/test-splits en een scheiding tussen dirty-input voor de service en clean-referentie voor de evaluator. Doe niet alsof die integratie of praktijkvalidatie al af is wanneer deze opdracht alleen de data-acquisitie heeft uitgevoerd.

Rapporteer echte uitvoer: downloadstatus, bestanden en hashes, aantallen dirty/clean-verschillen per dataset, groene/rode tests en exacte commit-URL. Gebruik geen Kaggle-token voor deze drie datasets.
