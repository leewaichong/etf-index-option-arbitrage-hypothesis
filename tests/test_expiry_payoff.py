from collections import Counter
from datetime import date
import csv
import zipfile

import pytest

from spyspx.expiry_payoff import Quote, evaluate, payoff, select_pairs, validate_quote
from spyspx.expiry_payoff_source import SCHEMA, read_zip


def q(root, strike, bid=2, ask=3, *, day=date(2022, 9, 15), expiry=date(2022, 9, 16), close=None, style=None, settle="PM"):
    close = close or (400 if root == "SPY" else 4000)
    style = style or ("A" if root == "SPY" else "E")
    osi_strike = int(round(strike * 1000))
    contract = f"{root}{expiry:%y%m%d}C{osi_strike:08d}"
    return Quote(contract, root, expiry, "call", strike, style, day, bid, ask, close, settle)


@pytest.mark.parametrize("spy_terminal,idx_terminal,expected", [
    (399, 3990, 0),       # neither leg ITM
    (401, 3990, -1000),   # short SPY only ITM
    (399, 4010, 1000),    # long SPXW only ITM
    (401, 4010, 0),       # same ratio, intrinsic cancels
])
def test_terminal_intrinsic_cash_signs_and_ratio_cancellation(spy_terminal, idx_terminal, expected):
    result = payoff(q("SPY", 400), q("SPXW", 4000), 10, spy_terminal, idx_terminal)
    assert result.terminal_value == expected
    assert result.crossing_credit == 1700
    assert result.midpoint_credit == 2250
    assert result.reverse_crossing_pnl == -2800 - expected


def test_basis_residual_notional_mismatch_and_index_stress():
    spy = q("SPY", 400, close=400)
    idx = q("SPXW", 3980, close=3980)
    result = payoff(spy, idx, 9.95, 402, 4000)
    assert result.terminal_value == 0
    assert result.strike_cash_mismatch == 2000
    assert result.entry_underlying_exposure_mismatch == -2000
    assert result.terminal_stress_low <= result.terminal_value <= result.terminal_stress_high


@pytest.mark.parametrize("stress", [-1, float("nan"), float("inf"), ""])
def test_invalid_stress_points_rejected(stress):
    with pytest.raises(ValueError, match="stress_points"):
        payoff(q("SPY", 400), q("SPXW", 4000), 10, 400, 4000, stress)


@pytest.mark.parametrize("change,reason", [
    ({"bid": float("nan")}, "quote"), ({"ask": 0}, "quote"),
    ({"strike": 400.5}, "contract_identity"), ({"right": "put"}, "right"),
    ({"style": "E"}, "spy_style_settlement"), ({"settlement_time": "AM"}, "spy_style_settlement"),
    ({"contract": "SPX220916C04000000"}, "contract_root"),
    ({"contract": "SPY221332C00400000"}, "contract_identity"),
    ({"contract": "SPY220923C00400000"}, "contract_identity"),
    ({"underlying_close": float("inf")}, "underlying_close"),
    ({"quote_date": date(2022, 9, 17)}, "date"),
])
def test_contract_and_numeric_validation(change, reason):
    from dataclasses import replace
    if reason == "contract_root":
        change["contract"] = "SPX220916C00400000"
    assert validate_quote(replace(q("SPY", 400), **change)) == reason


def test_matching_lower_strike_tie_and_future_independence():
    spy = q("SPY", 400)
    lower, upper = q("SPXW", 3997), q("SPXW", 4003)
    assert select_pairs([spy, lower, upper])[0][1] == lower
    # Adding any future quote cannot affect the prior entry selection.
    future = q("SPXW", 4100, day=date(2022, 9, 16), expiry=date(2022, 9, 17))
    assert select_pairs([spy, lower, upper]) == select_pairs([spy, lower, upper, future])


def test_conflicting_same_day_underlyings_excluded_and_missing_terminal_counted():
    spy = q("SPY", 400)
    idx = q("SPXW", 4000)
    spy_conflict = q("SPY", 400.1, close=401)
    counts = Counter()
    assert select_pairs([spy, spy_conflict, idx], counts) == []
    assert counts["entry_underlying_conflict_or_missing"] == 1
    pair = (spy, q("SPXW", 4000), 10)
    assert evaluate([pair], {}, counts) == []
    assert counts["missing_terminal_reference"] == 1
    for bad in (float("nan"), float("inf"), 0, ""):
        assert evaluate([pair], {(spy.expiration, "SPY"): bad, (spy.expiration, "SPXW"): 4000}, counts) == []
    assert counts["invalid_terminal_reference"] == 4


def test_duplicates_are_rejected_and_exact_expiry_day_required():
    counts = Counter()
    assert select_pairs([q("SPY", 400), q("SPY", 400, bid=1), q("SPXW", 4000)], counts) == []
    assert counts["duplicate_conflict"] == 1
    consistent_counts = Counter()
    selected = select_pairs([q("SPY", 400), q("SPY", 400), q("SPXW", 4000)], consistent_counts)
    assert len(selected) == 1
    assert consistent_counts["duplicate"] == 1
    wrong_day = q("SPY", 400, day=date(2022, 9, 14))
    assert select_pairs([wrong_day, q("SPXW", 4000)]) == []


def test_moneyness_tolerance_and_spy_two_percent_edges():
    counts = Counter()
    assert select_pairs([q("SPY", 400), q("SPXW", 3995)], counts) == []
    assert counts["moneyness_mismatch"] == 1
    assert len(select_pairs([q("SPY", 400), q("SPXW", 3996.01)])) == 1
    edge_pairs = []
    for strike in (392, 408):
        edge_pairs.extend(select_pairs([q("SPY", strike), q("SPXW", strike * 10)]))
    assert len(edge_pairs) == 2
    out_counts = Counter()
    assert select_pairs([q("SPY", 391.99), q("SPXW", 3919.9)], out_counts) == []
    assert out_counts["spy_outside_2pct"] == 1


def test_expiry_date_mismatch_rejects_pair():
    assert select_pairs([q("SPY", 400), q("SPXW", 4000, expiry=date(2022, 9, 17))]) == []


def test_zip_adapter_34_column_fixture_and_proxy_root_separation(tmp_path):
    archive_path = tmp_path / "sample.zip"
    rows = [
        [q("SPY", 400).contract, "SPY", "2022-09-16", "call", "400", "A", "2022-09-15", "2", "1", "3", "1", "", "1", "1", "", "", "", "", "", "", "", "", "", "400", "PM", "", "", "", "0", "", "", "", "", ""],
        [q("SPXW", 4000).contract, "SPXW", "2022-09-16", "call", "4000", "E", "2022-09-15", "20", "1", "21", "1", "", "1", "1", "", "", "", "", "", "", "", "", "", "4000", "PM", "", "", "", "0", "", "", "", "", ""],
        ["SPX220916C04000000", "SPX", "2022-09-16", "call", "4000", "E", "2022-09-15", "20", "1", "21", "1", "", "1", "1", "", "", "", "", "", "", "", "", "", "4000", "PM", "", "", "", "0", "", "", "", "", ""],
    ]
    assert all(len(row) == len(SCHEMA) == 34 for row in rows)
    with zipfile.ZipFile(archive_path, "w") as zf:
        with zf.open("day_by_date/2022-09-15_options.csv", "w") as raw:
            import io
            stream = io.TextIOWrapper(raw, newline="", encoding="utf-8")
            writer = csv.writer(stream)
            writer.writerow(SCHEMA)
            writer.writerows(rows)
            stream.flush()
    quotes, terminal, counts = read_zip(archive_path)
    assert len(quotes) == 2
    assert {x.underlying for x in quotes} == {"SPY", "SPXW"}
    assert terminal[(date(2022, 9, 15), "SPY")] == 400
    assert terminal[(date(2022, 9, 15), "SPXW")] == 4000
    assert not any("SPX" == x.underlying for x in quotes)


def _source_row(root, quote_day, expiry, strike, close, *, right="call", bid="2", ask="3"):
    values = {name: "" for name in SCHEMA}
    values.update({
        "contract": q(root, strike, day=date.fromisoformat(quote_day), expiry=date.fromisoformat(expiry)).contract,
        "underlying": root, "expiration": expiry, "type": right, "strike": str(strike),
        "style": "A" if root == "SPY" else "E", "quote_date": quote_day,
        "bid": bid, "ask": ask, "underlying_close": close, "settlement_time": "PM",
    })
    return values


def _write_source_zip(path, rows):
    with zipfile.ZipFile(path, "w") as archive:
        with archive.open("day_by_date/2022-09-15_options.csv", "w") as raw:
            import io
            stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            writer = csv.DictWriter(stream, fieldnames=SCHEMA)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()


@pytest.mark.parametrize("bad_close", ["nan", "inf", "0", ""])
def test_source_adapter_invalid_close_invalidates_entire_root_date(tmp_path, bad_close):
    path = tmp_path / "invalid-close.zip"
    rows = [
        _source_row("SPY", "2022-09-15", "2022-09-16", 400, "400"),
        _source_row("SPXW", "2022-09-15", "2022-09-16", 4000, "4000"),
        _source_row("SPY", "2022-09-15", "2022-09-15", 400, bad_close, right="put"),
    ]
    _write_source_zip(path, rows)
    quotes, terminal, counts = read_zip(path)
    assert {quote.underlying for quote in quotes} == {"SPXW"}
    assert (date(2022, 9, 15), "SPY") not in terminal
    assert counts["invalid_underlying_close_rows"] == 1
    assert counts["terminal_underlying_conflict"] == 1
    assert counts["entry_underlying_conflict"] == 1


def test_source_adapter_conflicting_closes_invalidate_root_date(tmp_path):
    path = tmp_path / "conflicting-close.zip"
    rows = [
        _source_row("SPY", "2022-09-15", "2022-09-16", 400, "400"),
        _source_row("SPXW", "2022-09-15", "2022-09-16", 4000, "4000"),
        _source_row("SPY", "2022-09-15", "2022-09-15", 400, "401", right="put"),
    ]
    _write_source_zip(path, rows)
    quotes, terminal, counts = read_zip(path)
    assert {quote.underlying for quote in quotes} == {"SPXW"}
    assert (date(2022, 9, 15), "SPY") not in terminal
    assert counts["terminal_underlying_conflict"] == 1
    assert counts["entry_underlying_conflict"] == 1


def test_crossed_quote_and_reverse_crossing_use_opposite_sides():
    crossed = q("SPY", 400, bid=3, ask=2)
    assert validate_quote(crossed) == "quote"
    spy = q("SPY", 400, bid=1, ask=4)
    idx = q("SPXW", 4000, bid=2, ask=8)
    result = payoff(spy, idx, 10, 400, 4000)
    assert result.crossing_credit == 200
    assert result.reverse_crossing_pnl == 200 - 4000
    assert result.reverse_crossing_pnl != -result.gross_crossing_pnl
