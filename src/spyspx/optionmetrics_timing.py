"""Frozen exploratory timing-reference sensitivity for the OptionMetrics study."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import optionmetrics_normalizer as normalizer
from . import optionmetrics_replication as base

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "planning/optionmetrics-timing-20261029/candidate-protocol.md"
MANIFEST = ROOT / "planning/optionmetrics-timing-20261029/comparison-manifest.json"
PROTOCOL_SHA256 = "e4ae0387236466fa1a69bfdc7e654501a4a6dde292077412e86f8199d052cae7"
MANIFEST_SHA256 = "0464e6716d18e2715193c275017fb65fd0a90a8e57dbd2f3c39168a0e3dd7f8d"
MODES = ("close_reference", "prior_session_close", "current_session_open")
CODE_PATHS = ("src/spyspx/optionmetrics_timing.py", "src/spyspx/optionmetrics_replication.py",
              "src/spyspx/optionmetrics_normalizer.py", "src/spyspx/optionmetrics_admission.py",
              "src/spyspx/expiry_extension.py", "src/spyspx/expiry_payoff.py")
IMPORTED_MODULES = {
    "src/spyspx/optionmetrics_timing.py": lambda: sys.modules[__name__],
    "src/spyspx/optionmetrics_replication.py": lambda: base,
    "src/spyspx/optionmetrics_normalizer.py": lambda: normalizer,
    "src/spyspx/optionmetrics_admission.py": lambda: sys.modules["spyspx.optionmetrics_admission"],
    "src/spyspx/expiry_extension.py": lambda: sys.modules["spyspx.expiry_extension"],
    "src/spyspx/expiry_payoff.py": lambda: sys.modules["spyspx.expiry_payoff"],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture_identity(repo: Path) -> dict:
    head, clean = base._git_clean(repo)
    if not clean:
        raise ValueError("run requires a clean Git worktree before any raw source read")
    code = {}
    for relative in CODE_PATHS:
        loaded_path = Path(IMPORTED_MODULES[relative]().__file__).resolve(strict=True)
        path = repo / relative
        expected_path = path.resolve(strict=True)
        if loaded_path != expected_path:
            raise ValueError(f"loaded module path does not match repository: {relative}")
        data = path.read_bytes()
        blob = subprocess.run(["git", "show", f"{head}:{relative}"], cwd=repo, capture_output=True)
        if blob.returncode or blob.stdout != data:
            raise ValueError(f"loaded code does not match initial HEAD: {relative}")
        code[relative] = {"path": str(expected_path), "loaded_path": str(loaded_path),
                          "sha256": sha(data), "bytes": len(data), "data": data}
    return {"head": head, "code": code}


def check_identity(repo: Path, identity: dict, inputs: dict, selection: tuple[Path, str] | None = None) -> dict:
    head, clean = base._git_clean(repo)
    if head != identity["head"] or not clean:
        raise ValueError("BLOCKED: Git HEAD or clean state changed during run")
    for relative, rec in identity["code"].items():
        loaded_path = Path(IMPORTED_MODULES[relative]().__file__).resolve(strict=True)
        if str(loaded_path) != rec["loaded_path"] or loaded_path != (repo / relative).resolve(strict=True):
            raise ValueError(f"BLOCKED: imported module path changed: {relative}")
        data = Path(rec["path"]).read_bytes()
        blob = subprocess.run(["git", "show", f"{head}:{relative}"], cwd=repo, capture_output=True)
        if data != rec["data"] or sha(data) != rec["sha256"] or blob.returncode or blob.stdout != data:
            raise ValueError(f"BLOCKED: code changed during run: {relative}")
    if not base._snapshots_unchanged(inputs):
        raise ValueError("BLOCKED: source, protocol, manifest, or control changed during run")
    if selection and sha(selection[0].read_bytes()) != selection[1]:
        raise ValueError("BLOCKED: durable selection snapshot changed during run")
    return {"status": "PASS", "head": head, "clean": clean,
            "code_sha256": {relative: record["sha256"] for relative, record in identity["code"].items()},
            "input_sha256": {role: record["sha256"] for role, record in inputs.items()},
            "selection_sha256": selection[1] if selection else None}


def atomic_run_audit(path: Path, payload: dict, repo: Path, identity: dict, inputs: dict,
                     selection: tuple[Path, str] | None = None) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name("." + path.name + ".tmp")
    if stage.exists():
        raise FileExistsError(stage)
    try:
        payload["integrity_check_before_audit_publish"] = check_identity(repo, identity, inputs, selection)
        stage.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
        publish_checkpoint = check_identity(repo, identity, inputs, selection)
        if publish_checkpoint != payload["integrity_check_before_audit_publish"]:
            payload["integrity_check_before_audit_publish"] = publish_checkpoint
            stage.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
            final_checkpoint = check_identity(repo, identity, inputs, selection)
            if final_checkpoint != publish_checkpoint:
                raise ValueError("integrity checkpoint changed before audit publish")
        if path.exists():
            raise FileExistsError(path)
        os.rename(stage, path)
    except Exception:
        stage.unlink(missing_ok=True)
        raise


def atomic_publish_run_bundle(output: Path, documents: dict[str, dict], run_manifest: dict,
                              repo: Path, identity: dict, inputs: dict,
                              selection: tuple[Path, str]) -> dict:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        hashes = {}
        for name, document in documents.items():
            data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
            (stage / name).write_bytes(data)
            hashes[name] = sha(data)
        run_manifest["ended_utc"] = datetime.now(timezone.utc).isoformat()
        run_manifest["output_sha256"] = hashes
        run_manifest["integrity_checkpoints"]["immediately_before_atomic_bundle_publish"] = check_identity(
            repo, identity, inputs, selection)
        run_manifest["integrity_after"] = run_manifest["integrity_checkpoints"]["immediately_before_atomic_bundle_publish"]
        manifest_path = stage / "manifest.json"
        manifest_path.write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n")
        # Recheck after writing every artifact and the manifest, directly before rename.
        checkpoint = check_identity(repo, identity, inputs, selection)
        run_manifest["integrity_checkpoints"]["immediately_before_atomic_bundle_publish"] = checkpoint
        manifest_path.write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n")
        manifest_hash = sha(manifest_path.read_bytes())
        receipt = {"status": run_manifest["status"], "output": str(output), "manifest_sha256": manifest_hash,
                   "artifact_sha256": hashes}
        receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
        (stage / "cli-receipt.json").write_bytes(receipt_bytes)
        final_check = check_identity(repo, identity, inputs, selection)
        if final_check != checkpoint:
            raise ValueError("BLOCKED: integrity changed after manifest staging")
        if output.exists():
            raise FileExistsError(f"output already exists: {output}")
        os.rename(stage, output)
        return {"output_sha256": hashes, "manifest_sha256": manifest_hash,
                "cli_receipt_sha256": sha((output / "cli-receipt.json").read_bytes())}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _reference_sets(prices: dict, spx: dict, sessions: set, pairs: list[dict]) -> dict:
    by_session = sorted(sessions)
    previous = {right: left for left, right in zip(by_session, by_session[1:])}
    result = {mode: ({}, {}) for mode in MODES}
    for pair in pairs:
        day = pair["entry"]
        spy = prices.get((base.SECURITY_IDS["SPY"], day))
        if not spy or spy["cfadj"] != 1.0:
            raise ValueError(f"missing or nonunit SPY reference for {day}")
        if day not in spx:
            raise ValueError(f"missing official SPX reference for {day}")
        result["close_reference"][0][(base.SECURITY_IDS["SPY"], day)] = {"close": spy["close"]}
        result["close_reference"][1][day] = spx[day]
        prior = previous.get(day)
        if prior is None:
            raise ValueError(f"missing immediately preceding session for {day}")
        prior_spy = prices.get((base.SECURITY_IDS["SPY"], prior))
        if not prior_spy or prior_spy["cfadj"] != 1.0:
            raise ValueError(f"missing or nonunit prior-session SPY reference for {day} ({prior})")
        if prior not in spx:
            raise ValueError(f"missing official prior-session SPX reference for {day} ({prior})")
        result["prior_session_close"][0][(base.SECURITY_IDS["SPY"], day)] = {"close": prior_spy["close"]}
        result["prior_session_close"][1][day] = spx[prior]
        spy_open = base._number(spy["open"], "current-session raw SPY open", positive=True)
        spx_row = prices.get((base.SECURITY_IDS["SPX"], day))
        if not spx_row or spx_row["cfadj"] != 1.0:
            raise ValueError(f"missing or nonunit current-session SPX reference for {day}")
        spx_open = base._number(spx_row["open"], "current-session raw SPX open", positive=True)
        result["current_session_open"][0][(base.SECURITY_IDS["SPY"], day)] = {"close": spy_open}
        result["current_session_open"][1][day] = spx_open
    return result


def _select_with_references(quotes: list[dict], pairs: list[dict], spy_prices: dict, spx_prices: dict) -> tuple[list[dict], dict]:
    """Apply the original eligibility rules with explicit reference-price maps."""
    by_day: dict = {}
    for row in quotes:
        if row["normalized_cp_flag"] != "C" or row["normalized_contract_size"].strip() != "100" or row["normalized_special_settlement"]:
            continue
        if row["symbol"].split(" ", 1)[0] == "SPX":
            continue
        try:
            bid = base._number(row["normalized_best_bid"], "option bid", positive=True)
            ask = base._number(row["normalized_best_offer"], "option ask", positive=True)
        except ValueError:
            continue
        if ask < bid:
            continue
        day = base.iso_day(row["normalized_quote_date"], "quote date")
        expiry = base.iso_day(row["normalized_expiry_date"], "expiry date")
        if (expiry - day).days == 1:
            by_day.setdefault(day, []).append(row)
    selected, missing, candidate_audit = [], [], []
    def canonical_id_key(value):
        text = str(value)
        return (0, int(text)) if text.isdigit() else (1, text)
    for pair in pairs:
        entry, expiry = pair["entry"], pair["expiry"]
        spy_ref = spy_prices.get((base.SECURITY_IDS["SPY"], entry))
        spx_ref = spx_prices.get(entry)
        if not spy_ref or not spx_ref:
            missing.append({"entry": entry.isoformat(), "reason": "missing selection reference"})
            continue
        candidates_spy_all = [r for r in by_day.get(entry, []) if r["normalized_underlying"] == "SPY" and
            r["normalized_exercise_style"] == "A" and r["normalized_am_settlement"] == "0" and r["normalized_expiry_date"] == expiry.isoformat()]
        candidates_idx = [r for r in by_day.get(entry, []) if r["normalized_underlying"] == "SPX" and
            r["normalized_exercise_style"] == "E" and r["normalized_am_settlement"] == "0" and
            r["symbol"].startswith("SPXW ") and r["normalized_expiry_date"] == expiry.isoformat()]
        def strike_range(rows):
            values = [int(r["normalized_strike_milli"]) / 1000 for r in rows]
            return {"min": min(values), "max": max(values)} if values else {"min": None, "max": None}
        candidate_audit.append({"entry": entry.isoformat(), "returned_universe_only": True,
            "bbo_eligible_candidate_count": {"SPY": len(candidates_spy_all), "SPXW": len(candidates_idx)},
            "strike_range": {"SPY": strike_range(candidates_spy_all), "SPXW": strike_range(candidates_idx)}})
        candidates_spy = candidates_spy_all
        candidates_spy = [r for r in candidates_spy if abs(int(r["normalized_strike_milli"]) / 1000 / spy_ref["close"] - 1) <= .02 + 1e-12]
        candidates_spy.sort(key=lambda r: (abs(int(r["normalized_strike_milli"]) / 1000 / spy_ref["close"] - 1),
                                           int(r["normalized_strike_milli"]), canonical_id_key(r["normalized_option_id"])))
        if not candidates_spy or not candidates_idx:
            missing.append({"entry": entry.isoformat(), "reason": "no eligible SPY or SPXW quote"})
            continue
        spy = candidates_spy[0]
        spy_strike = int(spy["normalized_strike_milli"]) / 1000
        idx = []
        for row in candidates_idx:
            strike = int(row["normalized_strike_milli"]) / 1000
            mismatch = abs((strike / spx_ref) / (spy_strike / spy_ref["close"]) - 1)
            if mismatch <= .001 + 1e-12:
                idx.append((mismatch, strike, canonical_id_key(row["normalized_option_id"]), row))
        if not idx:
            missing.append({"entry": entry.isoformat(), "reason": "no SPXW quote within frozen mismatch tolerance"})
            continue
        mismatch, _, _, spxw = min(idx, key=lambda x: x[:3])
        selected.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": pair["cover"].isoformat(),
            "spy": dict(spy), "spxw": dict(spxw), "reference_spy": spy_ref["close"],
            "reference_spx": spx_ref, "moneyness_mismatch": mismatch})
    return selected, {"selected_count": len(selected), "missing_selection_count": len(missing), "missing_selections": missing,
                      "candidate_audit": candidate_audit,
                      "universe_limit": "counts and strike ranges describe returned source rows only, not the complete vendor universe"}


def select_modes(quotes: list[dict], pairs: list[dict], prices: dict, spx: dict, sessions: set,
                 source_hashes: dict | None = None) -> dict:
    references = _reference_sets(prices, spx, sessions, pairs)
    output = {}
    for mode in MODES:
        selected, info = _select_with_references(quotes, pairs, *references[mode])
        for item in selected:
            day = base.iso_day(item["entry"], "entry")
            if mode == "close_reference":
                reference_date = day
                spy_source, spx_source = "close", "official_close"
            elif mode == "prior_session_close":
                reference_date = max(d for d in sessions if d < day)
                spy_source, spx_source = "close", "official_close"
            else:
                reference_date = day
                spy_source, spx_source = "open", "open"
            item["selection_reference"] = {"mode": mode, "date": reference_date.isoformat(),
                "prior_date": reference_date.isoformat() if mode == "prior_session_close" else None,
                "spy_security_id": base.SECURITY_IDS["SPY"], "spx_security_id": base.SECURITY_IDS["SPX"],
                "spy_field": spy_source, "spx_field": spx_source,
                "spy_price": item.pop("reference_spy"), "spx_price": item.pop("reference_spx"),
                "source_sha256": {"spy": (source_hashes or {}).get("security-prices-20190801-20250829.csv"),
                                  "spx": ((source_hashes or {}).get("security-prices-20190801-20250829.csv") if mode == "current_session_open"
                                          else (source_hashes or {}).get("official_spx_calendar"))}}
        # Keep actual closes alongside, and independent from, selection references.
        for item in selected:
            day = base.iso_day(item["entry"], "entry")
            spy_actual = prices[(base.SECURITY_IDS["SPY"], day)]["close"]
            spx_actual = spx[day]
            item["spy_entry_close"] = spy_actual
            item["official_spx_entry_close"] = spx_actual
            item["actual_entry_closes"] = {"spy_close": spy_actual, "official_spx_close": spx_actual}
        output[mode] = {"pairs": selected, "selection": info}
    return output


def evaluate_modes(selected_modes: dict, expected: list[dict], prices: dict, spx: dict,
                   settlements: dict, dividends: list[dict], sessions: set) -> dict:
    """Calculate frozen lanes using the existing ledger after selection is durable."""
    evaluated = {}
    expected_entries = [p["entry"].isoformat() for p in expected]
    if len(expected_entries) != len(set(expected_entries)):
        raise ValueError("expected pair list contains duplicate entries")
    for mode in MODES:
        pairs = []
        for saved in selected_modes[mode]["pairs"]:
            pair = dict(saved)
            ref = pair["selection_reference"]
            pair["spy_entry_close"] = pair["actual_entry_closes"]["spy_close"]
            pair["official_spx_entry_close"] = pair["actual_entry_closes"]["official_spx_close"]
            pairs.append(pair)
        coverage, rows = base._evaluation_rows(pairs, expected, prices, spx, settlements, dividends, sessions)
        refs_by_entry = {item["entry"]: item for item in selected_modes[mode]["pairs"]}
        for row in rows:
            chosen = refs_by_entry[row["entry"]]
            row["selection_reference"] = chosen["selection_reference"]
            row["actual_entry_closes"] = chosen["actual_entry_closes"]
            if mode != "close_reference":
                row["timing_status"] = "EARLIER_REFERENCE_DAILY_QUOTES_THEORETICAL"
                for fill in row["fill_rows"]:
                    fill["timing_status"] = row["timing_status"]
        for item in coverage:
            selection_item = refs_by_entry.get(item["entry"])
            if selection_item:
                item["selection_reference"] = selection_item["selection_reference"]
        evaluated[mode] = {"coverage": coverage, "outcomes": rows}
    return evaluated


def terminal_coverage_blockers(selected_modes: dict, expected: list[dict], prices: dict, spx: dict,
                               settlements: dict, dividends: list[dict], sessions: set) -> list[dict]:
    blockers = []
    expected_entries = [p["entry"].isoformat() for p in expected]
    if len(expected_entries) != len(set(expected_entries)):
        raise ValueError("expected pair list contains duplicate entries")
    for mode in MODES:
        selected_rows = selected_modes[mode]["pairs"]
        selected = _unique_by_entry(selected_rows, f"{mode} selections")
        for pair in expected:
            entry, expiry, cover = (pair[k] for k in ("entry", "expiry", "cover"))
            missing = []
            if entry.isoformat() not in selected:
                missing.append("selected_pair")
            reference_date = (base.iso_day(selected[entry.isoformat()]["selection_reference"]["date"], "selection reference date")
                             if entry.isoformat() in selected else entry)
            for day, label in ((entry, "spy_entry"), (expiry, "spy_expiry"), (cover, "spy_cover")):
                rec = prices.get((base.SECURITY_IDS["SPY"], day))
                if rec is None:
                    missing.append(label)
                elif rec["cfadj"] != 1.0:
                    missing.append(label + "_nonunit_cfadj")
            if entry not in spx:
                missing.append("official_spx_entry")
            if expiry not in spx:
                missing.append("official_spx_expiry")
            if expiry not in settlements:
                missing.append("official_spxw_pm_settlement")
            if not (base.iso_day("2019-08-01", "action coverage") <= reference_date and cover <= base.iso_day("2025-08-29", "action coverage")):
                missing.append("distribution_coverage_gap")
            for day in sessions:
                if reference_date <= day <= cover:
                    rec = prices.get((base.SECURITY_IDS["SPY"], day))
                    if rec is None:
                        missing.append("spy_session_price_gap")
                    elif rec["cfadj"] != 1.0:
                        missing.append("nonunit_spy_cfadj")
            for event in (e for e in dividends if reference_date < e["ex_date"] <= cover):
                if not base._is_confirmed_cash_dividend(event):
                    missing.append("unsupported_distribution_event_from_reference")
            blockers.extend({"mode": mode, "entry": entry.isoformat(), "missing": sorted(set(missing))} for _ in [0] if missing)
    return blockers


def evaluate_after_coverage(selected_modes: dict, expected: list[dict], prices: dict, spx: dict,
                            settlements: dict, dividends: list[dict], sessions: set) -> tuple[list[dict], dict | None]:
    blockers = terminal_coverage_blockers(selected_modes, expected, prices, spx, settlements, dividends, sessions)
    if blockers:
        return blockers, None
    return [], evaluate_modes(selected_modes, expected, prices, spx, settlements, dividends, sessions)


def freeze_before_terminal_joins(selected_modes: dict, expected_count: int, freeze_selection, terminal_loader):
    if set(selected_modes) != set(MODES):
        raise ValueError("all frozen modes must be present before terminal joins")
    if any(len(selected_modes[mode]["pairs"]) != expected_count for mode in MODES):
        raise ValueError("all fixed-denominator selections must be complete before terminal joins")
    selection_snapshot = freeze_selection()
    terminal_sources = terminal_loader()
    return selection_snapshot, terminal_sources


def reference_staleness_audit(selected_modes: dict, dividends: list[dict]) -> dict:
    result = {}
    for mode in MODES:
        rows = []
        for item in selected_modes[mode]["pairs"]:
            entry = base.iso_day(item["entry"], "entry")
            reference = base.iso_day(item["selection_reference"]["date"], "reference date")
            prior_events = [event for event in dividends if reference < event["ex_date"] <= entry and
                            base._is_confirmed_cash_dividend(event)]
            rows.append({"entry": entry.isoformat(), "reference_date": reference.isoformat(),
                         "confirmed_pre_entry_cash_dividend_dates": [event["ex_date"].isoformat() for event in prior_events],
                         "position_dividend_charge_for_pre_entry_events": 0.0,
                         "interpretation": "reference carry or staleness flag only; position was not held before entry"})
        result[mode] = rows
    return result


def returned_universe_candidate_audit(quotes: list[dict], expected: list[dict]) -> list[dict]:
    entries = {p["entry"] for p in expected}
    counts: dict = {}
    for row in quotes:
        day = base.iso_day(row["normalized_quote_date"], "quote date")
        if day not in entries or row["normalized_cp_flag"] != "C" or row["normalized_contract_size"].strip() != "100" or row["normalized_special_settlement"]:
            continue
        try:
            bid = base._number(row["normalized_best_bid"], "option bid", positive=True)
            ask = base._number(row["normalized_best_offer"], "option ask", positive=True)
        except ValueError:
            continue
        if ask < bid or (day, base.iso_day(row["normalized_expiry_date"], "expiry date")) not in {(p["entry"], p["expiry"]) for p in expected}:
            continue
        family = row["normalized_underlying"]
        if family == "SPY" and (row["normalized_exercise_style"], row["normalized_am_settlement"]) != ("A", "0"):
            continue
        if family == "SPX" and (row["normalized_exercise_style"], row["normalized_am_settlement"], row["symbol"].startswith("SPXW ")) != ("E", "0", True):
            continue
        if family not in {"SPY", "SPX"}:
            continue
        key = (day, family)
        counts.setdefault(key, []).append(int(row["normalized_strike_milli"]) / 1000)
    rows = []
    for pair in expected:
        by_family = {}
        for family in ("SPY", "SPX"):
            values = counts.get((pair["entry"], family), [])
            by_family["SPXW" if family == "SPX" else family] = {
                "returned_bbo_eligible_count": len(values), "minimum_strike": min(values) if values else None,
                "maximum_strike": max(values) if values else None}
        rows.append({"entry": pair["entry"].isoformat(), "families": by_family,
                     "universe_limit": "returned rows only; not a claim about the complete vendor universe"})
    return rows


def source_reference_coverage_audit(prices: dict, official_spx: dict, sessions: set,
                                    expected: list[dict], dividends: list[dict]) -> dict:
    ordered = sorted(sessions)
    previous = {right: left for left, right in zip(ordered, ordered[1:])}
    rows, blockers = [], []
    for pair in expected:
        entry, cover = pair["entry"], pair["cover"]
        for mode in MODES:
            reference = previous.get(entry) if mode == "prior_session_close" else entry
            missing = []
            if reference is None:
                missing.append("missing_previous_session")
                reference = entry
            if mode in {"close_reference", "prior_session_close"} and reference not in official_spx:
                missing.append("missing_official_spx_selection_close")
            if mode == "current_session_open":
                for sid, label in ((base.SECURITY_IDS["SPY"], "spy_open"), (base.SECURITY_IDS["SPX"], "spx_open")):
                    price = prices.get((sid, entry))
                    if price is None or price["cfadj"] != 1.0:
                        missing.append(f"missing_or_nonunit_{label}_source")
                    elif not math.isfinite(float(price["open"])) or float(price["open"]) <= 0:
                        missing.append(f"invalid_{label}")
            if reference < base.iso_day("2019-08-01", "distribution coverage") or cover > base.iso_day("2025-08-29", "distribution coverage"):
                missing.append("corporate_action_source_coverage_gap")
            missing_prices = []
            for day in ordered:
                if reference <= day <= cover:
                    price = prices.get((base.SECURITY_IDS["SPY"], day))
                    if price is None or price["cfadj"] != 1.0:
                        missing_prices.append(day.isoformat())
            if missing_prices:
                missing.append("spy_session_price_or_cfadj_gap")
            unsupported = [event["ex_date"].isoformat() for event in dividends
                           if reference < event["ex_date"] <= cover and not base._is_confirmed_cash_dividend(event)]
            if unsupported:
                missing.append("unsupported_distribution_event_from_reference")
            stale_dividends = [event["ex_date"].isoformat() for event in dividends
                               if reference < event["ex_date"] <= entry and base._is_confirmed_cash_dividend(event)]
            row = {"mode": mode, "entry": entry.isoformat(), "reference_date": reference.isoformat(),
                   "cover": cover.isoformat(), "missing": missing, "missing_spy_session_dates": missing_prices,
                   "unsupported_distribution_dates": unsupported,
                   "confirmed_pre_entry_dividend_staleness_dates": stale_dividends,
                   "pre_entry_dividend_position_charge": 0.0}
            rows.append(row)
            if missing:
                blockers.append(row)
    return {"status": "SOURCE_REFERENCE_COVERAGE_BLOCKED" if blockers else "SOURCE_REFERENCE_COVERAGE_PRESENT",
            "expected_count": len(expected), "mode_date_rows": rows, "blockers": blockers,
            "universe_limit": "coverage is for frozen expected dates and returned sources only"}


def compare_modes(evaluated: dict, expected_count: int, period: str) -> dict:
    control = _unique_by_entry(evaluated["close_reference"]["outcomes"], "close-reference outcomes")
    if len(control) != expected_count or any(len(evaluated[m]["outcomes"]) != expected_count for m in MODES):
        raise ValueError("expected selection or terminal coverage is incomplete; no denominator reduction")
    metric_fields = ("direct_intrinsic_pnl", "dividend_carry_pnl", "base_cost_pnl", "stress_cost_pnl")
    paired = {mode: {field: [] for field in metric_fields} for mode in MODES[1:]}
    changed = {mode: {"spy": 0, "spxw": 0, "matched": 0} for mode in MODES[1:]}
    lane_maps = {}
    for mode in MODES:
        lane = _unique_by_entry(evaluated[mode]["outcomes"], f"{mode} outcomes")
        for row in lane.values():
            _validate_fills(row, f"{mode} outcome {row['entry']}")
        lane_maps[mode] = lane
        if set(lane) != set(control):
            raise ValueError("lanes do not share every expected entry")
        for entry, row in lane.items():
            if mode != "close_reference":
                base_row = control[entry]
                changed[mode]["spy"] += row["spy_strike"] != base_row["spy_strike"]
                changed[mode]["spxw"] += row["spxw_strike"] != base_row["spxw_strike"]
                changed[mode]["matched"] += row["spy_contract"] == base_row["spy_contract"] and row["spxw_contract"] == base_row["spxw_contract"]
                for field in metric_fields:
                    lane_fill = next(x for x in row["fill_rows"] if x["fill"] == "full_cross")
                    control_fill = next(x for x in base_row["fill_rows"] if x["fill"] == "full_cross")
                    paired[mode][field].append(lane_fill[field] - control_fill[field])
    summaries = {}
    for mode in MODES:
        rows = evaluated[mode]["outcomes"]
        summaries[mode] = {"absolute": base.aggregate(rows, period), "changed_strikes_and_matches": changed.get(mode, {"spy": 0, "spxw": 0, "matched": expected_count})}
    paired_bootstrap = {}
    control_rows = lane_maps["close_reference"]
    week_by_entry = {}
    for entry, row in control_rows.items():
        expiry = base.iso_day(row["expiry"], "expiry")
        iso = expiry.isocalendar()
        week_by_entry[entry] = f"{iso.year}-W{iso.week:02d}"
    weeks = sorted(set(week_by_entry.values()))
    rng = random.Random(20261029)
    draws = [[rng.choice(weeks) for _ in weeks] for _ in range(10_000)]
    for mode, fields in paired.items():
        by_week = {week: [i for i, entry in enumerate(control_rows) if week_by_entry[entry] == week] for week in weeks}
        mode_boot = {}
        for field, values in fields.items():
            samples = []
            for sample in draws:
                indices = [i for week in sample for i in by_week[week]]
                samples.append(sum(values[i] for i in indices) / len(indices))
            samples.sort()
            mode_boot[field] = {"draws": 10_000, "seed": 20261029, "iso_week_clusters": len(weeks),
                                "low_95": base._q7(samples, .025), "high_95": base._q7(samples, .975),
                                "quantile_method": "linear_type_7", "descriptive_only": True}
        paired_bootstrap[mode] = mode_boot
    return {"paired_differences": {mode: {field: base._summary(values) for field, values in fields.items()} for mode, fields in paired.items()},
            "paired_full_cross_iso_week_cluster_bootstrap": paired_bootstrap,
            "bootstrap_shared_draws_across_metrics_and_lanes": True,
            "changed_strikes_and_matches": changed, "absolute_lane_metrics": summaries}


def verify_control_parity(evaluated: dict, selected_modes: dict, inputs: dict, period: str) -> dict:
    baseline_key = f"baseline_{period}/outcomes.json"
    selected_key = f"selection_{period}"
    baseline_outcomes = json.loads(inputs[baseline_key]["data"])
    baseline_selected = json.loads(inputs[selected_key]["data"])["selected_pairs"]
    current_rows = evaluated["close_reference"]["outcomes"]
    current_selected_rows = selected_modes["close_reference"]["pairs"]
    current = _unique_by_entry(current_rows, "current close outcomes")
    old = _unique_by_entry(baseline_outcomes, "baseline outcomes")
    old_selected = _unique_by_entry(baseline_selected, "baseline selections")
    selected_current = _unique_by_entry(current_selected_rows, "current selections")
    if set(current) != set(old) or set(current) != set(old_selected):
        raise ValueError("close_reference control does not match original expected entries")
    if set(selected_current) != set(old_selected):
        raise ValueError("close_reference selections do not match original expected entries")
    selection_comparisons = 0
    for entry, row in current.items():
        saved = old_selected[entry]
        selected = selected_current[entry]
        comparable_selected = {k: v for k, v in selected.items() if k not in {
            "selection_reference", "actual_entry_closes"}}
        selection_comparisons += _compare_exact_tree(saved, comparable_selected, 1e-8, f"selection[{entry}]")
        if abs(float(selected["actual_entry_closes"]["spy_close"]) - float(saved["spy_entry_close"])) > 1e-8:
            raise ValueError(f"close_reference actual SPY close differs from frozen selection for {entry}")
        if abs(float(selected["actual_entry_closes"]["official_spx_close"]) - float(saved["official_spx_entry_close"])) > 1e-8:
            raise ValueError(f"close_reference actual SPX close differs from frozen selection for {entry}")
        reference = selected["selection_reference"]
        if abs(float(reference["spy_price"]) - float(selected["actual_entry_closes"]["spy_close"])) > 1e-8:
            raise ValueError(f"close_reference SPY selection reference differs from actual close for {entry}")
        if abs(float(reference["spx_price"]) - float(selected["actual_entry_closes"]["official_spx_close"])) > 1e-8:
            raise ValueError(f"close_reference SPX selection reference differs from actual close for {entry}")
    for entry, row in current.items():
        _validate_fills(row, f"current outcome {entry}")
        _validate_fills(old[entry], f"baseline outcome {entry}")
        comparable_row = {k: v for k, v in row.items() if k not in {"selection_reference", "actual_entry_closes"}}
        selected_closes = selected_current[entry]["actual_entry_closes"]
        _compare_exact_tree(selected_closes, row["actual_entry_closes"], 1e-8, f"outcome_actual_closes[{entry}]")
        _compare_exact_tree(old[entry], comparable_row, 1e-8, f"outcome[{entry}]")
    baseline_summary = json.loads(inputs[f"baseline_{period}/summary.json"]["data"])
    current_summary = base.aggregate(list(current.values()), period)
    aggregate_checks = _compare_exact_tree(baseline_summary, current_summary, 1e-7, "summary")
    return {"status": "PASS", "entries": len(current), "selected_fields_compared": selection_comparisons,
            "outcome_fields_compared": "all recursively compared fields", "aggregate_numeric_fields_compared": aggregate_checks,
            "selection_snapshot_sha256": inputs[selected_key]["sha256"], "comparison_outcomes_sha256": inputs[baseline_key]["sha256"]}


def _unique_by_entry(rows: list[dict], label: str) -> dict:
    result = {}
    for row in rows:
        entry = row.get("entry")
        if not isinstance(entry, str) or entry in result:
            raise ValueError(f"{label} has a missing or duplicate entry")
        result[entry] = row
    return result


def _validate_fills(row: dict, label: str) -> None:
    fills = row.get("fill_rows")
    if not isinstance(fills, list):
        raise ValueError(f"{label} has no fill_rows list")
    names = [item.get("fill") for item in fills]
    if len(names) != 3 or len(set(names)) != 3 or set(names) != {"midpoint", "halfway", "full_cross"}:
        raise ValueError(f"{label} has missing, extra, or duplicate fill rows")
    controls = row.get("controls")
    expected_controls = {"reverse_full_cross_credit", "reverse_intrinsic_control_pnl", "reverse_closemark_control_pnl",
                         "reverse_spy_closemark_cash", "reverse_spxw_closemark_cash", "primary_assignment_threshold_applied",
                         "primary_threshold_residual_cash", "no_trade_zero_control_pnl", "reverse_physical_next_open_ledger"}
    if not isinstance(controls, dict) or set(controls) != expected_controls:
        raise ValueError(f"{label} has missing or extra reverse or zero controls")


def _compare_exact_tree(reference, actual, tolerance: float, path: str) -> int:
    if type(reference) is not type(actual) and not (isinstance(reference, (int, float)) and not isinstance(reference, bool)
                                                     and isinstance(actual, (int, float)) and not isinstance(actual, bool)):
        raise ValueError(f"parity type mismatch at {path}")
    checks = 0
    if isinstance(reference, dict):
        if set(reference) != set(actual):
            raise ValueError(f"parity fields differ at {path}: missing={sorted(set(reference)-set(actual))}, extra={sorted(set(actual)-set(reference))}")
        for key in reference:
            checks += _compare_exact_tree(reference[key], actual[key], tolerance, f"{path}.{key}")
    elif isinstance(reference, list):
        if len(reference) != len(actual):
            raise ValueError(f"parity list length differs at {path}")
        for i, (left, right) in enumerate(zip(reference, actual)):
            checks += _compare_exact_tree(left, right, tolerance, f"{path}[{i}]")
    elif isinstance(reference, bool):
        if reference is not actual:
            raise ValueError(f"parity value differs at {path}")
    elif isinstance(reference, (int, float)):
        if not math.isfinite(float(reference)) or not math.isfinite(float(actual)):
            raise ValueError(f"parity numeric value is nonfinite at {path}")
        if abs(float(reference) - float(actual)) > tolerance:
            raise ValueError(f"parity numeric value differs at {path}")
        checks += 1
    elif reference != actual:
        raise ValueError(f"parity value differs at {path}")
    return checks


def prepare(repo: Path, period: str, identity: dict, expected_modes: tuple[str, ...] = MODES) -> dict:
    if expected_modes != MODES:
        raise ValueError("all frozen modes must be selected together")
    proto, manifest_raw = PROTOCOL.read_bytes(), MANIFEST.read_bytes()
    if sha(proto) != PROTOCOL_SHA256 or sha(manifest_raw) != MANIFEST_SHA256:
        raise ValueError("timing protocol or comparison manifest hash changed")
    manifest = json.loads(manifest_raw)
    if manifest["status"] != "FROZEN_TIMING_SENSITIVITY_NOT_RUN":
        raise ValueError("timing comparison manifest is not frozen")
    baseline = {}
    for key, rec in manifest["comparison_files"].items():
        p = Path(rec["path"]); data = p.read_bytes()
        if len(data) != rec["bytes"] or sha(data) != rec["sha256"]:
            raise ValueError(f"baseline control changed: {key}")
        baseline[key] = {"path": str(p), "bytes": len(data), "sha256": sha(data), "data": data}
    snapshots = {}
    for period_key, rec in manifest["selection_snapshots"].items():
        p = Path(rec["path"]); data = p.read_bytes()
        if len(data) != rec["bytes"] or sha(data) != rec["sha256"]:
            raise ValueError(f"baseline selection snapshot changed: {period_key}")
        snapshots[f"selection_{period_key}"] = {"path": str(p), "bytes": len(data), "sha256": sha(data), "data": data}
    source_manifest = (repo / base.INPUT_MANIFEST).read_bytes()
    if sha(source_manifest) != base.INPUT_MANIFEST_SHA256:
        raise ValueError("original source manifest hash changed")
    source_obj = json.loads(source_manifest)
    frozen = base._frozen_files(repo, source_obj)
    sidecars = base._sidecars(repo, period, frozen)
    inputs = {"candidate_protocol": {"path": str(PROTOCOL), "bytes": len(proto), "sha256": sha(proto), "data": proto},
              "comparison_manifest": {"path": str(MANIFEST), "bytes": len(manifest_raw), "sha256": sha(manifest_raw), "data": manifest_raw},
              "original_manifest": {"path": str(repo / base.INPUT_MANIFEST), "bytes": len(source_manifest), "sha256": sha(source_manifest), "data": source_manifest},
              **{f"baseline_{k}": v for k, v in baseline.items()}, **snapshots, **frozen, **sidecars}
    original_manifest, _, original_inputs = base._runtime_inputs(repo, period)
    # Preserve the original study's frozen protocol and every input in the same
    # integrity snapshot as the new timing candidate documents.
    for role, record in original_inputs.items():
        inputs[f"original_{role}"] = record
    return {"manifest": original_manifest, "frozen": frozen, "inputs": inputs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source-audit", "run"))
    parser.add_argument("--period", choices=("primary_2024", "confirmation_2025"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--selection-out", type=Path)
    args = parser.parse_args(argv)
    repo = ROOT
    try:
        started = datetime.now(timezone.utc).isoformat()
        integrity_checkpoints = {}
        # Run identity is captured before any licensed raw source is opened.
        identity = capture_identity(repo) if args.mode == "run" else None
        prepared = prepare(repo, args.period, identity or {}, MODES)
        manifest, frozen, inputs = prepared["manifest"], prepared["frozen"], prepared["inputs"]
        if identity:
            integrity_checkpoints["after_input_capture_before_structural_audit"] = check_identity(repo, identity, inputs)
        audit = base._source_audit(args.period, {"_manifest": manifest}, frozen,
            base._sidecars(repo, args.period, frozen), defer_terminal_joins=args.mode == "run")
        if args.mode == "source-audit":
            # Structural audit parses terminal sources, but does not join selected
            # contracts to them or calculate payoff outcomes.
            raw_role = base.PERIOD_EXPORT[args.period][0]
            normalized = normalizer.normalize({"raw_export": frozen[raw_role],
                "source_metadata": base._sidecars(repo, args.period, frozen)["source_metadata"],
                "identity_metadata": base._sidecars(repo, args.period, frozen)["identity_metadata"]})
            prices, _ = base._read_prices(frozen["security-prices-20190801-20250829.csv"]["data"])
            sessions, official_spx = base._read_calendar(frozen["official_spx_calendar"]["data"])
            expected = base._validate_expected_pairs(manifest["periods"][args.period], sessions)
            dividends, _ = base._read_distributions(frozen["distributions-20190801-20250829.csv"]["data"])
            try:
                _reference_sets(prices, official_spx, sessions, expected)
                reference_audit = source_reference_coverage_audit(prices, official_spx, sessions, expected, dividends)
            except ValueError as exc:
                reference_audit = {"status": "SOURCE_REFERENCE_COVERAGE_BLOCKED", "reason": str(exc),
                                   "expected_count": len(expected), "mode_date_rows": [], "blockers": [str(exc)]}
            audit["timing_reference_coverage"] = reference_audit
            audit["returned_universe_candidate_audit"] = returned_universe_candidate_audit(normalized["normalized_rows"], expected)
            audit["historical_evaluation"] = "NOT RUN"
            top_status = ("BLOCKED_SOURCE" if audit["status"] != "SOURCE_AUDIT_ONLY" else
                          "BLOCKED_REFERENCE" if reference_audit["status"] != "SOURCE_REFERENCE_COVERAGE_PRESENT" else
                          "SOURCE_AUDIT_ONLY")
            audit["structural_source_audit_status"] = audit["status"]
            audit["status"] = top_status
            target = base._output_path(repo, args.out, "planning")
            base._atomic_json(target, {"status": top_status, "historical_evaluation": "NOT RUN",
                "period": args.period, "audit": audit, "normalized_quote_rows": len(normalized["normalized_rows"]),
                "protocol_sha256": PROTOCOL_SHA256, "comparison_manifest_sha256": MANIFEST_SHA256,
                "code_sha256": {path: sha((repo / path).read_bytes()) for path in CODE_PATHS},
                "git": base.git_info(repo),
                "inputs": base._records(inputs), "argv": [sys.argv[0], *(argv or sys.argv[1:])],
                "utc": started, "host": os.uname().nodename, "python": sys.version,
                "python_executable": sys.executable}, inputs)
            print(f"{top_status}: expected={audit['pair_denominator']['expected_count']} historical_evaluation=NOT RUN")
            return 0 if top_status == "SOURCE_AUDIT_ONLY" else 2
        if audit["status"] != "SOURCE_AUDIT_ONLY":
            blocked_audit = {**audit, "structural_source_audit_status": audit["status"], "status": "BLOCKED_SOURCE"}
            blocked = {"status": "BLOCKED_SOURCE", "historical_evaluation": "NOT RUN", "period": args.period,
                       "source_audit": blocked_audit, "blockers": audit.get("blockers", []),
                       "inputs": base._records(inputs)}
            plan_out = repo / "planning/optionmetrics-timing-20261029" / f"source-blocked-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            atomic_run_audit(plan_out, blocked, repo, identity, inputs)
            print("BLOCKED_SOURCE: historical_evaluation=NOT RUN")
            return 2
        raw_role = base.PERIOD_EXPORT[args.period][0]
        normalized = normalizer.normalize({"raw_export": frozen[raw_role], "source_metadata": base._sidecars(repo, args.period, frozen)["source_metadata"],
                                           "identity_metadata": base._sidecars(repo, args.period, frozen)["identity_metadata"]})
        prices, _ = base._read_prices(frozen["security-prices-20190801-20250829.csv"]["data"])
        sessions, official_spx = base._read_calendar(frozen["official_spx_calendar"]["data"])
        expected = base._validate_expected_pairs(manifest["periods"][args.period], sessions)
        dividends_for_reference, _ = base._read_distributions(frozen["distributions-20190801-20250829.csv"]["data"])
        try:
            _reference_sets(prices, official_spx, sessions, expected)
            reference_audit = source_reference_coverage_audit(prices, official_spx, sessions, expected, dividends_for_reference)
        except ValueError as exc:
            reference_audit = {"status": "SOURCE_REFERENCE_COVERAGE_BLOCKED", "reason": str(exc),
                               "expected_count": len(expected), "mode_date_rows": [], "blockers": [str(exc)]}
        if reference_audit["status"] != "SOURCE_REFERENCE_COVERAGE_PRESENT":
            audit_path = repo / "planning/optionmetrics-timing-20261029" / f"reference-source-blocked-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            atomic_run_audit(audit_path, {"status": "BLOCKED_REFERENCE", "historical_evaluation": "NOT RUN",
                "period": args.period, "reference_source_audit": reference_audit,
                "expected_count": len(expected), "inputs": base._records(inputs)}, repo, identity, inputs)
            print("BLOCKED_REFERENCE: historical_evaluation=NOT RUN")
            return 2
        try:
            selected = select_modes(normalized["normalized_rows"], expected, prices, official_spx, sessions,
                                    {k: v["sha256"] for k, v in frozen.items()})
        except ValueError as exc:
            audit_path = repo / "planning/optionmetrics-timing-20261029" / f"reference-blocked-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            atomic_run_audit(audit_path, {"status": "BLOCKED_REFERENCE", "historical_evaluation": "NOT RUN", "period": args.period,
                "expected_count": len(expected), "blocker": str(exc), "inputs": base._records(inputs)}, repo, identity, inputs)
            print("PREPARED_REFERENCE_BLOCKED: historical_evaluation=NOT RUN")
            return 2
        # Structural source parsing above does not join selected contracts or calculate P&L.
        # Freeze every mode before any selected-contract terminal join or payoff calculation.
        selection_out = args.selection_out or (repo / "planning/optionmetrics-timing-20261029" /
            f"selected-{args.period}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        target = base._output_path(repo, selection_out, "planning")
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if any(len(selected[m]["pairs"]) != len(expected) for m in MODES):
            atomic_run_audit(target, {"status": "BLOCKED_REFERENCE", "historical_evaluation": "NOT RUN", "period": args.period,
                "modes": selected, "expected_pairs": len(expected), "blockers": "one or more modes lack expected selections",
                "inputs": base._records(inputs)}, repo, identity, inputs)
            print("PREPARED_SELECTION_BLOCKED: historical_evaluation=NOT RUN")
            return 2
        frozen_doc = {"status": "SELECTED_NOT_EVALUATED", "historical_evaluation": "NOT RUN", "period": args.period,
                      "modes": selected, "inputs": base._records(inputs), "selection_utc": datetime.now(timezone.utc).isoformat(),
                      "argv": [sys.argv[0], *(argv or sys.argv[1:])],
                      "initial_run_identity": {"head": identity["head"], "clean": True,
                          "code": {k: {"path": v["path"], "loaded_path": v["loaded_path"], "sha256": v["sha256"], "bytes": v["bytes"]}
                                   for k, v in identity["code"].items()}}}
        selection_data = (json.dumps(frozen_doc, indent=2, sort_keys=True) + "\n").encode()
        def persist_selection():
            stage_path = target.with_name("." + target.name + ".tmp")
            if stage_path.exists():
                raise FileExistsError(stage_path)
            integrity_checkpoints["immediately_before_selection_publish"] = check_identity(repo, identity, inputs)
            try:
                stage_path.write_bytes(selection_data)
                integrity_checkpoints["selection_publish_checkpoint"] = check_identity(repo, identity, inputs)
                os.rename(stage_path, target)
            except Exception:
                stage_path.unlink(missing_ok=True)
                raise
            return (target, sha(selection_data))
        def load_terminal_sources():
            settlements_result, _ = base._read_pm_sources(frozen, args.period)
            distributions_result, _ = base._read_distributions(frozen["distributions-20190801-20250829.csv"]["data"])
            return settlements_result, distributions_result
        selection_ref, (settlements, dividends) = freeze_before_terminal_joins(
            selected, len(expected), persist_selection, load_terminal_sources)
        integrity_checkpoints["after_selection_before_terminal_join"] = check_identity(repo, identity, inputs, selection_ref)
        integrity_checkpoints["before_terminal_coverage_and_payoff_gate"] = check_identity(repo, identity, inputs, selection_ref)
        coverage_blockers = terminal_coverage_blockers(selected, expected, prices, official_spx, settlements, dividends, sessions)
        if coverage_blockers:
            audit_path = repo / "planning/optionmetrics-timing-20261029" / f"coverage-blocked-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            atomic_run_audit(audit_path, {"status": "BLOCKED_REFERENCE", "historical_evaluation": "NOT RUN", "period": args.period,
                "coverage_blockers": coverage_blockers, "expected_count": len(expected), "selection_snapshot": str(target)},
                repo, identity, inputs, selection_ref)
            print("PREPARED_COVERAGE_BLOCKED: historical_evaluation=NOT RUN")
            return 2
        integrity_checkpoints["immediately_before_payoff_calculation"] = check_identity(repo, identity, inputs, selection_ref)
        evaluated = evaluate_modes(selected, expected, prices, official_spx, settlements, dividends, sessions)
        if any(len(evaluated[m]["outcomes"]) != len(expected) or not all(x["complete"] for x in evaluated[m]["coverage"]) for m in MODES):
            audit_path = repo / "planning/optionmetrics-timing-20261029" / f"coverage-blocked-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            atomic_run_audit(audit_path, {"status": "BLOCKED_REFERENCE", "historical_evaluation": "NOT RUN", "coverage": {m: evaluated[m]["coverage"] for m in MODES},
                "selection_snapshot": str(target)}, repo, identity, inputs, selection_ref)
            print("PREPARED_COVERAGE_BLOCKED: historical_evaluation=NOT RUN")
            return 2
        parity = verify_control_parity(evaluated, selected, inputs, args.period)
        comparison = compare_modes(evaluated, len(expected), args.period)
        integrity_checkpoints["before_bundle_staging"] = check_identity(repo, identity, inputs, selection_ref)
        output = base._output_path(repo, args.out, "runs")
        if output.exists():
            raise FileExistsError(output)
        status = "EXPLORATORY_TIMING_SENSITIVITY_EVALUATED"
        stale_refs = reference_staleness_audit(selected, dividends)
        artifacts = {
            "outcomes.json": {"status": status, "lanes": {mode: evaluated[mode]["outcomes"] for mode in MODES}},
            "comparison.json": {"status": status, "control_parity": parity, "comparison": comparison},
            "coverage.json": {"status": status, "lanes": {mode: evaluated[mode]["coverage"] for mode in MODES},
                              "reference_carry_staleness": stale_refs},
            "source-audit.json": {"status": "SOURCE_AUDIT_ONLY", "historical_evaluation": "NOT RUN",
                                  "structural_source_audit": audit, "returned_universe_candidate_audit": returned_universe_candidate_audit(normalized["normalized_rows"], expected),
                                  "reference_carry_staleness": stale_refs}}
        selection_bytes = target.read_bytes()
        if sha(selection_bytes) != selection_ref[1]:
            raise ValueError("BLOCKED: selection changed during bundle staging")
        completed = datetime.now(timezone.utc).isoformat()
        input_inventory = base._records(inputs)
        timing_source_hashes = {role: record["sha256"] for role, record in input_inventory.items()
                                if not role.startswith(("baseline_", "selection_", "original_")) and
                                role not in {"candidate_protocol", "comparison_manifest", "original_manifest"}}
        run_manifest = {"status": status, "historical_evaluation": "RAN", "period": args.period,
            "expected_pairs": len(expected), "started_utc": started, "ended_utc": completed,
            "argv": [sys.argv[0], *(argv or sys.argv[1:])], "cwd": str(Path.cwd()), "host": os.uname().nodename,
            "python": sys.version, "python_executable": sys.executable, "pythonpath": os.environ.get("PYTHONPATH"),
            "initial_git": {"sha": identity["head"], "clean": True},
            "code_identities": {k: {"expected_path": v["path"], "loaded_path": v["loaded_path"],
                "bytes": v["bytes"], "sha256": v["sha256"]} for k, v in identity["code"].items()},
            "candidate_protocol": {"path": str(PROTOCOL), "sha256": PROTOCOL_SHA256},
            "original_protocol": {"path": str(repo / base.PROTOCOL), "sha256": inputs["original_protocol"]["sha256"],
                "bytes": inputs["original_protocol"]["bytes"]},
            "input_manifest_sha256": inputs["original_input_manifest"]["sha256"],
            "comparison_manifest_sha256": MANIFEST_SHA256, "source_hashes": timing_source_hashes,
            "control_hashes": {role: rec["sha256"] for role, rec in input_inventory.items() if role.startswith("baseline_") or role.startswith("selection_")},
            "inputs_before": input_inventory, "inputs_after": base._records(inputs),
            "integrity_before": integrity_checkpoints["after_input_capture_before_structural_audit"],
            "integrity_checkpoints": integrity_checkpoints,
            "selection_snapshot": {"path": str(target), "sha256": selection_ref[1], "bytes": len(selection_bytes)},
            "control_parity": parity,
            "model_endpoint": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
            "model_identity": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
            "limitations": audit.get("limitations", []) + ["Earlier references do not remove 15:59 quote-conditioned eligibility.",
                "The source universe is the returned export only. Opens are not publication-time verified or synchronized."]}
        publication = atomic_publish_run_bundle(output, artifacts, run_manifest, repo, identity, inputs, selection_ref)
        receipt = {"status": status, "output": str(output), "manifest_sha256": publication["manifest_sha256"],
                   "artifact_sha256": publication["output_sha256"],
                   "cli_receipt_sha256": publication["cli_receipt_sha256"]}
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except FileExistsError as exc:
        print(f"output already exists: {exc}", file=sys.stderr); return 4
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
