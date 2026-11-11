# Contributing

Issues and pull requests are welcome. This is a small reference project: standard library Python, deterministic
output, and documents that say exactly what was and was not checked. Changes should keep it that way.

## Ground rules

1. **Fictional data only.** The group, companies, sites, teams and tickets are invented and generated. Do not add
   a real organisation, person, site or ticket export, and do not add anything taken from an employer or client.
2. **Standard library only** for the generator, loader and report builder. `pytest` is the only test dependency.
3. **Deterministic output.** The same seed must give byte-identical files. Sort anything whose order matters, never
   write timestamps into outputs, and never rely on set or dict order.
4. **Every number in a document comes from a run.** If a figure in the README, the board pack or the guidance changes,
   regenerate it and update the text. Tests compare the committed outputs and the commentary with a fresh run.
5. **Say what was not run.** Power BI, SQL Server and GitHub Actions were not available when this was written.
   If you run any of them, add what you ran and what happened to the Verification status in the README and in
   `powerbi/README.md`. If you change DAX or M, keep the documentation header on every measure.
6. **British English, plain tone, no long dashes** (neither the em dash nor the en dash). Use commas, colons, full
   stops or brackets. No marketing language.
7. **No benchmarks without a source.** Targets are labelled as examples. Do not present a number as an industry norm
   unless you can cite a public source in the same change.

## Set up and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest
python -m pytest -q
```

## Changing behaviour

The files in `data/`, `model/` and `reports/` are committed, and tests fail if they differ from a fresh run. After
changing the generator, the SQL views or the report builder, regenerate them in the same change:

```bash
python run_pipeline.py
python -m pytest -q
```

If you edit `reports/commentary-2025-11.md`, keep the figures it quotes in agreement with the tables. A test checks this.

If you change a SQL view, add or update a test in `tests/test_views_fixture.py` with a value worked out by hand
from the fixture in `tests/fixture_builder.py`, not copied from the view's output. If you change the DAX, update
`powerbi/measures.md` in the same change. If you change a CSV column, update `powerbi/data-dictionary.md`.

## Pull request checklist

- [ ] Tests added or updated, and passing
- [ ] `python run_pipeline.py` run, and regenerated files committed
- [ ] Figures in documents updated from real output
- [ ] No real data, names or credentials anywhere in the diff
- [ ] Verification status updated if what was or was not run has changed

## Reporting a problem with the data or logic

Open an issue with the view name, the inputs that give the wrong answer, and the answer you expected with your
working. A hand-worked example is the quickest way to a fix.
