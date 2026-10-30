# Expiry-payoff study

This study belongs to the same project family as the original matched-moneyness
measurement, but asks a different question. The original study measures an option
level gap at equal moneyness. This one evaluates hypothetical 10-short-SPY and
1-long-SPXW daily-close expiry and carry cash ledgers, with 100 multipliers.

The primary selection uses one-calendar-day DTE, the full-cross entry, and equal
weights for each expiry. It models fees, financing, dividends and conditional
stock cover. These are historical sensitivities on data already inspected during
the research. No dependable executable edge has been established.

## Evaluated followups

- [OptionMetrics replication](../../results/expiry-payoff/optionmetrics-replication.md)
  reports the 2024 and partial 2025 periods.
- [Timing sensitivity](../../results/expiry-payoff/optionmetrics-timing.md)
  compares prior-close and session-open selection with the entry-close control.
- [Legacy stock-reference comparison](../../results/expiry-payoff/stock-reference-comparison.md)
  reports the fixed 2019 and 2022 contracts under five stock-reference arms.
- [Overnight stock-hedge study](../../results/expiry-payoff/overnight-stock-hedge.md)
  compares fixed-share hedges and an opening-price rule across four periods. It
  does not establish repeatable profit after costs.
- [2023 morning-hedge replication](../../results/expiry-payoff/morning-hedge-replication-2023.md)
  reports the separately evaluated 196-pair period. Its result does not establish
  a reliable after-cost edge.
- [Morning-hedge year-driver attribution](../../results/expiry-payoff/morning-hedge-year-drivers-20261030.md)
  compares 2023 with 2025 and separates the observed overnight stock term from
  other mean-P&L components. The option-quote clock is verified at 15:59 for
  2024 and 2025; the 2023 quote clock remains unverified. It is a post-hoc
  accounting analysis, not a predictive or causal result.
- [Three-year morning-hedge comparison](../../results/expiry-payoff/morning-hedge-three-year-20261030.md)
  and [aggregate summary](../../results/expiry-payoff/morning-hedge-three-year-20261030-summary.json)
  cover the 2023, 2024 and 2025 historical samples. No common-window intervals or
  between-year p-values were calculated.
- The five-page [three-year morning-hedge assessment PDF](../../reports/expiry-payoff/morning-hedge-assessment-20261030.pdf)
  and [full Markdown report](../../reports/expiry-payoff/morning-hedge-assessment-20261030.md)
  contain the final report. The former eight-page version is preserved in the
  [eight-page archive](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.md)
  with its [PDF](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.pdf).
  The earlier five-page version remains in the
  [older archive](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-year-attribution-20261030.md)
  and its [PDF](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-year-attribution-20261030.pdf).
- The earlier [2026-10-30 overnight-hedge assessment](../../reports/expiry-payoff/executive-report-20261030.pdf)
  and [full Markdown report](../../reports/expiry-payoff/overnight-hedge-assessment-20261030.md)
  remain available, along with the [2026-10-29 stock-reference report](../../reports/expiry-payoff/executive-report-20261029.pdf).

## Source and rerun status

The `src/spyspx` expiry package and `scripts/expiry_*.py` runners are source
exports assigned to this study. The source was ported from a private research
checkout; it is not the clean SHA used for the historical evaluations. See the
[source inventory](../../results/expiry-payoff/source-provenance.md) for original
and exported hashes and the publication-only changes.

**Implemented:** the source export and synthetic tests are present.
**Locally verified:** run the offline command below from the repository root.
**Evaluated:** the historical followups ran on the clean SHAs recorded in their
result notes. The 2023 morning-hedge evaluation used clean SHA
`64e72887b782fdf838257a09877ffb817dfbfbdf` and passed independent validation;
its aggregate counts and validation hash are in the result note.
**Historical public rerun: NOT RUN.** The public checkout lacks licensed inputs
and private frozen controls required by the guarded runners. Local tests do not
rerun a historical strategy evaluation.

Stock-reference inputs default under the ignored `data/expiry-payoff/stockrefs/`
directory. In this public port, place the 2022 option archive at
`$SPYSPX_STOCKREFS_OFFICIAL_ROOT/options_sample_2022H2.zip`. When the variable is
unset, that means `data/expiry-payoff/stockrefs/official-extension/options_sample_2022H2.zip`.
The private research checkout kept the archive outside its official-extension
data directory. The public port reads it from this configured root. Set
`SPYSPX_STOCKREFS_WRDS_ROOT`,
`SPYSPX_STOCKREFS_LEGACY_RUNS`, `SPYSPX_STOCKREFS_CALENDAR`,
`SPYSPX_STOCKREFS_LEGACY_2019_ROOT`, `SPYSPX_STOCKREFS_OFFICIAL_ROOT`, and
`SPYSPX_STOCKREFS_CODE_ROOT` to use local copies elsewhere. The 2019 runner
accepts `SPYSPX_2019_INPUT_ROOT`. These settings only locate inputs and code;
frozen hash, parity and clean-state guards remain in force.

Run the full offline test suite with Python 3.12:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

The timing protocol pin test keeps all hash assertions. It skips if any of its
three private frozen control files is absent from the checkout.

Inspect the normalizer and admission command interfaces without reading data:

```sh
PYTHONPATH=src python3 -m spyspx.optionmetrics_normalizer --help
PYTHONPATH=src python3 -m spyspx.optionmetrics_admission --help
```
