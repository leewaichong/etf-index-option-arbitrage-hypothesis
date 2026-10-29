from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import pytest

from spyspx.expiry_payoff_source import SCHEMA


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/expiry_payoff.py"


def source_row(root, day, expiry, strike, close, bid="2", ask="3"):
    row = {name: "" for name in SCHEMA}
    osi_strike = int(round(strike * 1000))
    row.update({
        "contract": f"{root}{expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{osi_strike:08d}",
        "underlying": root,
        "expiration": expiry,
        "type": "call",
        "strike": str(strike),
        "style": "A" if root == "SPY" else "E",
        "quote_date": day,
        "bid": bid,
        "ask": ask,
        "underlying_close": str(close),
        "settlement_time": "PM",
    })
    return row


def write_zip(path: Path, *, terminal=True):
    entry_day, expiry = "2022-09-15", "2022-09-16"
    rows = [
        source_row("SPY", entry_day, expiry, 400, 400, "2", "3"),
        source_row("SPXW", entry_day, expiry, 3980, 3980, "20", "21"),
    ]
    if terminal:
        rows.extend([
            source_row("SPY", expiry, expiry, 400, 401),
            source_row("SPXW", expiry, expiry, 3980, 3990),
        ])
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        days = {entry_day: rows[:2], expiry: rows[2:]}
        for day, day_rows in days.items():
            if not day_rows:
                continue
            member = f"day_by_date/{day}_options.csv"
            with archive.open(member, "w") as raw:
                import io
                stream = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                writer = csv.DictWriter(stream, fieldnames=SCHEMA)
                writer.writeheader()
                writer.writerows(day_rows)
                stream.flush()


def invoke(mode, archive, project, cwd, protocol=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    command = [sys.executable, str(CLI), mode, str(archive)]
    if protocol is not None:
        command.extend(["--protocol", str(protocol)])
    command.extend(["--project-root", str(project)])
    return subprocess.run(
        command,
        cwd=cwd, env=env, capture_output=True, text=True, check=False,
    )


def output_dir(stdout):
    return Path(json.loads(stdout)["output"])


def test_cli_synthetic_audit_and_run_write_aggregates_and_repro_manifest(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".gitignore").write_text("runs/\n")
    protocol = tmp_path / "synthetic-protocol.md"
    protocol.write_text("Synthetic frozen protocol for CLI integration coverage.\n")
    archive = tmp_path / "synthetic.zip"
    write_zip(archive)

    audit = invoke("source-audit", archive, project, tmp_path, protocol)
    assert audit.returncode == 0, audit.stderr
    audit_dir = output_dir(audit.stdout)
    assert json.loads((audit_dir / "source_audit.json").read_text())["status"] == "source_audit_only"
    assert not (audit_dir / "aggregates.json").exists()

    run = invoke("run", archive, project, tmp_path, protocol)
    assert run.returncode == 0, run.stderr
    run_dir = output_dir(run.stdout)
    aggregates = json.loads((run_dir / "aggregates.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert aggregates["retained_pairs"] == 1
    assert aggregates["no_trade_control_usd"] == 0
    assert aggregates["exact_settlement_status"] == "NOT RUN"
    cohort = aggregates["cohort_table"][0]
    assert cohort["mean_strike_cash_mismatch_usd"] == 2000
    assert cohort["mean_absolute_strike_cash_mismatch_usd"] == 2000
    assert cohort["mean_entry_underlying_exposure_mismatch_usd"] == -2000
    assert cohort["mean_absolute_entry_underlying_exposure_mismatch_usd"] == 2000
    assert manifest["integrity_status"] == "UNCHANGED"
    assert manifest["exact_settlement_status"] == "NOT RUN"
    assert manifest["command"]["cwd"] == str(tmp_path)
    assert manifest["command"]["executable"] == sys.executable
    assert manifest["command"]["pythonpath"] == str(ROOT / "src")
    assert manifest["baseline_before_outcomes"]["git_sha"]
    assert manifest["baseline_before_outcomes"]["workspace_state"] in {"clean", "dirty"}
    assert set(manifest["baseline_before_outcomes"]["code_file_sha256"]) == {
        "scripts/expiry_payoff.py", "src/spyspx/expiry_payoff.py", "src/spyspx/expiry_payoff_source.py",
        "tests/test_expiry_payoff.py", "tests/test_expiry_payoff_cli.py"
    }
    assert manifest["baseline_before_outcomes"]["input"]["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert "model endpoint not applicable" in manifest["runtime"]
    expected_protocol = {"path": str(protocol.resolve()), "sha256": hashlib.sha256(protocol.read_bytes()).hexdigest()}
    assert manifest["baseline_before_outcomes"]["protocol"] == expected_protocol
    assert manifest["protocol"] == expected_protocol
    for relpath, digest in manifest["baseline_before_outcomes"]["code_file_sha256"].items():
        assert hashlib.sha256((ROOT / relpath).read_bytes()).hexdigest() == digest
    serialized = json.dumps(aggregates)
    for forbidden in ("SPY220916C00400000", "SPXW220916C03980000", '"contract"', '"bid"', '"ask"', '"spy_strike"', '"spxw_strike"', '"entry_date"'):
        assert forbidden not in serialized


def test_cli_no_usable_data_returns_nonzero_with_status_and_manifest(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".gitignore").write_text("runs/\n")
    protocol = tmp_path / "synthetic-protocol.md"
    protocol.write_text("Synthetic protocol for the no-data case.\n")
    archive = tmp_path / "missing-terminal.zip"
    write_zip(archive, terminal=False)
    run = invoke("run", archive, project, tmp_path, protocol)
    assert run.returncode != 0
    run_dir = output_dir(run.stdout)
    aggregates = json.loads((run_dir / "aggregates.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert aggregates["status"] == "NO_USABLE_DATA"
    assert aggregates["exact_settlement_status"] == "NOT RUN"
    assert aggregates["no_trade_control_usd"] == 0
    assert aggregates["cohort_table"] == []
    assert manifest["integrity_status"] == "UNCHANGED"
    assert manifest["baseline_before_outcomes"]["input"]["sha256"]
    assert "run_complete" not in json.dumps(aggregates)


@pytest.mark.parametrize("mutation_target", ["input", "protocol"])
def test_cli_fails_closed_if_input_or_protocol_changes_during_processing(tmp_path, monkeypatch, mutation_target):
    spec = importlib.util.spec_from_file_location("expiry_payoff_cli_under_test", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".gitignore").write_text("runs/\n")
    protocol = tmp_path / "synthetic-protocol.md"
    protocol.write_text("Synthetic protocol for mutation detection.\n")
    archive = tmp_path / "mutable.zip"
    write_zip(archive)
    original_read = module.read_zip

    def read_then_mutate(path):
        result = original_read(path)
        target = path if mutation_target == "input" else protocol
        target.write_bytes(target.read_bytes() + b"changed")
        return result

    monkeypatch.setattr(module, "read_zip", read_then_mutate)
    monkeypatch.setattr(sys, "argv", [str(CLI), "run", str(archive), "--protocol", str(protocol), "--project-root", str(project)])
    monkeypatch.chdir(tmp_path)
    assert module.main() == 2
    run_dirs = list((project / "runs/expiry_payoff").iterdir())
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text())
    assert manifest["integrity_status"] == "CHANGED_DURING_PROCESSING"
    assert not (run_dirs[0] / "aggregates.json").exists()


@pytest.mark.parametrize("mode", ["source-audit", "run"])
@pytest.mark.parametrize("protocol_kind", ["missing_argument", "nonexistent_file"])
def test_cli_requires_readable_protocol_before_creating_output(tmp_path, mode, protocol_kind):
    project = tmp_path / "project"
    project.mkdir()
    archive = tmp_path / "synthetic.zip"
    write_zip(archive)
    protocol = None if protocol_kind == "missing_argument" else tmp_path / "absent-protocol.md"
    result = invoke(mode, archive, project, tmp_path, protocol)
    assert result.returncode != 0
    assert "--protocol" in result.stderr
    assert not (project / "runs").exists()
