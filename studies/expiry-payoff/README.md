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
  evaluates fixed-share hedges and an opening-price ITM hedge rule across four
  periods. The results do not establish repeatable profit after costs.
- [Approved aggregate report](../../reports/expiry-payoff/executive-report-20261029.pdf)
  contains the stock-reference comparison report.

## Source and rerun status

The `src/spyspx` expiry package and `scripts/expiry_*.py` runners are source
exports assigned to this study. The source was ported from a private research
checkout; it is not the clean SHA used for the historical evaluations. See the
[source inventory](../../results/expiry-payoff/source-provenance.md) for original
and exported hashes and the publication-only changes.

**Implemented:** the source export and synthetic tests are present.
**Locally verified:** run the offline command below from the repository root.
**Evaluated:** the three historical followups ran on the clean SHAs recorded in
their result notes. Those evaluations predate this export.
**Historical public rerun: NOT RUN.** The public checkout does not contain the
licensed exports, exact frozen manifests, run receipts or private control files
needed by the guarded historical runners. Do not treat a local source test as a
re-evaluation of a strategy.

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
