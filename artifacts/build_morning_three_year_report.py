#!/usr/bin/env python3
"""Render a validated three-year morning-hedge comparison as Markdown and A4 PDF."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

INK, VIOLET, MUTED, RULE = (colors.HexColor(c) for c in ("#292630", "#5D4284", "#696572", "#D9D5DE"))
COSTS = ("option_fees", "stock_fees", "residual_short_borrow", "premium_debit_funding", "hedge_funding", "stock_slippage")
COHORTS = ("full_2023", "full_2024", "jan_aug_2025", "jan_aug_2023", "jan_aug_2024")
SOURCE_ROLES = {"ledger_2023","summary_2023","evaluator_manifest_2023","execution_2023","validated_rows_2023","attribution_manifest_2023","validation_2023","case_ledgers_2024_2025","summaries_2024_2025","uncertainty_2024_2025","evaluator_manifest_2024_2025","execution_2024_2025"}
FRAME_WIDTH_MM = 176


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def finite(x, where):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f"{where} must be finite")


def validate_aggregate(d):
    if not isinstance(d,dict) or d.get("schema_version")!=1 or d.get("status")!="SUMMARIZED_NOT_VALIDATED" or d.get("synthetic_fixture") is not False:
        raise ValueError("real report requires a fresh summarized aggregate")
    if set(d.get("cohorts",{}))!=set(COHORTS):raise ValueError("five frozen cohorts required")
    for name,r in d["cohorts"].items():
        if type(r.get("n")) is not int or r["n"]<=0:raise ValueError(f"{name} count invalid")
        for key in ("mean","median","q0_control_mean","total","positive_fraction","gross_total","cost_total","overnight_total","dividend_total","option_baseline_total","retained_costs_net_minus_overnight"):
            finite(r.get(key),f"{name}.{key}")
        if set(r.get("cost_totals",{}))!=set(COSTS):raise ValueError(f"{name} cost rows incomplete")
        for key in COSTS:finite(r["cost_totals"][key],f"{name}.{key}")
    for year in ("2023","2024","2025"):
        months=d.get("monthly",{}).get(year)
        if not isinstance(months,dict) or len(months)!=12:raise ValueError(f"{year} monthly summaries incomplete")
        for label,r in months.items():
            if type(r.get("n")) is not int or r["n"]<0:raise ValueError(f"{label} monthly count invalid")
            if r["n"]==0 and r.get("mean") is not None:raise ValueError(f"{label} empty mean must be absent")
            if r["n"] and not math.isfinite(float(r.get("mean"))):raise ValueError(f"{label} monthly mean invalid")
    for name in COHORTS:
        if set(d.get("tail_removals",{}).get(name,{}))!={"1","5","10"}:raise ValueError(f"{name} tail table incomplete")
    if set(d.get("confidence_intervals",{}))!={"2023","2024","2025"}:raise ValueError("source-cohort intervals for all years required")
    ci_counts={"2023":196,"2024":195,"2025":127}
    for year,items in d["confidence_intervals"].items():
        if set(items)!={"absolute","paired_vs_q0"}:raise ValueError(f"{year} intervals incomplete")
        for label,row in items.items():
            if type(row.get("n")) is not int or row["n"]!=ci_counts[year]:raise ValueError(f"{year}/{label} interval cohort count invalid")
            for k in ("mean","low_95","high_95"):finite(row.get(k),f"{year}/{label}/{k}")
            if row["low_95"]>row["high_95"]:raise ValueError("confidence interval bounds reversed")
    for year in ("2024","2025"):
        cases=d.get("sensitivity",{}).get(year)
        if not isinstance(cases,list) or len(cases)!=36:raise ValueError(f"{year}: all 36 sensitivity cases required")
        keys=set()
        for row in cases:
            key=(row.get("fill"),row.get("cost_mode"),row.get("slippage_bp"),row.get("funding"))
            if key in keys:raise ValueError(f"{year} duplicate sensitivity case")
            keys.add(key);finite(row.get("mean"),"sensitivity mean")
            if type(row.get("n")) is not int or not isinstance(row.get("cost_means"),dict):raise ValueError("sensitivity row invalid")
            for c in COSTS:finite(row["cost_means"].get(c),f"sensitivity/{c}")
            if row["n"]!={"2024":195,"2025":127}[year]:raise ValueError(f"{year} sensitivity cohort count invalid")
            if any(row["cost_means"][c]<0 for c in COSTS):raise ValueError("sensitivity costs must be nonnegative")
        expected={(fill,cost,bps,fund) for fill in ("midpoint","halfway","full_cross") for cost in ("base","stress") for bps in (0,1,5) for fund in ("gross_prefunding","assignment_cash_net")}
        if keys!=expected:raise ValueError(f"{year} sensitivity matrix incomplete")
    src=d.get("source_hashes")
    if not isinstance(src,dict) or set(src)!=SOURCE_ROLES:raise ValueError("source hashes missing required frozen source bindings")
    for label,digest in src.items():
        if not re.fullmatch(r"[0-9a-f]{64}",digest):raise ValueError(f"invalid source hash {label}")
    run=d.get("run")
    if not isinstance(run,dict) or run.get("git_clean") is not True or not isinstance(run.get("command"),list) or not run["command"]:
        raise ValueError("clean source identity and executed command required")
    if not re.fullmatch(r"[0-9a-f]{40}",str(run.get("git_sha",""))) or not re.fullmatch(r"[0-9a-f]{64}",str(run.get("loaded_code_sha256",""))):
        raise ValueError("comparison builder hashes invalid")
    if d.get("source_evaluator_git_shas")!={"2023":"64e72887b782fdf838257a09877ffb817dfbfbdf","2024_2025":"44ed294deddb85df594ad1e1c8a5a91bb22d08d7"}:
        raise ValueError("source evaluator Git SHAs missing or unexpected")
    for key in ("manifest_sha256","protocol_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}",str(run.get(key,""))):raise ValueError(f"run.{key} invalid")


def validate_receipts(d, aggregate_hash, run_receipt, run_receipt_hash, validation, findings, validation_hash, findings_hash):
    if file_sha(aggregate_hash[0])!=aggregate_hash[1]:raise ValueError("aggregate changed or hash mismatch")
    if file_sha(run_receipt_hash[0])!=run_receipt_hash[1] or file_sha(validation_hash[0])!=validation_hash[1] or file_sha(findings_hash[0])!=findings_hash[1]:raise ValueError("run receipt, validation or findings hash mismatch")
    run=d.get("run",{})
    if run_receipt.get("status")!="SUMMARIZED_NOT_VALIDATED" or run_receipt.get("aggregate_sha256")!=aggregate_hash[1]:raise ValueError("comparison run receipt does not bind this aggregate")
    if run_receipt.get("source_hashes")!=d.get("source_hashes") or run_receipt.get("git_sha")!=run.get("git_sha") or run_receipt.get("loaded_code_sha256")!=run.get("loaded_code_sha256"):raise ValueError("comparison run receipt source identity mismatch")
    if run_receipt.get("returncode")!=0 or run_receipt.get("git_clean") is not True or not run_receipt.get("command") or not run_receipt.get("started_utc") or not run_receipt.get("ended_utc") or not isinstance(run_receipt.get("environment"),dict):raise ValueError("comparison run receipt is incomplete")
    if validation.get("status")!="PASS" or validation.get("aggregate_sha256")!=aggregate_hash[1]:raise ValueError("independent PASS receipt does not bind this aggregate")
    checker=validation.get("checker")
    if not isinstance(checker,dict) or not checker.get("identity") or not re.fullmatch(r"[0-9a-f]{64}",str(checker.get("sha256",""))):raise ValueError("checker identity and hash required")
    if validation.get("source_git_sha")!=run.get("git_sha") or validation.get("loaded_code_sha256")!=run.get("loaded_code_sha256"):raise ValueError("validation source identity mismatch")
    if validation.get("run_receipt_sha256")!=run_receipt_hash[1]:raise ValueError("independent validation does not bind the comparison run receipt")
    if type(validation.get("checks")) is not int or validation["checks"]<1 or type(validation.get("mismatches")) is not int or validation.get("mismatches")!=0:raise ValueError("validation checks or mismatches invalid")
    if not validation.get("command") or not validation.get("started_utc") or not validation.get("ended_utc"):raise ValueError("validation execution details required")
    if findings.get("status")!="LEAD_APPROVED" or not findings.get("verdict") or not isinstance(findings.get("findings"),list) or not findings["findings"]:raise ValueError("lead-approved verdict and findings required")
    if validation.get("findings_sha256")!=findings_hash[1]:raise ValueError("validation receipt does not bind approved findings")
    for text in [findings["verdict"],*findings["findings"]]:
        if not isinstance(text,str) or not text.strip() or re.search(r"(?:/Users/|/private/|/tmp/)|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[\"“”]",text):raise ValueError("approved findings contain private data, a direct quote, or are empty")


def money(v):return f"-${-v:,.2f}" if v < 0 else f"${v:,.2f}"
def pct(v):return "n/a" if v is None else f"{100*v:.1f}%"
def mean(v):return "n/a" if v is None else money(v)
def ci(x):return f"{money(x['mean'])} [{money(x['low_95'])}, {money(x['high_95'])}], n={x['n']}"
def label(s):return s.replace("_"," ").replace("jan aug","Jan-Aug").replace("full ","Full ").title()
def ci_label(year):return {"2023":"2023 full year","2024":"2024 full year","2025":"2025 Jan-Aug"}[year]


def markdown(d, findings, validation):
    out=["# SPY/SPX morning hedge: three-year comparison","", "## Executive summary", "",f"**{findings['verdict']}**", ""]
    out += [f"- {x}" for x in findings["findings"]]
    out += ["", "## Cohort results", "", "Focal case: full-cross fills, base costs, gross prefunding, 1 bp stock slippage. The original formal primary arm was fixed-500; this morning arm was secondary.", "",
            "| Cohort | n | Mean USD/expiry | Median USD/expiry | Total USD | Positive | Gross total USD | Costs total USD | Overnight total USD | Dividends total USD |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in COHORTS:
        r=d["cohorts"][name];out.append(f"| {label(name)} | {r['n']} | {money(r['mean'])} | {money(r['median'])} | {money(r['total'])} | {pct(r['positive_fraction'])} | {money(r['gross_total'])} | {money(r['cost_total'])} | {money(r['overnight_total'])} | {money(r['dividend_total'])} |")
    out += ["", "## Components and states", "", "| Cohort | Option baseline total | q0 control mean | Overnight total | Dividends total | q=0 | q=1,000 | Assigned | Residual long / short / zero | Net P&L minus overnight contribution, retaining modeled costs (total USD) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n in COHORTS:
        r=d["cohorts"][n];out.append(f"| {label(n)} | {money(r['option_baseline_total'])} | {money(r['q0_control_mean'])} | {money(r['overnight_total'])} | {money(r['dividend_total'])} | {r['q_counts']['0']} | {r['q_counts']['1000']} | {r['assignment_counts']['true']} | {r['residual_counts']['long']} / {r['residual_counts']['short']} / {r['residual_counts']['zero']} | {money(r['retained_costs_net_minus_overnight'])} |")
    out += ["", "*Component columns are cohort totals in USD; q0 control is a per-expiry mean. The net-minus-overnight value is a total-dollar diagnostic, not a tradable return.*", "", "Six modeled costs (total USD by cohort):", "", "| Cohort | Option fees | Stock fees | Borrow | Premium funding | Hedge funding | Slippage |", "|---|---:|---:|---:|---:|---:|---:|"]
    for n in COHORTS:
        c=d['cohorts'][n]['cost_totals'];out.append("| "+label(n)+" | "+" | ".join(money(c[k]) for k in COSTS)+" |")
    out += ["", "## Source-cohort uncertainty and tail checks", "", "Source-provided 95% type-7 intervals are shown for 2023 full year, 2024 full year, and 2025 Jan-Aug. These are previously inspected historical samples, not holdouts or predictive validation. The filtered Jan-Aug 2023 and Jan-Aug 2024 cohorts have no computed intervals. No new or common-window intervals were computed.", "", "| Source cohort | Hedge mean, absolute 95% CI | Paired vs q0 mean, 95% CI |", "|---|---:|---:|"]
    for y in ("2023","2024","2025"):
        c=d['confidence_intervals'][y];out.append(f"| {ci_label(y)} | {ci(c['absolute'])} | {ci(c['paired_vs_q0'])} |")
    out += ["", "Tail-removal means are USD per package after removing the largest or smallest k net outcomes. n after 10 is the count left after removing 10 outcomes. This is a post-hoc sensitivity check, not a trading filter.", "", "| Cohort | Remove top 1 mean | Remove top 5 mean | Remove top 10 mean | Remove bottom 1 mean | Remove bottom 5 mean | Remove bottom 10 mean | n after 10 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for n in COHORTS:
        t=d['tail_removals'][n];out.append(f"| {label(n)} | "+" | ".join(money(t[str(k)]['top_removed_mean']) for k in (1,5,10))+" | "+" | ".join(money(t[str(k)]['bottom_removed_mean']) for k in (1,5,10))+f" | {t['10']['n_remaining']} |")
    out += ["", "## Monthly net results", "", "| Month | 2023 n / mean | 2024 n / mean | 2025 n / mean |", "|---|---:|---:|---:|"]
    for m in range(1,13):
        vals=[]
        for y in ("2023","2024","2025"):
            r=d['monthly'][y][f"{y}-{m:02d}"];vals.append(f"{r['n']} / {mean(r['mean'])}")
        out.append(f"| {m:02d} | "+" | ".join(vals)+" |")
    out += ["", "## Cost sensitivity", "", "36 source cases per year. Means are net dollars per expiry.", "", "| Year | Fill | Costs | Slippage | Funding | n | Mean |", "|---|---|---|---:|---|---:|---:|"]
    for y in ("2024","2025"):
        for r in d['sensitivity'][y]:out.append(f"| {y} | {r['fill']} | {r['cost_mode']} | {r['slippage_bp']} bp | {r['funding']} | {r['n']} | {money(r['mean'])} |")
    out += ["", "## Method and provenance", "", "Expiry morning SPY open selects quantity using the frozen selected strike + $0.01 rule, with 1e-10 tolerance. The modeled stock purchase occurs at expiry close; the residual closes at the next session open. Options use one-calendar-day DTE from entry close to expiry close. The stock holding can span weekends. The option structure is 10 short SPY options and one long SPXW option, multiplier 100.", "", "The original fixed-500 arm was the formal primary arm; this morning arm was secondary. These are previously inspected historical samples, not holdouts or predictive validation. The 2024 cohort covers expiries 2024-01-03 through 2024-12-31, with the final next-session cover open on 2025-01-02. The 2023 15:59 quote clock is unverified; it is verified for 2024 and 2025. Later closing references carry execution limits. Results use daily theoretical fills and do not establish operational edge. No common-window CIs or between-year p-values were computed.", "", f"Comparison builder Git SHA: `{d['run']['git_sha']}`. Comparison builder file SHA-256: `{d['run']['loaded_code_sha256']}`. Source evaluator Git SHAs: 2023 `{d['source_evaluator_git_shas']['2023']}`, 2024/2025 `{d['source_evaluator_git_shas']['2024_2025']}`.", f"Aggregate SHA-256: `{validation['aggregate_sha256']}`. Comparison run receipt SHA-256: `{validation['run_receipt_sha256']}`. Validation receipt SHA-256: `{validation['receipt_sha256']}`. Independent checker SHA-256: `{validation['checker']['sha256']}`.", f"Input manifest SHA-256: `{d['run']['manifest_sha256']}`. Protocol SHA-256: `{d['run']['protocol_sha256']}`.", "", "Source hashes:"]
    for key,value in sorted(d['source_hashes'].items()):out.append(f"- `{key}`: `{value}`")
    return "\n".join(out)+"\n"


def register_fonts():
    f=Path("/System/Library/Fonts/Avenir Next.ttc")
    if f.exists():
        pdfmetrics.registerFont(TTFont("Avenir",str(f),subfontIndex=7));pdfmetrics.registerFont(TTFont("Avenir-Demi",str(f),subfontIndex=2));return "Avenir","Avenir-Demi"
    return "Helvetica","Helvetica-Bold"


def render_pdf(d, findings, validation, output):
    bodyfont,boldfont=register_fonts();sheet=getSampleStyleSheet()
    body=ParagraphStyle("body",parent=sheet["BodyText"],fontName=bodyfont,fontSize=8.5,leading=11,textColor=INK,spaceAfter=4)
    title=ParagraphStyle("title",parent=body,fontName=boldfont,fontSize=20,leading=23,spaceAfter=3)
    head=ParagraphStyle("head",parent=body,fontName=boldfont,fontSize=12,leading=14,textColor=VIOLET,spaceBefore=3,spaceAfter=5,keepWithNext=True)
    small=ParagraphStyle("small",parent=body,fontSize=7.5,leading=9)
    cell=ParagraphStyle("cell",parent=small,fontSize=8.3,leading=10)
    cellhead=ParagraphStyle("cellhead",parent=cell,fontName=boldfont,textColor=VIOLET)
    doc=BaseDocTemplate(str(output),pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=15*mm,bottomMargin=15*mm)
    frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="body",leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    def chrome(c,docr):
        c.saveState();c.setStrokeColor(RULE);c.setLineWidth(.45);c.line(17*mm,11*mm,193*mm,11*mm);c.setFillColor(MUTED);c.setFont(bodyfont,7.5);c.drawString(17*mm,7*mm,"SPY / SPX morning hedge · "+("SYNTHETIC LAYOUT CHECK" if d.get("synthetic_fixture") else "validated comparison"));c.drawRightString(193*mm,7*mm,str(docr.page));c.restoreState()
    doc.addPageTemplates(PageTemplate(id="report",frames=frame,onPage=chrome))
    P=lambda x,style=body:Paragraph(escape(str(x)),style)
    def table(rows,widths,fontsize=8.3):
        if sum(widths)>FRAME_WIDTH_MM:raise ValueError(f"table width {sum(widths)} mm exceeds A4 frame")
        t=Table([[P(x,cellhead if i==0 else cell) if not isinstance(x,Paragraph) else x for x in row] for i,row in enumerate(rows)],colWidths=[w*mm for w in widths],repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,0),.8,VIOLET),("LINEBELOW",(0,1),(-1,-1),.3,RULE),("FONTNAME",(0,0),(-1,-1),bodyfont),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,1),(-1,-1),"RIGHT"),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]));return t
    story=[P("SPY / SPX morning hedge",title),P("Three-year comparison · evidence through August 2025",small),Spacer(1,4*mm),P("Executive summary",head),P(findings['verdict'])]
    for f in findings['findings']:story.append(P("• "+f))
    story += [P("Cohort results",head),P("Focal case: full-cross fills, base costs, gross prefunding, 1 bp stock slippage. The original formal primary arm was fixed-500; this morning arm was secondary." ,small)]
    rows=[["Cohort","n","Mean","Median","Total","Positive","Costs","Overnight"]]
    for n in COHORTS:
        r=d['cohorts'][n];rows.append([label(n),str(r['n']),money(r['mean']),money(r['median']),money(r['total']),pct(r['positive_fraction']),money(r['cost_total']),money(r['overnight_total'])])
    # 31+10+23+23+23+19+27+20 = 176 mm, within 176 mm A4 frame.
    story += [table(rows,[31,10,23,23,23,19,27,20]),Spacer(1,3*mm),P("Mean, median, and total in the table have distinct units: mean and median are USD per expiry; total and component figures are cohort USD totals. The Markdown companion gives all six costs and the diagnostic Net minus overnight, which retains modeled costs and is a total USD value, not a tradable return.",small),PageBreak(),P("Components, states and tails",head)]
    rows=[["Cohort","Option base","q0 mean","Dividends","q0 / q1000","Assigned","Residual L/S/0"]]
    for n in COHORTS:
        r=d['cohorts'][n];rows.append([label(n),money(r['option_baseline_total']),money(r['q0_control_mean']),money(r['dividend_total']),f"{r['q_counts']['0']} / {r['q_counts']['1000']}",str(r['assignment_counts']['true']),f"{r['residual_counts']['long']} / {r['residual_counts']['short']} / {r['residual_counts']['zero']}"])
    story += [table(rows,[30,25,22,21,24,20,34]),Spacer(1,4*mm),P("Top and bottom tail removals",head)]
    rows=[["Cohort","Top 1","Top 5","Top 10","Bottom 1","Bottom 5","Bottom 10","n left"]]
    for n in COHORTS:
        t=d['tail_removals'][n];rows.append([label(n),*[money(t[str(k)]['top_removed_mean']) for k in (1,5,10)],*[money(t[str(k)]['bottom_removed_mean']) for k in (1,5,10)],str(t['10']['n_remaining'])])
    story += [table(rows,[34,22,22,22,22,22,22,10]),Spacer(1,2*mm),P("Tail means are USD per package after removing the largest or smallest k net outcomes. n left is the count after removing 10. This post-hoc sensitivity check is not a trading filter.",small),Spacer(1,3*mm),P("Monthly net results",head)]
    rows=[["Month","2023 n / mean","2024 n / mean","2025 n / mean"]]
    for m in range(1,13):
        vals=[]
        for y in ("2023","2024","2025"):
            r=d['monthly'][y][f"{y}-{m:02d}"];vals.append(f"{r['n']} / {mean(r['mean'])}")
        rows.append([f"{m:02d}",*vals])
    story += [table(rows,[25,50,50,50]),PageBreak(),P("Costs and uncertainty",head),P("Source-cohort 95% type-7 intervals",head)]
    rows=[["Source cohort","Hedge mean, absolute interval","Paired difference vs q0"]]
    for y in ("2023","2024","2025"):
        c=d['confidence_intervals'][y];rows.append([ci_label(y),ci(c['absolute']),ci(c['paired_vs_q0'])])
    story += [table(rows,[25,76,75]),Spacer(1,3*mm),P("Intervals are source-provided for 2023 full year, 2024 full year, and 2025 Jan-Aug. These are previously inspected historical samples, not holdouts or predictive validation. Filtered Jan-Aug 2023 and Jan-Aug 2024 cohorts have no computed intervals. No common-window confidence intervals or between-year p-values were computed.",small),P("Six modeled cost components",head)]
    rows=[["Cohort","Option fees","Stock fees","Borrow","Premium funding","Hedge funding","Slippage"]]
    for n in COHORTS:
        c=d["cohorts"][n]["cost_totals"]
        rows.append([label(n),money(c["option_fees"]),money(c["stock_fees"]),money(c["residual_short_borrow"]),money(c["premium_debit_funding"]),money(c["hedge_funding"]),money(c["stock_slippage"])])
    story += [table(rows,[32,22,22,22,26,26,26]),Spacer(1,4*mm),P("36-case sensitivity per year",head),P("Each sensitivity mean is net USD per expiry; the six cost component figures above are cohort totals in USD.",small)]
    rows=[["Year","Fill","Cost","Slip","Funding","n","Mean"]]
    for y in ("2024","2025"):
        for r in d['sensitivity'][y]:rows.append([y,r['fill'],r['cost_mode'],f"{r['slippage_bp']} bp",r['funding'].replace("_"," "),str(r['n']),money(r['mean'])])
    story += [table(rows,[15,28,22,18,42,12,39]),Spacer(1,3*mm),P("Method and provenance",head),P("Expiry morning SPY open selects quantity using the frozen selected strike + $0.01 rule, with 1e-10 tolerance. The modeled stock purchase occurs at expiry close; the residual closes at the next session open. Options use one-calendar-day DTE from entry close to expiry close. The stock holding can span weekends. The option package is 10 short SPY and one long SPXW, multiplier 100."),P("The original fixed-500 arm was the formal primary arm; this morning arm was secondary. These are previously inspected historical samples, not holdouts or predictive validation. The 2024 cohort covers expiries 2024-01-03 through 2024-12-31, with final next-session cover open on 2025-01-02. No rule tuning or outcome-based date selection is used."),P("15:59 quote-clock verification is unavailable for 2023 and verified for 2024/2025. Later closing references have execution limits. Trades are daily theoretical fills and do not establish operational edge. These are previously inspected historical samples, not holdouts or predictive validation."),P("Provenance hashes",head),P(f"Aggregate SHA-256 {validation['aggregate_sha256']} · run receipt SHA-256 {validation.get('run_receipt_sha256','synthetic')}",small),P(f"Comparison builder Git SHA {d['run']['git_sha']} · builder file SHA-256 {d['run']['loaded_code_sha256']}",small),P(f"Source evaluator Git SHAs: 2023 {d['source_evaluator_git_shas']['2023']} · 2024/2025 {d['source_evaluator_git_shas']['2024_2025']}",small),P(f"Checker SHA-256 {validation['checker']['sha256']} · input manifest SHA-256 {d['run'].get('manifest_sha256','not present in synthetic fixture')} · protocol SHA-256 {d['run'].get('protocol_sha256','not present in synthetic fixture')}",small)]
    doc.build(story)


def fixture():
    # Small, explicitly synthetic fixture used only to test guards and page layout.
    costs={k:1.0 for k in COSTS};coh={}
    for n in COHORTS:coh[n]={"n":12,"mean":1.5,"median":1.0,"q0_control_mean":4.0,"total":18.0,"positive_fraction":.6,"gross_total":30.0,"cost_total":6.0,"cost_totals":costs,"overnight_total":-2.0,"dividend_total":1.0,"option_baseline_total":31.0,"retained_costs_net_minus_overnight":20.0,"q_counts":{"0":4,"1000":8},"assignment_counts":{"true":5,"false":7},"residual_counts":{"long":3,"short":2,"zero":7}}
    monthly={y:{f"{y}-{m:02d}":{"n":0,"mean":None,"median":None,"q0_control_mean":None,"total":0.0,"positive_fraction":None,"gross_total":0.0,"cost_totals":costs,"cost_total":0.0,"overnight_total":0.0,"dividend_total":0.0,"option_baseline_total":0.0,"retained_costs_net_minus_overnight":None,"q_counts":{"0":0,"1000":0},"assignment_counts":{"true":0,"false":0},"residual_counts":{"long":0,"short":0,"zero":0}} for m in range(1,13)} for y in ("2023","2024","2025")}
    sens=[]
    for fill in ("midpoint","halfway","full_cross"):
      for cm in ("base","stress"):
       for bp in (0,1,5):
        for fund in ("gross_prefunding","assignment_cash_net"):sens.append({"fill":fill,"cost_mode":cm,"slippage_bp":bp,"funding":fund,"n":12,"mean":1.0,"cost_means":costs})
    ci={y:{k:{"mean":1.0,"low_95":-1.0,"high_95":3.0,"n":12} for k in ("absolute","paired_vs_q0")} for y in ("2023","2024","2025")}
    tail={n:{str(k):{"top_removed_mean":1.0,"bottom_removed_mean":1.0,"n_remaining":12-k} for k in (1,5,10)} for n in COHORTS}
    return {"schema_version":1,"status":"SUMMARIZED_NOT_VALIDATED","synthetic_fixture":True,"cohorts":coh,"monthly":monthly,"sensitivity":{"2024":[dict(row) for row in sens],"2025":[dict(row) for row in sens]},"confidence_intervals":ci,"tail_removals":tail,"source_hashes":{"fixture":"0"*64},"source_evaluator_git_shas":{"2023":"64e72887b782fdf838257a09877ffb817dfbfbdf","2024_2025":"44ed294deddb85df594ad1e1c8a5a91bb22d08d7"},"run":{"git_sha":"0"*40,"loaded_code_sha256":"0"*64,"manifest_sha256":"0"*64,"protocol_sha256":"0"*64}}


def render_synthetic(out):
    d=fixture()
    for year_index,year in enumerate(("2024","2025")):
        for row_index,row in enumerate(d["sensitivity"][year]):row["mean"]=1001+year_index*36+row_index
    findings={"verdict":"SYNTHETIC ONLY. No evaluation was run.","findings":["Synthetic layout and pagination check."]};validation={"aggregate_sha256":"0"*64,"checker":{"sha256":"0"*64}}
    out.mkdir(parents=True,exist_ok=False);(out/"report.md").write_text("# Synthetic report check\n\nSYNTHETIC ONLY. No evaluation was run.\n")
    render_pdf(d,findings,validation,out/"report.pdf")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--input",type=Path);p.add_argument("--input-sha256");p.add_argument("--run-receipt",type=Path);p.add_argument("--run-receipt-sha256");p.add_argument("--validation",type=Path);p.add_argument("--validation-sha256");p.add_argument("--findings",type=Path);p.add_argument("--findings-sha256");p.add_argument("--output-dir",required=True,type=Path);p.add_argument("--self-test",action="store_true");a=p.parse_args(argv)
    if a.self_test:
        if a.input or a.run_receipt or a.validation or a.findings:raise ValueError("synthetic self-test does not accept real inputs")
        render_synthetic(a.output_dir);return 0
    for path,digest,name in ((a.input,a.input_sha256,"input"),(a.run_receipt,a.run_receipt_sha256,"run receipt"),(a.validation,a.validation_sha256,"validation"),(a.findings,a.findings_sha256,"findings")):
        if not path or not digest or file_sha(path)!=digest:raise ValueError(f"{name} path and matching hash required")
    data=json.loads(a.input.read_text());run_receipt=json.loads(a.run_receipt.read_text());validation=json.loads(a.validation.read_text());findings=json.loads(a.findings.read_text())
    validate_aggregate(data)
    validate_receipts(data,(a.input,a.input_sha256),run_receipt,(a.run_receipt,a.run_receipt_sha256),validation,findings,(a.validation,a.validation_sha256),(a.findings,a.findings_sha256))
    validation["receipt_sha256"]=a.validation_sha256
    out=a.output_dir.absolute();allowed=Path(__file__).resolve().parents[1]/"planning/morning-three-year-report-20261030"
    if out.exists() or out.is_symlink() or out.parent.resolve()!=allowed.resolve():raise ValueError("real report output must be a fresh direct child of the ignored planning directory")
    if subprocess.run(["git","check-ignore","-q",str(out)],cwd=Path(__file__).resolve().parents[1]).returncode:raise ValueError("real report output path is not Git-ignored")
    stage=Path(tempfile.mkdtemp(prefix=".three-year-report-stage-",dir=allowed))
    try:
        (stage/"report.md").write_text(markdown(data,findings,validation))
        render_pdf(data,findings,validation,stage/"report.pdf")
        validate_receipts(data,(a.input,a.input_sha256),run_receipt,(a.run_receipt,a.run_receipt_sha256),validation,findings,(a.validation,a.validation_sha256),(a.findings,a.findings_sha256))
        os.replace(stage,out)
    except BaseException:
        raise
    return 0


if __name__=="__main__":raise SystemExit(main())
