"""REPRODUCTION SCRIPT. Needs a local copy of the HistoricalData.net 2022 H2 sample.

The sample is not included in this repository and must not be committed. Download
``options_sample_2022H2.zip`` from https://historicaldata.net/options.html, read
its licence, and pass either the zip itself or its extracted ``day_by_date``
folder:

    python3 examples/reproduce_from_sample.py /path/to/options_sample_2022H2.zip
    python3 examples/reproduce_from_sample.py /path/to/day_by_date --out my_table.csv

It regenerates the cohort table with the published method, diffs it against
``results/cohort_2022h2.csv`` and prints the sensitivity checks quoted in the
README (parity-forward ratio, a 1 ETF point strike tolerance, and two alternative
minimum-strike rules). Standard library only. Exit code 0 when every published
cohort matches.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import statistics as st
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
import matched_moneyness as mm  # noqa: E402

DAY_FILE = re.compile(r"(?:^|/)(\d{4}-\d{2}-\d{2})_options\.csv$")


def day_files(sample: str):
    """Yield (quote_date, text stream) per daily file, in date order."""
    if sample.endswith(".zip"):
        with zipfile.ZipFile(sample) as zf:
            names = sorted(n for n in zf.namelist() if DAY_FILE.search(n))
            for n in names:
                with zf.open(n) as fh:
                    yield DAY_FILE.search(n).group(1), io.TextIOWrapper(fh, encoding="utf-8", newline="")
    else:
        for n in sorted(os.listdir(sample)):
            m = DAY_FILE.search(n)
            if m:
                with open(os.path.join(sample, n), newline="", encoding="utf-8") as fh:
                    yield m.group(1), fh


def summary(label: str, table: list) -> str:
    v = mm.verdict(table)
    meds = [r["median_gap_bps"] for r in table]
    neg = sum(m < 0 for m in meds)
    zero = sum(m == 0 for m in meds)
    return (f"{label}: cohorts {len(table)}, pairs {sum(r['n_pairs'] for r in table)}, "
            f"median {v.get('median_of_cohort_medians_bps')} bps, {neg} neg / "
            f"{v.get('cohorts_positive')} pos / {zero} zero, same-sign share {v.get('same_direction_share')}, "
            f"{v['verdict']}")


def diff(table: list, published_csv: str) -> int:
    pub = {r["cohort_expiry"]: r for r in csv.DictReader(open(published_csv, newline=""))}
    mine = {r["cohort_expiry"]: r for r in table}
    bad = 0
    for exp in sorted(set(pub) | set(mine)):
        p, m = pub.get(exp), mine.get(exp)
        if p is None or m is None:
            print(f"  MISSING {exp}: published={p is not None} regenerated={m is not None}")
            bad += 1
        elif int(p["n_pairs"]) != m["n_pairs"] or f"{float(p['median_gap_bps']):.3f}" != f"{m['median_gap_bps']:.3f}":
            print(f"  DIFF {exp}: published n={p['n_pairs']} med={p['median_gap_bps']}"
                  f" regenerated n={m['n_pairs']} med={m['median_gap_bps']:.3f}")
            bad += 1
    print(f"check vs {os.path.relpath(published_csv, REPO)}: "
          f"{len(pub) - sum(1 for e in pub if e not in mine)} of {len(pub)} cohorts present, "
          f"{bad} mismatched (n_pairs exact, median to 3 dp)")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sample", help="options_sample_2022H2.zip or its day_by_date folder")
    ap.add_argument("--published", default=os.path.join(REPO, "results", "cohort_2022h2.csv"))
    ap.add_argument("--out", help="write the regenerated main table to this CSV")
    args = ap.parse_args()

    main_pairs, tol_pairs, parity_pairs = [], [], []
    n_far = n_days = 0
    non_unique = []
    for qd, fh in day_files(args.sample):
        snap = mm.load_snapshot(csv.DictReader(fh))
        if snap.quote_date != qd:
            raise SystemExit(f"{qd}: file quote_date column says {snap.quote_date}")
        n_days += 1
        for root in (mm.ETF_ROOT, mm.INDEX_ROOT):
            if not snap.close_is_unique(root):
                non_unique.append((qd, root, sorted(snap.close_values.get(root, ()))))
        a = mm.measure_snapshot(snap)
        main_pairs += a["pairs"]
        n_far += a["n_offset_over_1pt"]
        tol_pairs += mm.measure_snapshot(snap, max_offset=1.0)["pairs"]
        parity_pairs += mm.measure_snapshot(snap, ratio_method="parity")["pairs"]

    table = mm.cohort_table(main_pairs)
    offsets = sorted(abs(p.offset_etf_points) for p in main_pairs)
    worst = min(main_pairs, key=lambda p: p.gap_bps)
    far = max(main_pairs, key=lambda p: abs(p.offset_etf_points))
    print(f"days read {n_days}; days with a non-unique SPY or SPXW close {len(non_unique)}")
    print(summary("main (published method)", table))
    print(f"matched strike more than 1 ETF point off: {n_far} of {len(main_pairs)} pairs "
          f"({100 * n_far / len(main_pairs):.1f}%), median offset {st.median(offsets):.3f}, "
          f"max {offsets[-1]:.2f} ETF points; lowest single pair {worst.gap_bps:.1f} bps "
          f"({worst.quote_date} {worst.expiry} K={worst.etf_strike:g} vs {worst.index_strike:g}); "
          f"furthest-off pair scores {far.gap_bps:.1f} bps")
    bad = diff(table, args.published)

    print("sensitivity (not the published table):")
    print("  " + summary("parity-forward ratio", mm.cohort_table(parity_pairs)))
    print("  " + summary("tolerance 1 ETF point", mm.cohort_table(tol_pairs)))
    for rule in ("pairs", "per_snapshot"):
        alt = mm.cohort_table(main_pairs, count=rule)
        base = {r["cohort_expiry"]: r for r in table}
        other = {r["cohort_expiry"]: r for r in alt}
        changed = sum(1 for e in set(base) | set(other) if base.get(e) != other.get(e))
        print("  " + summary(f"min-strikes rule '{rule}'", alt) + f"; cohorts differing from main {changed}")
    par = {r["cohort_expiry"]: r["median_gap_bps"] for r in mm.cohort_table(parity_pairs)}
    for exp in ("2022-09-16", "2022-12-16"):
        m = next((r["median_gap_bps"] for r in table if r["cohort_expiry"] == exp), None)
        print(f"  ex-dividend cohort {exp}: main {m} bps, parity-forward {par.get(exp)} bps")

    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["cohort_expiry", "n_pairs", "median_gap_bps"])
            w.writeheader()
            w.writerows(table)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
